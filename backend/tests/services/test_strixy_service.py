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
    assert [tool["name"] for tool in sent["tools"]] == ["read_case_sources"]
    assert sent["tools"][0]["strict"] is True
    assert sent["text"]["format"]["strict"] is True
    assert "previous_response_id" not in sent


def test_missing_vault_key_never_calls_provider():
    service = StrixyService(None)
    with patch("app.services.strixy_service.OpenAI") as factory:
        with pytest.raises(ValidationException):
            service.generate([], StrixyConfig(), 12)
        factory.assert_not_called()


def test_responses_adapter_translates_function_request_without_executing_it():
    client = MagicMock()
    client.__enter__.return_value = client
    request = Mock(
        type="function_call",
        arguments='{"action":"search","source_id":null,"query":"Ada"}',
    )
    request.name = "read_case_sources"
    client.responses.create.return_value = Mock(
        status="completed", output_text="", output=[request], usage=None
    )
    service = StrixyService("fake")
    with patch("app.services.strixy_service.OpenAI", return_value=client):
        reply = service.generate(
            [ChatMessage(role="user", content="Find Ada")], StrixyConfig(), 12
        )
    assert reply.tool_requests == [
        {
            "name": "read_case_sources",
            "arguments": {"action": "search", "source_id": None, "query": "Ada"},
        }
    ]
    assert reply.content == "" and reply.citations == []


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
