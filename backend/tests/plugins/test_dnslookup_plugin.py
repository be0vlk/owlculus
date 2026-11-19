"""DNS lookup plugin contract tests."""

from typing import cast
from unittest.mock import AsyncMock

import pytest
from dns.exception import Timeout
from sqlmodel import Session

from app.plugins.base_plugin import PluginRun, ResultEvent
from app.plugins.dnslookup_plugin import DnsLookup


@pytest.mark.asyncio
async def test_reverse_lookup_reports_resolver_errors(monkeypatch):
    monkeypatch.setattr(
        "dns.asyncresolver.Resolver.resolve",
        AsyncMock(side_effect=[Timeout(), RuntimeError("boom")]),
    )
    ctx = PluginRun.for_test(
        session=cast(Session, None),
        user=cast(object, None),
        api_keys={},
        evidence=[],
        entities=[],
    )

    events = [
        event
        async for event in DnsLookup().run(
            {"domain": "192.0.2.1, 192.0.2.2, example.com", "lookup_mode": "reverse"},
            ctx,
        )
    ]

    assert [event.payload["results"][0]["error"] for event in events[:2]] == [
        "Reverse DNS error: The DNS operation timed out.",
        "Unexpected error: boom",
    ]
    assert events[2] == ResultEvent.error(
        "'example.com' is not a valid IP address for reverse lookup"
    )


def _ctx() -> PluginRun:
    return PluginRun.for_test(
        session=cast(Session, None),
        user=cast(object, None),
        api_keys={},
        evidence=[],
        entities=[],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "nameserver",
    [
        "10.0.0.1",
        "127.0.0.1",
        "169.254.169.254",
        "100.64.0.1",
        "192.0.2.1",
        "224.0.0.1",
        "::1",
        "fe80::1%eth0",
        "fc00::1",
        "fec0::1",
        "fec0::1%1",
        "ff02::1%1",
        "::ffff:127.0.0.1",
        "64:ff9b::a00:2",
        "2002:a00:1::1",
        "2001::1",
        "localhost",
        "https://dns.google/dns-query",
    ],
)
async def test_non_public_nameservers_are_rejected_before_any_query(
    monkeypatch, nameserver
):
    resolve = AsyncMock()
    monkeypatch.setattr("dns.asyncresolver.Resolver.resolve", resolve)

    events = [
        event
        async for event in DnsLookup().run(
            {"domain": "example.com", "nameservers": f"8.8.8.8, {nameserver}"},
            _ctx(),
        )
    ]

    assert events == [
        ResultEvent.error(
            f"'{nameserver}' is not a public IP address and cannot be used as a nameserver"
        )
    ]
    resolve.assert_not_awaited()


@pytest.mark.asyncio
async def test_public_nameservers_reach_the_resolver_unchanged(monkeypatch):
    used: list[list[str]] = []

    async def fake_resolve(self, *args, **kwargs):
        used.append(list(self.nameservers))
        return []

    monkeypatch.setattr("dns.asyncresolver.Resolver.resolve", fake_resolve)
    nameservers = [
        "8.8.8.8",
        "2001:4860:4860::8888",
        "64:ff9b::808:808",
        "2606:4700:4700::1111%1",
    ]

    events = [
        event
        async for event in DnsLookup().run(
            {"domain": "example.com", "nameservers": ", ".join(nameservers)},
            _ctx(),
        )
    ]

    assert [event.payload["results"][0]["records"] for event in events] == [[]]
    assert used == [nameservers]


def test_entity_writes_take_unique_a_and_aaaa_records():
    writes = DnsLookup().entity_writes(
        [
            {
                "target": "example.com",
                "results": [
                    {"type": "A", "records": ["192.0.2.1", "192.0.2.1"]},
                    {"type": "MX", "records": ["10 mail.example.com."]},
                    {"type": "AAAA", "records": ["2001:db8::1"]},
                ],
            }
        ],
        {},
    )

    assert [(write.address, write.description) for write in writes] == [
        ("192.0.2.1", "Discovered via DNS Lookup lookup for 'example.com (A record)'"),
        (
            "2001:db8::1",
            "Discovered via DNS Lookup lookup for 'example.com (AAAA record)'",
        ),
    ]
