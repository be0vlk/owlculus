"""Folder deletion applies protected Evidence policy before destructive work."""

from unittest.mock import AsyncMock, Mock

import pytest

from app.core.dependencies import get_current_user
from app.core.exceptions import AuthorizationException
from app.database.models import Case, CaseUserLink, CorrelationEvidence, Evidence
from app.main import app
from app.services.evidence_service import EvidenceService


@pytest.fixture
def folder_contents(session, test_case, test_admin):
    def create(*, nested=False, provenance="known", folder_path="Plugin Results"):
        related = Case(case_number="RELATED", title="Related")
        session.add(related)
        session.flush()

        def evidence(title, path, parent=None, is_folder=False):
            row = Evidence(
                case_id=test_case.id,
                title=title,
                evidence_type="folder" if is_folder else "file",
                content="" if is_folder else f"{test_case.id}/{path}/{title}.txt",
                folder_path=path,
                parent_folder_id=parent.id if parent else None,
                is_folder=is_folder,
                created_by_id=test_admin.id,
            )
            session.add(row)
            session.flush()
            return row

        folder = evidence("Plugin Results", folder_path, is_folder=True)
        child = evidence("Nested", f"{folder_path}/Nested", folder, True)
        ordinary = evidence("Ordinary", folder_path, folder)
        nested_ordinary = evidence("Nested ordinary", child.folder_path, child)
        parent = child if nested else folder
        report = evidence("Correlation Scan", parent.folder_path, parent)
        if provenance != "legacy":
            session.add(
                CorrelationEvidence(
                    evidence_id=report.id,
                    case_ids=(
                        [test_case.id, related.id] if provenance == "known" else None
                    ),
                )
            )
        session.commit()
        return (
            folder,
            related,
            report,
            [folder, child, ordinary, nested_ordinary, report],
        )

    return create


@pytest.fixture
def physical_deletion(monkeypatch):
    folder = Mock()
    file = AsyncMock()
    monkeypatch.setattr("app.services.evidence_service.delete_folder", folder)
    monkeypatch.setattr("app.services.evidence_service.delete_file", file)
    return folder, file


@pytest.mark.asyncio
@pytest.mark.parametrize("boundary", ["service", "api"])
@pytest.mark.parametrize("nested", [False, True], ids=["direct", "nested"])
@pytest.mark.parametrize("provenance", ["known", "unknown", "legacy"])
@pytest.mark.parametrize("access", ["narrow", "broad", "admin"])
async def test_folder_deletion_respects_every_reports_case_access(
    client,
    session,
    test_case,
    test_user,
    test_admin,
    folder_contents,
    physical_deletion,
    boundary,
    nested,
    provenance,
    access,
):
    folder, related, report, contents = folder_contents(
        nested=nested, provenance=provenance
    )
    session.add(CaseUserLink(case_id=test_case.id, user_id=test_user.id))
    if access == "broad":
        session.add(CaseUserLink(case_id=related.id, user_id=test_user.id))
    session.commit()
    user = test_admin if access == "admin" else test_user
    allowed = access == "admin" or (access == "broad" and provenance == "known")
    before = {row.id: row.model_dump() for row in contents}
    stored_provenance = session.get(CorrelationEvidence, report.id)
    before_provenance = stored_provenance.model_dump() if stored_provenance else None
    service = EvidenceService(session)
    if not allowed:
        with pytest.raises(AuthorizationException):
            await service.delete_evidence(report.id, user)
    if boundary == "api":
        app.dependency_overrides[get_current_user] = lambda: user
        response = client.delete(f"/api/evidence/folders/{folder.id}")
        assert response.status_code == (204 if allowed else 403), response.text
    elif allowed:
        result = await service.delete_folder(folder.id, user)
        assert result.id == folder.id
    else:
        with pytest.raises(AuthorizationException):
            await service.delete_folder(folder.id, user)

    session.expire_all()
    if allowed:
        assert all(session.get(Evidence, item_id) is None for item_id in before)
        assert session.get(CorrelationEvidence, report.id) is None
        physical_deletion[0].assert_called_once_with(test_case.id, folder.folder_path)
    else:
        assert {
            item_id: session.get(Evidence, item_id).model_dump() for item_id in before
        } == before
        remaining = session.get(CorrelationEvidence, report.id)
        assert (remaining.model_dump() if remaining else None) == before_provenance
        physical_deletion[0].assert_not_called()
    physical_deletion[1].assert_not_called()


