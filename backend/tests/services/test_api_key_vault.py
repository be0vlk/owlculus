"""Behaviour tests for provider API-key lookup."""

from unittest.mock import Mock

from sqlalchemy.exc import OperationalError

from app.core.security import encrypt_api_key
from app.database.models import SystemConfiguration
from app.services.api_key_vault import (
    ConfigurationApiKeyVault,
    Provider,
    StaticApiKeyVault,
)


def test_stored_key_takes_precedence_over_environment(session, monkeypatch):
    session.add(
        SystemConfiguration(
            api_keys={
                Provider.OPENAI.value: {
                    "api_key": encrypt_api_key("stored-key"),
                    "is_active": True,
                }
            }
        )
    )
    session.commit()
    monkeypatch.setenv("OPENAI_API_KEY", "environment-key")

    assert ConfigurationApiKeyVault(session).get_key(Provider.OPENAI) == "stored-key"


def test_environment_key_is_used_when_stored_key_is_absent(session, monkeypatch):
    monkeypatch.setenv("SHODAN_API_KEY", "environment-key")

    assert (
        ConfigurationApiKeyVault(session).get_key(Provider.SHODAN) == "environment-key"
    )


def test_absent_key_is_logged_and_empty_environment_value_is_not_returned(
    session, monkeypatch
):
    log = Mock()
    monkeypatch.setenv("VIRUSTOTAL_API_KEY", "")

    vault = ConfigurationApiKeyVault(session, log=log)

    assert vault.get_key(Provider.VIRUSTOTAL) is None
    log.bind.assert_any_call(
        provider=Provider.VIRUSTOTAL.value, event_type="api_key_absent"
    )


def test_decrypt_failure_is_logged_before_environment_fallback(session, monkeypatch):
    log = Mock()
    session.add(
        SystemConfiguration(
            api_keys={
                Provider.OPENAI.value: {
                    "api_key": "not-fernet-ciphertext",
                    "is_active": True,
                }
            }
        )
    )
    session.commit()
    monkeypatch.setenv("OPENAI_API_KEY", "environment-key")

    vault = ConfigurationApiKeyVault(session, log=log)

    assert vault.get_key(Provider.OPENAI) == "environment-key"
    log.bind.assert_any_call(
        provider=Provider.OPENAI.value, event_type="api_key_decrypt_failed"
    )


def test_database_failure_is_logged_before_environment_fallback(monkeypatch):
    log = Mock()
    unavailable_session = Mock()
    unavailable_session.exec.side_effect = OperationalError(
        "select configuration", {}, RuntimeError("database unavailable")
    )
    monkeypatch.setenv("PEOPLE_DATA_LABS_API_KEY", "environment-key")

    vault = ConfigurationApiKeyVault(unavailable_session, log=log)

    assert vault.get_key(Provider.PEOPLE_DATA_LABS) == "environment-key"
    log.bind.assert_any_call(
        provider=Provider.PEOPLE_DATA_LABS.value,
        event_type="api_key_database_unavailable",
    )


def test_static_vault_implements_lookup_and_configured_contract():
    vault = StaticApiKeyVault({Provider.OPENAI: "test-key", Provider.SHODAN: ""})

    assert vault.get_key(Provider.OPENAI) == "test-key"
    assert vault.is_configured(Provider.OPENAI) is True
    assert vault.get_key(Provider.SHODAN) is None
    assert vault.is_configured(Provider.SHODAN) is False


def test_provider_enum_covers_every_current_consumer():
    assert {provider.value for provider in Provider} == {
        "custom",
        "openai",
        "people_data_labs",
        "securitytrails",
        "shodan",
        "virustotal",
    }
