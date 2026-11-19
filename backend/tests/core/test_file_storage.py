"""
Tests for the file_storage module with comprehensive security testing.
"""

import hashlib
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastapi import UploadFile
from loguru import logger

from app.core import file_storage
from app.core.exceptions import DomainException, ValidationException


@pytest.fixture
def temp_upload_dir():
    """Create a temporary upload directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
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

    @pytest.mark.parametrize(
        "raw", ["..!/..!/etc", "..\\/..\\/x", "a/..$/b", ".. /x", "..?", "..?/..?/..?"]
    )
    def test_normalize_path_drops_parts_that_sanitize_to_dots(self, raw):
        parts = file_storage.normalize_folder_path(raw).split("/")
        assert ".." not in parts and "." not in parts


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
        with pytest.raises(ValidationException) as exc_info:
            file_storage.create_folder(0, "test_folder")
        assert "Invalid case ID" in str(exc_info.value)

    def test_create_folder_invalid_case_id_negative(self, temp_upload_dir):
        """Test that negative case ID raises HTTPException."""
        with pytest.raises(ValidationException) as exc_info:
            file_storage.create_folder(-1, "test_folder")
        assert "Invalid case ID" in str(exc_info.value)

    def test_create_folder_invalid_case_id_string(self, temp_upload_dir):
        """Test that string case ID raises HTTPException."""
        with pytest.raises(ValidationException) as exc_info:
            file_storage.create_folder("invalid", "test_folder")
        assert "Invalid case ID" in str(exc_info.value)

    def test_create_folder_empty_path(self, temp_upload_dir, case_id):
        """Test that empty folder path raises HTTPException."""
        with pytest.raises(ValidationException) as exc_info:
            file_storage.create_folder(case_id, "")
        assert "Folder path is required" in str(exc_info.value)

    def test_create_folder_invalid_path_after_normalization(
        self, temp_upload_dir, case_id
    ):
        """Test that path invalid after normalization raises HTTPException."""
        with pytest.raises(ValidationException) as exc_info:
            file_storage.create_folder(case_id, "../../../")
        assert "Invalid folder path" in str(exc_info.value)

    def test_create_folder_rejects_execution_artifact_directory(
        self, temp_upload_dir, case_id
    ):
        """Only the Case-root execution artifact directory is reserved."""
        for folder_path in (".execution-artifacts", "/.execution-artifacts/sub"):
            with pytest.raises(ValidationException, match="Invalid folder path"):
                file_storage.create_folder(case_id, folder_path)
        assert file_storage.create_folder(
            case_id, "notes/.execution-artifacts"
        ).is_dir()

    def test_create_folder_nested_path(self, temp_upload_dir, case_id):
        """Test creating nested folder structure."""
        folder_path = "level1/level2/level3"

        result = file_storage.create_folder(case_id, folder_path)

        assert result.exists()
        assert result.is_dir()
        assert (temp_upload_dir / str(case_id) / "level1").exists()
        assert (temp_upload_dir / str(case_id) / "level1" / "level2").exists()


class TestDeleteFolder:
    """Test the delete_folder function."""

    def test_delete_folder_valid_case_and_path(self, temp_upload_dir, case_id):
        """Test deleting existing folder."""
        folder_path = "test_folder"
        created_folder = file_storage.create_folder(case_id, folder_path)
        assert created_folder.exists()

        file_storage.delete_folder(case_id, folder_path)

        assert not created_folder.exists()

    def test_delete_folder_with_contents(self, temp_upload_dir, case_id):
        """Test deleting folder with files inside."""
        folder_path = "test_folder"
        created_folder = file_storage.create_folder(case_id, folder_path)
        test_file = created_folder / "test.txt"
        test_file.write_text("test content")

        file_storage.delete_folder(case_id, folder_path)

        assert not created_folder.exists()
        assert not test_file.exists()

    def test_delete_folder_removes_empty_parents(self, temp_upload_dir, case_id):
        """Test that empty parent directories are cleaned up."""
        folder_path = "parent/child/grandchild"
        file_storage.create_folder(case_id, folder_path)

        file_storage.delete_folder(case_id, folder_path)

        case_dir = temp_upload_dir / str(case_id)
        assert not (case_dir / "parent").exists()

    def test_delete_folder_preserves_nonempty_parents(self, temp_upload_dir, case_id):
        """Test that non-empty parent directories are preserved."""
        file_storage.create_folder(case_id, "parent/child1")
        file_storage.create_folder(case_id, "parent/child2")

        file_storage.delete_folder(case_id, "parent/child1")

        case_dir = temp_upload_dir / str(case_id)
        assert (case_dir / "parent").exists()
        assert (case_dir / "parent" / "child2").exists()
        assert not (case_dir / "parent" / "child1").exists()

    def test_delete_folder_invalid_case_id(self, temp_upload_dir):
        """Test that invalid case ID raises HTTPException."""
        with pytest.raises(ValidationException) as exc_info:
            file_storage.delete_folder(0, "test_folder")
        assert "Invalid case ID" in str(exc_info.value)

    def test_delete_folder_invalid_path(self, temp_upload_dir, case_id):
        """Test that invalid path raises HTTPException."""
        with pytest.raises(ValidationException) as exc_info:
            file_storage.delete_folder(case_id, "../../../")
        assert "Invalid folder path" in str(exc_info.value)

    def test_delete_folder_preserves_execution_artifacts(
        self, temp_upload_dir, case_id
    ):
        """A user folder delete cannot remove execution-owned artifacts."""
        artifact = temp_upload_dir / str(case_id) / ".execution-artifacts" / "1-a.txt"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("artifact")
        with pytest.raises(ValidationException, match="Invalid folder path"):
            file_storage.delete_folder(case_id, ".execution-artifacts")
        assert artifact.exists()

    def test_delete_folder_nonexistent_folder(self, temp_upload_dir, case_id):
        """Test deleting non-existent folder doesn't raise error."""
        file_storage.delete_folder(case_id, "nonexistent_folder")

    def test_delete_folder_stays_inside_case(self, temp_upload_dir, case_id):
        (temp_upload_dir / str(case_id)).mkdir()
        outside = temp_upload_dir / "outside"
        outside.mkdir()

        file_storage.delete_folder(case_id, "..!/outside")

        assert outside.is_dir()


