"""VirusTotal evidence formatting contract tests."""

from app.plugins.virustotal_plugin import VirustotalPlugin


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
