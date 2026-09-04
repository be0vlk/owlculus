# ruff: noqa: B008
"""
Plugin Management and Execution API for Owlculus OSINT Platform.

This module provides the core plugin system interface for executing OSINT tools and services,
enabling extensible investigation capabilities through a standardized plugin architecture.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from ..core.dependencies import get_current_user
from ..database.connection import get_db
from ..database.db_utils import get_session
from ..database.models import User
from ..schemas.plugin_schema import PluginMetadata
from ..services.api_key_vault import ApiKeyVault, ConfigurationApiKeyVault
from ..services.plugin_service import PluginService

router = APIRouter(tags=["plugins"])


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
):
    plugin_svc = PluginService(db, api_keys)
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
):
    plugin_svc = PluginService(db, api_keys, session_factory=session_factory)
    stream = await plugin_svc.stream_plugin_execution(
        plugin_name, params, current_user=current_user
    )
    return StreamingResponse(
        stream,
        media_type="application/json",
    )
