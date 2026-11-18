"""Provider protocol translation; the HTTP lifecycle tests own application behavior."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from app.core.exceptions import ValidationException
from app.core.strixy_config import StrixyConfig
from app.schemas.strixy_schema import ChatMessage, ModelMessage, VisualInput
from app.services.strixy_service import StrixyService


@pytest.mark.parametrize("limited", [False, True])
def test_responses_adapter_bounds_usage_and_withholds_incomplete_json(limited):
    client = MagicMock()
    client.__enter__.return_value = client
    client.responses.create.return_value = Mock(
        status="incomplete" if limited else "completed",
        incomplete_details=Mock(reason="max_output_tokens") if limited else None,
        output_text='{"content":"Useful text","citations":[]}',
        output=[],
        usage=Mock(input_tokens=10, output_tokens=20),
    )
    service = StrixyService("fake")
    config = StrixyConfig()
    with patch("app.services.strixy_service.OpenAI", return_value=client) as factory:
        result = service.generate(
            [
                ModelMessage(
                    role="user",
                    content="Question",
                    images=[
                        VisualInput(
                            source_id="evidence:2",
                            field="attachment:page:1:image",
                            data="cGl4ZWxz",
                        )
                    ],
                )
            ],
            config,
            12,
        )
    assert result.content == ("" if limited else "Useful text")
    assert result.limit_code == ("output_limit" if limited else None)
    assert (result.input_tokens, result.output_tokens) == (10, 20)
    assert factory.call_args.kwargs["max_retries"] == 0
    assert factory.call_args.kwargs["timeout"] == 12
    sent = client.responses.create.call_args.kwargs
    assert sent["model"] == "gpt-6-astra"
    assert sent["reasoning"] == {"effort": "low"}
    assert sent["input"][1]["role"] == "user"
    image_parts = sent["input"][1]["content"]
    assert '"source_id": "evidence:2"' in image_parts[0]["text"]
    assert image_parts[1] == {
        "type": "input_image",
        "detail": "high",
        "image_url": "data:image/png;base64,cGl4ZWxz",
    }
    assert sent["store"] is False
    assert sent["max_output_tokens"] == config.max_output_tokens
    assert not {"tools", "parallel_tool_calls"} & sent.keys()
    assert sent["text"]["format"]["strict"] is True
    assert "previous_response_id" not in sent


def test_missing_vault_key_never_calls_provider():
    service = StrixyService(None)
    with patch("app.services.strixy_service.OpenAI") as factory:
        with pytest.raises(ValidationException):
            service.generate([], StrixyConfig(), 12)
        factory.assert_not_called()


def test_streams_only_visible_answer_content_and_retains_incomplete_output():
    client = MagicMock()
    client.__enter__.return_value = client
    stream = MagicMock()
    stream.__enter__.return_value = stream
    stream.__iter__.return_value = iter(
        [
            Mock(type="response.reasoning_text.delta", delta="private reasoning"),
            Mock(type="response.output_text.delta", delta='{"content":"A useful'),
            Mock(type="response.output_text.delta", delta=" partial finding"),
            Mock(
                type="response.incomplete",
                response=Mock(
                    status="incomplete",
                    incomplete_details=Mock(reason="max_output_tokens"),
                    output_text='{"content":"A useful partial finding',
                    output=[],
                    usage=Mock(input_tokens=10, output_tokens=16),
                ),
            ),
        ]
    )
    client.responses.create.return_value = stream
    updates = []
    service = StrixyService("fake", on_progress=updates.append)
    with patch("app.services.strixy_service.OpenAI", return_value=client):
        result = service.generate(
            [ChatMessage(role="user", content="Question")], StrixyConfig(), 12
        )
    assert updates[0].content == "A useful"
    assert result.content == "A useful partial finding"
    assert result.limit_code == "output_limit"
    assert result.citations == []
    assert "private reasoning" not in str(updates)
    sent = client.responses.create.call_args.kwargs
    assert sent["stream"] is True
    assert sent["model"] == "gpt-6-astra"
    assert sent["reasoning"] == {"effort": "low"}


def test_streaming_preserves_complete_citations_before_output_limit():
    client = MagicMock()
    client.__enter__.return_value = client
    citation = {"source_id": "case:1", "field": "title", "excerpt": "Known fact"}
    import json

    text = json.dumps({"content": "Finding", "citations": [citation]})[:-2]
    stream = MagicMock()
    stream.__enter__.return_value = stream
    stream.__iter__.return_value = iter(
        [
            Mock(type="response.output_text.delta", delta=text),
            Mock(
                type="response.incomplete",
                response=Mock(
                    status="incomplete",
                    incomplete_details=Mock(reason="max_output_tokens"),
                    output_text=text,
                    output=[],
                    usage=None,
                ),
            ),
        ]
    )
    client.responses.create.return_value = stream
    updates = []
    service = StrixyService("fake", on_progress=updates.append)
    with patch("app.services.strixy_service.OpenAI", return_value=client):
        reply = service.generate([], StrixyConfig(), 12)
    assert updates[0].citations == [citation]
    assert reply.citations == [citation]
    assert reply.content == "Finding"
    assert reply.limit_code == "output_limit"


COMPAT = StrixyConfig(
    provider="openai_compatible", base_url="http://10.0.0.5:11434/v1", model="llama3"
)
ANTHROPIC = StrixyConfig(provider="anthropic", model="claude-sonnet-5-5")
VISUAL_QUESTION = ModelMessage(
    role="user",
    content="Question",
    images=[
        VisualInput(
            source_id="evidence:2", field="attachment:page:1:image", data="cGl4"
        )
    ],
)


def context_client() -> MagicMock:
    client = MagicMock()
    client.__enter__.return_value = client
    return client


def completion(content="", finish="stop", usage=(10, 20)):
    return Mock(
        choices=[Mock(finish_reason=finish, message=Mock(content=content))],
        usage=Mock(prompt_tokens=usage[0], completion_tokens=usage[1]),
    )


def chunk(content=None, finish=None):
    return Mock(
        choices=[Mock(finish_reason=finish, delta=Mock(content=content))],
        usage=None,
    )


@pytest.mark.parametrize("limited", [False, True])
def test_compatible_adapter_sends_chat_completions_without_reasoning(limited):
    client = context_client()
    client.chat.completions.create.return_value = completion(
        '{"content":"Useful text","citations":[]}',
        finish="length" if limited else "stop",
    )
    with patch("app.services.strixy_service.OpenAI", return_value=client) as factory:
        result = StrixyService("local-key").generate(
            [
                ChatMessage(role="system", content="Earlier note"),
                VISUAL_QUESTION,
            ],
            COMPAT,
            12,
        )
    assert result.content == ("" if limited else "Useful text")
    assert result.limit_code == ("output_limit" if limited else None)
    assert (result.input_tokens, result.output_tokens) == (10, 20)
    assert factory.call_args.kwargs == {
        "base_url": "http://10.0.0.5:11434/v1",
        "api_key": "local-key",
        "max_retries": 0,
        "timeout": 12,
    }
    client.responses.create.assert_not_called()
    sent = client.chat.completions.create.call_args.kwargs
    assert sent["model"] == "llama3"
    assert sent["max_tokens"] == COMPAT.max_output_tokens
    assert not {"tools", "parallel_tool_calls"} & sent.keys()
    assert sent["stream"] is False
    assert not {"reasoning", "reasoning_effort", "store"} & sent.keys()
    assert [m["role"] for m in sent["messages"]] == ["system", "user"]
    assert sent["messages"][0]["content"] == COMPAT.instructions + "\n\nEarlier note"
    user_parts = sent["messages"][1]["content"]
    assert user_parts[0] == {"type": "text", "text": "Question"}
    assert '"source_id": "evidence:2"' in user_parts[1]["text"]
    assert user_parts[2] == {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64,cGl4"},
    }
    assert sent["response_format"]["type"] == "json_schema"
    assert sent["response_format"]["json_schema"]["strict"] is True
    assert sent["response_format"]["json_schema"]["name"] == "grounded_answer"


def test_compatible_adapter_streams_visible_content():
    client = context_client()
    stream = MagicMock()
    stream.__enter__.return_value = stream
    usage_chunk = Mock(choices=[], usage=Mock(prompt_tokens=7, completion_tokens=9))
    stream.__iter__.return_value = iter(
        [
            chunk(content='{"content":"A useful'),
            chunk(content=' finding","citations":[]}', finish="stop"),
            usage_chunk,
        ]
    )
    client.chat.completions.create.return_value = stream
    updates = []
    with patch("app.services.strixy_service.OpenAI", return_value=client):
        reply = StrixyService("k", on_progress=updates.append).generate(
            [ChatMessage(role="user", content="Question")], COMPAT, 12
        )
    sent = client.chat.completions.create.call_args.kwargs
    assert sent["stream"] is True
    assert sent["stream_options"] == {"include_usage": True}
    assert updates[0].content == "A useful"
    assert reply.content == "A useful finding"
    assert (reply.input_tokens, reply.output_tokens) == (7, 9)


def test_compatible_stream_retains_partial_answer_at_the_length_limit():
    client = context_client()
    stream = MagicMock()
    stream.__enter__.return_value = stream
    stream.__iter__.return_value = iter(
        [
            chunk(content='{"content":"Partial finding'),
            chunk(finish="length"),
            Mock(choices=[], usage=Mock(prompt_tokens=3, completion_tokens=4)),
        ]
    )
    client.chat.completions.create.return_value = stream
    with patch("app.services.strixy_service.OpenAI", return_value=client):
        reply = StrixyService("k", on_progress=lambda _: None).generate([], COMPAT, 12)
    assert reply.content == "Partial finding"
    assert reply.limit_code == "output_limit"


def message(stop="end_turn", content=(), usage=(10, 20)):
    return Mock(
        stop_reason=stop,
        content=list(content),
        usage=Mock(input_tokens=usage[0], output_tokens=usage[1]),
    )


def text_block(text):
    return Mock(type="text", text=text)


@pytest.mark.parametrize("limited", [False, True])
def test_anthropic_adapter_sends_structured_output_and_effort(limited):
    client = context_client()
    client.messages.create.return_value = message(
        "max_tokens" if limited else "end_turn",
        [text_block('{"content":"Useful text","citations":[]}')],
    )
    with patch("app.services.strixy_service.Anthropic", return_value=client) as factory:
        result = StrixyService("sk-ant").generate(
            [
                ChatMessage(role="system", content="Earlier note"),
                ChatMessage(role="user", content="First"),
                ChatMessage(role="assistant", content="Answer"),
                VISUAL_QUESTION,
            ],
            ANTHROPIC,
            12,
        )
    assert result.content == ("" if limited else "Useful text")
    assert result.limit_code == ("output_limit" if limited else None)
    assert (result.input_tokens, result.output_tokens) == (10, 20)
    assert factory.call_args.kwargs == {
        "api_key": "sk-ant",
        "max_retries": 0,
        "timeout": 12,
    }
    sent = client.messages.create.call_args.kwargs
    assert sent["model"] == "claude-sonnet-5-5"
    assert sent["max_tokens"] == ANTHROPIC.max_output_tokens
    assert sent["system"] == f"{ANTHROPIC.instructions}\n\nEarlier note"
    assert [m["role"] for m in sent["messages"]] == ["user", "assistant", "user"]
    final_blocks = sent["messages"][2]["content"]
    assert final_blocks[0] == {"type": "text", "text": "Question"}
    assert '"source_id": "evidence:2"' in final_blocks[1]["text"]
    assert final_blocks[2] == {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/png", "data": "cGl4"},
    }
    assert sent["output_config"]["effort"] == "low"
    assert sent["output_config"]["format"]["type"] == "json_schema"
    assert sent["output_config"]["format"]["schema"]["required"] == [
        "content",
        "citations",
    ]
    assert not {"tools", "tool_choice"} & sent.keys()
    assert "stream" not in sent


def test_anthropic_adapter_streams_only_answer_text_deltas():
    client = context_client()
    stream = MagicMock()
    stream.__enter__.return_value = stream
    delta = lambda kind, **kw: Mock(  # noqa: E731
        type="content_block_delta", delta=Mock(type=kind, **kw)
    )
    stream.__iter__.return_value = iter(
        [
            Mock(type="message_start"),
            delta("thinking_delta", thinking="private reasoning"),
            delta("text_delta", text='{"content":"A useful'),
            delta("text_delta", text=' partial finding"'),
        ]
    )
    stream.get_final_message.return_value = message(
        "max_tokens", [text_block('{"content":"A useful partial finding"')], (5, 6)
    )
    client.messages.stream.return_value = stream
    updates = []
    with patch("app.services.strixy_service.Anthropic", return_value=client):
        reply = StrixyService("k", on_progress=updates.append).generate(
            [ChatMessage(role="user", content="Question")], ANTHROPIC, 12
        )
    client.messages.create.assert_not_called()
    assert updates[0].content == "A useful"
    assert "private reasoning" not in str(updates)
    assert reply.content == "A useful partial finding"
    assert reply.limit_code == "output_limit"
    assert (reply.input_tokens, reply.output_tokens) == (5, 6)
    assert client.messages.stream.call_args.kwargs["output_config"]["effort"] == "low"


def test_missing_key_message_names_the_configured_provider():
    with pytest.raises(ValidationException, match="Anthropic API key not configured"):
        StrixyService(None).generate([], ANTHROPIC, 12)


OPENROUTER = StrixyConfig(
    provider="openrouter",
    base_url="https://openrouter.ai/api/v1",
    model="vendor/model",
    reasoning_effort="medium",
)
ANSWER = '{"content":"Useful text","citations":[]}'
QUESTION = [ChatMessage(role="user", content="Q")]


def test_openrouter_requires_parameters_and_sends_effort_without_echoing_it():
    client = context_client()
    client.chat.completions.create.return_value = completion(ANSWER)
    with patch("app.services.strixy_service.OpenAI", return_value=client) as factory:
        StrixyService("or-key").generate(QUESTION, OPENROUTER, 12)
    assert factory.call_args.kwargs["base_url"] == "https://openrouter.ai/api/v1"
    sent = client.chat.completions.create.call_args.kwargs
    assert sent["extra_body"] == {
        "provider": {"require_parameters": True},
        "reasoning": {"effort": "medium", "exclude": True},
    }
    # Any parameter an endpoint doesn't list makes require_parameters exclude it.
    assert not {"tools", "parallel_tool_calls"} & sent.keys()
    client.responses.create.assert_not_called()


def test_openrouter_without_an_effort_sends_no_reasoning():
    client = context_client()
    client.chat.completions.create.return_value = completion(ANSWER)
    config = OPENROUTER.model_copy(update={"reasoning_effort": None})
    with patch("app.services.strixy_service.OpenAI", return_value=client):
        StrixyService("or-key").generate(QUESTION, config, 12)
    sent = client.chat.completions.create.call_args.kwargs
    assert sent["extra_body"] == {"provider": {"require_parameters": True}}


def test_compatible_adapter_sends_no_extra_body():
    client = context_client()
    client.chat.completions.create.return_value = completion(ANSWER)
    with patch("app.services.strixy_service.OpenAI", return_value=client):
        StrixyService("k").generate(QUESTION, COMPAT, 12)
    assert "extra_body" not in client.chat.completions.create.call_args.kwargs


def test_responses_adapter_omits_reasoning_without_an_effort():
    client = context_client()
    client.responses.create.return_value = Mock(
        status="completed", output_text=ANSWER, output=[], usage=None
    )
    config = StrixyConfig(reasoning_effort=None)
    with patch("app.services.strixy_service.OpenAI", return_value=client):
        StrixyService("k").generate(QUESTION, config, 12)
    assert "reasoning" not in client.responses.create.call_args.kwargs


def test_anthropic_adapter_omits_effort_without_one():
    client = context_client()
    client.messages.create.return_value = message("end_turn", [text_block(ANSWER)])
    config = ANTHROPIC.model_copy(update={"reasoning_effort": None})
    with patch("app.services.strixy_service.Anthropic", return_value=client):
        StrixyService("k").generate(QUESTION, config, 12)
    sent = client.messages.create.call_args.kwargs
    assert "effort" not in sent["output_config"]
    assert sent["output_config"]["format"]["type"] == "json_schema"


def test_chat_completions_error_finish_reason_fails_the_run():
    client = context_client()
    client.chat.completions.create.return_value = completion("", finish="error")
    with patch("app.services.strixy_service.OpenAI", return_value=client):
        with pytest.raises(RuntimeError, match="did not complete"):
            StrixyService("k").generate(QUESTION, OPENROUTER, 12)
