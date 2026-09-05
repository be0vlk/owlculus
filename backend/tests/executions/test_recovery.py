"""Worker loss and safe recovery through durable APIs and visible case records."""

import os
import signal
from contextlib import closing
from datetime import timedelta

import pytest
from sqlmodel import Session, select

from app.core.utils import get_utc_now
from app.database.models import ExecutionControl
from tests.executions.conftest import eventually
from tests.executions.test_execution_system import finished, submit


def expire_owner(system, accepted, *, kind="plugin"):
    with Session(system.engine) as db:
        association = (
            ExecutionControl.hunt_execution_id
            if kind == "hunt"
            else ExecutionControl.plugin_execution_id
        )
        control = db.exec(
            select(ExecutionControl).where(association == accepted["id"])
        ).one()
        control.lease_until = get_utc_now() - timedelta(seconds=6)
        db.commit()


def test_worker_loss_before_provider_start_redispatches_same_execution(
    execution_system,
):
    system = execution_system
    system.env["EXECUTION_TEST_BOUNDARY"] = "after-claim"
    _, client = system.api()
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    with closing(client):
        accepted = submit(client, system)
        marker = system.root / "boundary-reached"
        eventually(marker.exists)
        os.kill(int(marker.read_text()), signal.SIGKILL)
        assert not (system.root / "provider-starts").exists()
        (system.root / "release-boundary").touch()
        expire_owner(system, accepted)
        result = eventually(lambda: finished(client, accepted), timeout=25)
        assert result["status"] == "completed", result
        assert result["id"] == accepted["id"]
        assert (system.root / "provider-starts").read_text().splitlines() == ["none"]


def test_hunt_resumes_committed_steps_without_duplicate_effects(execution_system):
    from tests.executions.test_case_effects import contents
    from tests.executions.test_hunt_execution_system import (
        detail,
        step,
        submit_hunt,
        terminal,
    )

    system = execution_system
    system.env["EXECUTION_TEST_BOUNDARY"] = "hunt-boundary"
    _, client = system.api()
    system.start("-m", "tests.executions.runtime", "hunt-worker")
    system.start("-m", "app.executions.dispatcher")
    with closing(client):
        accepted = submit_hunt(
            system,
            client,
            [
                step("first", save_to_case=True),
                step(
                    "next",
                    depends_on=["first"],
                    parameter_mapping={"query": "first.results[0].query"},
                ),
            ],
        )
        marker = system.root / "boundary-reached"
        eventually(marker.exists)
        before = detail(client, accepted)
        evidence = contents(client, system)
        assert evidence
        os.kill(int(marker.read_text()), signal.SIGKILL)
        (system.root / "release-boundary").touch()
        result = eventually(lambda: terminal(client, accepted))
        assert result["status"] == "completed", result
        assert result["steps"][0] == before["steps"][0]
        assert len(result["steps"]) == 2
        assert result["steps"][1]["parameters"]["query"] == "owl"
        assert contents(client, system) == evidence
        assert (system.root / "provider-starts").read_text().splitlines() == [
            "none",
            "none",
        ]


def test_hard_worker_loss_stops_provider_and_does_not_repeat_uncertain_work(
    execution_system,
):
    from pathlib import Path

    from celery import Celery

    from tests.executions.test_cancellation import stopped
    from tests.executions.test_case_effects import contents

    system = execution_system
    _, client = system.api()
    system.worker()
    dispatcher = system.start("-m", "app.executions.dispatcher")
    with closing(client):
        accepted = submit(
            client, system, mode="subprocess", barrier="never", save_to_case=True
        )
        items = eventually(
            lambda: client.get(accepted["links"]["results"]).json()["items"]
        )
        pid = next(item["data"]["pid"] for item in items if item["type"] == "data")
        eventually(lambda: (system.root / "subprocess-pid").exists())
        # Kill the actual Celery pool worker, leaving its provider group alive.
        guard_pid = int(Path(f"/proc/{pid}/stat").read_text().split()[3])
        worker_pid = int(Path(f"/proc/{guard_pid}/stat").read_text().split()[3])
        system.stop(dispatcher)
        os.kill(worker_pid, signal.SIGKILL)
        eventually(lambda: stopped(pid), timeout=8)
        assert stopped(int((system.root / "subprocess-pid").read_text()))
        expire_owner(system, accepted)
        waiting = client.get(accepted["links"]["detail"]).json()
        assert waiting["dispatch_state"] == "recovery_waiting"
        assert "retained" in waiting["waiting_reason"]
        history = client.get(accepted["links"]["history"]).json()["items"]
        assert history[0]["dispatch_state"] == "recovery_waiting"
        system.start("-m", "app.executions.dispatcher")
        result = eventually(lambda: finished(client, accepted))
        assert result["error"]["code"] == "interrupted_uncertain_outcome", result
        assert client.get(accepted["links"]["results"]).json()["items"] == items
        assert contents(client, system) == []
        broker = Celery(broker=system.env["REDIS_URL"])
        broker.send_task(
            "owlculus.execute_plugin",
            args=[accepted["id"]],
            queue=system.env["PLUGIN_QUEUE"],
        )
        canary = submit(client, system, mode="empty")
        eventually(lambda: finished(client, canary))
        assert client.get(accepted["links"]["detail"]).json() == result
        assert (system.root / "provider-starts").read_text().splitlines() == [
            "never",
            "none",
        ]


