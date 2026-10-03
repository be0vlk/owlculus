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


@pytest.mark.parametrize("ip", ["192.0.2.8", None])
def test_evidence_formatter_receives_payloads_and_includes_findings(ip):
    content = SubdomainEnumPlugin().format_evidence(
        [
            {
                "subdomain": "api.example.com",
                "ip": ip,
                "resolved": ip is not None,
                "source": "crt.sh",
            },
            {
                "phase": "summary",
                "total_discovered": 1,
                "total_resolved": int(ip is not None),
                "sources_used": ["crt.sh"],
            },
        ],
        {"domain": "example.com"},
    )

    assert "api.example.com" in content
    assert f"→ {ip or 'N/A':<15} (Source: crt.sh)" in content
    assert "Total Unique Subdomains Found: 1" in content
    assert f"Successfully Resolved: {int(ip is not None)}" in content


@pytest.mark.asyncio
async def test_queries_all_three_sources_and_resolves_sequentially(monkeypatch):
    import dns.asyncresolver
    import httpx

    from app.services.api_key_vault import Provider

    requests = []

    def provider(request):
        requests.append(request)
        if request.url.host == "crt.sh":
            return httpx.Response(
                200, json=[{"name_value": "api.example.com\n*.example.com"}]
            )
        if request.url.host == "api.hackertarget.com":
            return httpx.Response(
                200, text="API.example.com,192.0.2.1\nwww.other.org,x"
            )
        assert request.headers["APIKEY"] == "st-key"
        return httpx.Response(200, json={"subdomains": ["dev"]})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(provider), **kwargs),
    )

    class Answer:
        def to_text(self):
            return "192.0.2.1"

    async def resolve(self, name, record_type):
        if name == "dev.example.com":
            raise dns.resolver.NXDOMAIN
        return [Answer()]

    monkeypatch.setattr(dns.asyncresolver.Resolver, "resolve", resolve)
    ctx = PluginRun.for_test(
        session=cast(Session, None),
        user=cast(object, None),
        api_keys={Provider.SECURITYTRAILS: "st-key"},
        evidence=[],
        entities=[],
    )

    events = [
        event
        async for event in SubdomainEnumPlugin().run(
            {"domain": "Example.com", "use_securitytrails": True}, ctx
        )
    ]

    assert [str(request.url) for request in requests] == [
        "https://crt.sh/?q=%25.example.com&output=json",
        "https://api.hackertarget.com/hostsearch/?q=example.com",
        "https://api.securitytrails.com/v1/domain/example.com/subdomains",
    ]
    assert [event.payload for event in events] == [
        {
            "subdomain": "api.example.com",
            "ip": "192.0.2.1",
            "resolved": True,
            "source": "crt.sh, HackerTarget",
        },
        {
            "subdomain": "dev.example.com",
            "ip": None,
            "resolved": False,
            "source": "SecurityTrails",
        },
        {
            "status": "complete",
            "phase": "summary",
            "total_discovered": 2,
            "total_resolved": 1,
            "sources_used": ["crt.sh", "HackerTarget", "SecurityTrails"],
        },
    ]
