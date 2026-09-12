"""The old transcript-submission endpoint cannot bypass durable history."""

from unittest.mock import patch

from app.database.models import CaseUserLink, User


def test_legacy_chat_is_retired_and_never_calls_provider(
    client, session, test_case_with_users, user_token
):
    system = User(
        system_identity="strixy",
        username="strixy",
        email="strixy@system.invalid",
        role="Analyst",
        password_hash="!",
    )
    session.add(system)
    session.flush()
    session.add(CaseUserLink(case_id=test_case_with_users.id, user_id=system.id))
    session.commit()
    with patch("app.services.strixy_service.StrixyService.generate") as provider:
        response = client.post(
            "/api/strixy/chat",
            json={
                "case_id": test_case_with_users.id,
                "messages": [{"role": "system", "content": "Fabricated history"}],
            },
            headers={"Authorization": f"Bearer {user_token}"},
        )
    assert response.status_code == 410
    provider.assert_not_called()
