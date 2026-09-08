"""Login admission through HTTP against isolated shared PostgreSQL and Redis."""

import asyncio

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlmodel import Session

from app.api.auth import router
from app.core.config import settings
from app.core.exception_handler import handle_domain_exception
from app.core.exceptions import BaseException as DomainException
from app.database.connection import get_db


def login_app(system):
    api = FastAPI()
    api.include_router(router, prefix="/auth")
    api.add_exception_handler(DomainException, handle_domain_exception)

    def database():
        with Session(system.engine) as db:
            yield db

    api.dependency_overrides[get_db] = database
    return api


@pytest.mark.asyncio
@pytest.mark.parametrize("budget", ["account", "ip"])
async def test_shared_budget_precedes_verification(
    execution_system, monkeypatch, budget
):
    system = execution_system
    monkeypatch.setattr(settings, "REDIS_URL", system.env["REDIS_URL"])
    monkeypatch.setattr(
        settings, "LOGIN_ACCOUNT_MAX_ATTEMPTS", 2 if budget == "account" else 30
    )
    monkeypatch.setattr(settings, "LOGIN_IP_MAX_ATTEMPTS", 2 if budget == "ip" else 30)
    clients = [
        AsyncClient(
            transport=ASGITransport(
                app=login_app(system),
                client=(f"198.51.100.{i if budget == 'account' else 1}", 1234),
            ),
            base_url="http://test",
        )
        for i in range(8)
    ]
    try:
        responses = await asyncio.gather(
            *[
                client.post(
                    "/auth/login",
                    data={"username": "acceptance", "password": "acceptance-password"},
                )
                for client in clients
            ]
        )
        assert sorted(r.status_code for r in responses) == [
            200,
            200,
            429,
            429,
            429,
            429,
            429,
            429,
        ]
        assert all(
            1 <= int(r.headers["Retry-After"]) <= 300
            for r in responses
            if r.status_code == 429
        )
        async with AsyncClient(
            transport=ASGITransport(
                app=login_app(system), client=("198.51.100.1", 1234)
            ),
            base_url="http://test",
        ) as restarted:
            response = await restarted.post(
                "/auth/login",
                data={"username": "acceptance", "password": "acceptance-password"},
            )
            assert response.status_code == 429
        async with Redis.from_url(system.env["REDIS_URL"]) as redis:
            assert not await redis.keys("owlculus:bootstrap-rate-limit:*")
    finally:
        for client in clients:
            await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("account_state", ["active", "inactive", "missing"])
async def test_account_exhaustion_and_expiry(
    execution_system, monkeypatch, account_state
):
    from app.core import security
    from app.database.models import User

    system = execution_system
    monkeypatch.setattr(settings, "REDIS_URL", system.env["REDIS_URL"])
    monkeypatch.setattr(settings, "LOGIN_ACCOUNT_MAX_ATTEMPTS", 1)
    monkeypatch.setattr(settings, "LOGIN_LIMIT_WINDOW_SECONDS", 1)
    if account_state == "inactive":
        with Session(system.engine) as db:
            user = db.get(User, system.user_id)
            user.is_active = False
            db.add(user)
            db.commit()
    username = "absent" if account_state == "missing" else "acceptance"
    async with AsyncClient(
        transport=ASGITransport(app=login_app(system)), base_url="http://test"
    ) as api:
        data = {"username": username, "password": "wrong"}
        assert (await api.post("/auth/login", data=data)).status_code == 401
        with monkeypatch.context() as blocked:

            def forbidden(*args, **kwargs):
                pytest.fail(
                    "Rejected login entered account lookup/password verification"
                )

            blocked.setattr(Session, "exec", forbidden)
            blocked.setattr(security, "verify_password", forbidden)
            rejected = await api.post("/auth/login", data=data)
            assert rejected.status_code == 429
            assert rejected.headers["Retry-After"] == "1"
        await asyncio.sleep(1.05)
        recovered = await api.post(
            "/auth/login", data={**data, "password": "acceptance-password"}
        )
        assert recovered.status_code == (200 if account_state == "active" else 401)


@pytest.mark.asyncio
async def test_ip_budget_and_exact_username_semantics(execution_system, monkeypatch):
    system = execution_system
    monkeypatch.setattr(settings, "REDIS_URL", system.env["REDIS_URL"])
    monkeypatch.setattr(settings, "LOGIN_IP_MAX_ATTEMPTS", 3)
    monkeypatch.setattr(settings, "LOGIN_ACCOUNT_MAX_ATTEMPTS", 1)
    async with AsyncClient(
        transport=ASGITransport(app=login_app(system), client=("198.51.100.1", 1)),
        base_url="http://test",
    ) as api:
        for username in ["missing", "Missing", " missing"]:
            assert (
                await api.post(
                    "/auth/login", data={"username": username, "password": "wrong"}
                )
            ).status_code == 401
        response = await api.post(
            "/auth/login",
            data={"username": "acceptance", "password": "acceptance-password"},
        )
        assert response.status_code == 429
    # IP rejection did not consume the previously untouched account budget.
    async with AsyncClient(
        transport=ASGITransport(app=login_app(system), client=("198.51.100.2", 1)),
        base_url="http://test",
    ) as api:
        response = await api.post(
            "/auth/login",
            data={"username": "acceptance", "password": "acceptance-password"},
        )
        assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("trusted", [False, True])
async def test_proxy_identity_cannot_be_chosen_by_untrusted_peer(
    execution_system, monkeypatch, trusted
):
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

    system = execution_system
    monkeypatch.setattr(settings, "REDIS_URL", system.env["REDIS_URL"])
    monkeypatch.setattr(settings, "LOGIN_IP_MAX_ATTEMPTS", 1)
    monkeypatch.setattr(settings, "FORWARDED_ALLOW_IPS", "172.29.0.254")
    peer = "172.29.0.254" if trusted else "198.51.100.10"
    api = ProxyHeadersMiddleware(
        login_app(system), trusted_hosts=settings.FORWARDED_ALLOW_IPS
    )
    async with AsyncClient(
        transport=ASGITransport(app=api, client=(peer, 1)), base_url="http://test"
    ) as client:
        responses = [
            await client.post(
                "/auth/login",
                data={"username": f"missing{i}", "password": "wrong"},
                headers={
                    "X-Forwarded-For": f"203.0.113.{i}",
                    "X-Real-IP": f"203.0.113.{i}",
                },
            )
            for i in range(2)
        ]
        assert [r.status_code for r in responses] == (
            [401, 401] if trusted else [401, 429]
        )
