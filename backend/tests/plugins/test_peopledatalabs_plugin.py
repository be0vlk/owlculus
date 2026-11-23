"""People Data Labs plugin contract tests."""

import json

import httpx
import pytest

from app.plugins.base_plugin import PluginRun, ResultEvent
from app.plugins.peopledatalabs_plugin import PeopledatalabsPlugin
from app.services.api_key_vault import Provider


def context(session, user, keys):
    return PluginRun.for_test(
        session=session,
        user=user,
        api_keys=keys,
        evidence=[],
        entities=[],
    )


@pytest.mark.asyncio
async def test_people_data_labs_uses_key_from_context(session, test_admin, monkeypatch):
    class Response:
        ok = True
        text = "ok"
        status_code = 200

        def json(self):
            return {"status": 200, "data": {"full_name": "Ada"}}

    class Client:
        def __init__(self, api_key):
            assert api_key == "key"
            self.person = self

        def enrichment(self, **params):
            return Response()

    monkeypatch.setattr("peopledatalabs.PDLPY", Client)
    events = [
        event
        async for event in PeopledatalabsPlugin().run(
            {"search_type": "person", "email": "ada@example.com"},
            context(session, test_admin, {Provider.PEOPLE_DATA_LABS: "key"}),
        )
    ]

    assert events == [
        ResultEvent.data(
            {
                "search_type": "person",
                "person": {"full_name": "Ada"},
                "api_credits_used": 1,
                "confidence": "unknown",
            }
        )
    ]


def test_evidence_formatter_receives_payloads():
    content = PeopledatalabsPlugin().format_evidence(
        [{"search_type": "person", "person": {"full_name": "Ada Lovelace"}}],
        {"search_type": "person"},
    )

    assert "Ada Lovelace" in content


@pytest.mark.asyncio
@pytest.mark.parametrize("queued", [False, True])
async def test_person_enrichment_with_only_monid_key(
    session, test_admin, monkeypatch, queued
):
    monkeypatch.setenv("MONID_API_KEY", "monid-test-key")
    run = {
        "status": "COMPLETED",
        "output": {"status": 200, "data": {"full_name": "李"}},
    }
    polls = []

    def post(url, *, headers, content, timeout):
        assert url == "https://api.monid.ai/v1/run"
        assert headers == {
            "Authorization": "Bearer monid-test-key",
            "Content-Type": "application/json; charset=utf-8",
        }
        assert "李".encode() in content
        assert json.loads(content) == {
            "provider": "pdl",
            "endpoint": "/v5/person/enrich",
            "input": {
                "body": {
                    "name": "李",
                    "profile": "linkedin.com/in/test",
                    "pretty": True,
                }
            },
        }
        return httpx.Response(
            202 if queued else 200,
            json={"runId": "test-run"} if queued else run,
            request=httpx.Request("POST", url),
        )

    def get(url, *, headers, timeout):
        assert url == "https://api.monid.ai/v1/runs/test-run"
        assert headers == {"Authorization": "Bearer monid-test-key"}
        polls.append(url)
        return httpx.Response(
            200,
            json={"status": "RUNNING"} if len(polls) == 1 else run,
            request=httpx.Request("GET", url),
        )

    def unexpected_client(**kwargs):
        pytest.fail("The Monid path must bypass the People Data Labs client")

    monkeypatch.setattr("httpx.post", post)
    monkeypatch.setattr("httpx.get", get)
    monkeypatch.setattr("app.plugins.peopledatalabs_plugin.time.sleep", lambda _: None)
    monkeypatch.setattr("peopledatalabs.PDLPY", unexpected_client)
    plugin = PeopledatalabsPlugin()
    ctx = context(session, test_admin, {})

    assert plugin.get_metadata()["api_key_requirements"] == []
    events = [
        event
        async for event in plugin.run(
            {"search_type": "person", "name": "李", "linkedin": "linkedin.com/in/test"},
            ctx,
        )
    ]
    assert events == [
        ResultEvent.data(
            {
                "search_type": "person",
                "person": {"full_name": "李"},
                "api_credits_used": 1,
                "confidence": "unknown",
            }
        )
    ]
    assert len(polls) == (2 if queued else 0)
    assert [
        event
        async for event in plugin.run({"search_type": "company", "name": "Acme"}, ctx)
    ] == [ctx.missing_key(Provider.PEOPLE_DATA_LABS)]


@pytest.mark.asyncio
async def test_monid_routes_vendor_no_match_to_provider_error(
    session, test_admin, monkeypatch
):
    monkeypatch.setenv("MONID_API_KEY", "monid-test-key")

    def post(url, **kwargs):
        return httpx.Response(
            200,
            json={
                "status": "COMPLETED",
                "providerResponse": {
                    "httpStatus": 404,
                    "error": {"error": {"message": "No match found"}},
                },
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("httpx.post", post)
    events = [
        event
        async for event in PeopledatalabsPlugin().run(
            {"search_type": "person", "email": "ada@example.com"},
            context(session, test_admin, {}),
        )
    ]

    assert events == [ResultEvent.error("People Data Labs API error: No match found")]


@pytest.mark.asyncio
async def test_company_search_sends_domain_as_website(session, test_admin, monkeypatch):
    sent = {}

    class Response:
        ok = True
        text = "ok"

        def json(self):
            return {"status": 200, "data": {"name": "Acme", "likelihood": 9}}

    class Client:
        def __init__(self, api_key):
            self.company = self

        def enrichment(self, **params):
            sent.update(params)
            return Response()

    monkeypatch.setattr("peopledatalabs.PDLPY", Client)
    ctx = context(session, test_admin, {Provider.PEOPLE_DATA_LABS: "key"})

    events = [
        event
        async for event in PeopledatalabsPlugin().run(
            {"search_type": "company", "name": "Acme", "domain": "acme.test"}, ctx
        )
    ]
    missing = [
        event
        async for event in PeopledatalabsPlugin().run({"search_type": "company"}, ctx)
    ]

    assert sent == {"name": "Acme", "website": "acme.test", "pretty": True}
    assert events == [
        ResultEvent.data(
            {
                "search_type": "company",
                "company": {"name": "Acme", "likelihood": 9},
                "api_credits_used": 1,
                "confidence": 9,
            }
        )
    ]
    assert missing == [
        ResultEvent.error(
            "At least one company identifier is required (name, website, domain, or LinkedIn)"
        )
    ]
