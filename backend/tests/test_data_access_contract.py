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
                    imports_old_module = node.module == "app.database.crud"
                    imports_old_package_member = node.module == "app.database" and any(
                        alias.name == "crud" for alias in node.names
                    )
                    if imports_old_module or imports_old_package_member:
                        offenders.append(str(path.relative_to(backend_root)))
                elif isinstance(node, ast.Import):
                    if any(alias.name == "app.database.crud" for alias in node.names):
                        offenders.append(str(path.relative_to(backend_root)))

    assert offenders == []


def test_transaction_helper_is_the_only_application_commit_point() -> None:
    app_root = Path(__file__).parents[1] / "app"
    transaction_module = app_root / "database" / "db_utils.py"
    offenders: list[str] = []

    for path in app_root.rglob("*.py"):
        if path == transaction_module:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        if any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "commit"
            for node in ast.walk(tree)
        ):
            offenders.append(str(path.relative_to(app_root)))

    assert offenders == []
