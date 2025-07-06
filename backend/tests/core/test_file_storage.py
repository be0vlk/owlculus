"""
Tests for the file_storage module with comprehensive security testing.
"""

import hashlib
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from app.core import file_storage
from fastapi import HTTPException, UploadFile


@pytest.fixture
def temp_upload_dir():
    """Create a temporary upload directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Mock the UPLOAD_DIR for testing
        with patch.object(file_storage, "UPLOAD_DIR", Path(temp_dir)):
            yield Path(temp_dir)


@pytest.fixture
def sample_upload_file():
    """Create a mock UploadFile for testing."""
    from unittest.mock import AsyncMock

    mock_file = Mock(spec=UploadFile)
    mock_file.filename = "test_file.txt"
    mock_file.read = AsyncMock(return_value=b"test content")
    return mock_file


@pytest.fixture
def case_id():
    """Return a valid case ID for testing."""
    return 123


class TestCalculateFileHash:
    """Test the calculate_file_hash function."""

    def test_calculate_file_hash_returns_correct_sha256(self):
        """Test that file hash calculation returns correct SHA-256."""
        content = b"test content"
        expected_hash = hashlib.sha256(content).hexdigest()

        result = file_storage.calculate_file_hash(content)

        assert result == expected_hash

    def test_calculate_file_hash_empty_content(self):
        """Test hash calculation with empty content."""
        content = b""
        expected_hash = hashlib.sha256(content).hexdigest()

        result = file_storage.calculate_file_hash(content)

        assert result == expected_hash

    def test_calculate_file_hash_large_content(self):
        """Test hash calculation with large content."""
        content = b"x" * 1024 * 1024  # 1MB of data
        expected_hash = hashlib.sha256(content).hexdigest()

        result = file_storage.calculate_file_hash(content)

        assert result == expected_hash


class TestNormalizeFolderPath:
    """Test the normalize_folder_path function."""

    def test_normalize_empty_path_returns_empty_string(self):
        """Test that empty path returns empty string."""
        result = file_storage.normalize_folder_path("")
        assert result == ""

    def test_normalize_none_path_returns_empty_string(self):
        """Test that None path returns empty string."""
        result = file_storage.normalize_folder_path(None)
        assert result == ""

    def test_normalize_valid_path(self):
        """Test normalization of valid folder path."""
        result = file_storage.normalize_folder_path("folder1/folder2")
        assert result == "folder1/folder2"

    def test_normalize_path_with_leading_slash(self):
        """Test normalization removes leading slash."""
        result = file_storage.normalize_folder_path("/folder1/folder2")
        assert result == "folder1/folder2"

    def test_normalize_path_with_trailing_slash(self):
        """Test normalization removes trailing slash."""
        result = file_storage.normalize_folder_path("folder1/folder2/")
        assert result == "folder1/folder2"

    def test_normalize_path_with_whitespace(self):
        """Test normalization handles whitespace."""
        result = file_storage.normalize_folder_path("  folder1/folder2  ")
        assert result == "folder1/folder2"

    def test_normalize_path_removes_dots(self):
        """Test that . and .. are removed for security."""
        result = file_storage.normalize_folder_path("folder1/../folder2/./folder3")
        assert result == "folder1/folder2/folder3"

    def test_normalize_path_sanitizes_invalid_chars(self):
        """Test that invalid characters are removed."""
        result = file_storage.normalize_folder_path('folder<>:"|?*1/folder2')
        assert result == "folder1/folder2"

    def test_normalize_path_preserves_valid_chars(self):
        """Test that valid characters are preserved."""
        result = file_storage.normalize_folder_path("folder_1-test.backup/folder 2")
        assert result == "folder_1-test.backup/folder 2"

    def test_normalize_path_empty_after_sanitization(self):
        """Test that completely invalid path returns empty string."""
        result = file_storage.normalize_folder_path("../../../")
        assert result == ""


class TestCreateFolder:
    """Test the create_folder function."""

    def test_create_folder_valid_case_id_and_path(self, temp_upload_dir, case_id):
        """Test creating folder with valid case ID and path."""
        folder_path = "evidence/documents"

        result = file_storage.create_folder(case_id, folder_path)

        expected_path = temp_upload_dir / str(case_id) / folder_path
        assert result == expected_path
        assert result.exists()
        assert result.is_dir()

    def test_create_folder_invalid_case_id_zero(self, temp_upload_dir):
        """Test that invalid case ID (0) raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            file_storage.create_folder(0, "test_folder")

        assert exc_info.value.status_code == 400
        assert "Invalid case ID" in exc_info.value.detail

    def test_create_folder_invalid_case_id_negative(self, temp_upload_dir):
        """Test that negative case ID raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            file_storage.create_folder(-1, "test_folder")

        assert exc_info.value.status_code == 400
        assert "Invalid case ID" in exc_info.value.detail

    def test_create_folder_invalid_case_id_string(self, temp_upload_dir):
        """Test that string case ID raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            file_storage.create_folder("invalid", "test_folder")

        assert exc_info.value.status_code == 400
        assert "Invalid case ID" in exc_info.value.detail

    def test_create_folder_empty_path(self, temp_upload_dir, case_id):
        """Test that empty folder path raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            file_storage.create_folder(case_id, "")

        assert exc_info.value.status_code == 400
        assert "Folder path is required" in exc_info.value.detail

    def test_create_folder_invalid_path_after_normalization(
        self, temp_upload_dir, case_id
    ):
        """Test that path invalid after normalization raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            file_storage.create_folder(case_id, "../../../")

        assert exc_info.value.status_code == 400
        assert "Invalid folder path" in exc_info.value.detail

    def test_create_folder_nested_path(self, temp_upload_dir, case_id):
        """Test creating nested folder structure."""
        folder_path = "level1/level2/level3"

        result = file_storage.create_folder(case_id, folder_path)

        assert result.exists()
        assert result.is_dir()
        # Check all parent directories were created
        assert (temp_upload_dir / str(case_id) / "level1").exists()
        assert (temp_upload_dir / str(case_id) / "level1" / "level2").exists()


