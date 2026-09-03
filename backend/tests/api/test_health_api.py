"""Public API contract tests for liveness and readiness health checks."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import create_engine

from app import main as main_module


async def get(path: str):
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

    response = await get("/health/live")

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

    response = await get("/health/ready")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {
        "status": "ready",
        "checks": {"database": "ok", "schema": "ok", "setup_token": "ok"},
    }


@pytest.mark.asyncio
async def test_readiness_waits_for_the_startup_setup_token_check(engine, monkeypatch):
    """A usable schema is insufficient until startup setup initialization finishes."""
    monkeypatch.setattr(main_module, "engine", engine)
    monkeypatch.setattr(
        main_module.app.state, "setup_token_check_complete", False, raising=False
    )

    response = await get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {
            "database": "ok",
            "schema": "ok",
            "setup_token": "incomplete",
        },
    }


@pytest.mark.asyncio
async def test_readiness_reports_a_missing_schema(monkeypatch):
    """A reachable database without initialized tables is not ready."""
    monkeypatch.setattr(main_module, "engine", create_engine("sqlite://"))
    monkeypatch.setattr(
        main_module.app.state, "setup_token_check_complete", False, raising=False
    )

    response = await get("/health/ready")

    assert response.status_code == 503
    assert response.json()["checks"] == {
        "database": "ok",
        "schema": "missing",
        "setup_token": "incomplete",
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

    response = await get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {
            "database": "unavailable",
            "schema": "unavailable",
            "setup_token": "ok",
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

    response = await get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"database": "ok", "schema": "ok", "setup_token": "ok"},
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
