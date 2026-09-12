"""
API endpoints for Strixy service integration (external OSINT service).

This module handles Strixy-specific OSINT data retrieval and processing,
providing chat interface functionality for interacting with the Strixy
service for intelligence gathering operations.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.core.database_boundary import DatabaseRoute
from app.core.dependencies import get_current_user
from app.database import models
from app.database.connection import get_db
from app.schemas.strixy_schema import ChatRequest, ChatResponse
from app.services.api_key_vault import ConfigurationApiKeyVault, Provider
from app.services.strixy_access import require_strixy_access
from app.services.strixy_service import StrixyService

router = APIRouter(route_class=DatabaseRoute)


@router.get("/availability")
async def strixy_availability(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
    case_id: Annotated[int, Query(gt=0)],
) -> dict[str, bool]:
    require_strixy_access(db, current_user, case_id)
    return {
        "is_configured": bool(ConfigurationApiKeyVault(db).get_key(Provider.OPENAI))
    }


@router.post("/chat", response_model=ChatResponse)
async def chat_with_strixy(
    request: ChatRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
) -> ChatResponse:
    require_strixy_access(db, current_user, request.case_id)
    service = StrixyService(db)
    return await service.send_chat_message(request.messages)
