"""
Business logic for system configuration management.

This module handles system settings, configuration validation, and updates including
case number templates, API key management, evidence folder templates, and
administrative system configuration functionality.
"""

import os
from typing import Dict, List, Optional, Tuple

from sqlmodel import Session, select

from ..core.dependencies import admin_only
from ..core.evidence_templates import DEFAULT_TEMPLATES
from ..core.logging import get_security_logger
from ..core.security import decrypt_api_key, encrypt_api_key
from ..core.utils import get_utc_now
from ..database import models

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


class SystemConfigError(Exception):
    """Base exception for system configuration errors"""

    pass


class CaseNumberTemplateError(SystemConfigError):
    """Raised when case number template is invalid"""

    pass


class ApiKeyError(SystemConfigError):
    """Raised when API key operations fail"""

    pass


class EvidenceTemplateError(SystemConfigError):
    """Raised when evidence template operations fail"""

    pass


class SystemConfigValidator:
    """Handles validation logic for system configuration"""

    @staticmethod
    def validate_case_number_template(template: str) -> None:
        """Validate case number template format"""
        if template not in VALID_CASE_NUMBER_TEMPLATES:
            raise CaseNumberTemplateError(f"Invalid case number template: {template}")

    @staticmethod
    def validate_case_number_prefix(prefix: Optional[str], template: str) -> None:
        """Validate case number prefix based on template"""
        if template == CASE_NUMBER_TEMPLATE_PREFIX:
            if not prefix:
                raise CaseNumberTemplateError(
                    "Prefix is required for PREFIX-YYMM-NN template"
                )

            if not prefix.isalnum():
                raise CaseNumberTemplateError(
                    "Prefix must contain only alphanumeric characters"
                )

            if len(prefix) < PREFIX_MIN_LENGTH or len(prefix) > PREFIX_MAX_LENGTH:
                raise CaseNumberTemplateError(
                    f"Prefix must be {PREFIX_MIN_LENGTH}-{PREFIX_MAX_LENGTH} characters"
                )

    @staticmethod
    def validate_evidence_template(template_data: dict, template_key: str) -> None:
        """Validate evidence folder template structure"""
        if not isinstance(template_data, dict):
            raise EvidenceTemplateError(
                f"Invalid template structure for {template_key}"
            )

        required_fields = ["name", "description", "folders"]
        for field in required_fields:
            if field not in template_data:
                raise EvidenceTemplateError(
                    f"Template {template_key} must have {field}"
                )

        if not isinstance(template_data["folders"], list):
            raise EvidenceTemplateError(
                f"Template {template_key} must have folders array"
            )


