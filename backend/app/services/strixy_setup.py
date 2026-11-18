"""Stateless provider lookups for the admin Strixy setup screen.

Model lists and capabilities come from each provider's own models endpoint.
None means the provider does not say; an empty efforts list means the model
takes no reasoning effort.

Verified 2026-11-18 against official documentation:
https://openrouter.ai/docs/api-reference/list-available-models
  Each model has architecture.input_modalities and supported_parameters
  (including "tools", "structured_outputs" and "reasoning"); the OpenAI SDK
  keeps these extra fields on model_extra.
https://platform.claude.com/docs/en/api/models/list
  ModelInfo.capabilities reports structured_outputs, image_input and effort.
"""

from time import monotonic

import anthropic
import openai
from anthropic import Anthropic
from openai import OpenAI
from pydantic import ValidationError

from app.core.exceptions import ValidationException
from app.core.strixy_config import OPENROUTER_BASE_URL, ReasoningEffort, StrixyConfig
from app.schemas.strixy_schema import ChatMessage
from app.services.strixy_service import StrixyService

LIST_TIMEOUT_SECONDS = 15
TEST_TIMEOUT_SECONDS = 60
EFFORT_LEVELS: tuple[ReasoningEffort, ...] = ("low", "medium", "high", "xhigh", "max")
CHECK_PROMPT = "Connection check: answer OK with no citations."


def list_models(provider: str, base_url: str | None, api_key: str) -> list[dict]:
    if provider == "anthropic":
        return anthropic_models(api_key)
    url = OPENROUTER_BASE_URL if provider == "openrouter" else base_url
    with OpenAI(
        base_url=url, api_key=api_key, max_retries=0, timeout=LIST_TIMEOUT_SECONDS
    ) as client:
        models = sorted(
            client.models.list(), key=lambda m: m.created or 0, reverse=True
        )
    if provider == "openrouter":
        return [entry for m in models if (entry := openrouter_entry(m))]
    return [{"id": m.id, "name": m.id, "vision": None, "efforts": None} for m in models]


def openrouter_entry(model) -> dict | None:
    extra = model.model_extra or {}
    supported = extra.get("supported_parameters") or []
    if "structured_outputs" not in supported:
        return None
    modalities = (extra.get("architecture") or {}).get("input_modalities") or []
    return {
        "id": model.id,
        "name": extra.get("name") or model.id,
        "vision": "image" in modalities,
        "efforts": None if "reasoning" in supported else [],
    }


def anthropic_models(api_key: str) -> list[dict]:
    with Anthropic(
        api_key=api_key, max_retries=0, timeout=LIST_TIMEOUT_SECONDS
    ) as client:
        models = list(client.models.list(limit=1000))
    entries = []
    for m in models:
        caps = m.capabilities
        if caps and not caps.structured_outputs.supported:
            continue
        entries.append(
            {
                "id": m.id,
                "name": m.display_name,
                "vision": caps.image_input.supported if caps else None,
                "efforts": anthropic_efforts(caps.effort) if caps else None,
            }
        )
    return entries


def anthropic_efforts(effort) -> list[str]:
    if not effort.supported:
        return []
    return [
        level
        for level in EFFORT_LEVELS
        if (support := getattr(effort, level, None)) and support.supported
    ]


def test_connection(config: StrixyConfig, api_key: str | None) -> dict:
    started = monotonic()
    try:
        StrixyService(api_key).generate(
            [ChatMessage(role="user", content=CHECK_PROMPT)],
            config,
            timeout=TEST_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        return {"ok": False, "message": provider_error(exc)}
    return {
        "ok": True,
        "model": config.model,
        "seconds": round(monotonic() - started, 1),
    }


def provider_message(exc: openai.APIError | anthropic.APIError) -> str:
    """The provider's own message; the SDKs prefix theirs with the whole error body."""
    body = exc.body
    if isinstance(body, dict):
        body = body.get("error", body)
        if isinstance(body, dict) and isinstance(body.get("message"), str):
            return body["message"]
    return exc.message


def provider_error(exc: Exception) -> str:
    if isinstance(exc, (openai.AuthenticationError, anthropic.AuthenticationError)):
        return "The provider rejected the API key"
    if isinstance(exc, (openai.NotFoundError, anthropic.NotFoundError)):
        return f"Model or endpoint not found: {provider_message(exc)}"
    if isinstance(exc, (openai.APIConnectionError, anthropic.APIConnectionError)):
        return f"Couldn't reach the provider: {exc.message}"
    if isinstance(exc, (openai.APIStatusError, anthropic.APIStatusError)):
        return f"Provider returned {exc.status_code}: {provider_message(exc)}"
    if isinstance(exc, (openai.APIError, anthropic.APIError)):
        return f"Provider error: {provider_message(exc)}"
    if isinstance(exc, ValidationError):
        return (
            "The model didn't return Strixy's JSON format; "
            "pick a model that supports structured outputs"
        )
    if isinstance(exc, (ValidationException, RuntimeError)):
        return str(exc)
    return f"Unexpected error: {type(exc).__name__}"


def provider_reason(exc: Exception) -> str | None:
    """Chat users see only what the provider's API said, never internal error text."""
    if isinstance(exc, (openai.APIError, anthropic.APIError)):
        return provider_error(exc)[:500]
    return None