def test_effect_commit_before_interruption_is_retained_without_replay(execution_system):
    from tests.executions.test_case_effects import contents

    system = execution_system
    system.env["EXECUTION_TEST_BOUNDARY"] = "after-effect"
    _, client = system.api()
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    with closing(client):
        accepted = submit(client, system, save_to_case=True)
        marker = system.root / "boundary-reached"
        eventually(marker.exists)
        evidence = contents(client, system)
        items = client.get(accepted["links"]["results"]).json()["items"]
        assert evidence
        os.kill(int(marker.read_text()), signal.SIGKILL)
        result = eventually(lambda: finished(client, accepted))
        assert result["error"]["code"] == "interrupted_uncertain_outcome", result
        assert contents(client, system) == evidence
        assert client.get(accepted["links"]["results"]).json()["items"] == items
        assert (system.root / "provider-starts").read_text().splitlines() == ["none"]


def test_completion_committed_before_ack_survives_worker_loss(execution_system):
    from tests.executions.test_case_effects import contents

    system = execution_system
    system.env["EXECUTION_TEST_BOUNDARY"] = "after-terminal"
    _, client = system.api()
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    with closing(client):
        accepted = submit(client, system, save_to_case=True)
        marker = system.root / "boundary-reached"
        eventually(marker.exists)
        result = finished(client, accepted)
        assert result["status"] == "completed"
        evidence = contents(client, system)
        os.kill(int(marker.read_text()), signal.SIGKILL)
        (system.root / "release-boundary").touch()
        canary = submit(client, system, mode="empty")
        eventually(lambda: finished(client, canary))
        assert client.get(accepted["links"]["detail"]).json() == result
        assert contents(client, system) == evidence
        assert (system.root / "provider-starts").read_text().splitlines() == [
            "none",
            "none",
        ]


@pytest.mark.parametrize("change", ["cancel", "access", "build", "definition"])
def test_hunt_recovery_rechecks_accepted_work_and_current_access(
    execution_system, change
):
    from app.database.models import Hunt, User
    from tests.executions.test_hunt_execution_system import (
        detail,
        step,
        submit_hunt,
        terminal,
    )

    system = execution_system
    system.env["EXECUTION_TEST_BOUNDARY"] = "hunt-boundary"
    _, client = system.api()
    worker = system.start("-m", "tests.executions.runtime", "hunt-worker")
    dispatcher = system.start("-m", "app.executions.dispatcher")
    with closing(client):
        accepted = submit_hunt(
            system, client, [step("first"), step("next", depends_on=["first"])]
        )
        marker = system.root / "boundary-reached"
        eventually(marker.exists)
        before = detail(client, accepted)
        system.stop(dispatcher)
        os.kill(int(marker.read_text()), signal.SIGKILL)
        eventually(lambda: detail(client, accepted)["status"] == "pending")
        assert detail(client, accepted)["dispatch_state"] == "recovery_waiting"
        if change == "cancel":
            assert (
                client.delete(accepted["links"]["detail"]).json()["status"]
                == "cancelled"
            )
        elif change == "access":
            with Session(system.engine) as db:
                user = db.get(User, system.user_id)
                user.role = "Analyst"
                db.commit()
        elif change == "build":
            system.stop(worker)
            patch_dir = system.root / "other-build"
            patch_dir.mkdir()
            (patch_dir / "sitecustomize.py").write_text(
                "import app.executions.build\napp.executions.build.implementation_build = lambda: 'other-build'\n"
            )
            system.env["PYTHONPATH"] = f"{patch_dir}:{system.env['PYTHONPATH']}"
            system.start("-m", "tests.executions.runtime", "hunt-worker")
        else:
            with Session(system.engine) as db:
                hunt = db.get(Hunt, accepted["hunt_id"])
                hunt.definition_json = {"steps": [step("different")]}
                db.commit()
        (system.root / "release-boundary").touch()
        system.start("-m", "app.executions.dispatcher")
        result = eventually(lambda: terminal(client, accepted))
        assert (
            result["status"]
            == {
                "cancel": "cancelled",
                "access": "failed",
                "build": "failed",
                "definition": "completed",
            }[change]
        ), result
        if change in {"access", "build"}:
            assert (
                result["error"]["code"]
                == {"access": "access_revoked", "build": "incompatible_build"}[change]
            )
        assert result["steps"][0] == before["steps"][0]
        assert [s["step_id"] for s in result["steps"]] == ["first", "next"]
        assert len((system.root / "provider-starts").read_text().splitlines()) == (
            2 if change == "definition" else 1
        )


