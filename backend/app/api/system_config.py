from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..database.connection import get_db
from ..database import models
from ..schemas import system_config_schema
from ..services.system_config_service import SystemConfigService
from ..core.dependencies import get_current_user, admin_only

router = APIRouter()


@router.get(
    "/configuration", response_model=system_config_schema.SystemConfigurationResponse
)
@admin_only()
async def get_configuration(
    current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get current system configuration (admin only)."""
    config_service = SystemConfigService(db)
    config = await config_service.get_configuration()
    return config


@router.put(
    "/configuration", response_model=system_config_schema.SystemConfigurationResponse
)
@admin_only()
async def update_configuration(
    config_data: system_config_schema.SystemConfigurationUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update system configuration (admin only)."""
    config_service = SystemConfigService(db)
    try:
        config = await config_service.update_configuration(
            case_number_template=config_data.case_number_template,
            case_number_prefix=config_data.case_number_prefix,
        )
        return config
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/configuration/preview",
    response_model=system_config_schema.SystemConfigurationPreview,
)
@admin_only()
async def preview_configuration(
    template: str,
    prefix: str = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Preview case number format with given template and prefix (admin only)."""
    config_service = SystemConfigService(db)

    # Validate template
    if template not in ["YYMM-NN", "PREFIX-YYMM-NN"]:
        raise HTTPException(status_code=400, detail="Invalid template")

    # Generate example
    example = config_service.generate_example_case_number(template, prefix)
    display_name = config_service.get_template_display_name(template)

    return system_config_schema.SystemConfigurationPreview(
        template=template,
        prefix=prefix,
        example_case_number=example,
        display_name=display_name,
    )