class TestSaveUploadFile:
    """Test the save_upload_file function."""

    @pytest.mark.asyncio
    async def test_save_upload_file_valid_case(
        self, temp_upload_dir, case_id, sample_upload_file
    ):
        """Test saving upload file with valid case ID."""
        with (
            patch("app.core.file_storage.validate_file_security") as mock_validate,
            patch("app.core.file_storage.secure_filename_with_path") as mock_secure,
        ):
            mock_validate.return_value = None
            mock_secure.return_value = "test_file.txt"

            result = await file_storage.save_upload_file(sample_upload_file, case_id)

            relative_path, file_hash = result
            assert relative_path == f"{case_id}/test_file.txt"
            assert file_hash == hashlib.sha256(b"test content").hexdigest()

            file_path = temp_upload_dir / relative_path
            assert file_path.exists()
            assert file_path.read_bytes() == b"test content"

    @pytest.mark.asyncio
    async def test_save_upload_file_with_folder_path(
        self, temp_upload_dir, case_id, sample_upload_file
    ):
        """Test saving upload file with folder path."""
        with (
            patch("app.core.file_storage.validate_file_security") as mock_validate,
            patch("app.core.file_storage.secure_filename_with_path") as mock_secure,
        ):
            mock_validate.return_value = None
            mock_secure.return_value = "test_file.txt"
            folder_path = "evidence/documents"

            result = await file_storage.save_upload_file(
                sample_upload_file, case_id, folder_path
            )

            relative_path, file_hash = result
            assert relative_path == f"{case_id}/evidence/documents/test_file.txt"

            file_path = temp_upload_dir / relative_path
            assert file_path.exists()

    @pytest.mark.asyncio
    async def test_save_upload_file_rejects_execution_artifact_directory(
        self, temp_upload_dir, case_id, sample_upload_file
    ):
        """User uploads cannot land in the execution artifact directory."""
        with patch("app.core.file_storage.validate_file_security"):
            with pytest.raises(ValidationException, match="Invalid folder path"):
                await file_storage.save_upload_file(
                    sample_upload_file, case_id, ".execution-artifacts"
                )
        assert not (temp_upload_dir / str(case_id) / ".execution-artifacts").exists()

    @pytest.mark.asyncio
    async def test_save_upload_file_keeps_concurrent_upload_with_same_name(
        self, temp_upload_dir, case_id, sample_upload_file
    ):
        """A same-name file created after the name was chosen is not overwritten."""
        real_secure = file_storage.secure_filename_with_path

        def concurrent_upload_takes_name(filename, base_path):
            name = real_secure(filename, base_path)
            if not (base_path / "test_file.txt").exists():
                (base_path / name).write_bytes(b"other upload")
            return name

        with (
            patch("app.core.file_storage.validate_file_security"),
            patch(
                "app.core.file_storage.secure_filename_with_path",
                side_effect=concurrent_upload_takes_name,
            ),
        ):
            relative_path, _ = await file_storage.save_upload_file(
                sample_upload_file, case_id
            )

        case_dir = temp_upload_dir / str(case_id)
        assert relative_path == f"{case_id}/test_file_1.txt"
        assert (case_dir / "test_file.txt").read_bytes() == b"other upload"
        assert (case_dir / "test_file_1.txt").read_bytes() == b"test content"

    @pytest.mark.asyncio
    async def test_save_upload_file_none_case_id(
        self, temp_upload_dir, sample_upload_file
    ):
        """Test that None case ID raises HTTPException."""
        with pytest.raises(ValidationException) as exc_info:
            await file_storage.save_upload_file(sample_upload_file, None)
        assert "Invalid case ID" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_save_upload_file_invalid_case_id(
        self, temp_upload_dir, sample_upload_file
    ):
        """Test that invalid case ID raises HTTPException."""
        with pytest.raises(ValidationException) as exc_info:
            await file_storage.save_upload_file(sample_upload_file, 0)
        assert "Invalid case ID" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_save_upload_file_none_file(self, temp_upload_dir, case_id):
        """Test that None file raises HTTPException."""
        with pytest.raises(ValidationException) as exc_info:
            await file_storage.save_upload_file(None, case_id)
        assert "No file was provided" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_save_upload_file_validation_fails(
        self, temp_upload_dir, case_id, sample_upload_file
    ):
        """Test that file validation failure is propagated."""
        with patch("app.core.file_storage.validate_file_security") as mock_validate:
            mock_validate.side_effect = ValidationException("File not allowed")

            with pytest.raises(ValidationException) as exc_info:
                await file_storage.save_upload_file(sample_upload_file, case_id)
            assert "File not allowed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_save_upload_file_generic_exception_handling(
        self, temp_upload_dir, case_id, sample_upload_file
    ):
        """Test that generic exceptions are handled properly."""
        with (
            patch("app.core.file_storage.validate_file_security") as mock_validate,
            patch("app.core.file_storage.secure_filename_with_path") as mock_secure,
        ):
            mock_validate.return_value = None
            mock_secure.side_effect = Exception("Unexpected error")

            with pytest.raises(DomainException) as exc_info:
                await file_storage.save_upload_file(sample_upload_file, case_id)
            assert "Could not save file" in str(exc_info.value)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("fails", [False, True])
    async def test_save_upload_file_escapes_filename_in_log_messages(
        self, temp_upload_dir, case_id, sample_upload_file, fails
    ):
        sample_upload_file.filename = "a.png\n2026-01-01 | INFO | forged\r\x1b[2J\u2028"
        messages: list[str] = []
        sink = logger.add(lambda message: messages.append(message.record["message"]))
        try:
            with (
                patch("app.core.file_storage.validate_file_security"),
                patch(
                    "app.core.file_storage.secure_filename_with_path",
                    side_effect=Exception("boom") if fails else None,
                    return_value="a.png",
                ) as mock_secure,
            ):
                if fails:
                    with pytest.raises(DomainException):
                        await file_storage.save_upload_file(sample_upload_file, case_id)
                else:
                    await file_storage.save_upload_file(sample_upload_file, case_id)
        finally:
            logger.remove(sink)

        assert mock_secure.call_args.args[0] == sample_upload_file.filename
        escaped = "a.png\\n2026-01-01 | INFO | forged\\r\\x1b[2J\\u2028"
        assert messages[0] == f"File upload validated: {escaped}"
        assert messages[-1] == (
            f"Failed to save file {escaped}: boom"
            if fails
            else f"File uploaded successfully: {escaped} to {case_id}/a.png"
        )


