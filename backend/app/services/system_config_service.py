import os
from typing import Dict, List, Optional

from sqlmodel import Session, select

from ..core.dependencies import admin_only
from ..core.evidence_templates import DEFAULT_TEMPLATES
from ..core.logging import get_security_logger
from ..core.security import decrypt_api_key, encrypt_api_key
from ..core.utils import get_utc_now
from ..database import models


class SystemConfigService:
    def __init__(self, db: Session):
        self.db = db

    async def get_configuration(
        self, current_user: models.User = None
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

    @admin_only()
    async def update_configuration(
        self,
        case_number_template: str,
        current_user: models.User,
        case_number_prefix: Optional[str] = None,
    ) -> models.SystemConfiguration:
        config_logger = get_security_logger(
            admin_user_id=current_user.id,
            action="update_system_config",
            template=case_number_template,
            event_type="system_config_update_attempt",
        )

        try:
            if case_number_template not in ["YYMM-NN", "PREFIX-YYMM-NN"]:
                config_logger.bind(
                    event_type="system_config_update_failed",
                    failure_reason="invalid_template",
                ).warning("System config update failed: invalid case number template")
                raise ValueError("Invalid case number template")

            if case_number_template == "PREFIX-YYMM-NN":
                if not case_number_prefix:
                    config_logger.bind(
                        event_type="system_config_update_failed",
                        failure_reason="prefix_required",
                    ).warning(
                        "System config update failed: prefix required for PREFIX-YYMM-NN template"
                    )
                    raise ValueError("Prefix is required for PREFIX-YYMM-NN template")
                if (
                    not case_number_prefix.isalnum()
                    or len(case_number_prefix) < 2
                    or len(case_number_prefix) > 8
                ):
                    config_logger.bind(
                        event_type="system_config_update_failed",
                        failure_reason="invalid_prefix",
                    ).warning(
                        "System config update failed: prefix must be 2-8 alphanumeric characters"
                    )
                    raise ValueError("Prefix must be 2-8 alphanumeric characters")
            else:
                case_number_prefix = None

            config = await self.get_configuration()
            old_template = config.case_number_template
            old_prefix = config.case_number_prefix

            config.case_number_template = case_number_template
            config.case_number_prefix = case_number_prefix
            config.updated_at = get_utc_now()

            self.db.add(config)
            self.db.commit()
            self.db.refresh(config)

            config_logger.bind(
                old_template=old_template,
                new_template=case_number_template,
                old_prefix=old_prefix,
                new_prefix=case_number_prefix,
                event_type="system_config_update_success",
            ).info("System configuration updated successfully")

            return config

        except ValueError:
            raise
        except Exception as e:
            config_logger.bind(
                event_type="system_config_update_error", error_type="system_error"
            ).error(f"System config update error: {str(e)}")
            raise

    def get_template_display_name(self, template: str) -> str:
        template_names = {
            "YYMM-NN": "Monthly Reset (YYMM-NN)",
            "PREFIX-YYMM-NN": "Prefix + Monthly Reset (PREFIX-YYMM-NN)",
        }
        return template_names.get(template, template)

    def generate_example_case_number(
        self, template: str, prefix: Optional[str] = None
    ) -> str:
        current_time = get_utc_now()
        year = str(current_time.year)[2:]
        month = str(current_time.month).zfill(2)

        if template == "PREFIX-YYMM-NN" and prefix:
            return f"{prefix}-{year}{month}-01"
        else:
            return f"{year}{month}-01"

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

        config_logger = get_security_logger(
            admin_user_id=current_user.id,
            action=f"{operation_type}_api_key",
            provider=provider,
            key_name=name,
            is_new_key=is_new_key,
            event_type=f"api_key_{operation_type}_attempt",
        )

        try:
            if provider in current_keys:
                existing_data = current_keys[provider].copy()
                old_name = existing_data.get("name", "Unknown")

                key_being_updated = api_key is not None

                current_keys[provider] = {
                    "api_key": (
                        encrypt_api_key(api_key)
                        if api_key
                        else existing_data.get("api_key")
                    ),
                    "name": name,
                    "is_active": True,
                    "created_at": existing_data.get(
                        "created_at", get_utc_now().isoformat()
                    ),
                }

                config_logger = config_logger.bind(
                    old_name=old_name,
                    new_name=name,
                    key_updated=key_being_updated,
                    metadata_only=not key_being_updated,
                )
            else:
                if not api_key:
                    config_logger.bind(
                        event_type="api_key_add_failed",
                        failure_reason="api_key_required",
                    ).warning(
                        f"Failed to add new API key for {provider}: API key is required for new providers"
                    )
                    raise ValueError("API key is required for new providers")

                encrypted_key = encrypt_api_key(api_key)
                current_keys[provider] = {
                    "api_key": encrypted_key,
                    "name": name,
                    "is_active": True,
                    "created_at": get_utc_now().isoformat(),
                }

            config.api_keys = current_keys
            config.updated_at = get_utc_now()

            self.db.add(config)
            self.db.commit()
            self.db.refresh(config)

            success_event_type = f"api_key_{operation_type}_success"
            if is_new_key:
                config_logger.bind(event_type=success_event_type).info(
                    f"New API key added successfully for provider: {provider}"
                )
            else:
                config_logger.bind(event_type=success_event_type).info(
                    f"API key updated successfully for provider: {provider}"
                )

            return config

        except ValueError as e:
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

    def get_api_key(self, provider: str) -> Optional[str]:
        try:
            stmt = select(models.SystemConfiguration)
            config = self.db.exec(stmt).first()

            if not config or not config.api_keys or provider not in config.api_keys:
                env_var = f"{provider.upper()}_API_KEY"
                return os.environ.get(env_var)

            encrypted_key = config.api_keys[provider].get("api_key")
            if encrypted_key:
                return decrypt_api_key(encrypted_key)

            return None

        except Exception:
            env_var = f"{provider.upper()}_API_KEY"
            return os.environ.get(env_var)

    @admin_only()
    async def list_api_keys(self, current_user: models.User) -> Dict[str, dict]:
        try:
            stmt = select(models.SystemConfiguration)
            config = self.db.exec(stmt).first()

            if not config or not config.api_keys:
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
        api_key = self.get_api_key(provider)
        return bool(api_key)

    def get_configured_providers(self) -> List[str]:
        api_keys = self.list_api_keys()
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
        config_logger = get_security_logger(
            admin_user_id=current_user.id,
            action="update_evidence_templates",
            event_type="evidence_templates_update_attempt",
        )

        try:
            config = await self.get_configuration()
            old_templates = (
                config.evidence_folder_templates.copy()
                if config.evidence_folder_templates
                else {}
            )

            for template_key, template_data in templates.items():
                if not isinstance(template_data, dict):
                    raise ValueError(f"Invalid template structure for {template_key}")
                if "name" not in template_data or "description" not in template_data:
                    raise ValueError(
                        f"Template {template_key} must have name and description"
                    )
                if "folders" not in template_data or not isinstance(
                    template_data["folders"], list
                ):
                    raise ValueError(f"Template {template_key} must have folders array")

            config.evidence_folder_templates = templates
            config.updated_at = get_utc_now()

            self.db.add(config)
            self.db.commit()
            self.db.refresh(config)

            config_logger.bind(
                template_count=len(templates),
                old_template_count=len(old_templates),
                event_type="evidence_templates_update_success",
            ).info("Evidence folder templates updated successfully")

            return config

        except ValueError as e:
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
