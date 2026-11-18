"""Strixy provider settings: validation and resolution from saved configuration."""

import pytest
from pydantic import ValidationError

from app.core.strixy_config import StrixyConfig, StrixySettings, get_strixy_config
from app.database.models import SystemConfiguration


def save(session, settings: dict) -> None:
    session.add(SystemConfiguration(strixy_settings=settings))
    session.commit()


def test_unsaved_settings_give_the_built_in_defaults(session) -> None:
    assert get_strixy_config(session) == StrixyConfig()


def test_saved_anthropic_settings_use_the_default_model_and_effort(session) -> None:
    save(session, {"provider": "anthropic", "reasoning_effort": "high"})

    config = get_strixy_config(session)

    assert (config.provider, config.model, config.base_url) == (
        "anthropic",
        "claude-sonnet-5-5",
        None,
    )
    assert config.reasoning_effort == "high"


def test_saved_openai_compatible_settings_pass_through(session) -> None:
    save(
        session,
        {
            "provider": "openai_compatible",
            "model": "llama3",
            "base_url": "http://10.0.0.5:11434/v1",
            "supports_vision": False,
        },
    )

    config = get_strixy_config(session)

    assert config.provider == "openai_compatible"
    assert config.model == "llama3"
    assert config.base_url == "http://10.0.0.5:11434/v1"
    assert config.supports_vision is False


@pytest.mark.parametrize(
    "given",
    [{"model": "llama3"}, {"base_url": "http://x/v1"}, {}],
)
def test_openai_compatible_requires_model_and_base_url(given) -> None:
    with pytest.raises(ValidationError, match="requires a model and base URL"):
        StrixySettings(provider="openai_compatible", **given)


def test_base_url_must_be_http_or_https() -> None:
    with pytest.raises(ValidationError, match="http"):
        StrixySettings(provider="openai", base_url="ftp://host/v1")


def test_blank_strings_mean_unset() -> None:
    settings = StrixySettings(model=" ", base_url="")

    assert settings.model is None and settings.base_url is None
