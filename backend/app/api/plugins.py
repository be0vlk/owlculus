"""
Plugin Management and Execution API for Owlculus OSINT Platform.

This module provides the core plugin system interface for executing OSINT tools and services,
enabling extensible investigation capabilities through a standardized plugin architecture.

Key features include:
- Plugin discovery and metadata retrieval for available OSINT tools
- Secure plugin execution with streaming JSON response handling
- Role-based plugin access control preventing unauthorized tool usage
- Standardized plugin interface supporting various OSINT data sources
- Error handling and logging for plugin execution monitoring
- Extensible architecture allowing custom OSINT tool integration
"""

import json
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..core.dependencies import get_current_user, get_db, no_analyst
from ..core.exceptions import ResourceNotFoundException
from ..database.models import User
from ..schemas.plugin_schema import PluginMetadata
from ..services.plugin_service import PluginService

router = APIRouter(tags=["plugins"])


@router.get("/", response_model=Dict[str, PluginMetadata])
@no_analyst()
async def list_plugins(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    plugin_svc = PluginService(db)
    try:
        return await plugin_svc.list_plugins(current_user=current_user)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


async def stream_generator(
    plugin_name: str,
    params: Dict[str, Any] = None,
    current_user: User = None,
    db: Session = None,
):
    try:
        plugin_svc = PluginService(db)
        result = await plugin_svc.execute_plugin(
            plugin_name, params, current_user=current_user
        )
        async for line in result:
            yield json.dumps(line) + "\n"
    except ResourceNotFoundException as e:
        yield json.dumps({"type": "error", "data": {"message": str(e)}}) + "\n"
    except Exception as e:
        yield json.dumps(
            {"type": "error", "data": {"message": f"Plugin execution error: {str(e)}"}}
        ) + "\n"


@router.post("/{plugin_name}/execute")
@no_analyst()
async def execute_plugin(
    plugin_name: str,
    params: Dict[str, Any] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return StreamingResponse(
        stream_generator(plugin_name, params, current_user, db),
        media_type="application/json",
    )
