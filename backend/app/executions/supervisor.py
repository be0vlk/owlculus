"""Keep control I/O outside provider processes so blocked adapters remain stoppable."""

import ctypes
import logging
import os
import queue
import signal
import subprocess
import sys
import threading
import time
from datetime import UTC, timedelta

from sqlmodel import Session, create_engine, select

from app.core.config import settings
from app.core.utils import get_utc_now
from app.database.models import HuntStep
from app.executions.cancellation import finish_stopped
from app.executions.limits import (
    CLEANUP_SECONDS,
    HUNT_SECONDS,
    PLUGIN_SECONDS,
    STEP_SECONDS,
)
from app.executions.ownership import (
    HEARTBEAT_SECONDS,
    LEASE_SECONDS,
    OwnershipLost,
    claim,
    heartbeat,
)

CHILD_COMMAND = [sys.executable, "-m", "app.executions.child"]


def stop_process(process):
    # Each execution starts a new session. Its adapters inherit only this group.
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=CLEANUP_SECONDS - 1)
    except subprocess.TimeoutExpired:
        pass
    except ProcessLookupError:
        pass
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        # Linux subreaping lets us wait for descendants, including provider-created
        # subprocesses, before advertising a terminal execution state.
        while True:
            try:
                os.waitpid(-process.pid, 0)
            except ChildProcessError:
                break


def run(execution_id: int, kind: str):
    engine = create_engine(
        settings.get_database_url(), pool_pre_ping=True, hide_parameters=True
    )
    # PR_SET_CHILD_SUBREAPER: adopted descendants stay attributable by process group.
    if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "Could not enable execution process cleanup")
    started = time.monotonic()
    with Session(engine) as db:
        ownership = claim(db, execution_id, kind=kind)
    if ownership is None:
        engine.dispose()
        return
    updates: queue.Queue = queue.Queue()
    stopped = threading.Event()

    def monitor():
        next_heartbeat = 0.0
        while not stopped.is_set():
            checked = time.monotonic()
            try:
                with Session(engine) as db:
                    control, _ = ownership.lock(db)
                    assert control.deadline_at is not None
                    deadline = control.deadline_at.replace(tzinfo=UTC)
                    if kind == "hunt":
                        step = db.exec(
                            select(HuntStep).where(
                                HuntStep.execution_id == execution_id,
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
                    updates.put(
                        (
                            checked + LEASE_SECONDS if renewed else None,
                            checked + remaining,
                            None,
                        )
                    )
            except OwnershipLost:
                updates.put((None, None, "control_lost"))
                return
            except Exception:  # noqa: BLE001 - local clock enforces the last lease
                logging.getLogger(__name__).warning(
                    "Execution control unavailable; stopping by lease expiry"
                )
            stopped.wait(0.5)

    process = None
    reason = None
    lease_end = started + LEASE_SECONDS
    deadline_end = started + (HUNT_SECONDS if kind == "hunt" else PLUGIN_SECONDS)
    monitor_thread = threading.Thread(target=monitor, daemon=True)
    previous = signal.getsignal(signal.SIGTERM)

    def shutting_down(signum, frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, shutting_down)
    try:
        process = subprocess.Popen(
            [
                *CHILD_COMMAND,
                kind,
                str(execution_id),
                str(ownership.control_id),
                str(ownership.generation),
                ownership.owner,
            ],
            start_new_session=True,
        )
        monitor_thread.start()
        while process.poll() is None:
            try:
                lease, deadline, stop_reason = updates.get(timeout=0.1)
                if lease:
                    lease_end = lease
                if deadline:
                    deadline_end = deadline
                if stop_reason:
                    reason = stop_reason
                    break
            except queue.Empty:
                pass
            now = time.monotonic()
            if now >= min(lease_end, deadline_end) - CLEANUP_SECONDS:
                reason = (
                    "execution_timeout"
                    if deadline_end <= lease_end
                    else "lease_expired"
                )
                break
    finally:
        stopped.set()
        if process is not None:
            stop_process(process)
        # Finish only once cleanup is proven. A partition keeps the durable view
        # nonterminal until this transaction can be committed.
        while True:
            try:
                with Session(engine) as db:
                    finish_stopped(db, ownership, reason=reason)
                break
            except Exception:  # noqa: BLE001 - restore the durable cleanup report
                time.sleep(1)
        signal.signal(signal.SIGTERM, previous)
        engine.dispose()
