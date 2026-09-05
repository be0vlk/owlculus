"""Acceptance across the public API, real broker, dispatcher and prefork worker."""

import time

from celery import Celery
from sqlmodel import Session, select

from app.database.models import CaseUserLink
from tests.executions.conftest import eventually


def submit(client, system, **params):
    response = client.post(
        "/api/plugins/AcceptancePlugin/execute",
        json={"case_id": system.case_id, **params},
    )
    assert response.status_code == 202, response.text
    assert response.headers["location"] == response.json()["links"]["detail"]
    return response.json()


def finished(client, accepted):
    state = client.get(accepted["links"]["detail"]).json()
    return state if state["status"] in {"completed", "failed"} else None


def test_provider_survives_api_restart_and_retains_ordered_partial_results(
    execution_system,
):
    system = execution_system
    api, client = system.api()
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    start = time.monotonic()
    accepted = submit(client, system, barrier="release", save_to_case=True)
    assert time.monotonic() - start < 5
    eventually(lambda: client.get(accepted["links"]["results"]).json()["items"])
    assert client.get(accepted["links"]["detail"]).json()["status"] == "running"
    system.stop(api)
    client.close()
    _, observer = system.api()
    try:
        assert (
            observer.get(accepted["links"]["results"]).json()["items"][0]["data"][
                "case_id"
            ]
            == system.case_id
        )
        broker = Celery(broker=system.env["REDIS_URL"])
        broker.send_task(
            "owlculus.execute_plugin",
            args=[accepted["id"]],
            queue=system.env["PLUGIN_QUEUE"],
        )
        (system.root / "release").touch()
        state = eventually(lambda: finished(observer, accepted))
        assert state["status"] == "completed", state
        events = observer.get(accepted["links"]["results"]).json()["items"]
        assert [event["type"] for event in events] == ["data", "complete"]
        evidence = observer.get(f"/api/evidence/case/{system.case_id}").json()
        entities = observer.get(f"/api/cases/{system.case_id}/entities").json()
        assert len(evidence) == 2
        assert all(item["created_by_id"] == system.user_id for item in evidence)
        assert entities[0]["data"]["ip_address"] == "192.0.2.10"
        broker.send_task(
            "owlculus.execute_plugin",
            args=[accepted["id"]],
            queue=system.env["PLUGIN_QUEUE"],
        )
        empty = submit(observer, system, mode="empty")
        assert eventually(lambda: finished(observer, empty))["status"] == "completed"
        assert observer.get(empty["links"]["results"]).json()["items"] == [
            {"type": "complete", "data": {}}
        ]
        assert (system.root / "provider-starts").read_text().splitlines().count(
            "release"
        ) == 1
        assert (
            observer.get(accepted["links"]["detail"]).json()["revision"]
            == state["revision"]
        )
        assert len(observer.get(f"/api/evidence/case/{system.case_id}").json()) == 2
        history = observer.get(
            f"/api/plugins/executions/case/{system.case_id}?limit=1"
        ).json()
        assert history["items"][0]["id"] == empty["id"]
        older = observer.get(
            f"/api/plugins/executions/case/{system.case_id}?limit=1&cursor={history['next_cursor']}"
        ).json()
        assert older["items"][0]["id"] == accepted["id"]
    finally:
        observer.close()


def test_errors_vault_and_revocation_at_claim(execution_system):
    system = execution_system
    _, client = system.api()
    try:
        revoked = submit(client, system)
        with Session(system.engine) as db:
            link = db.exec(
                select(CaseUserLink).where(CaseUserLink.user_id == system.user_id)
            ).one()
            db.delete(link)
            db.commit()
        system.worker()
        system.start("-m", "app.executions.dispatcher")
        assert client.get(revoked["links"]["detail"]).status_code == 403
        from app.database.models import PluginExecution

        def revoked_failed():
            with Session(system.engine) as db:
                return db.get(PluginExecution, revoked["id"]).status == "failed"

        eventually(revoked_failed)
        with Session(system.engine) as db:
            db.add(CaseUserLink(case_id=system.case_id, user_id=system.user_id))
            db.commit()
        assert (
            client.get(revoked["links"]["detail"]).json()["error"]["code"]
            == "access_revoked"
        )
        assert not (system.root / "provider-starts").exists()
        failed = submit(client, system, mode="error")
        assert eventually(lambda: finished(client, failed))["status"] == "failed"
        page = client.get(f"{failed['links']['results']}?limit=1").json()
        assert page["items"][0]["type"] == "data"
        remaining = client.get(
            f"{failed['links']['results']}?cursor={page['next_cursor']}"
        ).json()
        assert [item["type"] for item in remaining["items"]] == ["error", "complete"]
        vault = submit(client, system, mode="vault")
        assert eventually(lambda: finished(client, vault))["status"] == "completed"
        events = client.get(vault["links"]["results"]).json()["items"]
        assert events[0]["data"] == {"configured": True, "redacted": "[redacted]"}
        assert client.get(f"/api/evidence/case/{system.case_id}").json() == []
        assert client.get(f"/api/cases/{system.case_id}/entities").json() == []
    finally:
        client.close()


