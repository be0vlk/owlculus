"""HTTP-level coverage for hunt execution JSON and PDF exports."""

from datetime import UTC, datetime
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlmodel import Session, select

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.database.models import Case, CaseUserLink, Hunt, HuntExecution, HuntStep, User
from app.main import app


@pytest.fixture
def hunt_export_user(session: Session) -> User:
    user = User(
        username="hunt-exporter",
        email="hunt-exporter@example.com",
        password_hash="unused",
        role="Investigator",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def hunt_export_execution(session: Session, hunt_export_user: User) -> HuntExecution:
    case = Case(case_number="CASE-042", title="International enquiry", status="Open")
    hunt = Hunt(
        name="person_hunt",
        display_name="Person Discovery",
        description="Gather public records for a person.",
        category="person",
        definition_json={"steps": []},
    )
    session.add_all([case, hunt])
    session.commit()
    session.refresh(case)
    session.refresh(hunt)
    session.add(CaseUserLink(case_id=case.id, user_id=hunt_export_user.id))
    execution = HuntExecution(
        hunt_id=hunt.id,
        case_id=case.id,
        status="failed",
        progress=0.5,
        initial_parameters={"subject": "José Москва"},
        context_data={"evidence_refs": [{"title": "Profile", "folder_path": "People"}]},
        started_at=datetime(2026, 8, 1, 10, 0, tzinfo=UTC),
        completed_at=datetime(2026, 8, 1, 10, 1, 30, tzinfo=UTC),
        created_at=datetime(2026, 8, 1, 9, 59, tzinfo=UTC),
        created_by_id=hunt_export_user.id,
    )
    session.add(execution)
    session.commit()
    session.refresh(execution)
    session.add(
        HuntStep(
            execution_id=execution.id,
            step_id="lookup-person",
            plugin_name="PeopleData",
            status="failed",
            parameters={"country": "España"},
            output={
                "results": [{"finding": "München Москва"}],
                "result_count": 1,
                "plugin": "PeopleData",
                "errors": [{"message": "Remote source timed out"}],
            },
            error_details="Remote source timed out",
            started_at=datetime(2026, 8, 1, 10, 0, tzinfo=UTC),
            completed_at=datetime(2026, 8, 1, 10, 1, tzinfo=UTC),
        )
    )
    session.commit()
    return execution


def test_hunt_execution_json_export_is_lossless_backend_representation(
    client: TestClient,
    hunt_export_user: User,
    hunt_export_execution: HuntExecution,
):
    app.dependency_overrides[get_current_user] = lambda: hunt_export_user

    response = client.get(
        f"{settings.API_V1_STR}/hunts/executions/{hunt_export_execution.id}/export",
        params={"format": "json"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["content-disposition"] == (
        f'attachment; filename="hunt-execution-{hunt_export_execution.id}-person_hunt.json"'
    )
    payload = response.json()
    assert payload["export_version"] == "1.0"
    assert payload["timestamp"].endswith("+00:00")
    assert payload["execution"]["id"] == hunt_export_execution.id
    assert payload["execution"]["hunt"]["display_name"] == "Person Discovery"
    assert payload["execution"]["case"] == {
        "id": hunt_export_execution.case_id,
        "title": "International enquiry",
        "case_number": "CASE-042",
    }
    assert payload["execution"]["created_by"]["username"] == "hunt-exporter"
    assert payload["execution"]["steps"][0]["output"] == {
        "results": [{"finding": "München Москва"}],
        "result_count": 1,
        "plugin": "PeopleData",
        "errors": [{"message": "Remote source timed out"}],
    }


def test_hunt_execution_pdf_is_a_readable_standalone_report(
    client: TestClient,
    hunt_export_user: User,
    hunt_export_execution: HuntExecution,
):
    app.dependency_overrides[get_current_user] = lambda: hunt_export_user

    response = client.get(
        f"{settings.API_V1_STR}/hunts/executions/{hunt_export_execution.id}/export",
        params={"format": "pdf"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == (
        f'attachment; filename="hunt-execution-{hunt_export_execution.id}-person_hunt.pdf"'
    )
    assert response.content.startswith(b"%PDF")
    reader = PdfReader(BytesIO(response.content))
    assert len(reader.pages) >= 1
    text = "\n".join(page.extract_text() for page in reader.pages)
    for expected in (
        "Person Discovery",
        f"Execution #{hunt_export_execution.id}",
        "CASE-042",
        "lookup-person",
        "PeopleData",
        "España",
        "Remote source timed out",
        "München Москва",
        "Profile",
        "People",
        "Page 1",
    ):
        assert expected in text
    assert "Full output is available in the JSON export" not in text


def test_hunt_execution_pdf_truncates_oversized_step_output(
    client: TestClient,
    session: Session,
    hunt_export_user: User,
    hunt_export_execution: HuntExecution,
):
    step = session.exec(
        select(HuntStep).where(HuntStep.execution_id == hunt_export_execution.id)
    ).one()
    step.output = {"large_result": "x" * (33 * 1024)}
    session.add(step)
    session.commit()
    app.dependency_overrides[get_current_user] = lambda: hunt_export_user

    response = client.get(
        f"{settings.API_V1_STR}/hunts/executions/{hunt_export_execution.id}/export",
        params={"format": "pdf"},
    )

    text = "\n".join(
        page.extract_text() for page in PdfReader(BytesIO(response.content)).pages
    )
    assert "Output truncated" in text
    assert "Full output is available in the JSON export" in text


def test_cancelled_execution_without_steps_still_exports_as_pdf(
    client: TestClient,
    session: Session,
    hunt_export_user: User,
    hunt_export_execution: HuntExecution,
):
    step = session.exec(
        select(HuntStep).where(HuntStep.execution_id == hunt_export_execution.id)
    ).one()
    session.delete(step)
    hunt_export_execution.status = "cancelled"
    session.add(hunt_export_execution)
    session.commit()
    app.dependency_overrides[get_current_user] = lambda: hunt_export_user

    response = client.get(
        f"{settings.API_V1_STR}/hunts/executions/{hunt_export_execution.id}/export",
        params={"format": "pdf"},
    )

    assert response.status_code == 200
    text = "\n".join(
        page.extract_text() for page in PdfReader(BytesIO(response.content)).pages
    )
    assert "cancelled" in text
    assert "No steps recorded" in text


@pytest.mark.parametrize(
    "execution_status",
    ["pending", "running", "completed", "partial", "failed", "cancelled"],
)
def test_hunt_execution_json_export_supports_every_execution_status(
    execution_status: str,
    client: TestClient,
    session: Session,
    hunt_export_user: User,
    hunt_export_execution: HuntExecution,
):
    hunt_export_execution.status = execution_status
    session.add(hunt_export_execution)
    session.commit()
    app.dependency_overrides[get_current_user] = lambda: hunt_export_user

    response = client.get(
        f"{settings.API_V1_STR}/hunts/executions/{hunt_export_execution.id}/export",
        params={"format": "json"},
    )

    assert response.status_code == 200
    assert response.json()["execution"]["status"] == execution_status


def test_hunt_execution_export_validates_format_and_missing_execution(
    client: TestClient,
    hunt_export_user: User,
    hunt_export_execution: HuntExecution,
):
    app.dependency_overrides[get_current_user] = lambda: hunt_export_user
    url = f"{settings.API_V1_STR}/hunts/executions/{hunt_export_execution.id}/export"

    assert client.get(url).status_code == 422
    assert client.get(url, params={"format": "xml"}).status_code == 422
    assert (
        client.get(
            f"{settings.API_V1_STR}/hunts/executions/999999/export",
            params={"format": "json"},
        ).status_code
        == 404
    )


def test_hunt_execution_export_enforces_role_and_case_access(
    client: TestClient,
    session: Session,
    hunt_export_execution: HuntExecution,
):
    case = session.get(Case, hunt_export_execution.case_id)
    analyst = User(
        username="hunt-analyst",
        email="hunt-analyst@example.com",
        password_hash="unused",
        role="Analyst",
    )
    outsider = User(
        username="hunt-outsider",
        email="hunt-outsider@example.com",
        password_hash="unused",
        role="Investigator",
    )
    admin = User(
        username="hunt-admin",
        email="hunt-admin@example.com",
        password_hash="unused",
        role="Admin",
    )
    session.add_all([analyst, outsider, admin])
    session.commit()
    session.refresh(analyst)
    session.add(CaseUserLink(case_id=case.id, user_id=analyst.id))
    session.commit()
    url = f"{settings.API_V1_STR}/hunts/executions/{hunt_export_execution.id}/export"

    app.dependency_overrides[get_current_user] = lambda: analyst
    analyst_response = client.get(url, params={"format": "json"})
    app.dependency_overrides[get_current_user] = lambda: outsider
    outsider_response = client.get(url, params={"format": "json"})
    app.dependency_overrides[get_current_user] = lambda: admin
    admin_response = client.get(url, params={"format": "json"})

    assert analyst_response.status_code == 200
    assert outsider_response.status_code == 403
    assert admin_response.status_code == 200


def test_hunt_execution_export_requires_authentication(
    client: TestClient,
    hunt_export_execution: HuntExecution,
):
    response = client.get(
        f"{settings.API_V1_STR}/hunts/executions/{hunt_export_execution.id}/export",
        params={"format": "json"},
    )

    assert response.status_code == 401
