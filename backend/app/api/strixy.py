"""
API endpoints for Strixy service integration (external OSINT service).

This module handles Strixy-specific OSINT data retrieval and processing,
providing chat interface functionality for interacting with the Strixy
service for intelligence gathering operations.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlmodel import Session

from app.core.database_boundary import DatabaseRoute
from app.core.dependencies import get_current_user
from app.database import models
from app.database.connection import get_db
from app.schemas.strixy_schema import ChatRequest, ChatResponse, SubmitMessage
from app.services.api_key_vault import ConfigurationApiKeyVault, Provider
from app.services.strixy_access import require_strixy_access
from app.services.strixy_conversations import StrixyConversations

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
    raise HTTPException(410, "Use private conversations to submit a new user message")


@router.post("/cases/{case_id}/conversations", status_code=201)
async def create_conversation(
    case_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    return StrixyConversations(db, current_user, case_id).create()


@router.get("/cases/{case_id}/conversations")
async def list_conversations(
    case_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    return StrixyConversations(db, current_user, case_id).list()


@router.get("/cases/{case_id}/conversations/{conversation_id}")
async def read_conversation(
    case_id: int,
    conversation_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    return StrixyConversations(db, current_user, case_id).read(conversation_id)


@router.delete("/cases/{case_id}/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    case_id: int,
    conversation_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    StrixyConversations(db, current_user, case_id).delete(conversation_id)
    return Response(status_code=204)


@router.get("/cases/{case_id}/conversations/{conversation_id}/runs/{run_id}")
async def observe_run(
    case_id: int,
    conversation_id: str,
    run_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    return StrixyConversations(db, current_user, case_id).observe(
        conversation_id, run_id
    )


@router.post(
    "/cases/{case_id}/conversations/{conversation_id}/messages", status_code=202
)
async def submit_message(
    case_id: int,
    conversation_id: str,
    request: SubmitMessage,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    run = StrixyConversations(db, current_user, case_id).submit(
        conversation_id, request.content, request.focus
    )
    response.headers["Location"] = (
        f"/api/strixy/cases/{case_id}/conversations/{conversation_id}/runs/{run['id']}"
    )
    return run


@router.get("/cases/{case_id}/sources")
async def list_sources(
    case_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    from app.core.strixy_config import get_strixy_config
    from app.services.strixy_sources import CaseSources

    catalog = CaseSources(db, current_user, case_id).catalog(get_strixy_config())
    return {
        "sources": [
            {"source_id": s.source_id, "kind": s.kind} for s in catalog.sources
        ],
        "enumeration_complete": catalog.complete,
    }


@router.get("/cases/{case_id}/sources/{source_id}")
async def read_source(
    case_id: int,
    source_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    from app.core.strixy_config import get_strixy_config
    from app.services.strixy_sources import CaseSources, GroundedMaterial

    config = get_strixy_config()
    source = CaseSources(db, current_user, case_id).read(source_id)
    material = GroundedMaterial([source], True, config, [])
    if not CaseSources(db, current_user, case_id).validate_provenance(
        material.provenance(), current=True
    ):
        from app.core.exceptions import ResourceNotFoundException

        raise ResourceNotFoundException("Source unavailable")
    return material.context()


@router.post("/cases/{case_id}/conversations/{conversation_id}/runs/{run_id}/cancel")
async def cancel_run(
    case_id: int,
    conversation_id: str,
    run_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    return StrixyConversations(db, current_user, case_id).cancel(
        conversation_id, run_id
    )


@router.post(
    "/cases/{case_id}/conversations/{conversation_id}/runs/{run_id}/{action}",
    status_code=202,
)
async def restart_run(
    case_id: int,
    conversation_id: str,
    run_id: str,
    action: Literal["continue", "retry", "reanalyze"],
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    run = StrixyConversations(db, current_user, case_id).restart(
        conversation_id, run_id, action
    )
    response.headers["Location"] = (
        f"/api/strixy/cases/{case_id}/conversations/{conversation_id}/runs/{run['id']}"
    )
    return run
