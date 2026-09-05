"""Opt-in engineering benchmark; real processes and deterministic providers only."""

import asyncio
import json
import os
import platform
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from statistics import quantiles

import pytest
from redis import Redis
from sqlmodel import Session

from app.database.models import Hunt
from tests.executions.conftest import eventually
from tests.executions.test_execution_system import submit
from tests.executions.test_hunt_execution_system import step, submit_hunt, terminal


def p95(values):
    return (
        quantiles(values, n=100, method="inclusive")[94]
        if len(values) > 1
        else values[0]
    )


def test_background_performance_acceptance(execution_system):
    if os.environ.get("RUN_EXECUTION_BENCHMARK") != "1":
        pytest.skip("Set RUN_EXECUTION_BENCHMARK=1 for timing acceptance")
    system = execution_system
    _, client = system.api()
    system.worker()
    system.start("-m", "tests.executions.runtime", "hunt-worker")
    system.start("-m", "app.executions.dispatcher")

    def operations():
        result = subprocess.run(
            [os.sys.executable, "-m", "app.executions.operations"],
            env=system.env,
            capture_output=True,
            text=True,
            check=False,
        )
        return json.loads(result.stdout) if result.returncode == 0 else None

    eventually(operations)
    with Session(system.engine) as db:
        hunt = Hunt(
            name="benchmark",
            display_name="Benchmark",
            description="Deterministic",
            category="test",
            definition_json={
                "steps": [
                    step("first", static_parameters={"delay_ms": 2500}),
                    step(
                        "second",
                        depends_on=["first"],
                        static_parameters={"delay_ms": 2500},
                    ),
                ]
            },
        )
        db.add(hunt)
        db.commit()
        hunt_id = hunt.id
    case_path = f"/api/cases/{system.case_id}"

    def read_case():
        start = time.monotonic()
        response = client.get(case_path)
        assert response.status_code == 200, response.text
        return time.monotonic() - start

    idle = [read_case() for _ in range(20)]
    redis = Redis.from_url(system.env["REDIS_URL"])

    async def rate_limit_attempt():
        from redis.asyncio import Redis as AsyncRedis

        from app.core.rate_limiting import RedisClientRateLimiter

        async with AsyncRedis.from_url(system.env["REDIS_URL"]) as connection:
            limiter = RedisClientRateLimiter(
                connection, max_attempts=1, window_seconds=600
            )
            return await limiter.allow("benchmark-client")

    assert asyncio.run(rate_limit_attempt())
    memory_before = redis.info("memory")["used_memory"]

    def submission(index):
        start = time.monotonic()
        if index < 10:
            accepted = submit(client, system, delay_ms=5000, save_to_case=False)
        else:
            response = client.post(
                f"/api/hunts/{hunt_id}/execute",
                json={"case_id": system.case_id, "parameters": {}},
            )
            assert response.status_code == 202, response.text
            accepted = response.json()
        return accepted, time.monotonic() - start

    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=20) as pool:
        submissions = list(pool.map(submission, range(20)))
    pending = [item for item, _ in submissions]
    states, loaded = [], []
    memory_peak = memory_before
    process_memory_peak_kib = 0
    while pending and time.monotonic() - start < 90:
        loaded.append(read_case())
        for item in pending[:]:
            state = client.get(item["links"]["detail"]).json()
            if state["status"] in {"completed", "failed", "partial", "cancelled"}:
                assert state["status"] == "completed", state
                states.append((item["kind"], state))
                pending.remove(item)
        memory_peak = max(memory_peak, redis.info("memory")["used_memory"])
        rows = [
            tuple(map(int, row.split()))
            for row in subprocess.check_output(
                ["ps", "-eo", "pid=,ppid=,rss="], text=True
            ).splitlines()
        ]
        owned = {process.pid for process in system.processes}
        for _ in range(5):
            owned.update(pid for pid, parent, _ in rows if parent in owned)
        process_memory_peak_kib = max(
            process_memory_peak_kib, sum(rss for pid, _, rss in rows if pid in owned)
        )
        time.sleep(0.1)
    elapsed = time.monotonic() - start
    assert not pending
    waits = []
    capacity = {}
    for kind in ("plugin", "hunt"):
        edges = []
        for state_kind, state in states:
            if state_kind != kind:
                continue
            created, began, ended = [
                datetime.fromisoformat(state[key])
                for key in ("created_at", "started_at", "completed_at")
            ]
            waits.append((began - created).total_seconds())
            edges.extend([(began, 1), (ended, -1)])
        active = maximum = 0
        for _, delta in sorted(edges):
            active += delta
            maximum = max(maximum, active)
        capacity[kind] = maximum
    assert not asyncio.run(rate_limit_attempt())
    # Full hunt capacity must leave standalone plugin capacity available.
    blocked = [
        submit_hunt(
            system,
            client,
            [step("blocked", static_parameters={"barrier": "release-saturation"})],
        )
        for _ in range(2)
    ]
    eventually(
        lambda: all(
            client.get(item["links"]["detail"]).json()["status"] == "running"
            for item in blocked
        )
    )
    saturation_start = time.monotonic()
    isolated = submit(client, system, delay_ms=5000, save_to_case=False)
    eventually(
        lambda: client.get(isolated["links"]["detail"]).json()["status"] == "running"
    )
    isolated_start = time.monotonic() - saturation_start
    cancelled_at = time.monotonic()
    response = client.delete(isolated["links"]["detail"])
    assert response.status_code in {200, 202}, response.text
    eventually(
        lambda: client.get(isolated["links"]["detail"]).json()["status"] == "cancelled"
    )
    cancellation = time.monotonic() - cancelled_at
    (system.root / "release-saturation").touch()
    for item in blocked:
        eventually(lambda item=item: terminal(client, item))
    output_bytes = sum(
        len(
            client.get(
                (
                    item["links"]["results"]
                    if item["kind"] == "plugin"
                    else item["links"]["detail"]
                ),
                params={"include_steps": True},
            ).content
        )
        for item, _ in submissions
    )
    report = {
        "retained_result_response_bytes": output_bytes,
        "hardware": {
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
            "memory": Path("/proc/meminfo").read_text().splitlines()[0],
            "cpu": subprocess.check_output(["lscpu"], text=True),
        },
        "database": "PostgreSQL 15 Alpine defaults; dedicated Docker database",
        "concurrency_per_queue": 2,
        "jobs": 20,
        "provider_output": "one small JSON result per plugin/step plus completion",
        "idle_case_p95_seconds": p95(idle),
        "loaded_case_p95_seconds": p95(loaded),
        "submission_p95_seconds": p95([duration for _, duration in submissions]),
        "completion_seconds": elapsed,
        "queue_wait_p95_seconds": p95(waits),
        "max_active": capacity,
        "redis_bytes_before": memory_before,
        "redis_bytes_peak": memory_peak,
        "api_dispatcher_worker_process_tree_peak_rss_kib": process_memory_peak_kib,
        "isolated_plugin_start_seconds": isolated_start,
        "cooperative_cancellation_seconds": cancellation,
        "operations": operations(),
    }
    output = Path(
        os.environ.get(
            "EXECUTION_BENCHMARK_REPORT", str(system.root / "benchmark.json")
        )
    )
    output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    client.close()
    redis.close()
    assert report["submission_p95_seconds"] < 1
    assert report["loaded_case_p95_seconds"] < max(0.5, 2 * p95(idle))
    assert elapsed < 40
    assert capacity == {"plugin": 2, "hunt": 2}
    assert isolated_start < 2
    assert cancellation < 5


