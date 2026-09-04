"""HTTP contracts for plugin listing and NDJSON execution."""

from collections.abc import AsyncGenerator
from contextlib import nullcontext
from typing import Any

from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.plugins import (
    get_plugin_api_keys,
    get_plugin_registry,
    get_plugin_session_factory,
)
from app.core.dependencies import get_current_user
from app.database.models import User
from app.main import app
from app.plugins.base_plugin import BasePlugin, PluginRun, ResultEvent
from app.plugins.peopledatalabs_plugin import PeopledatalabsPlugin
from app.plugins.plugin_registry import PluginRegistry
from app.services.api_key_vault import Provider, StaticApiKeyVault


class EchoPlugin(BasePlugin):
    def __init__(self):
        super().__init__(display_name="Echo")
        self.description = "Echo a query."
        self.category = "Test"
        self.parameters = {"query": {"type": "string", "required": True}}

    async def run(
        self, params: dict[str, Any], ctx: PluginRun
    ) -> AsyncGenerator[ResultEvent, None]:
        yield self.status("Starting")
        yield self.data({"query": params["query"]})


def configure_plugins(
    session: Session, user: User, plugin_classes: list[type[BasePlugin]]
) -> None:
    registry = PluginRegistry.from_classes(plugin_classes)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_plugin_registry] = lambda: registry
    app.dependency_overrides[get_plugin_api_keys] = lambda: StaticApiKeyVault({})
    app.dependency_overrides[get_plugin_session_factory] = lambda: (
        lambda: nullcontext(session)
    )


def test_list_plugins_uses_class_list_registry(
    client: TestClient, session: Session, test_admin: User
):
    configure_plugins(session, test_admin, [EchoPlugin])

    response = client.get("/api/plugins/")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["EchoPlugin"] == {
        "name": "EchoPlugin",
        "display_name": "Echo",
        "description": "Echo a query.",
        "enabled": True,
        "category": "Test",
        "parameters": {
            "query": {"type": "string", "required": True},
            "save_to_case": {
                "type": "boolean",
                "description": "Save Echo results as evidence to the case",
                "default": False,
                "required": False,
            },
        },
        "api_key_requirements": [],
        "api_key_status": {},
    }


def test_execute_real_plugin_ends_with_complete(
    client: TestClient, session: Session, test_user: User
):
    configure_plugins(session, test_user, [EchoPlugin])

    response = client.post("/api/plugins/EchoPlugin/execute", json={"query": "owl"})

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "application/json"
    assert response.text.splitlines() == [
        '{"type": "status", "data": {"message": "Starting"}}',
        '{"type": "data", "data": {"query": "owl"}}',
        '{"type": "complete", "data": {}}',
    ]


def test_people_data_labs_runs_with_static_vault(
    client: TestClient, session: Session, test_user: User, monkeypatch
):
    class Response:
        ok = True
        text = "ok"
        status_code = 200

        def json(self):
            return {
                "status": 200,
                "data": {"full_name": "Ada Lovelace", "likelihood": 10},
                "credits_used": 1,
            }

    class Client:
        def __init__(self, api_key):
            assert api_key == "pdl-test-key"
            self.person = self

        def enrichment(self, **params):
            assert params["email"] == "ada@example.com"
            return Response()

    monkeypatch.setattr("peopledatalabs.PDLPY", Client)
    configure_plugins(session, test_user, [PeopledatalabsPlugin])
    app.dependency_overrides[get_plugin_api_keys] = lambda: StaticApiKeyVault(
        {Provider.PEOPLE_DATA_LABS: "pdl-test-key"}
    )

    response = client.post(
        "/api/plugins/PeopledatalabsPlugin/execute",
        json={"search_type": "person", "email": "ada@example.com"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.text.splitlines() == [
        (
            '{"type": "data", "data": {"search_type": "person", '
            '"person": {"full_name": "Ada Lovelace", "likelihood": 10}, '
            '"api_credits_used": 1, "confidence": 10}}'
        ),
        '{"type": "complete", "data": {}}',
    ]


def test_throwing_plugin_is_error_then_complete(
    client: TestClient, session: Session, test_user: User, throwing_plugin_class
):
    configure_plugins(session, test_user, [throwing_plugin_class])

    response = client.post("/api/plugins/ThrowingPlugin/execute", json={})

    assert response.text.splitlines() == [
        '{"type": "data", "data": {"partial": true}}',
        '{"type": "error", "data": {"message": "Plugin execution error: provider exploded"}}',
        '{"type": "complete", "data": {}}',
    ]


def test_unknown_plugin_is_error_then_complete(
    client: TestClient, session: Session, test_user: User
):
    configure_plugins(session, test_user, [])

    response = client.post("/api/plugins/Unknown/execute", json={})

    assert response.text.splitlines() == [
        '{"type": "error", "data": {"message": "Plugin Unknown not found"}}',
        '{"type": "complete", "data": {}}',
    ]


def test_analyst_cannot_execute_plugins(
    client: TestClient, session: Session, test_analyst: User
):
    configure_plugins(session, test_analyst, [EchoPlugin])

    response = client.post("/api/plugins/EchoPlugin/execute", json={"query": "owl"})

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_execute_plugin_requires_authentication(client: TestClient):
    response = client.post("/api/plugins/EchoPlugin/execute", json={"query": "owl"})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
