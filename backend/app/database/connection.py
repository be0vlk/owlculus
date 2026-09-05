"""
Database connection management and session handling for Owlculus.

This module provides database connection utilities including engine configuration,
database creation, table initialization, and session management. It uses SQLModel
with PostgreSQL and includes connection pooling and health check configuration.
"""

import os
from collections.abc import Generator

from fastapi import HTTPException
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy_utils import create_database, database_exists
from sqlmodel import Session, create_engine

from ..core.config import settings
from .models import SQLModel


def create_execution_engine(
    *, default_pool_size: int = 2, default_max_overflow: int = 0
) -> Engine:
    """Create a pool in its owning process, with a bounded connection budget."""
    return create_engine(
        settings.get_database_url(),
        echo=False,
        hide_parameters=True,
        pool_size=int(os.environ.get("DATABASE_POOL_SIZE", default_pool_size)),
        max_overflow=int(os.environ.get("DATABASE_MAX_OVERFLOW", default_max_overflow)),
        pool_timeout=5,
        connect_args={"connect_timeout": 5},
        pool_pre_ping=True,
        pool_recycle=3600,
    )


engine = create_execution_engine(default_pool_size=5, default_max_overflow=5)


def create_db_and_tables(database_engine: Engine = engine) -> None:
    if not database_exists(database_engine.url):
        create_database(database_engine.url)
    SQLModel.metadata.create_all(database_engine)


def get_db() -> Generator[Session, None, None]:
    db = Session(engine)
    try:
        yield db
    except OperationalError:
        # Authentication and validation can touch PostgreSQL before acceptance.
        raise HTTPException(
            503,
            "Database temporarily unavailable; retry when service recovers",
            headers={"Retry-After": "10"},
        ) from None
    finally:
        db.close()
