"""Supervised PostgreSQL outbox publisher, independent of API lifetimes."""

import random
import time
from datetime import timedelta
from pathlib import Path

from sqlmodel import Session, col, select

from app.core.utils import get_utc_now
from app.database.connection import engine
from app.database.db_utils import transaction
from app.database.models import ExecutionControl, ExecutionOutbox
from app.executions.celery_app import HUNT_QUEUE, QUEUE, app


def dispatch_once(database_engine=engine) -> bool:
    with Session(database_engine) as db, transaction(db):
        row = db.exec(
            select(ExecutionOutbox)
            .where(
                ExecutionOutbox.published_at == None,
                ExecutionOutbox.available_at <= get_utc_now(),
            )
            .order_by(col(ExecutionOutbox.id))
            .with_for_update(skip_locked=True)
            .limit(1)
        ).first()
        if row is None:
            return False
        control = db.get(ExecutionControl, row.control_id)
        assert control is not None
        kind = "hunt" if control.hunt_execution_id is not None else "plugin"
        execution_id = (
            control.hunt_execution_id if kind == "hunt" else control.plugin_execution_id
        )
        row.attempts += 1
        try:
            app.send_task(
                f"owlculus.execute_{kind}",
                args=[execution_id],
                task_id=f"{kind}-{execution_id}",
                queue=HUNT_QUEUE if kind == "hunt" else QUEUE,
                retry=False,
            )
        except Exception:  # noqa: BLE001 - isolate execution failures
            row.available_at = get_utc_now() + timedelta(
                seconds=min(60, 2 ** min(row.attempts, 6)) + random.random()
            )
        else:
            row.published_at = get_utc_now()
        return True


def main():
    while True:
        try:
            busy = dispatch_once()
            Path("/tmp/owlculus-dispatcher-heartbeat").touch()
        except Exception:  # noqa: BLE001 - isolate execution failures
            busy = False
        if not busy:
            time.sleep(1)


if __name__ == "__main__":
    main()