def test_revoked_access_blocks_case_effects_and_missing_keys_fail_once(
    execution_system,
):
    from app.database.models import PluginExecution, SystemConfiguration

    system = execution_system
    _, client = system.api()
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    try:
        accepted = submit(client, system, barrier="effect-release", save_to_case=True)
        eventually(lambda: client.get(accepted["links"]["results"]).json()["items"])
        with Session(system.engine) as db:
            link = db.exec(
                select(CaseUserLink).where(CaseUserLink.user_id == system.user_id)
            ).one()
            db.delete(link)
            config = db.exec(select(SystemConfiguration)).one()
            config.api_keys = {}
            db.commit()
        (system.root / "effect-release").touch()

        def failed():
            with Session(system.engine) as db:
                return db.get(PluginExecution, accepted["id"]).status == "failed"

        eventually(failed)
        with Session(system.engine) as db:
            db.add(CaseUserLink(case_id=system.case_id, user_id=system.user_id))
            db.commit()
        assert client.get(f"/api/evidence/case/{system.case_id}").json() == []
        assert client.get(f"/api/cases/{system.case_id}/entities").json() == []
        missing = submit(client, system, mode="vault")
        state = eventually(lambda: finished(client, missing))
        assert state["status"] == "failed"
        assert "API key required" in state["error"]["message"]
    finally:
        client.close()


def test_upgrade_preserves_hunts_and_enforces_immutable_execution(execution_system):
    import pytest
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from app.database.models import Hunt, HuntExecution
    from app.database.upgrade_executions import upgrade

    system = execution_system
    # Simulate the pre-feature schema with historical and running hunts.
    with system.engine.begin() as db:
        db.execute(
            text(
                "DROP TABLE pluginexecutionresult, executionoutbox, executioncontrol, pluginexecution, schema_upgrade"
            )
        )
    with Session(system.engine) as db:
        hunt = Hunt(
            name="historical",
            display_name="Historical",
            description="Preserved",
            category="Other",
            definition_json={},
        )
        db.add(hunt)
        db.flush()
        for state in ["completed", "running"]:
            db.add(
                HuntExecution(
                    hunt_id=hunt.id,
                    case_id=system.case_id,
                    created_by_id=system.user_id,
                    status=state,
                    initial_parameters={},
                )
            )
        db.commit()
    upgrade(system.engine)
    upgrade(system.engine)
    with Session(system.engine) as db:
        assert {row.status for row in db.exec(select(HuntExecution)).all()} == {
            "completed",
            "running",
        }
    _, client = system.api()
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    try:
        accepted = submit(client, system, mode="empty")
        eventually(lambda: finished(client, accepted))
        with pytest.raises(DBAPIError), system.engine.begin() as db:
            db.execute(
                text("UPDATE pluginexecution SET status = 'running' WHERE id=:id"),
                {"id": accepted["id"]},
            )
        assert client.get(accepted["links"]["detail"]).json()["status"] == "completed"
    finally:
        client.close()


def test_expired_owner_cannot_commit_late_results_or_case_effects(execution_system):
    from datetime import timedelta

    from app.core.utils import get_utc_now
    from app.database.models import ExecutionControl

    system = execution_system
    _, client = system.api()
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    try:
        accepted = submit(client, system, barrier="stale-release", save_to_case=True)
        eventually(lambda: client.get(accepted["links"]["results"]).json()["items"])
        before = client.get(accepted["links"]["detail"]).json()
        with Session(system.engine) as db:
            control = db.exec(
                select(ExecutionControl).where(
                    ExecutionControl.plugin_execution_id == accepted["id"]
                )
            ).one()
            control.lease_until = get_utc_now() - timedelta(seconds=1)
            db.commit()
        (system.root / "stale-release").touch()
        subsequent = submit(client, system, mode="empty")
        eventually(lambda: finished(client, subsequent))
        assert (
            client.get(accepted["links"]["detail"]).json()["revision"]
            == before["revision"]
        )
        assert client.get(f"/api/evidence/case/{system.case_id}").json() == []
        assert client.get(f"/api/cases/{system.case_id}/entities").json() == []
    finally:
        client.close()


def test_vault_secrets_are_redacted_from_saved_evidence_and_entities(execution_system):
    system = execution_system
    _, client = system.api()
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    try:
        accepted = submit(client, system, mode="vault", save_to_case=True)
        assert eventually(lambda: finished(client, accepted))["status"] == "completed"
        evidence = client.get(f"/api/evidence/case/{system.case_id}").json()
        file = next(item for item in evidence if not item["is_folder"])
        content = client.get(f"/api/evidence/{file['id']}/download")
        assert content.status_code == 200
        assert "acceptance-vault-secret" not in content.text
        assert "[redacted]" in content.text
        entities = client.get(f"/api/cases/{system.case_id}/entities")
        assert "acceptance-vault-secret" not in entities.text
        assert "[redacted]" in entities.text
        assert all(
            "acceptance-vault-secret" not in path.read_text()
            for path in system.root.glob("*.log")
        )
    finally:
        client.close()
