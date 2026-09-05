"""Reliable acceptance and dispatch through independent processes."""

from concurrent.futures import ThreadPoolExecutor

from sqlmodel import Session, select

from app.database.models import ExecutionControl, ExecutionOutbox
from tests.executions.conftest import eventually


def test_matching_submissions_across_apis_share_acceptance(execution_system):
    system = execution_system
    _, first = system.api()
    _, second = system.api()
    path = "/api/plugins/AcceptancePlugin/execute"
    payload = {"case_id": system.case_id}

    def submit(index):
        return (first if index % 2 else second).post(
            path, json=payload, headers={"Idempotency-Key": "lost-response"}
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(submit, range(12)))
    assert {r.status_code for r in responses} == {202}
    assert len({r.json()["id"] for r in responses}) == 1
    accepted = responses[0].json()
    with Session(system.engine) as db:
        assert len(db.exec(select(ExecutionControl)).all()) == 1
        assert len(db.exec(select(ExecutionOutbox)).all()) == 1
    assert (
        second.post(
            path,
            json={**payload, "query": "different"},
            headers={"Idempotency-Key": "lost-response"},
        ).status_code
        == 409
    )
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    eventually(
        lambda: first.get(accepted["links"]["detail"]).json()["status"] == "completed"
    )
    assert submit(0).json()["id"] == accepted["id"]
    assert (
        first.post(
            path, json=payload, headers={"Idempotency-Key": "deliberate-rerun"}
        ).json()["id"]
        != accepted["id"]
    )


def test_published_unstarted_work_recovers_after_redis_loss(execution_system):
    from redis import Redis

    system = execution_system
    system.env["EXECUTION_REDISPATCH_SECONDS"] = "1"
    _, client = system.api()
    accepted = client.post(
        "/api/plugins/AcceptancePlugin/execute", json={"case_id": system.case_id}
    ).json()
    dispatcher = system.start("-m", "app.executions.dispatcher")
    eventually(
        lambda: client.get(accepted["links"]["detail"]).json()["dispatch_state"]
        == "published"
    )
    system.stop(dispatcher)
    broker = Redis.from_url(system.env["REDIS_URL"])
    broker.flushdb()
    state = client.get(accepted["links"]["detail"]).json()
    assert state["waiting_reason"] == "Waiting for an available background worker"
    assert state["last_dispatch_at"]
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    eventually(
        lambda: client.get(accepted["links"]["detail"]).json()["status"] == "completed"
    )
    assert (system.root / "provider-starts").read_text().splitlines() == ["none"]


import pytest

from app.database.models import CaseUserLink, Hunt


@pytest.mark.parametrize("limit", ["GLOBAL", "CASE", "USER"])
def test_admission_is_atomic_across_kinds_and_api_instances(execution_system, limit):
    system = execution_system
    system.env[f"EXECUTION_LIMIT_{limit}"] = "2"
    _, first = system.api()
    _, second = system.api()
    with Session(system.engine) as db:
        hunt = Hunt(
            name="admission",
            display_name="Admission",
            description="Test",
            category="test",
            definition_json={"steps": []},
        )
        db.add(hunt)
        db.commit()
        hunt_id = hunt.id

    def submit(index):
        client = first if index % 2 else second
        path = (
            f"/api/hunts/{hunt_id}/execute"
            if index % 2
            else "/api/plugins/AcceptancePlugin/execute"
        )
        return client.post(
            path,
            json={"case_id": system.case_id},
            headers={"Idempotency-Key": f"admission-{index}"},
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(submit, range(8)))
    assert [r.status_code for r in responses].count(202) == 2
    assert [r.status_code for r in responses].count(429) == 6
    for index, response in enumerate(responses):
        if response.status_code == 429:
            assert response.headers["retry-after"] == "10"
        else:
            assert submit(index).json()["id"] == response.json()["id"]
    with Session(system.engine) as db:
        assert len(db.exec(select(ExecutionOutbox)).all()) == 2
    system.worker()
    system.start("-m", "tests.executions.runtime", "hunt-worker")
    system.start("-m", "app.executions.dispatcher")
    for response in responses:
        if response.status_code == 202:
            eventually(
                lambda response=response: first.get(
                    response.json()["links"]["detail"]
                ).json()["status"]
                == "completed"
            )
    assert submit(9).status_code == 202


