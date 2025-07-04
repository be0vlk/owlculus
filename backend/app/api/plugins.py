"""
API endpoints for plugin management and execution
"""

import json
from typing import Any, Dict

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..core.dependencies import get_current_user, get_db
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
    except ValueError as e:
        yield json.dumps({"type": "error", "data": {"message": str(e)}}) + "\n"
    except Exception as e:
        yield json.dumps(
            {"type": "error", "data": {"message": f"Plugin execution error: {str(e)}"}}
        ) + "\n"


@router.post("/{plugin_name}/execute")
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
