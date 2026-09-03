"""Regression tests for the backend's synchronous API-test runtime."""

import subprocess
import sys
import textwrap

from fastapi.testclient import TestClient


def test_minimal_synchronous_testclient_request_has_a_bounded_runtime():
    """A standalone synchronous ASGI request cannot hang the test process."""
    probe = textwrap.dedent(
        """
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()

        @app.get("/")
        def root():
            return {"ok": True}

        with TestClient(app) as client:
            response = client.get("/")

        assert response.status_code == 200
        assert response.json() == {"ok": True}
        """
    )

    subprocess.run(
        [sys.executable, "-c", probe],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )


def test_shared_synchronous_client_owns_an_active_lifespan(client: TestClient):
    """The shared client fixture owns startup and shutdown for each test."""
    assert client.portal is not None
