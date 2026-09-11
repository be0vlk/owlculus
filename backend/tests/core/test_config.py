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


@pytest.mark.parametrize("name", ["API_WORKERS", "API_DATABASE_CONCURRENCY"])
@pytest.mark.parametrize("value", ["0", "-1", "invalid", "1.5", "100"])
def test_api_concurrency_configuration_rejects_invalid_values(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError, match=name):
        Settings(_env_file=None)


def test_production_launcher_preserves_worker_and_proxy_configuration(monkeypatch):
    from app import serve

    calls = []
    monkeypatch.setattr(serve.settings, "API_WORKERS", 2)
    monkeypatch.setattr(serve.settings, "FORWARDED_ALLOW_IPS", "172.29.0.254")
    monkeypatch.setattr(
        serve.uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs))
    )
    serve.main()
    assert calls == [
        (
            ("app.main:app",),
            {
                "host": "0.0.0.0",
                "port": 8000,
                "workers": 2,
                "proxy_headers": True,
                "forwarded_allow_ips": "172.29.0.254",
            },
        )
    ]


def test_authentication_endpoint_is_independent_of_legacy_execution_url(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://execution.example:6379/0")
    monkeypatch.setenv("AUTH_REDIS_URL", "redis://authentication.example:6379/0")
    configured = Settings(_env_file=None)
    assert configured.AUTH_REDIS_URL == "redis://authentication.example:6379/0"
    assert configured.REDIS_URL == "redis://execution.example:6379/0"
