from sqlmodel import Session, select
from typing import Optional
from datetime import datetime

from ..database import models
from ..core.utils import get_utc_now
from ..core.logging import get_security_logger


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
                case_number_template="YYMM-NN", case_number_prefix=None
            )
            self.db.add(config)
            self.db.commit()
            self.db.refresh(config)

        return config

    async def update_configuration(
        self, case_number_template: str, case_number_prefix: Optional[str] = None, current_user: models.User = None
    ) -> models.SystemConfiguration:
        """Update the system configuration."""
        config_logger = get_security_logger(
            admin_user_id=current_user.id if current_user else None,
            action="update_system_config",
            template=case_number_template,
            event_type="system_config_update_attempt"
        )

        try:
            # Validate template
            if case_number_template not in ["YYMM-NN", "PREFIX-YYMM-NN"]:
                config_logger.bind(
                    event_type="system_config_update_failed",
                    failure_reason="invalid_template"
                ).warning("System config update failed: invalid case number template")
                raise ValueError("Invalid case number template")

            # Validate prefix for PREFIX template
            if case_number_template == "PREFIX-YYMM-NN":
                if not case_number_prefix:
                    config_logger.bind(
                        event_type="system_config_update_failed",
                        failure_reason="prefix_required"
                    ).warning("System config update failed: prefix required for PREFIX-YYMM-NN template")
                    raise ValueError("Prefix is required for PREFIX-YYMM-NN template")
                if (
                    not case_number_prefix.isalnum()
                    or len(case_number_prefix) < 2
                    or len(case_number_prefix) > 8
                ):
                    config_logger.bind(
                        event_type="system_config_update_failed",
                        failure_reason="invalid_prefix"
                    ).warning("System config update failed: prefix must be 2-8 alphanumeric characters")
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
                event_type="system_config_update_success"
            ).info("System configuration updated successfully")

            return config

        except ValueError:
            raise
        except Exception as e:
            config_logger.bind(
                event_type="system_config_update_error",
                error_type="system_error"
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
