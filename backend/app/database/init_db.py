"""Create the Owlculus schema and seed deployment-level defaults."""

from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app.database.connection import create_db_and_tables, engine
from app.database.db_utils import transaction
from app.database.models import Client


def initialize_database(database_engine: Engine = engine) -> None:
    """Create the schema and idempotently seed the default Personal client."""
    create_db_and_tables(database_engine)
    if database_engine.dialect.name == "postgresql":
        from app.database.upgrade_executions import upgrade

        upgrade(database_engine)

    from app.database.upgrade_case_relationships import upgrade as upgrade_relationships

    upgrade_relationships(database_engine)

    with Session(database_engine) as session:
        personal_client = session.exec(
            select(Client).where(Client.name == "Personal")
        ).first()
        if personal_client is None:
            with transaction(session):
                session.add(Client(name="Personal"))


if __name__ == "__main__":
    initialize_database()