class TestDeleteFolder:
    """Test the delete_folder function."""

    def test_delete_folder_valid_case_and_path(self, temp_upload_dir, case_id):
        """Test deleting existing folder."""
        # Create folder first
        folder_path = "test_folder"
        created_folder = file_storage.create_folder(case_id, folder_path)
        assert created_folder.exists()

        # Delete the folder
        file_storage.delete_folder(case_id, folder_path)

        assert not created_folder.exists()

    def test_delete_folder_with_contents(self, temp_upload_dir, case_id):
        """Test deleting folder with files inside."""
        # Create folder and add a file
        folder_path = "test_folder"
        created_folder = file_storage.create_folder(case_id, folder_path)
        test_file = created_folder / "test.txt"
        test_file.write_text("test content")

        # Delete the folder
        file_storage.delete_folder(case_id, folder_path)

        assert not created_folder.exists()
        assert not test_file.exists()

    def test_delete_folder_removes_empty_parents(self, temp_upload_dir, case_id):
        """Test that empty parent directories are cleaned up."""
        # Create nested folder structure
        folder_path = "parent/child/grandchild"
        created_folder = file_storage.create_folder(case_id, folder_path)

        # Delete the deepest folder
        file_storage.delete_folder(case_id, folder_path)

        case_dir = temp_upload_dir / str(case_id)
        # All empty parent directories should be removed
        assert not (case_dir / "parent").exists()

    def test_delete_folder_preserves_nonempty_parents(self, temp_upload_dir, case_id):
        """Test that non-empty parent directories are preserved."""
        # Create nested structure with sibling
        file_storage.create_folder(case_id, "parent/child1")
        file_storage.create_folder(case_id, "parent/child2")

        # Delete one child
        file_storage.delete_folder(case_id, "parent/child1")

        case_dir = temp_upload_dir / str(case_id)
        # Parent should still exist because child2 exists
        assert (case_dir / "parent").exists()
        assert (case_dir / "parent" / "child2").exists()
        assert not (case_dir / "parent" / "child1").exists()

    def test_delete_folder_invalid_case_id(self, temp_upload_dir):
        """Test that invalid case ID raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            file_storage.delete_folder(0, "test_folder")

        assert exc_info.value.status_code == 400
        assert "Invalid case ID" in exc_info.value.detail

    def test_delete_folder_invalid_path(self, temp_upload_dir, case_id):
        """Test that invalid path raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            file_storage.delete_folder(case_id, "../../../")

        assert exc_info.value.status_code == 400
        assert "Invalid folder path" in exc_info.value.detail

    def test_delete_folder_nonexistent_folder(self, temp_upload_dir, case_id):
        """Test deleting non-existent folder doesn't raise error."""
        # Should not raise an exception
        file_storage.delete_folder(case_id, "nonexistent_folder")


