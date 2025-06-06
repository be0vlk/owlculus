"""
File storage utilities for handling evidence uploads
"""

import os
import hashlib
from pathlib import Path
from typing import Optional, Tuple
from fastapi import UploadFile, HTTPException

from .security import validate_file_security, secure_filename_with_path

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
    """
    if not folder_path:
        return ""
    
    # Remove leading/trailing whitespace and slashes
    path = folder_path.strip().strip("/\\")
    
    # Split path and validate each component
    parts = []
    for part in path.split("/"):
        part = part.strip()
        if not part or part in (".", ".."):
            continue
        # Sanitize the folder name
        sanitized = "".join(c for c in part if c.isalnum() or c in "._- ")
        if sanitized:
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

        # Read file content once
        content = await upload_file.read()
        
        # Calculate hash
        file_hash = calculate_file_hash(content)
        
        # Save file
        with open(file_path, "wb") as buffer:
            buffer.write(content)

        # Return the relative path and hash
        relative_path = str(file_path.relative_to(UPLOAD_DIR))
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
        except:
            pass
        raise HTTPException(
            status_code=500,
            detail=f"Could not save file: {str(e)}",
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
        file_path = UPLOAD_DIR / relative_path
        if file_path.exists():
            file_path.unlink()

        # Remove empty parent directories
        parent_dir = file_path.parent
        while parent_dir != UPLOAD_DIR and not any(parent_dir.iterdir()):
            parent_dir.rmdir()
            parent_dir = parent_dir.parent
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not delete file: {str(e)}")
