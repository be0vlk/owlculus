"""Create the Owlculus schema and seed deployment-level defaults."""

import os

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app.database.connection import create_db_and_tables, engine
from app.database.db_utils import transaction
from app.database.models import Client


def initialize_database(database_engine: Engine = engine) -> None:
    """Create the schema and idempotently seed the default Personal client."""
    if database_engine.dialect.name == "postgresql":
        with database_engine.begin() as connection:
            connection.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
    create_db_and_tables(database_engine)
    from app.database.upgrade_authorization import upgrade as upgrade_authorization

    upgrade_authorization(database_engine)
    if database_engine.dialect.name == "postgresql":
        from app.database.upgrade_executions import upgrade

        upgrade(database_engine)

    from app.database.upgrade_case_relationships import upgrade as upgrade_relationships

    upgrade_relationships(database_engine)

    from app.database.upgrade_correlation import upgrade as upgrade_correlation

    upgrade_correlation(database_engine)

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
