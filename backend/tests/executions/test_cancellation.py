"""Stop guarantees through two APIs and real supervised provider processes."""

import subprocess
import time
from contextlib import closing
from pathlib import Path

import pytest

from tests.executions.conftest import eventually
from tests.executions.test_execution_system import submit
from tests.executions.test_hunt_execution_system import step, submit_hunt, terminal


def stopped(pid):
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
        return stat.split()[2] == "Z"
    except FileNotFoundError:
        return True


def state(client, accepted):
    return client.get(accepted["links"]["detail"]).json()


def test_cancel_before_claim_and_repeat_through_another_api(execution_system):
    system = execution_system
    _, client = system.api()
    _, other = system.api()
    with closing(client), closing(other):
        accepted = submit(client, system, barrier="never")
        cancelled = other.delete(accepted["links"]["detail"])
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"
        system.worker()
        system.start("-m", "app.executions.dispatcher")
        assert client.delete(accepted["links"]["detail"]).json() == cancelled.json()
        # A successful canary proves the queue is being consumed after cancellation.
        canary = submit(client, system, mode="empty")
        eventually(lambda: state(client, canary)["status"] == "completed")
        assert "never" not in (system.root / "provider-starts").read_text()
        assert state(client, accepted)["status"] == "cancelled"


@pytest.mark.parametrize("mode", ["success", "blocking", "subprocess"])
def test_cancel_stops_local_work_and_retains_output_without_redis(
    execution_system, mode
):
    system = execution_system
    _, client = system.api()
    _, other = system.api()
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    with closing(client), closing(other):
        accepted = submit(client, system, mode=mode, barrier="never", save_to_case=True)
        items = eventually(
            lambda accepted=accepted: client.get(accepted["links"]["results"]).json()[
                "items"
            ]
        )
        pid = next(item["data"]["pid"] for item in items if item["type"] == "data")
        if mode == "subprocess":
            eventually(lambda: (system.root / "subprocess-pid").exists())
        subprocess.run(
            ["docker", "stop", system.redis_container], check=True, capture_output=True
        )
        started = time.monotonic()
        response = other.delete(accepted["links"]["detail"])
        assert response.status_code == 200, response.text
        assert response.json()["status"] in {"cancelling", "cancelled"}
        eventually(
            lambda accepted=accepted: state(client, accepted)["status"] == "cancelled",
            timeout=30,
        )
        assert time.monotonic() - started < 30
        assert stopped(pid)
        if mode == "subprocess":
            assert stopped(int((system.root / "subprocess-pid").read_text()))
        retained = client.get(accepted["links"]["results"]).json()["items"]
        assert retained == items
        assert other.delete(accepted["links"]["detail"]).json()["status"] == "cancelled"
        (system.root / "never").touch()
        assert state(client, accepted)["status"] == "cancelled"


def test_hunt_cancel_preserves_completed_steps_and_prevents_later_steps(
    execution_system,
):
    system = execution_system
    _, client = system.api()
    system.start("-m", "tests.executions.runtime", "hunt-worker")
    system.start("-m", "app.executions.dispatcher")
    with closing(client):
        accepted = submit_hunt(
            system,
            client,
            [
                step("first"),
                step(
                    "active",
                    depends_on=["first"],
                    static_parameters={"barrier": "never"},
                ),
                step("last", depends_on=["active"]),
            ],
        )
        eventually(
            lambda: (
                "never" in (system.root / "provider-starts").read_text()
                if (system.root / "provider-starts").exists()
                else False
            )
        )
        assert (
            client.delete(accepted["links"]["detail"]).json()["status"] == "cancelling"
        )
        result = eventually(lambda: terminal(client, accepted))
        assert result["status"] == "cancelled"
        assert [s["status"] for s in result["steps"]] == [
            "completed",
            "cancelled",
            "cancelled",
        ]
        assert result["steps"][1]["output"]["result_count"] == 1
        assert len((system.root / "provider-starts").read_text().splitlines()) == 2


@pytest.mark.parametrize("kind", ["plugin", "step", "hunt"])
def test_execution_deadline_stops_blocking_work(execution_system, kind):
    system = execution_system
    system.env[
        {
            "plugin": "PLUGIN_EXECUTION_SECONDS",
            "step": "HUNT_STEP_SECONDS",
            "hunt": "HUNT_EXECUTION_SECONDS",
        }[kind]
    ] = "12"
    _, client = system.api()
    system.start(
        "-m",
        "tests.executions.runtime",
        "worker" if kind == "plugin" else "hunt-worker",
    )
    system.start("-m", "app.executions.dispatcher")
    with closing(client):
        accepted = (
            submit(client, system, mode="blocking")
            if kind == "plugin"
            else submit_hunt(
                system,
                client,
                [step("blocked", static_parameters={"mode": "blocking"})],
            )
        )
        eventually(lambda: (system.root / "blocked").exists())
        result = eventually(
            lambda: (
                state(client, accepted)
                if state(client, accepted)["status"] == "failed"
                else None
            ),
            timeout=20,
        )
        assert result["error"]["code"] == "execution_timeout"
        assert result["error"]["partial"]


def test_storage_partition_stops_at_lease_expiry_and_reports_after_restoration(
    execution_system,
):
    system = execution_system
    _, client = system.api()
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    with closing(client):
        accepted = submit(client, system, mode="blocking")
        items = eventually(
            lambda accepted=accepted: client.get(accepted["links"]["results"]).json()[
                "items"
            ]
        )
        pid = next(item["data"]["pid"] for item in items if item["type"] == "data")
        subprocess.run(
            ["docker", "pause", system.db_container], check=True, capture_output=True
        )
        try:
            eventually(lambda: stopped(pid), timeout=65)
        finally:
            subprocess.run(
                ["docker", "unpause", system.db_container],
                check=True,
                capture_output=True,
            )
        result = eventually(
            lambda: (
                state(client, accepted)
                if state(client, accepted)["status"] == "failed"
                else None
            )
        )
        assert result["error"]["code"] == "lease_expired"


def test_cancellation_races_claim_and_completion(execution_system):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    system = execution_system
    _, client = system.api()
    _, other = system.api()
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    with closing(client), closing(other):
        for index in range(4):
            marker = f"race-{index}"
            accepted = submit(client, system, barrier=marker, save_to_case=True)
            if index >= 2:
                eventually(
                    lambda accepted=accepted: client.get(
                        accepted["links"]["results"]
                    ).json()["items"]
                )
            barrier = Barrier(2)

            def cancel(barrier=barrier, accepted=accepted):
                barrier.wait()
                return other.delete(accepted["links"]["detail"])

            with ThreadPoolExecutor(max_workers=1) as pool:
                request = pool.submit(cancel)
                barrier.wait()
                (system.root / marker).touch()
                response = request.result()
            assert response.status_code == 200
            result = eventually(
                lambda accepted=accepted: (
                    state(client, accepted)
                    if state(client, accepted)["status"] in {"completed", "cancelled"}
                    else None
                )
            )
            retained = client.get(accepted["links"]["results"]).json()["items"]
            assert other.delete(accepted["links"]["detail"]).json() == result
            assert client.get(accepted["links"]["results"]).json()["items"] == retained
