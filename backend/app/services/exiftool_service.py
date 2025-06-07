"""
ExifTool service for extracting metadata from evidence files
"""

import os
from typing import Dict, Any, List, Optional
from pathlib import Path


class ExifToolService:
    """Service for extracting metadata from files using ExifTool"""

    def __init__(self):
        self.supported_extensions = {
            # Images
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".tiff",
            ".tif",
            ".webp",
            ".heic",
            ".heif",
            ".raw",
            ".cr2",
            ".nef",
            ".arw",
            ".dng",
            # Videos
            ".mp4",
            ".avi",
            ".mov",
            ".wmv",
            ".flv",
            ".webm",
            ".mkv",
            ".m4v",
            ".3gp",
            # Documents
            ".pdf",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".ppt",
            ".pptx",
        }

    def is_supported_file(self, file_path: str) -> bool:
        """Check if the file type is supported by ExifTool"""
        file_ext = Path(file_path).suffix.lower()
        return file_ext in self.supported_extensions

    async def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract metadata from a single file using ExifTool"""
        if not os.path.exists(file_path):
            return {"error": f"File not found: {file_path}"}

        if not self.is_supported_file(file_path):
            return {"error": f"Unsupported file type: {Path(file_path).suffix}"}

        try:
            import exiftool

            with exiftool.ExifToolHelper() as et:
                metadata = et.get_metadata([file_path])
                if metadata:
                    raw_metadata = metadata[0]
                    return self._process_metadata(raw_metadata, file_path)
                return {"error": "No metadata found"}

        except ImportError:
            return {"error": "PyExifTool library not installed"}
        except FileNotFoundError as e:
            if "exiftool" in str(e):
                return {
                    "error": "ExifTool binary not found. Please install exiftool on the system."
                }
            return {"error": f"File not found: {str(e)}"}
        except Exception as e:
            return {"error": f"Failed to extract metadata: {str(e)}"}

    def _process_metadata(
        self, raw_metadata: Dict[str, Any], file_path: str
    ) -> Dict[str, Any]:
        """Process and categorize the extracted metadata"""
        # Categorize metadata
        categorized = self._categorize_metadata(raw_metadata)

        # Extract key information
        file_info = self._extract_file_info(raw_metadata, file_path)
        camera_info = self._extract_camera_info(categorized.get("camera", {}))
        gps_info = self._extract_gps_info(categorized.get("gps", {}))
        timestamp_info = self._extract_timestamp_info(categorized.get("timestamps", {}))

        return {
            "success": True,
            "file_info": file_info,
            "camera_info": camera_info,
            "gps_info": gps_info,
            "timestamp_info": timestamp_info,
            "categories": categorized,
            "total_fields": len(raw_metadata),
            "supported_file": True,
        }

    def _categorize_metadata(
        self, metadata: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """Organize metadata into logical categories"""
        categorized = {
            "camera": {},
            "gps": {},
            "timestamps": {},
            "technical": {},
            "other": {},
        }

        # Define field mappings
        camera_fields = [
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

        gps_fields = [
            "EXIF:GPSLatitude",
            "EXIF:GPSLongitude",
            "EXIF:GPSAltitude",
            "EXIF:GPSTimeStamp",
            "EXIF:GPSDateStamp",
            "Composite:GPSPosition",
        ]

        timestamp_fields = [
            "EXIF:DateTimeOriginal",
            "EXIF:CreateDate",
            "EXIF:ModifyDate",
            "File:FileModifyDate",
            "File:FileAccessDate",
            "File:FileCreateDate",
        ]

        technical_fields = [
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

        # Categorize fields
        for key, value in metadata.items():
            if any(field in key for field in camera_fields):
                categorized["camera"][key] = value
            elif any(field in key for field in gps_fields):
                categorized["gps"][key] = value
            elif any(field in key for field in timestamp_fields):
                categorized["timestamps"][key] = value
            elif any(field in key for field in technical_fields):
                categorized["technical"][key] = value
            else:
                categorized["other"][key] = value

        return categorized

    def _extract_file_info(
        self, metadata: Dict[str, Any], file_path: str
    ) -> Dict[str, Any]:
        """Extract basic file information"""
        return {
            "filename": Path(file_path).name,
            "file_type": metadata.get("File:FileType", "Unknown"),
            "mime_type": metadata.get("File:MIMEType", "Unknown"),
            "file_size": self._format_file_size(metadata.get("File:FileSize", 0)),
            "dimensions": self._get_dimensions(metadata),
        }

    def _extract_camera_info(self, camera_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and format camera information"""
        camera_info = {}

        if "EXIF:Make" in camera_metadata:
            camera_info["make"] = camera_metadata["EXIF:Make"]
        if "EXIF:Model" in camera_metadata:
            camera_info["model"] = camera_metadata["EXIF:Model"]
        if "EXIF:LensModel" in camera_metadata:
            camera_info["lens"] = camera_metadata["EXIF:LensModel"]

        # Format camera settings
        settings = {}
        if "EXIF:FocalLength" in camera_metadata:
            settings["focal_length"] = f"{camera_metadata['EXIF:FocalLength']}mm"
        if "EXIF:FNumber" in camera_metadata:
            settings["aperture"] = f"f/{camera_metadata['EXIF:FNumber']}"
        if "EXIF:ExposureTime" in camera_metadata:
            exposure = camera_metadata["EXIF:ExposureTime"]
            if exposure < 1:
                settings["shutter_speed"] = f"1/{int(1/exposure)}s"
            else:
                settings["shutter_speed"] = f"{exposure}s"
        if "EXIF:ISO" in camera_metadata:
            settings["iso"] = f"ISO {camera_metadata['EXIF:ISO']}"

        if settings:
            camera_info["settings"] = settings

        return camera_info

    def _extract_gps_info(self, gps_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and format GPS information"""
        gps_info = {}

        if "Composite:GPSPosition" in gps_metadata:
            gps_info["coordinates"] = gps_metadata["Composite:GPSPosition"]
        elif "EXIF:GPSLatitude" in gps_metadata and "EXIF:GPSLongitude" in gps_metadata:
            lat = gps_metadata["EXIF:GPSLatitude"]
            lon = gps_metadata["EXIF:GPSLongitude"]
            gps_info["coordinates"] = f"{lat}, {lon}"

        if "EXIF:GPSAltitude" in gps_metadata:
            gps_info["altitude"] = f"{gps_metadata['EXIF:GPSAltitude']}m"

        if "EXIF:GPSTimeStamp" in gps_metadata:
            gps_info["timestamp"] = gps_metadata["EXIF:GPSTimeStamp"]

        return gps_info

    def _extract_timestamp_info(
        self, timestamp_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract and format timestamp information"""
        timestamps = {}

        if "EXIF:DateTimeOriginal" in timestamp_metadata:
            timestamps["taken"] = timestamp_metadata["EXIF:DateTimeOriginal"]
        if "EXIF:CreateDate" in timestamp_metadata:
            timestamps["created"] = timestamp_metadata["EXIF:CreateDate"]
        if "EXIF:ModifyDate" in timestamp_metadata:
            timestamps["modified"] = timestamp_metadata["EXIF:ModifyDate"]

        return timestamps

    def _get_dimensions(self, metadata: Dict[str, Any]) -> Optional[str]:
        """Get image/video dimensions"""
        width = metadata.get("EXIF:ImageWidth")
        height = metadata.get("EXIF:ImageHeight")

        if width and height:
            return f"{width} x {height}"
        return None

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        if not size_bytes:
            return "Unknown"

        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
