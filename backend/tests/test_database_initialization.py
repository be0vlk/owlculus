"""Behavioral tests for deployment database initialization."""

from pathlib import Path

import pytest
import yaml
from sqlmodel import Session, create_engine, select

from app.database.init_db import initialize_database
from app.database.models import Client, User

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SUPPORTED_COMPOSE_FILES = [
    "docker-compose.yml",
    "docker-compose.dev.yml",
    "docker-compose.reverse-proxy.yml",
]


def test_fresh_initialization_creates_personal_client_without_a_user(tmp_path):
    """A fresh deployment has its schema and case default, but no credentials."""
    database_path = tmp_path / "owlculus.db"
    database_engine = create_engine(f"sqlite:///{database_path}")

    initialize_database(database_engine)

    with Session(database_engine) as session:
        clients = list(session.exec(select(Client)))
        users = list(session.exec(select(User)))

    assert [(client.name, client.email) for client in clients] == [("Personal", None)]
    assert users == []


def test_repeated_initialization_does_not_duplicate_seed_data(tmp_path):
    """Restarting initialization preserves one credential-free Personal client."""
    database_engine = create_engine(f"sqlite:///{tmp_path / 'owlculus.db'}")

    initialize_database(database_engine)
    initialize_database(database_engine)

    with Session(database_engine) as session:
        clients = list(session.exec(select(Client)))
        users = list(session.exec(select(User)))

    assert [(client.name, client.email) for client in clients] == [("Personal", None)]
    assert users == []


@pytest.mark.parametrize(
    "compose_file",
    SUPPORTED_COMPOSE_FILES,
)
def test_compose_initialization_uses_the_backend_module_without_admin_credentials(
    compose_file,
):
    """Every topology invokes the shared initializer without default credentials."""
    configuration = yaml.safe_load((REPOSITORY_ROOT / compose_file).read_text())
    initialization_service = configuration["services"]["db-init"]

    assert initialization_service["command"] == "python3 -m app.database.init_db"
    assert (
        not {
            "ADMIN_USERNAME",
            "ADMIN_PASSWORD",
            "ADMIN_EMAIL",
        }
        & initialization_service["environment"].keys()
    )
    assert all(
        "init_db_auto.py" not in volume
        for volume in initialization_service.get("volumes", [])
    )


@pytest.mark.parametrize(
    "compose_file",
    [path.name for path in REPOSITORY_ROOT.glob("docker-compose*.yml")],
)
def test_admin_bootstrap_variables_are_absent_from_every_compose_file(compose_file):
    """No shipped Compose overlay advertises obsolete administrator seeding."""
    contents = (REPOSITORY_ROOT / compose_file).read_text()

    assert "ADMIN_USERNAME" not in contents
    assert "ADMIN_PASSWORD" not in contents
    assert "ADMIN_EMAIL" not in contents
