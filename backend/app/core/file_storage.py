"""
File storage utilities for handling evidence uploads
"""

import hashlib
import os
import shutil
import urllib.parse
from pathlib import Path
from typing import Any, Optional, Tuple
from uuid import UUID

from .exceptions import DomainException, ValidationException
from .logging import get_security_logger
from .security import secure_filename_with_path, validate_file_security

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
EXECUTION_ARTIFACT_DIR = ".execution-artifacts"


def _case_dir(case_id: int) -> Path:
    if not isinstance(case_id, int) or case_id <= 0:
        raise ValidationException(f"Invalid case ID: {case_id}")
    return UPLOAD_DIR / str(case_id)


def _remove_empty_parents(path: Path, stop: Path) -> None:
    parent = path.parent
    while parent != stop and parent.exists() and not any(parent.iterdir()):
        parent.rmdir()
        parent = parent.parent


def normalize_folder_path(folder_path: str) -> str:
    """
    Normalize and validate a folder path to prevent directory traversal attacks.
    Returns a safe, normalized folder path.
    """
    if not folder_path:
        return ""

    path = folder_path.strip().strip("/\\")

    if "\x00" in path or any(ord(c) < 32 for c in path if c not in " "):
        return ""

    if len(path) > 255:
        return ""

    parts = []
    for part in path.split("/"):
        # Check dots after sanitizing: "..!" must not become "..".
        sanitized = "".join(c for c in part if c.isalnum() or c in "._- ").strip()
        if sanitized.strip(".") and len(sanitized) <= 100:
            parts.append(sanitized)

    return "/".join(parts) if parts else ""


def _user_folder_path(folder_path: str | None) -> str:
    """Normalize a user folder path; the Case's execution artifact directory is reserved."""
    normalized = normalize_folder_path(folder_path or "")
    if normalized.partition("/")[0] == EXECUTION_ARTIFACT_DIR:
        raise ValidationException("Invalid folder path")
    return normalized


def _contained(root: Path, relative: str) -> Path:
    path = root / relative
    real_root = os.path.realpath(root)
    real_path = os.path.realpath(path)
    if real_path != real_root and not real_path.startswith(real_root + os.sep):
        raise ValidationException("Invalid folder path")
    return path


def create_folder(case_id: int, folder_path: str) -> Path:
    """
    Create a folder structure within a case directory.
    Returns the path to the created folder.
    """
    case_dir = _case_dir(case_id)
    if not folder_path:
        raise ValidationException("Folder path is required")

    normalized_path = _user_folder_path(folder_path)
    if not normalized_path:
        raise ValidationException("Invalid folder path")

    folder_dir = _contained(case_dir, normalized_path)
    folder_dir.mkdir(parents=True, exist_ok=True)
    return folder_dir


def delete_folder(case_id: int, folder_path: str) -> None:
    """
    Delete a folder and all its contents from a case directory.
    """
    case_dir = _case_dir(case_id)
    normalized_path = _user_folder_path(folder_path)
    if not normalized_path:
        raise ValidationException("Invalid folder path")

    folder_dir = _contained(case_dir, normalized_path)
    if folder_dir.is_dir():
        shutil.rmtree(folder_dir)
    _remove_empty_parents(folder_dir, case_dir)


