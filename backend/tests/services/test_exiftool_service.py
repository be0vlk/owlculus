"""
Comprehensive test suite for ExifTool service
"""

import pytest
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from app.services.exiftool_service import (
    ExifToolService,
    ExifToolExtractor,
    StandardFileValidator,
    StandardMetadataProcessor,
    MetadataFieldCategorizer,
    FileInfoExtractor,
    CameraInfoExtractor,
    GPSInfoExtractor,
    TimestampInfoExtractor,
    FileInfo,
    CameraInfo,
    GPSInfo,
    TimestampInfo,
    MetadataResult,
    FileType,
    BYTES_PER_KB,
    FILE_SIZE_UNITS
)


class TestFileType:
    """Test FileType enum functionality"""
    
    def test_get_all_extensions(self):
        """Test getting all supported extensions"""
        extensions = FileType.get_all_extensions()
        
        assert isinstance(extensions, set)
        assert ".jpg" in extensions
        assert ".mp4" in extensions
        assert ".pdf" in extensions
        assert len(extensions) > 20
    
    def test_file_type_categories(self):
        """Test file type categorization"""
        assert ".jpg" in FileType.JPEG.value
        assert ".jpeg" in FileType.JPEG.value
        assert ".mp4" in FileType.MP4.value
        assert ".pdf" in FileType.PDF.value


class TestExifToolExtractor:
    """Test ExifTool metadata extractor"""
    
    @patch('app.services.exiftool_service.ExifToolExtractor._ensure_exiftool_available')
    def test_init_success(self, mock_ensure):
        """Test successful initialization"""
        extractor = ExifToolExtractor()
        mock_ensure.assert_called_once()
    
    @patch('builtins.__import__')
    def test_ensure_exiftool_missing(self, mock_import):
        """Test handling missing PyExifTool"""
        mock_import.side_effect = ImportError("No module named 'exiftool'")
        
        with pytest.raises(RuntimeError) as exc_info:
            ExifToolExtractor()
        
        assert "PyExifTool library not installed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    @patch('app.services.exiftool_service.ExifToolExtractor._ensure_exiftool_available')
    async def test_extract_success(self, mock_ensure):
        """Test successful metadata extraction"""
        # Mock ExifTool
        mock_et_helper = MagicMock()
        mock_et_helper.__enter__.return_value.get_metadata.return_value = [
            {"File:FileType": "JPEG", "EXIF:Make": "Canon"}
        ]
        
        extractor = ExifToolExtractor()
        extractor._exiftool = MagicMock()
        extractor._exiftool.ExifToolHelper.return_value = mock_et_helper
        
        result = await extractor.extract("/path/to/file.jpg")
        
        assert result == {"File:FileType": "JPEG", "EXIF:Make": "Canon"}
    
    @pytest.mark.asyncio
    @patch('app.services.exiftool_service.ExifToolExtractor._ensure_exiftool_available')
    async def test_extract_exiftool_not_found(self, mock_ensure):
        """Test handling missing exiftool binary"""
        extractor = ExifToolExtractor()
        extractor._exiftool = MagicMock()
        
        mock_et_helper = MagicMock()
        mock_et_helper.__enter__.side_effect = FileNotFoundError("exiftool not found")
        extractor._exiftool.ExifToolHelper.return_value = mock_et_helper
        
        with pytest.raises(RuntimeError) as exc_info:
            await extractor.extract("/path/to/file.jpg")
        
        assert "ExifTool binary not found" in str(exc_info.value)


class TestStandardFileValidator:
    """Test file validation"""
    
    @pytest.fixture
    def validator(self):
        return StandardFileValidator({".jpg", ".mp4", ".pdf"})
    
    def test_validate_success(self, validator, tmp_path):
        """Test successful file validation"""
        test_file = tmp_path / "test.jpg"
        test_file.write_text("dummy content")
        
        # Should not raise exception
        validator.validate(str(test_file))
    
    def test_validate_file_not_found(self, validator):
        """Test validation of non-existent file"""
        with pytest.raises(FileNotFoundError) as exc_info:
            validator.validate("/nonexistent/file.jpg")
        
        assert "File not found" in str(exc_info.value)
    
    def test_validate_unsupported_type(self, validator, tmp_path):
        """Test validation of unsupported file type"""
        test_file = tmp_path / "test.xyz"
        test_file.write_text("dummy content")
        
        with pytest.raises(ValueError) as exc_info:
            validator.validate(str(test_file))
        
        assert "Unsupported file type: .xyz" in str(exc_info.value)