class SystemConfigService:
    def __init__(self, db: Session) -> None:
        self.db = db

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
                evidence_folder_templates=self._get_default_templates(),
            )
            self.db.add(config)
            self.db.commit()
            self.db.refresh(config)

        return config

    @admin_only()
    async def get_configuration_admin(
        self, current_user: models.User
    ) -> models.SystemConfiguration:
        """Admin-only method to get configuration."""
        return await self.get_configuration()

    def _create_config_logger(self, user_id: int, action: str, **kwargs) -> any:
        """Create a security logger with common parameters"""
        return get_security_logger(admin_user_id=user_id, action=action, **kwargs)

    def _normalize_prefix(self, template: str, prefix: Optional[str]) -> Optional[str]:
        """Normalize prefix based on template type"""
        return None if template != CASE_NUMBER_TEMPLATE_PREFIX else prefix

    def _save_configuration(
        self, config: models.SystemConfiguration
    ) -> models.SystemConfiguration:
        """Save configuration changes to database"""
        config.updated_at = get_utc_now()
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return config

    @admin_only()
    async def update_configuration(
        self,
        case_number_template: str,
        current_user: models.User,
        case_number_prefix: Optional[str] = None,
    ) -> models.SystemConfiguration:
        config_logger = self._create_config_logger(
            user_id=current_user.id,
            action="update_system_config",
            template=case_number_template,
            event_type="system_config_update_attempt",
        )

        try:
            SystemConfigValidator.validate_case_number_template(case_number_template)
            SystemConfigValidator.validate_case_number_prefix(
                case_number_prefix, case_number_template
            )

            case_number_prefix = self._normalize_prefix(
                case_number_template, case_number_prefix
            )

            config = await self.get_configuration()
            old_template = config.case_number_template
            old_prefix = config.case_number_prefix

            config.case_number_template = case_number_template
            config.case_number_prefix = case_number_prefix

            config = self._save_configuration(config)
            config_logger.bind(
                old_template=old_template,
                new_template=case_number_template,
                old_prefix=old_prefix,
                new_prefix=case_number_prefix,
                event_type="system_config_update_success",
            ).info("System configuration updated successfully")

            return config

        except CaseNumberTemplateError as e:
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
        current_time = get_utc_now()
        year = str(current_time.year)[2:]
        month = str(current_time.month).zfill(2)

        if template == CASE_NUMBER_TEMPLATE_PREFIX and prefix:
            return f"{prefix}-{year}{month}-01"
        return f"{year}{month}-01"

    def _create_api_key_data(
        self, api_key: Optional[str], name: str, created_at: Optional[str] = None
    ) -> dict:
        """Create API key data structure"""
        return {
            "api_key": encrypt_api_key(api_key) if api_key else None,
            "name": name,
            "is_active": True,
            "created_at": created_at or get_utc_now().isoformat(),
        }

    def _update_existing_api_key(
        self, current_keys: dict, provider: str, api_key: Optional[str], name: str
    ) -> Tuple[dict, dict]:
        """Update existing API key and return updated keys and metadata"""
        existing_data = current_keys[provider].copy()
        old_name = existing_data.get("name", "Unknown")
        key_being_updated = api_key is not None

        updated_data = self._create_api_key_data(
            api_key if api_key else None, name, existing_data.get("created_at")
        )

        if not key_being_updated:
            updated_data["api_key"] = existing_data.get("api_key")

        current_keys[provider] = updated_data

        metadata = {
            "old_name": old_name,
            "new_name": name,
            "key_updated": key_being_updated,
            "metadata_only": not key_being_updated,
        }

        return current_keys, metadata

    def _add_new_api_key(
        self, current_keys: dict, provider: str, api_key: str, name: str
    ) -> dict:
        """Add new API key"""
        if not api_key:
            raise ApiKeyError("API key is required for new providers")

        current_keys[provider] = self._create_api_key_data(api_key, name)
        return current_keys

    @admin_only()
    async def set_api_key(
        self,
        provider: str,
        api_key: Optional[str],
        name: str,
        current_user: models.User,
    ) -> models.SystemConfiguration:
        config = await self.get_configuration()
        current_keys = config.api_keys.copy() if config.api_keys else {}
        is_new_key = provider not in current_keys
        operation_type = "add" if is_new_key else "update"

        config_logger = self._create_config_logger(
            user_id=current_user.id,
            action=f"{operation_type}_api_key",
            provider=provider,
            key_name=name,
            is_new_key=is_new_key,
            event_type=f"api_key_{operation_type}_attempt",
        )

        try:
            if is_new_key:
                current_keys = self._add_new_api_key(
                    current_keys, provider, api_key, name
                )
            else:
                current_keys, metadata = self._update_existing_api_key(
                    current_keys, provider, api_key, name
                )
                config_logger = config_logger.bind(**metadata)

            config.api_keys = current_keys
            config = self._save_configuration(config)
            config_logger.bind(event_type=f"api_key_{operation_type}_success").info(
                f"API key {operation_type}d successfully for provider: {provider}"
            )

            return config

        except ApiKeyError as e:
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

    @admin_only()
    async def remove_api_key(
        self, provider: str, current_user: models.User
    ) -> models.SystemConfiguration:
        config = await self.get_configuration()

        existing_key_data = None
        if config.api_keys and provider in config.api_keys:
            existing_key_data = config.api_keys[provider]

        config_logger = get_security_logger(
            admin_user_id=current_user.id,
            action="remove_api_key",
            provider=provider,
            key_name=existing_key_data.get("name") if existing_key_data else None,
            key_existed=existing_key_data is not None,
            event_type="api_key_remove_attempt",
        )

        try:
            if config.api_keys and provider in config.api_keys:
                current_keys = config.api_keys.copy()
                removed_key_data = current_keys[provider]
                del current_keys[provider]
                config.api_keys = current_keys
                config.updated_at = get_utc_now()

                self.db.add(config)
                self.db.commit()
                self.db.refresh(config)

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

    def _get_env_api_key(self, provider: str) -> Optional[str]:
        """Get API key from environment variable"""
        env_var = f"{provider.upper()}_API_KEY"
        return os.environ.get(env_var)

    def get_api_key(self, provider: str) -> Optional[str]:
        """Get decrypted API key for a provider"""
        try:
            stmt = select(models.SystemConfiguration)
            config = self.db.exec(stmt).first()

            if not config or not config.api_keys or provider not in config.api_keys:
                return self._get_env_api_key(provider)

            encrypted_key = config.api_keys[provider].get("api_key")
            if encrypted_key:
                return decrypt_api_key(encrypted_key)

            return None

        except Exception:
            return self._get_env_api_key(provider)

    @admin_only()
    async def list_api_keys(self, current_user: models.User) -> Dict[str, dict]:
        """List all configured API keys (admin only)"""
        try:
            config = await self.get_configuration()

            if not config.api_keys:
                return {}

            result = {}
            for provider, key_data in config.api_keys.items():
                if key_data.get("is_active", True):
                    result[provider] = {
                        "name": key_data.get("name", provider),
                        "is_configured": True,
                        "created_at": key_data.get("created_at"),
                    }

            return result

        except Exception:
            return {}

    def is_provider_configured(self, provider: str) -> bool:
        """Check if a provider has a configured API key"""
        api_key = self.get_api_key(provider)
        return bool(api_key)

    async def get_configured_providers(self, current_user: models.User) -> List[str]:
        """Get list of configured providers (requires admin access)"""
        api_keys = await self.list_api_keys(current_user=current_user)
        return list(api_keys.keys())

    def _get_default_templates(self) -> dict:
        return DEFAULT_TEMPLATES.copy()

    async def get_evidence_folder_templates(self) -> dict:
        config = await self.get_configuration()
        if not config.evidence_folder_templates:
            config.evidence_folder_templates = self._get_default_templates()
            config.updated_at = get_utc_now()
            self.db.add(config)
            self.db.commit()
            self.db.refresh(config)
        return config.evidence_folder_templates

    @admin_only()
    async def update_evidence_folder_templates(
        self, templates: dict, current_user: models.User
    ) -> models.SystemConfiguration:
        config_logger = self._create_config_logger(
            user_id=current_user.id,
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
            config = self._save_configuration(config)
            config_logger.bind(
                template_count=len(templates),
                old_template_count=old_template_count,
                event_type="evidence_templates_update_success",
            ).info("Evidence folder templates updated successfully")

            return config

        except EvidenceTemplateError as e:
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
