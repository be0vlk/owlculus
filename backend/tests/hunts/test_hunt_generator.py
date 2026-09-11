"""Contract tests for the repository's hunt-definition generator."""

import runpy
from pathlib import Path


def test_generated_hunt_does_not_emit_removed_timeout_fields():
    generator = runpy.run_path(
        str(Path(__file__).parents[3] / "scripts/create_hunt.py")
    )

    generated = generator["generate_hunt_definition"](
        {
            "class_name": "Example",
            "display_name": "Example",
            "description": "Example hunt",
            "category": "domain",
            "needs_db_session": False,
        }
    )

    assert "timeout_seconds" not in generated
