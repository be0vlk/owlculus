"""Operator-facing setup and test-data workflow contracts."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.deployment import REPOSITORY_ROOT, load_compose_configuration


def _write_executable(path: Path, contents: str) -> None:
    path.write_text(contents)
    path.chmod(0o755)


@pytest.fixture
def setup_workspace(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """Copy the setup entrypoint and replace external tools at their boundary."""
    shutil.copy2(REPOSITORY_ROOT / "setup.sh", tmp_path / "setup.sh")
    shutil.copy2(REPOSITORY_ROOT / "Makefile", tmp_path / "Makefile")
    (tmp_path / "scripts").mkdir()
    shutil.copy2(
        REPOSITORY_ROOT / "scripts/compose.sh", tmp_path / "scripts/compose.sh"
    )
    shutil.copy2(
        REPOSITORY_ROOT / "scripts/validate-deployment.py",
        tmp_path / "scripts/validate-deployment.py",
    )
    (tmp_path / "backend/app/core").mkdir(parents=True)
    shutil.copy2(
        REPOSITORY_ROOT / "backend/app/core/deployment.py",
        tmp_path / "backend/app/core/deployment.py",
    )
    (tmp_path / "frontend").mkdir()

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_calls = tmp_path / "docker-calls.log"
    _write_executable(
        fake_bin / "docker",
        """#!/usr/bin/env bash
if [[ "$*" == "compose version" ]]; then
    exit 0
fi
printf '%s\n' "$*" >> "$DOCKER_CALL_LOG"
if [[ "$*" == *"config --format json"* ]]; then
    if [[ "$*" == *"docker-compose.dev.yml"* ]]; then export TEST_TOPOLOGY=development; fi
    python3 - <<'PYTHON'
import json, os
from pathlib import Path
values = dict(line.split("=", 1) for line in Path(".env").read_text().splitlines() if line and not line.startswith("#") and "=" in line) if Path(".env").exists() else {}
values["OWLCULUS_ENV"] = "development" if os.environ.get("TEST_TOPOLOGY") == "development" else "production"
services = {name: {"environment": values} for name in ("backend", "plugin-worker", "hunt-worker", "execution-dispatcher", "db-init")}
services["backend"]["ports"] = [{"target": 8000, "published": "8000"}]
services["frontend"] = {"environment": {"__VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS": os.environ.get("TEST_DEV_HOST", "localhost")}, "ports": [{"target": 5173, "published": os.environ.get("TEST_DEV_PORT", "5173")}]}
print(json.dumps({"services": services}))
PYTHON
    exit 0
fi
if [[ -n "${FAIL_COMPOSE_COMMAND:-}" && " $* " == *" $FAIL_COMPOSE_COMMAND "* ]]; then
    echo "simulated Docker failure" >&2
    exit 1
fi
if [[ "$*" == *"exec -T backend python -c"* ]]; then
    case "${SETUP_TOKEN_STATE:-pending}" in
        unavailable) exit 1 ;;
        complete) exit 0 ;;
        delayed)
            if [[ ! -f "$DOCKER_CALL_LOG.retried" ]]; then
                touch "$DOCKER_CALL_LOG.retried"
                exit 1
            fi
            ;;
    esac
    printf '%s\n' 'test-one-time-setup-token'
