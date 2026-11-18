"""Configuration boundary tests."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_required_settings_are_loaded_from_the_environment(monkeypatch) -> None:
    values = {
        "SECRET_KEY": "secret",
        "POSTGRES_USER": "owlculus",
        "POSTGRES_PASSWORD": "password",
        "POSTGRES_HOST": "database",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "owlculus",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)

    configured = Settings(_env_file=None)

    assert configured.DB_USER == "owlculus"
    assert configured.DB_PASSWORD.get_secret_value() == "password"
    assert configured.DATABASE_URI == (
        "postgresql://owlculus:password@database:5432/owlculus"
    )


def test_missing_required_setting_is_rejected(monkeypatch) -> None:
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    "name",
    [
        "LOGIN_IP_MAX_ATTEMPTS",
        "LOGIN_ACCOUNT_MAX_ATTEMPTS",
        "LOGIN_LIMIT_WINDOW_SECONDS",
    ],
)
@pytest.mark.parametrize("value", ["0", "-1", "invalid", "100000"])
def test_login_limits_require_finite_positive_configuration(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError, match=name):
        Settings(_env_file=None)


@pytest.mark.parametrize("value", ["0", "-1", "invalid", "1.5", "100"])
def test_api_concurrency_configuration_rejects_invalid_values(monkeypatch, value):
    monkeypatch.setenv("API_DATABASE_CONCURRENCY", value)
    with pytest.raises(ValidationError, match="API_DATABASE_CONCURRENCY"):
        Settings(_env_file=None)


def test_authentication_endpoint_is_independent_of_legacy_execution_url(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://execution.example:6379/0")
    monkeypatch.setenv("AUTH_REDIS_URL", "redis://authentication.example:6379/0")
    configured = Settings(_env_file=None)
    assert configured.AUTH_REDIS_URL == "redis://authentication.example:6379/0"


def test_strixy_model_defaults_to_the_built_in_and_can_be_overridden(monkeypatch):
    from app.core.config import settings
    from app.core.strixy_config import StrixyConfig, get_strixy_config

    assert get_strixy_config() == StrixyConfig()

    monkeypatch.setenv("STRIXY_MODEL", "gpt-next")
    overridden = Settings(_env_file=None)
    assert overridden.STRIXY_MODEL == "gpt-next"
    monkeypatch.setattr(settings, "STRIXY_MODEL", overridden.STRIXY_MODEL)
    assert get_strixy_config().model == "gpt-next"
    assert get_strixy_config().reasoning_effort == StrixyConfig().reasoning_effort


def strixy_env(monkeypatch, **values) -> None:
    for name, value in {
        "SECRET_KEY": "secret",
        "POSTGRES_USER": "owlculus",
        "POSTGRES_PASSWORD": "password",
        "POSTGRES_HOST": "database",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "owlculus",
        **values,
    }.items():
        monkeypatch.setenv(name, value)


@pytest.mark.parametrize(
    ("provider", "model"),
    [
        ("openai", "gpt-6-astra"),
        ("anthropic", "claude-sonnet-5-5"),
    ],
)
def test_strixy_model_defaults_per_provider(monkeypatch, provider, model) -> None:
    from app.core.strixy_config import get_strixy_config

    strixy_env(monkeypatch, STRIXY_PROVIDER=provider)
    monkeypatch.setattr("app.core.config.settings", Settings(_env_file=None))

    config = get_strixy_config()

    assert (config.provider, config.model, config.base_url) == (provider, model, None)
    assert config.supports_vision is True


def test_strixy_openai_compatible_settings_pass_through(monkeypatch) -> None:
    from app.core.strixy_config import get_strixy_config

    strixy_env(
        monkeypatch,
        STRIXY_PROVIDER="openai_compatible",
        STRIXY_MODEL="llama3",
        STRIXY_BASE_URL="http://10.0.0.5:11434/v1",
        STRIXY_SUPPORTS_VISION="false",
    )
    monkeypatch.setattr("app.core.config.settings", Settings(_env_file=None))

    config = get_strixy_config()

    assert config.provider == "openai_compatible"
    assert config.model == "llama3"
    assert config.base_url == "http://10.0.0.5:11434/v1"
    assert config.supports_vision is False


@pytest.mark.parametrize(
    "given",
    [{"STRIXY_MODEL": "llama3"}, {"STRIXY_BASE_URL": "http://x/v1"}, {}],
)
def test_strixy_openai_compatible_requires_model_and_base_url(
    monkeypatch, given
) -> None:
    monkeypatch.delenv("STRIXY_MODEL", raising=False)
    monkeypatch.delenv("STRIXY_BASE_URL", raising=False)
    strixy_env(monkeypatch, STRIXY_PROVIDER="openai_compatible", **given)

    with pytest.raises(ValidationError, match="STRIXY_"):
        Settings(_env_file=None)


def test_blank_strixy_overrides_from_compose_mean_unset(monkeypatch) -> None:
    strixy_env(monkeypatch, STRIXY_MODEL="", STRIXY_BASE_URL="")

    configured = Settings(_env_file=None)

    assert configured.STRIXY_MODEL is None and configured.STRIXY_BASE_URL is None
