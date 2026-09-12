"""Single-claim Strixy work with fresh authorization and fenced publication."""

from datetime import timedelta

from openai import APIConnectionError
from sqlalchemy.engine import Engine
from sqlmodel import Session, col, select

from app.core.exceptions import BaseException as DomainException
from app.core.exceptions import ValidationException
from app.core.strixy_config import StrixyConfig
from app.core.utils import get_utc_now
from app.database.connection import engine
from app.database.db_utils import transaction
from app.database.models import (
    StrixyConversation,
    StrixyGrounding,
    StrixyMessage,
    StrixyProgress,
    StrixyRun,
    User,
)
from app.schemas.strixy_schema import ChatMessage
from app.services.strixy_access import require_strixy_access
from app.services.strixy_analysis import GroundingError, analyze
from app.services.strixy_sources import CaseSources


def lock_run(db: Session, run_id: str):
    """Every lifecycle mutation locks conversation before run, including deletion."""
    run = db.get(StrixyRun, run_id)
    if run is None:
        return None
    conversation = db.exec(
        select(StrixyConversation)
        .where(StrixyConversation.id == run.conversation_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    run = db.exec(
        select(StrixyRun)
        .where(StrixyRun.id == run_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if run is None or conversation is None or conversation.deleted_at is not None:
        return None
    return conversation, run


def authorize(db: Session, conversation: StrixyConversation, run: StrixyRun):
    human = db.get(User, conversation.owner_id)
    if human is None:
        raise ValidationException("Owner unavailable")
    strixy = require_strixy_access(db, human, conversation.case_id)
    if strixy.id != run.strixy_id:
        raise ValidationException("Analyst unavailable")


def finish(run: StrixyRun, status: str, error: str | None = None):
    run.status, run.error_code, run.finished_at = status, error, get_utc_now()


def execute(run_id: str, database_engine: Engine = engine):
    with Session(database_engine) as db, transaction(db):
        selected = lock_run(db, run_id)
        if selected is None:
            return
        conversation, run = selected
        if run.status != "pending":
            return
        try:
            authorize(db, conversation, run)
        except DomainException:
            finish(run, "cancelled", "access_revoked")
            db.add(run)
            return
        config = StrixyConfig.model_validate(run.configuration)
        run.status, run.started_at = "running", get_utc_now()
        run.deadline = run.started_at + timedelta(seconds=config.runtime_seconds)
        run.dispatch_at = run.deadline + timedelta(seconds=10)
        db.add(run)
        messages = [
            ChatMessage(role=m.role, content=m.content)
            for m in db.exec(
                select(StrixyMessage)
                .where(StrixyMessage.conversation_id == conversation.id)
                .order_by(col(StrixyMessage.position))
            ).all()
        ]
        deadline = run.deadline
    reply = None
    error = None
    try:
        reply = analyze(run_id, database_engine, config, deadline)
    except GroundingError as failure:
        error = failure.code
    except ValidationException:
        error = "provider_not_configured"
    except DomainException:
        error = "access_revoked"
    except APIConnectionError:
        error = "completion_uncertain"
    except Exception:  # noqa: BLE001 - sanitized external failures
        error = "provider_failed"
    with Session(database_engine) as db, transaction(db):
        selected = lock_run(db, run_id)
        if selected is None or selected[1].status != "running":
            return
        conversation, run = selected
        try:
            authorize(db, conversation, run)
        except DomainException:
            finish(run, "cancelled", "access_revoked")
            db.add(run)
            return
        ledger = db.get(StrixyGrounding, run_id)
        human = db.get(User, conversation.owner_id)
        assert human is not None
        if ledger and not CaseSources(
            db, human, conversation.case_id
        ).validate_provenance(ledger.provenance, current=True):
            error = "sources_changed"
        if get_utc_now() >= deadline or error == "runtime_limit":
            run.limit_code = "runtime_limit"
            finish(run, "completed")
        elif error:
            finish(run, "failed", error)
        elif reply is not None:
            run.input_tokens, run.output_tokens = (
                reply.input_tokens,
                reply.output_tokens,
            )
            run.limit_code = reply.limit_code
            run.coverage = "case_records"
            if reply.content:
                db.add(
                    StrixyMessage(
                        conversation_id=conversation.id,
                        position=len(messages),
                        role="assistant",
                        content=reply.content,
                    )
                )
                progress = db.get(StrixyProgress, run_id)
                if progress:
                    progress.content = ""
                    db.add(progress)
            finish(run, "completed")
        if error in {"sources_changed", "invalid_citation", "access_revoked"}:
            progress = db.get(StrixyProgress, run_id)
            if progress:
                progress.content = ""
                db.add(progress)
        db.add(run)
