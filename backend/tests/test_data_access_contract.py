"""Architecture contract for service-owned database access."""

import ast
from pathlib import Path


def test_backend_does_not_import_shared_crud_module() -> None:
    backend_root = Path(__file__).parents[1]
    crud_module = backend_root / "app" / "database" / "crud.py"

    assert not crud_module.exists()

    offenders: list[str] = []
    for source_root in (backend_root / "app", backend_root / "tests"):
        for path in source_root.rglob("*.py"):
            if path == Path(__file__):
                continue
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    imports_crud_name = any(
                        alias.name == "crud" for alias in node.names
                    )
                    if imports_crud_name or node.module == "app.database.crud":
                        offenders.append(str(path.relative_to(backend_root)))
                elif isinstance(node, ast.Import):
                    if any(alias.name == "app.database.crud" for alias in node.names):
                        offenders.append(str(path.relative_to(backend_root)))

    assert offenders == []
