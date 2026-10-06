"""Permanent AI identity behavior through authentication and membership APIs."""

from unittest.mock import patch

import pytest
from sqlmodel import select

from app.core import setup
from app.core.security import create_access_token
from app.database.models import User
from app.database.upgrade_strixy import upgrade
from app.main import app
from tests.client_rate_limiter import InMemoryClientRateLimiter


@pytest.fixture
def strixy(engine, session):
    upgrade(engine)
    return session.exec(select(User).where(User.system_identity == "strixy")).one()


def headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_system_identity_leaves_first_administrator_setup_open(client, strixy):
    app.state.bootstrap_rate_limiter = InMemoryClientRateLimiter(
        max_attempts=3, window_seconds=3600
    )
    token = setup.create_setup_token_once()[0]
    response = client.post(
        "/api/users/",
        json={
            "username": "first_admin",
            "email": "first@example.com",
            "password": "first-admin-password",
            "setup_token": token,
        },
    )
    assert response.status_code == 201
    assert response.json()["is_superadmin"] is True
    assert response.json()["system_identity"] is None
    assert (
        client.post(
            "/api/users/",
            json={
                "username": "second_admin",
                "email": "second@example.com",
                "password": "second-admin-password",
                "setup_token": token,
            },
        ).status_code
        == 401
    )


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("put", "", {"role": "Admin", "is_superadmin": True}),
        ("put", "", {"system_identity": None, "username": "human"}),
        ("put", "", {"is_active": True}),
        ("put", "/password", {"new_password": "human-password"}),
        ("delete", "", None),
    ],
)
def test_permanent_identity_rejects_account_mutations(
    client, strixy, admin_token, method, path, payload
):
    response = client.request(
        method,
        f"/api/users/{strixy.id}{path}",
        headers=headers(admin_token),
        json=payload,
    )
    assert response.status_code == 403
    users = client.get("/api/users/", headers=headers(admin_token)).json()
    system = next(user for user in users if user["id"] == strixy.id)
    assert system["system_identity"] == "strixy"
    assert system["role"] == "Analyst"
    assert system["is_superadmin"] is False


def test_system_identity_cannot_login_or_use_signed_tokens(client, strixy):
    assert (
        client.post(
            "/api/auth/login",
            data={
                "username": strixy.username,
                "password": "!",
            },
        ).status_code
        == 401
    )
    token = create_access_token(
        {"sub": strixy.auth_identity, "session_version": strixy.session_version}
    )
    assert client.get("/api/users/me", headers=headers(token)).status_code == 401
    assert (
        client.put(
            "/api/users/me/password",
            headers=headers(token),
            json={
                "current_password": "!",
                "new_password": "human-password",
            },
        ).status_code
        == 401
    )


def test_assignment_controls_chat_for_admin_and_human_analyst(
    client,
    strixy,
    admin_token,
    analyst_token,
    user_token,
    test_case_with_users,
    session,
):
    test_case_with_users.title = "Assigned case"
    session.add(test_case_with_users)
    session.commit()
    case_id = test_case_with_users.id
    membership = f"/api/cases/{case_id}/users/{strixy.id}"
    payload = {"case_id": case_id, "messages": [{"role": "user", "content": "Hello"}]}
    with patch(
        "app.services.strixy_service.StrixyService.generate",
    ) as provider:
        denied = client.post(
            "/api/strixy/chat", json=payload, headers=headers(admin_token)
        )
        assert denied.status_code == 403
        assert "not assigned" in denied.json()["detail"]
        assert denied.json()["code"] == "strixy_not_assigned"
        provider.assert_not_called()

        for token in [analyst_token, user_token]:
            assert (
                client.post(
                    membership, json={"user_id": strixy.id}, headers=headers(token)
                ).status_code
                == 403
            )
        assert (
            client.post(
                membership,
                json={"user_id": strixy.id, "is_lead": True},
                headers=headers(admin_token),
            ).status_code
            == 422
        )
        assert (
            client.post(
                membership, json={"user_id": strixy.id}, headers=headers(admin_token)
            ).status_code
            == 200
        )
        case = client.get(
            f"/api/cases/{case_id}", headers=headers(analyst_token)
        ).json()
        assert (
            next(u for u in case["users"] if u["id"] == strixy.id)["system_identity"]
            == "strixy"
        )
        for token in [admin_token, analyst_token, user_token]:
            reply = client.post(
                "/api/strixy/chat", json=payload, headers=headers(token)
            )
            assert reply.status_code == 410
        assert (
            client.patch(
                membership, json={"is_lead": True}, headers=headers(admin_token)
            ).status_code
            == 422
        )
        assert (
            client.delete(membership, headers=headers(admin_token)).status_code == 200
        )
        provider.reset_mock()
        assert (
            client.post(
                "/api/strixy/chat", json=payload, headers=headers(analyst_token)
            ).status_code
            == 403
        )
        provider.assert_not_called()


@pytest.mark.parametrize(
    "unavailable", ["human", "strixy", "human_membership", "missing_case"]
)
def test_unavailable_accounts_and_cases_do_not_reach_provider(
    client, strixy, test_user, user_token, test_case_with_users, session, unavailable
):
    from app.database.models import CaseUserLink

    case_id = test_case_with_users.id
    session.add(CaseUserLink(case_id=case_id, user_id=strixy.id))
    if unavailable in {"human", "strixy"}:
        account = test_user if unavailable == "human" else strixy
        account.is_active = False
        session.add(account)
    elif unavailable == "human_membership":
        session.delete(session.get(CaseUserLink, (case_id, test_user.id)))
    else:
        case_id = 99999
    session.commit()
    expected = (
        401 if unavailable == "human" else 404 if unavailable == "missing_case" else 403
    )
    with patch("app.services.strixy_service.StrixyService.generate") as provider:
        for response in [
            client.get(
                "/api/strixy/availability",
                params={"case_id": case_id},
                headers=headers(user_token),
            ),
            client.post(
                "/api/strixy/chat",
                json={"case_id": case_id, "messages": []},
                headers=headers(user_token),
            ),
        ]:
            assert response.status_code == expected
        provider.assert_not_called()


def test_availability_exposes_configuration_boolean_to_assigned_analyst(
    client, strixy, analyst_token, test_case_with_users, session
):
    from app.database.models import CaseUserLink

    case_id = test_case_with_users.id
    session.add(CaseUserLink(case_id=case_id, user_id=strixy.id))
    session.commit()
    response = client.get(
        "/api/strixy/availability",
        params={"case_id": case_id},
        headers=headers(analyst_token),
    )
    assert response.status_code == 200
    assert response.json() == {"is_configured": False}
