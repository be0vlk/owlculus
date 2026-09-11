"""Test-only process identity header; production routes and dependencies unchanged."""

import os


def create_app():
    from app.main import app

    @app.middleware("http")
    async def process_identity(request, call_next):
        response = await call_next(request)
        response.headers["X-Test-Process"] = str(os.getpid())
        return response

    return app
