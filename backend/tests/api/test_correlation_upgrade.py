"""Repeatable production upgrade verified through the Evidence read boundary."""

import pytest
from sqlmodel import Session

from app.core.exceptions import AuthorizationException
from app.database.models import Case, CaseUserLink, Evidence, User
from app.database.upgrade_correlation import upgrade
from app.schemas.evidence_schema import EvidenceUpdate
from app.services.evidence_service import EvidenceService


@pytest.mark.asyncio
async def test_upgrade_keeps_unverified_reports_protected_after_renaming(
    engine, tmp_path
):
    file = tmp_path / "report.txt"
    file.write_bytes(b"Historical immutable report")
    with Session(engine) as db:
        admin = User(
            username="admin",
            email="admin@example.test",
            password_hash="unused",
            role="Admin",
        )
        reader = User(
            username="reader",
            email="reader@example.test",
            password_hash="unused",
            role="Investigator",
        )
        case = Case(case_number="A")
        db.add_all([admin, reader, case])
        db.flush()
        db.add(CaseUserLink(case_id=case.id, user_id=reader.id))
        report = Evidence(
            case_id=case.id,
            created_by_id=admin.id,
            title="Correlation Scan results",
            evidence_type="file",
            content=str(file),
        )
        db.add(report)
        db.commit()
        report_id, reader_id, admin_id = report.id, reader.id, admin.id
    upgrade(engine)
    upgrade(engine)
    with Session(engine) as db:
        # Simulate historical metadata changing after the upgrade. Read policy
        # must use the persisted marker, not recognize the old title again.
        report = db.get(Evidence, report_id)
        report.title = "Ordinary"
        report.description = "Ordinary"
        db.commit()
        service = EvidenceService(db)
        service.update_evidence(
            report_id,
            EvidenceUpdate(title="Ordinary", description="Ordinary"),
            db.get(User, admin_id),
        )
        with pytest.raises(AuthorizationException):
            await service.get_evidence(report_id, db.get(User, reader_id))
        assert (
            await service.download_evidence(report_id, db.get(User, admin_id)) == file
        )
    assert file.read_bytes() == b"Historical immutable report"
