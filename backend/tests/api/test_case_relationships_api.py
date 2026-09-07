"""Case relationship regressions through real login and fresh HTTP sessions."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api import auth, cases, evidence, tasks, users
from app.core import file_storage
from app.core.exception_handler import handle_domain_exception
from app.core.exceptions import BaseException as DomainException
from app.core.security import get_password_hash
from app.database.connection import get_db
from app.database.models import Case, CaseUserLink, User


@pytest.fixture
def relationship_api(engine, tmp_path, monkeypatch):
    monkeypatch.setattr(file_storage, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(
        "app.services.evidence_service.UPLOAD_DIR", tmp_path / "uploads"
    )
    password_hash = get_password_hash("relationship-pass")
    with Session(engine) as db:
        people = {}
        for name, role in [
            ("lead", "Investigator"),
            ("reader", "Analyst"),
            ("outsider", "Investigator"),
            ("admin", "Admin"),
        ]:
            person = User(
                username=name,
                email=f"{name}@private.test",
                role=role,
                password_hash=password_hash,
                is_active=True,
            )
            db.add(person)
            db.flush()
            people[name] = person.id
        case_ids = []
        for number in ("A", "B"):
            case = Case(case_number=number, name=number, created_by_id=people["admin"])
            db.add(case)
            db.flush()
            case_ids.append(case.id)
        for name in ("lead", "reader"):
            db.add(
                CaseUserLink(
                    case_id=case_ids[0], user_id=people[name], is_lead=name == "lead"
                )
            )
        db.commit()

    def request_db():
        with Session(engine) as db:
            yield db

    api = FastAPI()
    api.add_exception_handler(DomainException, handle_domain_exception)
    for module, prefix in [
        (auth, "auth"),
        (cases, "cases"),
        (evidence, "evidence"),
        (tasks, "tasks"),
        (users, "users"),
    ]:
        api.include_router(module.router, prefix=f"/api/{prefix}")
    api.dependency_overrides[get_db] = request_db
    with TestClient(api) as client:
        headers = {}
        for name in people:
            response = client.post(
                "/api/auth/login",
                data={"username": name, "password": "relationship-pass"},
            )
            assert response.status_code == 200
            headers[name] = {
                "Authorization": f"Bearer {response.json()['access_token']}"
            }
        yield client, headers, people, case_ids, tmp_path / "uploads"


def test_task_create_rejects_outsider_without_profile_disclosure(relationship_api):
    client, headers, people, (case_a, case_b), _ = relationship_api
    assert (
        client.get(f"/api/cases/{case_b}", headers=headers["lead"]).status_code == 403
    )
    assert client.get("/api/users/", headers=headers["lead"]).status_code == 403
    response = client.post(
        "/api/tasks/",
        headers=headers["lead"],
        json={
            "case_id": case_a,
            "title": "Investigate",
            "description": "Original",
            "assigned_to_id": people["outsider"],
        },
    )
    assert response.status_code == 403
    assert "outsider" not in response.text
    assert (
        client.get(f"/api/tasks/?case_id={case_a}", headers=headers["lead"]).json()
        == []
    )


@pytest.mark.parametrize("actor", ["lead", "admin"])
@pytest.mark.parametrize(
    "route", ["folder_create", "folder_update", "upload", "evidence_update"]
)
@pytest.mark.parametrize("parent_kind", ["foreign", "missing", "nonfolder"])
def test_invalid_evidence_parent_has_no_effect(
    relationship_api, actor, route, parent_kind
):
    client, headers, _, (case_a, case_b), storage = relationship_api
    foreign = client.post(
        "/api/evidence/folders",
        headers=headers["admin"],
        json={
            "case_id": case_b,
            "title": "confidential-foreign-folder",
        },
    ).json()
    local = client.post(
        "/api/evidence/folders",
        headers=headers["lead"],
        json={
            "case_id": case_a,
            "title": "local-folder",
        },
    ).json()
    upload = client.post(
        f"/api/evidence/?title=file&case_id={case_a}&category=Other",
        headers=headers["lead"],
        data={"parent_folder_id": local["id"]},
        files={"files": ("original.txt", b"investigation contents")},
    )
    file_record = upload.json()["created"][0]
    parent_id = {
        "foreign": foreign["id"],
        "missing": 999999,
        "nonfolder": file_record["id"],
    }[parent_kind]
    before = {
        p.relative_to(storage): p.read_bytes() if p.is_file() else None
        for p in storage.rglob("*")
    }
    before_records = client.get(
        f"/api/evidence/case/{case_a}", headers=headers["lead"]
    ).json()
    if route == "folder_create":
        response = client.post(
            "/api/evidence/folders",
            headers=headers[actor],
            json={"case_id": case_a, "title": "attack", "parent_folder_id": parent_id},
        )
    elif route == "upload":
        response = client.post(
            f"/api/evidence/?title=file&case_id={case_a}&category=Other",
            headers=headers[actor],
            data={"parent_folder_id": parent_id},
            files={"files": ("attack.txt", b"new data")},
        )
    else:
        path = (
            f"/api/evidence/folders/{local['id']}"
            if route == "folder_update"
            else f"/api/evidence/{file_record['id']}"
        )
        response = client.put(
            path,
            headers=headers[actor],
            json={
                "title": "attack",
                "description": "changed",
                "parent_folder_id": parent_id,
            },
        )
    if route == "upload" and parent_kind != "missing":
        assert response.status_code == 201
        assert response.json()["created"] == []
        assert response.json()["failed"][0]["error"] == "Invalid parent folder"
    else:
        assert response.status_code == (404 if parent_kind == "missing" else 422)
    assert "confidential-foreign-folder" not in response.text
    assert (
        client.get(f"/api/evidence/case/{case_a}", headers=headers["lead"]).json()
        == before_records
    )
    assert {
        p.relative_to(storage): p.read_bytes() if p.is_file() else None
        for p in storage.rglob("*")
    } == before


@pytest.mark.parametrize("route", ["create", "update", "assign", "bulk"])
@pytest.mark.parametrize("assignee", ["reader", "outsider", "admin", "missing", "zero"])
def test_assignment_routes_share_eligibility(relationship_api, route, assignee):
    client, headers, people, (case_a, _), _ = relationship_api
    original = client.post(
        "/api/tasks/",
        headers=headers["lead"],
        json={
            "case_id": case_a,
            "title": "Investigate",
            "description": "Original",
            "assigned_to_id": people["lead"],
            "custom_fields": {"kept": "original"},
        },
    ).json()
    task_id = original["id"]
    user_id = {**people, "missing": 999999, "zero": 0}[assignee]
    changes = {
        "description": "Changed",
        "status": "completed",
        "custom_fields": {"injected": "changed"},
        "assigned_to_id": user_id,
    }
    if route == "create":
        response = client.post(
            "/api/tasks/",
            headers=headers["lead"],
            json={"case_id": case_a, "title": "Second", **changes},
        )
    elif route == "update":
        response = client.put(
            f"/api/tasks/{task_id}", headers=headers["lead"], json=changes
        )
    elif route == "assign":
        response = client.post(
            f"/api/tasks/{task_id}/assign?user_id={user_id}", headers=headers["lead"]
        )
    else:
        response = client.post(
            "/api/tasks/bulk/assign",
            headers=headers["lead"],
            json={"task_ids": [task_id], "user_id": user_id},
        )
    if assignee in ("reader", "admin"):
        assert response.status_code == 200
        result = response.json()[0] if route == "bulk" else response.json()
        assert result["assigned_to"]["id"] == user_id
        assert result["assigned_to"]["username"] == assignee
        assert (
            client.get(
                f"/api/tasks/{result['id']}", headers=headers["reader"]
            ).status_code
            == 200
        )
        assert (
            client.put(
                f"/api/tasks/{result['id']}/status?status=completed",
                headers=headers["reader"],
            ).status_code
            == 403
        )
    else:
        if route == "bulk":
            assert response.status_code == 200
            assert response.json() == []  # Established best-effort bulk contract.
        else:
            assert response.status_code == (403 if assignee == "outsider" else 404)
        assert "outsider" not in response.text
        assert "private.test" not in response.text
        assert (
            client.get(f"/api/tasks/{task_id}", headers=headers["lead"]).json()
            == original
        )
        assert (
            len(
                client.get(
                    f"/api/tasks/?case_id={case_a}", headers=headers["lead"]
                ).json()
            )
            == 1
        )


def test_legacy_task_assignee_is_hidden_on_reads_and_writes(relationship_api, engine):
    from app.database.models import Task

    client, headers, people, (case_a, _), _ = relationship_api
    with Session(engine) as db:
        task = Task(
            case_id=case_a,
            title="Historical",
            description="Keep history",
            assigned_by_id=people["lead"],
            assigned_to_id=people["outsider"],
        )
        db.add(task)
        db.commit()
        task_id = task.id
    responses = [
        client.get(f"/api/tasks/{task_id}", headers=headers["lead"]),
        client.get(f"/api/tasks/?case_id={case_a}", headers=headers["reader"]),
        client.put(
            f"/api/tasks/{task_id}",
            headers=headers["lead"],
            json={"description": "Still useful"},
        ),
        client.put(
            f"/api/tasks/{task_id}/status?status=completed", headers=headers["lead"]
        ),
        client.post(
            "/api/tasks/bulk/status",
            headers=headers["lead"],
            json={"task_ids": [task_id], "status": "in_progress"},
        ),
    ]
    for response in responses:
        assert response.status_code == 200
        result = (
            response.json()[0] if isinstance(response.json(), list) else response.json()
        )
        assert result["assigned_to"] is None
        assert result["assigned_to_id"] is None
        assert "outsider" not in response.text


def test_legacy_relationships_are_safe_and_upgrade_preserves_data(
    relationship_api, engine
):
    import io
    import json
    import zipfile

    from app.database.init_db import initialize_database
    from app.database.models import Evidence, Task
    from app.database.upgrade_case_relationships import upgrade

    client, headers, people, (case_a, case_b), storage = relationship_api
    foreign = client.post(
        "/api/evidence/folders",
        headers=headers["admin"],
        json={"case_id": case_b, "title": "foreign-parent"},
    ).json()
    local = client.post(
        "/api/evidence/folders",
        headers=headers["lead"],
        json={"case_id": case_a, "title": "local-history"},
    ).json()
    uploaded = client.post(
        f"/api/evidence/?title=file&case_id={case_a}&category=Other",
        headers=headers["lead"],
        data={"parent_folder_id": local["id"]},
        files={"files": ("preserved.txt", b"valuable investigation data")},
    ).json()["created"][0]
    with Session(engine) as db:
        folder = db.get(Evidence, local["id"])
        folder.parent_folder_id = foreign["id"]
        task = Task(
            case_id=case_a,
            title="Historical task",
            description="Keep history",
            assigned_by_id=people["lead"],
            assigned_to_id=people["outsider"],
            custom_fields={"history": "preserved"},
        )
        db.add(task)
        db.commit()
        task_id = task.id
    before_files = {
        p.relative_to(storage): p.read_bytes() if p.is_file() else None
        for p in storage.rglob("*")
    }
    # An apparently local parent must not expand its invalid historical ancestry.
    response = client.post(
        "/api/evidence/folders",
        headers=headers["lead"],
        json={"case_id": case_a, "title": "new-child", "parent_folder_id": local["id"]},
    )
    assert response.status_code == 422
    for path in [
        f"/api/evidence/{local['id']}",
        f"/api/evidence/case/{case_a}",
        f"/api/evidence/case/{case_a}/folder-tree",
    ]:
        response = client.get(path, headers=headers["lead"])
        assert response.status_code == 200
        rows = (
            response.json() if isinstance(response.json(), list) else [response.json()]
        )
        assert all(row["parent_folder_id"] is None for row in rows)
    response = client.put(
        f"/api/evidence/folders/{local['id']}",
        headers=headers["lead"],
        json={"description": "Still useful"},
    )
    assert response.json()["parent_folder_id"] is None
    bundle = client.get(f"/api/cases/{case_a}/export", headers=headers["lead"])
    assert bundle.status_code == 200
    with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
        task_path = next(
            name for name in archive.namelist() if name.endswith("tasks.json")
        )
        assert json.loads(archive.read(task_path))[0]["assigned_to"] is None
        assert b"outsider" not in archive.read(task_path)
    for normalize in (upgrade, upgrade, initialize_database):
        normalize(engine)
        response = client.get(f"/api/evidence/{local['id']}", headers=headers["lead"])
        assert response.json()["parent_folder_id"] is None
        assert response.json()["title"] == "local-history"
        task = client.get(f"/api/tasks/{task_id}", headers=headers["lead"]).json()
        assert task["assigned_to"] is None
        assert task["custom_fields"] == {"history": "preserved"}
        assert task["description"] == "Keep history"
        download = client.get(
            f"/api/evidence/{uploaded['id']}/download", headers=headers["lead"]
        )
        assert download.status_code == 200
        assert download.content == b"valuable investigation data"
        assert {
            p.relative_to(storage): p.read_bytes() if p.is_file() else None
            for p in storage.rglob("*")
        } == before_files
        with Session(engine) as db:
            assert db.get(Evidence, local["id"]).parent_folder_id is None
            assert db.get(Task, task_id).assigned_to_id is None
            assert db.get(Evidence, foreign["id"]).title == "foreign-parent"


def test_valid_nesting_omission_and_unassignment_remain_available(relationship_api):
    client, headers, people, (case_a, _), _ = relationship_api
    root = client.post(
        "/api/evidence/folders",
        headers=headers["lead"],
        json={"case_id": case_a, "title": "Root"},
    ).json()
    nested = client.post(
        "/api/evidence/folders",
        headers=headers["lead"],
        json={"case_id": case_a, "title": "Nested", "parent_folder_id": root["id"]},
    ).json()
    assert nested["folder_path"] == "Root/Nested"
    assert nested["parent_folder_id"] == root["id"]
    response = client.put(
        f"/api/evidence/folders/{nested['id']}",
        headers=headers["lead"],
        json={"description": "Updated", "parent_folder_id": None},
    )
    assert response.status_code == 200
    assert response.json()["parent_folder_id"] == root["id"]
    uploaded = client.post(
        f"/api/evidence/?title=file&case_id={case_a}&category=Other",
        headers=headers["lead"],
        data={"parent_folder_id": nested["id"], "folder_path": nested["folder_path"]},
        files={"files": ("valid.txt", b"valid contents")},
    ).json()["created"][0]
    response = client.put(
        f"/api/evidence/{uploaded['id']}",
        headers=headers["lead"],
        json={"parent_folder_id": root["id"]},
    )
    assert response.status_code == 200
    assert response.json()["parent_folder_id"] == root["id"]
    assert (
        client.get(
            f"/api/evidence/{uploaded['id']}/download", headers=headers["reader"]
        ).content
        == b"valid contents"
    )
    assert (
        client.get(
            f"/api/evidence/{uploaded['id']}/download", headers=headers["outsider"]
        ).status_code
        == 403
    )
    task = client.post(
        "/api/tasks/",
        headers=headers["lead"],
        json={
            "case_id": case_a,
            "title": "Valid",
            "description": "Original",
            "assigned_to_id": people["reader"],
        },
    ).json()
    response = client.put(
        f"/api/tasks/{task['id']}",
        headers=headers["lead"],
        json={"description": "Updated", "assigned_to_id": None},
    )
    assert response.json()["assigned_to_id"] == people["reader"]
    response = client.post(f"/api/tasks/{task['id']}/assign", headers=headers["lead"])
    assert response.json()["assigned_to"] is None
    assert response.json()["assigned_to_id"] is None
    client.post(
        f"/api/tasks/{task['id']}/assign?user_id={people['admin']}",
        headers=headers["lead"],
    )
    response = client.post(
        "/api/tasks/bulk/assign",
        headers=headers["lead"],
        json={"task_ids": [task["id"]]},
    )
    assert response.json()[0]["assigned_to_id"] is None
