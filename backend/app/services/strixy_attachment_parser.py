"""Private resource-limited parser process; consumes snapshots, never storage paths."""

import csv
import io
import json
import resource
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import olefile

from app.services.strixy_office import OfficeDocument, PreparationFailure


def json_units(value, pointer=""):
    if isinstance(value, dict) and value:
        yield "json-type:" + pointer, "object"
        for key, child in value.items():
            yield from json_units(
                child, pointer + "/" + key.replace("~", "~0").replace("/", "~1")
            )
    elif isinstance(value, list) and value:
        yield "json-type:" + pointer, "array"
        for index, child in enumerate(value):
            yield from json_units(child, f"{pointer}/{index}")
    else:
        yield "json:" + pointer, json.dumps(value, ensure_ascii=False)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError("Non-JSON constant")


def units(path, extension, limits, warnings):
    if extension in {".doc", ".docx", ".xlsx", ".pptx"} and olefile.isOleFile(path):
        with olefile.OleFileIO(path) as compound:
            if compound.exists("EncryptedPackage") or compound.exists("EncryptionInfo"):
                raise PreparationFailure("encrypted_file")
            if extension == ".doc" and compound.exists("WordDocument"):
                header = compound.openstream("WordDocument").read(32)
                if len(header) < 12:
                    raise PreparationFailure("unreadable_file")
                if int.from_bytes(header[10:12], "little") & 0x8100:
                    raise PreparationFailure("encrypted_file")
    if extension == ".doc":
        target = path.with_suffix(".txt")
        try:
            output_limit = resource.getrlimit(resource.RLIMIT_FSIZE)
            try:
                resource.setrlimit(
                    resource.RLIMIT_FSIZE,
                    (limits["attachment_max_expanded_bytes"], output_limit[1]),
                )
                with target.open("wb") as output:
                    process = subprocess.run(
                        ["antiword", "-m", "UTF-8.txt", "-w", "0", str(path)],
                        stdout=output,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
            finally:
                resource.setrlimit(resource.RLIMIT_FSIZE, output_limit)
            if process.returncode:
                if target.stat().st_size >= limits["attachment_max_expanded_bytes"]:
                    raise PreparationFailure("attachment_expansion_limit")
                raise PreparationFailure("unreadable_file")
            warnings.add("legacy_layout_and_visuals_unexamined")
            for index, line in enumerate(target.read_text().splitlines(), 1):
                yield f"extracted-line:{index}", line
        except FileNotFoundError:
            raise PreparationFailure("converter_unavailable") from None
        return
    if extension in {".docx", ".xlsx", ".pptx"}:
        with ZipFile(path) as archive:
            document = OfficeDocument(archive, limits["attachment_max_expanded_bytes"])
            reader = {
                ".docx": document.word,
                ".xlsx": document.spreadsheet,
                ".pptx": document.presentation,
            }[extension]
            yield from reader()
            warnings.update(document.warnings)
        return
    text = path.read_bytes().decode("utf-8-sig")
    if "\x00" in text:
        raise ValueError("Binary text")
    if extension == ".json":
        yield from json_units(
            json.loads(
                text, object_pairs_hook=unique_object, parse_constant=invalid_constant
            )
        )
    elif extension == ".csv":
        csv.field_size_limit(limits["attachment_max_expanded_bytes"])
        width = None
        for index, row in enumerate(
            csv.reader(io.StringIO(text, newline=""), strict=True), 1
        ):
            if width is not None and len(row) != width:
                raise ValueError("Inconsistent CSV rows")
            width = len(row)
            yield f"row:{index}", json.dumps(row, ensure_ascii=False)
    else:
        for index, line in enumerate(text.splitlines(), 1):
            yield f"line:{index}", line


def main():
    limits = json.loads(sys.argv[2])
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (limits["attachment_seconds"],) * 2)
    resource.setrlimit(
        resource.RLIMIT_FSIZE,
        (limits["attachment_max_expanded_bytes"] * 8 + 65536,) * 2,
    )
    path = Path(sys.argv[1])
    start = int(sys.argv[3])
    result: dict = {
        "fields": {},
        "state": "read",
        "reason": None,
        "units_read": 0,
        "next_unit": start,
    }
    warnings: set[str] = set()
    try:
        # Validate the entire bounded file even when only a slice is returned.
        total_bytes = 0
        for index, (locator, text) in enumerate(
            units(path, path.suffix, limits, warnings)
        ):
            total_bytes += len(text.encode()) + len(locator.encode())
            if total_bytes > limits["attachment_max_expanded_bytes"]:
                result["state"], result["reason"] = (
                    "partly_read",
                    "attachment_expansion_limit",
                )
                break
            if index < start:
                continue
            if result["units_read"] >= limits["attachment_max_units"]:
                result["state"], result["reason"] = (
                    "partly_read",
                    "attachment_unit_limit",
                )
                continue
            result["fields"]["attachment:" + locator] = text
            result["units_read"] += 1
            result["next_unit"] = index + 1
        if warnings:
            result["state"] = "partly_read"
            result["reason"] = result["reason"] or "content_unexamined"
            result["warnings"] = sorted(warnings)
    except PreparationFailure as error:
        result = {"state": "unavailable", "reason": error.code}
    except Exception:  # noqa: BLE001 - parser process emits only safe format outcomes
        result = {"state": "unavailable", "reason": "unreadable_file"}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
