"""Deployment contract tests for backend container healthchecks."""

import pytest

from tests.deployment import (
    REPOSITORY_ROOT,
    SUPPORTED_TOPOLOGIES,
    load_compose_configuration,
)


def test_backend_image_excludes_runtime_setup_data():
    """A local pending setup token can never be copied into an image layer."""
    dockerignore = (REPOSITORY_ROOT / "backend/.dockerignore").read_text().splitlines()

    assert "data/setup/" in dockerignore


def test_backend_image_exposes_production_and_development_targets():
    """One backend image definition supplies both supported runtime adapters."""
    contents = (REPOSITORY_ROOT / "backend/Dockerfile").read_text()

    assert "AS development" in contents
    assert "AS production" in contents
    development_target = contents.split("AS development", maxsplit=1)[1].split(
        "AS production", maxsplit=1
    )[0]
    assert '"--reload"' in development_target


def test_backend_image_checks_process_liveness():
    """The shared backend image determines health through the liveness endpoint."""
    contents = (REPOSITORY_ROOT / "backend/Dockerfile").read_text()

    assert "HEALTHCHECK" in contents
    assert "http://localhost:8000/health/live" in contents


def test_backend_image_owns_persistent_directories_as_the_runtime_user():
    """Fresh named volumes inherit writable ownership for the non-root process."""
    contents = (REPOSITORY_ROOT / "backend/Dockerfile").read_text()
    runtime_instructions = contents[: contents.index("USER app")]

    assert "mkdir -p uploads data/setup" in runtime_instructions
    assert "chown -R app:app /app" in runtime_instructions


@pytest.mark.parametrize(
    "topology",
    SUPPORTED_TOPOLOGIES,
)
def test_compose_backend_healthchecks_wait_for_readiness(topology):
    """Every supported topology gates backend health on full readiness."""
    configuration = load_compose_configuration(topology)

    command = configuration["services"]["backend"]["healthcheck"]["test"]

    assert "http://localhost:8000/health/ready" in command
