"""HTTP-level coverage for complete case ZIP exports."""

import csv
import io
import json
import tempfile
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlmodel import Session

from app.core import file_storage
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.database.models import (
    Case,
    CaseUserLink,
    Client,
    Entity,
    Evidence,
    Hunt,
    HuntExecution,
    HuntStep,
    Task,
    TaskTemplate,
    User,
)
from app.main import app
from app.services.hunt_execution_export import (
    HuntExecutionExportFormat,
    RenderedHuntExecutionExport,
)


@pytest.fixture
def case_export_user(session: Session) -> User:
    user = User(
        username="case-exporter",
        email="case-exporter@example.com",
        password_hash="unused",
        role="Investigator",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def case_export_case(session: Session, case_export_user: User) -> Case:
    client = Client(name="Acme International")
    session.add(client)
    session.commit()
    session.refresh(client)
    case = Case(
        client_id=client.id,
        case_number="CASE / 003",
        title="Sparse export",
        status="Closed",
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    session.add(
        CaseUserLink(case_id=case.id, user_id=case_export_user.id, is_lead=True)
    )
    session.commit()
    return case


def test_sparse_closed_case_exports_as_a_self_describing_zip(
    client: TestClient,
    case_export_user: User,
    case_export_case: Case,
    tmp_path,
    monkeypatch,
):
    app.dependency_overrides[get_current_user] = lambda: case_export_user
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))

    response = client.get(f"{settings.API_V1_STR}/cases/{case_export_case.id}/export")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["content-disposition"].startswith(
        'attachment; filename="CASE-003-export-'
    )
    assert response.headers["content-disposition"].endswith('.zip"')

    archive_path = tmp_path / "download.zip"
    archive_path.write_bytes(response.content)
    with ZipFile(archive_path) as archive:
        assert archive.namelist() == [
            "CASE-003/case.json",
            "CASE-003/entities/entities.json",
            "CASE-003/evidence/manifest.json",
            "CASE-003/tasks/tasks.json",
            "CASE-003/tasks/tasks.csv",
            "CASE-003/hunts/executions.json",
        ]
        assert all(
            member.compress_type == ZIP_DEFLATED for member in archive.infolist()
        )
        metadata = json.loads(archive.read("CASE-003/case.json"))
        assert metadata["id"] == case_export_case.id
        assert metadata["case_number"] == "CASE / 003"
        assert metadata["title"] == "Sparse export"
        assert metadata["status"] == "Closed"
        assert metadata["client"] == {
            "id": case_export_case.client_id,
            "name": "Acme International",
        }
        assert metadata["users"] == [
            {
                "username": "case-exporter",
                "role": "Investigator",
                "is_lead": True,
            }
        ]
        assert metadata["exported_at"].endswith("+00:00")
        assert metadata["exported_by"] == "case-exporter"
        assert json.loads(archive.read("CASE-003/entities/entities.json")) == []
        assert json.loads(archive.read("CASE-003/evidence/manifest.json")) == []
        assert json.loads(archive.read("CASE-003/tasks/tasks.json")) == []
        assert json.loads(archive.read("CASE-003/hunts/executions.json")) == []

    assert list(tmp_path.glob("owlculus-case-export-*.zip")) == []


