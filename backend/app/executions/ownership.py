"""Generation-fenced execution writes; transactions never span provider calls."""

from dataclasses import dataclass
from datetime import UTC, timedelta
from typing import cast
from uuid import uuid4

from fastapi import HTTPException
from sqlmodel import Session, select

from app.core.enums import ExecutionStatus
from app.core.exceptions import AuthorizationException, ResourceNotFoundException
from app.core.utils import get_utc_now
from app.database.db_utils import transaction
from app.database.models import (
    ExecutionControl,
    HuntExecution,
    PluginExecution,
    PluginExecutionResult,
)
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

    def lock(
        self, db: Session
    ) -> tuple[ExecutionControl, PluginExecution | HuntExecution]:
        # Read persisted state without flushing or overwriting pending domain writes.
        with db.no_autoflush:
            control = db.exec(
                select(ExecutionControl)
                .where(ExecutionControl.id == self.control_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ).one()
            model = (
                HuntExecution
                if control.hunt_execution_id is not None
                else PluginExecution
            )
            execution_id = (
                control.hunt_execution_id
                if model is HuntExecution
                else control.plugin_execution_id
            )
            status = db.exec(
                select(model.status).where(model.id == execution_id)
            ).one_or_none()
            if (
                status != ExecutionStatus.RUNNING.value
                or control.owner != self.owner
                or control.generation != self.generation
                or control.lease_until is None
                or control.lease_until.replace(tzinfo=UTC) <= get_utc_now()
            ):
                raise OwnershipLost()
            execution = cast(
                HuntExecution | PluginExecution | None, db.get(model, execution_id)
            )
            assert execution is not None
            return control, execution


def claim(db: Session, execution_id: int, *, kind: str = "plugin") -> Ownership | None:
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
        if control is None:
            return None
        execution = cast(
            HuntExecution | PluginExecution | None, db.get(model, execution_id)
        )
        if (
            execution is None
            or execution.status
            != ("pending" if kind == "hunt" else ExecutionStatus.QUEUED.value)
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
        if isinstance(execution, HuntExecution):
            from app.executions.build import implementation_build

            if execution.implementation_build != implementation_build():
                execution.status = "failed"
                execution.error = {
                    "code": "incompatible_build",
                    "message": "Hunt requires its accepted implementation build; deploy matching API and workers and submit a new run",
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
        assert isinstance(execution, PluginExecution)
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
