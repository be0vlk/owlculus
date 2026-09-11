"""HTTP contract tests for system configuration administration."""

from sqlmodel import select

from app.core.dependencies import get_current_user
from app.core.security import decrypt_api_key
from app.database.models import SystemConfiguration
from app.main import app
from app.services.api_key_vault import ConfigurationApiKeyVault, Provider


def authenticate_as(user):
    app.dependency_overrides[get_current_user] = lambda: user


def test_admin_can_read_and_update_configuration(client, test_admin):
    authenticate_as(test_admin)

    response = client.get("/api/admin/configuration")
    assert response.status_code == 200
    assert response.json()["case_number_template"] == "YYMM-NN"

    response = client.put(
        "/api/admin/configuration",
        json={
            "case_number_template": "PREFIX-YYMM-NN",
            "case_number_prefix": "OWL",
        },
    )
    assert response.status_code == 200
    assert response.json()["case_number_prefix"] == "OWL"


def test_configuration_admin_routes_reject_non_admin(client, test_user):
    authenticate_as(test_user)

    assert client.get("/api/admin/configuration").status_code == 403
    assert (
        client.get(
            "/api/admin/configuration/preview",
            params={"template": "YYMM-NN"},
        ).status_code
        == 403
    )
    assert (
        client.get("/api/admin/configuration/api-keys/openai/status").status_code == 403
    )
    assert (
        client.put(
            "/api/admin/configuration/api-keys/openai",
            json={"api_key": "secret", "name": "OpenAI"},
        ).status_code
        == 403
    )


def test_configuration_routes_require_authentication(client):
    assert client.get("/api/admin/configuration").status_code == 401


def test_unknown_provider_is_rejected_before_key_editing(client, test_admin):
    authenticate_as(test_admin)

    response = client.put(
        "/api/admin/configuration/api-keys/typo-provider",
        json={"api_key": "secret", "name": "Typo"},
    )

    assert response.status_code == 422


def test_existing_custom_provider_option_remains_editable(client, test_admin):
    authenticate_as(test_admin)

    response = client.put(
        "/api/admin/configuration/api-keys/custom",
        json={"api_key": "custom-secret", "name": "Custom"},
    )

    assert response.status_code == 200
    assert response.json()["api_keys_configured"] == ["custom"]


def test_stored_key_round_trips_from_admin_route_through_vault(
    client, session, test_admin
):
    authenticate_as(test_admin)

    response = client.put(
        "/api/admin/configuration/api-keys/openai",
        json={"api_key": "round-trip-secret", "name": "OpenAI"},
    )

    assert response.status_code == 200
    assert response.json()["api_keys_configured"] == ["openai"]
    assert (
        ConfigurationApiKeyVault(session).get_key(Provider.OPENAI)
        == "round-trip-secret"
    )
    stored = session.exec(select(SystemConfiguration)).one()
    assert decrypt_api_key(stored.api_keys["openai"]["api_key"]) == "round-trip-secret"


def test_key_status_list_and_removal_use_real_services(client, test_admin):
    authenticate_as(test_admin)
    client.put(
        "/api/admin/configuration/api-keys/shodan",
        json={"api_key": "shodan-secret", "name": "Shodan"},
    )

    status_response = client.get("/api/admin/configuration/api-keys/shodan/status")
    assert status_response.status_code == 200
    assert status_response.json() == {"provider": "shodan", "is_configured": True}

    list_response = client.get("/api/admin/configuration/api-keys")
    assert list_response.status_code == 200
    assert list_response.json()["shodan"]["name"] == "Shodan"

    remove_response = client.delete("/api/admin/configuration/api-keys/shodan")
    assert remove_response.status_code == 200
    assert "shodan" not in remove_response.json()["api_keys_configured"]


def test_preview_and_evidence_templates_are_public_behaviour(client, test_admin):
    authenticate_as(test_admin)

    preview = client.get(
        "/api/admin/configuration/preview",
        params={"template": "PREFIX-YYMM-NN", "prefix": "OWL"},
    )
    assert preview.status_code == 200
    assert preview.json()["example_case_number"].startswith("OWL-")

    templates = {
        "compact": {
            "name": "Compact",
            "description": "Compact tree",
            "folders": [],
        }
    }
    update = client.put(
        "/api/admin/configuration/evidence-templates",
        json={"templates": templates},
    )
    assert update.status_code == 200
    assert update.json()["templates"] == templates
