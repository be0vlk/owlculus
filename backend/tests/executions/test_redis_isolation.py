"""Capacity isolation and maintenance rehearsal against disposable Redis stores."""

import asyncio
import json
import subprocess

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from app.core.config import settings
from app.core.login_rate_limiting import RedisLoginRateLimiter
from app.core.rate_limiting import RedisClientRateLimiter
from app.core.redis_health import storage_ready
from tests.executions.conftest import eventually
from tests.executions.test_login_limits import login_app


def exhaust(redis):
    # Reject allocations without allocating host memory. PING must still work.
    redis.config_set("maxmemory", 1)
    assert redis.ping()


@pytest.mark.asyncio
async def test_execution_pressure_preserves_login_bootstrap_and_auth_failure_is_closed(
    execution_system, monkeypatch
):
    system = execution_system
    monkeypatch.setattr(settings, "AUTH_REDIS_URL", system.env["AUTH_REDIS_URL"])
    execution = Redis.from_url(system.env["REDIS_URL"])
    auth = Redis.from_url(system.env["AUTH_REDIS_URL"])
    exhaust(execution)
    assert not storage_ready(execution, "broker")
    assert not storage_ready(execution, "events")
    assert storage_ready(auth, "authentication")
    async with AsyncRedis.from_url(system.env["AUTH_REDIS_URL"]) as shared:
        bootstrap = RedisClientRateLimiter(shared, max_attempts=1, window_seconds=60)
        assert await bootstrap.allow("198.51.100.3")
        assert not await bootstrap.allow("198.51.100.3")
        async with AsyncClient(
            transport=ASGITransport(app=login_app(system)), base_url="http://test"
        ) as api:
            credentials = {"username": "acceptance", "password": "acceptance-password"}
            assert (await api.post("/auth/login", data=credentials)).status_code == 200
            exhaust(auth)
            assert not storage_ready(auth, "authentication")
            with monkeypatch.context() as blocked:

                def forbidden(*args, **kwargs):
                    raise AssertionError("verification must follow shared admission")

                blocked.setattr("app.core.security.verify_password", forbidden)
                response = await api.post("/auth/login", data=credentials)
                assert response.status_code == 503
                assert "redis://" not in response.text
            auth.config_set("maxmemory", "256mb")
            assert storage_ready(auth, "authentication")
            assert (await api.post("/auth/login", data=credentials)).status_code == 200
    execution.config_set("maxmemory", "256mb")
    assert storage_ready(execution, "broker")
    assert storage_ready(execution, "events")
    assert not execution.keys("owlculus:health:*")
    assert not auth.keys("owlculus:health:*")


def test_queued_and_running_work_and_results_survive_execution_pressure(
    execution_system,
):
    system = execution_system
    system.env["EXECUTION_REDISPATCH_SECONDS"] = "1"
    _, api = system.api()
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    running = api.post(
        "/api/plugins/AcceptancePlugin/execute",
        json={"case_id": system.case_id, "barrier": "release-pressure"},
    ).json()
    eventually(lambda: (system.root / "provider-starts").exists())
    redis = Redis.from_url(system.env["REDIS_URL"])
    exhaust(redis)
    assert api.get("/health/ready").status_code == 200
    assert api.get("/health/execution").json()["checks"] == {
        "broker": "unavailable",
        "events": "unavailable",
    }
    token = api.post(
        "/api/auth/websocket-token",
        json={"execution_id": running["id"], "kind": "plugin"},
    )
    assert token.status_code == 503
    queued = api.post(
        "/api/plugins/AcceptancePlugin/execute", json={"case_id": system.case_id}
    ).json()
    assert api.get(queued["links"]["detail"]).json()["status"] == "queued"
    (system.root / "release-pressure").touch()
    eventually(
        lambda: api.get(running["links"]["detail"]).json()["status"] == "completed"
    )
    results = api.get(running["links"]["results"]).json()
    assert results["items"]
    redis.config_set("maxmemory", "256mb")
    eventually(
        lambda: api.get(queued["links"]["detail"]).json()["status"] == "completed"
    )
    assert api.get(running["links"]["results"]).json() == results
    assert api.get("/health/execution").status_code == 200
    assert (
        api.post(
            "/api/auth/websocket-token",
            json={"execution_id": running["id"], "kind": "plugin"},
        ).status_code
        == 200
    )


