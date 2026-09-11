"""Two real Uvicorn workers sharing disposable PostgreSQL, Redis and setup files."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import httpx
from sqlmodel import SQLModel

from tests.executions.conftest import eventually, free_port


def test_two_workers_share_setup_revocation_invitations_and_limits(execution_system):
    system = execution_system
    # This fixture's database is disposable and unique to this test.
    with system.engine.begin() as db:
        for table in reversed(SQLModel.metadata.sorted_tables):
            db.execute(table.delete())
    system.env.update(
        OWLCULUS_SETUP_DATA_DIR=str(system.root / "setup"),
        LOGIN_ACCOUNT_MAX_ATTEMPTS="3",
        LOGIN_IP_MAX_ATTEMPTS="100",
    )
    port = free_port()
    system.start(
        "-m",
        "uvicorn",
        "tests.executions.multiprocess_api:create_app",
        "--factory",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--workers",
        "2",
        "--timeout-keep-alive",
        "60",
    )
    base_url = f"http://127.0.0.1:{port}"
    clients = {}

    def collect_workers():
        client = httpx.Client(base_url=base_url, timeout=5)
        try:
            response = client.get("/health/ready")
            if response.status_code == 200:
                pid = response.headers["X-Test-Process"]
                if pid not in clients:
                    clients[pid] = client
                    return len(clients) == 2
        except httpx.HTTPError:
            pass
        client.close()
        return False

    try:
        eventually(collect_workers)
        first, second = clients.values()
        token_file = system.root / "setup" / ".setup_token"
        setup_token = token_file.read_text()
        assert token_file.stat().st_mode & 0o777 == 0o600
        for client in clients.values():
            assert client.get("/api/auth/setup-status").json()["setup_required"]
        payload = {
            "username": "firstadmin",
            "email": "first@example.com",
            "password": "first-admin-password",
            "setup_token": setup_token,
        }
        assert first.post("/api/users/", json=payload).status_code == 201
        assert not token_file.exists()
        assert not second.get("/api/auth/setup-status").json()["setup_required"]
        assert (
            second.post(
                "/api/users/", json={**payload, "username": "secondadmin"}
            ).status_code
            == 401
        )
        login = second.post(
            "/api/auth/login",
            data={
                "username": "firstadmin",
                "password": "first-admin-password",
            },
        )
        assert login.status_code == 200
        auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
        for client in clients.values():
            assert client.get("/api/users/me", headers=auth).status_code == 200
        invite = first.post(
            "/api/invites/", headers=auth, json={"role": "Investigator"}
        )
        assert invite.status_code == 201
        registration = {"token": invite.json()["token"], "password": "invite-password"}
        barrier = Barrier(2)

        def register(client, index):
            barrier.wait(timeout=5)
            return client.post(
                "/api/invites/register",
                json={
                    **registration,
                    "username": f"invited{index}",
                    "email": f"invited{index}@example.com",
                },
            )

        with ThreadPoolExecutor(2) as workers:
            attempts = [
                workers.submit(register, client, i)
                for i, client in enumerate(clients.values())
            ]
            statuses = sorted(attempt.result().status_code for attempt in attempts)
        assert statuses == [201, 422]
        assert (
            first.put(
                "/api/users/me/password",
                headers=auth,
                json={
                    "current_password": "first-admin-password",
                    "new_password": "changed-admin-password",
                },
            ).status_code
            == 200
        )
        assert second.get("/api/users/me", headers=auth).status_code == 401
        # Same unknown account consumes one shared three-attempt budget across PIDs.
        for client in (first, second, first):
            assert (
                client.post(
                    "/api/auth/login",
                    data={
                        "username": "missing-account",
                        "password": "invalid-password",
                    },
                ).status_code
                == 401
            )
        assert (
            second.post(
                "/api/auth/login",
                data={
                    "username": "missing-account",
                    "password": "invalid-password",
                },
            ).status_code
            == 429
        )
        assert {
            client.get("/health/live").headers["X-Test-Process"]
            for client in clients.values()
        } == set(clients)
    finally:
        for client in clients.values():
            client.close()


def test_database_lock_preserves_liveness_readiness_and_observation(execution_system):
    from sqlalchemy import text
    from websockets.sync.client import connect

    from tests.executions.test_execution_system import submit
    from tests.executions.test_observation import receive, stream

    system = execution_system
    system.env.update(
        API_DATABASE_CONCURRENCY="1", DATABASE_POOL_SIZE="1", DATABASE_MAX_OVERFLOW="0"
    )
    _, client = system.api()
    accepted = submit(client, system)
    socket_url = stream(client, accepted)
    # Hold a real PostgreSQL relation lock on an independent disposable connection.
    with system.engine.connect() as lock:
        lock.execute(text("LOCK TABLE client IN ACCESS EXCLUSIVE MODE"))
        with ThreadPoolExecutor(1) as requests:
            blocked = requests.submit(client.get, "/api/clients/")
            try:

                def waiting_on_lock():
                    with system.engine.connect() as observer:
                        return observer.execute(text("""
                            SELECT count(*) FROM pg_stat_activity
                            WHERE datname = current_database() AND wait_event_type = 'Lock'
                              AND query LIKE 'SELECT client.%'
                        """)).scalar() == 1

                eventually(waiting_on_lock, timeout=3)
                with httpx.Client(
                    base_url=str(client.base_url), timeout=3
                ) as independent:
                    assert independent.get("/health/live").status_code == 200
                    assert independent.get("/health/ready").status_code == 200
                    assert independent.get("/api/users/me").status_code == 503
                with connect(socket_url, open_timeout=3) as socket:
                    snapshot = receive(socket)
                    assert snapshot["execution_id"] == accepted["id"]
                    assert snapshot["state"]["status"] == "queued"
                assert not blocked.done()
            finally:
                lock.rollback()
            assert blocked.result().status_code == 200
