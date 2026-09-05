"""Conservative recovery after proven cleanup or the enforced local stopping bound."""

import random
from datetime import UTC, timedelta

from sqlalchemy import or_
from sqlmodel import Session, col, select

from app.core.utils import get_utc_now
from app.database.connection import engine
from app.database.db_utils import transaction
from app.database.models import (
    ExecutionControl,
    ExecutionOutbox,
    HuntExecution,
    PluginExecution,
)
from app.executions.cancellation import TERMINAL, associated_execution, cancel_steps
from app.executions.limits import CLEANUP_SECONDS


def recover_stopped(db, control, execution, *, reason=None):
    """Caller holds the control lock and has established the cleanup bound."""
    now = get_utc_now()
    control.generation += 1
    control.owner = None
    control.revision += 1
    control.recovered_at = now
    if control.cancellation_requested_at:
        execution.status = "cancelled"
        execution.error = {
            "code": "cancelled",
            "message": "Execution cancelled; committed output retained",
            "partial": True,
        }
    elif reason == "execution_timeout" or (
        control.deadline_at and control.deadline_at.replace(tzinfo=UTC) <= now
    ):
        execution.status = "failed"
        execution.error = {
            "code": "execution_timeout",
            "message": "Execution deadline exceeded; committed output retained",
            "partial": True,
        }
    elif control.pending_status:
        execution.status = control.pending_status
    elif control.operation_id is not None:
        execution.status = "failed"
        execution.error = {
            "code": "interrupted_uncertain_outcome",
            "message": "Worker interrupted after operation start. External work may have occurred; review retained output before deliberately submitting a new run.",
            "operation_id": control.operation_id,
            "partial": True,
        }
    elif control.recovery_attempts >= 4:
        control.recovery_attempts += 1
        execution.status = "failed"
        execution.error = {
            "code": "recovery_exhausted",
            "message": "Worker recovery failed five times before operation start. Check worker configuration and background services, then deliberately submit a new run.",
            "attempts": control.recovery_attempts,
            "partial": True,
        }
    else:
        control.recovery_attempts += 1
        execution.status = (
            "pending" if isinstance(execution, HuntExecution) else "queued"
        )
        outbox = db.exec(
            select(ExecutionOutbox)
            .where(ExecutionOutbox.control_id == control.id)
            .with_for_update()
        ).one()
        outbox.published_at = None
        outbox.available_at = now + timedelta(
            seconds=min(60, 2 ** min(control.recovery_attempts, 6)) + random.random()
        )
        return
    execution.completed_at = now
    cancel_steps(db, execution)


BATCH_SIZE = 100


def reconcile(database_engine=engine) -> int:
    """Drain stale ownership promptly, committing between bounded batches."""
    total = 0
    while True:
        recovered = _reconcile_batch(database_engine)
        total += recovered
        if recovered < BATCH_SIZE:
            return total


def _reconcile_batch(database_engine) -> int:
    """Run independently of broker availability; serialize with all owner writes."""
    count = 0
    with Session(database_engine) as db, transaction(db):
        controls = db.exec(
            select(ExecutionControl)
            .where(
                or_(
                    col(ExecutionControl.plugin_execution_id).in_(
                        select(PluginExecution.id).where(
                            col(PluginExecution.status).in_(["running", "cancelling"])
                        )
                    ),
                    col(ExecutionControl.hunt_execution_id).in_(
                        select(HuntExecution.id).where(
                            col(HuntExecution.status).in_(["running", "cancelling"])
                        )
                    ),
                ),
                col(ExecutionControl.owner).is_not(None),
                col(ExecutionControl.lease_until)
                <= get_utc_now() - timedelta(seconds=CLEANUP_SECONDS),
            )
            .with_for_update(skip_locked=True)
            .limit(BATCH_SIZE)
        ).all()
        for control in controls:
            execution = associated_execution(db, control)
            if execution.status in TERMINAL:
                continue
            recover_stopped(db, control, execution)
            count += 1
    return count


if __name__ == "__main__":
    reconcile()
