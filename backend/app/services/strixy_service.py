"""Small stateless provider adapters; application state stays in PostgreSQL.

openai uses the Responses API, openai_compatible uses Chat Completions against
the configured base URL, and anthropic uses the Messages API. Each adapter sends
the messages, images and the answer JSON schema, and returns a ProviderReply.

Verified 2026-11-18 against official documentation:
https://platform.claude.com/docs/en/build-with-claude/structured-outputs
  Anthropic JSON outputs are GA: output_config={"format": {"type": "json_schema",
  "schema": {...}}}. It does not accept numeric or string constraints such as
  maxLength, so the schema passes through anthropic.transform_schema, which
  moves them into descriptions.
https://platform.claude.com/docs/en/build-with-claude/effort
  GA: output_config={"effort": "low"|"medium"|"high"|"xhigh"|"max"}. Sonnet 5.5
  supports all five, so STRIXY reasoning_effort is passed through unchanged;
  models outside that list (for example Haiku 4.5) reject the parameter.
https://platform.claude.com/docs/en/build-with-claude/streaming
  Text arrives as content_block_delta events with delta.type "text_delta";
  thinking arrives as "thinking_delta".
  stop_reason "max_tokens" means the output limit was hit.
  The pinned SDK (anthropic 2.10.0) takes output_config on its stable
  messages.create/messages.stream, so no beta namespace is needed.
https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create
  Chat Completions: response_format={"type": "json_schema", "json_schema":
  {"name", "schema", "strict"}}, finish_reason "length" at the token cap,
  stream_options={"include_usage": true} adds a final chunk with empty choices
  and usage. max_tokens is deprecated by OpenAI in favor of
  max_completion_tokens, but OpenAI-compatible servers honor max_tokens
  universally; no reasoning parameters are sent because many reject them.
https://openrouter.ai/docs/features/provider-routing
  openrouter reuses Chat Completions at https://openrouter.ai/api/v1.
  provider.require_parameters=true routes only to endpoints that honor every
  request parameter (response_format), instead of silently ignoring them.
  No data_collection or zdr preference is sent: the account's own privacy
  settings decide.
https://openrouter.ai/docs/use-cases/reasoning-tokens
  reasoning={"effort": ..., "exclude": true} sets effort and keeps reasoning
  out of the response; OpenRouter maps it to the nearest level the model has.
https://openrouter.ai/docs/features/structured-outputs
  response_format json_schema is passed through to endpoints that support it.
  A reply can end with finish_reason "error" when the upstream failed midway.
A reasoning_effort of None means the model default: no effort parameter is sent.
"""

import json
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from time import monotonic
from typing import Any, cast

from anthropic import Anthropic, transform_schema
from openai import OpenAI, Stream
from openai.types.chat import ChatCompletion, ChatCompletionMessageParam
from openai.types.responses import Response, ResponseInputParam, ResponseStreamEvent
from pydantic import ValidationError
from pydantic_core import from_json

from app.core.exceptions import ValidationException
from app.core.strixy_config import PROVIDER_NAMES, StrixyConfig
from app.schemas.strixy_schema import (
    ChatMessage,
    GroundedAnswer,
    ModelMessage,
    SourceCitation,
)


def message_text(message: ChatMessage, marker: str) -> str:
    """Case material is the only ModelMessage; the per-request marker keeps source
    text from closing the block it sits in."""
    if not isinstance(message, ModelMessage):
        return message.content
    return (
        f"BEGIN UNTRUSTED CASE MATERIAL {marker}\n{message.content}\n"
        f"END UNTRUSTED CASE MATERIAL {marker}"
    )


