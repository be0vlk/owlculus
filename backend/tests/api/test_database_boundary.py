"""Hold database I/O until independent same-process HTTP work completes."""

import asyncio
from threading import BoundedSemaphore, Event, get_ident

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlmodel import Session

from app import main
from app.core import database_boundary, security
from app.database import connection, models


@pytest.fixture
def database_api(engine, monkeypatch):
    monkeypatch.setattr(connection, "engine", engine)
    with Session(engine) as db:
        user = models.User(
            username="boundary",
            email="boundary@example.com",
            password_hash="unused",
            role="Admin",
            is_active=True,
            is_superadmin=True,
        )
        db.add(user)
        db.commit()
        token = security.create_access_token(
            {"sub": user.auth_identity, "session_version": user.session_version}
        )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,statement",
    [
        ("/api/clients/", "FROM client"),
        ("/api/plugins/executions/case/1", "FROM user"),
        ("/api/cases/", "FROM case"),
        ("/api/evidence/1", "FROM evidence"),
        ("/api/users/me", "FROM user"),
    ],
)
async def test_database_wait_allows_other_requests_and_owns_session(
    engine,
    database_api,
    monkeypatch,
    path,
    statement,
):
    entered, release, closed = Event(), Event(), Event()
    owner_threads = []

    class OwnedSession(Session):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.owner = get_ident()

        def close(self):
            assert get_ident() == self.owner
            owner_threads.append(self.owner)
            super().close()
            closed.set()

    monkeypatch.setattr(connection, "Session", OwnedSession)

    def hold(conn, cursor, sql, params, context, many):
        if statement in sql.replace('"', "") and not entered.is_set():
            entered.set()
            assert release.wait(10), "test must release blocked database call"

    event.listen(engine, "before_cursor_execute", hold)
    async with AsyncClient(
        transport=ASGITransport(app=main.app), base_url="http://test"
    ) as client:
        blocked = asyncio.create_task(client.get(path, headers=database_api))
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            for other_path in ("/health/live", "/", "/api/users/me"):
                response = await asyncio.wait_for(
                    client.get(other_path, headers=database_api), 3
                )
                assert response.status_code == 200
            assert not blocked.done()
        finally:
            release.set()
            response = await blocked
            event.remove(engine, "before_cursor_execute", hold)
    assert response.status_code in (200, 404)
    assert closed.is_set()
    assert owner_threads and get_ident() not in owner_threads


@pytest.mark.asyncio
async def test_saturation_and_cancellation_retain_session_until_database_finishes(
    engine,
    database_api,
    monkeypatch,
):
    entered, release, closed = Event(), Event(), Event()
    monkeypatch.setattr(database_boundary, "_request_slots", BoundedSemaphore(1))

    class OwnedSession(Session):
        def close(self):
            super().close()
            closed.set()

    monkeypatch.setattr(connection, "Session", OwnedSession)

    def hold(*args):
        entered.set()
        assert release.wait(10)

    event.listen(engine, "before_cursor_execute", hold)
    async with AsyncClient(
        transport=ASGITransport(app=main.app), base_url="http://test"
    ) as client:
        blocked = asyncio.create_task(client.get("/api/clients/", headers=database_api))
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            blocked.cancel()
            assert (
                await client.get("/api/clients/", headers=database_api)
            ).status_code == 503
            assert (await client.get("/health/live")).status_code == 200
            assert not closed.is_set()
        finally:
            release.set()
            await asyncio.gather(blocked, return_exceptions=True)
            event.remove(engine, "before_cursor_execute", hold)
        assert closed.is_set()
        assert (
            await client.get("/api/clients/", headers=database_api)
        ).status_code == 200


@pytest.mark.asyncio
async def test_database_failure_translates_and_closes_session(
    database_api, monkeypatch
):
    closed = Event()

    class FailingSession(Session):
        def exec(self, *args, **kwargs):
            raise OperationalError("hidden query", {}, Exception("hidden details"))

        def close(self):
            super().close()
            closed.set()

    monkeypatch.setattr(connection, "Session", FailingSession)
    async with AsyncClient(
        transport=ASGITransport(app=main.app), base_url="http://test"
    ) as client:
        response = await client.get("/api/clients/", headers=database_api)
    assert response.status_code == 503
    assert "hidden" not in response.text
    assert closed.is_set()


@pytest.mark.asyncio
async def test_delayed_readiness_is_bounded_and_coalesced(monkeypatch):
    entered, release = Event(), Event()
    calls = []

    def delayed():
        calls.append(1)
        entered.set()
        assert release.wait(10)
        return True, {"database": "ok"}

    monkeypatch.setattr(main, "_readiness_status", delayed)
    monkeypatch.setattr(main, "READINESS_TIMEOUT_SECONDS", 0.05)
    async with AsyncClient(
        transport=ASGITransport(app=main.app), base_url="http://test"
    ) as client:
        probe = asyncio.create_task(client.get("/health/ready"))
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            assert (await client.get("/health/live")).status_code == 200
            assert (await probe).json() == {
                "status": "not_ready",
                "checks": {"database": "delayed"},
            }
            assert (await client.get("/health/ready")).status_code == 503
            assert len(calls) == 1
        finally:
            release.set()
            await asyncio.wrap_future(main.app.state.readiness_work)
