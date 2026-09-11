"""Behavioral tests for deployment database initialization."""

import pytest
from sqlmodel import Session, create_engine, select

from app.database.init_db import initialize_database
from app.database.models import Client, User
from tests.deployment import SUPPORTED_TOPOLOGIES, load_compose_configuration


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
    "topology",
    SUPPORTED_TOPOLOGIES,
)
def test_compose_initialization_uses_the_backend_module_without_admin_credentials(
    topology,
):
    """Every topology invokes the shared initializer without default credentials."""
    configuration = load_compose_configuration(topology)
    initialization_service = configuration["services"]["db-init"]

    assert initialization_service["command"] == [
        "python3",
        "-m",
        "app.database.init_db",
    ]
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
    "topology",
    SUPPORTED_TOPOLOGIES,
)
def test_compose_backend_starts_after_successful_database_initialization(topology):
    """Every backend starts only after the healthy database is initialized."""
    configuration = load_compose_configuration(topology)
    services = configuration["services"]

    assert (
        services["db-init"]["depends_on"]["postgres"]["condition"] == "service_healthy"
    )
    assert (
        services["backend"]["depends_on"]["db-init"]["condition"]
        == "service_completed_successfully"
    )


@pytest.mark.parametrize(
    ("topology", "volume_name"),
    [
        ("direct", "setup_data"),
        ("development", "setup_dev_data"),
        ("reverse-proxy", "setup_data"),
    ],
)
def test_compose_persists_setup_data_only_for_the_backend(topology, volume_name):
    """Pending setup credentials persist without reaching browser-facing services."""
    configuration = load_compose_configuration(topology)
    services = configuration["services"]

    assert configuration["volumes"][volume_name]["driver"] == "local"
    assert {
        volume["source"]: volume["target"] for volume in services["backend"]["volumes"]
    }[volume_name] == "/app/data/setup"
    assert {
        service_name
        for service_name, service in services.items()
        if any(
            volume.get("source") == volume_name for volume in service.get("volumes", [])
        )
    } == {"backend"}


def test_development_topology_keeps_hot_reload_and_published_ports():
    """Setup persistence does not change the existing development workflow."""
    configuration = load_compose_configuration("development")
    backend = configuration["services"]["backend"]
    frontend = configuration["services"]["frontend"]

    assert backend["build"]["target"] == "development"
    assert backend["ports"] == [
        {
            "host_ip": "127.0.0.1",
            "mode": "ingress",
            "protocol": "tcp",
            "published": "8000",
            "target": 8000,
        }
    ]
    assert frontend["ports"] == [
        {
            "host_ip": "127.0.0.1",
            "mode": "ingress",
            "protocol": "tcp",
            "published": "5173",
            "target": 5173,
        }
    ]


@pytest.mark.parametrize(
    "topology",
    SUPPORTED_TOPOLOGIES,
)
def test_admin_bootstrap_variables_are_absent_from_every_compose_file(topology):
    """No shipped Compose overlay advertises obsolete administrator seeding."""
    configuration = load_compose_configuration(topology)
    environment_names = {
        name
        for service in configuration["services"].values()
        for name in service.get("environment", {})
    }

    assert not {"ADMIN_USERNAME", "ADMIN_PASSWORD", "ADMIN_EMAIL"} & environment_names
