"""
API endpoints for Strixy service integration (external OSINT service).

This module handles Strixy-specific OSINT data retrieval and processing,
providing chat interface functionality for interacting with the Strixy
service for intelligence gathering operations.

Key features include:
- OSINT-focused AI chat interface with specialized investigation guidance
- OpenAI integration with custom system prompts for intelligence analysis
- Real-time conversational support for digital investigation methodologies
- Secure API key management and authentication handling
- Professional OSINT expertise covering SOCMINT, GEOINT, and cyber investigations
"""

from app.core.dependencies import get_current_user, get_db
from app.database import models
from app.schemas.strixy_schema import ChatRequest, ChatResponse
from app.services.strixy_service import StrixyService
from fastapi import APIRouter, Depends
from sqlmodel import Session

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat_with_strixy(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> ChatResponse:
    service = StrixyService(db)
    return await service.send_chat_message(request.messages)
