# ruff: noqa: B008
"""
Plugin Management and Execution API for Owlculus OSINT Platform.

This module provides the core plugin system interface for executing OSINT tools and services,
enabling extensible investigation capabilities through a standardized plugin architecture.
"""

import json
from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractContextManager
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from ..core.dependencies import get_current_user
from ..database.connection import get_db
from ..database.db_utils import get_session
from ..database.models import User
from ..plugins.plugin_context import ProductionPluginRunAdapter
from ..plugins.plugin_registry import PluginRegistry
from ..plugins.plugin_runner import PluginRunner
from ..schemas.plugin_schema import PluginMetadata
from ..services.api_key_vault import ApiKeyVault, ConfigurationApiKeyVault
from ..services.case_access import CaseAccess

router = APIRouter(tags=["plugins"])


def get_plugin_registry(request: Request) -> PluginRegistry:
    """Return the catalogue built during application startup."""
    return request.app.state.plugin_registry


def get_plugin_runner(
    registry: PluginRegistry = Depends(get_plugin_registry),
) -> PluginRunner:
    return PluginRunner(registry)


def get_plugin_api_keys(db: Session = Depends(get_db)) -> ApiKeyVault:
    """Provide the production credential adapter to plugin run contexts."""
    return ConfigurationApiKeyVault(db)


def get_plugin_session_factory() -> Callable[[], AbstractContextManager[Session]]:
    """Open a session whose lifetime is scoped to streamed plugin iteration."""
    return get_session


def build_run_adapter(
    api_keys: ApiKeyVault,
    session_factory: Callable[[], AbstractContextManager[Session]],
) -> ProductionPluginRunAdapter:
    """Bind streamed runs to their own session and credential adapter."""
    api_key_vault_factory = (
        ConfigurationApiKeyVault
        if isinstance(api_keys, ConfigurationApiKeyVault)
        else lambda _: api_keys
    )
    return ProductionPluginRunAdapter(session_factory, api_key_vault_factory)


@router.get("/", response_model=dict[str, PluginMetadata])
async def list_plugins(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    api_keys: ApiKeyVault = Depends(get_plugin_api_keys),
    registry: PluginRegistry = Depends(get_plugin_registry),
):
    CaseAccess(db).require_non_analyst(current_user)
    return registry.metadata(api_keys)


@router.post("/{plugin_name}/execute")
async def execute_plugin(
    plugin_name: str,
    params: dict[str, Any] | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    api_keys: ApiKeyVault = Depends(get_plugin_api_keys),
    session_factory: Callable[[], AbstractContextManager[Session]] = Depends(
        get_plugin_session_factory
    ),
    runner: PluginRunner = Depends(get_plugin_runner),
):
    CaseAccess(db).require_non_analyst(current_user)
    run_params = dict(params or {})
    case_id = run_params.pop("case_id", None)
    if type(case_id) is not int or case_id <= 0:
        raise HTTPException(
            status_code=422, detail="A positive integer case_id is required"
        )
    save_to_case = run_params.pop("save_to_case", False)
    if not isinstance(save_to_case, bool):
        raise HTTPException(status_code=422, detail="save_to_case must be a boolean")
    access = CaseAccess(db)
    if save_to_case:
        access.writable(current_user, case_id)
    else:
        access.readable(current_user, case_id)
    run_adapter = build_run_adapter(api_keys, session_factory)

    async def stream() -> AsyncGenerator[str, None]:
        with run_adapter.open(
            user=current_user,
            case_id=case_id,
            save_to_case=save_to_case,
        ) as run:
            async for event in runner.run(plugin_name, run_params, run):
                yield json.dumps(event.to_wire()) + "\n"

    return StreamingResponse(
        stream(),
        media_type="application/json",
    )
