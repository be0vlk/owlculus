"""Subdomain enumeration tests at the plugin-author contract."""

from typing import cast

import pytest
from sqlmodel import Session

from app.plugins.base_plugin import PluginRun, ResultEvent
from app.plugins.subdomain_enum_plugin import SubdomainEnumPlugin


def context(session, user):
    return PluginRun.for_test(
        session=session,
        user=user,
        api_keys={},
        evidence=[],
        entities=[],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("has_session", [True, False])
async def test_no_key_run_is_independent_of_session_shape(
    session, test_admin, has_session
):
    plugin = SubdomainEnumPlugin()
    run_session = session if has_session else cast(Session, None)

    events = [
        event
        async for event in plugin.run(
            {
                "domain": "example.com",
                "use_securitytrails": True,
            },
            context(run_session, test_admin),
        )
    ]

    assert events == [
        ResultEvent.error(
            "API key required for Securitytrails. Add it in Admin → Configuration → API Keys."
        )
    ]


def test_evidence_formatter_receives_payloads_and_includes_findings():
    content = SubdomainEnumPlugin().format_evidence(
        [
            {
                "subdomain": "api.example.com",
                "ip": "192.0.2.8",
                "resolved": True,
                "source": "crt.sh",
            },
            {
                "phase": "summary",
                "total_discovered": 1,
                "total_resolved": 1,
                "sources_used": ["crt.sh"],
            },
        ],
        {"domain": "example.com"},
    )

    assert "api.example.com" in content
    assert "192.0.2.8" in content
    assert "Total Unique Subdomains Found: 1" in content
