"""
File storage utilities for handling evidence uploads
"""

import hashlib
import urllib.parse
from pathlib import Path
from typing import Optional, Tuple

from fastapi import HTTPException, UploadFile

from .logging import get_security_logger
from .security import secure_filename_with_path, validate_file_security

UPLOAD_DIR = Path("uploads")
if not UPLOAD_DIR.exists():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def calculate_file_hash(content: bytes) -> str:
    """
    Calculate SHA-256 hash of file content.
    Returns the hash as a hexadecimal string.
    """
    hasher = hashlib.sha256()
    hasher.update(content)
    return hasher.hexdigest()


def normalize_folder_path(folder_path: str) -> str:
    """
    Normalize and validate a folder path to prevent directory traversal attacks.
    Returns a safe, normalized folder path.
    
    OWASP-compliant path sanitization that:
    - Removes dangerous path components (., .., null bytes)
    - Sanitizes filenames to alphanumeric + safe chars only
    - Validates path length and structure
    """
    if not folder_path:
        return ""

    # Remove leading/trailing whitespace and slashes
    path = folder_path.strip().strip("/\\")
    
    # Additional security: check for null bytes and other dangerous chars
    if "\x00" in path or any(ord(c) < 32 for c in path if c not in " "):
        return ""
    
    # Limit path length to prevent resource exhaustion
    if len(path) > 255:
        return ""

    # Split path and validate each component
    parts = []
    for part in path.split("/"):
        part = part.strip()
        if not part or part in (".", "..", "..."):
            continue
        
        # More restrictive sanitization - only allow safe characters
        sanitized = "".join(c for c in part if c.isalnum() or c in "._- ")
        
        # Ensure component isn't empty after sanitization and has reasonable length
        if sanitized and len(sanitized) <= 100:
            parts.append(sanitized)

    return "/".join(parts) if parts else ""


def create_folder(case_id: int, folder_path: str) -> Path:
    """
    Create a folder structure within a case directory.
    Returns the path to the created folder.
    """
    if not isinstance(case_id, int) or case_id <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid case ID: {case_id}",
        )

    if not folder_path:
        raise HTTPException(
            status_code=400,
            detail="Folder path is required",
        )

    normalized_path = normalize_folder_path(folder_path)
    if not normalized_path:
        raise HTTPException(
            status_code=400,
            detail="Invalid folder path",
        )

    case_dir = UPLOAD_DIR / str(case_id)
    folder_dir = case_dir / normalized_path
    folder_dir.mkdir(parents=True, exist_ok=True)
    return folder_dir


def delete_folder(case_id: int, folder_path: str) -> None:
    """
    Delete a folder and all its contents from a case directory.
    """
    if not isinstance(case_id, int) or case_id <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid case ID: {case_id}",
        )

    normalized_path = normalize_folder_path(folder_path)
    if not normalized_path:
        raise HTTPException(
            status_code=400,
            detail="Invalid folder path",
        )

    case_dir = UPLOAD_DIR / str(case_id)
    folder_dir = case_dir / normalized_path

    if folder_dir.exists() and folder_dir.is_dir():
        import shutil

        shutil.rmtree(folder_dir)

    # Clean up empty parent directories
    parent = folder_dir.parent
    while parent != case_dir and parent.exists() and not any(parent.iterdir()):
        parent.rmdir()
        parent = parent.parent


