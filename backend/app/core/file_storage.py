"""
File storage utilities for handling evidence uploads
"""

from pathlib import Path
from typing import Optional
from fastapi import UploadFile, HTTPException

from .security import validate_file_security, secure_filename_with_path

UPLOAD_DIR = Path("uploads")
if not UPLOAD_DIR.exists():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


async def save_upload_file(
    upload_file: UploadFile, case_id: int, subfolder: Optional[str] = None
) -> str:
    """
    Save an uploaded file to the uploads directory.
    Returns the relative path to the saved file.
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
        # Create case-specific directory
        case_dir = UPLOAD_DIR / str(case_id)
        if subfolder:
            case_dir = case_dir / subfolder
        case_dir.mkdir(parents=True, exist_ok=True)

        safe_filename = secure_filename_with_path(upload_file.filename, case_dir)
        file_path = case_dir / safe_filename

        with open(file_path, "wb") as buffer:
            content = await upload_file.read()
            buffer.write(content)

        # Return the relative path from the uploads directory
        return str(file_path.relative_to(UPLOAD_DIR))
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