def response_input(messages: list[ChatMessage]) -> ResponseInputParam:
    items: list[dict] = []
    marker = secrets.token_hex(16)
    for message in messages:
        items.append({"role": message.role, "content": message_text(message, marker)})
        if isinstance(message, ModelMessage):
            for image in message.images:
                items.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": json.dumps(
                                    {
                                        "source_id": image.source_id,
                                        "field": image.field,
                                        "notice": "Untrusted Evidence visual input",
                                    }
                                ),
                            },
                            {
                                "type": "input_image",
                                "detail": "high",
                                "image_url": "data:image/png;base64," + image.data,
                            },
                        ],
                    }
                )
    return cast(ResponseInputParam, items)


def visual_label(image) -> str:
    return json.dumps(
        {
            "source_id": image.source_id,
            "field": image.field,
            "notice": "Untrusted Evidence visual input",
        }
    )


def chat_messages(
    messages: list[ChatMessage], config: StrixyConfig
) -> list[ChatCompletionMessageParam]:
    turns = merged_turns(
        messages,
        lambda data: {
            "type": "image_url",
            "image_url": {"url": "data:image/png;base64," + data},
        },
    )
    for turn in turns:
        # Many local servers accept only string content for text-only turns.
        if all(part["type"] == "text" for part in turn["content"]):
            turn["content"] = "\n\n".join(part["text"] for part in turn["content"])
    return cast(
        list[ChatCompletionMessageParam],
        [{"role": "system", "content": config.instructions}] + turns,
    )


def anthropic_messages(
    messages: list[ChatMessage], config: StrixyConfig
) -> tuple[str, list[dict]]:
    turns = merged_turns(
        messages,
        lambda data: {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": data},
        },
    )
    return config.instructions, turns


def merged_turns(
    messages: list[ChatMessage], image_part: Callable[[str], dict]
) -> list[dict]:
    marker = secrets.token_hex(16)
    turns: list[dict] = []

    def add(role: str, blocks: list[dict]) -> None:
        # Anthropic and strict local chat templates require alternating roles;
        # visual inputs are extra user turns.
        if turns and turns[-1]["role"] == role:
            turns[-1]["content"].extend(blocks)
        else:
            turns.append({"role": role, "content": blocks})

    for message in messages:
        if message.content:
            add(
                message.role,
                [{"type": "text", "text": message_text(message, marker)}],
            )
        if isinstance(message, ModelMessage):
            for image in message.images:
                add(
                    "user",
                    [
                        {"type": "text", "text": visual_label(image)},
                        image_part(image.data),
                    ],
                )
    return turns


@dataclass(frozen=True)
class ProviderReply:
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    limit_code: str | None = None
    citations: list[dict] = field(default_factory=list)


