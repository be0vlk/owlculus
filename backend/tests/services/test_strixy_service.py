"""Provider protocol translation; the HTTP lifecycle tests own application behavior."""

from unittest.mock import MagicMock, Mock, patch

import pytest
from app.core.exceptions import ValidationException
from app.core.strixy_config import StrixyConfig
from app.schemas.strixy_schema import ChatMessage
from app.services.api_key_vault import Provider, StaticApiKeyVault
from app.services.strixy_service import StrixyService


@pytest.mark.parametrize("limited", [False, True])
def test_responses_adapter_bounds_usage_and_retains_partial_text(limited):
    client = MagicMock()
    client.__enter__.return_value = client
    client.responses.create.return_value = Mock(
        status="incomplete" if limited else "completed",
        incomplete_details=Mock(reason="max_output_tokens") if limited else None,
        output_text="Useful text",
        usage=Mock(input_tokens=10, output_tokens=20),
    )
    service = StrixyService(Mock(), StaticApiKeyVault({Provider.OPENAI: "fake"}))
    config = StrixyConfig()
    with patch("app.services.strixy_service.OpenAI", return_value=client) as factory:
        result = service.generate(
            [ChatMessage(role="user", content="Question")], config, 12
        )
    assert result.content == "Useful text"
    assert result.limit_code == ("output_limit" if limited else None)
    assert (result.input_tokens, result.output_tokens) == (10, 20)
    assert factory.call_args.kwargs["max_retries"] == 0
    assert factory.call_args.kwargs["timeout"] == 12
    sent = client.responses.create.call_args.kwargs
    assert sent["store"] is False
    assert sent["max_output_tokens"] == config.max_output_tokens
    assert "tools" not in sent and "previous_response_id" not in sent


def test_missing_vault_key_never_calls_provider():
    service = StrixyService(Mock(), StaticApiKeyVault({}))
    with patch("app.services.strixy_service.OpenAI") as factory:
        with pytest.raises(ValidationException):
            service.generate([], StrixyConfig(), 12)
        factory.assert_not_called()
