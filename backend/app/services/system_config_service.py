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
from ..core.utils import get_utc_now
from ..database import models
from ..database.db_utils import transaction
from .api_key_vault import Provider, StoredApiKey
from .case_access import CaseAccess

CASE_NUMBER_TEMPLATE_MONTHLY = "YYMM-NN"
CASE_NUMBER_TEMPLATE_PREFIX = "PREFIX-YYMM-NN"
VALID_CASE_NUMBER_TEMPLATES = [
    CASE_NUMBER_TEMPLATE_MONTHLY,
    CASE_NUMBER_TEMPLATE_PREFIX,
]

PREFIX_MIN_LENGTH = 2
PREFIX_MAX_LENGTH = 8
TEMPLATE_DISPLAY_NAMES = {
    CASE_NUMBER_TEMPLATE_MONTHLY: "Monthly Reset (YYMM-NN)",
    CASE_NUMBER_TEMPLATE_PREFIX: "Prefix + Monthly Reset (PREFIX-YYMM-NN)",
}


class SystemConfigValidator:
    """Handles validation logic for system configuration"""

    @staticmethod
    def validate_case_number_template(template: str) -> None:
        """Validate case number template format"""
        if template not in VALID_CASE_NUMBER_TEMPLATES:
            raise ValidationException(f"Invalid case number template: {template}")

    @staticmethod
    def validate_case_number_prefix(prefix: str | None, template: str) -> None:
        """Validate case number prefix based on template"""
        if template == CASE_NUMBER_TEMPLATE_PREFIX:
            if not prefix:
                raise ValidationException(
                    "Prefix is required for PREFIX-YYMM-NN template"
                )

            if not prefix.isalnum():
                raise ValidationException(
                    "Prefix must contain only alphanumeric characters"
                )

            if len(prefix) < PREFIX_MIN_LENGTH or len(prefix) > PREFIX_MAX_LENGTH:
                raise ValidationException(
                    f"Prefix must be {PREFIX_MIN_LENGTH}-{PREFIX_MAX_LENGTH} characters"
                )

    @staticmethod
    def validate_evidence_template(template_data: dict, template_key: str) -> None:
        """Validate evidence folder template structure"""
        if not isinstance(template_data, dict):
            raise ValidationException(f"Invalid template structure for {template_key}")

        required_fields = ["name", "description", "folders"]
        for field in required_fields:
            if field not in template_data:
                raise ValidationException(f"Template {template_key} must have {field}")

        if not isinstance(template_data["folders"], list):
            raise ValidationException(
                f"Template {template_key} must have folders array"
            )


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
        SystemConfigValidator.validate_case_number_template(case_number_template)
        SystemConfigValidator.validate_case_number_prefix(
            case_number_prefix, case_number_template
        )
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
        current_keys = config.api_keys.copy() if config.api_keys else {}
        provider_name = provider.value
        if provider_name not in current_keys:
            if not api_key:
                raise ValidationException("API key is required for new providers")
            current_keys[provider_name] = StoredApiKey(
                encrypted_key=encrypt_api_key(api_key),
                name=name,
                is_active=True,
                created_at=self._clock().isoformat(),
            ).to_mapping()
        else:
            existing_key = StoredApiKey.from_mapping(
                provider_name, current_keys[provider_name]
            )
            current_keys[provider_name] = StoredApiKey(
                encrypted_key=(
                    encrypt_api_key(api_key) if api_key else existing_key.encrypted_key
                ),
                name=name,
                is_active=True,
                created_at=existing_key.created_at or self._clock().isoformat(),
            ).to_mapping()

        config.api_keys = current_keys
        return self._persist_configuration(config)

    @audit_operation("api_key_remove")
    async def remove_api_key(
        self, provider: Provider, current_user: models.User
    ) -> models.SystemConfiguration:
        self.case_access.require_admin(current_user)
        config = await self.get_configuration()
        provider_name = provider.value
        if config.api_keys and provider_name in config.api_keys:
            current_keys = config.api_keys.copy()
            del current_keys[provider_name]
            config.api_keys = current_keys
            config = self._persist_configuration(config)
        return config

    async def list_api_keys(self, current_user: models.User) -> dict[str, dict]:
        """List all configured API keys (admin only)"""
        self.case_access.require_admin(current_user)
        try:
            config = await self.get_configuration()

            if not config.api_keys:
                return {}

            result = {}
            for provider, key_data in config.api_keys.items():
                stored_key = StoredApiKey.from_mapping(provider, key_data)
                if stored_key.is_active:
                    result[provider] = {
                        "name": stored_key.name,
                        "is_configured": True,
                        "created_at": stored_key.created_at,
                    }

            return result

        except Exception:
            return {}

    async def get_configured_providers(self, current_user: models.User) -> list[str]:
        """Get list of configured providers (requires admin access)"""
        api_keys = await self.list_api_keys(current_user=current_user)
        return list(api_keys.keys())

    def preview_case_number_template(
        self, template: str, prefix: str | None, current_user: models.User
    ) -> tuple[str, str]:
        """Authorize and render an administrative case-number preview."""
        self.case_access.require_admin(current_user)
        SystemConfigValidator.validate_case_number_template(template)
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
        for template_key, template_data in templates.items():
            SystemConfigValidator.validate_evidence_template(
                template_data, template_key
            )

        config = await self.get_configuration()
        config.evidence_folder_templates = templates
        return self._persist_configuration(config)
