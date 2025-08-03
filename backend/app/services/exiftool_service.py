"""
Metadata extraction service for Owlculus OSINT digital forensics and evidence analysis.

This module provides comprehensive metadata extraction from digital files using ExifTool,
following clean architecture and SOLID principles. Supports forensic analysis of images,
videos, and documents with structured data extraction, GPS location parsing,
and camera information analysis for OSINT investigations.

Key features include:
- Multi-format metadata extraction (images, videos, documents)
- Structured data processing with categorized output
- GPS coordinate and timestamp extraction
- Camera settings and technical metadata analysis
- File validation and type detection
- Modular architecture with dependency injection
- Error handling and logging for forensic workflows
"""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Protocol, Set

from app.core.logging import logger

BYTES_PER_KB = 1024
FILE_SIZE_UNITS = ["B", "KB", "MB", "GB", "TB"]


class FileType(Enum):
    """Supported file types categorized by format"""

    JPEG = (".jpg", ".jpeg")
    PNG = (".png",)
    GIF = (".gif",)
    BMP = (".bmp",)
    TIFF = (".tiff", ".tif")
    WEBP = (".webp",)
    HEIC = (".heic", ".heif")
    RAW = (".raw", ".cr2", ".nef", ".arw", ".dng")

    MP4 = (".mp4",)
    AVI = (".avi",)
    MOV = (".mov",)
    WMV = (".wmv",)
    FLV = (".flv",)
    WEBM = (".webm",)
    MKV = (".mkv",)
    M4V = (".m4v",)
    THREEGP = (".3gp",)

    PDF = (".pdf",)
    DOC = (".doc", ".docx")
    XLS = (".xls", ".xlsx")
    PPT = (".ppt", ".pptx")

    @classmethod
    def get_all_extensions(cls) -> Set[str]:
        extensions = set()
        for file_type in cls:
            extensions.update(file_type.value)
        return extensions


@dataclass
class FileInfo:
    """Basic file information"""

    filename: str
    file_type: str
    mime_type: str
    file_size: str
    dimensions: Optional[str] = None


@dataclass
class CameraInfo:
    """Camera and settings information"""

    make: Optional[str] = None
    model: Optional[str] = None
    lens: Optional[str] = None
    settings: Optional[Dict[str, str]] = None


@dataclass
class GPSInfo:
    """GPS location information"""

    coordinates: Optional[str] = None
    altitude: Optional[str] = None
    timestamp: Optional[str] = None


@dataclass
class TimestampInfo:
    """File timestamp information"""

    taken: Optional[str] = None
    created: Optional[str] = None
    modified: Optional[str] = None


@dataclass
class MetadataResult:
    """Complete metadata extraction result"""

    success: bool
    file_info: Optional[FileInfo] = None
    camera_info: Optional[CameraInfo] = None
    gps_info: Optional[GPSInfo] = None
    timestamp_info: Optional[TimestampInfo] = None
    categories: Optional[Dict[str, Dict[str, Any]]] = None
    total_fields: int = 0
    error: Optional[str] = None


class MetadataExtractor(Protocol):
    """Protocol for metadata extraction tools"""

    async def extract(self, file_path: str) -> Dict[str, Any]:
        """Extract raw metadata from file"""
        ...


class FileValidator(ABC):
    """Abstract base class for file validation"""

    @abstractmethod
    def validate(self, file_path: str) -> None:
        """Validate file, raise exception if invalid"""
        ...


class MetadataProcessor(ABC):
    """Abstract base class for metadata processing"""

    @abstractmethod
    def process(self, raw_metadata: Dict[str, Any], file_path: str) -> MetadataResult:
        """Process raw metadata into structured result"""
        ...


class ExifToolExtractor:
    """ExifTool implementation of metadata extractor"""

    def __init__(self):
        self._exiftool = None
        self._ensure_exiftool_available()

    def _ensure_exiftool_available(self) -> None:
        try:
            import exiftool

            self._exiftool = exiftool
        except ImportError:
            raise RuntimeError("PyExifTool library not installed")

    async def extract(self, file_path: str) -> Dict[str, Any]:
        try:
            with self._exiftool.ExifToolHelper() as et:
                metadata = et.get_metadata([file_path])
                if metadata and metadata[0]:
                    return metadata[0]
                return {}
        except FileNotFoundError as e:
            if "exiftool" in str(e).lower():
                raise RuntimeError(
                    "ExifTool binary not found. Please install exiftool on the system."
                )
            raise
        except Exception as e:
            logger.error(f"Failed to extract metadata: {e}")
            raise RuntimeError(f"Metadata extraction failed: {str(e)}")


class StandardFileValidator(FileValidator):
    """Standard file validation implementation"""

    def __init__(self, supported_extensions: Set[str]):
        self.supported_extensions = supported_extensions

    def validate(self, file_path: str) -> None:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_ext = Path(file_path).suffix.lower()
        if file_ext not in self.supported_extensions:
            raise ValueError(f"Unsupported file type: {file_ext}")