@pytest.mark.asyncio
async def test_maintenance_waits_for_old_budgets_and_preserves_persisted_queue(
    execution_system, monkeypatch
):
    system = execution_system
    old = Redis.from_url(system.env["REDIS_URL"])
    monkeypatch.setattr(settings, "LOGIN_LIMIT_WINDOW_SECONDS", 2)
    monkeypatch.setattr(settings, "LOGIN_ACCOUNT_MAX_ATTEMPTS", 1)
    async with AsyncRedis.from_url(system.env["REDIS_URL"]) as shared:
        limiter = RedisLoginRateLimiter(shared)
        await limiter.check("198.51.100.4", "acceptance")
        with pytest.raises(HTTPException) as limited:
            await limiter.check("198.51.100.4", "acceptance")
        assert limited.value.status_code == 429
        assert await RedisClientRateLimiter(
            shared, max_attempts=1, window_seconds=2
        ).allow("198.51.100.4")
    old.lpush("migration-fixture-queue", "retained-work")
    await asyncio.to_thread(
        subprocess.run,
        ["docker", "restart", system.redis_container],
        check=True,
        capture_output=True,
    )
    # Docker can assign a new ephemeral published port on restart.
    info = json.loads(
        await asyncio.to_thread(
            subprocess.check_output, ["docker", "inspect", system.redis_container]
        )
    )[0]
    port = info["NetworkSettings"]["Ports"]["6379/tcp"][0]["HostPort"]
    old.close()
    old = Redis(host="127.0.0.1", port=int(port))

    def restarted():
        from redis.exceptions import RedisError

        try:
            return old.ping()
        except RedisError:
            return False

    eventually(restarted)
    assert old.lindex("migration-fixture-queue", 0) == b"retained-work"
    eventually(
        lambda: not list(old.scan_iter("owlculus:login-rate-limit:*"))
        and not list(old.scan_iter("owlculus:bootstrap-rate-limit:*"))
    )
    async with AsyncRedis.from_url(system.env["AUTH_REDIS_URL"]) as shared:
        await RedisLoginRateLimiter(shared).check("198.51.100.4", "acceptance")
    assert old.rpop("migration-fixture-queue") == b"retained-work"


@pytest.mark.asyncio
async def test_bootstrap_http_uses_auth_store_under_pressure(
    execution_system, engine, monkeypatch, tmp_path
):
    from fastapi import FastAPI
    from sqlmodel import Session

    from app.api.users import router
    from app.core import setup
    from app.core.exception_handler import handle_domain_exception
    from app.core.exceptions import BaseException as DomainException
    from app.database.connection import get_db

    monkeypatch.setattr(
        settings, "AUTH_REDIS_URL", execution_system.env["AUTH_REDIS_URL"]
    )
    monkeypatch.setattr(setup, "SETUP_TOKEN_FILE", tmp_path / "bootstrap-token")
    token = setup.generate_setup_token()
    api = FastAPI()
    api.include_router(router, prefix="/users")
    api.add_exception_handler(DomainException, handle_domain_exception)

    def database():
        with Session(engine) as db:
            yield db

    api.dependency_overrides[get_db] = database
    execution = Redis.from_url(execution_system.env["REDIS_URL"])
    auth = Redis.from_url(execution_system.env["AUTH_REDIS_URL"])
    exhaust(execution)
    payload = {
        "username": "first_admin",
        "email": "first@example.com",
        "password": "StrongPassword123!",
        "setup_token": token,
    }
    async with AsyncClient(
        transport=ASGITransport(app=api), base_url="http://test"
    ) as client:
        # Charge a real attempt first; pressure must also reject already-used keys.
        assert (
            await client.post("/users/", json={**payload, "setup_token": "wrong"})
        ).status_code == 403
        exhaust(auth)
        rejected = await client.post("/users/", json=payload)
        assert rejected.status_code == 503
        assert setup.validate_setup_token(token)
        auth.config_set("maxmemory", "256mb")
        accepted = await client.post("/users/", json=payload)
        assert accepted.status_code == 201, accepted.text
        assert accepted.json()["role"] == "Admin"
    await api.state.bootstrap_rate_limiter.redis_client.aclose()
