"""Public-behaviour tests for system configuration administration."""

from datetime import UTC, datetime

import pytest
from sqlmodel import select

from app.core.exceptions import AuthorizationException, ValidationException
from app.core.security import decrypt_api_key
from app.database.models import SystemConfiguration
from app.services.api_key_vault import Provider
from app.services.system_config_service import SystemConfigService

FIXED_TIME = datetime(2026, 9, 3, 12, 30, tzinfo=UTC)


@pytest.fixture(name="service")
def service_fixture(session):
    return SystemConfigService(session, clock=lambda: FIXED_TIME)


async def test_get_configuration_creates_and_reuses_defaults(service, session):
    first = await service.get_configuration()
    second = await service.get_configuration()

    assert first.id == second.id
    assert first.case_number_template == "YYMM-NN"
    assert first.api_keys == {}
    assert first.evidence_folder_templates
    assert len(session.exec(select(SystemConfiguration)).all()) == 1


async def test_admin_configuration_rejects_non_admin(service, test_user):
    with pytest.raises(AuthorizationException) as error:
        await service.get_configuration_admin(current_user=test_user)

    assert str(error.value) == "Not authorized"


async def test_update_configuration_validates_and_persists(service, test_admin):
    updated = await service.update_configuration(
        "PREFIX-YYMM-NN", current_user=test_admin, case_number_prefix="OWL"
    )

    assert updated.case_number_prefix == "OWL"
    assert updated.updated_at == FIXED_TIME.replace(tzinfo=None)

    with pytest.raises(ValidationException):
        await service.update_configuration("invalid", current_user=test_admin)


async def test_monthly_template_clears_an_existing_prefix(service, test_admin):
    await service.update_configuration(
        "PREFIX-YYMM-NN", current_user=test_admin, case_number_prefix="OWL"
    )

    updated = await service.update_configuration("YYMM-NN", current_user=test_admin)

    assert updated.case_number_prefix is None


def test_preview_uses_injected_time(service):
    assert service.generate_example_case_number("YYMM-NN") == "2609-01"
    assert (
        service.generate_example_case_number("PREFIX-YYMM-NN", "OWL") == "OWL-2609-01"
    )
    assert service.get_template_display_name("YYMM-NN") == "Monthly Reset (YYMM-NN)"


async def test_key_editing_encrypts_and_preserves_creation_time(service, test_admin):
    created = await service.set_api_key(
        Provider.OPENAI, "secret-one", "OpenAI", current_user=test_admin
    )
    stored = created.api_keys[Provider.OPENAI.value]

    assert stored["api_key"] != "secret-one"
    assert decrypt_api_key(stored["api_key"]) == "secret-one"
    assert stored["created_at"] == FIXED_TIME.isoformat()

    updated = await service.set_api_key(
        Provider.OPENAI, None, "OpenAI renamed", current_user=test_admin
    )
    assert decrypt_api_key(updated.api_keys["openai"]["api_key"]) == "secret-one"
    assert updated.api_keys["openai"]["created_at"] == FIXED_TIME.isoformat()


async def test_new_key_requires_a_value(service, test_admin):
    with pytest.raises(ValidationException):
        await service.set_api_key(
            Provider.SHODAN, None, "Shodan", current_user=test_admin
        )


async def test_list_and_remove_keys(service, test_admin):
    await service.set_api_key(
        Provider.VIRUSTOTAL, "secret", "VirusTotal", current_user=test_admin
    )

    listed = await service.list_api_keys(current_user=test_admin)
    assert listed == {
        "virustotal": {
            "name": "VirusTotal",
            "is_configured": True,
            "created_at": FIXED_TIME.isoformat(),
        }
    }

    removed = await service.remove_api_key(Provider.VIRUSTOTAL, current_user=test_admin)
    assert removed.api_keys == {}


async def test_evidence_template_update_is_validated(service, test_admin):
    templates = {
        "compact": {
            "name": "Compact",
            "description": "A compact evidence tree",
            "folders": [],
        }
    }

    await service.update_evidence_folder_templates(templates, current_user=test_admin)
    assert await service.get_evidence_folder_templates() == templates

    with pytest.raises(ValidationException):
        await service.update_evidence_folder_templates(
            {"broken": {"name": "Broken"}}, current_user=test_admin
        )
