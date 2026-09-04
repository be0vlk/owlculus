"""
Business logic for system configuration management.

This module handles system settings, configuration validation, and updates including
case number templates, API key management, evidence folder templates, and
administrative system configuration functionality.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Dict, List, Optional

from sqlmodel import Session, select

from ..core.evidence_templates import DEFAULT_TEMPLATES
from ..core.exceptions import ValidationException
from ..core.logging import get_security_logger
from ..core.security import encrypt_api_key
from ..core.utils import get_utc_now
from ..database import models
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
    def validate_case_number_prefix(prefix: Optional[str], template: str) -> None:
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
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return config

    async def get_configuration(
        self, current_user: Optional[models.User] = None
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
            self.db.commit()
            self.db.refresh(config)

        return config

    async def get_configuration_admin(
        self, current_user: models.User
    ) -> models.SystemConfiguration:
        """Admin-only method to get configuration."""
        self.case_access.require_admin(current_user)
        return await self.get_configuration()

    async def update_configuration(
        self,
        case_number_template: str,
        current_user: models.User,
        case_number_prefix: Optional[str] = None,
    ) -> models.SystemConfiguration:
        self.case_access.require_admin(current_user)
        config_logger = get_security_logger(
            admin_user_id=current_user.id,
            action="update_system_config",
            template=case_number_template,
            event_type="system_config_update_attempt",
        )

        try:
            SystemConfigValidator.validate_case_number_template(case_number_template)
            SystemConfigValidator.validate_case_number_prefix(
                case_number_prefix, case_number_template
            )

            if case_number_template != CASE_NUMBER_TEMPLATE_PREFIX:
                case_number_prefix = None

            config = await self.get_configuration()
            old_template = config.case_number_template
            old_prefix = config.case_number_prefix

            config.case_number_template = case_number_template
            config.case_number_prefix = case_number_prefix

            config = self._persist_configuration(config)
            config_logger.bind(
                old_template=old_template,
                new_template=case_number_template,
                old_prefix=old_prefix,
                new_prefix=case_number_prefix,
                event_type="system_config_update_success",
            ).info("System configuration updated successfully")

            return config

        except ValidationException as e:
            config_logger.bind(
                event_type="system_config_update_failed",
                failure_reason="validation_error",
                error_message=str(e),
            ).warning(f"System config update failed: {str(e)}")
            raise
        except Exception as e:
            config_logger.bind(
                event_type="system_config_update_error",
                error_type="system_error",
                error_message=str(e),
            ).error(f"System config update error: {str(e)}")
            raise

    def get_template_display_name(self, template: str) -> str:
        """Get display name for a case number template"""
        return TEMPLATE_DISPLAY_NAMES.get(template, template)

    def generate_example_case_number(
        self, template: str, prefix: Optional[str] = None
    ) -> str:
        """Generate an example case number based on template"""
        current_time = self._clock()
        year = str(current_time.year)[2:]
        month = str(current_time.month).zfill(2)

        if template == CASE_NUMBER_TEMPLATE_PREFIX and prefix:
            return f"{prefix}-{year}{month}-01"
        return f"{year}{month}-01"

    async def set_api_key(
        self,
        provider: Provider,
        api_key: Optional[str],
        name: str,
        current_user: models.User,
    ) -> models.SystemConfiguration:
        self.case_access.require_admin(current_user)
        config = await self.get_configuration()
        current_keys = config.api_keys.copy() if config.api_keys else {}
        provider_name = provider.value
        is_new_key = provider_name not in current_keys
        operation_type = "add" if is_new_key else "update"

        config_logger = get_security_logger(
            admin_user_id=current_user.id,
            action=f"{operation_type}_api_key",
            provider=provider,
            key_name=name,
            is_new_key=is_new_key,
            event_type=f"api_key_{operation_type}_attempt",
        )

        try:
            if is_new_key:
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
                key_being_updated = api_key is not None
                current_keys[provider_name] = StoredApiKey(
                    encrypted_key=(
                        encrypt_api_key(api_key)
                        if api_key
                        else existing_key.encrypted_key
                    ),
                    name=name,
                    is_active=True,
                    created_at=existing_key.created_at or self._clock().isoformat(),
                ).to_mapping()
                config_logger = config_logger.bind(
                    old_name=existing_key.name,
                    new_name=name,
                    key_updated=key_being_updated,
                    metadata_only=not key_being_updated,
                )

            config.api_keys = current_keys
            config = self._persist_configuration(config)
            config_logger.bind(event_type=f"api_key_{operation_type}_success").info(
                f"API key {operation_type}d successfully for provider: {provider}"
            )

            return config

        except ValidationException as e:
            config_logger.bind(
                event_type=f"api_key_{operation_type}_failed",
                failure_reason="validation_error",
                error_message=str(e),
            ).warning(f"API key {operation_type} failed for {provider}: {str(e)}")
            raise
        except Exception as e:
            config_logger.bind(
                event_type=f"api_key_{operation_type}_error",
                error_type="system_error",
                error_message=str(e),
            ).error(f"API key {operation_type} error for {provider}: {str(e)}")
            raise

    async def remove_api_key(
        self, provider: Provider, current_user: models.User
    ) -> models.SystemConfiguration:
        self.case_access.require_admin(current_user)
        config = await self.get_configuration()

        existing_key_data = None
        provider_name = provider.value
        if config.api_keys and provider_name in config.api_keys:
            existing_key_data = config.api_keys[provider_name]

        config_logger = get_security_logger(
            admin_user_id=current_user.id,
            action="remove_api_key",
            provider=provider,
            key_name=existing_key_data.get("name") if existing_key_data else None,
            key_existed=existing_key_data is not None,
            event_type="api_key_remove_attempt",
        )

        try:
            if config.api_keys and provider_name in config.api_keys:
                current_keys = config.api_keys.copy()
                removed_key_data = current_keys[provider_name]
                del current_keys[provider_name]
                config.api_keys = current_keys
                config = self._persist_configuration(config)

                config_logger.bind(
                    removed_key_name=removed_key_data.get("name"),
                    key_created_at=removed_key_data.get("created_at"),
                    event_type="api_key_remove_success",
                ).info(f"API key removed successfully for provider: {provider}")
            else:
                config_logger.bind(
                    event_type="api_key_remove_not_found",
                    failure_reason="key_not_found",
                ).warning(
                    f"Attempted to remove non-existent API key for provider: {provider}"
                )

            return config

        except Exception as e:
            config_logger.bind(
                event_type="api_key_remove_error",
                error_type="system_error",
                error_message=str(e),
            ).error(f"API key remove error for {provider}: {str(e)}")
            raise

    async def list_api_keys(self, current_user: models.User) -> Dict[str, dict]:
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

    async def get_configured_providers(self, current_user: models.User) -> List[str]:
        """Get list of configured providers (requires admin access)"""
        api_keys = await self.list_api_keys(current_user=current_user)
        return list(api_keys.keys())

    def preview_case_number_template(
        self, template: str, prefix: Optional[str], current_user: models.User
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
        return config.evidence_folder_templates

    async def update_evidence_folder_templates(
        self, templates: dict, current_user: models.User
    ) -> models.SystemConfiguration:
        self.case_access.require_admin(current_user)
        config_logger = get_security_logger(
            admin_user_id=current_user.id,
            action="update_evidence_templates",
            event_type="evidence_templates_update_attempt",
        )

        try:
            for template_key, template_data in templates.items():
                SystemConfigValidator.validate_evidence_template(
                    template_data, template_key
                )

            config = await self.get_configuration()
            old_template_count = len(config.evidence_folder_templates or {})

            config.evidence_folder_templates = templates
            config = self._persist_configuration(config)
            config_logger.bind(
                template_count=len(templates),
                old_template_count=old_template_count,
                event_type="evidence_templates_update_success",
            ).info("Evidence folder templates updated successfully")

            return config

        except ValidationException as e:
            config_logger.bind(
                event_type="evidence_templates_update_failed",
                failure_reason="validation_error",
                error_message=str(e),
            ).warning(f"Evidence templates update failed: {str(e)}")
            raise
        except Exception as e:
            config_logger.bind(
                event_type="evidence_templates_update_error",
                error_type="system_error",
                error_message=str(e),
            ).error(f"Evidence templates update error: {str(e)}")
            raise