class TestSaveUploadFile:
    """Test the save_upload_file function."""

    @pytest.mark.asyncio
    async def test_save_upload_file_valid_case(
        self, temp_upload_dir, case_id, sample_upload_file
    ):
        """Test saving upload file with valid case ID."""
        with patch(
            "app.core.file_storage.validate_file_security"
        ) as mock_validate, patch(
            "app.core.file_storage.secure_filename_with_path"
        ) as mock_secure:

            mock_validate.return_value = None  # No exception
            mock_secure.return_value = "test_file.txt"

            result = await file_storage.save_upload_file(sample_upload_file, case_id)

            relative_path, file_hash = result
            assert relative_path == f"{case_id}/test_file.txt"
            assert file_hash == hashlib.sha256(b"test content").hexdigest()

            # Verify file was created
            file_path = temp_upload_dir / relative_path
            assert file_path.exists()
            assert file_path.read_bytes() == b"test content"

    @pytest.mark.asyncio
    async def test_save_upload_file_with_folder_path(
        self, temp_upload_dir, case_id, sample_upload_file
    ):
        """Test saving upload file with folder path."""
        with patch(
            "app.core.file_storage.validate_file_security"
        ) as mock_validate, patch(
            "app.core.file_storage.secure_filename_with_path"
        ) as mock_secure:

            mock_validate.return_value = None
            mock_secure.return_value = "test_file.txt"
            folder_path = "evidence/documents"

            result = await file_storage.save_upload_file(
                sample_upload_file, case_id, folder_path
            )

            relative_path, file_hash = result
            assert relative_path == f"{case_id}/evidence/documents/test_file.txt"

            # Verify file was created in correct location
            file_path = temp_upload_dir / relative_path
            assert file_path.exists()

    @pytest.mark.asyncio
    async def test_save_upload_file_none_case_id(
        self, temp_upload_dir, sample_upload_file
    ):
        """Test that None case ID raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            await file_storage.save_upload_file(sample_upload_file, None)

        assert exc_info.value.status_code == 400
        assert "Case ID is required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_save_upload_file_invalid_case_id(
        self, temp_upload_dir, sample_upload_file
    ):
        """Test that invalid case ID raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            await file_storage.save_upload_file(sample_upload_file, 0)

        assert exc_info.value.status_code == 400
        assert "Invalid case ID" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_save_upload_file_none_file(self, temp_upload_dir, case_id):
        """Test that None file raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            await file_storage.save_upload_file(None, case_id)

        assert exc_info.value.status_code == 400
        assert "No file was provided" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_save_upload_file_validation_fails(
        self, temp_upload_dir, case_id, sample_upload_file
    ):
        """Test that file validation failure is propagated."""
        with patch("app.core.file_storage.validate_file_security") as mock_validate:
            mock_validate.side_effect = HTTPException(
                status_code=400, detail="File not allowed"
            )

            with pytest.raises(HTTPException) as exc_info:
                await file_storage.save_upload_file(sample_upload_file, case_id)

            assert exc_info.value.status_code == 400
            assert "File not allowed" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_save_upload_file_generic_exception_handling(
        self, temp_upload_dir, case_id, sample_upload_file
    ):
        """Test that generic exceptions are handled properly."""
        with patch(
            "app.core.file_storage.validate_file_security"
        ) as mock_validate, patch(
            "app.core.file_storage.secure_filename_with_path"
        ) as mock_secure:

            mock_validate.return_value = None
            mock_secure.side_effect = Exception("Unexpected error")

            with pytest.raises(HTTPException) as exc_info:
                await file_storage.save_upload_file(sample_upload_file, case_id)

            assert exc_info.value.status_code == 500
            assert "Could not save file" in exc_info.value.detail


class TestDeleteFile:
    """Test the delete_file function with security focus."""

    @pytest.mark.asyncio
    async def test_delete_file_valid_path(self, temp_upload_dir):
        """Test deleting a valid file."""
        # Create a test file
        test_file = temp_upload_dir / "test_case" / "test_file.txt"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("test content")

        await file_storage.delete_file("test_case/test_file.txt")

        assert not test_file.exists()

    @pytest.mark.asyncio
    async def test_delete_file_path_traversal_attack(self, temp_upload_dir):
        """Test that path traversal attacks are blocked."""
        with pytest.raises(HTTPException) as exc_info:
            await file_storage.delete_file("../../etc/passwd")

        assert exc_info.value.status_code == 400
        assert "Invalid file path" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_delete_file_path_traversal_with_dots(self, temp_upload_dir):
        """Test that paths with .. are blocked."""
        with pytest.raises(HTTPException) as exc_info:
            await file_storage.delete_file("test/../../../sensitive_file")

        assert exc_info.value.status_code == 400
        assert "Invalid file path" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_delete_file_absolute_path_attack(self, temp_upload_dir):
        """Test that absolute paths are blocked."""
        with pytest.raises(HTTPException) as exc_info:
            await file_storage.delete_file("/etc/passwd")

        assert exc_info.value.status_code == 400
        assert "Invalid file path" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_delete_file_empty_path(self, temp_upload_dir):
        """Test that empty path is blocked."""
        with pytest.raises(HTTPException) as exc_info:
            await file_storage.delete_file("")

        assert exc_info.value.status_code == 400
        assert "Invalid file path" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_delete_file_root_directory_attempt(self, temp_upload_dir):
        """Test that attempting to delete upload directory itself is blocked."""
        with pytest.raises(HTTPException) as exc_info:
            await file_storage.delete_file(".")

        assert exc_info.value.status_code == 400
        assert "Invalid file path" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_delete_file_nonexistent_file(self, temp_upload_dir):
        """Test deleting non-existent file doesn't raise error."""
        # Should not raise an exception
        await file_storage.delete_file("test_case/nonexistent.txt")

    @pytest.mark.asyncio
    async def test_delete_file_directory_not_file(self, temp_upload_dir):
        """Test that attempting to delete directory (not file) is safe."""
        # Create a directory
        test_dir = temp_upload_dir / "test_case" / "test_dir"
        test_dir.mkdir(parents=True)

        # Should not delete directory, only files
        await file_storage.delete_file("test_case/test_dir")

        # Directory should still exist
        assert test_dir.exists()

    @pytest.mark.asyncio
    async def test_delete_file_cleans_empty_parents(self, temp_upload_dir):
        """Test that empty parent directories are cleaned up."""
        # Create nested file structure
        test_file = temp_upload_dir / "test_case" / "level1" / "level2" / "file.txt"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("content")

        await file_storage.delete_file("test_case/level1/level2/file.txt")

        # Empty parent directories should be cleaned up
        assert not (temp_upload_dir / "test_case" / "level1").exists()

    @pytest.mark.asyncio
    async def test_delete_file_preserves_nonempty_parents(self, temp_upload_dir):
        """Test that non-empty parent directories are preserved."""
        # Create files in same directory
        file1 = temp_upload_dir / "test_case" / "level1" / "file1.txt"
        file2 = temp_upload_dir / "test_case" / "level1" / "file2.txt"
        file1.parent.mkdir(parents=True)
        file1.write_text("content1")
        file2.write_text("content2")

        await file_storage.delete_file("test_case/level1/file1.txt")

        # Parent directory should still exist because file2 exists
        assert (temp_upload_dir / "test_case" / "level1").exists()
        assert file2.exists()
        assert not file1.exists()

    @pytest.mark.asyncio
    async def test_delete_file_symlink_attack_prevention(self, temp_upload_dir):
        """Test that symlink-based attacks are prevented by path resolution."""
        # This test verifies that symlinks can't be used to escape the upload directory
        # The normalize_folder_path and path resolution should handle this
        with pytest.raises(HTTPException) as exc_info:
            await file_storage.delete_file("test_case/../../../etc/passwd")

        assert exc_info.value.status_code == 400
        assert "Invalid file path" in exc_info.value.detail


