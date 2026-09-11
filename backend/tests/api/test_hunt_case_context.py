"""Hunt HTTP boundaries keep execution and history within authorized cases."""

import pytest

from app.core.dependencies import get_current_user
from app.database.models import Case, CaseUserLink, Hunt, User
from app.main import app


@pytest.mark.parametrize(
    ("role", "assigned", "expected"),
    [
        ("Investigator", False, 403),
        ("Analyst", True, 403),
        ("Investigator", True, 202),
        ("Admin", False, 202),
    ],
)
def test_hunt_execution_authorizes_supplied_case(
    client, session, monkeypatch, role, assigned, expected
):
    user = User(
        username="hunter", email="hunter@example.com", password_hash="unused", role=role
    )
    case = Case(case_number="HUNT-1", title="Investigation", status="Closed")
    other = Case(case_number="HUNT-2", title="Other investigation", status="Open")
    hunt = Hunt(
        name="context_test",
        display_name="Context test",
        description="Test hunt context",
        category="general",
        definition_json={
            "steps": [],
            "initial_parameters": {"subject": {"type": "string"}},
        },
    )
    session.add_all([user, case, other, hunt])
    session.commit()
    if assigned:
        session.add(CaseUserLink(case_id=case.id, user_id=user.id))
        session.commit()
    app.dependency_overrides[get_current_user] = lambda: user

    response = client.post(
        f"/api/hunts/{hunt.id}/execute",
        json={"case_id": case.id, "parameters": {"subject": "example.org"}},
    )

    assert response.status_code == expected
    if expected == 403:
        return
    execution = response.json()
    assert execution["kind"] == "hunt"
    assert execution["status"] == "pending"
    assert execution["dispatch_state"] == "pending"
    assert response.headers["location"] == execution["links"]["detail"]
    assert execution["case_id"] == case.id
    assert execution["initial_parameters"] == {"subject": "example.org"}
    detail = client.get(f"/api/hunts/executions/{execution['id']}")
    assert detail.status_code == 200
    assert detail.json()["case_id"] == case.id
    history = client.get(f"/api/hunts/cases/{case.id}/executions")
    assert [item["id"] for item in history.json()] == [execution["id"]]
    other_history = client.get(f"/api/hunts/cases/{other.id}/executions")
    assert other_history.status_code == (200 if role == "Admin" else 403)
    if role == "Admin":
        assert other_history.json() == []

    # Losing membership also revokes access through copied execution links.
    user.role = "Investigator"
    for link in list(case.users):
        case.users.remove(link)
    session.add(user)
    session.commit()
    assert client.get(f"/api/hunts/executions/{execution['id']}").status_code == 403


@pytest.mark.parametrize(
    "parameters",
    [{"subject": 42}, {}, {"subject": ""}, {"subject": "owl", "extra": True}],
)
def test_hunt_rejects_invalid_initial_parameters_before_acceptance(
    client, session, parameters
):
    user = User(
        username="validation",
        email="validation@example.com",
        password_hash="unused",
        role="Admin",
    )
    case = Case(case_number="VALIDATE-1")
    hunt = Hunt(
        name="validation",
        display_name="Validation",
        description="Validation",
        category="test",
        definition_json={
            "steps": [],
            "initial_parameters": {"subject": {"type": "string", "required": True}},
        },
    )
    session.add_all([user, case, hunt])
    session.commit()
    app.dependency_overrides[get_current_user] = lambda: user
    response = client.post(
        f"/api/hunts/{hunt.id}/execute",
        json={"case_id": case.id, "parameters": parameters},
    )
    assert response.status_code == 422
    assert client.get(f"/api/hunts/cases/{case.id}/executions").json() == []