def test_case_bundle_composes_notes_entities_tasks_and_hunts(
    client: TestClient,
    session: Session,
    case_export_user: User,
    case_export_case: Case,
):
    case_export_case.notes = "<p>Investigation notes — 東京</p>"
    person = Entity(
        case_id=case_export_case.id,
        entity_type="person",
        data={"first_name": "Zoë", "last_name": "Ng", "email": "zoe@example.com"},
        created_by_id=case_export_user.id,
    )
    domain = Entity(
        case_id=case_export_case.id,
        entity_type="domain",
        data={"domain": "example.test", "description": "Test domain"},
        created_by_id=case_export_user.id,
    )
    template = TaskTemplate(
        name="verify-source",
        display_name="Verify source",
        description="Verify a source",
        category="Investigation",
        definition_json={},
        created_by_id=case_export_user.id,
    )
    hunt = Hunt(
        name="person_hunt",
        display_name="Person Hunt",
        description="Find a person",
        category="person",
        definition_json={"steps": []},
    )
    session.add_all([person, domain, template, hunt])
    session.commit()
    session.refresh(template)
    session.refresh(hunt)
    task = Task(
        case_id=case_export_case.id,
        template_id=template.id,
        title="Validate finding",
        description="Check the source",
        priority="High",
        status="Completed",
        assigned_to_id=case_export_user.id,
        assigned_by_id=case_export_user.id,
        due_date=datetime(2026, 9, 10, tzinfo=UTC),
        completed_at=datetime(2026, 9, 2, tzinfo=UTC),
        completed_by_id=case_export_user.id,
        custom_fields={"source": "東京"},
    )
    execution = HuntExecution(
        hunt_id=hunt.id,
        case_id=case_export_case.id,
        status="completed",
        progress=1,
        initial_parameters={"name": "Zoë"},
        created_by_id=case_export_user.id,
    )
    session.add_all([task, execution])
    session.commit()
    session.refresh(execution)
    session.add(
        HuntStep(
            execution_id=execution.id,
            step_id="search-person",
            plugin_name="PeopleSearch",
            status="completed",
            parameters={"country": "日本"},
            output={"result": "found"},
        )
    )
    session.commit()
    app.dependency_overrides[get_current_user] = lambda: case_export_user

    response = client.get(f"{settings.API_V1_STR}/cases/{case_export_case.id}/export")

    assert response.status_code == 200
    with ZipFile(BytesIO(response.content)) as archive:
        root = "CASE-003"
        assert archive.read(f"{root}/notes.html").decode() == case_export_case.notes
        entity_records = json.loads(archive.read(f"{root}/entities/entities.json"))
        assert [record["data"] for record in entity_records] == [
            person.data,
            domain.data,
        ]
        person_rows = list(
            csv.DictReader(
                io.StringIO(
                    archive.read(f"{root}/entities/person.csv").decode("utf-8-sig")
                )
            )
        )
        domain_rows = list(
            csv.DictReader(
                io.StringIO(
                    archive.read(f"{root}/entities/domain.csv").decode("utf-8-sig")
                )
            )
        )
        assert person_rows[0]["display_name"] == "Zoë Ng"
        assert person_rows[0]["email"] == "zoe@example.com"
        assert "description" not in person_rows[0]
        assert domain_rows[0]["domain"] == "example.test"
        assert domain_rows[0]["description"] == "Test domain"
        assert "first_name" not in domain_rows[0]

        task_records = json.loads(archive.read(f"{root}/tasks/tasks.json"))
        assert task_records[0]["title"] == "Validate finding"
        assert task_records[0]["custom_fields"] == {"source": "東京"}
        task_rows = list(
            csv.DictReader(
                io.StringIO(archive.read(f"{root}/tasks/tasks.csv").decode())
            )
        )
        assert list(task_rows[0]) == [
            "id",
            "title",
            "description",
            "status",
            "priority",
            "assigned_to",
            "assigned_by",
            "due_date",
            "completed_at",
            "completed_by",
            "template",
            "custom_fields",
            "created_at",
            "updated_at",
        ]
        assert task_rows[0]["assigned_to"] == "case-exporter"
        assert task_rows[0]["assigned_by"] == "case-exporter"
        assert task_rows[0]["completed_by"] == "case-exporter"
        assert task_rows[0]["template"] == "verify-source"
        assert json.loads(task_rows[0]["custom_fields"]) == {"source": "東京"}

        executions = json.loads(archive.read(f"{root}/hunts/executions.json"))
        assert executions[0]["hunt_display_name"] == "Person Hunt"
        hunt_root = f"{root}/hunts/{execution.id}-person_hunt"
        execution_export = json.loads(archive.read(f"{hunt_root}/execution.json"))
        assert execution_export["export_version"] == "1.0"
        assert execution_export["execution"]["steps"][0]["output"] == {
            "result": "found"
        }
        pdf = archive.read(f"{hunt_root}/execution.pdf")
        assert pdf.startswith(b"%PDF")
        pdf_text = "\n".join(
            page.extract_text() for page in PdfReader(BytesIO(pdf)).pages
        )
        assert "Person Hunt" in pdf_text
        assert "PeopleSearch" in pdf_text


