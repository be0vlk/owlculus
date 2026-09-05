"""Operator CLI: background capability and durable metrics, separate from API liveness."""

import json
from datetime import UTC
from typing import Any, cast

from redis import Redis
from sqlalchemy import text

from app.core.utils import get_utc_now
from app.database.connection import engine
from app.executions.celery_app import HUNT_QUEUE, QUEUE, app
from app.executions.events import redis_client


def snapshot():
    report: dict[str, Any] = {"status": "ready", "queues": {}, "redis": {}}
    with engine.connect() as db:
        for kind, table, queue in (
            ("plugin", "pluginexecution", QUEUE),
            ("hunt", "huntexecution", HUNT_QUEUE),
        ):
            row = db.execute(text(f"""
                SELECT count(*) FILTER (WHERE e.status IN ('queued','pending')) AS pending,
                  count(*) FILTER (WHERE e.status IN ('running','cancelling')) AS active,
                  count(*) FILTER (WHERE e.status='failed') AS failures,
                  count(*) FILTER (WHERE o.published_at IS NULL AND e.status IN ('queued','pending')) AS dispatch_backlog,
                  count(*) FILTER (WHERE o.last_error IS NOT NULL AND e.status IN ('queued','pending')) AS dispatch_errors,
                  min(e.created_at) FILTER (WHERE e.status IN ('queued','pending')) AS oldest_pending,
                  avg(extract(epoch FROM e.completed_at-e.started_at)) AS duration_seconds_mean,
                  max(extract(epoch FROM e.completed_at-c.cancellation_requested_at)) AS cancellation_seconds_max,
                  coalesce(sum(c.recovery_attempts),0) AS recoveries
                FROM {table} e LEFT JOIN executioncontrol c ON c.{kind}_execution_id=e.id
                LEFT JOIN executionoutbox o ON o.control_id=c.id
            """)).mappings().one()
            metrics = dict(row)
            oldest = metrics.pop("oldest_pending")
            metrics["oldest_pending_seconds"] = (
                (get_utc_now() - oldest.replace(tzinfo=UTC)).total_seconds()
                if oldest
                else 0
            )
            report["queues"][queue] = metrics
        report["event_publication_backlog"] = db.execute(
            text("SELECT count(*) FROM executionevent")
        ).scalar_one()
    try:
        workers = app.control.inspect(timeout=2).active_queues() or {}
        for queue, metrics in report["queues"].items():
            metrics["live_workers"] = sum(
                any(item["name"] == queue for item in queues)
                for queues in workers.values()
            )
            metrics["condition"] = (
                "missing_workers"
                if not metrics["live_workers"]
                else (
                    "failed_dispatch"
                    if metrics["dispatch_errors"]
                    else "waiting_for_capacity" if metrics["pending"] else "ready"
                )
            )
            if metrics["condition"] in {"missing_workers", "failed_dispatch"}:
                report["status"] = "degraded"
    except Exception:  # noqa: BLE001 - never expose broker credentials
        report["status"] = "degraded"
        report["worker_observation"] = "unavailable"
    for role, client in (
        (
            "broker",
            Redis.from_url(
                app.conf.broker_url, socket_timeout=2, socket_connect_timeout=2
            ),
        ),
        ("events", redis_client()),
    ):
        try:
            with client:
                info = cast(dict[str, Any], client.info("memory"))
                report["redis"][role] = {
                    key: info[key]
                    for key in (
                        "used_memory",
                        "used_memory_peak",
                        "maxmemory",
                        "maxmemory_policy",
                    )
                }
        except Exception:  # noqa: BLE001 - never expose connection strings
            report["redis"][role] = {"status": "unavailable"}
            report["status"] = "degraded"
    return report


def main():
    try:
        report = snapshot()
    except Exception:  # noqa: BLE001 - operator error excludes connection credentials
        report = {"status": "degraded", "database": "unavailable"}
    print(json.dumps(report, default=float))
    raise SystemExit(0 if report["status"] == "ready" else 1)


if __name__ == "__main__":
    main()
