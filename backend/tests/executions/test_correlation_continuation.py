"""Bounded correlation groups through durable results and protected Evidence."""

import pytest
from sqlmodel import Session

from app.database.models import Case, CaseUserLink, Entity
from app.schemas.entity_schema import EntityCreate
from tests.executions.conftest import eventually
from tests.executions.test_execution_system import finished


@pytest.mark.parametrize(
    "operation_limit,status", [(50000, "completed"), (6500, "failed")]
)
def test_correlation_continuations_survive_retention_and_report_download(
    execution_system, operation_limit, status
):
    system = execution_system
    system.env.update(
        EXECUTION_EVENT_LIMIT_BYTES="2400",
        EXECUTION_RESULT_LIMIT_BYTES=str(operation_limit),
    )
    with Session(system.engine) as db:
        related = Case(case_number="RELATED", title="Related investigation")
        db.add(related)
        db.flush()
        db.add(CaseUserLink(case_id=related.id, user_id=system.user_id))
        rows = []
        for case_id, count in ((system.case_id, 1), (related.id, 16)):
            for index in range(count):
                payload = EntityCreate(
                    entity_type="person",
                    data={
                        "first_name": f"Person {index}",
                        "email": "exact@example.com",
                        "phone": "+1 (202) 555-0123",
                    },
                )
                rows.append(
                    Entity(
                        case_id=case_id,
                        created_by_id=system.user_id,
                        entity_type=payload.entity_type,
                        data=payload.data,
                    )
                )
        db.add_all(rows)
        db.commit()
        related_id = related.id
    _, client = system.api()
    system.worker()
    system.start("-m", "app.executions.dispatcher")
    try:
        response = client.post(
            "/api/plugins/CorrelationScan/execute",
            json={"case_id": system.case_id, "save_to_case": True},
        )
        assert response.status_code == 202, response.text
        accepted = response.json()
        state = eventually(lambda: finished(client, accepted))
        assert state["status"] == status, state
        parts, cursor = [], 0
        while True:
            page = client.get(
                accepted["links"]["results"], params={"cursor": cursor, "limit": 1}
            ).json()
            parts.extend(
                event["data"]
                for event in page["items"]
                if "matches" in event.get("data", {})
            )
            cursor = page["next_cursor"]
            if cursor is None:
                break
        assert len(parts) > 1
        email = [part for part in parts if part["match_type"] == "email"]
        assert len({part["group_id"] for part in email}) == 1
        email_ids = [match["entity_id"] for part in email for match in part["matches"]]
        assert len(email_ids) == len(set(email_ids))
        saved = [
            row
            for row in client.get(f"/api/evidence/case/{system.case_id}").json()
            if not row["is_folder"]
        ]
        if status == "completed":
            assert len(email_ids) == 16
            assert len(saved) == 1
            original = client.get(f"/api/evidence/{saved[0]['id']}/download")
            assert original.status_code == 200
            for expected in (
                "Total entities with matches: 1",
                "Total matches: 49",
                "Exact email match",
                "Exact phone match",
                "+1 (202) 555-0123",
            ):
                assert expected in original.text
            assert original.text.count("Match Type: email") == 1
            with Session(system.engine) as db:
                link = db.get(CaseUserLink, (related_id, system.user_id))
                db.delete(link)
                db.commit()
            assert (
                client.get(f"/api/evidence/{saved[0]['id']}/download").status_code
                == 403
            )
            assert not any(
                "matches" in event.get("data", {})
                for event in client.get(accepted["links"]["results"]).json()["items"]
            )
        else:
            assert 0 < len(email_ids) < 16
            assert state["error"]["code"] == "result_size_limit"
            assert saved == []
    finally:
        client.close()
