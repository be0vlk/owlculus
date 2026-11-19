"""Provider-typed access to third-party API keys."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from cryptography.fernet import InvalidToken
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.core.logging import get_security_logger
from app.core.security import decrypt_api_key
from app.database.models import SystemConfiguration


class Provider(StrEnum):
    """Third-party providers supported by Owlculus."""

    ANTHROPIC = "anthropic"
    CUSTOM = "custom"
    OPENAI = "openai"
    OPENAI_COMPATIBLE = "openai_compatible"
    OPENROUTER = "openrouter"
    PEOPLE_DATA_LABS = "people_data_labs"
    SECURITYTRAILS = "securitytrails"
    SHODAN = "shodan"
    VIRUSTOTAL = "virustotal"


class ApiKeyVault(Protocol):
    """Read access to provider credentials."""

    def get_key(self, provider: Provider) -> str | None: ...

    def is_configured(self, provider: Provider) -> bool: ...


@dataclass(frozen=True)
class StoredApiKey:
    """The encrypted API-key record persisted in system configuration."""

    encrypted_key: str | None
    name: str
    is_active: bool
    created_at: str | None

    @classmethod
    def from_mapping(cls, provider: str, data: Mapping[str, object]) -> "StoredApiKey":
        encrypted_key = data.get("api_key")
        name = data.get("name")
        created_at = data.get("created_at")
        is_active = data.get("is_active", True)
        return cls(
            encrypted_key=encrypted_key if isinstance(encrypted_key, str) else None,
            name=name if isinstance(name, str) else provider,
            is_active=is_active if isinstance(is_active, bool) else False,
            created_at=created_at if isinstance(created_at, str) else None,
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "api_key": self.encrypted_key,
            "name": self.name,
            "is_active": self.is_active,
            "created_at": self.created_at,
        }


class ConfigurationApiKeyVault:
    """Read encrypted configuration keys, falling back to the environment."""

    def __init__(self, db: Session, *, log=None) -> None:
        self._db = db
        self._log = log or get_security_logger(component="api_key_vault")

    def get_key(self, provider: Provider) -> str | None:
        return self._stored_key(provider) or self._environment_key(
            provider, log_absent=True
        )

    def _stored_key(self, provider: Provider) -> str | None:
        try:
            config = self._db.exec(select(SystemConfiguration)).first()
        except SQLAlchemyError as error:
            self._log.bind(
                provider=provider.value,
                event_type="api_key_database_unavailable",
            ).warning(f"API key database lookup failed: {error}")
            return None

        key_data: dict | None = (
            (config.api_keys or {}).get(provider.value) if config else None
        )
        stored_key = (
            StoredApiKey.from_mapping(provider.value, key_data) if key_data else None
        )
        if stored_key and stored_key.encrypted_key and stored_key.is_active:
            try:
                decrypted_key = decrypt_api_key(stored_key.encrypted_key)
                if decrypted_key:
                    return decrypted_key
            except InvalidToken as error:
                self._log.bind(
                    provider=provider.value,
                    event_type="api_key_decrypt_failed",
                ).warning(f"Stored API key could not be decrypted: {error}")
        return None

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
    """In-memory vault adapter for tests."""

    def __init__(self, keys: Mapping[Provider, str | None]) -> None:
        self._keys = dict(keys)

    def get_key(self, provider: Provider) -> str | None:
        return self._keys.get(provider) or None

    def is_configured(self, provider: Provider) -> bool:
        return self.get_key(provider) is not None


def strixy_key(db: Session, provider: str, base_url: str | None) -> str | None:
    """The key for a Strixy request to base_url, the endpoint it will be sent to."""
    vault = ConfigurationApiKeyVault(db)
    if provider != Provider.OPENAI_COMPATIBLE:
        return vault.get_key(Provider(provider))
    key = vault._stored_key(Provider.OPENAI_COMPATIBLE)
    # Admins can set the base URL, so the environment key is bound to the
    # operator's own URL instead; otherwise an admin could send it anywhere.
    env_url = os.environ.get("OPENAI_COMPATIBLE_BASE_URL", "").rstrip("/")
    if key is None and env_url and env_url == (base_url or "").rstrip("/"):
        key = vault._environment_key(Provider.OPENAI_COMPATIBLE, log_absent=True)
    # Local OpenAI-compatible servers often need no key, but the SDK requires one.
    return key or "not-needed"
