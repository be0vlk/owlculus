"""API coverage for complete entity CSV and JSON exports."""

import csv
import io
import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.database.models import Case, CaseUserLink, Entity, User
from app.main import app


@pytest.fixture
def export_user_factory(session: Session):
    def create_user(username: str, role: str) -> User:
        user = User(
            username=username,
            email=f"{username}@example.com",
            password_hash="unused",
            role=role,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    return create_user


@pytest.fixture
def export_admin(export_user_factory) -> User:
    return export_user_factory("export-admin", "Admin")


@pytest.fixture
def export_case(session: Session, export_admin: User) -> Case:
    case = Case(case_number="CASE / 001", title="Export case", status="Open")
    session.add(case)
    session.commit()
    session.refresh(case)
    session.add(CaseUserLink(case_id=case.id, user_id=export_admin.id))
    session.commit()
    return case


@pytest.fixture
def export_investigator(export_user_factory) -> User:
    return export_user_factory("export-investigator", "Investigator")


@pytest.fixture
def authenticate_as():
    def authenticate(user: User) -> None:
        app.dependency_overrides[get_current_user] = lambda: user

    return authenticate


def test_entity_csv_export_contains_the_complete_flattened_record(
    client: TestClient,
    session: Session,
    export_admin: User,
    export_case: Case,
    authenticate_as,
):
    authenticate_as(export_admin)
    created_at = datetime(2026, 8, 1, 10, 30, tzinfo=UTC)
    updated_at = datetime(2026, 8, 2, 11, 45, tzinfo=UTC)
    entity = Entity(
        case_id=export_case.id,
        entity_type="person",
        data={
            "first_name": "Zoë",
            "last_name": "O'Connor",
            "address": {"street": "1 Main St", "city": "Dublin"},
            "social_media": {"x": "https://x.example/zoe"},
            "usernames": ["zoe", "zoc"],
            "associates": {"partner/spouse": "Sam"},
            "notes": "<p>First line</p><p>Second <strong>line</strong></p>",
            "sources": {"zeta": "archive", "alpha": "interview"},
        },
        created_by_id=export_admin.id,
        created_at=created_at,
        updated_at=updated_at,
    )
    session.add(entity)
    session.commit()
    session.refresh(entity)

    response = client.get(
        f"{settings.API_V1_STR}/cases/{export_case.id}/entities/export"
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert response.headers["content-disposition"].startswith(
        'attachment; filename="CASE-001-entities-'
    )
    assert response.headers["content-disposition"].endswith('.csv"')
    assert response.content.startswith(b"\xef\xbb\xbf")

    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert len(rows) == 1
    assert list(rows[0]) == [
        "id",
        "entity_type",
        "display_name",
        "first_name",
        "last_name",
        "dob",
        "nationality",
        "address.street",
        "address.city",
        "address.state",
        "address.country",
        "address.postal_code",
        "email",
        "phone",
        "employer",
        "social_media.bluesky",
        "social_media.discord",
        "social_media.facebook",
        "social_media.instagram",
        "social_media.linkedin",
        "social_media.reddit",
        "social_media.telegram",
        "social_media.tiktok",
        "social_media.twitch",
        "social_media.x",
        "social_media.youtube",
        "social_media.other",
        "usernames",
        "associates.children",
        "associates.colleagues",
        "associates.father",
        "associates.friends",
        "associates.mother",
        "associates.partner/spouse",
        "associates.siblings",
        "associates.other",
        "other",
        "notes",
        "sources.alpha",
        "sources.zeta",
        "created_at",
        "updated_at",
        "created_by",
    ]
    assert rows[0]["display_name"] == "Zoë O'Connor"
    assert rows[0]["address.street"] == "1 Main St"
    assert rows[0]["social_media.x"] == "https://x.example/zoe"
    assert rows[0]["usernames"] == "zoe; zoc"
    assert rows[0]["associates.partner/spouse"] == "Sam"
    assert rows[0]["notes"] == "First line\nSecond line"
    assert rows[0]["sources.alpha"] == "interview"
    assert rows[0]["sources.zeta"] == "archive"
    assert rows[0]["created_at"] == "2026-08-01T10:30:00+00:00"
    assert rows[0]["updated_at"] == "2026-08-02T11:45:00+00:00"
    assert rows[0]["created_by"] == "export-admin"


def test_entity_json_export_preserves_raw_data_and_adds_creator_username(
    client: TestClient,
    session: Session,
    export_admin: User,
    export_case: Case,
    authenticate_as,
):
    authenticate_as(export_admin)
    raw_data = {
        "domain": "münich.example",
        "notes": "<p>Keep this HTML</p>",
        "subdomains": [{"name": "api", "addresses": ["192.0.2.1"]}],
        "sources": {"domain": "https://source.example"},
        "unregistered_field": {"must": "survive"},
    }
    entity = Entity(
        case_id=export_case.id,
        entity_type="domain",
        data=raw_data,
        created_by_id=export_admin.id,
    )
    session.add(entity)
    session.commit()
    session.refresh(entity)

    response = client.get(
        f"{settings.API_V1_STR}/cases/{export_case.id}/entities/export?format=json"
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["content-disposition"].endswith('.json"')
    assert response.json() == [
        {
            "id": entity.id,
            "case_id": export_case.id,
            "entity_type": "domain",
            "data": raw_data,
            "created_at": entity.created_at.replace(tzinfo=UTC).isoformat(),
            "updated_at": entity.updated_at.replace(tzinfo=UTC).isoformat(),
            "created_by_id": export_admin.id,
            "created_by": "export-admin",
        }
    ]


def test_entity_csv_export_encodes_object_lists_as_json(
    client: TestClient,
    session: Session,
    export_admin: User,
    export_case: Case,
    authenticate_as,
):
    authenticate_as(export_admin)
    subdomains = [{"name": "www", "addresses": ["192.0.2.2"]}]
    session.add(
        Entity(
            case_id=export_case.id,
            entity_type="domain",
            data={"domain": "example.test", "subdomains": subdomains},
            created_by_id=export_admin.id,
        )
    )
    session.commit()

    response = client.get(
        f"{settings.API_V1_STR}/cases/{export_case.id}/entities/export"
    )

    row = next(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert json.loads(row["subdomains"]) == subdomains


def test_entity_export_applies_repeatable_types_and_display_or_description_search(
    client: TestClient,
    session: Session,
    export_admin: User,
    export_case: Case,
    authenticate_as,
):
    authenticate_as(export_admin)
    noise_entities = [
        Entity(
            case_id=export_case.id,
            entity_type="person",
            data={"first_name": f"Noise {index}"},
            created_by_id=export_admin.id,
        )
        for index in range(101)
    ]
    entities = [
        Entity(
            case_id=export_case.id,
            entity_type="person",
            data={"first_name": "Alice", "description": "No match"},
            created_by_id=export_admin.id,
        ),
        Entity(
            case_id=export_case.id,
            entity_type="person",
            data={"first_name": "Bob", "description": "Needle in description"},
            created_by_id=export_admin.id,
        ),
        Entity(
            case_id=export_case.id,
            entity_type="domain",
            data={"domain": "needle.example"},
            created_by_id=export_admin.id,
        ),
        Entity(
            case_id=export_case.id,
            entity_type="company",
            data={"name": "Needle Industries"},
            created_by_id=export_admin.id,
        ),
    ]
    session.add_all([*noise_entities, *entities])
    session.commit()

    response = client.get(
        f"{settings.API_V1_STR}/cases/{export_case.id}/entities/export",
        params=[
            ("format", "json"),
            ("entity_type", "person"),
            ("entity_type", "domain"),
            ("search", "nEeDlE"),
            ("skip", "999"),
            ("limit", "1"),
        ],
    )

    assert response.status_code == 200
    assert [record["data"] for record in response.json()] == [
        {"first_name": "Bob", "description": "Needle in description"},
        {"domain": "needle.example"},
    ]


def test_empty_entity_exports_keep_the_requested_schema_header(
    client: TestClient,
    export_admin: User,
    export_case: Case,
    authenticate_as,
):
    authenticate_as(export_admin)

    csv_response = client.get(
        f"{settings.API_V1_STR}/cases/{export_case.id}/entities/export",
        params={"entity_type": "vehicle"},
    )
    json_response = client.get(
        f"{settings.API_V1_STR}/cases/{export_case.id}/entities/export",
        params={"format": "json", "entity_type": "vehicle"},
    )

    csv_rows = list(csv.reader(io.StringIO(csv_response.content.decode("utf-8-sig"))))
    assert csv_rows == [
        [
            "id",
            "entity_type",
            "display_name",
            "make",
            "model",
            "year",
            "vin",
            "license_plate",
            "color",
            "owner",
            "registration_state",
            "description",
            "notes",
            "created_at",
            "updated_at",
            "created_by",
        ]
    ]
    assert json_response.status_code == 200
    assert json_response.json() == []


def test_entity_export_requires_authentication(client: TestClient, export_case: Case):
    response = client.get(
        f"{settings.API_V1_STR}/cases/{export_case.id}/entities/export"
    )

    assert response.status_code == 401


def test_entity_export_enforces_case_access_while_allowing_admins(
    client: TestClient,
    session: Session,
    export_admin: User,
    export_investigator: User,
    export_case: Case,
    authenticate_as,
):
    authenticate_as(export_investigator)
    forbidden_response = client.get(
        f"{settings.API_V1_STR}/cases/{export_case.id}/entities/export"
    )

    session.add(CaseUserLink(case_id=export_case.id, user_id=export_investigator.id))
    session.commit()
    session.expire(export_case, ["users"])
    allowed_response = client.get(
        f"{settings.API_V1_STR}/cases/{export_case.id}/entities/export"
    )

    unassigned_case = Case(case_number="ADMIN-ONLY", title="Admin export")
    session.add(unassigned_case)
    session.commit()
    session.refresh(unassigned_case)
    authenticate_as(export_admin)
    admin_response = client.get(
        f"{settings.API_V1_STR}/cases/{unassigned_case.id}/entities/export?format=json"
    )
    missing_response = client.get(f"{settings.API_V1_STR}/cases/999999/entities/export")

    assert forbidden_response.status_code == 403
    assert allowed_response.status_code == 200
    assert admin_response.status_code == 200
    assert missing_response.status_code == 404


def test_analyst_may_export_entities_from_an_assigned_case(
    client: TestClient,
    session: Session,
    export_case: Case,
    export_user_factory,
    authenticate_as,
):
    analyst = export_user_factory("export-analyst", "Analyst")
    session.add(CaseUserLink(case_id=export_case.id, user_id=analyst.id))
    session.commit()
    authenticate_as(analyst)

    response = client.get(
        f"{settings.API_V1_STR}/cases/{export_case.id}/entities/export"
    )

    assert response.status_code == 200


def test_entity_export_rejects_an_unknown_format(
    client: TestClient,
    export_admin: User,
    export_case: Case,
    authenticate_as,
):
    authenticate_as(export_admin)

    response = client.get(
        f"{settings.API_V1_STR}/cases/{export_case.id}/entities/export?format=xlsx"
    )

    assert response.status_code == 422


def test_mixed_entity_csv_uses_registry_order_and_network_asset_fields(
    client: TestClient,
    session: Session,
    export_admin: User,
    export_case: Case,
    authenticate_as,
):
    authenticate_as(export_admin)
    session.add_all(
        [
            Entity(
                case_id=export_case.id,
                entity_type="company",
                data={
                    "name": "Acme",
                    "affiliates": {
                        "Affiliated Companies": "Example Holdings",
                        "Parent Company": "Example Parent",
                    },
                },
                created_by_id=export_admin.id,
            ),
            Entity(
                case_id=export_case.id,
                entity_type="person",
                data={"first_name": "Ada"},
                created_by_id=export_admin.id,
            ),
            Entity(
                case_id=export_case.id,
                entity_type="network_assets",
                data={
                    "domains": ["first.example", "second.example"],
                    "ip_addresses": ["192.0.2.10"],
                    "subdomains": ["api.first.example"],
                    "notes": "Network notes",
                },
                created_by_id=export_admin.id,
            ),
            Entity(
                case_id=export_case.id,
                entity_type="vehicle",
                data={"year": 2020, "make": "Ford", "model": "Transit"},
                created_by_id=export_admin.id,
            ),
        ]
    )
    session.commit()

    response = client.get(
        f"{settings.API_V1_STR}/cases/{export_case.id}/entities/export"
    )

    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    columns = list(rows[0])
    assert columns.index("first_name") < columns.index("name")
    assert columns.index("name") < columns.index("domains")
    assert columns.index("domains") < columns.index("make")
    assert "affiliates.Affiliated Companies" in columns
    assert "affiliates.Parent Company" in columns
    company_row = next(row for row in rows if row["entity_type"] == "company")
    network_row = next(row for row in rows if row["entity_type"] == "network_assets")
    vehicle_row = next(row for row in rows if row["entity_type"] == "vehicle")
    assert network_row["display_name"] == "first.example"
    assert network_row["domains"] == "first.example; second.example"
    assert network_row["ip_addresses"] == "192.0.2.10"
    assert vehicle_row["display_name"] == "2020 Ford Transit"
    assert company_row["affiliates.Affiliated Companies"] == "Example Holdings"
    assert company_row["affiliates.Parent Company"] == "Example Parent"