class MetadataFieldCategorizer:
    """Categorizes metadata fields into logical groups"""

    CAMERA_PATTERNS = [
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
    ]

    GPS_PATTERNS = [
        "EXIF:GPSLatitude",
        "EXIF:GPSLongitude",
        "EXIF:GPSAltitude",
        "EXIF:GPSTimeStamp",
        "EXIF:GPSDateStamp",
        "Composite:GPSPosition",
    ]

    TIMESTAMP_PATTERNS = [
        "EXIF:DateTimeOriginal",
        "EXIF:CreateDate",
        "EXIF:ModifyDate",
        "File:FileModifyDate",
        "File:FileAccessDate",
        "File:FileCreateDate",
    ]

    TECHNICAL_PATTERNS = [
        "File:FileSize",
        "File:FileType",
        "File:MIMEType",
        "EXIF:ImageWidth",
        "EXIF:ImageHeight",
        "EXIF:BitsPerSample",
        "EXIF:ColorComponents",
        "EXIF:Compression",
        "File:FilePermissions",
    ]

    def categorize(self, metadata: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        categories = {
            "camera": {},
            "gps": {},
            "timestamps": {},
            "technical": {},
            "other": {},
        }

        pattern_map = {
            "camera": self.CAMERA_PATTERNS,
            "gps": self.GPS_PATTERNS,
            "timestamps": self.TIMESTAMP_PATTERNS,
            "technical": self.TECHNICAL_PATTERNS,
        }

        for key, value in metadata.items():
            categorized = False

            for category, patterns in pattern_map.items():
                if any(pattern in key for pattern in patterns):
                    categories[category][key] = value
                    categorized = True
                    break

            if not categorized:
                categories["other"][key] = value

        return categories


class FileInfoExtractor:
    """Extracts basic file information"""

    def extract(self, metadata: Dict[str, Any], file_path: str) -> FileInfo:
        return FileInfo(
            filename=Path(file_path).name,
            file_type=metadata.get("File:FileType", "Unknown"),
            mime_type=metadata.get("File:MIMEType", "Unknown"),
            file_size=self._format_file_size(metadata.get("File:FileSize", 0)),
            dimensions=self._get_dimensions(metadata),
        )

    def _get_dimensions(self, metadata: Dict[str, Any]) -> Optional[str]:
        width = metadata.get("EXIF:ImageWidth")
        height = metadata.get("EXIF:ImageHeight")

        if width and height:
            return f"{width} x {height}"
        return None

    def _format_file_size(self, size_bytes: int) -> str:
        if not size_bytes:
            return "Unknown"

        size = float(size_bytes)
        for unit in FILE_SIZE_UNITS[:-1]:
            if size < BYTES_PER_KB:
                return f"{size:.1f} {unit}"
            size /= BYTES_PER_KB

        return f"{size:.1f} {FILE_SIZE_UNITS[-1]}"


class CameraInfoExtractor:
    """Extracts camera and photography information"""

    def extract(self, camera_metadata: Dict[str, Any]) -> CameraInfo:
        settings = self._extract_camera_settings(camera_metadata)

        return CameraInfo(
            make=camera_metadata.get("EXIF:Make"),
            model=camera_metadata.get("EXIF:Model"),
            lens=camera_metadata.get("EXIF:LensModel"),
            settings=settings if settings else None,
        )

    def _extract_camera_settings(self, metadata: Dict[str, Any]) -> Dict[str, str]:
        settings = {}

        if "EXIF:FocalLength" in metadata:
            settings["focal_length"] = f"{metadata['EXIF:FocalLength']}mm"

        if "EXIF:FNumber" in metadata:
            settings["aperture"] = f"f/{metadata['EXIF:FNumber']}"

        if "EXIF:ExposureTime" in metadata:
            exposure = metadata["EXIF:ExposureTime"]
            settings["shutter_speed"] = self._format_exposure_time(exposure)

        if "EXIF:ISO" in metadata:
            settings["iso"] = f"ISO {metadata['EXIF:ISO']}"

        return settings

    def _format_exposure_time(self, exposure: float) -> str:
        if exposure < 1:
            return f"1/{int(1/exposure)}s"
        return f"{exposure}s"


class GPSInfoExtractor:
    """Extracts GPS location information"""

    def extract(self, gps_metadata: Dict[str, Any]) -> GPSInfo:
        coordinates = self._extract_coordinates(gps_metadata)
        altitude = self._extract_altitude(gps_metadata)
        timestamp = gps_metadata.get("EXIF:GPSTimeStamp")

        return GPSInfo(coordinates=coordinates, altitude=altitude, timestamp=timestamp)

    def _extract_coordinates(self, metadata: Dict[str, Any]) -> Optional[str]:
        if "Composite:GPSPosition" in metadata:
            return metadata["Composite:GPSPosition"]

        lat = metadata.get("EXIF:GPSLatitude")
        lon = metadata.get("EXIF:GPSLongitude")

        if lat and lon:
            return f"{lat}, {lon}"
        elif lat:
            return lat

        return None

    def _extract_altitude(self, metadata: Dict[str, Any]) -> Optional[str]:
        if "EXIF:GPSAltitude" in metadata:
            return f"{metadata['EXIF:GPSAltitude']}m"
        return None


class TimestampInfoExtractor:
    """Extracts timestamp information"""

    def extract(self, timestamp_metadata: Dict[str, Any]) -> TimestampInfo:
        return TimestampInfo(
            taken=timestamp_metadata.get("EXIF:DateTimeOriginal"),
            created=timestamp_metadata.get("EXIF:CreateDate"),
            modified=timestamp_metadata.get("EXIF:ModifyDate"),
        )


class StandardMetadataProcessor(MetadataProcessor):
    """Standard metadata processor implementation"""

    def __init__(self):
        self.categorizer = MetadataFieldCategorizer()
        self.file_extractor = FileInfoExtractor()
        self.camera_extractor = CameraInfoExtractor()
        self.gps_extractor = GPSInfoExtractor()
        self.timestamp_extractor = TimestampInfoExtractor()

    def process(self, raw_metadata: Dict[str, Any], file_path: str) -> MetadataResult:
        categories = self.categorizer.categorize(raw_metadata)

        file_info = self.file_extractor.extract(raw_metadata, file_path)
        camera_info = self.camera_extractor.extract(categories.get("camera", {}))
        gps_info = self.gps_extractor.extract(categories.get("gps", {}))
        timestamp_info = self.timestamp_extractor.extract(
            categories.get("timestamps", {})
        )

        return MetadataResult(
            success=True,
            file_info=file_info,
            camera_info=camera_info,
            gps_info=gps_info,
            timestamp_info=timestamp_info,
            categories=categories,
            total_fields=len(raw_metadata),
        )


class ExifToolService:
    """
    Facade for metadata extraction service
    Coordinates validation, extraction, and processing
    """

    def __init__(
        self,
        extractor: Optional[MetadataExtractor] = None,
        validator: Optional[FileValidator] = None,
        processor: Optional[MetadataProcessor] = None,
    ):
        self.extractor = extractor or ExifToolExtractor()
        self.validator = validator or StandardFileValidator(
            FileType.get_all_extensions()
        )
        self.processor = processor or StandardMetadataProcessor()

    async def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Extract and process metadata from a file

        Args:
            file_path: Path to the file to analyze

        Returns:
            Dictionary containing processed metadata or error information
        """
        try:
            self.validator.validate(file_path)

            raw_metadata = await self.extractor.extract(file_path)

            if not raw_metadata:
                return {"error": "No metadata found", "success": False}

            result = self.processor.process(raw_metadata, file_path)

            return self._result_to_dict(result)

        except FileNotFoundError as e:
            logger.warning(f"File not found: {file_path}")
            return {"error": str(e), "success": False}
        except ValueError as e:
            logger.warning(f"Invalid file: {file_path} - {e}")
            return {"error": str(e), "success": False}
        except RuntimeError as e:
            logger.error(f"Runtime error: {e}")
            return {"error": str(e), "success": False}
        except Exception as e:
            logger.error(f"Unexpected error extracting metadata: {e}", exc_info=True)
            return {"error": f"Failed to extract metadata: {str(e)}", "success": False}

    def is_supported_file(self, file_path: str) -> bool:
        """
        Check if file type is supported

        Args:
            file_path: Path to check

        Returns:
            True if file type is supported
        """
        try:
            self.validator.validate(file_path)
            return True
        except (FileNotFoundError, ValueError):
            return False

    def _result_to_dict(self, result: MetadataResult) -> Dict[str, Any]:
        return {
            "success": result.success,
            "file_info": (
                self._dataclass_to_dict(result.file_info) if result.file_info else {}
            ),
            "camera_info": (
                self._dataclass_to_dict(result.camera_info)
                if result.camera_info
                else {}
            ),
            "gps_info": (
                self._dataclass_to_dict(result.gps_info) if result.gps_info else {}
            ),
            "timestamp_info": (
                self._dataclass_to_dict(result.timestamp_info)
                if result.timestamp_info
                else {}
            ),
            "categories": result.categories or {},
            "total_fields": result.total_fields,
            "supported_file": True,
        }

    def _dataclass_to_dict(self, obj: Any) -> Dict[str, Any]:
        result = {}
        for field in obj.__dataclass_fields__:
            value = getattr(obj, field)
            if value is not None:
                result[field] = value
        return result
