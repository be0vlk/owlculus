# ruff: noqa: B008
"""
Plugin Management and Execution API for Owlculus OSINT Platform.

This module provides the core plugin system interface for executing OSINT tools and services,
enabling extensible investigation capabilities through a standardized plugin architecture.
"""

from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Request, Response, WebSocket
from sqlalchemy.engine import Engine
from sqlmodel import Session

from ..core.database_boundary import DatabaseRoute
from ..core.dependencies import get_current_user
from ..database.connection import get_db, get_observation_engine
from ..database.models import User
from ..executions import service as execution_service
from ..plugins.plugin_registry import PluginRegistry
from ..schemas.plugin_schema import PluginMetadata
from ..services.api_key_vault import ApiKeyVault, ConfigurationApiKeyVault

router = APIRouter(tags=["plugins"], route_class=DatabaseRoute)


def get_plugin_registry(request: Request) -> PluginRegistry:
    """Return the catalogue built during application startup."""
    return request.app.state.plugin_registry


async def get_plugin_api_keys(db: Session = Depends(get_db)) -> ApiKeyVault:
    """Provide the production credential adapter to plugin run contexts."""
    return ConfigurationApiKeyVault(db)


@router.get("/", response_model=dict[str, PluginMetadata])
async def list_plugins(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    api_keys: ApiKeyVault = Depends(get_plugin_api_keys),
    registry: PluginRegistry = Depends(get_plugin_registry),
):
    return execution_service.plugin_catalogue(db, current_user, registry, api_keys)


@router.get("/executions/case/{case_id}")
async def execution_history(
    case_id: int,
    cursor: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return execution_service.history(db, current_user, case_id, cursor, limit)


@router.get("/executions/{execution_id}")
async def execution_detail(
    execution_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return execution_service.detail(db, current_user, execution_id)


@router.delete("/executions/{execution_id}")
async def cancel_execution(
    execution_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from ..executions.cancellation import request_cancel

    request_cancel(db, current_user, execution_id)
    return execution_service.detail(db, current_user, execution_id)


@router.get("/executions/{execution_id}/results")
async def execution_results(
    execution_id: int,
    cursor: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return execution_service.results(db, current_user, execution_id, cursor, limit)


@router.post("/{plugin_name}/execute", status_code=202)
async def execute_plugin(
    plugin_name: str,
    response: Response,
    params: dict[str, Any] | None = None,
    idempotency_key: str | None = Header(None, max_length=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    registry: PluginRegistry = Depends(get_plugin_registry),
):
    accepted = execution_service.accept(
        db, current_user, registry, plugin_name, params or {}, idempotency_key
    )
    response.headers["Location"] = accepted["links"]["detail"]
    return accepted


@router.websocket("/executions/{execution_id}/stream")
async def stream_execution(
    websocket: WebSocket,
    execution_id: int,
    database_engine: Engine = Depends(get_observation_engine),
):
    from app.executions.observation import observe

    await observe(websocket, database_engine, "plugin", execution_id)