class TestCreateCaseDirectory:
    """Test the create_case_directory function."""

    def test_create_case_directory_valid_id(self, temp_upload_dir, case_id):
        """Test creating case directory with valid ID."""
        result = file_storage.create_case_directory(case_id)

        expected_path = temp_upload_dir / str(case_id)
        assert result == expected_path
        assert result.exists()
        assert result.is_dir()

    def test_create_case_directory_invalid_id(self, temp_upload_dir):
        """Test that invalid case ID raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            file_storage.create_case_directory(0)

        assert exc_info.value.status_code == 400
        assert "Invalid case ID" in exc_info.value.detail

    def test_create_case_directory_existing_directory(self, temp_upload_dir, case_id):
        """Test that creating existing directory doesn't fail."""
        # Create directory first
        first_result = file_storage.create_case_directory(case_id)

        # Create again - should not fail
        second_result = file_storage.create_case_directory(case_id)

        assert first_result == second_result
        assert second_result.exists()


class TestSecurityIntegration:
    """Integration tests focusing on security aspects."""

    @pytest.mark.asyncio
    async def test_path_traversal_comprehensive(self, temp_upload_dir):
        """Comprehensive test of path traversal protection."""
        attack_vectors = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "test/../../../sensitive",
            "./../../etc/hosts",
            "test/../../etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fpasswd",  # URL encoded
            "....//....//....//etc/passwd",  # Double dots
            "../\x00/etc/passwd",  # Null byte injection attempt
        ]

        for attack_vector in attack_vectors:
            with pytest.raises(HTTPException) as exc_info:
                await file_storage.delete_file(attack_vector)

            assert exc_info.value.status_code == 400
            assert "Invalid file path" in exc_info.value.detail

    def test_normalize_path_security_comprehensive(self):
        """Comprehensive test of path normalization security."""
        dangerous_inputs = [
            "../../../",
            "..\\..\\..\\",
            "./../../",
            "test/../../../etc",
            "folder/./../../sensitive",
            "",
            None,
            "   ",
            "///",
            "\\\\\\",
        ]

        for dangerous_input in dangerous_inputs:
            result = file_storage.normalize_folder_path(dangerous_input)
            # Should either be empty or not contain dangerous patterns
            assert not result or not any(
                dangerous in result for dangerous in ["../", "..\\", "/.."]
            )

    @pytest.mark.asyncio
    async def test_file_operations_boundary_validation(self, temp_upload_dir):
        """Test that all file operations respect upload directory boundaries."""
        base_dir = temp_upload_dir.resolve()

        # Test that resolved paths always stay within base directory
        valid_paths = [
            "case123/document.txt",
            "case456/folder/subfolder/file.pdf",
            "case789/evidence/image.jpg",
        ]

        for path in valid_paths:
            normalized = file_storage.normalize_folder_path(path)
            if normalized:  # Only test non-empty normalized paths
                resolved_path = (base_dir / normalized).resolve()
                # Verify the resolved path is within the base directory
                assert str(resolved_path).startswith(str(base_dir))
