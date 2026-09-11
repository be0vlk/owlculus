"""Exercise fresh and existing-volume runtime permissions on disposable PostgreSQL."""

import subprocess
import time
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlmodel import Session, select

from app.core.security import (
    decrypt_api_key,
    encrypt_api_key,
    get_password_hash,
    verify_password,
)
from app.database.init_db import initialize_database
from app.database.models import Case, Client, SystemConfiguration, User
from app.database.runtime_role import provision_runtime_role


@pytest.fixture
def bootstrap_engine():
    name = f"owlculus-role-test-{uuid.uuid4().hex[:12]}"
    subprocess.run(
        [
            "docker",
            "run",
            "--pull=never",
            "--rm",
            "-d",
            "--name",
            name,
            "-e",
            "POSTGRES_PASSWORD=fixture-bootstrap",
            "-e",
            "POSTGRES_DB=fixture",
            "-p",
            "127.0.0.1::5432",
            "postgres:15-alpine",
        ],
        check=True,
        capture_output=True,
    )
    engine = None
    try:
        address = subprocess.check_output(
            ["docker", "port", name, "5432/tcp"], text=True
        ).strip()
        engine = create_engine(
            f"postgresql://postgres:fixture-bootstrap@{address}/fixture",
            hide_parameters=True,
        )
        for _ in range(100):
            try:
                with engine.connect():
                    break
            except DBAPIError:
                time.sleep(0.1)
        else:
            pytest.fail("Disposable PostgreSQL did not become ready")
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        subprocess.run(["docker", "rm", "-f", name], check=True, capture_output=True)


@pytest.mark.parametrize("existing", [False, True])
def test_fresh_and_existing_database_runtime_access(
    bootstrap_engine, monkeypatch, existing
):
    engine = bootstrap_engine
    if existing:
        initialize_database(engine)
        with Session(engine) as session:
            session.add(
                User(
                    username="existing",
                    email="existing@example.com",
                    password_hash=get_password_hash("existing-password"),
                )
            )
            session.add(
                SystemConfiguration(
                    api_keys={
                        "provider": {
                            "api_key": encrypt_api_key("existing-provider-secret"),
                            "is_active": True,
                        }
                    }
                )
            )
            session.add(Case(case_number="UPGRADE-1", title="Existing investigation"))
            session.commit()
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE legacy_record (id serial PRIMARY KEY, encrypted_key text, password_hash text)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO legacy_record (encrypted_key, password_hash) VALUES ('preserved-ciphertext', 'preserved-hash')"
                )
            )
            connection.execute(text("GRANT CREATE ON SCHEMA public TO PUBLIC"))
    monkeypatch.setenv("RUNTIME_POSTGRES_USER", "app_runtime")
    monkeypatch.setenv("RUNTIME_POSTGRES_PASSWORD", "fixture-runtime:@/'password")
    initialize_database(engine)
    initialize_database(engine)
    runtime = create_engine(
        engine.url.set(username="app_runtime", password="fixture-runtime:@/'password"),
        hide_parameters=True,
    )
    try:
        with Session(runtime) as session:
            personal = session.exec(
                select(Client).where(Client.name == "Personal")
            ).one()
            assert personal.id
            if existing:
                user = session.exec(
                    select(User).where(User.username == "existing")
                ).one()
                assert user.is_active
                assert verify_password("existing-password", user.password_hash)
                config = session.exec(select(SystemConfiguration)).one()
                assert (
                    decrypt_api_key(config.api_keys["provider"]["api_key"])
                    == "existing-provider-secret"
                )
                case = session.exec(
                    select(Case).where(Case.case_number == "UPGRADE-1")
                ).one()
                assert case.title == "Existing investigation"
                case.notes = "Updated after upgrade"
                session.add(case)
            session.add(Client(name="runtime-created"))
            session.commit()
        with engine.begin() as connection:
            connection.execute(
                text("CREATE TABLE future_record (id serial PRIMARY KEY, value text)")
            )
        with runtime.begin() as connection:
            connection.execute(
                text("INSERT INTO future_record (value) VALUES ('worker-result')")
            )
            connection.execute(
                text("SELECT * FROM future_record FOR UPDATE SKIP LOCKED")
            )
            connection.execute(text("UPDATE future_record SET value='dispatched'"))
            connection.execute(text("DELETE FROM future_record"))
            if existing:
                assert connection.execute(
                    text("SELECT encrypted_key, password_hash FROM legacy_record")
                ).one() == ("preserved-ciphertext", "preserved-hash")
                connection.execute(
                    text(
                        "INSERT INTO legacy_record (encrypted_key) VALUES ('new-ciphertext')"
                    )
                )
        for statement in [
            "CREATE TABLE forbidden (id int)",
            "CREATE TEMP TABLE forbidden (id int)",
            "CREATE ROLE forbidden",
            "CREATE DATABASE forbidden",
            "SET ROLE postgres",
            "ALTER TABLE client ADD COLUMN forbidden int",
            "TRUNCATE client",
            "DROP TABLE client",
            "CREATE EXTENSION file_fdw",
            "SELECT pg_read_file('/etc/passwd')",
        ]:
            with runtime.connect() as connection, pytest.raises(DBAPIError):
                connection.execute(text(statement))
        with pytest.raises(ValueError, match="restore its existing password"):
            provision_runtime_role(engine, "app_runtime", "incorrect-password")
        with runtime.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar() == 1
    finally:
        runtime.dispose()


def test_rejects_existing_elevated_or_member_roles(bootstrap_engine):
    with bootstrap_engine.begin() as connection:
        connection.execute(
            text("CREATE ROLE elevated LOGIN SUPERUSER PASSWORD 'fixture'")
        )
        connection.execute(text("CREATE ROLE member LOGIN PASSWORD 'fixture'"))
        connection.execute(text("GRANT postgres TO member"))
    for role in ("elevated", "member"):
        with pytest.raises(ValueError, match="elevated attributes or role memberships"):
            provision_runtime_role(bootstrap_engine, role, "fixture")
