"""Account cutover and concurrent resets on disposable PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import text
from sqlmodel import Session

from app.core.security import create_access_token
from app.database.init_db import initialize_database
from app.database.models import Evidence, Task, User
from app.database.upgrade_authorization import upgrade
from tests.executions.conftest import eventually


def test_existing_account_upgrade_is_repeatable_and_preserves_login(execution_system):
    system = execution_system
    evidence_file = system.root / "preserved-evidence.bin"
    evidence_file.write_bytes(b"Investigation contents\x00\r\n")
    with Session(system.engine) as db:
        evidence = Evidence(
            case_id=system.case_id,
            title="Preserved evidence",
            evidence_type="file",
            content=str(evidence_file),
            created_by_id=system.user_id,
        )
        task = Task(
            case_id=system.case_id,
            title="Completed work",
            description="Preserve history",
            assigned_by_id=system.user_id,
            completed_by_id=system.user_id,
            status="Completed",
        )
        db.add_all([evidence, task])
        db.commit()
        evidence_id, task_id = evidence.id, task.id
    with system.engine.begin() as connection:
        connection.execute(text("UPDATE \"user\" SET role = 'Analyst'"))
        connection.execute(text("UPDATE caseuserlink SET is_lead = true"))
        # Reproduce the previous schema without recreating accounts or relationships.
        connection.execute(text('ALTER TABLE "user" DROP COLUMN auth_identity'))
        connection.execute(text('ALTER TABLE "user" DROP COLUMN session_version'))
    upgrade(system.engine)
    with Session(system.engine) as db:
        user = db.get(User, system.user_id)
        identity = user.auth_identity
        assert user.session_version == 0
    initialize_database(system.engine)
    upgrade(system.engine)
    with Session(system.engine) as db:
        assert db.get(User, system.user_id).auth_identity == identity
        evidence = db.get(Evidence, evidence_id)
        task = db.get(Task, task_id)
        assert evidence.content == str(evidence_file)
        assert evidence.created_by_id == system.user_id
        assert task.description == "Preserve history"
        assert task.status == "Completed"
        assert task.completed_by_id == system.user_id
        assert evidence_file.read_bytes() == b"Investigation contents\x00\r\n"
    _, client = system.api()
    legacy = create_access_token({"sub": "acceptance"})
    assert (
        client.get(
            "/api/users/me", headers={"Authorization": "Bearer " + legacy}
        ).status_code
        == 401
    )
    login = client.post(
        "/api/auth/login",
        data={"username": "acceptance", "password": "acceptance-password"},
    )
    assert login.status_code == 200
    client.headers["Authorization"] = "Bearer " + login.json()["access_token"]
    me = client.get("/api/users/me")
    assert me.json()["id"] == system.user_id
    case = client.get(f"/api/cases/{system.case_id}")
    assert case.status_code == 200
    assert case.json()["users"][0]["is_lead"] is False
    assert (
        client.post(
            "/api/tasks/",
            json={
                "case_id": system.case_id,
                "title": "Denied",
                "description": "Denied",
            },
        ).status_code
        == 403
    )
    with system.engine.connect() as connection:
        columns = {
            row[0]: row[1]
            for row in connection.execute(
                text(
                    "SELECT column_name, is_nullable FROM information_schema.columns WHERE table_name = 'user'"
                )
            )
        }
        assert columns["auth_identity"] == columns["session_version"] == "NO"


def test_concurrent_resets_increment_without_lost_updates(execution_system):
    system = execution_system
    with Session(system.engine) as db:
        db.get(User, system.user_id).role = "Admin"
        db.commit()
    _, first = system.api()
    _, second = system.api()
    with ThreadPoolExecutor(2) as pool:
        with system.engine.begin() as lock:
            lock.execute(
                text('SELECT id FROM "user" WHERE id = :id FOR UPDATE'),
                {"id": system.user_id},
            )
            pending = [
                pool.submit(
                    client.put,
                    f"/api/users/{system.user_id}/password",
                    json={"new_password": password},
                )
                for client, password in [(first, "reset-one"), (second, "reset-two")]
            ]

            def both_waiting():
                with system.engine.connect() as connection:
                    return (
                        connection.execute(
                            text(
                                "SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock' AND query LIKE 'UPDATE%user%'"
                            )
                        ).scalar()
                        == 2
                    )

            eventually(both_waiting, timeout=4)
        assert [request.result().status_code for request in pending] == [200, 200]
    with Session(system.engine) as db:
        assert db.get(User, system.user_id).session_version == 2
    assert first.get("/api/users/me").status_code == 401
    responses = [
        second.post(
            "/api/auth/login", data={"username": "acceptance", "password": password}
        )
        for password in ["reset-one", "reset-two"]
    ]
    assert sorted(response.status_code for response in responses) == [200, 401]
