"""Durability across real PostgreSQL, Redis, API restart and prefork workers."""

from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from celery import Celery
from sqlmodel import Session, select

from app.core.security import encrypt_api_key
from app.database.models import CaseUserLink, SystemConfiguration, User
from app.database.upgrade_strixy import upgrade
from tests.executions.conftest import eventually


@pytest.fixture
def strixy_system(execution_system):
    system = execution_system
    upgrade(system.engine)
    with Session(system.engine) as db:
        strixy = db.exec(select(User).where(User.system_identity == "strixy")).one()
        db.add(CaseUserLink(case_id=system.case_id, user_id=strixy.id))
        config = db.exec(select(SystemConfiguration)).one()
        config.api_keys = {
            **config.api_keys,
            "openai": {"api_key": encrypt_api_key("test-only"), "is_active": True},
        }
        db.add(config)
        db.commit()
    system.env["STRIXY_ACCEPTANCE"] = "1"
    return system


def conversation(client, system):
    url = f"/api/strixy/cases/{system.case_id}/conversations"
    response = client.post(url)
    assert response.status_code == 201, response.text
    return f"{url}/{response.json()['id']}"


def test_accepted_reply_survives_restart_and_duplicate_delivery(strixy_system):
    system = strixy_system
    api, client = system.api()
    detail = conversation(client, system)
    accepted = client.post(f"{detail}/messages", json={"content": "Persist me"})
    assert accepted.status_code == 202
    system.stop(api)
    _, reopened = system.api()
    assert reopened.get(accepted.headers["location"]).json()["status"] == "pending"
    system.start("-m", "app.executions.dispatcher")
    system.worker()
    eventually(lambda: (system.root / "strixy-ready").exists())
    broker = Celery(broker=system.env["REDIS_URL"])
    broker.send_task(
        "owlculus.execute_strixy",
        args=[accepted.json()["id"]],
        queue=system.env["PLUGIN_QUEUE"],
    )
    (system.root / "strixy-release").touch()
    eventually(
        lambda: reopened.get(accepted.headers["location"]).json()["status"]
        == "completed"
    )
    saved = reopened.get(detail).json()
    assert [m["content"] for m in saved["messages"]] == [
        "Persist me",
        "Saved answer: Persist me",
    ]
    answer = saved["messages"][-1]
    assert answer["coverage"]["counts"]["read"] >= 1
    assert answer["citations"][0]["source_id"] == f"case:{system.case_id}"
    assert reopened.get(answer["citations"][0]["url"]).status_code == 200
    assert reopened.get(detail).json() == saved
    assert (system.root / "strixy-starts").read_text().splitlines() == ["started"]


def test_concurrent_turns_have_one_acceptance(strixy_system):
    system = strixy_system
    _, client = system.api()
    detail = conversation(client, system)

    def submit(_):
        with httpx.Client(
            base_url=str(client.base_url), headers=client.headers, timeout=10
        ) as separate:
            return separate.post(
                f"{detail}/messages", json={"content": "Only one turn"}
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(submit, range(2)))
    assert sorted(statuses) == [202, 409]
    assert len(client.get(detail).json()["messages"]) == 1


def test_interrupted_model_is_failed_without_replay(strixy_system):
    system = strixy_system
    _, client = system.api()
    detail = conversation(client, system)
    accepted = client.post(f"{detail}/messages", json={"content": "Do not replay"})
    worker = system.worker()
    system.start("-m", "app.executions.dispatcher")
    eventually(lambda: (system.root / "strixy-ready").exists())
    system.stop(worker)
    eventually(
        lambda: client.get(accepted.headers["location"]).json()["status"] == "failed"
    )
    saved = client.get(detail).json()
    assert saved["runs"][0]["error_code"] == "completion_uncertain"
    assert saved["runs"][0]["partial"]["content"] == "Partial answer: Do not replay"
    assert len(saved["messages"]) == 1
    assert (system.root / "strixy-starts").read_text().splitlines() == ["started"]