class TestDeleteFile:
    """Test the delete_file function with security focus."""

    @pytest.mark.asyncio
    async def test_delete_file_valid_path(self, temp_upload_dir):
        """Test deleting a valid file."""
        test_file = temp_upload_dir / "test_case" / "test_file.txt"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("test content")

        await file_storage.delete_file("test_case/test_file.txt")

        assert not test_file.exists()

    @pytest.mark.asyncio
    async def test_delete_file_path_traversal_attack(self, temp_upload_dir):
        """Test that path traversal attacks are blocked."""
        with pytest.raises(ValidationException) as exc_info:
            await file_storage.delete_file("../../etc/passwd")
        assert "Invalid file path" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_file_path_traversal_with_dots(self, temp_upload_dir):
        """Test that paths with .. are blocked."""
        with pytest.raises(ValidationException) as exc_info:
            await file_storage.delete_file("test/../../../sensitive_file")
        assert "Invalid file path" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_file_absolute_path_attack(self, temp_upload_dir):
        """Test that absolute paths are blocked."""
        with pytest.raises(ValidationException) as exc_info:
            await file_storage.delete_file("/etc/passwd")
        assert "Invalid file path" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_file_empty_path(self, temp_upload_dir):
        """Test that empty path is blocked."""
        with pytest.raises(ValidationException) as exc_info:
            await file_storage.delete_file("")
        assert "Invalid file path" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_file_root_directory_attempt(self, temp_upload_dir):
        """Test that attempting to delete upload directory itself is blocked."""
        with pytest.raises(ValidationException) as exc_info:
            await file_storage.delete_file(".")
        assert "Invalid file path" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_file_nonexistent_file(self, temp_upload_dir):
        """Test deleting non-existent file doesn't raise error."""
        await file_storage.delete_file("test_case/nonexistent.txt")

    @pytest.mark.asyncio
    async def test_delete_file_directory_not_file(self, temp_upload_dir):
        """Test that attempting to delete directory (not file) is safe."""
        test_dir = temp_upload_dir / "test_case" / "test_dir"
        test_dir.mkdir(parents=True)

        await file_storage.delete_file("test_case/test_dir")

        assert test_dir.exists()

    @pytest.mark.asyncio
    async def test_delete_file_cleans_empty_parents(self, temp_upload_dir):
        """Test that empty parent directories are cleaned up."""
        test_file = temp_upload_dir / "test_case" / "level1" / "level2" / "file.txt"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("content")

        await file_storage.delete_file("test_case/level1/level2/file.txt")

        assert not (temp_upload_dir / "test_case" / "level1").exists()

    @pytest.mark.asyncio
    async def test_delete_file_preserves_nonempty_parents(self, temp_upload_dir):
        """Test that non-empty parent directories are preserved."""
        file1 = temp_upload_dir / "test_case" / "level1" / "file1.txt"
        file2 = temp_upload_dir / "test_case" / "level1" / "file2.txt"
        file1.parent.mkdir(parents=True)
        file1.write_text("content1")
        file2.write_text("content2")

        await file_storage.delete_file("test_case/level1/file1.txt")

        assert (temp_upload_dir / "test_case" / "level1").exists()
        assert file2.exists()
        assert not file1.exists()

    @pytest.mark.asyncio
    async def test_delete_file_symlink_attack_prevention(self, temp_upload_dir):
        """Test that symlink-based attacks are prevented by path resolution."""
        # This test verifies that symlinks can't be used to escape the upload directory
        # The normalize_folder_path and path resolution should handle this
        with pytest.raises(ValidationException) as exc_info:
            await file_storage.delete_file("test_case/../../../etc/passwd")
        assert "Invalid file path" in str(exc_info.value)


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
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fpasswd",
            "....//....//....//etc/passwd",
            "../\x00/etc/passwd",
        ]

        for attack_vector in attack_vectors:
            with pytest.raises(ValidationException) as exc_info:
                await file_storage.delete_file(attack_vector)
            assert "Invalid file path" in str(exc_info.value)

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
            assert not result or not any(
                dangerous in result for dangerous in ["../", "..\\", "/.."]
            )

    @pytest.mark.asyncio
    async def test_file_operations_boundary_validation(self, temp_upload_dir):
        """Test that all file operations respect upload directory boundaries."""
        base_dir = temp_upload_dir.resolve()

        valid_paths = [
            "case123/document.txt",
            "case456/folder/subfolder/file.pdf",
            "case789/evidence/image.jpg",
        ]

        for path in valid_paths:
            normalized = file_storage.normalize_folder_path(path)
            if normalized:
                resolved_path = (base_dir / normalized).resolve()
                assert str(resolved_path).startswith(str(base_dir))