@pytest.mark.parametrize("optional", [False, True])
def test_hunt_recovery_preserves_failed_step_and_dependency_semantics(
    execution_system, optional
):
    from tests.executions.test_hunt_execution_system import (
        detail,
        step,
        submit_hunt,
        terminal,
    )

    system = execution_system
    system.env["EXECUTION_TEST_BOUNDARY"] = "hunt-boundary"
    _, client = system.api()
    system.start("-m", "tests.executions.runtime", "hunt-worker")
    system.start("-m", "app.executions.dispatcher")
    with closing(client):
        accepted = submit_hunt(
            system,
            client,
            [
                step("failed", optional=optional, static_parameters={"mode": "error"}),
                step("dependent", depends_on=["failed"]),
                step("independent"),
            ],
        )
        marker = system.root / "boundary-reached"
        eventually(marker.exists)
        before = detail(client, accepted)
        os.kill(int(marker.read_text()), signal.SIGKILL)
        (system.root / "release-boundary").touch()
        result = eventually(lambda: terminal(client, accepted))
        assert result["status"] == ("completed" if optional else "partial"), result
        assert result["steps"][0] == before["steps"][0]
        assert [s["status"] for s in result["steps"]] == [
            "failed",
            "skipped",
            "completed",
        ]
        assert result["context_data"]["failed_steps"] == ["failed"]
        assert result["context_data"]["skipped_steps"] == ["dependent"]
        assert len((system.root / "provider-starts").read_text().splitlines()) == 2


def test_missing_heartbeat_keeps_cancellation_pending_until_cleanup_bound(
    execution_system,
):
    system = execution_system
    system.env["EXECUTION_TEST_BOUNDARY"] = "before-terminal"
    _, client = system.api()
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    with closing(client):
        accepted = submit(client, system)
        marker = system.root / "boundary-reached"
        eventually(marker.exists)
        assert (
            client.delete(accepted["links"]["detail"]).json()["status"] == "cancelling"
        )
        os.kill(int(marker.read_text()), signal.SIGKILL)
        # Exercise the recovery pass with an unexpired stopping bound.
        recovery = system.start("-m", "app.executions.recovery")
        eventually(lambda: recovery.poll() is not None)
        assert client.get(accepted["links"]["detail"]).json()["status"] == "cancelling"
        expire_owner(system, accepted)
        eventually(
            lambda: client.get(accepted["links"]["detail"]).json()["status"]
            == "cancelled"
        )
        result = client.get(accepted["links"]["detail"]).json()
        assert client.delete(accepted["links"]["detail"]).json() == result


def test_live_owned_duplicate_cannot_start_another_provider(execution_system):
    from celery import Celery

    system = execution_system
    _, client = system.api()
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    with closing(client):
        accepted = submit(client, system, barrier="hold")
        eventually(lambda: client.get(accepted["links"]["results"]).json()["items"])
        broker = Celery(broker=system.env["REDIS_URL"])
        broker.send_task(
            "owlculus.execute_plugin",
            args=[accepted["id"]],
            queue=system.env["PLUGIN_QUEUE"],
        )
        canary = submit(client, system, mode="empty")
        eventually(lambda: finished(client, canary))
        assert (system.root / "provider-starts").read_text().splitlines() == [
            "hold",
            "none",
        ]
        (system.root / "hold").touch()
        assert eventually(lambda: finished(client, accepted))["status"] == "completed"


