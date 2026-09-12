"""Durability across real PostgreSQL, Redis, API restart and prefork workers."""

from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from app.core.security import encrypt_api_key
from app.database.models import CaseUserLink, SystemConfiguration, User
from app.database.upgrade_strixy import upgrade
from celery import Celery
from sqlmodel import Session, select

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
