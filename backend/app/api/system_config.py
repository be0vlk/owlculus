"""Admin system configuration routes."""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.database_boundary import DatabaseRoute

from ..core.dependencies import get_current_user
from ..core.exceptions import ValidationException
from ..core.strixy_config import (
    DEFAULT_MODELS,
    PROVIDER_NAMES,
    StrixyModelQuery,
    StrixySettings,
    StrixySetup,
)
from ..database import models
from ..database.connection import get_db
from ..schemas import system_config_schema
from ..services.api_key_vault import ConfigurationApiKeyVault, Provider
from ..services.system_config_service import SystemConfigService

router = APIRouter(route_class=DatabaseRoute)


@router.get(
    "/configuration", response_model=system_config_schema.SystemConfigurationResponse
)
async def get_configuration(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config = await SystemConfigService(db).get_configuration_admin(
        current_user=current_user
    )
    return system_config_schema.SystemConfigurationResponse.from_model(config)


@router.put(
    "/configuration", response_model=system_config_schema.SystemConfigurationResponse
)
async def update_configuration(
    config_data: system_config_schema.SystemConfigurationUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config = await SystemConfigService(db).update_configuration(
        case_number_template=config_data.case_number_template,
        case_number_prefix=config_data.case_number_prefix,
        current_user=current_user,
    )
    return system_config_schema.SystemConfigurationResponse.from_model(config)


@router.put(
    "/configuration/api-keys/{provider}",
    response_model=system_config_schema.SystemConfigurationResponse,
)
async def set_api_key(
    provider: Provider,
    api_key_data: system_config_schema.APIKeyUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not api_key_data.api_key and not api_key_data.name:
        raise ValidationException("Either api_key or name must be provided")

    config = await SystemConfigService(db).set_api_key(
        provider=provider,
        api_key=api_key_data.api_key,
        name=api_key_data.name or f"{provider.value.title()} API",
        current_user=current_user,
    )
    return system_config_schema.SystemConfigurationResponse.from_model(config)


@router.delete(
    "/configuration/api-keys/{provider}",
    response_model=system_config_schema.SystemConfigurationResponse,
)
async def remove_api_key(
    provider: Provider,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config = await SystemConfigService(db).remove_api_key(
        provider=provider,
        current_user=current_user,
    )
    return system_config_schema.SystemConfigurationResponse.from_model(config)


@router.get("/configuration/api-keys", response_model=dict)
async def list_api_keys(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await SystemConfigService(db).list_api_keys(current_user=current_user)


@router.get(
    "/configuration/api-keys/{provider}/status",
    response_model=system_config_schema.APIKeyStatusResponse,
)
async def get_api_key_status(
    provider: Provider,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    await SystemConfigService(db).get_configuration_admin(current_user=current_user)
    vault = ConfigurationApiKeyVault(db)
    is_configured = vault.is_configured(provider)
    return system_config_schema.APIKeyStatusResponse(
        provider=provider.value, is_configured=is_configured
    )


@router.get("/configuration/preview")
async def preview_case_number_template(
    template: str,
    prefix: str | None = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    example, display_name = SystemConfigService(db).preview_case_number_template(
        template, prefix, current_user
    )
    return system_config_schema.SystemConfigurationPreview(
        template=template,
        prefix=prefix,
        example_case_number=example,
        display_name=display_name,
    )


@router.get("/configuration/evidence-templates")
async def get_evidence_folder_templates(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    templates = await SystemConfigService(db).get_evidence_folder_templates()
    return system_config_schema.EvidenceFolderTemplatesResponse(templates=templates)


@router.put("/configuration/evidence-templates")
async def update_evidence_folder_templates(
    templates_data: system_config_schema.EvidenceFolderTemplatesUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config_service = SystemConfigService(db)
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


def _strixy_response(settings: StrixySettings, db: Session) -> dict:
    vault = ConfigurationApiKeyVault(db)
    return settings.model_dump() | {
        "providers": {
            key: {
                "name": name,
                "default_model": DEFAULT_MODELS[key],
                "key_configured": vault.is_configured(Provider(key)),
            }
            for key, name in PROVIDER_NAMES.items()
        }
    }


@router.get("/configuration/strixy")
async def get_strixy_settings(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _strixy_response(
        await SystemConfigService(db).get_strixy_settings(current_user), db
    )


@router.put("/configuration/strixy")
async def update_strixy_settings(
    setup: StrixySetup,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = SystemConfigService(db)
    service.case_access.require_admin(current_user)
    await service.require_key_for_changed_base_url(
        setup.provider, setup.base_url, setup.api_key
    )
    if setup.api_key:
        await service.set_api_key(
            provider=Provider(setup.provider),
            api_key=setup.api_key,
            name=f"{PROVIDER_NAMES[setup.provider]} API",
            current_user=current_user,
        )
    settings = StrixySettings.model_validate(setup.model_dump(exclude={"api_key"}))
    return _strixy_response(
        await service.update_strixy_settings(settings, current_user), db
    )


@router.post("/configuration/strixy/models")
async def list_strixy_models(
    query: StrixyModelQuery,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {
        "models": await SystemConfigService(db).list_strixy_models(query, current_user)
    }


@router.post("/configuration/strixy/test")
async def test_strixy_connection(
    setup: StrixySetup,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await SystemConfigService(db).test_strixy_connection(setup, current_user)
