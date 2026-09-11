"""Login fails closed while asynchronous shared storage is unavailable."""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from redis.exceptions import ConnectionError

from app.core.login_rate_limiting import RedisLoginRateLimiter, get_login_rate_limiter
from app.main import app
from app.services.auth_service import AuthService


@pytest.mark.asyncio
async def test_unavailable_storage_precedes_authentication_without_blocking(
    monkeypatch,
):
    started, release = asyncio.Event(), asyncio.Event()

    class UnavailableRedis:
        async def eval(self, *args):
            started.set()
            await release.wait()
            raise ConnectionError("private Redis credentials must not escape")

    def forbidden(*args, **kwargs):
        pytest.fail("Storage failure entered authentication")

    monkeypatch.setattr(AuthService, "authenticate_user", forbidden)
    app.dependency_overrides[get_login_rate_limiter] = lambda: RedisLoginRateLimiter(
        UnavailableRedis()
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as api:
        request = asyncio.create_task(
            api.post(
                "/api/auth/login", data={"username": "name", "password": "password"}
            )
        )
        try:
            await asyncio.wait_for(started.wait(), 3)
            assert (
                await asyncio.wait_for(api.get("/health/live"), 3)
            ).status_code == 200
            assert not request.done()
        finally:
            release.set()
            response = await request
        assert response.status_code == 503
        assert response.headers["Retry-After"] == "5"
        assert response.json() == {
            "detail": "Login is temporarily unavailable. Please retry shortly."
        }
