"""Architecture contract for centralized HTTP exception translation."""

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"


def _imports_http_exception(path: Path) -> bool:
    tree = ast.parse(path.read_text())
    framework_names: set[str] = set()

    def root_name(node: ast.expr) -> str | None:
        while isinstance(node, ast.Attribute):
            node = node.value
        return node.id if isinstance(node, ast.Name) else None

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in {"fastapi", "fastapi.exceptions", "starlette.exceptions"}:
                if any(alias.name == "HTTPException" for alias in node.names):
                    return True
            if module in {"fastapi", "starlette"}:
                framework_names.update(
                    alias.asname or alias.name
                    for alias in node.names
                    if alias.name == "exceptions"
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in {
                    "fastapi",
                    "fastapi.exceptions",
                    "starlette",
                    "starlette.exceptions",
                }:
                    framework_names.add(alias.asname or alias.name.split(".")[0])

    return any(
        isinstance(node, ast.Attribute)
        and node.attr == "HTTPException"
        and root_name(node.value) in framework_names
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


def test_guard_recognizes_framework_http_exception_import_styles(
    tmp_path: Path,
) -> None:
    """Aliases and qualified framework imports cannot bypass the guard."""
    sources = (
        "from fastapi import HTTPException as TransportError\n",
        "from starlette.exceptions import HTTPException\n",
        "import fastapi\nerror = fastapi.HTTPException\n",
        "import fastapi.exceptions\nerror = fastapi.exceptions.HTTPException\n",
        "import starlette.exceptions as exceptions\nerror = exceptions.HTTPException\n",
    )

    for index, source in enumerate(sources):
        module = tmp_path / f"transport_import_{index}.py"
        module.write_text(source)
        assert _imports_http_exception(module)
