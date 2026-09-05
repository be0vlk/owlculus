"""Output limits and retained chunks through real public execution APIs."""

from tests.executions.conftest import eventually
from tests.executions.test_execution_system import finished, submit
from tests.executions.test_hunt_execution_system import (
    detail,
    step,
    submit_hunt,
    terminal,
)


def test_plugin_and_hunt_limits_retain_ordered_partial_output(execution_system):
    system = execution_system
    system.env.update(
        EXECUTION_EVENT_LIMIT_BYTES="256", EXECUTION_RESULT_LIMIT_BYTES="500"
    )
    _, client = system.api()
    system.worker()
    system.start("-m", "tests.executions.runtime", "hunt-worker")
    system.start("-m", "app.executions.dispatcher")
    try:
        for mode, code, count in [
            ("large-event", "event_size_limit", 1),
            ("many-results", "result_size_limit", 4),
        ]:
            accepted = submit(client, system, mode=mode, save_to_case=True)
            state = eventually(lambda accepted=accepted: finished(client, accepted))
            assert state["status"] == "failed"
            assert state["error"]["code"] == code
            events = client.get(accepted["links"]["results"]).json()["items"]
            assert len([e for e in events if e["type"] == "data"]) == count
            assert events[-2]["data"]["partial"] is True
        for optional, status in [(False, "partial"), (True, "completed")]:
            accepted = submit_hunt(
                system,
                client,
                [
                    step(
                        "limited",
                        optional=optional,
                        static_parameters={"mode": "large-event"},
                    )
                ],
            )
            state = eventually(lambda accepted=accepted: terminal(client, accepted))
            assert state["status"] == status, state
            output = state["steps"][0]["output"]
            assert output["result_count"] == 1
            assert output["errors"][0]["code"] == "event_size_limit"
            exported = client.get(
                accepted["links"]["export"], params={"format": "json"}
            ).json()
            assert exported["execution"]["steps"][0]["output"] == output
        assert client.get(f"/api/evidence/case/{system.case_id}").json() == []
        assert client.get(f"/api/cases/{system.case_id}/entities").json() == []
    finally:
        client.close()


def test_hunt_chunks_are_readable_before_step_finishes(execution_system):
    system = execution_system
    _, client = system.api()
    system.start("-m", "tests.executions.runtime", "hunt-worker")
    system.start("-m", "app.executions.dispatcher")
    try:
        accepted = submit_hunt(
            system, client, [step("stream", static_parameters={"barrier": "release"})]
        )
        url = f"/api/hunts/executions/{accepted['id']}/steps/stream/results"
        page = eventually(
            lambda: (
                response
                if (response := client.get(url)).status_code == 200
                and response.json()["items"]
                else None
            )
        )
        assert page.json()["items"][0]["data"]["query"] == "owl"
        assert detail(client, accepted)["status"] == "running"
        assert client.get(url, params={"limit": 201}).status_code == 422
        (system.root / "release").touch()
        assert (
            eventually(lambda accepted=accepted: terminal(client, accepted))["status"]
            == "completed"
        )
    finally:
        client.close()


def test_default_byte_boundaries_and_evidence_parts(execution_system):
    system = execution_system
    _, client = system.api()
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    try:
        # The compact UTF-8 wire event is exactly 1 MiB, including its envelope.
        at_event = submit(client, system, mode="sized", bytes=1048576)
        assert eventually(lambda: finished(client, at_event))["status"] == "completed"
        over_event = submit(client, system, mode="sized", bytes=1048577)
        assert (
            eventually(lambda: finished(client, over_event))["error"]["code"]
            == "event_size_limit"
        )
        at_total = submit(
            client, system, mode="sized", bytes=1048576, count=25, save_to_case=True
        )
        assert eventually(lambda: finished(client, at_total))["status"] == "completed"
        saved = [
            item
            for item in client.get(f"/api/evidence/case/{system.case_id}").json()
            if not item["is_folder"]
        ]
        assert len(saved) > 1
        assert all(item["created_by_id"] == system.user_id for item in saved)
        files = sorted((system.root / "uploads").rglob("*.txt"))
        assert sum(path.stat().st_size for path in files) > 25 * 1024 * 1024 - 1000
        over_total = submit(client, system, mode="sized", bytes=1048576, count=26)
        assert (
            eventually(lambda: finished(client, over_total))["error"]["code"]
            == "result_size_limit"
        )
        events = client.get(over_total["links"]["results"]).json()["items"]
        assert len([event for event in events if event["type"] == "data"]) == 25
    finally:
        client.close()


def test_result_pages_survive_live_event_expiration(execution_system):
    import redis

    system = execution_system
    _, client = system.api()
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    try:
        accepted = submit(client, system, mode="pages")
        assert (
            eventually(lambda accepted=accepted: finished(client, accepted))["status"]
            == "completed"
        )
        redis.Redis.from_url(system.env["REDIS_URL"]).flushdb()
        first = client.get(accepted["links"]["results"]).json()
        assert len(first["items"]) == 50
        second = client.get(
            accepted["links"]["results"],
            params={"cursor": first["cursor"], "limit": 200},
        ).json()
        events = first["items"] + second["items"]
        assert [e["data"]["index"] for e in events if e["type"] == "data"] == list(
            range(205)
        )
        assert second["next_cursor"] is None
        assert (
            client.get(accepted["links"]["results"], params={"limit": 201}).status_code
            == 422
        )
    finally:
        client.close()


def test_receipt_upgrade_is_repeatable_on_prior_schema(execution_system):
    from sqlalchemy import text

    from app.database.upgrade_executions import upgrade

    system = execution_system
    with system.engine.begin() as db:
        db.execute(text("DROP TABLE executioneffect, huntstepresult"))
        db.execute(
            text("ALTER TABLE pluginexecutionresult DROP COLUMN operation_index")
        )
        db.execute(
            text("ALTER TABLE executioncontrol DROP COLUMN cancellation_requested_at")
        )
        db.execute(
            text(
                "DELETE FROM schema_upgrade WHERE version='004_bounded_results_and_effects'"
            )
        )
    upgrade(system.engine)
    upgrade(system.engine)
    _, client = system.api()
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    try:
        accepted = submit(client, system, save_to_case=True)
        assert (
            eventually(lambda accepted=accepted: finished(client, accepted))["status"]
            == "completed"
        )
        assert len(client.get(f"/api/evidence/case/{system.case_id}").json()) == 2
        assert (
            client.get(accepted["links"]["results"]).json()["items"][0]["type"]
            == "data"
        )
    finally:
        client.close()
