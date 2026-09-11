"""HTTP catalogue, authentication and submission validation contracts."""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.plugins import (
    get_plugin_api_keys,
    get_plugin_registry,
)
from app.core.dependencies import get_current_user
from app.database.models import User
from app.main import app
from app.plugins.base_plugin import BasePlugin, PluginRun, ResultEvent
from app.plugins.plugin_registry import PluginRegistry
from app.services.api_key_vault import StaticApiKeyVault


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


def test_analyst_cannot_execute_plugins(
    client: TestClient, session: Session, test_analyst: User
):
    configure_plugins(session, test_analyst, [EchoPlugin])

    response = client.post("/api/plugins/EchoPlugin/execute", json={"query": "owl"})

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_execute_plugin_requires_authentication(client: TestClient):
    response = client.post("/api/plugins/EchoPlugin/execute", json={"query": "owl"})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("save", [False, True])
def test_execution_rejects_unassigned_case_before_plugin_work(
    client, session, test_user, test_case, save
):
    configure_plugins(session, test_user, [EchoPlugin])
    response = client.post(
        "/api/plugins/EchoPlugin/execute",
        json={
            "case_id": test_case.id,
            "query": "owl",
            "save_to_case": save,
        },
    )
    assert response.status_code == 403


@pytest.mark.parametrize("case_id", [None, True, "1", 0, -1, 1.5])
def test_execution_requires_valid_case_context(client, session, test_user, case_id):
    configure_plugins(session, test_user, [EchoPlugin])
    response = client.post(
        "/api/plugins/EchoPlugin/execute",
        json={
            "case_id": case_id,
            "query": "owl",
        },
    )
    assert response.status_code == 422


def test_execution_rejects_missing_case(client, session, test_user):
    configure_plugins(session, test_user, [EchoPlugin])
    response = client.post(
        "/api/plugins/EchoPlugin/execute",
        json={
            "case_id": 99999,
            "query": "owl",
        },
    )
    assert response.status_code == 404


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"query": 4},
        {"query": "owl", "unexpected": True},
        {"query": "owl", "save_to_case": "yes"},
    ],
)
def test_invalid_parameters_are_rejected_before_acceptance(
    client, session, test_admin, test_case, params
):
    configure_plugins(session, test_admin, [EchoPlugin])
    response = client.post(
        "/api/plugins/EchoPlugin/execute", json={"case_id": test_case.id, **params}
    )
    assert response.status_code == 422
    assert (
        client.get(f"/api/plugins/executions/case/{test_case.id}").json()["items"] == []
    )


def test_unknown_and_disabled_definitions_are_rejected(
    client, session, test_admin, test_case
):
    class DisabledPlugin(EchoPlugin):
        def __init__(self):
            super().__init__()
            self.enabled = False

    configure_plugins(session, test_admin, [DisabledPlugin])
    for name, code in [("Unknown", 404), ("DisabledPlugin", 409)]:
        response = client.post(
            f"/api/plugins/{name}/execute",
            json={"case_id": test_case.id, "query": "owl"},
        )
        assert response.status_code == code


@pytest.mark.parametrize("limit", [0, 201])
def test_observation_page_sizes_are_bounded(
    client, session, test_admin, test_case, limit
):
    configure_plugins(session, test_admin, [EchoPlugin])
    assert (
        client.get(
            f"/api/plugins/executions/case/{test_case.id}?limit={limit}"
        ).status_code
        == 422
    )


def test_analyst_can_observe_assigned_case_history(
    client, session, test_admin, test_analyst, test_case
):
    from app.database.models import CaseUserLink

    configure_plugins(session, test_admin, [EchoPlugin])
    accepted = client.post(
        "/api/plugins/EchoPlugin/execute",
        json={"case_id": test_case.id, "query": "owl"},
    ).json()
    session.add(CaseUserLink(case_id=test_case.id, user_id=test_analyst.id))
    session.commit()
    app.dependency_overrides[get_current_user] = lambda: test_analyst
    assert client.get(accepted["links"]["detail"]).status_code == 200
    assert client.get(accepted["links"]["results"]).status_code == 200
    assert client.get(accepted["links"]["history"]).status_code == 200
