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


def test_backend_image_excludes_local_python_runtime_state():
    """Host environments and caches cannot leak into backend image layers."""
    dockerignore = (REPOSITORY_ROOT / "backend/.dockerignore").read_text().splitlines()

    assert {".venv/", "__pycache__/", ".pytest_cache/"} <= set(dockerignore)


def test_backend_image_installs_locked_production_dependencies():
    """The backend image and local development use one resolved dependency graph."""
    contents = (REPOSITORY_ROOT / "backend/Dockerfile").read_text()

    assert "COPY pyproject.toml uv.lock ./" in contents
    assert "uv sync --frozen --no-dev" in contents
    assert "requirements.txt" not in contents


def test_backend_source_root_does_not_shadow_the_app_package():
    """Copying the backend context must not create a competing /app package."""
    assert not (REPOSITORY_ROOT / "backend/__init__.py").exists()


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


@pytest.mark.parametrize("worker_name", ["plugin-worker", "hunt-worker"])
@pytest.mark.parametrize("topology", SUPPORTED_TOPOLOGIES)
def test_execution_processes_share_configuration_and_have_role_healthchecks(
    topology,
    worker_name,
):
    services = load_compose_configuration(topology)["services"]
    api = services["backend"]
    worker = services[worker_name]
    dispatcher = services["execution-dispatcher"]
    for service in (worker, dispatcher):
        assert service["build"] == api["build"]
        for key in (
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_DB",
            "POSTGRES_HOST",
            "SECRET_KEY",
            "REDIS_URL",
        ):
            assert service["environment"][key] == api["environment"][key]
        assert "8000" not in str(service["healthcheck"])
        assert (
            service["depends_on"]["db-init"]["condition"]
            == "service_completed_successfully"
        )
    assert "--pool=prefork" in worker["command"]
    assert "--concurrency=2" in worker["command"]
    assert "--prefetch-multiplier=1" in worker["command"]
    assert "worker-egress" in worker["networks"]
    uploads = lambda service: next(
        volume["source"]
        for volume in service["volumes"]
        if volume["target"] == "/app/uploads"
    )
    assert uploads(worker) == uploads(api)
