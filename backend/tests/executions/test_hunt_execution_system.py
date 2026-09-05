"""Durable hunt behavior through independent API, dispatcher and worker processes."""

from sqlmodel import Session

from app.database.models import Hunt
from tests.executions.conftest import eventually


def step(name, **kwargs):
    return {
        "step_id": name,
        "plugin_name": "AcceptancePlugin",
        "display_name": name,
        "description": name,
        "save_to_case": False,
        **kwargs,
    }


def submit_hunt(system, client, steps):
    with Session(system.engine) as db:
        hunt = Hunt(
            name=f"acceptance-{len(system.processes)}-{id(steps)}",
            display_name="Acceptance hunt",
            description="Deterministic",
            category="test",
            definition_json={"steps": steps},
        )
        db.add(hunt)
        db.commit()
        hunt_id = hunt.id
    response = client.post(
        f"/api/hunts/{hunt_id}/execute",
        json={"case_id": system.case_id, "parameters": {}},
    )
    assert response.status_code == 202, response.text
    assert response.headers["location"] == response.json()["links"]["detail"]
    return response.json()


def detail(client, accepted):
    response = client.get(accepted["links"]["detail"], params={"include_steps": True})
    assert response.status_code == 200, response.text
    return response.json()


def terminal(client, accepted):
    state = detail(client, accepted)
    return (
        state
        if state["status"] in {"completed", "partial", "failed", "cancelled"}
        else None
    )


def test_hunt_survives_api_restart_and_uses_accepted_definition(execution_system):
    system = execution_system
    api, client = system.api()
    accepted = submit_hunt(
        system,
        client,
        [
            step("first", static_parameters={"barrier": "release"}),
            step(
                "second",
                depends_on=["first"],
                parameter_mapping={"query": "first.results[0].query"},
            ),
        ],
    )
    with Session(system.engine) as db:
        hunt = db.get(Hunt, accepted["hunt_id"])
        hunt.definition_json = {"steps": []}
        db.commit()
    system.start("-m", "tests.executions.runtime", "hunt-worker")
    system.start("-m", "app.executions.dispatcher")
    eventually(lambda: (system.root / "provider-starts").exists())
    assert detail(client, accepted)["status"] == "running"
    system.stop(api)
    client.close()
    _, observer = system.api()
    try:
        (system.root / "release").touch()
        state = eventually(lambda: terminal(observer, accepted))
        assert state["status"] == "completed", state
        assert [s["step_id"] for s in state["steps"]] == ["first", "second"]
        assert state["steps"][1]["parameters"]["query"] == "owl"
        assert state["context_data"]["step_outputs"]["first"]["result_count"] == 1
        assert (
            observer.get(f"/api/hunts/cases/{system.case_id}/executions").json()[0][
                "id"
            ]
            == accepted["id"]
        )
        assert (
            observer.get(
                accepted["links"]["export"], params={"format": "json"}
            ).status_code
            == 200
        )
    finally:
        observer.close()


def test_hunt_capacity_is_separate_and_failures_retain_outputs(execution_system):
    from tests.executions.test_execution_system import finished, submit

    system = execution_system
    _, client = system.api()
    try:
        accepted = [
            submit_hunt(
                system,
                client,
                [step("blocked", static_parameters={"barrier": f"release-{i}"})],
            )
            for i in range(3)
        ]
        system.start("-m", "tests.executions.runtime", "hunt-worker")
        system.worker()
        system.start("-m", "app.executions.dispatcher")
        eventually(
            lambda: (system.root / "provider-starts").exists()
            and len((system.root / "provider-starts").read_text().splitlines()) == 2
        )
        states = [detail(client, item)["status"] for item in accepted]
        assert states.count("running") == 2
        assert states.count("pending") == 1
        plugin = submit(client, system, mode="empty")
        assert eventually(lambda: finished(client, plugin))["status"] == "completed"
        assert [detail(client, item)["status"] for item in accepted] == states
        for i in range(3):
            (system.root / f"release-{i}").touch()
        for item in accepted:
            assert (
                eventually(lambda item=item: terminal(client, item))["status"]
                == "completed"
            )
        for optional, expected in [(True, "completed"), (False, "partial")]:
            item = submit_hunt(
                system,
                client,
                [
                    step(
                        "error", optional=optional, static_parameters={"mode": "error"}
                    ),
                    step("dependent", depends_on=["error"]),
                    step("independent", static_parameters={"mode": "empty"}),
                ],
            )
            state = eventually(lambda item=item: terminal(client, item))
            assert state["status"] == expected
            assert [s["status"] for s in state["steps"]] == [
                "failed",
                "skipped",
                "completed",
            ]
            assert state["steps"][0]["output"]["result_count"] == 1
            assert (
                state["steps"][0]["output"]["errors"][0]["message"]
                == "Deterministic failure"
            )
            assert state["context_data"]["skipped_steps"] == ["dependent"]
        empty = submit_hunt(system, client, [])
        assert eventually(lambda: terminal(client, empty))["status"] == "completed"
    finally:
        client.close()


