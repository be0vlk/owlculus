"""
Business logic for system configuration management.

This module handles system settings, configuration validation, and updates including
case number templates, API key management, evidence folder templates, and
administrative system configuration functionality.
"""

from collections.abc import Callable
from datetime import datetime

from sqlmodel import Session, select

from ..core.evidence_templates import DEFAULT_TEMPLATES
from ..core.exceptions import ValidationException
from ..core.logging import audit_operation
from ..core.security import encrypt_api_key
from ..core.strixy_config import (
    PROVIDER_NAMES,
    StrixyModelQuery,
    StrixySettings,
    StrixySetup,
    strixy_config_from,
)
from ..core.utils import get_utc_now
from ..database import models
from ..database.db_utils import transaction
from . import strixy_setup
from .api_key_vault import Provider, StoredApiKey, strixy_key
from .case_access import CaseAccess

CASE_NUMBER_TEMPLATE_MONTHLY = "YYMM-NN"
CASE_NUMBER_TEMPLATE_PREFIX = "PREFIX-YYMM-NN"
TEMPLATE_DISPLAY_NAMES = {
    CASE_NUMBER_TEMPLATE_MONTHLY: "Monthly Reset (YYMM-NN)",
    CASE_NUMBER_TEMPLATE_PREFIX: "Prefix + Monthly Reset (PREFIX-YYMM-NN)",
}