class StrixyService:
    def __init__(
        self,
        api_key: str | None,
        on_progress: Callable[[ProviderReply], None] | None = None,
    ):
        self.api_key, self.on_progress = api_key, on_progress

    def generate(
        self, messages: list[ChatMessage], config: StrixyConfig, timeout: float
    ) -> ProviderReply:
        if not self.api_key:
            raise ValidationException(
                f"{PROVIDER_NAMES[config.provider]} API key not configured"
            )
        if config.provider == "anthropic":
            return self.generate_anthropic(messages, config, timeout)
        if config.provider in {"openai_compatible", "openrouter"}:
            return self.generate_chat_completions(messages, config, timeout)
        return self.generate_responses(messages, config, timeout)

    def generate_responses(
        self, messages: list[ChatMessage], config: StrixyConfig, timeout: float
    ) -> ProviderReply:
        key = self.api_key
        # No SDK retries: an uncertain completion must require explicit human action.
        partial = ProviderReply("")
        streaming = bool(self.on_progress and config.supports_streaming)
        effort: dict[str, Any] = (
            {"reasoning": {"effort": config.reasoning_effort}}
            if config.reasoning_effort
            else {}
        )
        with OpenAI(api_key=key, max_retries=0, timeout=timeout) as client:
            result = client.responses.create(
                model=config.model,
                **effort,
                instructions=config.instructions,
                input=response_input(messages),
                max_output_tokens=config.max_output_tokens,
                store=False,
                stream=streaming,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "grounded_answer",
                        "schema": GroundedAnswer.model_json_schema(),
                        "strict": True,
                    }
                },
            )
            if streaming:
                response, partial = self.consume_stream(
                    cast(Stream[ResponseStreamEvent], result), config
                )
            else:
                response = cast(Response, result)
        limit = None
        if (
            response.status == "incomplete"
            and response.incomplete_details
            and response.incomplete_details.reason == "max_output_tokens"
        ):
            limit = "output_limit"
        elif response.status != "completed":
            raise RuntimeError("Provider did not complete the response")
        return build_reply(
            response.output_text,
            limit,
            partial,
            response.usage.input_tokens if response.usage else 0,
            response.usage.output_tokens if response.usage else 0,
        )

    def generate_chat_completions(
        self, messages: list[ChatMessage], config: StrixyConfig, timeout: float
    ) -> ProviderReply:
        streaming = bool(self.on_progress and config.supports_streaming)
        with OpenAI(
            base_url=config.base_url,
            api_key=self.api_key,
            max_retries=0,
            timeout=timeout,
        ) as client:
            extra: dict[str, Any] = (
                {"stream_options": {"include_usage": True}} if streaming else {}
            )
            if config.provider == "openrouter":
                body: dict[str, Any] = {"provider": {"require_parameters": True}}
                if config.reasoning_effort:
                    body["reasoning"] = {
                        "effort": config.reasoning_effort,
                        "exclude": True,
                    }
                extra["extra_body"] = body
            result = client.chat.completions.create(
                model=config.model,
                messages=chat_messages(messages, config),
                max_tokens=config.max_output_tokens,
                stream=streaming,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "grounded_answer",
                        "schema": GroundedAnswer.model_json_schema(),
                        "strict": True,
                    },
                },
                **extra,
            )
            partial = ProviderReply("")
            if streaming:
                text, finish, usage, partial = self.consume_chat_stream(result, config)
            else:
                completion = cast(ChatCompletion, result)
                choice = completion.choices[0]
                text = choice.message.content or ""
                finish, usage = choice.finish_reason, completion.usage
        if finish == "length":
            limit = "output_limit"
        elif finish in {"content_filter", "error"}:
            raise RuntimeError("Provider did not complete the response")
        else:
            limit = None
        return build_reply(
            text,
            limit,
            partial,
            usage.prompt_tokens if usage else 0,
            usage.completion_tokens if usage else 0,
        )

    def consume_chat_stream(self, stream, config: StrixyConfig):
        text, finish, usage = "", None, None
        partial, last_update = ProviderReply(""), 0.0
        with stream:
            for event in stream:
                if event.usage:
                    usage = event.usage
                if not event.choices:
                    continue
                choice = event.choices[0]
                finish = choice.finish_reason or finish
                if choice.delta.content:
                    text += choice.delta.content
                    partial, last_update = self.report_progress(
                        text, config, partial, last_update
                    )
        if finish is None:
            raise RuntimeError("Provider stream ended without completion")
        return text, finish, usage, partial

    def report_progress(
        self,
        text: str,
        config: StrixyConfig,
        partial: ProviderReply,
        last_update: float,
    ) -> tuple[ProviderReply, float]:
        assert self.on_progress is not None
        if len(text.encode()) > config.max_output_tokens * 64:
            raise RuntimeError("Provider output exceeded its bound")
        partial = partial_answer(text)
        if partial.content and monotonic() - last_update >= 0.25:
            self.on_progress(partial)
            last_update = monotonic()
        return partial, last_update

    def generate_anthropic(
        self, messages: list[ChatMessage], config: StrixyConfig, timeout: float
    ) -> ProviderReply:
        streaming = bool(self.on_progress and config.supports_streaming)
        system, turns = anthropic_messages(messages, config)
        request: dict[str, Any] = {
            "model": config.model,
            "max_tokens": config.max_output_tokens,
            "system": system,
            "messages": turns,
            "output_config": {
                **(
                    {"effort": config.reasoning_effort}
                    if config.reasoning_effort
                    else {}
                ),
                "format": {
                    "type": "json_schema",
                    "schema": transform_schema(GroundedAnswer.model_json_schema()),
                },
            },
        }
        partial = ProviderReply("")
        with Anthropic(api_key=self.api_key, max_retries=0, timeout=timeout) as client:
            if streaming:
                with client.messages.stream(**request) as stream:
                    text, last_update = "", 0.0
                    for event in stream:
                        if (
                            event.type == "content_block_delta"
                            and event.delta.type == "text_delta"
                        ):
                            text += event.delta.text
                            partial, last_update = self.report_progress(
                                text, config, partial, last_update
                            )
                    response = stream.get_final_message()
            else:
                response = client.messages.create(**request)
        if response.stop_reason == "max_tokens":
            limit = "output_limit"
        elif response.stop_reason in {"end_turn", "stop_sequence"}:
            limit = None
        else:
            raise RuntimeError("Provider did not complete the response")
        answer_text = "".join(b.text for b in response.content if b.type == "text")
        return build_reply(
            answer_text,
            limit,
            partial,
            response.usage.input_tokens,
            response.usage.output_tokens,
        )

    def consume_stream(
        self, stream: Stream[ResponseStreamEvent], config: StrixyConfig
    ) -> tuple[Response, ProviderReply]:
        """Only the structured answer's content is visible, never reasoning deltas.

        Verified against https://developers.openai.com/api/docs/guides/streaming-responses
        (2026-09-12). Checkpoints are cumulative snapshots, so reconnect needs no replay.
        """
        assert self.on_progress is not None
        text = ""
        partial = ProviderReply("")
        last_update = 0.0
        response = None
        with stream:
            for event in stream:
                if event.type == "response.output_text.delta":
                    text += event.delta
                    if len(text.encode()) > config.max_output_tokens * 64:
                        raise RuntimeError("Provider output exceeded its bound")
                    partial = partial_answer(text)
                    if partial.content and monotonic() - last_update >= 0.25:
                        self.on_progress(partial)
                        last_update = monotonic()
                elif (
                    event.type == "response.completed"
                    or event.type == "response.incomplete"
                ):
                    response = event.response
                elif event.type in {"response.failed", "error"}:
                    raise RuntimeError("Provider stream failed")
        if response is None:
            raise RuntimeError("Provider stream ended without completion")
        return response, partial


