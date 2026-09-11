"""Configuration-independent inputs for the Domain investigation hunt."""

from app.hunts.definitions.domain_hunt import DomainHunt


def test_domain_hunt_always_offers_the_optional_securitytrails_input():
    hunt = DomainHunt()

    assert hunt.initial_parameters["use_securitytrails"] == {
        "type": "boolean",
        "description": "Enable SecurityTrails API for enhanced subdomain discovery",
        "default": False,
        "required": False,
    }