def test_hunt_retry_normalization_conflicts_and_revoked_access(execution_system):
    system = execution_system
    _, first = system.api()
    _, second = system.api()
    with Session(system.engine) as db:
        hunt = Hunt(
            name="retry",
            display_name="Retry",
            description="Test",
            category="test",
            definition_json={
                "steps": [],
                "initial_parameters": {"query": {"type": "string", "default": "owl"}},
            },
        )
        db.add(hunt)
        db.commit()
        hunt_id = hunt.id
    path = f"/api/hunts/{hunt_id}/execute"

    def submit(index):
        return (first if index % 2 else second).post(
            path,
            json={
                "case_id": system.case_id,
                "parameters": {} if index % 2 else {"query": "owl"},
            },
            headers={"Idempotency-Key": "hunt-retry"},
        )

    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(submit, range(6)))
    assert {r.status_code for r in responses} == {202}
    assert len({r.json()["id"] for r in responses}) == 1
    assert (
        first.post(
            path,
            json={"case_id": system.case_id, "parameters": {"query": "changed"}},
            headers={"Idempotency-Key": "hunt-retry"},
        ).status_code
        == 409
    )
    system.start("-m", "tests.executions.runtime", "hunt-worker")
    system.start("-m", "app.executions.dispatcher")
    accepted = responses[0].json()
    eventually(
        lambda: first.get(accepted["links"]["detail"]).json()["status"] == "completed"
    )
    assert submit(1).json()["id"] == accepted["id"]
    with Session(system.engine) as db:
        link = db.exec(
            select(CaseUserLink).where(
                CaseUserLink.case_id == system.case_id,
                CaseUserLink.user_id == system.user_id,
            )
        ).one()
        db.delete(link)
        db.commit()
    assert submit(0).status_code in {403, 404}


@pytest.mark.parametrize("window", ["before", "after"])
def test_dispatcher_crash_around_publication_preserves_identity(
    execution_system, window
):
    system = execution_system
    _, client = system.api()
    accepted = client.post(
        "/api/plugins/AcceptancePlugin/execute",
        json={"case_id": system.case_id, "barrier": "provider-release"},
    ).json()
    dispatcher = system.start("-m", "tests.executions.runtime", f"dispatch-{window}")
    eventually(lambda: (system.root / "publication-window").exists())
    # Abrupt death rolls back the database claim/acknowledgment in either window.
    import os
    import signal

    os.killpg(dispatcher.pid, signal.SIGKILL)
    dispatcher.wait(timeout=5)
    system.worker()
    system.env["EXECUTION_REDISPATCH_SECONDS"] = "1"
    system.start("-m", "app.executions.dispatcher")
    system.start("-m", "app.executions.dispatcher")
    eventually(
        lambda: client.get(accepted["links"]["detail"]).json()["status"] == "running"
    )
    (system.root / "provider-release").touch()
    eventually(
        lambda: client.get(accepted["links"]["detail"]).json()["status"] == "completed"
    )
    assert (system.root / "provider-starts").read_text().splitlines() == [
        "provider-release"
    ]


