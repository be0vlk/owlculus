"""Create the Owlculus schema and seed deployment-level defaults."""

import os

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, select

from app.database import (
    upgrade_authorization,
    upgrade_case_relationships,
    upgrade_correlation,
    upgrade_executions,
    upgrade_strixy,
)
from app.database.connection import engine
from app.database.db_utils import transaction
from app.database.models import Client


def initialize_database(database_engine: Engine = engine) -> None:
    """Create the schema and idempotently seed the default Personal client."""
    SQLModel.metadata.create_all(database_engine)
    upgrade_authorization.upgrade(database_engine)
    upgrade_strixy.upgrade(database_engine)
    if database_engine.dialect.name == "postgresql":
        upgrade_executions.upgrade(database_engine)
    upgrade_case_relationships.upgrade(database_engine)
    upgrade_correlation.upgrade(database_engine)

    with Session(database_engine) as session:
        personal_client = session.exec(
            select(Client).where(Client.name == "Personal")
        ).first()
        if personal_client is None:
            with transaction(session):
                session.add(Client(name="Personal"))

    if database_engine.dialect.name == "postgresql" and os.environ.get(
        "RUNTIME_POSTGRES_USER"
    ):
        from app.database.runtime_role import provision_runtime_role

        provision_runtime_role(
            database_engine,
            os.environ["RUNTIME_POSTGRES_USER"],
            os.environ.get("RUNTIME_POSTGRES_PASSWORD", ""),
        )


if __name__ == "__main__":
    initialize_database()
