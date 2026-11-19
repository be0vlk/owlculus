"""Behavioral tests for initial-setup state and token storage."""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.core.setup import (
    check_and_generate_setup_token,
    clear_setup_token,
    create_setup_token_once,
    get_setup_token,
    validate_setup_token,
)


def test_generated_setup_token_is_persisted(tmp_path, monkeypatch):
    """A generated token is non-empty and can be read from persistent storage."""
    token_file = tmp_path / "setup" / ".setup_token"
    monkeypatch.setattr("app.core.setup.SETUP_TOKEN_FILE", token_file)

    token = create_setup_token_once()[0]

    assert token
    assert get_setup_token() == token
    assert token_file.read_text() == token


def test_failed_setup_token_publication_leaves_no_secret_fragment(
    tmp_path, monkeypatch
):
    """A storage failure removes every temporary file containing the token."""
    token_file = tmp_path / "setup" / ".setup_token"
    monkeypatch.setattr("app.core.setup.SETUP_TOKEN_FILE", token_file)

    def fail_to_sync(_descriptor):
        raise OSError("simulated storage failure")

    monkeypatch.setattr("app.core.setup.os.fsync", fail_to_sync)

    with pytest.raises(OSError, match="simulated storage failure"):
        create_setup_token_once()[0]

    assert list(token_file.parent.iterdir()) == []


def test_setup_token_validation_accepts_only_the_persisted_token(tmp_path, monkeypatch):
    """Token validation accepts the current value and rejects missing or wrong ones."""
    monkeypatch.setattr(
        "app.core.setup.SETUP_TOKEN_FILE", tmp_path / "setup" / ".setup_token"
    )
    token = create_setup_token_once()[0]

    assert validate_setup_token(token) is True
    assert validate_setup_token("wrong-token") is False
    assert validate_setup_token(None) is False


def test_clearing_setup_token_invalidates_and_removes_it(tmp_path, monkeypatch):
    """Clearing a token makes it unavailable and is safe to repeat."""
    token_file = tmp_path / "setup" / ".setup_token"
    monkeypatch.setattr("app.core.setup.SETUP_TOKEN_FILE", token_file)
    token = create_setup_token_once()[0]

    clear_setup_token()
    clear_setup_token()

    assert get_setup_token() is None
    assert validate_setup_token(token) is False
    assert not token_file.exists()


def test_create_setup_token_once_reuses_the_persisted_private_token(
    tmp_path, monkeypatch
):
    """Independent initializers converge on one owner-readable token."""
    token_file = tmp_path / "setup" / ".setup_token"
    monkeypatch.setattr("app.core.setup.SETUP_TOKEN_FILE", token_file)

    first_token, first_created = create_setup_token_once()
    second_token, second_created = create_setup_token_once()

    assert first_created is True
    assert second_created is False
    assert second_token == first_token
    assert token_file.stat().st_mode & 0o777 == 0o600


def test_new_process_reuses_token_from_configured_setup_directory(
    tmp_path, monkeypatch
):
    """A restarted backend process reads the same token from shared storage."""
    setup_directory = tmp_path / "shared-setup"
    token_file = setup_directory / ".setup_token"
    monkeypatch.setattr("app.core.setup.SETUP_TOKEN_FILE", token_file)
    first_token, _ = create_setup_token_once()
    backend_root = Path(__file__).resolve().parents[2]
    script = (
        "import json, sys; "
        f"sys.path.insert(0, {str(backend_root)!r}); "
        "from app.core.setup import create_setup_token_once; "
        "print(json.dumps(create_setup_token_once()))"
    )
    child_environment = os.environ.copy()
    child_environment["OWLCULUS_SETUP_DATA_DIR"] = str(setup_directory)

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=child_environment,
        check=True,
        capture_output=True,
        text=True,
    )

    restarted_token, created = json.loads(completed.stdout)
    assert created is False
    assert restarted_token == first_token


def test_concurrent_initializers_publish_only_one_setup_token(tmp_path, monkeypatch):
    """Concurrent process-equivalent initializers converge on one persisted value."""
    token_file = tmp_path / "setup" / ".setup_token"
    monkeypatch.setattr("app.core.setup.SETUP_TOKEN_FILE", token_file)
    barrier = Barrier(8)

    def initialize(_):
        barrier.wait()
        return create_setup_token_once()

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(initialize, range(8)))

    assert {token for token, _ in results} == {token_file.read_text()}
    assert sum(created for _, created in results) == 1


def test_empty_installation_prints_new_token_once(
    session, tmp_path, monkeypatch, capsys
):
    """Startup persists and prints one retrievable token for an empty user table."""
    token_file = tmp_path / "setup" / ".setup_token"
    monkeypatch.setattr("app.core.setup.SETUP_TOKEN_FILE", token_file)

    check_and_generate_setup_token(session)
    first_output = capsys.readouterr()
    first_token = token_file.read_text()
    check_and_generate_setup_token(session)
    second_output = capsys.readouterr()

    assert first_token in first_output.err
    assert "SETUP TOKEN (use this to create your admin account)" in first_output.err
    assert "docker compose logs backend" in first_output.err
    assert second_output.out == ""
    assert second_output.err == ""
    assert token_file.read_text() == first_token


def test_existing_installation_does_not_create_or_print_token(
    session, test_admin, tmp_path, monkeypatch, capsys
):
    """Startup leaves setup closed when any user already exists."""
    token_file = tmp_path / "setup" / ".setup_token"
    monkeypatch.setattr("app.core.setup.SETUP_TOKEN_FILE", token_file)

    check_and_generate_setup_token(session)
    output = capsys.readouterr()

    assert output.out == ""
    assert output.err == ""
    assert not token_file.exists()


def test_application_startup_initializes_setup_token(engine, tmp_path, monkeypatch):
    """Starting the API initializes setup state after the schema is available."""
    token_file = tmp_path / "setup" / ".setup_token"
    monkeypatch.setattr("app.core.setup.SETUP_TOKEN_FILE", token_file)
    monkeypatch.setattr(main_module, "engine", engine, raising=False)

    with TestClient(main_module.app) as startup_client:
        response = startup_client.get("/")

    assert response.status_code == 200
    assert token_file.read_text()
