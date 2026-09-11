"""Shared interface for inspecting supported Docker Compose topologies."""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_SCRIPT = REPOSITORY_ROOT / "scripts/compose.sh"
SUPPORTED_TOPOLOGIES = ("direct", "development", "reverse-proxy")


def load_compose_configuration(
    topology: str, *, environment_overrides: dict[str, str] | None = None
) -> dict[str, Any]:
    """Render one supported topology through Docker Compose's merge semantics."""
    environment = os.environ.copy()
    for variable in (
        "DEV_BIND_HOST",
        "DEV_HOST",
        "DEV_FRONTEND_PORT",
        "DB_PORT",
        "RUNTIME_POSTGRES_USER",
        "RUNTIME_POSTGRES_PASSWORD",
        "BACKEND_PORT",
        "BACKEND_URL",
        "DOMAIN",
        "FORWARDED_ALLOW_IPS",
        "FRONTEND_PORT",
        "FRONTEND_URL",
        "HTTPS_PORT",
        "POSTGRES_DB",
        "POSTGRES_PASSWORD",
        "POSTGRES_USER",
        "REDIS_URL",
        "AUTH_REDIS_URL",
        "EXECUTION_BROKER_URL",
        "EXECUTION_EVENT_REDIS_URL",
        "SECRET_KEY",
    ):
        environment.pop(variable, None)
    environment.update(environment_overrides or {})

    completed = subprocess.run(
        [
            COMPOSE_SCRIPT,
            topology,
            "--env-file",
            "/dev/null",
            "config",
            "--format",
            "json",
        ],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)