class TestMetadataFieldCategorizer:
    """Test metadata field categorization"""
    
    @pytest.fixture
    def categorizer(self):
        return MetadataFieldCategorizer()
    
    def test_categorize_camera_fields(self, categorizer):
        """Test categorization of camera fields"""
        metadata = {
            "EXIF:Make": "Canon",
            "EXIF:Model": "EOS R5",
            "EXIF:ISO": 400,
            "File:FileSize": 1234567
        }
        
        result = categorizer.categorize(metadata)
        
        assert "EXIF:Make" in result["camera"]
        assert "EXIF:Model" in result["camera"]
        assert "EXIF:ISO" in result["camera"]
        assert "File:FileSize" in result["technical"]
    
    def test_categorize_gps_fields(self, categorizer):
        """Test categorization of GPS fields"""
        metadata = {
            "EXIF:GPSLatitude": "40.7128 N",
            "EXIF:GPSLongitude": "74.0060 W",
            "Composite:GPSPosition": "40.7128 N, 74.0060 W"
        }
        
        result = categorizer.categorize(metadata)
        
        assert all(key in result["gps"] for key in metadata.keys())
    
    def test_categorize_other_fields(self, categorizer):
        """Test categorization of unknown fields"""
        metadata = {
            "Custom:Field": "value",
            "Unknown:Tag": "data"
        }
        
        result = categorizer.categorize(metadata)
        
        assert all(key in result["other"] for key in metadata.keys())


class TestFileInfoExtractor:
    """Test file information extraction"""
    
    @pytest.fixture
    def extractor(self):
        return FileInfoExtractor()
    
    def test_extract_complete_info(self, extractor):
        """Test extraction with complete metadata"""
        metadata = {
            "File:FileType": "JPEG",
            "File:MIMEType": "image/jpeg",
            "File:FileSize": 2048576,  # 2MB
            "EXIF:ImageWidth": 1920,
            "EXIF:ImageHeight": 1080
        }
        
        result = extractor.extract(metadata, "/path/to/photo.jpg")
        
        assert result.filename == "photo.jpg"
        assert result.file_type == "JPEG"
        assert result.mime_type == "image/jpeg"
        assert result.file_size == "2.0 MB"
        assert result.dimensions == "1920 x 1080"
    
    def test_extract_missing_info(self, extractor):
        """Test extraction with missing metadata"""
        metadata = {}
        
        result = extractor.extract(metadata, "/path/to/photo.jpg")
        
        assert result.filename == "photo.jpg"
        assert result.file_type == "Unknown"
        assert result.mime_type == "Unknown"
        assert result.file_size == "Unknown"
        assert result.dimensions is None
    
    @pytest.mark.parametrize("size_bytes,expected", [
        (0, "Unknown"),
        (512, "512.0 B"),
        (1536, "1.5 KB"),
        (2097152, "2.0 MB"),
        (3221225472, "3.0 GB"),
        (4398046511104, "4.0 TB")
    ])
    def test_format_file_size(self, extractor, size_bytes, expected):
        """Test file size formatting"""
        assert extractor._format_file_size(size_bytes) == expected


