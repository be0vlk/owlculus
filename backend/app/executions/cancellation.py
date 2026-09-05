"""Authoritative stop requests and post-cleanup terminal transitions."""

import logging
import os

from fastapi import HTTPException
from redis import Redis
from sqlmodel import Session, select

from app.core.exceptions import ResourceNotFoundException
from app.core.utils import get_utc_now
from app.database.db_utils import transaction
from app.database.models import (
    ExecutionControl,
    HuntExecution,
    HuntStep,
    PluginExecution,
)
from app.services.case_access import CaseAccess

TERMINAL = {"completed", "partial", "failed", "cancelled"}


def associated_execution(db, control):
    if control.hunt_execution_id is not None:
        return db.get(HuntExecution, control.hunt_execution_id)
    return db.get(PluginExecution, control.plugin_execution_id)


def cancel_steps(db, execution):
    if isinstance(execution, HuntExecution):
        for step in db.exec(
            select(HuntStep).where(HuntStep.execution_id == execution.id)
        ).all():
            if step.status in {"pending", "running"}:
                step.status = "cancelled"
                step.completed_at = get_utc_now()


def request_cancel(db, user, execution_id, *, kind="plugin"):
    model = HuntExecution if kind == "hunt" else PluginExecution
    association = (
        ExecutionControl.hunt_execution_id
        if kind == "hunt"
        else ExecutionControl.plugin_execution_id
    )
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
            raise HTTPException(403, "Inactive user")
        if execution.status in TERMINAL:
            return execution
        if control is None:
            raise HTTPException(
                409, "Legacy execution requires the background execution upgrade"
            )
        if control.cancellation_requested_at is None:
            control.cancellation_requested_at = get_utc_now()
            control.revision += 1
            execution.status = "cancelling" if control.owner else "cancelled"
            if control.owner is None:
                control.generation += 1
                execution.completed_at = get_utc_now()
                cancel_steps(db, execution)
    # The hint is expendable. The worker polls PostgreSQL independently.
    try:
        with Redis.from_url(
            os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
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
