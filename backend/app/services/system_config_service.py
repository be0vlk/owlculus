from sqlmodel import Session, select
from typing import Optional
from datetime import datetime

from ..database import models
from ..core.utils import get_utc_now


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
        self, case_number_template: str, case_number_prefix: Optional[str] = None
    ) -> models.SystemConfiguration:
        """Update the system configuration."""
        # Validate template
        if case_number_template not in ["YYMM-NN", "PREFIX-YYMM-NN"]:
            raise ValueError("Invalid case number template")

        # Validate prefix for PREFIX template
        if case_number_template == "PREFIX-YYMM-NN":
            if not case_number_prefix:
                raise ValueError("Prefix is required for PREFIX-YYMM-NN template")
            if (
                not case_number_prefix.isalnum()
                or len(case_number_prefix) < 2
                or len(case_number_prefix) > 8
            ):
                raise ValueError("Prefix must be 2-8 alphanumeric characters")
        else:
            case_number_prefix = None  # Clear prefix for non-prefix templates

        config = await self.get_configuration()
        config.case_number_template = case_number_template
        config.case_number_prefix = case_number_prefix
        config.updated_at = get_utc_now()

        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)

        return config

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
