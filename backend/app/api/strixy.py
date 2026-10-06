"""Strixy conversation, run, source and share routes."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlmodel import Session

from app.core.database_boundary import DatabaseRoute
from app.core.dependencies import get_current_user
from app.core.exceptions import ResourceNotFoundException
from app.database import models
from app.database.connection import get_db
from app.schemas.strixy_schema import (
    ChatRequest,
    ChatResponse,
    CreateShare,
    SubmitMessage,
)
from app.services.api_key_vault import ConfigurationApiKeyVault, Provider
from app.services.strixy_access import require_strixy_access
from app.services.strixy_conversations import StrixyConversations
from app.services.strixy_shares import StrixyShares
from app.services.strixy_sources import CaseSources, GroundedMaterial, SourceCatalog

router = APIRouter(route_class=DatabaseRoute)


async def get_conversations(
    case_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
) -> StrixyConversations:
    return StrixyConversations(db, current_user, case_id)


Conversations = Annotated[StrixyConversations, Depends(get_conversations)]


async def get_shares(conversations: Conversations) -> StrixyShares:
    return StrixyShares(conversations)


Shares = Annotated[StrixyShares, Depends(get_shares)]


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
async def create_conversation(conversations: Conversations):
    return conversations.create()


@router.get("/cases/{case_id}/conversations")
async def list_conversations(conversations: Conversations):
    return conversations.list()


@router.get("/cases/{case_id}/conversations/{conversation_id}")
async def read_conversation(conversation_id: str, conversations: Conversations):
    return conversations.read(conversation_id)


@router.delete("/cases/{case_id}/conversations/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: str, conversations: Conversations):
    conversations.delete(conversation_id)
    return Response(status_code=204)


@router.get("/cases/{case_id}/conversations/{conversation_id}/runs/{run_id}")
async def observe_run(conversation_id: str, run_id: str, conversations: Conversations):
    return conversations.observe(conversation_id, run_id)


@router.post(
    "/cases/{case_id}/conversations/{conversation_id}/messages", status_code=202
)
async def submit_message(
    case_id: int,
    conversation_id: str,
    request: SubmitMessage,
    response: Response,
    conversations: Conversations,
):
    run = conversations.submit(conversation_id, request.content, request.focus)
    response.headers["Location"] = (
        f"/api/strixy/cases/{case_id}/conversations/{conversation_id}/runs/{run['id']}"
    )
    return run


@router.get("/cases/{case_id}/sources")
async def list_sources(conversations: Conversations):
    from app.core.strixy_config import get_strixy_config

    catalog = CaseSources(
        conversations.db, conversations.human, conversations.case_id
    ).catalog(get_strixy_config())
    return {
        "sources": [source.catalog_entry() for source in catalog.sources],
        "enumeration_complete": catalog.complete,
    }


@router.get("/cases/{case_id}/sources/{source_id}")
async def read_source(
    source_id: str,
    conversations: Conversations,
    unit: Annotated[int | None, Query(ge=1, le=100000)] = None,
):
    from app.core.strixy_config import get_strixy_config

    config = get_strixy_config()
    reader = CaseSources(conversations.db, conversations.human, conversations.case_id)
    material = GroundedMaterial(
        SourceCatalog([reader.read(source_id)], True),
        config.model_copy(update={"visual_max_images": 1}),
        [],
        attachment_start=(unit or 1) - 1,
    )
    if not reader.validate_provenance(material.provenance(), current=True):
        raise ResourceNotFoundException("Source unavailable")
    return material.context() | {"images": [v.model_dump() for v in material.images]}


@router.post("/cases/{case_id}/conversations/{conversation_id}/runs/{run_id}/cancel")
async def cancel_run(conversation_id: str, run_id: str, conversations: Conversations):
    return conversations.cancel(conversation_id, run_id)


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
    conversations: Conversations,
):
    run = conversations.restart(conversation_id, run_id, action)
    response.headers["Location"] = (
        f"/api/strixy/cases/{case_id}/conversations/{conversation_id}/runs/{run['id']}"
    )
    return run


@router.post("/cases/{case_id}/conversations/{conversation_id}/shares", status_code=201)
async def create_share(conversation_id: str, request: CreateShare, shares: Shares):
    return shares.create(conversation_id, request.through_message_id)


@router.get("/cases/{case_id}/conversations/{conversation_id}/shares")
async def list_shares(conversation_id: str, shares: Shares):
    return shares.list(conversation_id)


@router.get("/cases/{case_id}/shares/{share_id}")
async def read_share(share_id: str, shares: Shares):
    return shares.read(share_id)


@router.delete("/cases/{case_id}/shares/{share_id}", status_code=204)
async def revoke_share(share_id: str, shares: Shares):
    shares.revoke(share_id)
    return Response(status_code=204)


@router.post("/cases/{case_id}/shares/{share_id}/copy", status_code=201)
async def copy_share(share_id: str, shares: Shares):
    return shares.copy(share_id)
