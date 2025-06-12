from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..core.dependencies import admin_only, get_current_active_user
from ..database import models
from ..database.connection import get_db
from ..schemas import system_config_schema
from ..services.system_config_service import SystemConfigService

router = APIRouter()


@router.get(
    "/configuration", response_model=system_config_schema.SystemConfigurationResponse
)
@admin_only()
async def get_configuration(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get current system configuration (admin only)."""
    config_service = SystemConfigService(db)
    config = await config_service.get_configuration()
    return system_config_schema.SystemConfigurationResponse.from_model(config)


@router.put(
    "/configuration", response_model=system_config_schema.SystemConfigurationResponse
)
@admin_only()
async def update_configuration(
    config_data: system_config_schema.SystemConfigurationUpdate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Update system configuration (admin only)."""
    config_service = SystemConfigService(db)
    try:
        config = await config_service.update_configuration(
            case_number_template=config_data.case_number_template,
            case_number_prefix=config_data.case_number_prefix,
            current_user=current_user,
        )
        return system_config_schema.SystemConfigurationResponse.from_model(config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put(
    "/configuration/api-keys/{provider}",
    response_model=system_config_schema.SystemConfigurationResponse,
)
@admin_only()
async def set_api_key(
    provider: str,
    api_key_data: system_config_schema.APIKeyUpdate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Set or update an API key for a specific provider (admin only)."""
    config_service = SystemConfigService(db)
    try:
        # Validate that at least one field is provided
        if not api_key_data.api_key and not api_key_data.name:
            raise HTTPException(
                status_code=400, detail="Either api_key or name must be provided"
            )

        config = await config_service.set_api_key(
            provider=provider,
            api_key=api_key_data.api_key,
            name=api_key_data.name or f"{provider.title()} API",
            current_user=current_user,
        )
        return system_config_schema.SystemConfigurationResponse.from_model(config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/configuration/api-keys/{provider}",
    response_model=system_config_schema.SystemConfigurationResponse,
)
@admin_only()
async def remove_api_key(
    provider: str,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Remove an API key for a specific provider (admin only)."""
    config_service = SystemConfigService(db)
    try:
        config = await config_service.remove_api_key(
            provider=provider,
            current_user=current_user,
        )
        return system_config_schema.SystemConfigurationResponse.from_model(config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/configuration/api-keys", response_model=dict)
@admin_only()
async def list_api_keys(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List all configured API keys with masked keys (admin only)."""
    config_service = SystemConfigService(db)
    return config_service.list_api_keys()


@router.get(
    "/configuration/api-keys/{provider}/status",
    response_model=system_config_schema.APIKeyStatusResponse,
)
async def get_api_key_status(
    provider: str,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Check if a specific provider has an API key configured."""
    config_service = SystemConfigService(db)
    is_configured = config_service.is_provider_configured(provider)
    return system_config_schema.APIKeyStatusResponse(
        provider=provider, is_configured=is_configured
    )


@router.get("/configuration/preview")
@admin_only()
async def preview_case_number_template(
    template: str,
    prefix: str = None,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Preview what a case number would look like with given template and prefix."""
    config_service = SystemConfigService(db)
    try:
        # Validate template
        if template not in ["YYMM-NN", "PREFIX-YYMM-NN"]:
            raise HTTPException(status_code=400, detail="Invalid template")

        example = config_service.generate_example_case_number(template, prefix)
        display_name = config_service.get_template_display_name(template)
        return system_config_schema.SystemConfigurationPreview(
            template=template,
            prefix=prefix,
            example_case_number=example,
            display_name=display_name,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/configuration/evidence-templates")
@admin_only()
async def get_evidence_folder_templates(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get evidence folder templates (admin only)."""
    config_service = SystemConfigService(db)
    templates = await config_service.get_evidence_folder_templates()
    return system_config_schema.EvidenceFolderTemplatesResponse(templates=templates)


@router.put("/configuration/evidence-templates")
@admin_only()
async def update_evidence_folder_templates(
    templates_data: system_config_schema.EvidenceFolderTemplatesUpdate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Update evidence folder templates (admin only)."""
    config_service = SystemConfigService(db)
    try:
        # Convert Pydantic models to dictionaries
        templates_dict = {}
        for key, template in templates_data.templates.items():
            templates_dict[key] = template.model_dump()

        await config_service.update_evidence_folder_templates(
            templates=templates_dict,
            current_user=current_user,
        )
        # Return updated templates
        updated_templates = await config_service.get_evidence_folder_templates()
        return system_config_schema.EvidenceFolderTemplatesResponse(
            templates=updated_templates
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