async def save_upload_file(
    upload_file: Any,
    case_id: int,
    folder_path: Optional[str] = None,
    *,
    artifact_id: str | None = None,
) -> Tuple[str, str]:
    """
    Save an uploaded file to the uploads directory.
    Returns a tuple of (relative_path, file_hash).
    """
    case_root = _case_dir(case_id)
    if upload_file is None:
        raise ValidationException("No file was provided for upload")

    await validate_file_security(upload_file)

    security_logger = get_security_logger(
        event="file_upload_validated",
        filename=upload_file.filename,
        case_id=case_id,
        file_size=upload_file.size if hasattr(upload_file, "size") else None,
    )
    security_logger.info(f"File upload validated: {upload_file.filename}")

    try:
        case_dir = _contained(case_root, _user_folder_path(folder_path))
        case_dir.mkdir(parents=True, exist_ok=True)

        if artifact_id is not None:
            # Only internal effect adapters supply this UUID. A reserved directory
            # keeps reconciliation separate from ordinary uploaded evidence.
            control_id, _, identity = artifact_id.partition("-")
            if not control_id.isdigit() or int(control_id) <= 0:
                raise ValidationException("Invalid execution artifact identity")
            artifact_id = f"{int(control_id)}-{UUID(identity)}"
            case_dir = case_root / EXECUTION_ARTIFACT_DIR
            case_dir.mkdir(parents=True, exist_ok=True)
            safe_filename = f"{artifact_id}.txt"
        else:
            safe_filename = secure_filename_with_path(upload_file.filename, case_dir)
        file_path = case_dir / safe_filename

        content = await upload_file.read()

        if len(content) > 15 * 1024 * 1024:  # 15 MiB limit
            raise ValidationException("File too large. Maximum size is 15 MiB")

        file_hash = hashlib.sha256(content).hexdigest()

        if artifact_id:
            staging_path = file_path.with_suffix(".staging")
            with open(staging_path, "wb") as buffer:
                buffer.write(content)
                buffer.flush()
                os.fsync(buffer.fileno())
            os.replace(staging_path, file_path)
            directory_fd = os.open(case_dir, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        else:
            # Exclusive create: a concurrent upload that took this name gets the next one.
            while True:
                try:
                    with open(file_path, "xb") as buffer:
                        buffer.write(content)
                    break
                except FileExistsError:
                    file_path = case_dir / secure_filename_with_path(
                        upload_file.filename, case_dir
                    )

        relative_path = str(file_path.relative_to(UPLOAD_DIR))

        security_logger = get_security_logger(
            event="file_upload_complete",
            filename=upload_file.filename,
            case_id=case_id,
            relative_path=relative_path,
            file_hash=file_hash,
        )
        security_logger.info(
            f"File uploaded successfully: {upload_file.filename} to {relative_path}"
        )

        return relative_path, file_hash
    except DomainException:
        raise
    except Exception as e:
        try:
            if "file_path" in locals() and file_path.exists():
                file_path.unlink()
            if (
                "case_dir" in locals()
                and case_dir.exists()
                and not any(case_dir.iterdir())
            ):
                case_dir.rmdir()
        except Exception as cleanup_error:
            security_logger = get_security_logger(
                event="file_cleanup_error", case_id=case_id
            )
            security_logger.warning(
                f"Failed to cleanup after file save error: {cleanup_error}"
            )
        security_logger = get_security_logger(
            event="file_upload_error", filename=upload_file.filename, case_id=case_id
        )
        security_logger.error(f"Failed to save file {upload_file.filename}: {str(e)}")

        raise DomainException(
            "Could not save file. Please try again or contact support."
        ) from e


async def delete_file(relative_path: str) -> None:
    """Delete a file from the uploads directory."""
    try:
        if not relative_path:
            raise ValidationException("Invalid file path")

        decoded_path = urllib.parse.unquote(relative_path)

        if (
            ".." in decoded_path
            or relative_path.startswith("/")
            or "\x00" in decoded_path
            or "..." in decoded_path
        ):
            raise ValidationException("Invalid file path")

        normalized_path = normalize_folder_path(relative_path)
        if not normalized_path:
            raise ValidationException("Invalid file path")

        base_dir = UPLOAD_DIR.resolve()
        file_path = (base_dir / normalized_path).resolve()

        try:
            file_path.relative_to(base_dir)
        except ValueError:
            raise ValidationException("Invalid file path")

        if file_path == base_dir:
            raise ValidationException("Invalid file path")
        if file_path.exists() and file_path.is_file():
            file_path.unlink()

            security_logger = get_security_logger(
                event="file_delete_complete", file_path=relative_path
            )
            security_logger.info(f"File deleted successfully: {relative_path}")
        _remove_empty_parents(file_path, base_dir)

    except DomainException:
        raise
    except Exception as e:
        security_logger = get_security_logger(
            event="file_delete_error", file_path=relative_path
        )
        security_logger.error(f"Failed to delete file {relative_path}: {str(e)}")

        raise DomainException("Could not delete file") from e


def evidence_file_path(case_id: int, relative_path: str) -> Path:
    """Resolve stored Evidence inside its own Case; callers authorize the record first."""
    root = UPLOAD_DIR.resolve()
    case_root = root / str(case_id)
    path = (root / relative_path).resolve()
    if not case_root.is_relative_to(root) or case_root.resolve() != case_root:
        raise ValueError("Invalid Case storage")
    if not path.is_relative_to(case_root) or not path.is_file():
        raise ValueError("Evidence file unavailable")
    return path
