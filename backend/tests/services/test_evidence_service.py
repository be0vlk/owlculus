import pytest
import tempfile
import os
from io import BytesIO
from unittest.mock import Mock, patch, AsyncMock
from sqlmodel import Session
from fastapi import HTTPException, UploadFile

from app.database import models
from app.schemas import evidence_schema as schemas, case_schema
from app.services import evidence_service
from app.core.utils import get_utc_now


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


# Test create_evidence method
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

    with pytest.raises(HTTPException) as excinfo:
        await evidence_service_instance.create_evidence(
            evidence_data, test_admin, file=mock_upload_file
        )
    assert excinfo.value.status_code == 400
    assert "Cannot upload files without any folders" in excinfo.value.detail


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

    assert created_evidence.title == "Test File Evidence"
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

    with pytest.raises(HTTPException) as excinfo:
        await evidence_service_instance.create_evidence(evidence_data, test_admin)
    assert excinfo.value.status_code == 400
    assert "File is required for file-type evidence" in excinfo.value.detail


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

    with pytest.raises(HTTPException) as excinfo:
        await evidence_service_instance.create_evidence(evidence_data, test_admin)
    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == "Case not found"


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

    # Mock database error during commit
    with patch.object(
        evidence_service_instance.db, "commit", side_effect=Exception("DB Error")
    ):
        with pytest.raises(HTTPException) as excinfo:
            await evidence_service_instance.create_evidence(
                evidence_data, test_admin, file=mock_upload_file
            )
        assert excinfo.value.status_code == 500
        assert "Error creating evidence" in excinfo.value.detail
        mock_delete_file.assert_called_once()


# Test get_case_evidence method
@pytest.mark.asyncio
async def test_get_case_evidence(
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    test_admin: models.User,
):
    # Create some evidence
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
    with pytest.raises(HTTPException) as excinfo:
        await evidence_service_instance.get_case_evidence(999, test_admin)
    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == "Case not found"


@pytest.mark.asyncio
async def test_get_case_evidence_pagination(
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    test_admin: models.User,
):
    # Create 10 evidence items
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

    # Test pagination
    first_page = await evidence_service_instance.get_case_evidence(
        sample_case.id, test_admin, skip=0, limit=5
    )
    second_page = await evidence_service_instance.get_case_evidence(
        sample_case.id, test_admin, skip=5, limit=5
    )

    assert len(first_page) == 5
    assert len(second_page) == 5
    assert first_page[0].id != second_page[0].id


# Test get_evidence method
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
    with pytest.raises(HTTPException) as excinfo:
        await evidence_service_instance.get_evidence(999, test_admin)
    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == "Evidence not found"


# Test update_evidence method
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

    with pytest.raises(HTTPException) as excinfo:
        evidence_service_instance.update_evidence(evidence.id, update_data, test_admin)
    assert excinfo.value.status_code == 400
    assert "Cannot update content of file-type evidence" in excinfo.value.detail


def test_update_evidence_not_found(
    evidence_service_instance: evidence_service.EvidenceService,
    test_admin: models.User,
):
    update_data = schemas.EvidenceUpdate(title="Updated Title")

    with pytest.raises(HTTPException) as excinfo:
        evidence_service_instance.update_evidence(999, update_data, test_admin)
    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == "Evidence not found"


# Test delete_evidence method
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

    # Verify evidence is deleted from database
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

    # Verify evidence is deleted from database
    db_evidence = evidence_service_instance.db.get(models.Evidence, evidence.id)
    assert db_evidence is None


@pytest.mark.asyncio
async def test_delete_evidence_analyst_forbidden(
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    test_admin: models.User,
    test_analyst: models.User,
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

    with pytest.raises(HTTPException) as excinfo:
        await evidence_service_instance.delete_evidence(
            evidence.id, current_user=test_analyst
        )
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "Not authorized"


# Test create_folder method
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

    with pytest.raises(HTTPException) as excinfo:
        await evidence_service_instance.create_folder(folder_data, test_admin)
    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == "Case not found"


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

    with pytest.raises(HTTPException) as excinfo:
        await evidence_service_instance.create_folder(folder_data, test_admin)
    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == "Parent folder not found"


# Test get_folder_tree method
@pytest.mark.asyncio
async def test_get_folder_tree(
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    sample_folder: models.Evidence,
    test_admin: models.User,
):
    folder_tree = await evidence_service_instance.get_folder_tree(
        sample_case.id, test_admin
    )

    assert len(folder_tree) >= 1
    assert any(item.id == sample_folder.id for item in folder_tree)


@pytest.mark.asyncio
async def test_get_folder_tree_nonexistent_case(
    evidence_service_instance: evidence_service.EvidenceService,
    test_admin: models.User,
):
    with pytest.raises(HTTPException) as excinfo:
        await evidence_service_instance.get_folder_tree(999, test_admin)
    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == "Case not found"


# Test update_folder method
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

    with pytest.raises(HTTPException) as excinfo:
        await evidence_service_instance.update_folder(999, update_data, test_admin)
    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == "Folder not found"


# Test delete_folder method
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

    # Verify folder is deleted from database
    db_folder = evidence_service_instance.db.get(models.Evidence, sample_folder.id)
    assert db_folder is None


@pytest.mark.asyncio
async def test_delete_folder_analyst_forbidden(
    evidence_service_instance: evidence_service.EvidenceService,
    sample_folder: models.Evidence,
    test_analyst: models.User,
):
    with pytest.raises(HTTPException) as excinfo:
        await evidence_service_instance.delete_folder(
            sample_folder.id, current_user=test_analyst
        )
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "Not authorized"


@pytest.mark.asyncio
@patch("app.services.evidence_service.delete_folder")
async def test_delete_folder_with_contents(
    mock_delete_folder_func: Mock,
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    sample_folder: models.Evidence,
    test_admin: models.User,
):
    # Create evidence in the folder
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

    # Verify folder and its contents are deleted
    db_folder = evidence_service_instance.db.get(models.Evidence, sample_folder.id)
    assert db_folder is None
    db_evidence = evidence_service_instance.db.get(models.Evidence, evidence.id)
    assert db_evidence is None


# Test download_evidence method
@pytest.mark.asyncio
@patch("fastapi.responses.FileResponse")
@patch("app.core.file_storage.UPLOAD_DIR")
async def test_download_evidence_file(
    mock_upload_dir: Mock,
    mock_file_response: Mock,
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    sample_folder: models.Evidence,
    test_admin: models.User,
):
    # Mock the path object with exists method
    mock_path = Mock()
    mock_path.exists.return_value = True
    mock_path.name = "test_file.txt"
    mock_upload_dir.__truediv__ = Mock(return_value=mock_path)

    mock_file_response.return_value = Mock()

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

    result = await evidence_service_instance.download_evidence(evidence.id, test_admin)

    mock_file_response.assert_called_once()


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

    with pytest.raises(HTTPException) as excinfo:
        await evidence_service_instance.download_evidence(evidence.id, test_admin)
    assert excinfo.value.status_code == 400
    assert "Evidence type does not support downloading" in excinfo.value.detail


# Edge cases and additional tests
@pytest.mark.asyncio
async def test_evidence_categories_validation(
    evidence_service_instance: evidence_service.EvidenceService,
    sample_case: models.Case,
    test_admin: models.User,
):
    # Test all valid categories
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
    # Create multiple evidence items
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

    # Verify all evidence was created
    case_evidence = await evidence_service_instance.get_case_evidence(
        sample_case.id, test_admin, limit=100
    )

    assert len(case_evidence) == 50
    assert all(e.case_id == sample_case.id for e in case_evidence)