class TestCameraInfoExtractor:
    """Test camera information extraction"""
    
    @pytest.fixture
    def extractor(self):
        return CameraInfoExtractor()
    
    def test_extract_complete_camera_info(self, extractor):
        """Test extraction with complete camera metadata"""
        metadata = {
            "EXIF:Make": "Canon",
            "EXIF:Model": "EOS R5",
            "EXIF:LensModel": "RF 24-70mm f/2.8L",
            "EXIF:FocalLength": 50,
            "EXIF:FNumber": 2.8,
            "EXIF:ExposureTime": 0.002,  # 1/500s
            "EXIF:ISO": 400
        }
        
        result = extractor.extract(metadata)
        
        assert result.make == "Canon"
        assert result.model == "EOS R5"
        assert result.lens == "RF 24-70mm f/2.8L"
        assert result.settings["focal_length"] == "50mm"
        assert result.settings["aperture"] == "f/2.8"
        assert result.settings["shutter_speed"] == "1/500s"
        assert result.settings["iso"] == "ISO 400"
    
    def test_extract_partial_camera_info(self, extractor):
        """Test extraction with partial camera metadata"""
        metadata = {
            "EXIF:Make": "Nikon",
            "EXIF:Model": "D850"
        }
        
        result = extractor.extract(metadata)
        
        assert result.make == "Nikon"
        assert result.model == "D850"
        assert result.lens is None
        assert result.settings is None
    
    @pytest.mark.parametrize("exposure,expected", [
        (0.001, "1/1000s"),
        (0.5, "1/2s"),
        (1.0, "1.0s"),
        (2.5, "2.5s")
    ])
    def test_format_exposure_time(self, extractor, exposure, expected):
        """Test exposure time formatting"""
        assert extractor._format_exposure_time(exposure) == expected


class TestGPSInfoExtractor:
    """Test GPS information extraction"""
    
    @pytest.fixture
    def extractor(self):
        return GPSInfoExtractor()
    
    def test_extract_composite_gps(self, extractor):
        """Test extraction with composite GPS position"""
        metadata = {
            "Composite:GPSPosition": "40.7128 N, 74.0060 W",
            "EXIF:GPSAltitude": 10.5,
            "EXIF:GPSTimeStamp": "12:34:56"
        }
        
        result = extractor.extract(metadata)
        
        assert result.coordinates == "40.7128 N, 74.0060 W"
        assert result.altitude == "10.5m"
        assert result.timestamp == "12:34:56"
    
    def test_extract_separate_coordinates(self, extractor):
        """Test extraction with separate lat/lon"""
        metadata = {
            "EXIF:GPSLatitude": "40.7128 N",
            "EXIF:GPSLongitude": "74.0060 W"
        }
        
        result = extractor.extract(metadata)
        
        assert result.coordinates == "40.7128 N, 74.0060 W"
        assert result.altitude is None
        assert result.timestamp is None


class TestTimestampInfoExtractor:
    """Test timestamp information extraction"""
    
    @pytest.fixture
    def extractor(self):
        return TimestampInfoExtractor()
    
    def test_extract_all_timestamps(self, extractor):
        """Test extraction of all timestamp types"""
        metadata = {
            "EXIF:DateTimeOriginal": "2024:01:15 10:30:00",
            "EXIF:CreateDate": "2024:01:15 10:30:00",
            "EXIF:ModifyDate": "2024:01:15 11:00:00"
        }
        
        result = extractor.extract(metadata)
        
        assert result.taken == "2024:01:15 10:30:00"
        assert result.created == "2024:01:15 10:30:00"
        assert result.modified == "2024:01:15 11:00:00"


class TestStandardMetadataProcessor:
    """Test metadata processing"""
    
    @pytest.fixture
    def processor(self):
        return StandardMetadataProcessor()
    
    def test_process_complete_metadata(self, processor):
        """Test processing complete metadata"""
        raw_metadata = {
            "File:FileType": "JPEG",
            "File:FileSize": 2048576,
            "EXIF:Make": "Canon",
            "EXIF:Model": "EOS R5",
            "EXIF:GPSLatitude": "40.7128 N",
            "EXIF:DateTimeOriginal": "2024:01:15 10:30:00"
        }
        
        result = processor.process(raw_metadata, "/path/to/photo.jpg")
        
        assert result.success is True
        assert result.file_info.filename == "photo.jpg"
        assert result.camera_info.make == "Canon"
        assert result.gps_info.coordinates is not None
        assert result.timestamp_info.taken is not None
        assert result.total_fields == 6


