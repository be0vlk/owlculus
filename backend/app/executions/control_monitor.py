"""Disposable control I/O process; provider supervision never waits on the database."""

import json
import logging
import os
import sys
import time
from datetime import UTC, timedelta

from redis import Redis
from redis.exceptions import RedisError
from sqlmodel import Session, select

from app.core.utils import get_utc_now
from app.database.connection import create_execution_engine
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
    kind, execution_id, control_id, generation, owner, supervisor_pid = sys.argv[1:]
    ownership = Ownership(int(control_id), int(generation), owner)
    engine = create_execution_engine()
    next_heartbeat = 0.0
    redis = Redis.from_url(
        os.environ.get("EXECUTION_EVENT_REDIS_URL")
        or os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        socket_connect_timeout=0.2,
        socket_timeout=0.6,
    )
    hints = redis.pubsub(ignore_subscribe_messages=True)
    hints_available = True
    try:
        hints.subscribe(f"owlculus:execution:cancel:{control_id}")
    except RedisError:
        hints_available = False
    try:
        while os.getppid() == int(supervisor_pid):
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
                    if os.getppid() != int(supervisor_pid):
                        return
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
            if hints_available:
                try:
                    hints.get_message(timeout=0.5)
                except RedisError:
                    hints_available = False
            else:
                time.sleep(0.5)
    finally:
        hints.close()
        redis.close()
        engine.dispose()


if __name__ == "__main__":
    main()
