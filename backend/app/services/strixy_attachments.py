"""Bounded local attachment preparation; no provider uploads or shared text cache."""

import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from app.core import file_storage
from app.core.strixy_config import StrixyConfig


@dataclass
class Attachment:
    """Internal storage handle; only outcomes and content fields leave this boundary."""

    path: Path | None
    version: str
    size: int = 0
    reason: str | None = None

    @classmethod
    def locate(cls, case_id: int, relative_path: str) -> "Attachment":
        try:
            path = file_storage.evidence_file_path(case_id, relative_path)
            with path.open("rb") as stream:
                content = stream.read(15 * 1024 * 1024 + 1)
            if len(content) > 15 * 1024 * 1024:
                stat = path.stat()
                return cls(
                    None,
                    f"oversized:{stat.st_size}:{stat.st_mtime_ns}",
                    reason="attachment_size_limit",
                )
            return cls(path, hashlib.sha256(content).hexdigest(), len(content))
        except (OSError, ValueError):
            return cls(None, "unavailable", reason="file_unavailable")


@dataclass
class PreparedAttachment:
    fields: dict[str, str] = field(default_factory=dict)
    state: str = "unavailable"
    reason: str | None = None
    units_read: int = 0
    next_unit: int = 0
    warnings: list[str] = field(default_factory=list)

    images: list[dict] = field(default_factory=list)
    pages: list[dict] = field(default_factory=list)
    total_units: int = 0
    unexamined_from: int | None = None

    def view(self) -> dict:
        return {
            "state": self.state,
            "reason": self.reason,
            "units_read": self.units_read,
            "next_unit": self.next_unit,
            "warnings": self.warnings,
            **(
                {
                    "pages": self.pages,
                    "total_units": self.total_units,
                    "unexamined_from": self.unexamined_from,
                }
                if self.total_units
                else {}
            ),
        }


def prepare(
    attachment: Attachment,
    config: StrixyConfig,
    *,
    start: int = 0,
    timeout: float | None = None,
) -> PreparedAttachment:
    if timeout is not None and timeout <= 0:
        return PreparedAttachment(reason="attachment_time_limit")
    if attachment.path is None:
        return PreparedAttachment(reason=attachment.reason)
    if attachment.size > config.attachment_max_bytes:
        return PreparedAttachment(reason="attachment_size_limit")
    if attachment.path.suffix.lower() not in {
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".txt",
        ".json",
        ".csv",
        ".doc",
        ".docx",
        ".xlsx",
        ".pptx",
    }:
        return PreparedAttachment(reason="unsupported_format")
    try:
        with attachment.path.open("rb") as stream:
            data = stream.read(config.attachment_max_bytes + 1)
        if len(data) > config.attachment_max_bytes:
            return PreparedAttachment(reason="attachment_size_limit")
        if hashlib.sha256(data).hexdigest() != attachment.version:
            return PreparedAttachment(reason="source_changed")
        with tempfile.TemporaryDirectory(prefix="strixy-attachment-") as directory:
            snapshot = Path(directory) / ("input" + attachment.path.suffix.lower())
            snapshot.write_bytes(data)
            output = Path(directory) / "output.json"
            with output.open("wb") as stream:
                process = subprocess.Popen(
                    [
                        sys.executable,
                        str(Path(__file__).with_name("strixy_attachment_parser.py")),
                        str(snapshot),
                        json.dumps(config.model_dump()),
                        str(start),
                    ],
                    stdout=stream,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                    env={
                        "PATH": os.defpath,
                        "LANG": "C.UTF-8",
                        "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
                    },
                )
                try:
                    process.wait(
                        timeout=max(
                            0.001,
                            min(
                                config.attachment_seconds,
                                (
                                    timeout
                                    if timeout is not None
                                    else config.attachment_seconds
                                ),
                            ),
                        )
                    )
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    return PreparedAttachment(reason="attachment_time_limit")
            if process.returncode:
                return PreparedAttachment(reason="attachment_processing_limit")
            return PreparedAttachment(**json.loads(output.read_text()))
    except (OSError, ValueError):
        return PreparedAttachment(reason="unreadable_file")
