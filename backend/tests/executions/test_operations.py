"""Operator diagnostics and API liveness through separately running services."""

import json
import subprocess
import sys

from tests.executions.test_execution_system import submit


def test_missing_workers_do_not_make_api_dead(execution_system):
    system = execution_system
    _, client = system.api()
    accepted = submit(client, system, mode="empty")
    result = subprocess.run(
        [sys.executable, "-m", "app.executions.operations"],
        env=system.env,
        capture_output=True,
        text=True,
        check=False,
    )
    report = json.loads(result.stdout)
    assert result.returncode == 1
    assert report["dispatcher"] == "unavailable"
    queue = report["queues"][system.env["PLUGIN_QUEUE"]]
    assert queue["condition"] == "missing_workers"
    assert queue["dispatch_backlog"] == 1
    assert queue["oldest_pending_seconds"] > 0
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200
    assert client.get(accepted["links"]["detail"]).json()["status"] == "queued"
    assert system.env["SECRET_KEY"] not in result.stdout
    client.close()


def test_separate_broker_and_event_urls_run_both_queues(execution_system):
    from redis import Redis

    from tests.executions.conftest import eventually
    from tests.executions.test_hunt_execution_system import step, submit_hunt, terminal

    system = execution_system
    base = system.env["REDIS_URL"].rsplit("/", 1)[0]
    system.env["EXECUTION_BROKER_URL"] = base + "/1"
    system.env["EXECUTION_EVENT_REDIS_URL"] = base + "/2"
    _, client = system.api()
    system.worker()
    system.start("-m", "tests.executions.runtime", "hunt-worker")
    system.start("-m", "app.executions.dispatcher")
    plugin = submit(client, system, barrier="cancel-split", save_to_case=False)
    hunt = submit_hunt(system, client, [step("first")])
    eventually(lambda: client.get(plugin["links"]["results"]).json()["items"])
    assert client.delete(plugin["links"]["detail"]).status_code == 200
    assert eventually(lambda: terminal(client, plugin))["status"] == "cancelled"
    assert eventually(lambda: terminal(client, hunt))["status"] == "completed"
    with Redis.from_url(system.env["EXECUTION_EVENT_REDIS_URL"]) as events:
        eventually(lambda: events.xlen(f"owlculus:events:plugin:{plugin['id']}") > 0)
    with Redis.from_url(system.env["REDIS_URL"]) as rate_limits:
        assert rate_limits.xlen(f"owlculus:events:plugin:{plugin['id']}") == 0
    client.close()
