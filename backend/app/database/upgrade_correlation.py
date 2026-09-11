"""Repeatable provenance backfill that never rewrites historical report files."""

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, select

from app.database.connection import engine
from app.database.correlation_provenance import report_provenance
from app.database.models import Evidence


def upgrade(database_engine: Engine = engine) -> None:
    with database_engine.begin() as connection:
        if database_engine.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(827104001)"))
        SQLModel.metadata.tables["correlationevidence"].create(
            connection, checkfirst=True
        )
        with Session(bind=connection) as db:
            for evidence in db.exec(select(Evidence)):
                provenance = report_provenance(db, evidence)
                if provenance is not None:
                    db.merge(provenance)
            db.flush()


if __name__ == "__main__":
    upgrade()
