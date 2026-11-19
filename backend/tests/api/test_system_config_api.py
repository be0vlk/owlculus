"""HTTP contract tests for system configuration administration."""

from unittest.mock import patch

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

    response = client.put(
        "/api/admin/configuration", json={"case_number_template": "invalid"}
    )
    assert response.status_code == 422


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


def test_admin_can_read_and_update_strixy_settings(client, test_admin, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    authenticate_as(test_admin)

    response = client.get("/api/admin/configuration/strixy")
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "openai"
    assert body["reasoning_effort"] == "low"
    assert body["supports_vision"] is True
    assert body["providers"]["anthropic"] == {
        "name": "Anthropic",
        "default_model": "claude-sonnet-5-5",
        "key_configured": False,
    }
    assert set(body["providers"]) == {
        "openai",
        "openai_compatible",
        "anthropic",
        "openrouter",
    }

    saved = {
        "provider": "openai_compatible",
        "model": "llama3",
        "base_url": "http://10.0.0.5:11434/v1",
        "supports_vision": False,
        "reasoning_effort": "high",
    }
    response = client.put("/api/admin/configuration/strixy", json=saved)
    assert response.status_code == 200
    assert response.json() == body | saved

    response = client.get("/api/admin/configuration/strixy")
    assert response.json() == body | saved


def test_invalid_strixy_settings_are_rejected(client, test_admin):
    authenticate_as(test_admin)

    for invalid in (
        {"provider": "openai_compatible"},
        {"provider": "openai", "base_url": "ftp://host"},
        {"provider": "bogus"},
    ):
        response = client.put("/api/admin/configuration/strixy", json=invalid)
        assert response.status_code == 422


def test_strixy_settings_routes_reject_non_admin(client, test_user):
    authenticate_as(test_user)

    assert client.get("/api/admin/configuration/strixy").status_code == 403
    response = client.put("/api/admin/configuration/strixy", json={})
    assert response.status_code == 403


def test_strixy_put_stores_the_key_in_the_vault_and_never_returns_it(
    client, session, test_admin, monkeypatch
):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    authenticate_as(test_admin)
    saved = {
        "provider": "openrouter",
        "model": "vendor/model",
        "base_url": None,
        "supports_vision": True,
        "reasoning_effort": None,
    }

    before = client.get("/api/admin/configuration/strixy").json()
    assert before["providers"]["openrouter"]["key_configured"] is False

    response = client.put(
        "/api/admin/configuration/strixy", json=saved | {"api_key": "or-secret"}
    )

    assert response.status_code == 200
    body = response.json()
    assert "or-secret" not in response.text
    assert {k: body[k] for k in saved} == saved
    assert body["providers"]["openrouter"]["key_configured"] is True
    assert ConfigurationApiKeyVault(session).get_key(Provider.OPENROUTER) == "or-secret"
    stored = session.exec(select(SystemConfiguration)).one()
    assert "api_key" not in stored.strixy_settings


def test_strixy_put_with_a_blank_key_keeps_the_stored_key(client, session, test_admin):
    authenticate_as(test_admin)
    saved = {"provider": "openrouter", "model": "vendor/model"}
    client.put("/api/admin/configuration/strixy", json=saved | {"api_key": "kept"})

    response = client.put(
        "/api/admin/configuration/strixy", json=saved | {"api_key": "  "}
    )

    assert response.status_code == 200
    assert ConfigurationApiKeyVault(session).get_key(Provider.OPENROUTER) == "kept"


def test_strixy_models_route_lists_models_with_the_typed_key(client, test_admin):
    authenticate_as(test_admin)
    listed = [{"id": "m", "name": "M", "vision": True, "efforts": None}]

    with patch(
        "app.services.strixy_setup.list_models", return_value=listed
    ) as list_models:
        response = client.post(
            "/api/admin/configuration/strixy/models",
            json={"provider": "openrouter", "api_key": "typed"},
        )

    assert response.status_code == 200
    assert response.json() == {"models": listed}
    list_models.assert_called_once_with("openrouter", None, "typed")


def test_strixy_models_route_falls_back_to_the_stored_key(
    client, test_admin, monkeypatch
):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
    authenticate_as(test_admin)

    with patch("app.services.strixy_setup.list_models", return_value=[]) as list_models:
        client.post(
            "/api/admin/configuration/strixy/models", json={"provider": "anthropic"}
        )

    list_models.assert_called_once_with("anthropic", None, "env-key")


def test_strixy_models_route_reports_provider_failures_as_422(client, test_admin):
    authenticate_as(test_admin)

    with patch(
        "app.services.strixy_setup.list_models", side_effect=RuntimeError("boom")
    ):
        response = client.post(
            "/api/admin/configuration/strixy/models",
            json={"provider": "openrouter", "api_key": "k"},
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "boom"


def test_strixy_models_route_without_any_key_is_a_422(client, test_admin, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    authenticate_as(test_admin)

    response = client.post(
        "/api/admin/configuration/strixy/models", json={"provider": "openrouter"}
    )

    assert response.status_code == 422
    assert "API key not configured" in response.json()["detail"]


def test_strixy_models_route_rejects_an_invalid_query(client, test_admin):
    authenticate_as(test_admin)

    response = client.post(
        "/api/admin/configuration/strixy/models", json={"provider": "openai_compatible"}
    )

    assert response.status_code == 422


def test_strixy_test_route_checks_the_unsaved_form_with_the_typed_key(
    client, test_admin
):
    authenticate_as(test_admin)
    result = {"ok": True, "model": "vendor/model", "seconds": 1.2}

    with patch(
        "app.services.strixy_setup.test_connection", return_value=result
    ) as test_connection:
        response = client.post(
            "/api/admin/configuration/strixy/test",
            json={
                "provider": "openrouter",
                "model": "vendor/model",
                "reasoning_effort": None,
                "api_key": "typed",
            },
        )

    assert response.status_code == 200
    assert response.json() == result
    config, key = test_connection.call_args.args
    assert (config.provider, config.model) == ("openrouter", "vendor/model")
    assert config.base_url == "https://openrouter.ai/api/v1"
    assert config.reasoning_effort is None
    assert key == "typed"


def test_strixy_setup_routes_reject_non_admin(client, test_user):
    authenticate_as(test_user)
    bodies = {
        "models": {"provider": "openrouter", "api_key": "k"},
        "test": {"provider": "openrouter", "model": "vendor/model", "api_key": "k"},
    }

    for route, body in bodies.items():
        response = client.post(f"/api/admin/configuration/strixy/{route}", json=body)
        assert response.status_code == 403


COMPATIBLE = {
    "provider": "openai_compatible",
    "model": "local-model",
    "base_url": "https://llm.example.test/v1",
    "reasoning_effort": None,
}
OTHER_HOST = "https://elsewhere.example.test/v1"


def save_compatible(client, **extra):
    return client.put("/api/admin/configuration/strixy", json=COMPATIBLE | extra)


def test_stored_compatible_key_is_not_used_with_a_changed_base_url(
    client, session, test_admin, monkeypatch
):
    monkeypatch.delenv("OPENAI_COMPATIBLE_API_KEY", raising=False)
    authenticate_as(test_admin)
    assert save_compatible(client, api_key="stored-secret").status_code == 200
    moved = {"base_url": OTHER_HOST}

    with (
        patch("app.services.strixy_setup.list_models") as list_models,
        patch("app.services.strixy_setup.test_connection") as test_connection,
    ):
        listed = client.post(
            "/api/admin/configuration/strixy/models",
            json={"provider": "openai_compatible"} | moved,
        )
        tested = client.post(
            "/api/admin/configuration/strixy/test", json=COMPATIBLE | moved
        )
        saved = save_compatible(client, **moved)

    for response in (listed, tested, saved):
        assert response.status_code == 422
        assert "Enter the API key again" in response.json()["detail"]
    list_models.assert_not_called()
    test_connection.assert_not_called()
    stored = session.exec(select(SystemConfiguration)).one()
    assert stored.strixy_settings["base_url"] == COMPATIBLE["base_url"]


def test_switching_provider_does_not_free_the_stored_compatible_key(
    client, test_admin, monkeypatch
):
    monkeypatch.delenv("OPENAI_COMPATIBLE_API_KEY", raising=False)
    authenticate_as(test_admin)
    save_compatible(client, api_key="stored-secret")
    client.put(
        "/api/admin/configuration/strixy",
        json={"provider": "openrouter", "model": "vendor/model", "api_key": "or"},
    )

    with patch("app.services.strixy_setup.list_models") as list_models:
        listed = client.post(
            "/api/admin/configuration/strixy/models",
            json={"provider": "openai_compatible", "base_url": OTHER_HOST},
        )
    saved = save_compatible(client, base_url=OTHER_HOST)

    assert listed.status_code == saved.status_code == 422
    list_models.assert_not_called()


def test_a_base_url_saved_under_another_provider_does_not_free_the_compatible_key(
    client, session, test_admin, monkeypatch
):
    monkeypatch.delenv("OPENAI_COMPATIBLE_API_KEY", raising=False)
    authenticate_as(test_admin)
    save_compatible(client, api_key="stored-secret")
    staged = client.put(
        "/api/admin/configuration/strixy",
        json={"provider": "openai", "base_url": OTHER_HOST},
    )
    assert staged.status_code == 200
    stored = session.exec(select(SystemConfiguration)).one()
    assert stored.strixy_settings["base_url"] == OTHER_HOST

    with (
        patch("app.services.strixy_setup.list_models") as list_models,
        patch("app.services.strixy_setup.test_connection") as test_connection,
    ):
        listed = client.post(
            "/api/admin/configuration/strixy/models",
            json={"provider": "openai_compatible", "base_url": OTHER_HOST},
        )
        tested = client.post(
            "/api/admin/configuration/strixy/test",
            json=COMPATIBLE | {"base_url": OTHER_HOST},
        )
        saved = save_compatible(client, base_url=OTHER_HOST)

    for response in (listed, tested, saved):
        assert response.status_code == 422
        assert "Enter the API key again" in response.json()["detail"]
    list_models.assert_not_called()
    test_connection.assert_not_called()
    session.refresh(stored)
    assert stored.strixy_settings["provider"] == "openai"


def test_stored_compatible_key_still_works_with_the_saved_base_url(
    client, test_admin, monkeypatch
):
    monkeypatch.delenv("OPENAI_COMPATIBLE_API_KEY", raising=False)
    authenticate_as(test_admin)
    save_compatible(client, api_key="stored-secret")

    with patch("app.services.strixy_setup.list_models", return_value=[]) as listed:
        response = client.post(
            "/api/admin/configuration/strixy/models",
            json={
                "provider": "openai_compatible",
                "base_url": COMPATIBLE["base_url"] + "/",
            },
        )

    assert response.status_code == 200
    assert listed.call_args.args[2] == "stored-secret"
    assert save_compatible(client).status_code == 200


def test_a_typed_key_allows_a_changed_base_url(
    client, session, test_admin, monkeypatch
):
    monkeypatch.delenv("OPENAI_COMPATIBLE_API_KEY", raising=False)
    authenticate_as(test_admin)
    save_compatible(client, api_key="stored-secret")

    with patch("app.services.strixy_setup.list_models", return_value=[]) as listed:
        response = client.post(
            "/api/admin/configuration/strixy/models",
            json={
                "provider": "openai_compatible",
                "base_url": OTHER_HOST,
                "api_key": "new-secret",
            },
        )
    assert response.status_code == 200
    assert listed.call_args.args[2] == "new-secret"

    assert (
        save_compatible(client, base_url=OTHER_HOST, api_key="new-secret").status_code
        == 200
    )
    assert (
        ConfigurationApiKeyVault(session).get_key(Provider.OPENAI_COMPATIBLE)
        == "new-secret"
    )


def test_first_time_and_keyless_compatible_setup_is_unchanged(
    client, test_admin, monkeypatch
):
    monkeypatch.delenv("OPENAI_COMPATIBLE_API_KEY", raising=False)
    authenticate_as(test_admin)

    with patch("app.services.strixy_setup.list_models", return_value=[]) as listed:
        first = client.post(
            "/api/admin/configuration/strixy/models",
            json={"provider": "openai_compatible", "base_url": OTHER_HOST},
        )
    assert first.status_code == 200
    assert listed.call_args.args[2] == "not-needed"

    assert save_compatible(client).status_code == 200
    assert save_compatible(client, base_url=OTHER_HOST).status_code == 200


def test_environment_compatible_key_only_goes_to_the_environment_base_url(
    client, test_admin, monkeypatch
):
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "env-secret")
    monkeypatch.setenv("OPENAI_COMPATIBLE_BASE_URL", COMPATIBLE["base_url"])
    authenticate_as(test_admin)
    client.put(
        "/api/admin/configuration/strixy",
        json={"provider": "openai", "base_url": OTHER_HOST},
    )

    with patch("app.services.strixy_setup.list_models", return_value=[]) as listed:
        for base_url in (COMPATIBLE["base_url"], OTHER_HOST):
            response = client.post(
                "/api/admin/configuration/strixy/models",
                json={"provider": "openai_compatible", "base_url": base_url},
            )
            assert response.status_code == 200

    assert [call.args[2] for call in listed.call_args_list] == [
        "env-secret",
        "not-needed",
    ]
    assert save_compatible(client).status_code == 200
    saved = save_compatible(
        client, base_url=COMPATIBLE["base_url"], api_key="first-key"
    )
    assert saved.status_code == 200
