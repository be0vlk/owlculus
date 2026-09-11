"""Correlation confidentiality through real durable workers and artifact receipts."""

import httpx
import pytest
from sqlmodel import Session, select

from app.core.security import create_access_token, get_password_hash
from app.database.models import Case, CaseUserLink, Entity, User
from tests.executions.conftest import eventually
from tests.executions.test_hunt_execution_system import step, submit_hunt, terminal


@pytest.mark.parametrize("existing_ip", [False, True])
def test_hunt_correlation_and_dependent_reports_keep_case_provenance(
    execution_system, existing_ip
):
    system = execution_system
    with Session(system.engine) as db:
        related = Case(case_number="SECRET", title="SECRET.example.test")
        reader = User(
            username="reader",
            email="reader@example.test",
            password_hash=get_password_hash("test-password"),
            role="Analyst",
        )
        db.add_all([related, reader])
        db.flush()
        db.add_all(
            [
                CaseUserLink(case_id=system.case_id, user_id=reader.id),
                CaseUserLink(case_id=related.id, user_id=system.user_id),
            ]
        )
        for case_id in (system.case_id, related.id):
            db.add(
                Entity(
                    case_id=case_id,
                    entity_type="person",
                    data={"first_name": "Shared", "last_name": "Name"},
                    created_by_id=system.user_id,
                )
            )
        db.commit()
        related_id = related.id
        token = create_access_token(
            data={
                "sub": reader.auth_identity,
                "session_version": reader.session_version,
            }
        )
    if existing_ip:
        with Session(system.engine) as db:
            db.add(
                Entity(
                    case_id=system.case_id,
                    entity_type="ip_address",
                    data={"ip_address": "192.0.2.55", "description": "PUBLIC"},
                    created_by_id=system.user_id,
                )
            )
            db.commit()
    system.env["EXECUTION_TEST_DNS"] = "1"
    _, client = system.api()
    system.start("-m", "tests.executions.runtime", "hunt-worker")
    system.start("-m", "app.executions.dispatcher")
    try:
        accepted = submit_hunt(
            system,
            client,
            [
                step("scan", plugin_name="CorrelationScan", save_to_case=True),
                step(
                    "copy",
                    plugin_name="DnsLookup",
                    depends_on=["scan"],
                    parameter_mapping={
                        "domain": "scan.results[0].matches[0].case_title"
                    },
                    save_to_case=True,
                ),
                step("independent", static_parameters={"query": "PUBLIC"}),
            ],
        )
        state = eventually(lambda: terminal(client, accepted))
        assert state["status"] == "completed", state
        assert (
            "Entity save skipped: correlation provenance does not permit saving to this Case."
            in str(state)
        )
        reports = [
            row
            for row in client.get(f"/api/evidence/case/{system.case_id}").json()
            if not row["is_folder"]
        ]
        assert len(reports) == 2
        originals = {
            row["id"]: client.get(f"/api/evidence/{row['id']}/download").content
            for row in reports
        }
        assert all(b"SECRET" in content for content in originals.values())
        with httpx.Client(
            base_url=str(client.base_url), headers={"Authorization": f"Bearer {token}"}
        ) as observer:
            entities = observer.get(f"/api/cases/{system.case_id}/entities").json()
            ips = [row for row in entities if row["entity_type"] == "ip_address"]
            assert len(ips) == int(existing_ip)
            for row in entities:
                response = observer.get(
                    f"/api/cases/{system.case_id}/entities/{row['id']}"
                )
                assert response.status_code == 200
                assert "SECRET" not in response.text
            for format in ("json", "csv"):
                response = observer.get(
                    f"/api/cases/{system.case_id}/entities/export?format={format}"
                )
                assert response.status_code == 200
                assert "SECRET" not in response.text
            for suffix in (
                "?include_steps=true",
                "/steps/copy/results",
                "/export?format=json",
            ):
                response = observer.get(accepted["links"]["detail"] + suffix)
                assert response.status_code == 200
                assert "SECRET" not in response.text
            assert (
                "PUBLIC"
                in observer.get(
                    accepted["links"]["detail"] + "?include_steps=true"
                ).text
            )
            assert all(
                row["is_folder"]
                for row in observer.get(f"/api/evidence/case/{system.case_id}").json()
            )
            for report in reports:
                assert (
                    observer.get(f"/api/evidence/{report['id']}/download").status_code
                    == 403
                )
        with Session(system.engine) as db:
            db.delete(
                db.exec(
                    select(CaseUserLink).where(
                        CaseUserLink.case_id == related_id,
                        CaseUserLink.user_id == system.user_id,
                    )
                ).one()
            )
            db.commit()
        assert (
            "SECRET"
            not in client.get(accepted["links"]["detail"] + "?include_steps=true").text
        )
        for report in reports:
            assert (
                client.get(f"/api/evidence/{report['id']}/download").status_code == 403
            )
        with Session(system.engine) as db:
            db.add(CaseUserLink(case_id=related_id, user_id=system.user_id))
            db.commit()
        for report_id, original in originals.items():
            assert client.get(f"/api/evidence/{report_id}/download").content == original
    finally:
        client.close()
