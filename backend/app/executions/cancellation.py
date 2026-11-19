"""Authoritative stop requests and post-cleanup terminal transitions."""

import logging

from redis import Redis
from sqlmodel import Session, select

from app.core.exceptions import (
    AuthorizationException,
    RelatedResourceException,
    ResourceNotFoundException,
)
from app.core.utils import get_utc_now
from app.database.db_utils import transaction
from app.database.models import (
    TERMINAL,
    ExecutionControl,
    HuntExecution,
    HuntStep,
    associated_execution,
    execution_kind,
)
from app.executions.events import event_redis_url, record_event
from app.services.case_access import CaseAccess


def cancel_steps(db, execution):
    if isinstance(execution, HuntExecution):
        for step in db.exec(
            select(HuntStep).where(HuntStep.execution_id == execution.id)
        ).all():
            if step.status in {"pending", "running"}:
                step.status = "cancelled"
                step.completed_at = get_utc_now()


def request_cancel(db, user, execution_id, *, kind="plugin"):
    model, association = execution_kind(kind)
    with transaction(db):
        control = db.exec(
            select(ExecutionControl)
            .where(association == execution_id)
            .with_for_update()
        ).first()
        execution = db.get(model, execution_id)
        if execution is None:
            raise ResourceNotFoundException(
                "Hunt execution not found" if kind == "hunt" else "Execution not found"
            )
        access = CaseAccess(db)
        access.require_non_analyst(user)
        access.writable(user, execution.case_id)
        if not user.is_active:
            raise AuthorizationException("Inactive user")
        if execution.status in TERMINAL:
            return execution
        if control is None:
            raise RelatedResourceException(
                "Legacy execution requires the background execution upgrade"
            )
        if control.cancellation_requested_at is None:
            control.cancellation_requested_at = get_utc_now()
            record_event(db, control)
            execution.status = "cancelling" if control.owner else "cancelled"
            if control.owner is None:
                control.generation += 1
                execution.completed_at = get_utc_now()
                cancel_steps(db, execution)
    # The hint is expendable. The worker polls PostgreSQL independently.
    try:
        with Redis.from_url(
            event_redis_url(),
            socket_connect_timeout=0.2,
            socket_timeout=0.2,
        ) as redis:
            redis.publish(f"owlculus:execution:cancel:{control.id}", "cancel")
    except Exception:  # noqa: BLE001 - durable cancellation already committed
        logging.getLogger(__name__).info(
            "Cancellation hint unavailable; durable polling remains active"
        )
    return execution


def finish_stopped(db: Session, ownership, *, reason=None):
    """Called only after the owned process group has been stopped and reaped."""
    with transaction(db):
        control = db.exec(
            select(ExecutionControl)
            .where(ExecutionControl.id == ownership.control_id)
            .with_for_update()
        ).one()
        execution = associated_execution(db, control)
        if (
            control.owner != ownership.owner
            or control.generation != ownership.generation
            or execution.status in TERMINAL
        ):
            return
        from app.executions.recovery import recover_stopped

        recover_stopped(db, control, execution, reason=reason)