class SystemConfigService:
    def __init__(
        self, db: Session, *, clock: Callable[[], datetime] = get_utc_now
    ) -> None:
        self.db = db
        self._clock = clock
        self.case_access = CaseAccess(db)

    def _persist_configuration(
        self, config: models.SystemConfiguration
    ) -> models.SystemConfiguration:
        """Persist an administrative configuration change."""
        config.updated_at = self._clock()
        with transaction(self.db):
            self.db.add(config)
        self.db.refresh(config)
        return config

    async def get_configuration(
        self, current_user: models.User | None = None
    ) -> models.SystemConfiguration:
        stmt = select(models.SystemConfiguration)
        config = self.db.exec(stmt).first()

        if not config:
            config = models.SystemConfiguration(
                case_number_template="YYMM-NN",
                case_number_prefix=None,
                api_keys={},
                evidence_folder_templates=DEFAULT_TEMPLATES.copy(),
            )
            self.db.add(config)
            self.db.flush()

        return config

    async def get_configuration_admin(
        self, current_user: models.User
    ) -> models.SystemConfiguration:
        """Admin-only method to get configuration."""
        self.case_access.require_admin(current_user)
        return await self.get_configuration()

    @audit_operation("system_config_update")
    async def update_configuration(
        self,
        case_number_template: str,
        current_user: models.User,
        case_number_prefix: str | None = None,
    ) -> models.SystemConfiguration:
        self.case_access.require_admin(current_user)
        if case_number_template != CASE_NUMBER_TEMPLATE_PREFIX:
            case_number_prefix = None

        config = await self.get_configuration()
        config.case_number_template = case_number_template
        config.case_number_prefix = case_number_prefix
        return self._persist_configuration(config)

    def get_template_display_name(self, template: str) -> str:
        """Get display name for a case number template"""
        return TEMPLATE_DISPLAY_NAMES.get(template, template)

    def generate_example_case_number(
        self, template: str, prefix: str | None = None
    ) -> str:
        """Generate an example case number based on template"""
        current_time = self._clock()
        year = str(current_time.year)[2:]
        month = str(current_time.month).zfill(2)

        if template == CASE_NUMBER_TEMPLATE_PREFIX and prefix:
            return f"{prefix}-{year}{month}-01"
        return f"{year}{month}-01"

    @audit_operation("api_key_set")
    async def set_api_key(
        self,
        provider: Provider,
        api_key: str | None,
        name: str,
        current_user: models.User,
    ) -> models.SystemConfiguration:
        self.case_access.require_admin(current_user)
        config = await self.get_configuration()
        current_keys = dict(config.api_keys or {})
        previous = (
            StoredApiKey.from_mapping(provider.value, current_keys[provider.value])
            if provider.value in current_keys
            else None
        )
        if api_key:
            encrypted_key: str | None = encrypt_api_key(api_key)
        elif previous:
            encrypted_key = previous.encrypted_key
        else:
            raise ValidationException("API key is required for new providers")
        current_keys[provider.value] = StoredApiKey(
            encrypted_key=encrypted_key,
            name=name,
            is_active=True,
            created_at=(previous and previous.created_at) or self._clock().isoformat(),
        ).to_mapping()
        config.api_keys = current_keys
        return self._persist_configuration(config)

    @audit_operation("api_key_remove")
    async def remove_api_key(
        self, provider: Provider, current_user: models.User
    ) -> models.SystemConfiguration:
        self.case_access.require_admin(current_user)
        config = await self.get_configuration()
        remaining = dict(config.api_keys or {})
        if remaining.pop(provider.value, None) is None:
            return config
        config.api_keys = remaining
        return self._persist_configuration(config)

    async def list_api_keys(self, current_user: models.User) -> dict[str, dict]:
        """List all configured API keys (admin only)"""
        self.case_access.require_admin(current_user)
        config = await self.get_configuration()
        return {
            provider: {
                "name": stored.name,
                "is_configured": True,
                "created_at": stored.created_at,
            }
            for provider, key_data in (config.api_keys or {}).items()
            if (stored := StoredApiKey.from_mapping(provider, key_data)).is_active
        }

    def preview_case_number_template(
        self, template: str, prefix: str | None, current_user: models.User
    ) -> tuple[str, str]:
        """Authorize and render an administrative case-number preview."""
        self.case_access.require_admin(current_user)
        if template not in TEMPLATE_DISPLAY_NAMES:
            raise ValidationException(f"Invalid case number template: {template}")
        return (
            self.generate_example_case_number(template, prefix),
            self.get_template_display_name(template),
        )

    async def get_evidence_folder_templates(self) -> dict:
        config = await self.get_configuration()
        if not config.evidence_folder_templates:
            config.evidence_folder_templates = DEFAULT_TEMPLATES.copy()
            config = self._persist_configuration(config)
        return config.evidence_folder_templates or {}

    @audit_operation("evidence_templates_update")
    async def update_evidence_folder_templates(
        self, templates: dict, current_user: models.User
    ) -> models.SystemConfiguration:
        self.case_access.require_admin(current_user)
        config = await self.get_configuration()
        config.evidence_folder_templates = templates
        return self._persist_configuration(config)

    async def get_strixy_settings(self, current_user: models.User) -> StrixySettings:
        self.case_access.require_admin(current_user)
        config = await self.get_configuration()
        return StrixySettings.model_validate(config.strixy_settings or {})

    @audit_operation("strixy_settings_update")
    async def update_strixy_settings(
        self, settings: StrixySettings, current_user: models.User
    ) -> StrixySettings:
        self.case_access.require_admin(current_user)
        config = await self.get_configuration()
        config.strixy_settings = settings.model_dump()
        self._persist_configuration(config)
        return settings

    def _strixy_setup_key(self, provider: str, typed: str | None) -> str | None:
        return typed or strixy_key(self.db, provider)

    async def list_strixy_models(
        self, query: StrixyModelQuery, current_user: models.User
    ) -> list[dict]:
        self.case_access.require_admin(current_user)
        key = self._strixy_setup_key(query.provider, query.api_key)
        if not key:
            raise ValidationException(
                f"{PROVIDER_NAMES[query.provider]} API key not configured"
            )
        try:
            return strixy_setup.list_models(query.provider, query.base_url, key)
        except Exception as error:
            raise ValidationException(strixy_setup.provider_error(error)) from error

    @audit_operation("strixy_connection_test")
    async def test_strixy_connection(
        self, setup: StrixySetup, current_user: models.User
    ) -> dict:
        self.case_access.require_admin(current_user)
        return strixy_setup.test_connection(
            strixy_config_from(setup),
            self._strixy_setup_key(setup.provider, setup.api_key),
        )
