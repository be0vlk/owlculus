"""Account identity and revocation regressions through real HTTP authentication."""

import pytest
from sqlmodel import Session

from app.core.security import get_password_hash
from app.database.connection import get_db
from app.database.models import User
from app.main import app

PASSWORD = "account-password"


@pytest.fixture
def accounts(client, engine):
    with Session(engine) as db:
        db.add(
            User(
                username="admin",
                email="admin@example.com",
                password_hash=get_password_hash("adminpass"),
                role="Admin",
                is_superadmin=True,
            )
        )
        db.commit()

    def database():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    admin = login(client, "admin", "adminpass")
    response = client.post(
        "/api/users/",
        headers=admin,
        json={
            "username": "original",
            "email": "original@example.com",
            "password": PASSWORD,
            "is_active": True,
            "role": "Investigator",
        },
    )
    assert response.status_code == 201, response.text
    return client, admin, response.json(), login(client, "original")


def login(client, username, password=PASSWORD):
    response = client.post(
        "/api/auth/login", data={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.parametrize("actor", ["self", "admin"])
def test_rename_and_privileged_username_reuse_preserves_original_identity(
    accounts, actor, engine
):
    client, admin, user, token = accounts
    from app.database.models import Case, CaseUserLink

    with Session(engine) as db:
        assigned = Case(case_number="ORIGINAL", title="Original case", client_id=1)
        foreign = Case(case_number="REPLACEMENT", title="Replacement case", client_id=1)
        db.add_all([assigned, foreign])
        db.flush()
        assigned_id, foreign_id = assigned.id, foreign.id
        db.add(CaseUserLink(case_id=assigned_id, user_id=user["id"]))
        db.commit()
    assert (
        client.put(
            f"/api/users/{user['id']}",
            headers=token if actor == "self" else admin,
            json={"username": "12345"},
        ).status_code
        == 200
    )
    replacement = client.post(
        "/api/users/",
        headers=admin,
        json={
            "username": "original",
            "email": "replacement@example.com",
            "password": PASSWORD,
            "is_active": True,
            "role": "Admin",
        },
    )
    assert replacement.status_code == 201
    with Session(engine) as db:
        db.add(CaseUserLink(case_id=foreign_id, user_id=replacement.json()["id"]))
        db.commit()
    me = client.get("/api/users/me", headers=token)
    assert me.status_code == 200
    assert me.json()["id"] == user["id"]
    assert me.json()["username"] == "12345"
    assert client.get(f"/api/cases/{assigned_id}", headers=token).status_code == 200
    assert client.get(f"/api/cases/{foreign_id}", headers=token).status_code == 403
    assert (
        client.get(
            f"/api/cases/{assigned_id}", headers=login(client, "12345")
        ).status_code
        == 200
    )

    assert client.get("/api/users/", headers=token).status_code == 403
    assert (
        client.get("/api/users/me", headers=login(client, "12345")).json()["id"]
        == user["id"]
    )


@pytest.mark.parametrize("reset", [False, True])
def test_password_change_revokes_all_sessions_and_preserves_other_accounts(
    accounts, reset, monkeypatch
):
    client, admin, user, token = accounts
    from datetime import timedelta

    from app.core import security

    issued_at = security.get_utc_now() - timedelta(seconds=1)
    with monkeypatch.context() as clock:
        clock.setattr(security, "get_utc_now", lambda: issued_at)
        another = login(client, "original")
    assert another != token
    failed = client.put(
        "/api/users/me/password",
        headers=token,
        json={
            "current_password": "wrong",
            "new_password": "changed-password",
        },
    )
    assert failed.status_code == 422
    assert client.get("/api/users/me", headers=token).status_code == 200
    login(client, "original")
    for old_password, new_password in [
        (PASSWORD, "changed-password"),
        ("changed-password", "twice-changed"),
    ]:
        response = client.put(
            f"/api/users/{user['id']}/password" if reset else "/api/users/me/password",
            headers=admin if reset else token,
            json={"current_password": old_password, "new_password": new_password},
        )
        assert response.status_code == 200, response.text
        assert response.json()["id"] == user["id"]
        for previous in [token, another]:
            assert client.get("/api/users/me", headers=previous).status_code == 401
        assert client.get("/api/users/", headers=admin).status_code == 200
        assert (
            client.post(
                "/api/auth/login",
                data={"username": "original", "password": old_password},
            ).status_code
            == 401
        )
        token = login(client, "original", new_password)
        assert client.get("/api/users/me", headers=token).status_code == 200


def test_analyst_demotion_removes_lead_writes_but_preserves_reads(accounts, engine):
    from app.database.models import Case, CaseUserLink

    client, admin, user, token = accounts
    with Session(engine) as db:
        case = Case(case_number="LEAD", title="Assigned case", client_id=1)
        db.add(case)
        db.flush()
        case_id = case.id
        db.add(CaseUserLink(case_id=case_id, user_id=user["id"], is_lead=True))
        db.commit()
    created = client.post(
        "/api/tasks/",
        headers=token,
        json={"case_id": case_id, "title": "Task", "description": "Lead task"},
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["id"]
    assert (
        client.put(
            f"/api/users/{user['id']}", headers=admin, json={"role": "Analyst"}
        ).status_code
        == 200
    )
    assert client.get(f"/api/cases/{case_id}", headers=token).status_code == 200
    assert client.get(f"/api/tasks/{task_id}", headers=token).status_code == 200
    for role in ["Analyst", "Investigator"]:
        if role == "Investigator":
            assert (
                client.put(
                    f"/api/users/{user['id']}", headers=admin, json={"role": role}
                ).status_code
                == 200
            )
        assert (
            client.post(
                "/api/tasks/",
                headers=token,
                json={"case_id": case_id, "title": "Task", "description": "Denied"},
            ).status_code
            == 403
        )
        assert (
            client.put(
                f"/api/tasks/{task_id}", headers=token, json={"description": "Denied"}
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"/api/tasks/{task_id}/assign",
                headers=token,
                params={"user_id": user["id"]},
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/tasks/bulk/assign",
                headers=token,
                json={"task_ids": [task_id], "user_id": user["id"]},
            ).json()
            == []
        )
        assert (
            client.get(f"/api/tasks/{task_id}", headers=token).json()["assigned_to_id"]
            is None
        )


def test_only_superadmin_can_demote_then_delete_admin(accounts):
    client, superadmin, _, _ = accounts
    ids = []
    for username in ["ordinary_admin", "target_admin"]:
        response = client.post(
            "/api/users/",
            headers=superadmin,
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": PASSWORD,
                "role": "Admin",
                "is_active": True,
            },
        )
        assert response.status_code == 201
        ids.append(response.json()["id"])
    ordinary = login(client, "ordinary_admin")
    target = ids[1]
    assert client.delete(f"/api/users/{target}", headers=ordinary).status_code == 403
    for account_id in ids:
        assert (
            client.put(
                f"/api/users/{account_id}",
                headers=ordinary,
                json={"role": "Investigator"},
            ).status_code
            == 403
        )
    assert (
        client.get("/api/users/me", headers=login(client, "target_admin")).json()[
            "role"
        ]
        == "Admin"
    )
    assert (
        client.put(
            f"/api/users/{target}", headers=superadmin, json={"role": "Investigator"}
        ).status_code
        == 200
    )
    assert client.delete(f"/api/users/{target}", headers=superadmin).status_code == 204


def test_deleted_account_token_cannot_follow_recreated_account(accounts):
    client, admin, user, token = accounts
    assert client.delete(f"/api/users/{user['id']}", headers=admin).status_code == 204
    recreated = client.post(
        "/api/users/",
        headers=admin,
        json={
            "username": "original",
            "email": "original@example.com",
            "password": PASSWORD,
            "role": "Admin",
            "is_active": True,
        },
    )
    assert recreated.status_code == 201
    assert client.get("/api/users/me", headers=token).status_code == 401
    assert client.get("/api/users/", headers=token).status_code == 401
    assert (
        client.get("/api/users/", headers=login(client, "original")).status_code == 200
    )


@pytest.mark.parametrize(
    "claims",
    [
        {},
        {"sub": "original"},
        {"sub": "12345", "session_version": 0},
        {"sub": 2},
        {"sub": None},
        {"sub": []},
        {"session_version": None},
        {"session_version": "0"},
        {"session_version": True},
        {"session_version": -1},
        {"session_version": 0.0},
        {"session_version": []},
        {"exp": None},
    ],
)
def test_malformed_and_legacy_claims_are_rejected(accounts, claims):
    import jwt

    from app.core.config import settings

    client, _, _, token = accounts
    payload = jwt.decode(
        token["Authorization"].split()[1], options={"verify_signature": False}
    )
    if not claims:
        payload.pop("session_version")
    else:
        payload.update(claims)
    forged = jwt.encode(
        payload, settings.SECRET_KEY.get_secret_value(), algorithm="HS256"
    )
    assert (
        client.get(
            "/api/users/me", headers={"Authorization": f"Bearer {forged}"}
        ).status_code
        == 401
    )


def test_inconsistent_analyst_lead_cannot_create_tasks(accounts, engine):
    from app.database.models import Case, CaseUserLink

    client, admin, user, token = accounts
    assert (
        client.put(
            f"/api/users/{user['id']}", headers=admin, json={"role": "Analyst"}
        ).status_code
        == 200
    )
    with Session(engine) as db:
        case = Case(case_number="STALE", title="Historical lead", client_id=1)
        db.add(case)
        db.flush()
        case_id = case.id
        db.add(CaseUserLink(case_id=case_id, user_id=user["id"], is_lead=True))
        db.commit()
    assert client.get(f"/api/cases/{case_id}", headers=token).status_code == 200
    assert (
        client.post(
            "/api/tasks/",
            headers=token,
            json={"case_id": case_id, "title": "Denied", "description": "Denied"},
        ).status_code
        == 403
    )


def test_failed_role_change_keeps_lead_membership(accounts, engine):
    from app.database.models import Case, CaseUserLink

    client, admin, user, token = accounts
    with Session(engine) as db:
        case = Case(case_number="FAILED", title="Preserved", client_id=1)
        db.add(case)
        db.flush()
        case_id = case.id
        db.add(CaseUserLink(case_id=case_id, user_id=user["id"], is_lead=True))
        db.commit()
    assert (
        client.put(
            f"/api/users/{user['id']}",
            headers=admin,
            json={"role": "Analyst", "username": "admin"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/tasks/",
            headers=token,
            json={"case_id": case_id, "title": "Allowed", "description": "Allowed"},
        ).status_code
        == 200
    )


def test_login_racing_reset_never_gets_the_new_session_version(accounts, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from fastapi.testclient import TestClient

    from app.core import security

    client, admin, user, _ = accounts
    verified, release = Event(), Event()
    verify = security.verify_password

    def pause_after_verification(password, password_hash):
        valid = verify(password, password_hash)
        if password == PASSWORD:
            verified.set()
            assert release.wait(10)
        return valid

    monkeypatch.setattr(security, "verify_password", pause_after_verification)
    with ThreadPoolExecutor() as pool:
        pending = pool.submit(login, client, "original")
        try:
            assert verified.wait(10)
            # A separate TestClient portal models the second API process.
            reset = TestClient(app).put(
                f"/api/users/{user['id']}/password",
                headers=admin,
                json={"new_password": "reset-password"},
            )
            assert reset.status_code == 200
        finally:
            release.set()
        stale = pending.result(timeout=10)
    assert client.get("/api/users/me", headers=stale).status_code == 401
    assert (
        client.get(
            "/api/users/me", headers=login(client, "original", "reset-password")
        ).status_code
        == 200
    )


def test_failed_password_commit_preserves_credentials_and_sessions(accounts, engine):
    from sqlalchemy import event

    client, _, _, token = accounts

    def reject_password_update(
        connection, cursor, statement, parameters, context, executemany
    ):
        if statement.startswith("UPDATE") and "password_hash" in statement:
            raise RuntimeError("Injected database failure")

    event.listen(engine, "after_cursor_execute", reject_password_update)
    try:
        with pytest.raises(RuntimeError, match="Injected database failure"):
            client.put(
                "/api/users/me/password",
                headers=token,
                json={
                    "current_password": PASSWORD,
                    "new_password": "rejected-password",
                },
            )
    finally:
        event.remove(engine, "after_cursor_execute", reject_password_update)
    assert client.get("/api/users/me", headers=token).status_code == 200
    login(client, "original")
    assert (
        client.post(
            "/api/auth/login",
            data={"username": "original", "password": "rejected-password"},
        ).status_code
        == 401
    )
