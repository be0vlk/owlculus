"""Architecture contract for centralized HTTP exception translation."""

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"


def _imports_http_exception(path: Path) -> bool:
    tree = ast.parse(path.read_text())
    return any(
        isinstance(node, ast.ImportFrom)
        and node.module in {"fastapi", "fastapi.exceptions"}
        and any(alias.name == "HTTPException" for alias in node.names)
        for node in ast.walk(tree)
    )


def test_http_exception_is_confined_to_framework_translation() -> None:
    """Application modules raise domain exceptions, never transport exceptions."""
    offenders = [
        path.relative_to(APP_ROOT).as_posix()
        for path in APP_ROOT.rglob("*.py")
        if _imports_http_exception(path)
    ]

    assert offenders == []
