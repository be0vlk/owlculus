"""People Data Labs plugin contract tests."""

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