async def save_upload_file(
    upload_file: UploadFile, case_id: int, folder_path: Optional[str] = None
) -> Tuple[str, str]:
    """
    Save an uploaded file to the uploads directory.
    Returns a tuple of (relative_path, file_hash).
    """
    # Validate case_id
    if case_id is None:
        raise HTTPException(
            status_code=400,
            detail="Case ID is required but was not provided",
        )

    if not isinstance(case_id, int) or case_id <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid case ID: {case_id}. Please ensure you're uploading to a valid case.",
        )

    # Validate the file first
    if upload_file is None:
        raise HTTPException(
            status_code=400,
            detail="No file was provided for upload",
        )

    await validate_file_security(upload_file)
    
    # Log successful file upload validation for security monitoring
    security_logger = get_security_logger(
        event="file_upload_validated",
        filename=upload_file.filename,
        case_id=case_id,
        file_size=upload_file.size if hasattr(upload_file, 'size') else None
    )
    security_logger.info(f"File upload validated: {upload_file.filename}")

    try:
        # Create case-specific directory with optional folder path
        case_dir = UPLOAD_DIR / str(case_id)
        if folder_path:
            # Normalize and validate folder path
            normalized_path = normalize_folder_path(folder_path)
            case_dir = case_dir / normalized_path
        case_dir.mkdir(parents=True, exist_ok=True)

        safe_filename = secure_filename_with_path(upload_file.filename, case_dir)
        file_path = case_dir / safe_filename

        # Read file content once with size check
        content = await upload_file.read()
        
        # Check file size after reading (additional safety check)
        if len(content) > 15 * 1024 * 1024:  # 15MB limit
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size is 15MB"
            )

        # Calculate hash
        file_hash = calculate_file_hash(content)

        # Save file
        with open(file_path, "wb") as buffer:
            buffer.write(content)

        # Return the relative path and hash
        relative_path = str(file_path.relative_to(UPLOAD_DIR))
        
        # Log successful file upload for security monitoring
        security_logger = get_security_logger(
            event="file_upload_complete",
            filename=upload_file.filename,
            case_id=case_id,
            relative_path=relative_path,
            file_hash=file_hash
        )
        security_logger.info(f"File uploaded successfully: {upload_file.filename} to {relative_path}")
        
        return relative_path, file_hash
    except HTTPException:
        raise
    except Exception as e:
        # Clean up any partially created directories/files
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
            # Log cleanup failures for monitoring
            security_logger = get_security_logger(
                event="file_cleanup_error",
                case_id=case_id
            )
            security_logger.warning(f"Failed to cleanup after file save error: {cleanup_error}")
        # Log the actual error for debugging
        security_logger = get_security_logger(
            event="file_upload_error",
            filename=upload_file.filename,
            case_id=case_id
        )
        security_logger.error(f"Failed to save file {upload_file.filename}: {str(e)}")
        
        raise HTTPException(
            status_code=500,
            detail="Could not save file. Please try again or contact support.",
        )


def create_case_directory(case_id: int) -> Path:
    """
    Create the directory structure for a new case.
    Returns the path to the created case directory.
    """
    if not isinstance(case_id, int) or case_id <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid case ID: {case_id}",
        )

    case_dir = UPLOAD_DIR / str(case_id)
    case_dir.mkdir(parents=True, exist_ok=True)
    return case_dir


async def delete_file(relative_path: str) -> None:
    """Delete a file from the uploads directory."""
    try:
        # Security: Check for path traversal attempts before normalization
        if not relative_path:
            raise HTTPException(status_code=400, detail="Invalid file path")
            
        # Decode URL encoded strings
        decoded_path = urllib.parse.unquote(relative_path)
        
        # Check for various path traversal patterns
        if (
            ".." in decoded_path or 
            relative_path.startswith("/") or 
            "\x00" in decoded_path or  # Null bytes
            "..." in decoded_path  # Multiple dots
        ):
            raise HTTPException(status_code=400, detail="Invalid file path")
        
        normalized_path = normalize_folder_path(relative_path)
        if not normalized_path:
            raise HTTPException(status_code=400, detail="Invalid file path")
        
        base_dir = UPLOAD_DIR.resolve()
        file_path = (base_dir / normalized_path).resolve()

        # Use Path.relative_to() for more robust path validation
        try:
            file_path.relative_to(base_dir)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid file path")

        if file_path == base_dir:
            raise HTTPException(status_code=400, detail="Invalid file path")
        if file_path.exists() and file_path.is_file():
            file_path.unlink()
            
            # Log successful file deletion for security monitoring
            security_logger = get_security_logger(
                event="file_delete_complete",
                file_path=relative_path
            )
            security_logger.info(f"File deleted successfully: {relative_path}")
        parent_dir = file_path.parent
        while parent_dir != base_dir and parent_dir.exists() and not any(parent_dir.iterdir()):
            parent_dir.rmdir()
            parent_dir = parent_dir.parent
            
    except HTTPException:
        raise
    except Exception as e:
        # Log the actual error for debugging
        security_logger = get_security_logger(
            event="file_delete_error",
            file_path=relative_path
        )
        security_logger.error(f"Failed to delete file {relative_path}: {str(e)}")
        
        raise HTTPException(status_code=500, detail="Could not delete file")