fi
""",
    )
    _write_executable(
        fake_bin / "curl", "#!/usr/bin/env bash\nexit ${CURL_EXIT_CODE:-0}\n"
    )
    _write_executable(fake_bin / "sleep", "#!/usr/bin/env bash\nexit 0\n")

    environment = os.environ.copy()
    environment.update(
        {
            "DOCKER_CALL_LOG": str(docker_calls),
            "PATH": f"{fake_bin}:{environment['PATH']}",
        }
    )
    return tmp_path, environment


def _run_setup(workspace: Path, environment: dict[str, str], *args: str):
    return subprocess.run(
        ["bash", "setup.sh", *args],
        cwd=workspace,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def test_non_interactive_setup_hands_account_creation_to_the_browser(
    setup_workspace,
):
    """A fresh scripted install exposes setup without generating an administrator."""
    workspace, environment = setup_workspace

    completed = _run_setup(workspace, environment, "--non-interactive")

    generated_environment = (workspace / ".env").read_text()
    generated_names = {
        line.partition("=")[0]
        for line in generated_environment.splitlines()
        if line and not line.startswith("#") and "=" in line
    }
    assert (
        not {
            "ADMIN_USERNAME",
            "ADMIN_PASSWORD",
            "ADMIN_EMAIL",
            "FRONTEND_URL",
            "BACKEND_URL",
        }
        & generated_names
    )
    assert not (workspace / "frontend/.env").exists()
    assert not (workspace / "Caddyfile").exists()
    assert "Generated admin credentials" not in completed.stdout
    assert "Open http://localhost/setup" in completed.stdout
    assert "Setup token: test-one-time-setup-token" in completed.stdout
    assert "logs backend" not in completed.stdout
    assert (
        "up -d --wait --wait-timeout 120"
        in (workspace / "docker-calls.log").read_text()
    )


@pytest.mark.parametrize("mode", ["production", "dev"])
def test_setup_retries_token_retrieval_during_startup(setup_workspace, mode):
    workspace, environment = setup_workspace
    environment["SETUP_TOKEN_STATE"] = "delayed"

    completed = _run_setup(workspace, environment, mode, "--non-interactive")

    assert "Setup token: test-one-time-setup-token" in completed.stdout
    calls = (workspace / "docker-calls.log").read_text()
    assert calls.count("exec -T backend python -c") == 2
    if mode == "dev":
        assert "docker-compose.dev.yml" in calls


def test_setup_skips_token_for_existing_installation(setup_workspace):
    workspace, environment = setup_workspace
    environment["SETUP_TOKEN_STATE"] = "complete"

    completed = _run_setup(workspace, environment, "--non-interactive")

    assert "Administrator setup is already complete" in completed.stdout
    assert "Setup token:" not in completed.stdout
    assert "Complete first-run setup:" not in completed.stdout


def test_setup_falls_back_to_topology_logs_when_token_is_unavailable(setup_workspace):
    workspace, environment = setup_workspace
    environment["SETUP_TOKEN_STATE"] = "unavailable"

    completed = _run_setup(workspace, environment, "dev", "--non-interactive")

    assert "Could not retrieve the setup token" in completed.stdout
    assert "./scripts/compose.sh development logs backend" in completed.stdout
    assert "Setup token:" not in completed.stdout
    calls = (workspace / "docker-calls.log").read_text()
    assert calls.count("exec -T backend python -c") == 10


def test_clean_setup_removes_legacy_local_configuration(setup_workspace):
    """The clean option still discards local state before making a fresh config."""
    workspace, environment = setup_workspace
    (workspace / ".env").write_text("LEGACY_CONFIGURATION=true\n")
    (workspace / "frontend/.env").write_text("VITE_API_BASE_URL=legacy\n")

    _run_setup(workspace, environment, "--clean", "--non-interactive")

    assert "LEGACY_CONFIGURATION" not in (workspace / ".env").read_text()
    assert not (workspace / "frontend/.env").exists()


def test_test_data_helper_requires_operator_identity_without_a_password_flag():
    """Sample data cannot fall back to defaults or expose a password in argv."""
    completed = subprocess.run(
        [sys.executable, REPOSITORY_ROOT / "scripts/create_test_data.py"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "--username" in completed.stderr
    assert "required" in completed.stderr

    help_text = subprocess.run(
        [sys.executable, REPOSITORY_ROOT / "scripts/create_test_data.py", "--help"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "--password" not in help_text


def test_container_test_data_runner_forwards_username_without_password_argument(
    tmp_path: Path,
):
    """The Docker helper passes identity without exposing the password in argv."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy2(REPOSITORY_ROOT / "scripts/run_test_data.sh", scripts)
    shutil.copy2(REPOSITORY_ROOT / "scripts/create_test_data.py", scripts)
    compose_calls = tmp_path / "compose-calls.log"
    _write_executable(
        scripts / "compose.sh",
        f"#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >> {compose_calls}\n",
    )

    subprocess.run(
        [
            "bash",
            "scripts/run_test_data.sh",
            "--username",
            "chosen_admin",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    calls = compose_calls.read_text()
    assert "--username chosen_admin" in calls
    assert "--password" not in calls


def test_operator_documentation_explains_the_first_run_lifecycle():
    """The README makes fresh installs and upgrades operable without defaults."""
    readme = (REPOSITORY_ROOT / "README.md").read_text()

    for required_guidance in (
        "/setup",
        "docker compose logs backend",
        "same setup token",
        "token is consumed",
        "already has users",
        "DOMAIN",
        "same-origin",
    ):
        assert required_guidance in readme

    browser_docs = readme + (REPOSITORY_ROOT / "extension/README.md").read_text()
    assert "http://localhost:8000" not in browser_docs
    assert "--password" not in readme


def test_browser_extension_defaults_to_the_public_gateway():
    """Extension guidance and requests use the browser-facing site origin."""
    api_client = (REPOSITORY_ROOT / "extension/utils/api.js").read_text()
    session_config = (REPOSITORY_ROOT / "extension/utils/session.js").read_text()
    options_page = (REPOSITORY_ROOT / "extension/options/options.html").read_text()
    manifest = (REPOSITORY_ROOT / "extension/manifest.json").read_text()

    assert '|| "http://localhost"' in session_config
    assert 'placeholder="http://localhost"' in options_page
    assert '"http://localhost/*"' in manifest
    assert "http://localhost:8000" not in api_client + options_page + manifest


@pytest.mark.parametrize("command", ["build", "up"])
def test_setup_reports_docker_failure_without_claiming_success(
    setup_workspace, command
):
    workspace, environment = setup_workspace
    environment["FAIL_COMPOSE_COMMAND"] = command
    completed = subprocess.run(
        ["bash", "setup.sh", "dev", "--non-interactive"],
        cwd=workspace,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "simulated Docker failure" in completed.stderr
    assert "setup completed" not in completed.stdout
    assert "exec -T backend" not in (workspace / "docker-calls.log").read_text()


def test_setup_reports_failed_http_checks_without_claiming_success(setup_workspace):
    workspace, environment = setup_workspace
    environment["CURL_EXIT_CODE"] = "7"
    completed = subprocess.run(
        ["bash", "setup.sh", "dev", "--non-interactive"],
        cwd=workspace,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "setup completed" not in completed.stdout
    assert "logs" in completed.stdout


def test_development_logs_are_isolated_from_host_source_permissions():
    configuration = load_compose_configuration("development")
    mounts = configuration["services"]["backend"]["volumes"]
    log_mount = next(
        (mount for mount in mounts if mount["target"] == "/app/logs"), None
    )
    assert log_mount is not None
    assert log_mount["type"] == "volume"


@pytest.mark.parametrize("interactive", [False, True])
def test_development_setup_reports_effective_host_and_port(
    setup_workspace, interactive
):
    workspace, environment = setup_workspace
    (workspace / ".env").write_text("FRONTEND_PORT=80\n")
    environment.update(TEST_DEV_HOST="devbox.example.test", TEST_DEV_PORT="5180")
    completed = subprocess.run(
        ["bash", "setup.sh", "dev", *([] if interactive else ["--non-interactive"])],
        input="1\ny\n" if interactive else None,
        cwd=workspace,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "http://devbox.example.test:5180/setup" in completed.stdout
    if interactive:
        assert "Frontend URL: http://devbox.example.test:5180" in completed.stdout
    assert (workspace / ".env").read_text() == "FRONTEND_PORT=80\n"


@pytest.mark.parametrize("port", ["", "5180"])
def test_development_port_is_independent_of_production_port(port):
    configuration = load_compose_configuration(
        "development",
        environment_overrides={
            "FRONTEND_PORT": "8080",
            "DEV_FRONTEND_PORT": port,
            "DEV_HOST": "devbox.example.test",
        },
    )
    frontend = configuration["services"]["frontend"]
    assert frontend["ports"][0]["published"] == (port or "5173")
    assert (
        frontend["environment"]["__VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS"]
        == "devbox.example.test"
    )


def test_fresh_development_setup_saves_separate_development_settings(setup_workspace):
    workspace, environment = setup_workspace
    environment.update(TEST_DEV_HOST="devbox.example.test", TEST_DEV_PORT="5180")
    _run_setup(workspace, environment, "dev", "--non-interactive")
    settings = (workspace / ".env").read_text().splitlines()
    assert "FRONTEND_PORT=80" in settings
    assert "DEV_FRONTEND_PORT=5180" in settings
    assert "DEV_HOST=devbox.example.test" in settings


@pytest.mark.parametrize("invalid", ["", "owlculus_secure_password"])
def test_existing_setup_rejects_bad_credentials_without_rewriting(
    setup_workspace, invalid
):
    workspace, environment = setup_workspace
    original = f"SECRET_KEY=existing-private-key\nPOSTGRES_USER=owlculus\nPOSTGRES_PASSWORD={invalid}\nRUNTIME_POSTGRES_USER=owlculus_runtime\nRUNTIME_POSTGRES_PASSWORD=runtime-private-password\n"
    (workspace / ".env").write_text(original)
    result = subprocess.run(
        ["bash", "setup.sh", "--non-interactive"],
        cwd=workspace,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert (workspace / ".env").read_text() == original
    assert "POSTGRES_PASSWORD" in result.stderr
    assert "existing-private-key" not in result.stdout + result.stderr
    assert "runtime-private-password" not in result.stdout + result.stderr
    assert " build" not in (workspace / "docker-calls.log").read_text()


def test_existing_setup_explains_missing_runtime_credentials(setup_workspace):
    workspace, environment = setup_workspace
    original = (
        "SECRET_KEY=existing-private-key\n"
        "POSTGRES_USER=owlculus\n"
        "POSTGRES_PASSWORD=existing-private-password\n"
    )
    (workspace / ".env").write_text(original)
    result = subprocess.run(
        ["make", "setup"],
        input="2\ny\n",
        timeout=15,
        cwd=workspace,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "RUNTIME_POSTGRES_PASSWORD" in output
    assert "restricted database login" in output
    assert "openssl rand -hex 32" in output
    assert "Edit .env in the repository root" in output
    assert "Save .env and rerun: make setup" in output
    assert "preserve SECRET_KEY and POSTGRES_PASSWORD" in output
    assert "docs/deployment-security.md" not in output
    assert "existing-private-key" not in output
    assert "existing-private-password" not in output
    assert (workspace / ".env").read_text() == original
    assert " build" not in (workspace / "docker-calls.log").read_text()
