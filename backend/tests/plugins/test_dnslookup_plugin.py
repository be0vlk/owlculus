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