def test_broker_outage_retries_then_fails_visibly_without_provider_start(
    execution_system,
):
    import subprocess
    from datetime import timedelta

    from app.core.utils import get_utc_now

    system = execution_system
    _, client = system.api()
    accepted = client.post(
        "/api/plugins/AcceptancePlugin/execute", json={"case_id": system.case_id}
    ).json()
    subprocess.run(
        ["docker", "pause", system.redis_container], check=True, capture_output=True
    )
    try:
        system.start("-m", "app.executions.dispatcher")
        for attempt in range(1, 6):
            state = eventually(
                lambda attempt=attempt: (
                    state
                    if (state := client.get(accepted["links"]["detail"]).json())[
                        "dispatch_attempts"
                    ]
                    == attempt
                    else None
                ),
                timeout=15,
            )
            if attempt < 5:
                assert "broker unavailable" in state["waiting_reason"]
                assert state["next_dispatch_at"]
                with Session(system.engine) as db:
                    row = db.exec(select(ExecutionOutbox)).one()
                    row.available_at = get_utc_now() - timedelta(seconds=1)
                    db.commit()
        assert state["status"] == "failed"
        assert state["error"]["code"] == "dispatch_failed"
        assert state["dispatch_state"] == "failed"
        assert client.get(f"/api/cases/{system.case_id}").status_code == 200
        assert not (system.root / "provider-starts").exists()
    finally:
        subprocess.run(
            ["docker", "unpause", system.redis_container],
            check=True,
            capture_output=True,
        )
    system.worker()
    rerun = client.post(
        "/api/plugins/AcceptancePlugin/execute", json={"case_id": system.case_id}
    ).json()
    eventually(
        lambda: client.get(rerun["links"]["detail"]).json()["status"] == "completed"
    )
    assert client.get(accepted["links"]["detail"]).json()["status"] == "failed"


def test_conflicting_race_and_idempotency_scope(execution_system):
    from app.core.security import create_access_token
    from app.database.models import User

    system = execution_system
    _, first = system.api()
    _, second = system.api()
    path = "/api/plugins/AcceptancePlugin/execute"

    def submit(index):
        return (first if index % 2 else second).post(
            path,
            json={"case_id": system.case_id, "query": "a" if index % 2 else "b"},
            headers={"Idempotency-Key": "conflicting-race"},
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(submit, range(8)))
    assert [r.status_code for r in responses].count(202) == 4
    assert [r.status_code for r in responses].count(409) == 4
    assert len({r.json()["id"] for r in responses if r.status_code == 202}) == 1
    with Session(system.engine) as db:
        user = User(
            username="second",
            email="second@example.com",
            password_hash="unused",
            role="Investigator",
        )
        db.add(user)
        db.flush()
        db.add(CaseUserLink(user_id=user.id, case_id=system.case_id))
        hunt = Hunt(
            name="scope",
            display_name="Scope",
            description="Test",
            category="test",
            definition_json={"steps": []},
        )
        db.add(hunt)
        db.commit()
        hunt_id = hunt.id
    token = create_access_token(data={"sub": "second"})
    assert (
        second.post(
            path,
            json={"case_id": system.case_id},
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": "conflicting-race",
            },
        ).status_code
        == 202
    )
    assert (
        first.post(
            f"/api/hunts/{hunt_id}/execute",
            json={"case_id": system.case_id},
            headers={"Idempotency-Key": "conflicting-race"},
        ).status_code
        == 202
    )
    with Session(system.engine) as db:
        link = db.exec(
            select(CaseUserLink).where(CaseUserLink.user_id == system.user_id)
        ).one()
        db.delete(link)
        db.commit()
    assert submit(0).status_code in {403, 404}


def test_upgrade_adds_submission_metadata_to_prior_schema(execution_system):
    from sqlalchemy import text

    from app.database.upgrade_executions import upgrade

    system = execution_system
    _, client = system.api()
    accepted = client.post(
        "/api/plugins/AcceptancePlugin/execute", json={"case_id": system.case_id}
    ).json()
    with system.engine.begin() as connection:
        connection.execute(text("DROP TABLE executionsubmission"))
        connection.execute(
            text(
                "ALTER TABLE executionoutbox DROP COLUMN last_attempt_at, DROP COLUMN last_error"
            )
        )
        connection.execute(
            text("DELETE FROM schema_upgrade WHERE version='003_reliable_submission'")
        )
    upgrade(system.engine)
    upgrade(system.engine)
    assert client.get(accepted["links"]["detail"]).json()["id"] == accepted["id"]
    first = client.post(
        "/api/plugins/AcceptancePlugin/execute",
        json={"case_id": system.case_id},
        headers={"Idempotency-Key": "after-upgrade"},
    )
    retry = client.post(
        "/api/plugins/AcceptancePlugin/execute",
        json={"case_id": system.case_id},
        headers={"Idempotency-Key": "after-upgrade"},
    )
    assert first.status_code == retry.status_code == 202
    assert first.json()["id"] == retry.json()["id"]
