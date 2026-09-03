"""Deployment contract tests for backend container healthchecks."""

from pathlib import Path

import pytest
import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_backend_image_excludes_runtime_setup_data():
    """A local pending setup token can never be copied into an image layer."""
    dockerignore = (REPOSITORY_ROOT / "backend/.dockerignore").read_text().splitlines()

    assert "data/setup/" in dockerignore


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
    "dockerfile",
    ["backend/Dockerfile", "backend/Dockerfile.dev"],
)
def test_backend_images_own_persistent_directories_as_the_runtime_user(dockerfile):
    """Fresh named volumes inherit writable ownership for the non-root process."""
    contents = (REPOSITORY_ROOT / dockerfile).read_text()
    runtime_instructions = contents[: contents.index("USER app")]

    assert "mkdir -p uploads data/setup" in runtime_instructions
    assert "chown -R app:app /app" in runtime_instructions


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
