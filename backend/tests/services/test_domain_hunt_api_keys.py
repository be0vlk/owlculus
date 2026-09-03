"""API-key behaviour for the Domain investigation hunt."""

from app.hunts.definitions.domain_hunt import DomainHunt
from app.services.api_key_vault import Provider, StaticApiKeyVault


def test_domain_hunt_offers_securitytrails_when_key_is_configured():
    hunt = DomainHunt(
        api_key_vault=StaticApiKeyVault({Provider.SECURITYTRAILS: "test-key"})
    )

    assert "use_securitytrails" in hunt.initial_parameters


def test_domain_hunt_omits_securitytrails_when_key_is_absent():
    hunt = DomainHunt(api_key_vault=StaticApiKeyVault({}))

    assert "use_securitytrails" not in hunt.initial_parameters