def test_fault_and_limits_acceptance_under_load(execution_system):
    """Fault subjects share capacity with the same 20 deterministic background jobs."""
    if os.environ.get("RUN_EXECUTION_BENCHMARK") != "1":
        pytest.skip("Set RUN_EXECUTION_BENCHMARK=1 for loaded fault acceptance")
    import signal

    from tests.executions.test_cancellation import stopped

    system = execution_system
    system.env["EXECUTION_STREAM_LIMIT"] = "8"
    system.env["EXECUTION_RESULT_LIMIT_BYTES"] = "2048"
    _, client = system.api()
    # Place fault subjects ahead of the load, so their running state is measurable
    # while the 20 concurrent submissions are still outstanding.
    subjects = [
        submit(client, system, mode=mode, barrier=f"fault-{mode}", save_to_case=False)
        for mode in ("success", "blocking", "subprocess")
    ]
    uncertain = submit(client, system, barrier="uncertain", save_to_case=False)
    capped = submit(client, system, mode="pages", save_to_case=False)
    with Session(system.engine) as db:
        hunt = Hunt(
            name="fault-load",
            display_name="Fault load",
            description="Deterministic",
            category="test",
            definition_json={
                "steps": [
                    step("first", static_parameters={"delay_ms": 2500}),
                    step(
                        "second",
                        depends_on=["first"],
                        static_parameters={"delay_ms": 2500},
                    ),
                ]
            },
        )
        db.add(hunt)
        db.commit()
        hunt_id = hunt.id

    def submission(index):
        if index < 10:
            return submit(client, system, delay_ms=5000, save_to_case=False)
        response = client.post(
            f"/api/hunts/{hunt_id}/execute",
            json={"case_id": system.case_id, "parameters": {}},
        )
        assert response.status_code == 202, response.text
        return response.json()

    with ThreadPoolExecutor(max_workers=20) as pool:
        load = list(pool.map(submission, range(20)))
    system.worker()
    system.start("-m", "tests.executions.runtime", "hunt-worker")
    system.start("-m", "app.executions.dispatcher")
    measurements = {}
    for mode, accepted in zip(
        ("success", "blocking", "subprocess"), subjects, strict=True
    ):
        items = eventually(
            lambda accepted=accepted: client.get(accepted["links"]["results"]).json()[
                "items"
            ]
        )
        pid = next(item["data"]["pid"] for item in items if item["type"] == "data")
        if mode == "blocking":
            eventually(lambda: (system.root / "blocked").exists())
        if mode == "subprocess":
            eventually(lambda: (system.root / "subprocess-pid").exists())
        assert any(
            client.get(item["links"]["detail"]).json()["status"]
            in {"queued", "pending", "running"}
            for item in load
        )
        began = time.monotonic()
        assert client.delete(accepted["links"]["detail"]).status_code == 200
        eventually(
            lambda accepted=accepted: client.get(accepted["links"]["detail"]).json()[
                "status"
            ]
            == "cancelled",
            timeout=30,
        )
        measurements[f"{mode}_cancellation_seconds"] = time.monotonic() - began
        assert stopped(pid)
        if mode == "subprocess":
            assert stopped(int((system.root / "subprocess-pid").read_text()))
        assert client.get(accepted["links"]["results"]).json()["items"] == items
    items = eventually(
        lambda: client.get(uncertain["links"]["results"]).json()["items"]
    )
    pid = next(item["data"]["pid"] for item in items if item["type"] == "data")
    guard_pid = int(Path(f"/proc/{pid}/stat").read_text().split()[3])
    worker_pid = int(Path(f"/proc/{guard_pid}/stat").read_text().split()[3])
    began = time.monotonic()
    os.kill(worker_pid, signal.SIGKILL)
    result = eventually(lambda: terminal(client, uncertain), timeout=90)
    measurements["stale_owner_recovery_seconds"] = time.monotonic() - began
    assert result["error"]["code"] == "interrupted_uncertain_outcome"
    assert stopped(pid)
    assert client.get(uncertain["links"]["results"]).json()["items"] == items
    for item in load:
        assert (
            eventually(lambda item=item: terminal(client, item))["status"]
            == "completed"
        )
    capped_state = eventually(lambda: terminal(client, capped))
    assert capped_state["status"] == "failed"
    assert "limit" in json.dumps(capped_state["error"]).lower()
    retained = client.get(capped["links"]["results"]).json()["items"]
    assert retained
    redis = Redis.from_url(system.env["REDIS_URL"])
    key = f"owlculus:events:plugin:{capped['id']}"
    eventually(lambda: redis.xlen(key) == 8)
    redis.delete(key)
    assert client.get(capped["links"]["results"]).json()["items"] == retained
    measurements["redis_memory"] = redis.info("memory")["used_memory_peak"]
    measurements["retained_result_bytes"] = len(json.dumps(retained).encode())
    output = Path(
        os.environ.get("EXECUTION_FAULT_REPORT", str(system.root / "faults.json"))
    )
    output.write_text(json.dumps(measurements, indent=2))
    print(json.dumps(measurements, indent=2))
    redis.close()
    client.close()
    assert measurements["success_cancellation_seconds"] < 5
    assert measurements["blocking_cancellation_seconds"] < 30
    assert measurements["subprocess_cancellation_seconds"] < 30
    assert (
        measurements["stale_owner_recovery_seconds"] < 85
    )  # 75 + 10s dispatcher cadence
