"""Deployment contract tests for backend container healthchecks."""

from pathlib import Path

import pytest
import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "dockerfile",
    ["backend/Dockerfile", "backend/Dockerfile.dev"],
)
def test_backend_images_check_process_liveness(dockerfile):
    """Backend images determine container health through the liveness endpoint."""
    contents = (REPOSITORY_ROOT / dockerfile).read_text()

    assert "HEALTHCHECK" in contents
    assert "http://localhost:8000/health/live" in contents


@pytest.mark.parametrize(
    "compose_file",
    [
        "docker-compose.yml",
        "docker-compose.dev.yml",
        "docker-compose.reverse-proxy.yml",
    ],
)
def test_compose_backend_healthchecks_wait_for_readiness(compose_file):
    """Every supported topology gates backend health on full readiness."""
    configuration = yaml.safe_load((REPOSITORY_ROOT / compose_file).read_text())

    command = configuration["services"]["backend"]["healthcheck"]["test"]

    assert "http://localhost:8000/health/ready" in command