def build_reply(
    text: str,
    limit: str | None,
    partial: ProviderReply,
    input_tokens: int,
    output_tokens: int,
) -> ProviderReply:
    if not text and not limit:
        raise RuntimeError("Provider returned no answer")
    # Complete answers require the full schema; limited streams retain decoded visible fields.
    answer = GroundedAnswer.model_validate_json(text) if text and not limit else None
    return ProviderReply(
        content=answer.content if answer else partial.content,
        citations=(
            [c.model_dump() for c in answer.citations] if answer else partial.citations
        ),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        limit_code=limit,
    )


def partial_answer(text: str) -> ProviderReply:
    """Decode visible strings and only fully received citation fields from partial JSON."""
    try:
        visible = from_json(text, allow_partial="trailing-strings")
        complete_fields = from_json(text, allow_partial=True)
    except ValueError:
        return ProviderReply("")
    if not isinstance(visible, dict) or not isinstance(visible.get("content"), str):
        return ProviderReply("")
    citations = []
    if isinstance(complete_fields, dict) and isinstance(
        complete_fields.get("citations"), list
    ):
        for item in complete_fields["citations"]:
            try:
                citations.append(SourceCitation.model_validate(item).model_dump())
            except ValidationError:
                continue
    return ProviderReply(visible["content"], citations=citations)
