"""Keep control I/O outside provider processes so blocked adapters remain stoppable."""

import ctypes
import json
import os
import select
import signal
import subprocess
import sys
import time

from sqlmodel import Session, create_engine

from app.core.config import settings
from app.executions.cancellation import finish_stopped
from app.executions.limits import (
    CLEANUP_SECONDS,
    HUNT_SECONDS,
    PLUGIN_SECONDS,
)
from app.executions.ownership import (
    LEASE_SECONDS,
    claim,
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
    try:
        with Session(engine) as db:
            ownership = claim(db, execution_id, kind=kind)
    finally:
        engine.dispose()
    if ownership is None:
        return
    process = None
    reason = None
    lease_end = started + LEASE_SECONDS
    deadline_end = started + (HUNT_SECONDS if kind == "hunt" else PLUGIN_SECONDS)
    monitor = None
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
        monitor = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "app.executions.control_monitor",
                kind,
                str(execution_id),
                str(ownership.control_id),
                str(ownership.generation),
                ownership.owner,
            ],
            stdout=subprocess.PIPE,
            start_new_session=True,
        )
        assert monitor.stdout is not None
        pending = b""
        while process.poll() is None:
            readable, _, _ = select.select([monitor.stdout], [], [], 0.1)
            if readable:
                chunk = os.read(monitor.stdout.fileno(), 4096)
                if not chunk:
                    reason = "control_lost"
                    break
                pending += chunk
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    update = json.loads(line)
                    lease_end = update.get("lease_end") or lease_end
                    deadline_end = update.get("deadline_end") or deadline_end
                    if update.get("reason"):
                        reason = update["reason"]
                if reason:
                    break
            now = time.monotonic()
            if now >= min(lease_end, deadline_end) - CLEANUP_SECONDS:
                reason = (
                    "execution_timeout"
                    if deadline_end <= lease_end
                    else "lease_expired"
                )
                break
    finally:
        if process is not None:
            stop_process(process)
        if monitor is not None:
            stop_process(monitor)
            if monitor.stdout is not None:
                monitor.stdout.close()
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