def test_recovery_upgrade_preserves_started_legacy_work_conservatively(
    execution_system,
):
    from sqlalchemy import text

    from app.database.upgrade_executions import upgrade

    system = execution_system
    system.env["EXECUTION_TEST_BOUNDARY"] = "after-claim"
    api, client = system.api()
    system.worker()
    dispatcher = system.start("-m", "app.executions.dispatcher")
    with closing(client):
        accepted = submit(client, system)
        marker = system.root / "boundary-reached"
        eventually(marker.exists)
        os.kill(int(marker.read_text()), signal.SIGKILL)
        system.stop(dispatcher)
        system.stop(api)
        with system.engine.begin() as db:
            db.execute(
                text("DELETE FROM schema_upgrade WHERE version='006_worker_recovery'")
            )
            db.execute(
                text(
                    "ALTER TABLE executioncontrol DROP COLUMN operation_id, DROP COLUMN operation_started_at, DROP COLUMN recovered_at, DROP COLUMN recovery_attempts"
                )
            )
        upgrade(system.engine)
        upgrade(system.engine)
        expire_owner(system, accepted)
        _, observer = system.api()
        with closing(observer):
            system.start("-m", "app.executions.dispatcher")
            result = eventually(lambda: finished(observer, accepted))
            assert result["error"]["code"] == "interrupted_uncertain_outcome"
            assert result["error"]["operation_id"] == "legacy_unknown"
            assert not (system.root / "provider-starts").exists()


def test_repeated_prestart_infrastructure_failure_exhausts_a_bounded_retry_budget(
    execution_system,
):
    system = execution_system
    system.env["EXECUTION_TEST_EXIT_BEFORE_START"] = "1"
    _, client = system.api()
    worker = system.worker()
    system.start("-m", "app.executions.dispatcher")
    with closing(client):
        accepted = submit(client, system)
        result = eventually(lambda: finished(client, accepted), timeout=65)
        assert result["status"] == "failed"
        assert result["error"]["code"] == "recovery_exhausted"
        assert result["error"]["attempts"] == 5
        assert not (system.root / "provider-starts").exists()
        system.stop(worker)
        del system.env["EXECUTION_TEST_EXIT_BEFORE_START"]
        system.worker()
        rerun = submit(client, system)
        assert rerun["id"] != accepted["id"]
        assert eventually(lambda: finished(client, rerun))["status"] == "completed"
        assert client.get(accepted["links"]["detail"]).json() == result


def test_supervisor_loss_after_provider_exit_still_stops_descendants(execution_system):
    from tests.executions.test_cancellation import stopped

    system = execution_system
    system.env["EXECUTION_TEST_BOUNDARY"] = "before-cleanup"
    _, client = system.api()
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    descendant = None
    try:
        with closing(client):
            accepted = submit(client, system, mode="orphan-subprocess")
            marker = system.root / "boundary-reached"
            eventually(marker.exists)
            descendant = int((system.root / "subprocess-pid").read_text())
            os.kill(int(marker.read_text()), signal.SIGKILL)
            eventually(lambda: stopped(descendant), timeout=8)
            expire_owner(system, accepted)
            result = eventually(lambda: finished(client, accepted))
            assert result["status"] == "completed", result
    finally:
        if descendant and not stopped(descendant):
            os.kill(descendant, signal.SIGKILL)


def test_recovery_drains_all_stale_batches_even_without_broker(execution_system):
    import subprocess

    from app.database.models import PluginExecution

    system = execution_system
    system.env["EXECUTION_LIMIT_USER"] = "200"
    system.env["EXECUTION_LIMIT_CASE"] = "200"
    _, client = system.api()
    with closing(client):
        accepted = [submit(client, system) for _ in range(101)]
        # Arrange a fleet outage with expired leases before operation start.
        with Session(system.engine) as db:
            for control in db.exec(select(ExecutionControl)).all():
                control.owner = f"lost-{control.id}"
                control.generation = 1
                control.lease_until = get_utc_now() - timedelta(seconds=6)
                execution = db.get(PluginExecution, control.plugin_execution_id)
                execution.status = "running"
            db.commit()
        subprocess.run(
            ["docker", "stop", system.redis_container], check=True, capture_output=True
        )
        recovery = system.start("-m", "app.executions.recovery")
        eventually(lambda: recovery.poll() is not None)
        assert recovery.returncode == 0
        rows = client.get(
            accepted[0]["links"]["history"], params={"limit": 200}
        ).json()["items"]
        assert len(rows) == 101
        assert {row["status"] for row in rows} == {"queued"}
        assert {row["id"] for row in rows} == {run["id"] for run in accepted}
        assert not (system.root / "provider-starts").exists()
