from sqlmodel import Session, select
from typing import Optional, Dict, List
from datetime import datetime
import os

from ..database import models
from ..core.utils import get_utc_now
from ..core.logging import get_security_logger
from ..core.security import encrypt_api_key, decrypt_api_key


class SystemConfigService:
    def __init__(self, db: Session):
        self.db = db

    async def get_configuration(self) -> models.SystemConfiguration:
        """Get the system configuration. Creates default if none exists."""
        stmt = select(models.SystemConfiguration)
        config = self.db.exec(stmt).first()

        if not config:
            # Create default configuration
            config = models.SystemConfiguration(
                case_number_template="YYMM-NN", case_number_prefix=None, api_keys={}
            )
            self.db.add(config)
            self.db.commit()
            self.db.refresh(config)

        return config

    async def update_configuration(
        self,
        case_number_template: str,
        case_number_prefix: Optional[str] = None,
        current_user: models.User = None,
    ) -> models.SystemConfiguration:
        """Update the system configuration."""
        config_logger = get_security_logger(
            admin_user_id=current_user.id if current_user else None,
            action="update_system_config",
            template=case_number_template,
            event_type="system_config_update_attempt",
        )

        try:
            # Validate template
            if case_number_template not in ["YYMM-NN", "PREFIX-YYMM-NN"]:
                config_logger.bind(
                    event_type="system_config_update_failed",
                    failure_reason="invalid_template",
                ).warning("System config update failed: invalid case number template")
                raise ValueError("Invalid case number template")

            # Validate prefix for PREFIX template
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
                case_number_prefix = None  # Clear prefix for non-prefix templates

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
        """Get user-friendly display name for template."""
        template_names = {
            "YYMM-NN": "Monthly Reset (YYMM-NN)",
            "PREFIX-YYMM-NN": "Prefix + Monthly Reset (PREFIX-YYMM-NN)",
        }
        return template_names.get(template, template)

    def generate_example_case_number(
        self, template: str, prefix: Optional[str] = None
    ) -> str:
        """Generate an example case number for preview purposes."""
        current_time = get_utc_now()
        year = str(current_time.year)[2:]  # Last 2 digits
        month = str(current_time.month).zfill(2)

        if template == "PREFIX-YYMM-NN" and prefix:
            return f"{prefix}-{year}{month}-01"
        else:
            return f"{year}{month}-01"

    async def set_api_key(
        self,
        provider: str,
        api_key: Optional[str],
        name: str,
        current_user: models.User,
    ) -> models.SystemConfiguration:
        """Set or update an API key for a specific provider."""
        config_logger = get_security_logger(
            admin_user_id=current_user.id,
            action="set_api_key",
            provider=provider,
            event_type="api_key_set_attempt",
        )

        try:
            config = await self.get_configuration()

            # Create a new dictionary to ensure SQLAlchemy detects the change
            current_keys = config.api_keys.copy() if config.api_keys else {}

            # If updating existing provider, preserve existing data
            if provider in current_keys:
                existing_data = current_keys[provider].copy()
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
            else:
                # New provider - API key is required
                if not api_key:
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

            config_logger.bind(
                provider=provider, key_name=name, event_type="api_key_set_success"
            ).info(f"API key set successfully for provider: {provider}")

            return config

        except Exception as e:
            config_logger.bind(
                event_type="api_key_set_error",
                provider=provider,
                error_type="system_error",
            ).error(f"API key set error for {provider}: {str(e)}")
            raise

    async def remove_api_key(
        self, provider: str, current_user: models.User
    ) -> models.SystemConfiguration:
        """Remove an API key for a specific provider."""
        config_logger = get_security_logger(
            admin_user_id=current_user.id,
            action="remove_api_key",
            provider=provider,
            event_type="api_key_remove_attempt",
        )

        try:
            config = await self.get_configuration()

            if config.api_keys and provider in config.api_keys:
                # Create a new dictionary to ensure SQLAlchemy detects the change
                current_keys = config.api_keys.copy()
                del current_keys[provider]
                config.api_keys = current_keys
                config.updated_at = get_utc_now()

                self.db.add(config)
                self.db.commit()
                self.db.refresh(config)

                config_logger.bind(
                    provider=provider, event_type="api_key_remove_success"
                ).info(f"API key removed successfully for provider: {provider}")
            else:
                config_logger.bind(
                    provider=provider, event_type="api_key_remove_not_found"
                ).warning(f"API key not found for provider: {provider}")

            return config

        except Exception as e:
            config_logger.bind(
                event_type="api_key_remove_error",
                provider=provider,
                error_type="system_error",
            ).error(f"API key remove error for {provider}: {str(e)}")
            raise

    def get_api_key(self, provider: str) -> Optional[str]:
        """Get decrypted API key for a specific provider."""
        try:
            stmt = select(models.SystemConfiguration)
            config = self.db.exec(stmt).first()

            if not config or not config.api_keys or provider not in config.api_keys:
                # Fallback to environment variable
                env_var = f"{provider.upper()}_API_KEY"
                return os.environ.get(env_var)

            encrypted_key = config.api_keys[provider].get("api_key")
            if encrypted_key:
                return decrypt_api_key(encrypted_key)

            return None

        except Exception:
            # Fallback to environment variable on any error
            env_var = f"{provider.upper()}_API_KEY"
            return os.environ.get(env_var)

    def list_api_keys(self) -> Dict[str, dict]:
        """List all configured API keys with masked keys."""
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
        """Check if a specific provider has an API key configured."""
        api_key = self.get_api_key(provider)
        return bool(api_key)

    def get_configured_providers(self) -> List[str]:
        """Get list of all configured provider names."""
        api_keys = self.list_api_keys()
        return list(api_keys.keys())
