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
