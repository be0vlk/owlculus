"""Operator-facing setup and test-data workflow contracts."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.deployment import REPOSITORY_ROOT


def _write_executable(path: Path, contents: str) -> None:
    path.write_text(contents)
    path.chmod(0o755)


@pytest.fixture
def setup_workspace(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """Copy the setup entrypoint and replace external tools at their boundary."""
    shutil.copy2(REPOSITORY_ROOT / "setup.sh", tmp_path / "setup.sh")
    (tmp_path / "scripts").mkdir()
    shutil.copy2(
        REPOSITORY_ROOT / "scripts/compose.sh", tmp_path / "scripts/compose.sh"
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
""",
    )
    _write_executable(fake_bin / "curl", "#!/usr/bin/env bash\nexit 0\n")
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
    assert "docker compose logs backend" in completed.stdout


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
    options_page = (REPOSITORY_ROOT / "extension/options/options.html").read_text()
    manifest = (REPOSITORY_ROOT / "extension/manifest.json").read_text()

    assert '|| "http://localhost"' in api_client
    assert 'placeholder="http://localhost"' in options_page
    assert '"http://localhost/*"' in manifest
    assert "http://localhost:8000" not in api_client + options_page + manifest