def test_deleting_human_with_conversation_preserves_account_lifecycle(strixy_system):
    from app.core.security import create_access_token, get_password_hash

    system = strixy_system
    _, client = system.api()
    detail = conversation(client, system)
    accepted = client.post(f"{detail}/messages", json={"content": "Delete owner"})
    with Session(system.engine) as db:
        admin = User(
            username="deletion_admin",
            email="delete@example.com",
            password_hash=get_password_hash("not-used"),
            role="Admin",
            is_superadmin=True,
        )
        db.add(admin)
        db.commit()
        token = create_access_token(
            data={"sub": admin.auth_identity, "session_version": admin.session_version}
        )
    response = client.delete(
        f"/api/users/{system.user_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 204, response.text
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    assert client.get(accepted.headers["location"]).status_code == 401
    assert (
        client.get(detail, headers={"Authorization": f"Bearer {token}"}).status_code
        == 404
    )


@pytest.mark.parametrize("action", ["cancel", "delete", "revoke", "limit", "failure"])
def test_streamed_run_controls_across_real_worker_boundary(strixy_system, action):
    system = strixy_system
    # API restart is part of this journey; reserve time independently of the tested model limit.
    system.env["STRIXY_TEST_RUNTIME_SECONDS"] = "10"
    _, client = system.api()
    detail = conversation(client, system)
    accepted = client.post(
        f"{detail}/messages", json={"content": "Controlled analysis"}
    )
    observation = accepted.headers["location"]
    if action in {"limit", "failure"}:
        (system.root / "strixy-mode").write_text(action)
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    eventually(lambda: (system.root / "strixy-ready").exists())
    running = client.get(observation).json()
    assert running["status"] == "running"
    assert running["partial"]["content"] == "Partial answer: Controlled analysis"
    assert running["partial"]["citations"]
    _, reopened = system.api()
    assert reopened.get(observation).json() == running
    if action == "cancel":
        cancelled = client.post(observation + "/cancel").json()
        assert cancelled["status"] == "cancelled"
        assert client.post(observation + "/cancel").json() == cancelled
    elif action == "delete":
        assert client.delete(detail).status_code == 204
    elif action == "revoke":
        with Session(system.engine) as db:
            strixy = db.exec(select(User).where(User.system_identity == "strixy")).one()
            db.delete(db.get(CaseUserLink, (system.case_id, strixy.id)))
            db.commit()
    (system.root / "strixy-release").touch()
    if action in {"delete", "revoke"}:
        assert reopened.get(detail).status_code in {403, 404}
        return
    eventually(
        lambda: client.get(observation).json()["status"] not in {"pending", "running"}
    )
    saved = client.get(detail).json()
    assert len(saved["messages"]) == 1
    assert saved["runs"][0]["partial"]["content"] == running["partial"]["content"]
    if action == "limit":
        assert saved["runs"][0]["limit_code"] == "output_limit"
        (system.root / "strixy-mode").unlink()
        resumed = client.post(observation + "/continue")
        assert resumed.status_code == 202
        eventually(
            lambda: client.get(resumed.headers["location"]).json()["status"]
            == "completed"
        )
        assert len(client.get(detail).json()["messages"]) == 3
    elif action == "failure":
        assert saved["runs"][0]["error_code"] == "provider_failed"
        (system.root / "strixy-mode").unlink()
        retried = client.post(observation + "/retry")
        assert retried.status_code == 202
        eventually(
            lambda: client.get(retried.headers["location"]).json()["status"]
            == "completed"
        )


def test_progress_schema_upgrade_preserves_existing_conversations(strixy_system):
    from app.database.init_db import initialize_database
    from app.database.models import StrixyProgress

    system = strixy_system
    api, client = system.api()
    detail = conversation(client, system)
    accepted = client.post(
        f"{detail}/messages", json={"content": "Existing conversation"}
    )
    assert accepted.status_code == 202
    original = client.get(detail).json()
    system.stop(api)
    StrixyProgress.__table__.drop(system.engine)
    initialize_database(system.engine)
    initialize_database(system.engine)
    _, reopened = system.api()
    assert reopened.get(detail).json() == original


def test_mixed_attachments_cross_real_upload_broker_and_worker_boundary(strixy_system):
    import json
    from pathlib import Path

    from tests.attachment_fixtures import document, office, screenshot

    system = strixy_system
    system.env["STRIXY_TEST_RUNTIME_SECONDS"] = "30"
    from app.database.models import PluginExecution, PluginExecutionResult

    with Session(system.engine) as db:
        retained = PluginExecution(
            case_id=system.case_id,
            created_by_id=system.user_id,
            plugin_name="Synthetic",
            parameters={},
            status="completed",
        )
        db.add(retained)
        db.flush()
        db.add(
            PluginExecutionResult(
                execution_id=retained.id,
                sequence=1,
                payload={"type": "data", "data": {"employer": "Acme"}},
            )
        )
        db.commit()
    _, client = system.api()
    assert (
        client.post(
            "/api/evidence/folders",
            json={"case_id": system.case_id, "title": "Documents"},
        ).status_code
        == 201
    )
    fixtures = [
        ("witness.txt", b"Ada works at Acme.", "text/plain"),
        ("witness.json", b'{"employer":"Acme"}', "application/json"),
        ("witness.csv", b"name,employer\nAda,Acme", "text/csv"),
        (
            "witness.doc",
            (Path(__file__).parents[1] / "fixtures/strixy/witness.doc").read_bytes(),
            "application/msword",
        ),
    ]
    for extension in ("docx", "xlsx", "pptx"):
        data, mime = office(extension)
        fixtures.append(("witness." + extension, data, mime))
    fixtures.extend(
        [
            ("mixed.pdf", document(), "application/pdf"),
            ("screen.png", screenshot(), "image/png"),
        ]
    )
    uploaded = client.post(
        "/api/evidence/",
        params={
            "case_id": system.case_id,
            "title": "Witnesses",
            "category": "Documents",
        },
        files=[("files", item) for item in fixtures],
    )
    assert uploaded.status_code == 201 and not uploaded.json()["failed"], uploaded.text
    detail = conversation(client, system)
    accepted = client.post(f"{detail}/messages", json={"content": "Read attachments"})
    assert accepted.status_code == 202
    system.start("-m", "app.executions.dispatcher")
    system.worker()
    eventually(lambda: (system.root / "strixy-ready").exists())
    supplied = json.loads((system.root / "strixy-inputs.json").read_text())
    assert any(
        s["kind"] == "plugin_result" and "Acme" in s["fields"]["result"]
        for s in supplied["sources"]
    )
    visuals = json.loads((system.root / "strixy-visuals.json").read_text())
    assert len(visuals) == 3
    import base64
    import io

    from PIL import Image

    for visual in visuals:
        with Image.open(io.BytesIO(base64.b64decode(visual["data"]))) as image:
            assert image.width >= 600
    for evidence in uploaded.json()["created"]:
        source = next(
            s
            for s in supplied["sources"]
            if s["source_id"] == f"evidence:{evidence['id']}"
        )
        if source.get("visual_fields"):
            assert any(v["source_id"] == source["source_id"] for v in visuals)
            continue
        assert any(
            "Acme" in text
            for key, text in source["fields"].items()
            if key.startswith("attachment:")
        ), source
    (system.root / "strixy-release").touch()
    eventually(
        lambda: client.get(accepted.headers["location"]).json()["status"] == "completed"
    )
    saved = client.get(detail).json()
    assert len(saved["messages"][-1]["coverage"]["attachment_outcomes"]) == 9
    assert client.get(detail).json() == saved
    for evidence, (_, data, _) in zip(uploaded.json()["created"], fixtures):
        assert client.get(f"/api/evidence/{evidence['id']}/download").content == data


def test_cancellation_during_attachment_preparation_keeps_api_responsive(strixy_system):
    system = strixy_system
    temporary = system.root / "preparation"
    temporary.mkdir()
    system.env["TMPDIR"] = str(temporary)
    system.env["STRIXY_TEST_RUNTIME_SECONDS"] = "30"
    _, client = system.api()
    client.post(
        "/api/evidence/folders", json={"case_id": system.case_id, "title": "Documents"}
    ).raise_for_status()
    data = b"[" + b"0," * 3_999_999 + b"0]"
    uploaded = client.post(
        "/api/evidence/",
        params={"case_id": system.case_id, "title": "Slow", "category": "Documents"},
        files=[
            ("files", ("slow.json", data, "application/json")),
            ("files", ("later.txt", b"Later attachment", "text/plain")),
        ],
    )
    assert uploaded.status_code == 201 and not uploaded.json()["failed"], uploaded.text
    detail = conversation(client, system)
    accepted = client.post(
        f"{detail}/messages", json={"content": "Prepare attachments"}
    )
    assert accepted.status_code == 202
    system.start("-m", "app.executions.dispatcher")
    system.worker()
    eventually(lambda: any(temporary.glob("strixy-attachment-*/input.json")))
    cancelled = client.post(accepted.headers["location"] + "/cancel", timeout=2)
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    eventually(lambda: not list(temporary.glob("strixy-attachment-*")))
    assert not (system.root / "strixy-starts").exists()
    assert len(client.get(detail).json()["messages"]) == 1
    assert client.get(accepted.headers["location"]).json()["status"] == "cancelled"
