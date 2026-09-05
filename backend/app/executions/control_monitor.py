"""Disposable control I/O process; provider supervision never waits on the database."""

import json
import logging
import sys
import time
from datetime import UTC, timedelta

from sqlmodel import Session, create_engine, select

from app.core.config import settings
from app.core.utils import get_utc_now
from app.database.models import HuntStep
from app.executions.limits import STEP_SECONDS
from app.executions.ownership import (
    HEARTBEAT_SECONDS,
    LEASE_SECONDS,
    Ownership,
    OwnershipLost,
    heartbeat,
)


def main():
    kind, execution_id, control_id, generation, owner = sys.argv[1:]
    ownership = Ownership(int(control_id), int(generation), owner)
    engine = create_engine(
        settings.get_database_url(), pool_pre_ping=True, hide_parameters=True
    )
    next_heartbeat = 0.0
    try:
        while True:
            checked = time.monotonic()
            try:
                with Session(engine) as db:
                    control, _ = ownership.lock(db)
                    assert control.deadline_at is not None
                    deadline = control.deadline_at.replace(tzinfo=UTC)
                    if kind == "hunt":
                        step = db.exec(
                            select(HuntStep).where(
                                HuntStep.execution_id == int(execution_id),
                                HuntStep.status == "running",
                            )
                        ).first()
                        if step and step.started_at:
                            deadline = min(
                                deadline,
                                step.started_at.replace(tzinfo=UTC)
                                + timedelta(seconds=STEP_SECONDS),
                            )
                    remaining = (deadline - get_utc_now()).total_seconds()
                    db.rollback()
                    renewed = checked >= next_heartbeat
                    if renewed:
                        heartbeat(db, ownership)
                        next_heartbeat = checked + HEARTBEAT_SECONDS
                    print(
                        json.dumps(
                            {
                                "lease_end": (
                                    checked + LEASE_SECONDS if renewed else None
                                ),
                                "deadline_end": checked + remaining,
                            }
                        ),
                        flush=True,
                    )
            except OwnershipLost:
                print(json.dumps({"reason": "control_lost"}), flush=True)
                return
            except Exception:  # noqa: BLE001 - supervisor enforces its clock
                logging.getLogger(__name__).warning(
                    "Execution control unavailable; stopping by lease expiry"
                )
            time.sleep(0.5)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
