"""VirusTotal plugin contract tests."""

from typing import cast

import pytest
import vt
from sqlmodel import Session

from app.plugins.base_plugin import PluginRun, ResultEvent
from app.plugins.virustotal_plugin import VirustotalPlugin
from app.services.api_key_vault import Provider


def test_evidence_formatter_receives_payloads_and_includes_finding():
    content = VirustotalPlugin().format_evidence(
        [
            {
                "target": "example.com",
                "target_type": "domain",
                "verdict": "Suspicious",
                "detection_ratio": "3/90",
                "last_analysis_date": "2026-09-04",
                "domain_info": {"registrar": "Example Registrar"},
            }
        ],
        {"target": "example.com", "analysis_type": "domain"},
    )

    assert "example.com" in content
    assert "Suspicious" in content
    assert "3/90" in content
    assert "Example Registrar" in content


ANALYSIS = {
    "last_analysis_date": 1767225600,  # 2026-01-01 00:00:00 UTC
    "last_analysis_stats": {"malicious": 1, "harmless": 2, "unsupported": 5},
    "last_analysis_results": {
        "Zeta": {"result": "malware", "category": "malicious"},
        "Alpha": {"result": "clean"},
        "Beta": {"result": None},
    },
}
OBJECTS = {
    "/files/"
    + "a"
    * 32: {
        **ANALYSIS,
        "sha256": "s256",
        "sha1": "s1",
        "md5": "m5",
        "size": 10,
        "type_description": "PE32",
        "tags": ["peexe"],
    },
    "/urls/"
    + vt.url_id("https://example.com/x"): {
        **ANALYSIS,
        "title": "X",
        "categories": {},
    },
    "/domains/example.com": {
        **ANALYSIS,
        "registrar": "Reg",
        "creation_date": 1767225600,
        "categories": {"Vendor": "news"},
    },
    "/ip_addresses/192.0.2.1": {**ANALYSIS, "asn": 64500, "country": "EX"},
}


class FakeClient:
    def __init__(self, api_key):
        assert api_key == "key"

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get_object_async(self, path):
        kind, object_id = path.split("/")[1:3]
        return vt.Object(kind, object_id, OBJECTS[path])


async def analyze(monkeypatch, target):
    monkeypatch.setattr(vt, "Client", FakeClient)
    ctx = PluginRun.for_test(
        session=cast(Session, None),
        user=cast(object, None),
        api_keys={Provider.VIRUSTOTAL: "key"},
        evidence=[],
        entities=[],
    )
    return [event async for event in VirustotalPlugin().run({"target": target}, ctx)]


@pytest.mark.asyncio
async def test_file_analysis_keeps_any_vendor_result_and_tags(monkeypatch):
    [event] = await analyze(monkeypatch, "a" * 32)

    assert event == ResultEvent.data(
        {
            "target": "a" * 32,
            "target_type": "file",
            "detection_ratio": "1/3",
            "verdict": "Likely Malicious",
            "last_analysis_date": "2026-01-01 00:00:00",
            "file_info": {
                "sha256": "s256",
                "sha1": "s1",
                "md5": "m5",
                "size": 10,
                "type": "PE32",
                "names": [],
            },
            "detections": [
                {"vendor": "Alpha", "result": "clean", "category": "Unknown"},
                {"vendor": "Zeta", "result": "malware", "category": "malicious"},
            ],
            "tags": ["peexe"],
        }
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("target", "target_type", "info_key", "info", "extra"),
    [
        (
            "https://example.com/x",
            "url",
            "url_info",
            {"final_url": "https://example.com/x", "title": "X"},
            {"categories": {}},
        ),
        (
            "example.com",
            "domain",
            "domain_info",
            {"reputation": 0, "registrar": "Reg", "creation_date": "2026-01-01"},
            {"categories": {"Vendor": "news"}},
        ),
        (
            "192.0.2.1",
            "ip_address",
            "ip_info",
            {"asn": 64500, "as_owner": None, "country": "EX", "reputation": 0},
            {},
        ),
    ],
)
async def test_non_file_analysis_drops_clean_vendors(
    monkeypatch, target, target_type, info_key, info, extra
):
    [event] = await analyze(monkeypatch, target)

    assert event.payload == {
        "target": target,
        "target_type": target_type,
        "detection_ratio": "1/3",
        "verdict": "Likely Malicious",
        "last_analysis_date": "2026-01-01 00:00:00",
        info_key: info,
        "detections": [
            {"vendor": "Beta", "result": None, "category": "Unknown"},
            {"vendor": "Zeta", "result": "malware", "category": "malicious"},
        ],
        **extra,
    }
