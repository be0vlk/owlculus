"""API middleware tests for trusted request context."""

import pytest
from app.core.config import settings
from app.core.logging import get_security_logger
from app.main import request_info_middleware
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from loguru import logger
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("peer_address", "trusted_proxies", "headers", "expected_address"),
    [
        (
            "198.51.100.20",
            "127.0.0.1,::1",
            {"X-Forwarded-For": "203.0.113.80"},
            "198.51.100.20",
        ),
        (
            "192.0.2.10",
            "192.0.2.10",
            {"X-Forwarded-For": "203.0.113.80"},
            "203.0.113.80",
        ),
    ],
    ids=["untrusted-peer", "trusted-proxy"],
)
async def test_security_logs_use_the_trusted_client_address(
    monkeypatch,
    peer_address: str,
    trusted_proxies: str,
    headers: dict[str, str],
    expected_address: str,
):
    """Request context exposes the same safe address used by route protections."""
    monkeypatch.setattr(settings, "FORWARDED_ALLOW_IPS", trusted_proxies)
    test_app = FastAPI()
    test_app.middleware("http")(request_info_middleware)

    @test_app.get("/security-event")
    async def emit_security_event():
        get_security_logger(event_type="test_security_event").info("Test event")
        return {"status": "ok"}

    records = []
    sink_id = logger.add(lambda message: records.append(message.record))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=test_app, client=(peer_address, 41000)),
            base_url="http://testserver",
        ) as async_client:
            response = await async_client.get("/security-event", headers=headers)
    finally:
        logger.remove(sink_id)

    assert response.status_code == 200
    security_record = next(
        record
        for record in records
        if record["extra"].get("event_type") == "test_security_event"
    )
    assert security_record["extra"]["client_ip"] == expected_address


@pytest.mark.asyncio
async def test_uvicorn_proxy_boundary_preserves_the_forwarded_client(monkeypatch):
    """Uvicorn and application middleware agree on the trusted gateway policy."""
    proxy_address = "192.0.2.20"
    forwarded_address = "203.0.113.90"
    monkeypatch.setattr(settings, "FORWARDED_ALLOW_IPS", proxy_address)
    test_app = FastAPI()
    test_app.middleware("http")(request_info_middleware)

    @test_app.get("/security-event")
    async def emit_security_event():
        get_security_logger(event_type="uvicorn_boundary_event").info("Test event")
        return {"status": "ok"}

    proxy_app = ProxyHeadersMiddleware(test_app, trusted_hosts=proxy_address)
    records = []
    sink_id = logger.add(lambda message: records.append(message.record))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=proxy_app, client=(proxy_address, 41000)),
            base_url="http://testserver",
        ) as async_client:
            response = await async_client.get(
                "/security-event",
                headers={"X-Forwarded-For": forwarded_address},
            )
    finally:
        logger.remove(sink_id)

    assert response.status_code == 200
    security_record = next(
        record
        for record in records
        if record["extra"].get("event_type") == "uvicorn_boundary_event"
    )
    assert security_record["extra"]["client_ip"] == forwarded_address
