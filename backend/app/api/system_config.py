"""
API endpoints for system configuration management.

This module manages application settings, configuration updates, system parameters,
API key management, case number templates, and evidence folder templates.
Provides administrative endpoints for system configuration.

Key features include:
- System-wide configuration management with validation and template support
- Encrypted API key storage and management for external service integrations
- Case number template configuration with prefix support and preview functionality
- Evidence folder template management for consistent case organization
- Administrative access controls with comprehensive security logging and audit trails
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..core.dependencies import get_current_user
from ..database import models
from ..database.connection import get_db
from ..schemas import system_config_schema
from ..services.system_config_service import SystemConfigService

router = APIRouter()


@router.get(
    "/configuration", response_model=system_config_schema.SystemConfigurationResponse
)
async def get_configuration(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config_service = SystemConfigService(db)
    config = await config_service.get_configuration_admin(current_user=current_user)
    return system_config_schema.SystemConfigurationResponse.from_model(config)


@router.put(
    "/configuration", response_model=system_config_schema.SystemConfigurationResponse
)
async def update_configuration(
    config_data: system_config_schema.SystemConfigurationUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
async def set_api_key(
    provider: str,
    api_key_data: system_config_schema.APIKeyUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config_service = SystemConfigService(db)
    try:
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
async def remove_api_key(
    provider: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
async def list_api_keys(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config_service = SystemConfigService(db)
    return await config_service.list_api_keys(current_user=current_user)


@router.get(
    "/configuration/api-keys/{provider}/status",
    response_model=system_config_schema.APIKeyStatusResponse,
)
async def get_api_key_status(
    provider: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config_service = SystemConfigService(db)
    is_configured = config_service.is_provider_configured(provider)
    return system_config_schema.APIKeyStatusResponse(
        provider=provider, is_configured=is_configured
    )


@router.get("/configuration/preview")
async def preview_case_number_template(
    template: str,
    prefix: str = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config_service = SystemConfigService(db)
    try:
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
async def get_evidence_folder_templates(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config_service = SystemConfigService(db)
    templates = await config_service.get_evidence_folder_templates()
    return system_config_schema.EvidenceFolderTemplatesResponse(templates=templates)


@router.put("/configuration/evidence-templates")
async def update_evidence_folder_templates(
    templates_data: system_config_schema.EvidenceFolderTemplatesUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config_service = SystemConfigService(db)
    try:
        templates_dict = {}
        for key, template in templates_data.templates.items():
            templates_dict[key] = template.model_dump()

        await config_service.update_evidence_folder_templates(
            templates=templates_dict,
            current_user=current_user,
        )
        updated_templates = await config_service.get_evidence_folder_templates()
        return system_config_schema.EvidenceFolderTemplatesResponse(
            templates=updated_templates
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
