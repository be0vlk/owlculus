"""Public API contract tests for liveness and readiness health checks."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import SQLModel, create_engine

from app import main as main_module


@pytest.fixture(autouse=True)
def available_rate_limit_storage(monkeypatch):
    """Keep readiness tests focused unless they explicitly simulate Redis failure."""
    monkeypatch.setattr(
        main_module, "is_rate_limit_storage_ready", lambda: True, raising=False
    )


async def request_without_lifespan(path: str):
    """Issue a request without invoking the production application's lifespan."""
    async with AsyncClient(
        transport=ASGITransport(app=main_module.app), base_url="http://test"
    ) as client:
        return await client.get(path)


@pytest.mark.asyncio
async def test_liveness_is_healthy_without_touching_the_database(monkeypatch):
    """Liveness reports only process health and never opens a database connection."""

    class DatabaseMustNotBeUsed:
        def connect(self):
            raise AssertionError("liveness must not touch the database")

    monkeypatch.setattr(main_module, "engine", DatabaseMustNotBeUsed())

    response = await request_without_lifespan("/health/live")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_readiness_is_ready_after_schema_and_setup_initialization(
    engine, monkeypatch
):
    """Readiness succeeds once the database, schema, and setup check are ready."""
    monkeypatch.setattr(main_module, "engine", engine)
    monkeypatch.setattr(
        main_module.app.state, "setup_token_check_complete", True, raising=False
    )

    response = await request_without_lifespan("/health/ready")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {
        "status": "ready",
        "checks": {
            "database": "ok",
            "schema": "ok",
            "setup_token": "ok",
            "hunt_registry": "ok",
            "rate_limit_storage": "ok",
        },
    }


@pytest.mark.asyncio
async def test_readiness_waits_for_the_startup_setup_token_check(
    engine, tmp_path, monkeypatch
):
    """A usable schema is insufficient until startup setup initialization finishes."""
    blocked_parent = tmp_path / "not-a-directory"
    blocked_parent.write_text("blocks setup-token storage")
    monkeypatch.setattr(main_module, "engine", engine)
    monkeypatch.setattr(
        "app.core.setup.SETUP_TOKEN_FILE", blocked_parent / ".setup_token"
    )
    monkeypatch.setattr(
        main_module.app.state, "setup_token_check_complete", False, raising=False
    )

    response = await request_without_lifespan("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {
            "database": "ok",
            "schema": "ok",
            "setup_token": "incomplete",
            "hunt_registry": "ok",
            "rate_limit_storage": "ok",
        },
    }


@pytest.mark.asyncio
async def test_readiness_reports_a_missing_schema(monkeypatch):
    """A reachable database without initialized tables is not ready."""
    monkeypatch.setattr(main_module, "engine", create_engine("sqlite://"))
    monkeypatch.setattr(
        main_module.app.state, "setup_token_check_complete", False, raising=False
    )

    response = await request_without_lifespan("/health/ready")

    assert response.status_code == 503
    assert response.json()["checks"] == {
        "database": "ok",
        "schema": "missing",
        "setup_token": "incomplete",
        "hunt_registry": "incomplete",
        "rate_limit_storage": "ok",
    }


@pytest.mark.asyncio
async def test_readiness_reports_an_unreachable_database(monkeypatch):
    """Dependency failure is a safe JSON response rather than an API exception."""

    class UnreachableDatabase:
        def connect(self):
            raise SQLAlchemyError("contains internal connection details")

    monkeypatch.setattr(main_module, "engine", UnreachableDatabase())
    monkeypatch.setattr(
        main_module.app.state, "setup_token_check_complete", True, raising=False
    )

    response = await request_without_lifespan("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {
            "database": "unavailable",
            "schema": "unavailable",
            "setup_token": "ok",
            "hunt_registry": "incomplete",
            "rate_limit_storage": "ok",
        },
    }
    assert "internal connection details" not in response.text


@pytest.mark.asyncio
async def test_health_alias_has_the_readiness_contract(engine, monkeypatch):
    """The legacy-friendly health path is an exact readiness alias."""
    monkeypatch.setattr(main_module, "engine", engine)
    monkeypatch.setattr(
        main_module.app.state, "setup_token_check_complete", True, raising=False
    )

    response = await request_without_lifespan("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {
            "database": "ok",
            "schema": "ok",
            "setup_token": "ok",
            "hunt_registry": "ok",
            "rate_limit_storage": "ok",
        },
    }


@pytest.mark.asyncio
async def test_startup_marks_the_setup_token_check_complete(
    engine, tmp_path, monkeypatch
):
    """Successful application startup makes the setup check ready."""
    monkeypatch.setattr(main_module, "engine", engine)
    monkeypatch.setattr(
        "app.core.setup.SETUP_TOKEN_FILE", tmp_path / "setup" / ".setup_token"
    )

    async with main_module.lifespan(main_module.app):
        assert main_module.app.state.setup_token_check_complete is True


@pytest.mark.asyncio
async def test_startup_syncs_hunt_definitions_once(engine, tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "engine", engine)
    monkeypatch.setattr(
        "app.core.setup.SETUP_TOKEN_FILE", tmp_path / "setup" / ".setup_token"
    )
    sync_calls = []
    monkeypatch.setattr(
        main_module.shipped_hunt_registry,
        "sync",
        lambda session: sync_calls.append(session),
    )

    async with main_module.lifespan(main_module.app):
        pass

    assert len(sync_calls) == 1


@pytest.mark.asyncio
async def test_process_stays_live_and_becomes_ready_after_late_schema_initialization(
    tmp_path, monkeypatch
):
    """Startup exposes health checks while waiting for database initialization."""
    database_engine = create_engine("sqlite://")
    monkeypatch.setattr(main_module, "engine", database_engine)
    monkeypatch.setattr(
        "app.core.setup.SETUP_TOKEN_FILE", tmp_path / "setup" / ".setup_token"
    )

    async with main_module.lifespan(main_module.app):
        liveness = await request_without_lifespan("/health/live")
        waiting = await request_without_lifespan("/health/ready")

        assert liveness.status_code == 200
        assert waiting.status_code == 503
        assert waiting.json()["checks"] == {
            "database": "ok",
            "schema": "missing",
            "setup_token": "incomplete",
            "hunt_registry": "incomplete",
            "rate_limit_storage": "ok",
        }

        SQLModel.metadata.create_all(database_engine)
        ready = await request_without_lifespan("/health/ready")

        assert ready.status_code == 200
        assert ready.json()["checks"] == {
            "database": "ok",
            "schema": "ok",
            "setup_token": "ok",
            "hunt_registry": "ok",
            "rate_limit_storage": "ok",
        }


@pytest.mark.asyncio
async def test_readiness_reports_unavailable_rate_limit_storage(engine, monkeypatch):
    """Readiness fails closed when bootstrap throttling cannot be enforced."""
    monkeypatch.setattr(main_module, "engine", engine)
    monkeypatch.setattr(
        main_module.app.state, "setup_token_check_complete", True, raising=False
    )
    monkeypatch.setattr(main_module, "is_rate_limit_storage_ready", lambda: False)

    response = await request_without_lifespan("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {
            "database": "ok",
            "schema": "ok",
            "setup_token": "ok",
            "hunt_registry": "ok",
            "rate_limit_storage": "unavailable",
        },
    }
