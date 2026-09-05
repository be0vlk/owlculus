"""Supervised PostgreSQL outbox publisher, independent of API lifetimes."""

import logging
import os
import random
import time
from datetime import timedelta
from pathlib import Path

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
from app.executions.celery_app import HUNT_QUEUE, QUEUE, app
from app.executions.events import record_event


def dispatch_once(database_engine=engine) -> bool:
    now = get_utc_now()
    redispatch_seconds = max(
        1, float(os.environ.get("EXECUTION_REDISPATCH_SECONDS", "30"))
    )
    with Session(database_engine) as db, transaction(db):
        selected = db.exec(
            select(ExecutionOutbox, ExecutionControl)
            .join(
                ExecutionControl, col(ExecutionControl.id) == ExecutionOutbox.control_id
            )
            .outerjoin(
                PluginExecution,
                col(PluginExecution.id) == ExecutionControl.plugin_execution_id,
            )
            .outerjoin(
                HuntExecution,
                col(HuntExecution.id) == ExecutionControl.hunt_execution_id,
            )
            .where(
                ExecutionOutbox.available_at <= now,
                ExecutionControl.owner == None,
                or_(
                    col(PluginExecution.status) == "queued",
                    col(HuntExecution.status) == "pending",
                ),
                or_(
                    col(ExecutionOutbox.published_at).is_(None),
                    col(ExecutionOutbox.published_at)
                    <= now - timedelta(seconds=redispatch_seconds),
                ),
            )
            .order_by(col(ExecutionOutbox.available_at), col(ExecutionOutbox.id))
            # PostgreSQL owns the claim until publication and acknowledgment commit.
            # Worker claims take the same control lock. A crashed connection releases
            # both locks and rolls back the acknowledgment, enabling safe redelivery.
            .with_for_update(of=(ExecutionControl, ExecutionOutbox), skip_locked=True)
            .limit(1)
        ).first()
        if selected is None:
            return False
        row, control = selected
        kind = "hunt" if control.hunt_execution_id is not None else "plugin"
        execution_id = (
            control.hunt_execution_id if kind == "hunt" else control.plugin_execution_id
        )
        row.last_attempt_at = now
        try:
            app.send_task(
                f"owlculus.execute_{kind}",
                args=[execution_id],
                task_id=f"{kind}-{execution_id}",
                queue=HUNT_QUEUE if kind == "hunt" else QUEUE,
                retry=False,
            )
        except Exception:  # noqa: BLE001 - broker errors must never expose credentials
            row.attempts += 1
            row.last_error = "Background broker unavailable; dispatch will retry"
            row.available_at = get_utc_now() + timedelta(
                seconds=min(60, 2 ** min(row.attempts, 6)) + random.random()
            )
            if row.attempts >= 5:
                execution = db.get(
                    HuntExecution if kind == "hunt" else PluginExecution, execution_id
                )
                assert execution is not None
                execution.status = "failed"
                execution.completed_at = get_utc_now()
                execution.error = {
                    "code": "dispatch_failed",
                    "message": "Background dispatch failed after five consecutive attempts before worker claim. Check background services and deliberately submit a new run.",
                    "attempts": row.attempts,
                }
                record_event(db, control)
        else:
            row.published_at = get_utc_now()
            row.attempts = 0
            row.last_error = None
        return True


def main():
    from app.executions.events import publish_once, refresh_active_streams
    from app.executions.recovery import reconcile

    next_reconcile = 0.0
    while True:
        try:
            if time.monotonic() >= next_reconcile:
                reconcile()
                next_reconcile = time.monotonic() + 10
            busy = dispatch_once()
            # Event publication has its own failure boundary: completed work stays
            # completed, and dispatch/recovery proceed during event outages.
            try:
                for _ in range(200):
                    if not publish_once():
                        break
                    busy = True
                refresh_active_streams()
            except Exception:  # noqa: BLE001 - durable intent remains for retry
                logging.getLogger(__name__).info(
                    "Live publication deferred; durable results and retry intent retained"
                )
            Path("/tmp/owlculus-dispatcher-heartbeat").touch()
        except Exception:  # noqa: BLE001 - isolate infrastructure failures
            busy = False
        if not busy:
            time.sleep(1)


if __name__ == "__main__":
    main()
