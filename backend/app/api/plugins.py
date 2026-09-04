"""
Plugin Management and Execution API for Owlculus OSINT Platform.

This module provides the core plugin system interface for executing OSINT tools and services,
enabling extensible investigation capabilities through a standardized plugin architecture.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from ..core.dependencies import get_current_user
from ..database.connection import get_db
from ..database.models import User
from ..schemas.plugin_schema import PluginMetadata
from ..services.plugin_service import PluginService

router = APIRouter(tags=["plugins"])


@router.get("/", response_model=Dict[str, PluginMetadata])
async def list_plugins(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    plugin_svc = PluginService(db)
    return await plugin_svc.list_plugins(current_user=current_user)


@router.post("/{plugin_name}/execute")
async def execute_plugin(
    plugin_name: str,
    params: Dict[str, Any] | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plugin_svc = PluginService(db)
    stream = await plugin_svc.stream_plugin_execution(
        plugin_name, params, current_user=current_user
    )
    return StreamingResponse(
        stream,
        media_type="application/json",
    )
