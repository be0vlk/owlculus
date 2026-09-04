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

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from ..core.dependencies import get_current_user
from ..database.connection import get_db
from ..database.db_utils import get_session
from ..database.models import User
from ..plugins.plugin_registry import PluginRegistry, shipped_plugin_registry
from ..plugins.plugin_runner import PluginRunner
from ..schemas.plugin_schema import PluginMetadata
from ..services.api_key_vault import ApiKeyVault, ConfigurationApiKeyVault
from ..services.plugin_service import PluginService

router = APIRouter(tags=["plugins"])


def get_plugin_registry() -> PluginRegistry:
    """Return the catalogue constructed once when the application is imported."""
    return shipped_plugin_registry


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


@router.get("/", response_model=dict[str, PluginMetadata])
async def list_plugins(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    api_keys: ApiKeyVault = Depends(get_plugin_api_keys),
    registry: PluginRegistry = Depends(get_plugin_registry),
):
    plugin_svc = PluginService(db, api_keys, registry=registry)
    return await plugin_svc.list_plugins(current_user=current_user)


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
    registry: PluginRegistry = Depends(get_plugin_registry),
    runner: PluginRunner = Depends(get_plugin_runner),
):
    plugin_svc = PluginService(
        db, api_keys, registry=registry, session_factory=session_factory
    )
    plugin_svc.require_execution_access(current_user)
    run_params = params or {}

    async def stream() -> AsyncGenerator[str, None]:
        with plugin_svc.open_run(run_params, current_user=current_user) as run:
            async for event in runner.run(plugin_name, run_params, run):
                yield json.dumps(event.to_wire()) + "\n"

    return StreamingResponse(
        stream(),
        media_type="application/json",
    )
