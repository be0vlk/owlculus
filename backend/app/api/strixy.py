"""
API endpoints for Strixy service integration (external OSINT service).

This module handles Strixy-specific OSINT data retrieval and processing,
providing chat interface functionality for interacting with the Strixy
service for intelligence gathering operations.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.dependencies import get_current_user
from app.database import models
from app.database.connection import get_db
from app.schemas.strixy_schema import ChatRequest, ChatResponse
from app.services.case_access import CaseAccess
from app.services.strixy_service import StrixyService

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat_with_strixy(
    request: ChatRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
) -> ChatResponse:
    CaseAccess(db).readable(current_user, request.case_id)
    service = StrixyService(db)
    return await service.send_chat_message(request.messages)
