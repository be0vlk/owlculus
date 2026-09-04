"""HTTP contracts for plugin listing and NDJSON execution."""

import json
from collections.abc import AsyncGenerator
from contextlib import nullcontext
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.plugins import (
    get_plugin_api_keys,
    get_plugin_registry,
    get_plugin_session_factory,
)
from app.core.dependencies import get_current_user
from app.database.models import Case, CaseUserLink, Entity, User
from app.main import app
from app.plugins.base_plugin import BasePlugin, PluginRun, ResultEvent
from app.plugins.correlation_plugin import CorrelationScan
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
    client: TestClient, session: Session, test_user: User, test_case_with_users
):
    configure_plugins(session, test_user, [EchoPlugin])

    response = client.post(
        "/api/plugins/EchoPlugin/execute",
        json={"query": "owl", "case_id": test_case_with_users.id},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "application/json"
    assert response.text.splitlines() == [
        '{"type": "status", "data": {"message": "Starting"}}',
        '{"type": "data", "data": {"query": "owl"}}',
        '{"type": "complete", "data": {}}',
    ]


def test_correlation_catalogue_and_result_wire_contract(
    client: TestClient, session: Session, test_user: User, test_case_with_users
):
    source_case = Case(case_number="CORR-HTTP-1", title="Source investigation")
    other_case = Case(case_number="CORR-HTTP-2", title="Other investigation")
    session.add_all([source_case, other_case])
    session.flush()
    session.add_all(
        [
            CaseUserLink(case_id=source_case.id, user_id=test_user.id),
            CaseUserLink(case_id=other_case.id, user_id=test_user.id),
            Entity(
                case_id=source_case.id,
                entity_type="person",
                data={"first_name": "Ada", "last_name": "Lovelace"},
                created_by_id=test_user.id,
            ),
            Entity(
                case_id=other_case.id,
                entity_type="person",
                data={"first_name": "Ada", "last_name": "Lovelace"},
                created_by_id=test_user.id,
            ),
            Entity(
                case_id=source_case.id,
                entity_type="person",
                data={"first_name": "Ada", "last_name": "Lovelace"},
                created_by_id=test_user.id,
            ),
        ]
    )
    session.commit()
    configure_plugins(session, test_user, [CorrelationScan])

    catalogue = client.get("/api/plugins/").json()["CorrelationScan"]
    response = client.post(
        "/api/plugins/CorrelationScan/execute",
        json={"case_id": source_case.id},
    )

    assert catalogue["parameters"]["case_id"] == {
        "type": "integer",
        "description": "ID of the case to scan",
        "required": True,
    }
    assert [json.loads(line) for line in response.text.splitlines()] == [
        {
            "type": "data",
            "data": {
                "entity_id": 1,
                "entity_name": "Ada Lovelace",
                "entity_type": "person",
                "match_type": "name",
                "case_id": source_case.id,
                "matches": [
                    {
                        "entity_id": 2,
                        "entity_type": "person",
                        "case_id": other_case.id,
                        "case_number": "CORR-HTTP-2",
                        "case_title": "Other investigation",
                    }
                ],
            },
        },
        {"type": "complete", "data": {}},
    ]


def test_people_data_labs_runs_with_static_vault(
    client: TestClient,
    session: Session,
    test_user: User,
    test_case_with_users,
    monkeypatch,
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
        json={
            "search_type": "person",
            "email": "ada@example.com",
            "case_id": test_case_with_users.id,
        },
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
    client: TestClient,
    session: Session,
    test_user: User,
    test_case_with_users,
    throwing_plugin_class,
):
    configure_plugins(session, test_user, [throwing_plugin_class])

    response = client.post(
        "/api/plugins/ThrowingPlugin/execute", json={"case_id": test_case_with_users.id}
    )

    assert response.text.splitlines() == [
        '{"type": "data", "data": {"partial": true}}',
        '{"type": "error", "data": {"message": "Plugin execution error: provider exploded"}}',
        '{"type": "complete", "data": {}}',
    ]


def test_unknown_plugin_is_error_then_complete(
    client: TestClient, session: Session, test_user: User, test_case_with_users
):
    configure_plugins(session, test_user, [])

    response = client.post(
        "/api/plugins/Unknown/execute", json={"case_id": test_case_with_users.id}
    )

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


def test_execution_receives_case_context_without_saving(
    client, session, test_user, test_case_with_users
):
    class ContextPlugin(EchoPlugin):
        async def run(self, params, ctx):
            yield self.data(
                {
                    "case_id": ctx.case_id,
                    "save_to_case": ctx.save_to_case,
                    "params": params,
                }
            )

    configure_plugins(session, test_user, [ContextPlugin])
    response = client.post(
        "/api/plugins/ContextPlugin/execute",
        json={
            "case_id": test_case_with_users.id,
            "query": "owl",
            "save_to_case": False,
        },
    )
    assert response.status_code == 200
    assert json.loads(response.text.splitlines()[0])["data"] == {
        "case_id": test_case_with_users.id,
        "save_to_case": False,
        "params": {"query": "owl"},
    }


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


@pytest.mark.parametrize("save", [False, True])
def test_optional_saving_writes_only_execution_case(
    client,
    session,
    test_admin,
    test_case,
    test_closed_case,
    tmp_path,
    monkeypatch,
    save,
):
    from app.core import file_storage
    from app.plugins.plugin_types import IpAddressWrite

    monkeypatch.setattr(file_storage, "UPLOAD_DIR", tmp_path / "uploads")

    class SavingPlugin(EchoPlugin):
        def entity_writes(self, payloads, params):
            return [IpAddressWrite("192.0.2.10", "Test discovery")]

    configure_plugins(session, test_admin, [SavingPlugin])
    response = client.post(
        "/api/plugins/SavingPlugin/execute",
        json={
            "query": "owl",
            "case_id": test_case.id,
            "save_to_case": save,
        },
    )
    assert response.status_code == 200
    assert all(
        json.loads(line)["type"] != "error" for line in response.text.splitlines()
    )
    evidence = client.get(f"/api/evidence/case/{test_case.id}").json()
    entities = client.get(f"/api/cases/{test_case.id}/entities").json()
    assert bool(evidence) is save
    assert bool(entities) is save
    if save:
        assert all(item["case_id"] == test_case.id for item in evidence)
        assert entities[0]["data"]["ip_address"] == "192.0.2.10"
    assert client.get(f"/api/evidence/case/{test_closed_case.id}").json() == []
    assert client.get(f"/api/cases/{test_closed_case.id}/entities").json() == []
