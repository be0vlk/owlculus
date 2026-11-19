"""Whois plugin contract tests."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast

import pytest
import whois
from sqlmodel import Session

from app.plugins.base_plugin import PluginRun
from app.plugins.whois_plugin import WhoisPlugin


@pytest.mark.asyncio
async def test_lookup_unwraps_list_dates_and_derives_age(monkeypatch):
    # python-whois parses dates as UTC-aware datetimes.
    soon = datetime.now(UTC) + timedelta(days=10, hours=1)
    record = SimpleNamespace(
        registrar="Example Registrar",
        creation_date=[datetime(2000, 1, 2, 3, 4, 5, tzinfo=UTC), None],
        expiration_date=soon,
        updated_date="2020-01-01",
        name_servers=["NS1.EXAMPLE.COM ", None],
        status="active",
        emails=[],
    )
    monkeypatch.setattr(whois, "whois", lambda domain: record)
    ctx = PluginRun.for_test(
        session=cast(Session, None),
        user=cast(object, None),
        api_keys={},
        evidence=[],
        entities=[],
    )

    [event] = [
        event
        async for event in WhoisPlugin().run(
            {"domain": "https://Example.com/path"}, ctx
        )
    ]

    payload = event.payload
    assert payload["domain"] == "example.com"
    assert payload["creation_date"] == "2000-01-02 03:04:05 UTC"
    assert payload["updated_date"] == "2020-01-01"
    assert payload["name_servers"] == ["NS1.EXAMPLE.COM"]
    assert payload["status"] == ["active"]
    assert "emails" not in payload
    assert payload["domain_age_days"] > 9000
    assert payload["days_until_expiration"] == 10
    assert payload["expiration_warning"] == "Domain expires in 10 days"


def test_evidence_lists_present_fields_by_section():
    content = WhoisPlugin().format_evidence(
        [
            {
                "domain": "example.com",
                "registrar": "Example Registrar",
                "creation_date": "2000-01-02",
                "domain_age_years": 26.7,
                "name_servers": ["ns1.example.com"],
                "expiration_warning": "Domain expires in 10 days",
            }
        ],
        {"domain": "example.com"},
    )

    assert content.split("\n", 6)[6] == "\n".join(
        [
            "Registration Information:",
            "-" * 30,
            "Registrar: Example Registrar",
            "",
            "Important Dates:",
            "-" * 30,
            "Created: 2000-01-02",
            "Domain Age: 26.7 years",
            "",
            "Name Servers:",
            "-" * 30,
            "  ns1.example.com",
            "",
            "⚠️  WARNINGS:",
            "-" * 30,
            "  Domain expires in 10 days",
            "",
        ]
    )
