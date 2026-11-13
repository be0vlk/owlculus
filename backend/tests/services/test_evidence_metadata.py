"""Evidence metadata extraction through a faked exiftool binary."""

import json
import subprocess
from pathlib import Path

import pytest

from app.core.exceptions import ValidationException
from app.services import evidence_metadata
from app.services.evidence_metadata import extract_metadata


def _fake_exiftool(monkeypatch, raw):
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps([raw]))

    monkeypatch.setattr(evidence_metadata.subprocess, "run", run)
    return calls


def test_extract_metadata_builds_the_keys_the_frontend_renders(monkeypatch):
    raw = {
        "SourceFile": "uploads/1/photo.jpg",
        "File:FileType": "JPEG",
        "File:MIMEType": "image/jpeg",
        "File:FileSize": 1234567,
        "File:FileModifyDate": "2024:01:01 10:00:00",
        "EXIF:ImageWidth": 4000,
        "EXIF:ImageHeight": 3000,
        "EXIF:Make": "Canon",
        "EXIF:Model": "EOS R5",
        "EXIF:LensModel": "RF 24-70mm",
        "EXIF:FocalLength": 50,
        "EXIF:FNumber": 2.8,
        "EXIF:ExposureTime": 0.004,
        "EXIF:ISO": 400,
        "EXIF:GPSLatitude": 40.7,
        "EXIF:GPSLongitude": -74.0,
        "EXIF:GPSAltitude": 10,
        "EXIF:GPSTimeStamp": "12:00:00",
        "Composite:GPSPosition": "40.7 -74.0",
        "EXIF:DateTimeOriginal": "2024:01:01 09:00:00",
        "EXIF:CreateDate": "2024:01:01 09:00:01",
        "EXIF:ModifyDate": "2024:01:02 09:00:00",
        "XMP:Creator": "Someone",
    }
    calls = _fake_exiftool(monkeypatch, raw)

    result = extract_metadata(Path("uploads/1/photo.JPG"))

    assert calls == [["exiftool", "-j", "-G", "-n", "uploads/1/photo.JPG"]]
    assert result == {
        "file_info": {
            "filename": "photo.JPG",
            "file_type": "JPEG",
            "mime_type": "image/jpeg",
            "file_size": "1.2 MB",
            "dimensions": "4000 x 3000",
        },
        "camera_info": {
            "make": "Canon",
            "model": "EOS R5",
            "lens": "RF 24-70mm",
            "settings": {
                "focal_length": "50mm",
                "aperture": "f/2.8",
                "shutter_speed": "1/250s",
                "iso": "ISO 400",
            },
        },
        "gps_info": {
            "coordinates": "40.7 -74.0",
            "altitude": "10m",
            "timestamp": "12:00:00",
        },
        "timestamp_info": {
            "taken": "2024:01:01 09:00:00",
            "created": "2024:01:01 09:00:01",
            "modified": "2024:01:02 09:00:00",
        },
        "categories": {
            "camera": {
                key: raw[key]
                for key in (
                    "EXIF:Make",
                    "EXIF:Model",
                    "EXIF:LensModel",
                    "EXIF:FocalLength",
                    "EXIF:FNumber",
                    "EXIF:ExposureTime",
                    "EXIF:ISO",
                )
            },
            "gps": {
                key: raw[key]
                for key in (
                    "EXIF:GPSLatitude",
                    "EXIF:GPSLongitude",
                    "EXIF:GPSAltitude",
                    "EXIF:GPSTimeStamp",
                    "Composite:GPSPosition",
                )
            },
            "timestamps": {
                key: raw[key]
                for key in (
                    "File:FileModifyDate",
                    "EXIF:DateTimeOriginal",
                    "EXIF:CreateDate",
                    "EXIF:ModifyDate",
                )
            },
            "technical": {
                key: raw[key]
                for key in (
                    "File:FileType",
                    "File:MIMEType",
                    "File:FileSize",
                    "EXIF:ImageWidth",
                    "EXIF:ImageHeight",
                )
            },
            "other": {
                "SourceFile": "uploads/1/photo.jpg",
                "XMP:Creator": "Someone",
            },
        },
        "total_fields": len(raw),
    }


def test_extract_metadata_omits_fields_the_file_lacks(monkeypatch):
    _fake_exiftool(
        monkeypatch,
        {"EXIF:Make": "Canon", "EXIF:GPSLatitude": 40.7, "EXIF:ExposureTime": 2},
    )

    result = extract_metadata(Path("scan.pdf"))

    assert result["file_info"] == {
        "filename": "scan.pdf",
        "file_type": "Unknown",
        "mime_type": "Unknown",
        "file_size": "Unknown",
    }
    assert result["camera_info"] == {
        "make": "Canon",
        "settings": {"shutter_speed": "2s"},
    }
    assert result["gps_info"] == {"coordinates": 40.7}
    assert result["timestamp_info"] == {}


def test_extract_metadata_rejects_unsupported_files_without_running_exiftool(
    monkeypatch,
):
    calls = _fake_exiftool(monkeypatch, {})

    with pytest.raises(ValidationException, match="Unsupported file type"):
        extract_metadata(Path("notes.txt"))

    assert calls == []


def test_extract_metadata_reports_unreadable_files_as_validation_errors(
    monkeypatch,
):
    def run(args, **kwargs):
        raise subprocess.CalledProcessError(1, args, stderr="File format error")

    monkeypatch.setattr(evidence_metadata.subprocess, "run", run)

    with pytest.raises(ValidationException, match="Could not read metadata"):
        extract_metadata(Path("broken.jpg"))


@pytest.mark.parametrize("exposure", [0, "fast"])
def test_extract_metadata_omits_shutter_speed_for_unusable_exposure(
    monkeypatch, exposure
):
    _fake_exiftool(monkeypatch, {"EXIF:Make": "Canon", "EXIF:ExposureTime": exposure})

    result = extract_metadata(Path("photo.jpg"))

    assert result["camera_info"] == {"make": "Canon"}


@pytest.mark.parametrize("stdout", ["not json", "", "[]"])
def test_extract_metadata_reports_unparseable_output_as_validation_error(
    monkeypatch, stdout
):
    monkeypatch.setattr(
        evidence_metadata.subprocess,
        "run",
        lambda args, **kwargs: subprocess.CompletedProcess(args, 0, stdout=stdout),
    )

    with pytest.raises(ValidationException, match="Could not read metadata"):
        extract_metadata(Path("photo.jpg"))


def test_extract_metadata_reports_missing_exiftool_as_validation_error(monkeypatch):
    def run(args, **kwargs):
        raise FileNotFoundError("exiftool")

    monkeypatch.setattr(evidence_metadata.subprocess, "run", run)

    with pytest.raises(ValidationException, match="Could not read metadata"):
        extract_metadata(Path("photo.jpg"))