class TestExifToolService:
    """Test main service facade"""
    
    @pytest.fixture
    def mock_extractor(self):
        return AsyncMock()
    
    @pytest.fixture
    def mock_validator(self):
        return Mock()
    
    @pytest.fixture
    def mock_processor(self):
        processor = Mock()
        processor.process.return_value = MetadataResult(
            success=True,
            file_info=FileInfo("test.jpg", "JPEG", "image/jpeg", "1.0 MB"),
            camera_info=CameraInfo(make="Canon", model="EOS R5"),
            gps_info=GPSInfo(coordinates="40.7128 N, 74.0060 W"),
            timestamp_info=TimestampInfo(taken="2024:01:15 10:30:00"),
            categories={"camera": {}, "gps": {}},
            total_fields=10
        )
        return processor
    
    @pytest.fixture
    def service(self, mock_extractor, mock_validator, mock_processor):
        return ExifToolService(
            extractor=mock_extractor,
            validator=mock_validator,
            processor=mock_processor
        )
    
    @pytest.mark.asyncio
    async def test_extract_metadata_success(self, service, mock_extractor, mock_validator):
        """Test successful metadata extraction"""
        mock_extractor.extract.return_value = {"File:FileType": "JPEG"}
        
        result = await service.extract_metadata("/path/to/photo.jpg")
        
        assert result["success"] is True
        assert result["file_info"]["filename"] == "test.jpg"
        assert result["camera_info"]["make"] == "Canon"
        assert result["supported_file"] is True
        
        mock_validator.validate.assert_called_once_with("/path/to/photo.jpg")
        mock_extractor.extract.assert_called_once_with("/path/to/photo.jpg")
    
    @pytest.mark.asyncio
    async def test_extract_metadata_file_not_found(self, service, mock_validator):
        """Test handling file not found"""
        mock_validator.validate.side_effect = FileNotFoundError("File not found")
        
        result = await service.extract_metadata("/nonexistent.jpg")
        
        assert result["success"] is False
        assert "File not found" in result["error"]
    
    @pytest.mark.asyncio
    async def test_extract_metadata_unsupported_type(self, service, mock_validator):
        """Test handling unsupported file type"""
        mock_validator.validate.side_effect = ValueError("Unsupported file type")
        
        result = await service.extract_metadata("/file.xyz")
        
        assert result["success"] is False
        assert "Unsupported file type" in result["error"]
    
    @pytest.mark.asyncio
    async def test_extract_metadata_no_metadata(self, service, mock_extractor, mock_validator):
        """Test handling empty metadata"""
        mock_extractor.extract.return_value = {}
        
        result = await service.extract_metadata("/path/to/photo.jpg")
        
        assert result["success"] is False
        assert result["error"] == "No metadata found"
    
    def test_is_supported_file_valid(self, service, mock_validator):
        """Test checking supported file"""
        assert service.is_supported_file("/path/to/photo.jpg") is True
        mock_validator.validate.assert_called_once_with("/path/to/photo.jpg")
    
    def test_is_supported_file_invalid(self, service, mock_validator):
        """Test checking unsupported file"""
        mock_validator.validate.side_effect = ValueError("Unsupported")
        
        assert service.is_supported_file("/path/to/file.xyz") is False
    
    def test_dataclass_to_dict(self, service):
        """Test dataclass to dict conversion"""
        file_info = FileInfo(
            filename="test.jpg",
            file_type="JPEG",
            mime_type="image/jpeg",
            file_size="1.0 MB",
            dimensions=None  # Should be excluded
        )
        
        result = service._dataclass_to_dict(file_info)
        
        assert result == {
            "filename": "test.jpg",
            "file_type": "JPEG",
            "mime_type": "image/jpeg",
            "file_size": "1.0 MB"
        }
        assert "dimensions" not in result


# Performance tests without benchmark dependency
class TestPerformance:
    """Performance tests"""
    
    def test_categorization_performance(self):
        """Test categorization performance with large dataset"""
        categorizer = MetadataFieldCategorizer()
        
        # Create large metadata dict
        metadata = {}
        for i in range(1000):
            metadata[f"EXIF:Field{i}"] = f"value{i}"
            metadata[f"Custom:Field{i}"] = f"value{i}"
        
        import time
        start = time.time()
        result = categorizer.categorize(metadata)
        elapsed = time.time() - start
        
        assert len(result["other"]) > 0
        assert elapsed < 0.1  # Should complete in under 100ms
    
    def test_file_size_formatting_performance(self):
        """Test file size formatting performance"""
        extractor = FileInfoExtractor()
        
        sizes = [i * 1024 for i in range(1, 10000)]
        
        import time
        start = time.time()
        result = [extractor._format_file_size(size) for size in sizes]
        elapsed = time.time() - start
        
        assert len(result) == len(sizes)
        assert elapsed < 0.5  # Should complete in under 500ms