"""Public durable submission and observation contracts."""

from app.api.plugins import get_plugin_registry
from app.core.dependencies import get_current_user
from app.main import app
from app.plugins.base_plugin import BasePlugin
from app.plugins.plugin_registry import PluginRegistry


class AcceptedPlugin(BasePlugin):
    def __init__(self):
        super().__init__()
        self.parameters = {"query": {"type": "string", "required": True}}

    async def run(self, params, ctx):
        raise AssertionError("Submission must not invoke providers")
        yield


def test_submission_is_reopenable_before_any_provider_runs(
    client, test_admin, test_case
):
    app.dependency_overrides[get_current_user] = lambda: test_admin
    app.dependency_overrides[get_plugin_registry] = lambda: PluginRegistry.from_classes(
        [AcceptedPlugin]
    )
    response = client.post(
        "/api/plugins/AcceptedPlugin/execute",
        json={"case_id": test_case.id, "query": "owl"},
    )
    assert response.status_code == 202
    accepted = response.json()
    assert accepted["status"] == "queued"
    assert accepted["dispatch_state"] == "pending"
    assert accepted["kind"] == "plugin"
    detail = client.get(response.headers["location"])
    assert detail.status_code == 200
    assert detail.json()["parameters"] == {"query": "owl"}
    assert client.get(accepted["links"]["results"]).json()["items"] == []
    history = client.get(f"/api/plugins/executions/case/{test_case.id}").json()
    assert [item["id"] for item in history["items"]] == [accepted["id"]]


def test_acceptance_commit_failure_returns_503_without_execution(
    client, session, test_admin, test_case, monkeypatch
):
    from sqlalchemy.exc import OperationalError

    app.dependency_overrides[get_current_user] = lambda: test_admin
    app.dependency_overrides[get_plugin_registry] = lambda: PluginRegistry.from_classes(
        [AcceptedPlugin]
    )
    case_id = test_case.id

    def unavailable():
        raise OperationalError("commit", {}, RuntimeError("unavailable"))

    monkeypatch.setattr(session, "commit", unavailable)
    response = client.post(
        "/api/plugins/AcceptedPlugin/execute", json={"case_id": case_id, "query": "owl"}
    )
    assert response.status_code == 503
    assert "location" not in response.headers


def test_retry_uses_accepted_definition_when_plugin_becomes_unavailable(
    client, test_admin, test_case
):
    app.dependency_overrides[get_current_user] = lambda: test_admin
    app.dependency_overrides[get_plugin_registry] = lambda: PluginRegistry.from_classes(
        [AcceptedPlugin]
    )
    payload = {"case_id": test_case.id, "query": "owl"}
    first = client.post(
        "/api/plugins/AcceptedPlugin/execute",
        json=payload,
        headers={"Idempotency-Key": "accepted-definition"},
    )
    assert first.status_code == 202
    app.dependency_overrides[get_plugin_registry] = lambda: PluginRegistry.from_classes(
        []
    )
    retry = client.post(
        "/api/plugins/AcceptedPlugin/execute",
        json=payload,
        headers={"Idempotency-Key": "accepted-definition"},
    )
    assert retry.status_code == 202
    assert retry.json()["id"] == first.json()["id"]
