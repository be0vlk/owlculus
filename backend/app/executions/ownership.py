"""Generation-fenced execution writes; transactions never span provider calls."""

from dataclasses import dataclass
from datetime import UTC, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlmodel import Session, select

from app.core.enums import ExecutionStatus
from app.core.exceptions import AuthorizationException, ResourceNotFoundException
from app.core.utils import get_utc_now
from app.database.db_utils import transaction
from app.database.models import ExecutionControl, PluginExecution, PluginExecutionResult
from app.executions.service import authorize_execution

LEASE_SECONDS = 60
HEARTBEAT_SECONDS = 10


class OwnershipLost(Exception):
    """The caller no longer has permission to mutate the execution."""


@dataclass(frozen=True)
class Ownership:
    control_id: int
    generation: int
    owner: str

    def lock(self, db: Session) -> tuple[ExecutionControl, PluginExecution]:
        control = db.exec(
            select(ExecutionControl)
            .where(ExecutionControl.id == self.control_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).one()
        execution = db.get(
            PluginExecution, control.plugin_execution_id, populate_existing=True
        )
        if (
            execution is None
            or execution.status != ExecutionStatus.RUNNING.value
            or control.owner != self.owner
            or control.generation != self.generation
            or control.lease_until is None
            or control.lease_until.replace(tzinfo=UTC) <= get_utc_now()
        ):
            raise OwnershipLost()
        return control, execution


def claim(db: Session, execution_id: int) -> Ownership | None:
    with transaction(db):
        control = db.exec(
            select(ExecutionControl)
            .where(ExecutionControl.plugin_execution_id == execution_id)
            .with_for_update()
        ).first()
        if control is None:
            return None
        execution = db.get(PluginExecution, execution_id)
        if (
            execution is None
            or execution.status != ExecutionStatus.QUEUED.value
            or control.owner is not None
        ):
            return None
        try:
            authorize_execution(db, execution)
        except (HTTPException, AuthorizationException, ResourceNotFoundException):
            execution.status = ExecutionStatus.FAILED.value
            execution.error = {
                "code": "access_revoked",
                "message": "Initiating user no longer has execution access",
            }
            execution.completed_at = get_utc_now()
            control.revision += 1
            return None
        control.generation += 1
        control.owner = str(uuid4())
        control.heartbeat_at = get_utc_now()
        control.lease_until = get_utc_now() + timedelta(seconds=LEASE_SECONDS)
        control.revision += 1
        execution.status = ExecutionStatus.RUNNING.value
        execution.started_at = get_utc_now()
        assert control.id is not None
        return Ownership(control.id, control.generation, control.owner)


def heartbeat(db: Session, ownership: Ownership) -> None:
    with transaction(db):
        control, _ = ownership.lock(db)
        control.heartbeat_at = get_utc_now()
        control.lease_until = get_utc_now() + timedelta(seconds=LEASE_SECONDS)


def append_result(db: Session, ownership: Ownership, payload: dict) -> None:
    with transaction(db):
        control, execution = ownership.lock(db)
        control.revision += 1
        db.add(
            PluginExecutionResult(
                execution_id=execution.id, sequence=control.revision, payload=payload
            )
        )
        if payload["type"] == "error":
            execution.error = {
                "code": "plugin_error",
                "message": payload["data"].get("message", "Plugin failed"),
            }
        if payload["type"] == "complete":
            execution.status = (
                ExecutionStatus.FAILED.value
                if execution.error
                else ExecutionStatus.COMPLETED.value
            )
            execution.completed_at = get_utc_now()
