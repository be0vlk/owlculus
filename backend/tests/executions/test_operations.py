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
    queue = report["queues"][system.env["PLUGIN_QUEUE"]]
    assert queue["condition"] == "missing_workers"
    assert queue["dispatch_backlog"] == 1
    assert queue["oldest_pending_seconds"] > 0
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200
    assert client.get(accepted["links"]["detail"]).json()["status"] == "queued"
    assert system.env["SECRET_KEY"] not in result.stdout
    client.close()
