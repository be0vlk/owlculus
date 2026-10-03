"""Metadata extraction for Evidence files through the exiftool binary."""

import json
import subprocess
from pathlib import Path
from typing import Any

from app.core.exceptions import ValidationException

SUPPORTED_EXTENSIONS = {
    # Images
    *(".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp"),
    *(".heic", ".heif", ".raw", ".cr2", ".nef", ".arw", ".dng"),
    # Video
    *(".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm", ".mkv", ".m4v", ".3gp"),
    # Documents
    *(".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"),
}

# A key joins the first category with a fragment it contains; the rest are "other".
CATEGORY_KEYS = {
    "camera": (
        "EXIF:Make",
        "EXIF:Model",
        "EXIF:LensModel",
        "EXIF:FocalLength",
        "EXIF:FNumber",
        "EXIF:ExposureTime",
        "EXIF:ISO",
        "EXIF:Flash",
        "EXIF:WhiteBalance",
        "EXIF:ColorSpace",
        "EXIF:ExposureProgram",
    ),
    "gps": (
        "EXIF:GPSLatitude",
        "EXIF:GPSLongitude",
        "EXIF:GPSAltitude",
        "EXIF:GPSTimeStamp",
        "EXIF:GPSDateStamp",
        "Composite:GPSPosition",
    ),
    "timestamps": (
        "EXIF:DateTimeOriginal",
        "EXIF:CreateDate",
        "EXIF:ModifyDate",
        "File:FileModifyDate",
        "File:FileAccessDate",
        "File:FileCreateDate",
    ),
    "technical": (
        "File:FileSize",
        "File:FileType",
        "File:MIMEType",
        "EXIF:ImageWidth",
        "EXIF:ImageHeight",
        "EXIF:BitsPerSample",
        "EXIF:ColorComponents",
        "EXIF:Compression",
        "File:FilePermissions",
    ),
}


def extract_metadata(path: Path) -> dict[str, Any]:
    """Run exiftool on a supported file and shape it for the metadata view."""
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValidationException("Unsupported file type for metadata extraction")
    try:
        output = subprocess.run(
            ["exiftool", "-j", "-G", "-n", str(path)],
            capture_output=True,
            check=True,
            encoding="utf-8",
            timeout=30,
        ).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise ValidationException("Could not read metadata from this file") from error
    raw: dict[str, Any] = json.loads(output)[0]

    categories: dict[str, dict[str, Any]] = {
        name: {} for name in (*CATEGORY_KEYS, "other")
    }
    for key, value in raw.items():
        category = next(
            (
                name
                for name, fragments in CATEGORY_KEYS.items()
                if any(fragment in key for fragment in fragments)
            ),
            "other",
        )
        categories[category][key] = value

    width, height = raw.get("EXIF:ImageWidth"), raw.get("EXIF:ImageHeight")
    settings = {}
    if "EXIF:FocalLength" in raw:
        settings["focal_length"] = f"{raw['EXIF:FocalLength']}mm"
    if "EXIF:FNumber" in raw:
        settings["aperture"] = f"f/{raw['EXIF:FNumber']}"
    if "EXIF:ExposureTime" in raw:
        exposure = raw["EXIF:ExposureTime"]
        settings["shutter_speed"] = (
            f"1/{int(1 / exposure)}s" if exposure < 1 else f"{exposure}s"
        )
    if "EXIF:ISO" in raw:
        settings["iso"] = f"ISO {raw['EXIF:ISO']}"
    latitude, longitude = raw.get("EXIF:GPSLatitude"), raw.get("EXIF:GPSLongitude")
    if "Composite:GPSPosition" in raw:
        coordinates = raw["Composite:GPSPosition"]
    elif latitude and longitude:
        coordinates = f"{latitude}, {longitude}"
    else:
        coordinates = latitude or None

    return {
        "file_info": _present(
            filename=path.name,
            file_type=raw.get("File:FileType", "Unknown"),
            mime_type=raw.get("File:MIMEType", "Unknown"),
            file_size=_format_size(raw.get("File:FileSize", 0)),
            dimensions=f"{width} x {height}" if width and height else None,
        ),
        "camera_info": _present(
            make=raw.get("EXIF:Make"),
            model=raw.get("EXIF:Model"),
            lens=raw.get("EXIF:LensModel"),
            settings=settings or None,
        ),
        "gps_info": _present(
            coordinates=coordinates,
            altitude=(
                f"{raw['EXIF:GPSAltitude']}m" if "EXIF:GPSAltitude" in raw else None
            ),
            timestamp=raw.get("EXIF:GPSTimeStamp"),
        ),
        "timestamp_info": _present(
            taken=raw.get("EXIF:DateTimeOriginal"),
            created=raw.get("EXIF:CreateDate"),
            modified=raw.get("EXIF:ModifyDate"),
        ),
        "categories": categories,
        "total_fields": len(raw),
    }


def _present(**fields: Any) -> dict[str, Any]:
    return {key: value for key, value in fields.items() if value is not None}


def _format_size(size: float) -> str:
    if not size:
        return "Unknown"
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