def test_case_bundle_preserves_the_evidence_tree_and_records_missing_files(
    client: TestClient,
    session: Session,
    case_export_user: User,
    case_export_case: Case,
):
    original_bytes = b"\x00original evidence\xff"
    stored_file = (
        file_storage.UPLOAD_DIR
        / str(case_export_case.id)
        / "Reports"
        / "Screens"
        / "original.bin"
    )
    stored_file.parent.mkdir(parents=True)
    stored_file.write_bytes(original_bytes)
    evidence_records = [
        Evidence(
            case_id=case_export_case.id,
            title="Reports",
            description="Reports folder",
            evidence_type="folder",
            category="Other",
            content="",
            folder_path="Reports",
            is_folder=True,
            created_by_id=case_export_user.id,
        ),
        Evidence(
            case_id=case_export_case.id,
            title="Screens",
            evidence_type="folder",
            category="Other",
            content="",
            folder_path="Reports/Screens",
            is_folder=True,
            created_by_id=case_export_user.id,
        ),
        Evidence(
            case_id=case_export_case.id,
            title="Empty",
            evidence_type="folder",
            category="Other",
            content="",
            folder_path="Empty",
            is_folder=True,
            created_by_id=case_export_user.id,
        ),
        Evidence(
            case_id=case_export_case.id,
            title="original.bin",
            description="Binary source",
            evidence_type="file",
            category="Documents",
            content=f"{case_export_case.id}/Reports/Screens/original.bin",
            file_hash=sha256(original_bytes).hexdigest(),
            folder_path="Reports/Screens",
            created_by_id=case_export_user.id,
        ),
        Evidence(
            case_id=case_export_case.id,
            title="Interview 東京",
            evidence_type="text",
            category="Communications",
            content="Witness account — naïve café",
            folder_path="Reports",
            created_by_id=case_export_user.id,
        ),
        Evidence(
            case_id=case_export_case.id,
            title="missing.pdf",
            evidence_type="file",
            category="Documents",
            content=f"{case_export_case.id}/Reports/missing.pdf",
            file_hash="0" * 64,
            folder_path="Reports",
            created_by_id=case_export_user.id,
        ),
    ]
    session.add_all(evidence_records)
    session.commit()
    app.dependency_overrides[get_current_user] = lambda: case_export_user

    with patch("app.services.export_service.get_security_logger") as logger_factory:
        response = client.get(
            f"{settings.API_V1_STR}/cases/{case_export_case.id}/export"
        )

    assert response.status_code == 200
    with ZipFile(BytesIO(response.content)) as archive:
        root = "CASE-003/evidence"
        assert f"{root}/Reports/" in archive.namelist()
        assert f"{root}/Reports/Screens/" in archive.namelist()
        assert f"{root}/Empty/" in archive.namelist()
        stored_member = f"{root}/Reports/Screens/original.bin"
        assert archive.read(stored_member) == original_bytes
        assert archive.getinfo(stored_member).compress_type == 0
        text_member = f"{root}/Reports/Interview 東京.txt"
        assert (
            archive.read(text_member).decode("utf-8") == "Witness account — naïve café"
        )
        assert f"{root}/Reports/missing.pdf" not in archive.namelist()

        manifest = json.loads(archive.read(f"{root}/manifest.json"))
        assert len(manifest) == len(evidence_records)
        existing_file = next(
            item for item in manifest if item["title"] == "original.bin"
        )
        assert existing_file == {
            "id": evidence_records[3].id,
            "title": "original.bin",
            "description": "Binary source",
            "category": "Documents",
            "evidence_type": "file",
            "folder_path": "Reports/Screens",
            "file_name": "original.bin",
            "file_hash": sha256(original_bytes).hexdigest(),
            "is_folder": False,
            "parent_folder_id": None,
            "created_by": "case-exporter",
            "created_at": existing_file["created_at"],
            "updated_at": existing_file["updated_at"],
            "exported": True,
        }
        missing_file = next(item for item in manifest if item["title"] == "missing.pdf")
        assert missing_file["exported"] is False
        assert missing_file["reason"] == "File not found on disk"
    logger_factory.return_value.warning.assert_called_once_with(
        "Case export evidence file not found on disk"
    )


