"""Provider-typed access to third-party API keys."""

import os
from enum import StrEnum
from typing import Mapping, Protocol

from sqlmodel import Session, select

from app.core.logging import get_security_logger
from app.core.security import decrypt_api_key
from app.database.models import SystemConfiguration


class Provider(StrEnum):
    """Third-party providers supported by Owlculus."""

    OPENAI = "openai"
    PEOPLE_DATA_LABS = "people_data_labs"
    SECURITYTRAILS = "securitytrails"
    SHODAN = "shodan"
    VIRUSTOTAL = "virustotal"


class ApiKeyVault(Protocol):
    """Read access to provider credentials."""

    def get_key(self, provider: Provider) -> str | None: ...

    def is_configured(self, provider: Provider) -> bool: ...


class ConfigurationApiKeyVault:
    """Read encrypted configuration keys, falling back to the environment."""

    def __init__(self, db: Session, *, log=None) -> None:
        self._db = db
        self._log = log or get_security_logger(component="api_key_vault")

    def get_key(self, provider: Provider) -> str | None:
        try:
            config = self._db.exec(select(SystemConfiguration)).first()
        except Exception as error:
            self._log.bind(
                provider=provider.value,
                event_type="api_key_database_unavailable",
            ).warning(f"API key database lookup failed: {error}")
            return self._environment_key(provider, log_absent=True)

        key_data: dict | None = (
            (config.api_keys or {}).get(provider.value) if config else None
        )
        encrypted_key = key_data.get("api_key") if key_data is not None else None
        if encrypted_key and key_data is not None and key_data.get("is_active", True):
            try:
                decrypted_key = decrypt_api_key(encrypted_key)
                if decrypted_key:
                    return decrypted_key
            except Exception as error:
                self._log.bind(
                    provider=provider.value,
                    event_type="api_key_decrypt_failed",
                ).warning(f"Stored API key could not be decrypted: {error}")

        return self._environment_key(provider, log_absent=True)

    def is_configured(self, provider: Provider) -> bool:
        return self.get_key(provider) is not None

    def _environment_key(self, provider: Provider, *, log_absent: bool) -> str | None:
        key = os.environ.get(f"{provider.value.upper()}_API_KEY")
        if key:
            return key
        if log_absent:
            self._log.bind(
                provider=provider.value,
                event_type="api_key_absent",
            ).info("No API key is configured for provider")
        return None


class StaticApiKeyVault:
    """In-memory vault for tests and other fixed configurations."""

    def __init__(self, keys: Mapping[Provider, str | None]) -> None:
        self._keys = dict(keys)

    def get_key(self, provider: Provider) -> str | None:
        return self._keys.get(provider) or None

    def is_configured(self, provider: Provider) -> bool:
        return self.get_key(provider) is not None
