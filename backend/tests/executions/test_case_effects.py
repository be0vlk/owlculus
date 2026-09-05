"""Case-visible receipts, concurrency and actual process interruption windows."""

import os
import signal

from tests.executions.conftest import eventually
from tests.executions.test_execution_system import submit


def contents(client, system):
    return client.get(f"/api/evidence/case/{system.case_id}").json()


def replay(system, accepted, window="success"):
    marker = system.root / f"effect-{window}"
    marker.unlink(missing_ok=True)
    process = system.start(
        "-m", "tests.executions.runtime", "replay-effects", str(accepted["id"]), window
    )
    eventually(lambda: marker.exists() or process.poll() is not None)
    assert process.poll() in (None, 0), list(system.root.glob("*.log"))
    return process


def test_effect_retries_races_and_independent_runs(execution_system):
    system = execution_system
    _, client = system.api()
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    try:
        accepted = submit(client, system, barrier="hold", save_to_case=True)
        eventually(lambda: client.get(accepted["links"]["results"]).json()["items"])
        replay(system, accepted, "results")
        replay(system, accepted, "results")
        events = client.get(accepted["links"]["results"]).json()["items"]
        assert [e for e in events if e["data"].get("replayed")] == [
            {"type": "data", "data": {"replayed": True}}
        ]
        first = system.start(
            "-m",
            "tests.executions.runtime",
            "replay-effects",
            str(accepted["id"]),
            "success",
        )
        second = system.start(
            "-m",
            "tests.executions.runtime",
            "replay-effects",
            str(accepted["id"]),
            "success",
        )
        eventually(lambda: first.poll() is not None and second.poll() is not None)
        assert first.returncode == second.returncode == 0
        assert len(contents(client, system)) == 2
        replay(system, accepted)
        assert len(contents(client, system)) == 2
        entities = client.get(f"/api/cases/{system.case_id}/entities").json()
        assert len(entities) == 1
        assert entities[0]["data"]["description"] == "Exactly one enrichment"
        independent = submit(client, system, barrier="hold-second", save_to_case=True)
        eventually(lambda: client.get(independent["links"]["results"]).json()["items"])
        replay(system, independent)
        assert len(contents(client, system)) == 3
        assert sum(item["is_folder"] for item in contents(client, system)) == 1
        entities = client.get(f"/api/cases/{system.case_id}/entities").json()
        assert entities[0]["data"]["description"].count("Exactly one enrichment") == 2
    finally:
        client.close()


def test_file_interruption_and_lost_commit_acknowledgment(execution_system):
    system = execution_system
    _, client = system.api()
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    try:
        accepted = submit(client, system, barrier="hold", save_to_case=True)
        eventually(lambda: client.get(accepted["links"]["results"]).json()["items"])
        interrupted = replay(system, accepted, "after-file")
        assert contents(client, system) == []
        artifacts = list((system.root / "uploads").rglob("*.txt"))
        assert len(artifacts) == 1
        os.killpg(interrupted.pid, signal.SIGKILL)
        interrupted.wait(timeout=5)
        interrupted = replay(system, accepted, "after-commit")
        assert len(contents(client, system)) == 2
        os.killpg(interrupted.pid, signal.SIGKILL)
        interrupted.wait(timeout=5)
        interrupted = replay(system, accepted, "after-entity-commit")
        os.killpg(interrupted.pid, signal.SIGKILL)
        interrupted.wait(timeout=5)
        replay(system, accepted)
        entities = client.get(f"/api/cases/{system.case_id}/entities").json()
        assert entities[0]["data"]["description"] == "Exactly one enrichment"
        assert len(contents(client, system)) == 2
        assert list((system.root / "uploads").rglob("*.txt")) == artifacts
        assert artifacts[0].read_text() == "Stable retained evidence"
        assert all(
            item["created_by_id"] == system.user_id for item in contents(client, system)
        )
    finally:
        client.close()


def test_unsaved_effects_and_stale_or_cancelled_owners_cannot_write(execution_system):
    from sqlmodel import Session, select

    from app.core.utils import get_utc_now
    from app.database.models import ExecutionControl

    system = execution_system
    _, client = system.api()
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    try:
        unsaved = submit(client, system, barrier="hold", save_to_case=False)
        eventually(lambda: client.get(unsaved["links"]["results"]).json()["items"])
        replay(system, unsaved)
        assert contents(client, system) == []
        assert client.get(f"/api/cases/{system.case_id}/entities").json() == []
        saved = submit(client, system, barrier="hold-two", save_to_case=True)
        eventually(lambda: client.get(saved["links"]["results"]).json()["items"])
        with Session(system.engine) as db:
            control = db.exec(
                select(ExecutionControl).where(
                    ExecutionControl.plugin_execution_id == saved["id"]
                )
            ).one()
            control.cancellation_requested_at = get_utc_now()
            db.commit()
        process = system.start(
            "-m",
            "tests.executions.runtime",
            "replay-effects",
            str(saved["id"]),
            "cancelled",
        )
        eventually(lambda: process.poll() is not None)
        assert process.returncode != 0
        assert contents(client, system) == []
    finally:
        client.close()


def test_reconciliation_removes_only_uncommitted_owned_files(execution_system):
    from datetime import timedelta

    from sqlmodel import Session, select

    from app.core.utils import get_utc_now
    from app.database.models import ExecutionControl

    system = execution_system
    _, client = system.api()
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    try:
        accepted = submit(client, system, barrier="hold", save_to_case=True)
        eventually(lambda: client.get(accepted["links"]["results"]).json()["items"])
        replay(system, accepted)
        committed_files = list((system.root / "uploads").rglob("*.txt"))
        unrelated = system.root / "uploads" / "unrelated.txt"
        unrelated.write_text("Keep this")
        second = submit(client, system, barrier="hold-two", save_to_case=True)
        eventually(lambda: client.get(second["links"]["results"]).json()["items"])
        interrupted = replay(system, second, "after-file")
        os.killpg(interrupted.pid, signal.SIGKILL)
        interrupted.wait(timeout=5)
        with Session(system.engine) as db:
            control = db.exec(
                select(ExecutionControl).where(
                    ExecutionControl.plugin_execution_id == second["id"]
                )
            ).one()
            control.lease_until = get_utc_now() - timedelta(seconds=1)
            db.commit()
        reconcile = system.start("-m", "app.executions.reconcile_artifacts")
        eventually(lambda: reconcile.poll() is not None)
        assert reconcile.returncode == 0
        assert sorted((system.root / "uploads").rglob("*.txt")) == sorted(
            [unrelated, *committed_files]
        )
        assert len(contents(client, system)) == 2
    finally:
        client.close()
