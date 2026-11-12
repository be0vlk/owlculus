"""
Test suite for evidence service business logic.

This module tests evidence management, file handling, metadata processing,
folder operations, validation, and security functionality within the
evidence service layer.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import UploadFile
from loguru import logger
from sqlmodel import Session

from app.core import file_storage
from app.core.exceptions import (
    ResourceNotFoundException,
    ValidationException,
)
from app.core.utils import get_utc_now
from app.database import models
from app.schemas import case_schema
from app.schemas import evidence_schema as schemas
from app.services import evidence_service


@pytest.fixture(name="evidence_service_instance")
def evidence_service_fixture(session: Session):
    return evidence_service.EvidenceService(session)


@pytest.fixture(name="sample_case")
def sample_case_fixture(session: Session, test_admin: models.User):
    client = models.Client(name="Test Client", contact_email="test@example.com")
    session.add(client)
    session.commit()
    session.refresh(client)

    case_data = case_schema.CaseCreate(
        client_id=client.id,
        title="Test Case",
        case_number="2301-01",
        status="Open",
        notes="Test Notes",
    )
    case = models.Case(**case_data.model_dump(), created_by=test_admin)
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


@pytest.fixture(name="sample_folder")
def sample_folder_fixture(
    session: Session, sample_case: models.Case, test_admin: models.User
):
    folder = models.Evidence(
        case_id=sample_case.id,
        title="Test Folder",
        description="Test folder description",
        evidence_type="folder",
        category="Other",
        content="",
        folder_path="test_folder",
        is_folder=True,
        created_by_id=test_admin.id,
        created_at=get_utc_now(),
        updated_at=get_utc_now(),
    )
    session.add(folder)
    session.commit()
    session.refresh(folder)
    return folder


@pytest.fixture(name="mock_upload_file")
def mock_upload_file_fixture():
    mock_file = Mock(spec=UploadFile)
    mock_file.filename = "test_file.txt"
    mock_file.content_type = "text/plain"
    mock_file.size = 100
    mock_file.read = AsyncMock(return_value=b"test content")
    return mock_file


@pytest.mark.asyncio
async def test_create_evidence_text_type(
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    test_admin: models.User,
):
    evidence_data = schemas.EvidenceCreate(
        case_id=sample_case.id,
        title="Test Text Evidence",
        description="Test description",
        evidence_type="text",
        category="Other",
        content="Sample text content",
    )

    created_evidence = await evidence_service_instance.create_evidence(
        evidence_data, test_admin
    )

    assert created_evidence.title == "Test Text Evidence"
    assert created_evidence.evidence_type == "text"
    assert created_evidence.content == "Sample text content"
    assert created_evidence.case_id == sample_case.id
    assert created_evidence.created_by_id == test_admin.id


@pytest.mark.asyncio
async def test_create_evidence_file_without_folder_fails(
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    test_admin: models.User,
    mock_upload_file: Mock,
):
    evidence_data = schemas.EvidenceCreate(
        case_id=sample_case.id,
        title="Test File Evidence",
        description="Test description",
        evidence_type="file",
        category="Other",
    )

    with pytest.raises(ValidationException) as excinfo:
        await evidence_service_instance.create_evidence(
            evidence_data, test_admin, file=mock_upload_file
        )
    assert "Cannot upload files without any folders" in str(excinfo.value)


@pytest.mark.asyncio
@patch("app.services.evidence_service.save_upload_file")
async def test_create_evidence_file_with_folder(
    mock_save_file: AsyncMock,
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    sample_folder: models.Evidence,
    test_admin: models.User,
    mock_upload_file: Mock,
):
    mock_save_file.return_value = ("uploads/case_1/test_file.txt", "abc123hash")

    evidence_data = schemas.EvidenceCreate(
        case_id=sample_case.id,
        title="Test File Evidence",
        description="Test description",
        evidence_type="file",
        category="Other",
        folder_path="test_folder",
    )

    created_evidence = await evidence_service_instance.create_evidence(
        evidence_data, test_admin, file=mock_upload_file
    )

    assert created_evidence.title == "test_file.txt"
    assert created_evidence.evidence_type == "file"
    assert created_evidence.content == "uploads/case_1/test_file.txt"
    assert created_evidence.file_hash == "abc123hash"
    assert created_evidence.folder_path == "test_folder"
    mock_save_file.assert_called_once()


@pytest.mark.asyncio
async def test_create_evidence_file_without_file_fails(
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    sample_folder: models.Evidence,
    test_admin: models.User,
):
    evidence_data = schemas.EvidenceCreate(
        case_id=sample_case.id,
        title="Test File Evidence",
        description="Test description",
        evidence_type="file",
        category="Other",
        folder_path="test_folder",
    )

    with pytest.raises(ValidationException) as excinfo:
        await evidence_service_instance.create_evidence(evidence_data, test_admin)
    assert "File is required for file-type evidence" in str(excinfo.value)


@pytest.mark.asyncio
async def test_create_evidence_nonexistent_case(
    evidence_service_instance: evidence_service.EvidenceService,
    test_admin: models.User,
):
    evidence_data = schemas.EvidenceCreate(
        case_id=999,
        title="Test Evidence",
        description="Test description",
        evidence_type="text",
        category="Other",
        content="Sample content",
    )

    with pytest.raises(ResourceNotFoundException) as excinfo:
        await evidence_service_instance.create_evidence(evidence_data, test_admin)
    assert str(excinfo.value) == "Case not found"


@pytest.mark.asyncio
@patch("app.services.evidence_service.save_upload_file")
@patch("app.services.evidence_service.delete_file")
async def test_create_evidence_file_save_error_cleanup(
    mock_delete_file: AsyncMock,
    mock_save_file: AsyncMock,
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    sample_folder: models.Evidence,
    test_admin: models.User,
    mock_upload_file: Mock,
):
    mock_save_file.return_value = ("uploads/case_1/test_file.txt", "abc123hash")

    evidence_data = schemas.EvidenceCreate(
        case_id=sample_case.id,
        title="Test File Evidence",
        description="Test description",
        evidence_type="file",
        category="Other",
        folder_path="test_folder",
    )

    with patch.object(
        evidence_service_instance.db, "commit", side_effect=Exception("DB Error")
    ):
        with pytest.raises(Exception, match="DB Error"):
            await evidence_service_instance.create_evidence(
                evidence_data, test_admin, file=mock_upload_file
            )
        mock_delete_file.assert_called_once_with("uploads/case_1/test_file.txt")


@pytest.mark.asyncio
@patch("app.services.evidence_service.delete_folder")
@patch("app.services.evidence_service.create_folder")
async def test_create_folder_database_error_cleans_up_physical_folder(
    mock_create_folder: Mock,
    mock_delete_folder: Mock,
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    test_admin: models.User,
):
    case_id = sample_case.id
    folder_data = schemas.FolderCreate(case_id=case_id, title="Orphan")

    with (
        patch.object(
            evidence_service_instance.db, "commit", side_effect=Exception("DB Error")
        ),
        pytest.raises(Exception, match="DB Error"),
    ):
        await evidence_service_instance.create_folder(folder_data, test_admin)
    mock_delete_folder.assert_called_once_with(case_id, "Orphan")


@pytest.mark.asyncio
async def test_create_evidence_failure_logs_event_and_reason(
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    sample_folder: models.Evidence,
    test_admin: models.User,
):
    evidence_data = schemas.EvidenceCreate(
        case_id=sample_case.id,
        title="Missing upload",
        evidence_type="file",
        category="Other",
    )

    records: list[dict] = []
    sink = logger.add(lambda message: records.append(message.record["extra"]))
    try:
        with pytest.raises(ValidationException):
            await evidence_service_instance.create_evidence(evidence_data, test_admin)
    finally:
        logger.remove(sink)

    assert {
        "event_type": "evidence_creation_failed",
        "failure_reason": "file_required",
    }.items() <= records[-1].items()


@pytest.mark.asyncio
async def test_get_case_evidence(
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    test_admin: models.User,
):
    for i in range(3):
        evidence = models.Evidence(
            case_id=sample_case.id,
            title=f"Evidence {i}",
            description=f"Description {i}",
            evidence_type="text",
            category="Other",
            content=f"Content {i}",
            created_by_id=test_admin.id,
            created_at=get_utc_now(),
            updated_at=get_utc_now(),
        )
        evidence_service_instance.db.add(evidence)
    evidence_service_instance.db.commit()

    evidence_list = await evidence_service_instance.get_case_evidence(
        sample_case.id, test_admin
    )

    assert len(evidence_list) == 3
    assert all(e.case_id == sample_case.id for e in evidence_list)


@pytest.mark.asyncio
async def test_get_case_evidence_nonexistent_case(
    evidence_service_instance: evidence_service.EvidenceService,
    test_admin: models.User,
):
    with pytest.raises(ResourceNotFoundException) as excinfo:
        await evidence_service_instance.get_case_evidence(999, test_admin)
    assert str(excinfo.value) == "Case not found"


@pytest.mark.asyncio
async def test_get_case_evidence_pagination(
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    test_admin: models.User,
):
    for i in range(10):
        evidence = models.Evidence(
            case_id=sample_case.id,
            title=f"Evidence {i}",
            description=f"Description {i}",
            evidence_type="text",
            category="Other",
            content=f"Content {i}",
            created_by_id=test_admin.id,
            created_at=get_utc_now(),
            updated_at=get_utc_now(),
        )
        evidence_service_instance.db.add(evidence)
    evidence_service_instance.db.commit()

    first_page = await evidence_service_instance.get_case_evidence(
        sample_case.id, test_admin, skip=0, limit=5
    )
    second_page = await evidence_service_instance.get_case_evidence(
        sample_case.id, test_admin, skip=5, limit=5
    )

    assert len(first_page) == 5
    assert len(second_page) == 5
    assert first_page[0].id != second_page[0].id


@pytest.mark.asyncio
async def test_get_evidence(
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    test_admin: models.User,
):
    evidence = models.Evidence(
        case_id=sample_case.id,
        title="Test Evidence",
        description="Test description",
        evidence_type="text",
        category="Other",
        content="Test content",
        created_by_id=test_admin.id,
        created_at=get_utc_now(),
        updated_at=get_utc_now(),
    )
    evidence_service_instance.db.add(evidence)
    evidence_service_instance.db.commit()
    evidence_service_instance.db.refresh(evidence)

    retrieved_evidence = await evidence_service_instance.get_evidence(
        evidence.id, test_admin
    )

    assert retrieved_evidence.id == evidence.id
    assert retrieved_evidence.title == "Test Evidence"


@pytest.mark.asyncio
async def test_get_evidence_not_found(
    evidence_service_instance: evidence_service.EvidenceService,
    test_admin: models.User,
):
    with pytest.raises(ResourceNotFoundException) as excinfo:
        await evidence_service_instance.get_evidence(999, test_admin)
    assert str(excinfo.value) == "Evidence not found"


def test_update_evidence(
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    test_admin: models.User,
):
    evidence = models.Evidence(
        case_id=sample_case.id,
        title="Original Title",
        description="Original description",
        evidence_type="text",
        category="Other",
        content="Original content",
        created_by_id=test_admin.id,
        created_at=get_utc_now(),
        updated_at=get_utc_now(),
    )
    evidence_service_instance.db.add(evidence)
    evidence_service_instance.db.commit()
    evidence_service_instance.db.refresh(evidence)

    update_data = schemas.EvidenceUpdate(
        title="Updated Title",
        description="Updated description",
        content="Updated content",
    )

    updated_evidence = evidence_service_instance.update_evidence(
        evidence.id, update_data, test_admin
    )

    assert updated_evidence.title == "Updated Title"
    assert updated_evidence.description == "Updated description"
    assert updated_evidence.content == "Updated content"


def test_update_evidence_file_content_fails(
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    sample_folder: models.Evidence,
    test_admin: models.User,
):
    evidence = models.Evidence(
        case_id=sample_case.id,
        title="File Evidence",
        description="File description",
        evidence_type="file",
        category="Other",
        content="uploads/test_file.txt",
        created_by_id=test_admin.id,
        created_at=get_utc_now(),
        updated_at=get_utc_now(),
    )
    evidence_service_instance.db.add(evidence)
    evidence_service_instance.db.commit()
    evidence_service_instance.db.refresh(evidence)

    update_data = schemas.EvidenceUpdate(content="new_content")

    with pytest.raises(ValidationException) as excinfo:
        evidence_service_instance.update_evidence(evidence.id, update_data, test_admin)
    assert "Cannot update content of file-type evidence" in str(excinfo.value)


def test_update_evidence_not_found(
    evidence_service_instance: evidence_service.EvidenceService,
    test_admin: models.User,
):
    update_data = schemas.EvidenceUpdate(title="Updated Title")

    with pytest.raises(ResourceNotFoundException) as excinfo:
        evidence_service_instance.update_evidence(999, update_data, test_admin)
    assert str(excinfo.value) == "Evidence not found"


@pytest.mark.asyncio
@patch("app.services.evidence_service.delete_file")
async def test_delete_evidence_file(
    mock_delete_file: AsyncMock,
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    sample_folder: models.Evidence,
    test_admin: models.User,
):
    evidence = models.Evidence(
        case_id=sample_case.id,
        title="File Evidence",
        description="File description",
        evidence_type="file",
        category="Other",
        content="uploads/test_file.txt",
        created_by_id=test_admin.id,
        created_at=get_utc_now(),
        updated_at=get_utc_now(),
    )
    evidence_service_instance.db.add(evidence)
    evidence_service_instance.db.commit()
    evidence_service_instance.db.refresh(evidence)

    deleted_evidence = await evidence_service_instance.delete_evidence(
        evidence.id, current_user=test_admin
    )

    assert deleted_evidence.id == evidence.id
    mock_delete_file.assert_called_once_with("uploads/test_file.txt")

    db_evidence = evidence_service_instance.db.get(models.Evidence, evidence.id)
    assert db_evidence is None


@pytest.mark.asyncio
async def test_delete_evidence_text(
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    test_admin: models.User,
):
    evidence = models.Evidence(
        case_id=sample_case.id,
        title="Text Evidence",
        description="Text description",
        evidence_type="text",
        category="Other",
        content="Text content",
        created_by_id=test_admin.id,
        created_at=get_utc_now(),
        updated_at=get_utc_now(),
    )
    evidence_service_instance.db.add(evidence)
    evidence_service_instance.db.commit()
    evidence_service_instance.db.refresh(evidence)

    deleted_evidence = await evidence_service_instance.delete_evidence(
        evidence.id, current_user=test_admin
    )

    assert deleted_evidence.id == evidence.id

    db_evidence = evidence_service_instance.db.get(models.Evidence, evidence.id)
    assert db_evidence is None


@pytest.mark.asyncio
@patch("app.services.evidence_service.create_folder")
async def test_create_folder(
    mock_create_folder_func: Mock,
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    test_admin: models.User,
):
    folder_data = schemas.FolderCreate(
        case_id=sample_case.id,
        title="New Folder",
        description="New folder description",
    )

    created_folder = await evidence_service_instance.create_folder(
        folder_data, test_admin
    )

    assert created_folder.title == "New Folder"
    assert created_folder.is_folder == True
    assert created_folder.evidence_type == "folder"
    assert created_folder.folder_path == "New Folder"
    mock_create_folder_func.assert_called_once_with(sample_case.id, "New Folder")


@pytest.mark.asyncio
@patch("app.services.evidence_service.create_folder")
async def test_create_subfolder(
    mock_create_folder_func: Mock,
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    sample_folder: models.Evidence,
    test_admin: models.User,
):
    folder_data = schemas.FolderCreate(
        case_id=sample_case.id,
        title="Sub Folder",
        description="Sub folder description",
        parent_folder_id=sample_folder.id,
    )

    created_folder = await evidence_service_instance.create_folder(
        folder_data, test_admin
    )

    assert created_folder.title == "Sub Folder"
    assert created_folder.parent_folder_id == sample_folder.id
    assert created_folder.folder_path == "test_folder/Sub Folder"
    mock_create_folder_func.assert_called_once_with(
        sample_case.id, "test_folder/Sub Folder"
    )


@pytest.mark.asyncio
async def test_create_folder_nonexistent_case(
    evidence_service_instance: evidence_service.EvidenceService,
    test_admin: models.User,
):
    folder_data = schemas.FolderCreate(
        case_id=999,
        title="New Folder",
        description="New folder description",
    )

    with pytest.raises(ResourceNotFoundException) as excinfo:
        await evidence_service_instance.create_folder(folder_data, test_admin)
    assert str(excinfo.value) == "Case not found"


@pytest.mark.asyncio
async def test_create_folder_nonexistent_parent(
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    test_admin: models.User,
):
    folder_data = schemas.FolderCreate(
        case_id=sample_case.id,
        title="Sub Folder",
        description="Sub folder description",
        parent_folder_id=999,
    )

    with pytest.raises(ResourceNotFoundException) as excinfo:
        await evidence_service_instance.create_folder(folder_data, test_admin)
    assert str(excinfo.value) == "Parent folder not found"


@pytest.mark.asyncio
async def test_get_case_evidence_without_limit(
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    sample_folder: models.Evidence,
    test_admin: models.User,
):
    folder_tree = await evidence_service_instance.get_case_evidence(
        sample_case.id, test_admin, limit=None
    )

    assert len(folder_tree) >= 1
    assert any(item.id == sample_folder.id for item in folder_tree)


@pytest.mark.asyncio
async def test_get_case_evidence_without_limit_nonexistent_case(
    evidence_service_instance: evidence_service.EvidenceService,
    test_admin: models.User,
):
    with pytest.raises(ResourceNotFoundException) as excinfo:
        await evidence_service_instance.get_case_evidence(999, test_admin, limit=None)
    assert str(excinfo.value) == "Case not found"


@pytest.mark.asyncio
async def test_update_folder(
    evidence_service_instance: evidence_service.EvidenceService,
    sample_folder: models.Evidence,
    test_admin: models.User,
):
    update_data = schemas.FolderUpdate(
        title="Updated Folder", description="Updated description"
    )

    updated_folder = await evidence_service_instance.update_folder(
        sample_folder.id, update_data, test_admin
    )

    assert updated_folder.title == "Updated Folder"
    assert updated_folder.description == "Updated description"


@pytest.mark.asyncio
async def test_update_folder_not_found(
    evidence_service_instance: evidence_service.EvidenceService,
    test_admin: models.User,
):
    update_data = schemas.FolderUpdate(title="Updated Folder")

    with pytest.raises(ResourceNotFoundException) as excinfo:
        await evidence_service_instance.update_folder(999, update_data, test_admin)
    assert str(excinfo.value) == "Folder not found"


@pytest.mark.asyncio
@patch("app.services.evidence_service.delete_folder")
async def test_delete_folder(
    mock_delete_folder_func: Mock,
    evidence_service_instance: evidence_service.EvidenceService,
    sample_folder: models.Evidence,
    test_admin: models.User,
):
    deleted_folder = await evidence_service_instance.delete_folder(
        sample_folder.id, current_user=test_admin
    )

    assert deleted_folder.id == sample_folder.id
    mock_delete_folder_func.assert_called_once_with(
        sample_folder.case_id, sample_folder.folder_path
    )

    db_folder = evidence_service_instance.db.get(models.Evidence, sample_folder.id)
    assert db_folder is None


@pytest.mark.asyncio
@patch("app.services.evidence_service.delete_folder")
async def test_delete_folder_with_contents(
    mock_delete_folder_func: Mock,
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    sample_folder: models.Evidence,
    test_admin: models.User,
):
    evidence = models.Evidence(
        case_id=sample_case.id,
        title="Evidence in folder",
        description="Test evidence",
        evidence_type="text",
        category="Other",
        content="Test content",
        folder_path="test_folder/subfolder",
        created_by_id=test_admin.id,
        created_at=get_utc_now(),
        updated_at=get_utc_now(),
    )
    evidence_service_instance.db.add(evidence)
    evidence_service_instance.db.commit()

    deleted_folder = await evidence_service_instance.delete_folder(
        sample_folder.id, current_user=test_admin
    )

    assert deleted_folder.id == sample_folder.id
    mock_delete_folder_func.assert_called_once()

    db_folder = evidence_service_instance.db.get(models.Evidence, sample_folder.id)
    assert db_folder is None
    db_evidence = evidence_service_instance.db.get(models.Evidence, evidence.id)
    assert db_evidence is None


@pytest.mark.asyncio
async def test_download_evidence_file(
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    sample_folder: models.Evidence,
    test_admin: models.User,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(file_storage, "UPLOAD_DIR", tmp_path)
    content = f"{sample_case.id}/test_folder/test_file.txt"
    (tmp_path / content).parent.mkdir(parents=True)
    (tmp_path / content).write_bytes(b"data")

    evidence = models.Evidence(
        case_id=sample_case.id,
        title="File Evidence",
        description="File description",
        evidence_type="file",
        category="Other",
        content=content,
        created_by_id=test_admin.id,
        created_at=get_utc_now(),
        updated_at=get_utc_now(),
    )
    evidence_service_instance.db.add(evidence)
    evidence_service_instance.db.commit()
    evidence_service_instance.db.refresh(evidence)

    result = await evidence_service_instance.download_evidence(evidence.id, test_admin)

    assert result == (tmp_path / content).resolve()

    (tmp_path / content).unlink()
    with pytest.raises(ResourceNotFoundException, match="File not found"):
        await evidence_service_instance.download_evidence(evidence.id, test_admin)


@pytest.mark.asyncio
async def test_download_evidence_text_fails(
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    test_admin: models.User,
):
    evidence = models.Evidence(
        case_id=sample_case.id,
        title="Text Evidence",
        description="Text description",
        evidence_type="text",
        category="Other",
        content="Text content",
        created_by_id=test_admin.id,
        created_at=get_utc_now(),
        updated_at=get_utc_now(),
    )
    evidence_service_instance.db.add(evidence)
    evidence_service_instance.db.commit()
    evidence_service_instance.db.refresh(evidence)

    with pytest.raises(ValidationException) as excinfo:
        await evidence_service_instance.download_evidence(evidence.id, test_admin)
    assert "Evidence type does not support downloading" in str(excinfo.value)


@pytest.mark.asyncio
async def test_evidence_categories_validation(
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    test_admin: models.User,
):
    valid_categories = [
        "Social Media",
        "Associates",
        "Network Assets",
        "Communications",
        "Documents",
        "Other",
    ]

    for category in valid_categories:
        evidence_data = schemas.EvidenceCreate(
            case_id=sample_case.id,
            title=f"Test {category}",
            description="Test description",
            evidence_type="text",
            category=category,
            content="Sample content",
        )

        created_evidence = await evidence_service_instance.create_evidence(
            evidence_data, test_admin
        )
        assert created_evidence.category == category


@pytest.mark.asyncio
async def test_evidence_with_special_characters(
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    test_admin: models.User,
):
    special_title = "Evidence with 'quotes' and émojis 🎉"
    special_content = "Content with\nnewlines and\ttabs"

    evidence_data = schemas.EvidenceCreate(
        case_id=sample_case.id,
        title=special_title,
        description="Test description",
        evidence_type="text",
        category="Other",
        content=special_content,
    )

    created_evidence = await evidence_service_instance.create_evidence(
        evidence_data, test_admin
    )

    assert created_evidence.title == special_title
    assert created_evidence.content == special_content


@pytest.mark.asyncio
async def test_bulk_evidence_operations(
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    test_admin: models.User,
):
    evidence_list = []
    for i in range(50):
        evidence_data = schemas.EvidenceCreate(
            case_id=sample_case.id,
            title=f"Bulk Evidence {i:03d}",
            description=f"Bulk test evidence {i}",
            evidence_type="text",
            category="Other",
            content=f"Content {i}",
        )

        evidence = await evidence_service_instance.create_evidence(
            evidence_data, test_admin
        )
        evidence_list.append(evidence)

    case_evidence = await evidence_service_instance.get_case_evidence(
        sample_case.id, test_admin, limit=100
    )

    assert len(case_evidence) == 50
    assert all(e.case_id == sample_case.id for e in case_evidence)


@pytest.mark.asyncio
async def test_folder_template_uses_normalized_paths_for_storage_and_filesystem(
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    test_admin: models.User,
):
    templates = {
        "Normalized": {
            "folders": [
                {
                    "name": " Root ",
                    "subfolders": [{"name": " Child "}],
                }
            ]
        }
    }

    with (
        patch(
            "app.services.system_config_service.SystemConfigService.get_evidence_folder_templates",
            new=AsyncMock(return_value=templates),
        ),
        patch("app.services.evidence_service.create_folder") as create_folder_mock,
    ):
        folders = await evidence_service_instance.create_folders_from_template(
            sample_case.id, "Normalized", test_admin
        )

    assert [folder.folder_path for folder in folders] == ["Root", "Root/Child"]
    assert [call.args[1] for call in create_folder_mock.call_args_list] == [
        "Root",
        "Root/Child",
    ]
