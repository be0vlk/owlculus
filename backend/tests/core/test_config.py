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