def test_hunt_rechecks_access_before_claim_and_later_steps(execution_system):
    from app.database.models import User

    system = execution_system
    _, client = system.api()
    try:
        revoked = submit_hunt(system, client, [step("never")])
        with Session(system.engine) as db:
            user = db.get(User, system.user_id)
            user.role = "Analyst"
            db.commit()
        system.start("-m", "tests.executions.runtime", "hunt-worker")
        system.start("-m", "app.executions.dispatcher")
        state = eventually(lambda: terminal(client, revoked))
        assert state["error"]["code"] == "access_revoked"
        assert not (system.root / "provider-starts").exists()
        with Session(system.engine) as db:
            user = db.get(User, system.user_id)
            user.role = "Investigator"
            db.commit()
        later = submit_hunt(
            system,
            client,
            [
                step("first", static_parameters={"barrier": "revoke"}),
                step("never", depends_on=["first"]),
            ],
        )
        eventually(lambda: (system.root / "provider-starts").exists())
        with Session(system.engine) as db:
            user = db.get(User, system.user_id)
            user.role = "Analyst"
            db.commit()
        (system.root / "revoke").touch()
        state = eventually(lambda: terminal(client, later))
        assert state["status"] == "failed"
        assert state["steps"][0]["output"]["result_count"] == 1
        assert (system.root / "provider-starts").read_text().splitlines() == ["revoke"]
    finally:
        client.close()


def test_hunt_incompatible_worker_fails_before_provider(execution_system):
    system = execution_system
    _, client = system.api()
    try:
        accepted = submit_hunt(system, client, [step("never")])
        # A worker from another implementation build, with unchanged accepted work.
        patch_dir = system.root / "other-build"
        patch_dir.mkdir()
        (patch_dir / "sitecustomize.py").write_text(
            "import app.executions.build\napp.executions.build.implementation_build = lambda: 'other-build'\n"
        )
        original_path = system.env["PYTHONPATH"]
        system.env["PYTHONPATH"] = f"{patch_dir}:{original_path}"
        system.start("-m", "tests.executions.runtime", "hunt-worker")
        system.env["PYTHONPATH"] = original_path
        system.start("-m", "app.executions.dispatcher")
        state = eventually(lambda: terminal(client, accepted))
        assert state["error"]["code"] == "incompatible_build"
        assert not (system.root / "provider-starts").exists()
    finally:
        client.close()


def test_hunt_cutover_preserves_historical_output_and_interrupts_legacy_work(
    execution_system,
):
    from sqlalchemy import text

    from app.database.models import HuntExecution, HuntStep
    from app.database.upgrade_executions import upgrade

    system = execution_system
    with Session(system.engine) as db:
        hunt = Hunt(
            name="legacy",
            display_name="Legacy",
            description="Historical",
            category="test",
            definition_json={"steps": []},
        )
        db.add(hunt)
        db.flush()
        complete = HuntExecution(
            hunt_id=hunt.id,
            case_id=system.case_id,
            created_by_id=system.user_id,
            status="completed",
            initial_parameters={},
            context_data={"kept": True},
        )
        pending = HuntExecution(
            hunt_id=hunt.id,
            case_id=system.case_id,
            created_by_id=system.user_id,
            status="running",
            initial_parameters={},
        )
        db.add_all([complete, pending])
        db.flush()
        output = HuntStep(
            execution_id=complete.id,
            step_id="original",
            plugin_name="AcceptancePlugin",
            status="completed",
            parameters={},
            output={"result_count": 1, "results": [{"retained": True}]},
        )
        db.add(output)
        db.commit()
        completed_id, pending_id, step_id = complete.id, pending.id, output.id
    # Reproduce the ticket 01 schema, including duplicate API-owned step records.
    with system.engine.begin() as db:
        db.execute(
            text("DELETE FROM schema_upgrade WHERE version='002_hunt_executions'")
        )
        db.execute(text("DROP TRIGGER hunt_execution_immutable ON huntexecution"))
        db.execute(
            text(
                "ALTER TABLE huntexecution DROP COLUMN definition_snapshot, DROP COLUMN implementation_build, DROP COLUMN error"
            )
        )
        db.execute(
            text(
                "ALTER TABLE executioncontrol DROP CONSTRAINT execution_kind_xor, DROP COLUMN hunt_execution_id"
            )
        )
        db.execute(
            text(
                "ALTER TABLE executioncontrol ALTER COLUMN plugin_execution_id SET NOT NULL"
            )
        )
        db.execute(text("ALTER TABLE huntstep DROP CONSTRAINT uq_hunt_step"))
        db.execute(
            text(
                "INSERT INTO huntstep(execution_id, step_id, plugin_name, status, parameters, output) SELECT execution_id, step_id, plugin_name, status, parameters, output FROM huntstep WHERE id=:id"
            ),
            {"id": step_id},
        )
    upgrade(system.engine)
    upgrade(system.engine)
    _, client = system.api()
    try:
        history = client.get(f"/api/hunts/cases/{system.case_id}/executions").json()
        assert {row["id"] for row in history} == {completed_id, pending_id}
        original = client.get(
            f"/api/hunts/executions/{completed_id}?include_steps=true"
        ).json()
        assert original["status"] == "completed"
        assert original["context_data"] == {"kept": True}
        assert original["steps"][0]["id"] == step_id
        assert len(original["steps"]) == 2
        assert all(
            s["output"]["results"] == [{"retained": True}] for s in original["steps"]
        )
        interrupted = client.get(f"/api/hunts/executions/{pending_id}").json()
        assert interrupted["status"] == "failed"
        assert interrupted["error"]["code"] == "legacy_interrupted"
        assert (
            client.get(
                f"/api/hunts/executions/{completed_id}/export?format=json"
            ).status_code
            == 200
        )
    finally:
        client.close()