def test_analyst_case_bundle_omits_hunts(
    client: TestClient,
    session: Session,
    case_export_case: Case,
):
    analyst = User(
        username="case-analyst",
        email="case-analyst@example.com",
        password_hash="unused",
        role="Analyst",
    )
    session.add(analyst)
    session.commit()
    session.refresh(analyst)
    session.add(CaseUserLink(case_id=case_export_case.id, user_id=analyst.id))
    session.commit()
    app.dependency_overrides[get_current_user] = lambda: analyst

    response = client.get(f"{settings.API_V1_STR}/cases/{case_export_case.id}/export")

    assert response.status_code == 200
    with ZipFile(BytesIO(response.content)) as archive:
        assert not any(
            name.startswith("CASE-003/hunts/") for name in archive.namelist()
        )


def test_case_bundle_enforces_case_access(
    client: TestClient,
    session: Session,
    case_export_case: Case,
):
    unassigned_user = User(
        username="unassigned",
        email="unassigned@example.com",
        password_hash="unused",
        role="Investigator",
    )
    unassigned_admin = User(
        username="unassigned-admin",
        email="unassigned-admin@example.com",
        password_hash="unused",
        role="Admin",
    )
    session.add_all([unassigned_user, unassigned_admin])
    session.commit()

    app.dependency_overrides[get_current_user] = lambda: unassigned_user
    assert (
        client.get(
            f"{settings.API_V1_STR}/cases/{case_export_case.id}/export"
        ).status_code
        == 403
    )

    app.dependency_overrides[get_current_user] = lambda: unassigned_admin
    assert (
        client.get(
            f"{settings.API_V1_STR}/cases/{case_export_case.id}/export"
        ).status_code
        == 200
    )
    assert client.get(f"{settings.API_V1_STR}/cases/999999/export").status_code == 404


def test_case_bundle_requires_authentication(
    client: TestClient, case_export_case: Case
):
    response = client.get(f"{settings.API_V1_STR}/cases/{case_export_case.id}/export")

    assert response.status_code == 401


def test_case_bundle_logs_the_export_event(
    client: TestClient,
    case_export_user: User,
    case_export_case: Case,
):
    app.dependency_overrides[get_current_user] = lambda: case_export_user

    with patch("app.services.export_service.get_security_logger") as logger_factory:
        response = client.get(
            f"{settings.API_V1_STR}/cases/{case_export_case.id}/export"
        )

    assert response.status_code == 200
    assert any(
        call.kwargs.get("case_id") == case_export_case.id
        and call.kwargs.get("export_kind") == "case"
        and call.kwargs.get("requesting_user") == "case-exporter"
        for call in logger_factory.call_args_list
    )


def test_case_bundle_pdf_failure_returns_500_logs_and_removes_the_temp_file(
    client: TestClient,
    session: Session,
    case_export_user: User,
    case_export_case: Case,
    tmp_path,
    monkeypatch,
):
    hunt = Hunt(
        name="failing_hunt",
        display_name="Failing Hunt",
        description="Rendering fails",
        category="person",
        definition_json={"steps": []},
    )
    session.add(hunt)
    session.commit()
    session.refresh(hunt)
    session.add(
        HuntExecution(
            hunt_id=hunt.id,
            case_id=case_export_case.id,
            status="failed",
            progress=0,
            initial_parameters={},
            created_by_id=case_export_user.id,
        )
    )
    session.commit()
    app.dependency_overrides[get_current_user] = lambda: case_export_user
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    rendered_json = RenderedHuntExecutionExport(
        content=b"{}", media_type="application/json"
    )

    with (
        patch(
            "app.services.export_service.render_hunt_execution",
            side_effect=[rendered_json, RuntimeError("PDF render failed")],
        ) as render,
        patch("app.services.export_service.get_security_logger") as logger_factory,
        TestClient(app, raise_server_exceptions=False) as tolerant_client,
    ):
        response = tolerant_client.get(
            f"{settings.API_V1_STR}/cases/{case_export_case.id}/export"
        )

    assert response.status_code == 500
    assert [call.args[2] for call in render.call_args_list] == [
        HuntExecutionExportFormat.JSON,
        HuntExecutionExportFormat.PDF,
    ]
    logger_factory.return_value.bind.assert_any_call(
        event_type="export_generation_failed"
    )
    logger_factory.return_value.bind.return_value.exception.assert_called_once_with(
        "Case export failed"
    )
    assert list(tmp_path.glob("owlculus-case-export-*.zip")) == []