@pytest.mark.parametrize("access", ["unassigned", "analyst"])
def test_folder_deletion_still_requires_containing_case_write_access(
    client,
    session,
    test_case,
    test_user,
    test_analyst,
    folder_contents,
    physical_deletion,
    access,
):
    folder, related, report, contents = folder_contents()
    user = test_analyst if access == "analyst" else test_user
    case_ids = [related.id]
    if access == "analyst":
        case_ids.append(test_case.id)
    session.add_all(
        CaseUserLink(case_id=case_id, user_id=user.id) for case_id in case_ids
    )
    session.commit()
    item_ids = [item.id for item in contents]
    app.dependency_overrides[get_current_user] = lambda: user
    assert client.delete(f"/api/evidence/folders/{folder.id}").status_code == 403
    session.expire_all()
    assert all(session.get(Evidence, item_id) is not None for item_id in item_ids)
    assert session.get(CorrelationEvidence, report.id) is not None
    physical_deletion[0].assert_not_called()
    physical_deletion[1].assert_not_called()


@pytest.mark.parametrize(
    "folder_path,sibling_path",
    [
        ("Plugin Results", "Plugin Results Archive"),
        ("Plugin_Results", "PluginXResults"),
    ],
)
def test_folder_deletion_does_not_include_similarly_named_siblings(
    client,
    session,
    test_case,
    test_admin,
    test_user,
    folder_contents,
    physical_deletion,
    folder_path,
    sibling_path,
):
    folder, related, _report, _contents = folder_contents(folder_path=folder_path)
    sibling = Evidence(
        case_id=test_case.id,
        title="Sibling report",
        evidence_type="file",
        content=f"{test_case.id}/{sibling_path}/report.txt",
        folder_path=sibling_path,
        created_by_id=test_admin.id,
    )
    session.add(sibling)
    session.flush()
    session.add(CorrelationEvidence(evidence_id=sibling.id, case_ids=None))
    session.add_all(
        [
            CaseUserLink(case_id=test_case.id, user_id=test_user.id),
            CaseUserLink(case_id=related.id, user_id=test_user.id),
        ]
    )
    session.commit()
    sibling_id = sibling.id
    app.dependency_overrides[get_current_user] = lambda: test_user
    assert client.delete(f"/api/evidence/folders/{folder.id}").status_code == 204
    session.expire_all()
    assert session.get(Evidence, sibling_id) is not None
    assert session.get(CorrelationEvidence, sibling_id) is not None


def test_folder_alias_cannot_bypass_protected_report_authorization(
    client,
    session,
    test_case,
    test_user,
    test_admin,
    folder_contents,
    physical_deletion,
):
    _folder, _related, report, contents = folder_contents(nested=True)
    alias = Evidence(
        case_id=test_case.id,
        title="Plugin Results!",
        evidence_type="folder",
        content="",
        folder_path="Plugin Results!",
        is_folder=True,
        created_by_id=test_admin.id,
    )
    session.add(alias)
    session.add(CaseUserLink(case_id=test_case.id, user_id=test_user.id))
    session.commit()
    item_ids = [item.id for item in [*contents, alias]]
    app.dependency_overrides[get_current_user] = lambda: test_user
    assert client.delete(f"/api/evidence/folders/{alias.id}").status_code == 403
    session.expire_all()
    assert all(session.get(Evidence, item_id) is not None for item_id in item_ids)
    assert session.get(CorrelationEvidence, report.id) is not None
    physical_deletion[0].assert_not_called()
    physical_deletion[1].assert_not_called()
