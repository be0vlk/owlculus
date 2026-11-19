"""Setup-screen provider lookups, with every SDK client patched."""

from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch

import anthropic
import httpx
import openai
import pytest
from openai.types import Model

from app.core.exceptions import ValidationException
from app.core.strixy_config import StrixyConfig
from app.schemas.strixy_schema import GroundedAnswer
from app.services import strixy_setup
from app.services.strixy_service import ProviderReply

REQUEST = httpx.Request("GET", "https://provider.example/v1")


def context_client() -> MagicMock:
    client = MagicMock()
    client.__enter__.return_value = client
    return client


def openai_model(model_id, created=1, **extra) -> Model:
    return Model(id=model_id, created=created, object="model", owned_by="x", **extra)


def test_openai_models_are_newest_first_with_unknown_capabilities():
    client = context_client()
    client.models.list.return_value = [
        openai_model("old", 1),
        openai_model("new", 9),
    ]
    with patch("app.services.strixy_setup.OpenAI", return_value=client) as factory:
        models = strixy_setup.list_models("openai", None, "sk")
    assert models == [
        {"id": "new", "name": "new", "vision": None, "efforts": None},
        {"id": "old", "name": "old", "vision": None, "efforts": None},
    ]
    assert factory.call_args.kwargs["api_key"] == "sk"
    assert factory.call_args.kwargs["max_retries"] == 0


def test_compatible_models_use_the_given_base_url_and_ids_only():
    client = context_client()
    client.models.list.return_value = [openai_model("llama3")]
    with patch("app.services.strixy_setup.OpenAI", return_value=client) as factory:
        models = strixy_setup.list_models("openai_compatible", "http://x/v1", "k")
    assert factory.call_args.kwargs["base_url"] == "http://x/v1"
    assert models == [
        {"id": "llama3", "name": "llama3", "vision": None, "efforts": None}
    ]


def test_openrouter_keeps_structured_output_models_with_capabilities():
    client = context_client()
    client.models.list.return_value = [
        openai_model(
            "vendor/full",
            name="Full",
            supported_parameters=["tools", "structured_outputs", "reasoning"],
            architecture={"input_modalities": ["text", "image"]},
        ),
        openai_model(
            "vendor/plain",
            name="Plain",
            supported_parameters=["tools", "structured_outputs"],
            architecture={"input_modalities": ["text"]},
        ),
        openai_model(
            "vendor/no-tools",
            name="No tools",
            supported_parameters=["structured_outputs"],
            architecture={"input_modalities": ["text"]},
        ),
        openai_model("vendor/tools-only", supported_parameters=["tools"]),
        openai_model("vendor/bare"),
    ]
    with patch("app.services.strixy_setup.OpenAI", return_value=client) as factory:
        models = strixy_setup.list_models("openrouter", "http://ignored", "k")
    assert factory.call_args.kwargs["base_url"] == "https://openrouter.ai/api/v1"
    assert models == [
        {"id": "vendor/full", "name": "Full", "vision": True, "efforts": None},
        {"id": "vendor/plain", "name": "Plain", "vision": False, "efforts": []},
        {"id": "vendor/no-tools", "name": "No tools", "vision": False, "efforts": []},
    ]


def anthropic_model(model_id, name, structured=True, image=True, effort=()):
    def support(on):
        return NS(supported=on)

    levels = {
        level: support(level in effort) for level in ("low", "medium", "high", "max")
    }
    return NS(
        id=model_id,
        display_name=name,
        capabilities=NS(
            structured_outputs=support(structured),
            image_input=support(image),
            effort=NS(supported=bool(effort), xhigh=None, **levels),
        ),
    )


def test_anthropic_models_filter_structured_outputs_and_map_capabilities():
    client = context_client()
    client.models.list.return_value = [
        anthropic_model("claude-a", "Claude A", effort=("low", "high")),
        anthropic_model("claude-b", "Claude B", image=False),
        anthropic_model("claude-old", "Claude Old", structured=False),
    ]
    with patch("app.services.strixy_setup.Anthropic", return_value=client):
        models = strixy_setup.list_models("anthropic", None, "k")
    client.models.list.assert_called_once_with(limit=1000)
    assert models == [
        {
            "id": "claude-a",
            "name": "Claude A",
            "vision": True,
            "efforts": ["low", "high"],
        },
        {"id": "claude-b", "name": "Claude B", "vision": False, "efforts": []},
    ]


def test_connection_succeeds_when_the_model_answers():
    reply = ProviderReply('{"content":"OK","citations":[]}')
    config = StrixyConfig(model="m")
    with patch("app.services.strixy_setup.StrixyService") as service:
        service.return_value.generate.return_value = reply
        result = strixy_setup.test_connection(config, "key")
    service.assert_called_once_with("key")
    assert result["ok"] is True and result["model"] == "m"
    assert isinstance(result["seconds"], float)
    assert service.return_value.generate.call_args.kwargs["timeout"] == 60


def test_connection_failure_is_reported_not_raised():
    with patch("app.services.strixy_setup.StrixyService") as service:
        service.return_value.generate.side_effect = RuntimeError(
            "Provider returned no answer"
        )
        result = strixy_setup.test_connection(StrixyConfig(), "k")
    assert result == {"ok": False, "message": "Provider returned no answer"}


def status_error(cls, status, message):
    response = httpx.Response(status, request=REQUEST)
    return cls(message, response=response, body=None)


def invalid_json() -> Exception:
    try:
        GroundedAnswer.model_validate_json("not json")
    except Exception as exc:
        return exc
    raise AssertionError


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (status_error(openai.AuthenticationError, 401, "bad"), "rejected the API key"),
        (
            status_error(anthropic.AuthenticationError, 401, "bad"),
            "rejected the API key",
        ),
        (
            status_error(openai.NotFoundError, 404, "No such model"),
            "Model or endpoint not found: No such model",
        ),
        (
            openai.APIConnectionError(message="refused", request=REQUEST),
            "Couldn't reach the provider: refused",
        ),
        (
            openai.APITimeoutError(request=REQUEST),
            "Couldn't reach the provider",
        ),
        (
            status_error(openai.BadRequestError, 400, "No endpoints found"),
            "Provider returned 400: No endpoints found",
        ),
        (
            openai.APIError("rate-limited upstream", request=REQUEST, body=None),
            "Provider error: rate-limited upstream",
        ),
        (invalid_json(), "structured outputs"),
        (ValidationException("API key not configured"), "API key not configured"),
        (RuntimeError("Provider did not complete the response"), "did not complete"),
    ],
)
def test_provider_errors_become_admin_readable_text(exc, expected):
    assert expected in strixy_setup.provider_error(exc)


def test_unknown_errors_do_not_leak_details():
    assert "secret" not in strixy_setup.provider_error(KeyError("secret"))


def test_chat_reason_uses_the_provider_message_and_hides_internal_errors():
    body = {"error": {"type": "overloaded_error", "message": "Overloaded"}}
    response = httpx.Response(529, request=REQUEST)
    overloaded = anthropic.APIStatusError(
        "Error code: 529 - {...}", response=response, body=body
    )
    assert (
        strixy_setup.provider_reason(overloaded) == "Provider returned 529: Overloaded"
    )
    assert strixy_setup.provider_reason(RuntimeError("sensitive")) is None
    long = openai.APIError("x" * 2000, request=REQUEST, body=None)
    assert len(strixy_setup.provider_reason(long)) <= 500
