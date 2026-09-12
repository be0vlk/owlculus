"""Small stateless OpenAI Responses adapter; application state stays in PostgreSQL."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from time import monotonic
from typing import cast

from openai import OpenAI, Stream
from openai.types.responses import Response, ResponseInputParam, ResponseStreamEvent
from pydantic import ValidationError
from pydantic_core import from_json
from sqlmodel import Session

from app.core.exceptions import ValidationException
from app.core.strixy_config import StrixyConfig
from app.schemas.strixy_schema import (
    ChatMessage,
    GroundedAnswer,
    SourceCitation,
    SourceQuery,
)
from app.services.api_key_vault import ApiKeyVault, ConfigurationApiKeyVault, Provider


@dataclass(frozen=True)
class ProviderReply:
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    limit_code: str | None = None
    citations: list[dict] = field(default_factory=list)
    tool_requests: list[dict] = field(default_factory=list)


class StrixyService:
    def __init__(
        self,
        db: Session,
        api_key_vault: ApiKeyVault | None = None,
        on_progress: Callable[[ProviderReply], None] | None = None,
    ):
        self.on_progress = on_progress
        vault = api_key_vault or ConfigurationApiKeyVault(db)
        self.api_key = vault.get_key(Provider.OPENAI)

    def generate(
        self, messages: list[ChatMessage], config: StrixyConfig, timeout: float
    ) -> ProviderReply:
        key = self.api_key
        if not key:
            raise ValidationException("OpenAI API key not configured")
        # No SDK retries: an uncertain completion must require explicit human action.
        partial = ProviderReply("")
        streaming = bool(self.on_progress and config.supports_streaming)
        with OpenAI(api_key=key, max_retries=0, timeout=timeout) as client:
            result = client.responses.create(
                model=config.model,
                instructions=config.instructions,
                input=cast(ResponseInputParam, [m.model_dump() for m in messages]),
                max_output_tokens=config.max_output_tokens,
                store=False,
                stream=streaming,
                tools=[
                    {
                        "type": "function",
                        "name": "read_case_sources",
                        "description": "List, search or read the bounded authorized Case sources. No Case or identity overrides.",
                        "parameters": SourceQuery.model_json_schema(),
                        "strict": True,
                    }
                ],
                parallel_tool_calls=False,
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
        requests = [
            {"name": item.name, "arguments": json.loads(item.arguments)}
            for item in response.output
            if item.type == "function_call"
        ]
        if not response.output_text and not limit and not requests:
            raise RuntimeError("Provider returned no answer")
        # Complete answers require the full schema; limited streams retain decoded visible fields.
        answer = (
            GroundedAnswer.model_validate_json(response.output_text)
            if response.output_text and not limit
            else None
        )
        return ProviderReply(
            content=answer.content if answer else partial.content,
            citations=(
                [c.model_dump() for c in answer.citations]
                if answer
                else partial.citations
            ),
            tool_requests=requests,
            input_tokens=response.usage.input_tokens if response.usage else 0,
            output_tokens=response.usage.output_tokens if response.usage else 0,
            limit_code=limit,
        )

    def consume_stream(
        self, stream: Stream[ResponseStreamEvent], config: StrixyConfig
    ) -> tuple[Response, ProviderReply]:
        """Only the structured answer's content is visible, never reasoning/tool deltas.

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
