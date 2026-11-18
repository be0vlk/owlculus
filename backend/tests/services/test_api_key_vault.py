"""Behaviour tests for provider API-key lookup."""

from unittest.mock import Mock

from sqlalchemy.exc import OperationalError

from app.core.security import encrypt_api_key
from app.database.models import SystemConfiguration
from app.services.api_key_vault import (
    ConfigurationApiKeyVault,
    Provider,
    StaticApiKeyVault,
    strixy_key,
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


def test_malformed_active_flag_does_not_activate_stored_credential(
    session, monkeypatch
):
    session.add(
        SystemConfiguration(
            api_keys={
                Provider.OPENAI.value: {
                    "api_key": encrypt_api_key("stored-key"),
                    "is_active": "yes",
                }
            }
        )
    )
    session.commit()
    monkeypatch.setenv("OPENAI_API_KEY", "environment-key")

    assert (
        ConfigurationApiKeyVault(session).get_key(Provider.OPENAI) == "environment-key"
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
        "anthropic",
        "custom",
        "openai",
        "openai_compatible",
        "openrouter",
        "people_data_labs",
        "securitytrails",
        "shodan",
        "virustotal",
    }


def test_strixy_key_reads_the_configured_providers_key(session, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")

    assert strixy_key(session, "openai") == "openai-key"
    assert strixy_key(session, "anthropic") == "anthropic-key"


def test_openai_compatible_without_a_key_gets_a_placeholder(session, monkeypatch):
    monkeypatch.delenv("OPENAI_COMPATIBLE_API_KEY", raising=False)
    assert strixy_key(session, "openai_compatible") == "not-needed"
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "router-key")
    assert strixy_key(session, "openai_compatible") == "router-key"


def test_strixy_key_is_absent_for_unconfigured_hosted_providers(session, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert strixy_key(session, "anthropic") is None
