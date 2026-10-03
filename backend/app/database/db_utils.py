"""Database session and transaction boundaries.

``transaction`` is the sole commit point for service operations. Code running
inside it may add, delete, flush, and refresh, but must never commit. This keeps
each service operation atomic and prevents helpers from committing a caller's
partially completed work.
"""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from app.core.logging import get_logger_with_context
from app.database.connection import engine

logger = get_logger_with_context(module="db_utils")


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    Ensures proper session cleanup and error handling.

    Usage:
        with get_session() as session:
            with transaction(session):
                session.add(model)
    """
    session = Session(engine)
    try:
        yield session
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Database error: {e!s}")
        raise
    finally:
        session.close()


@contextmanager
def transaction(session: Session) -> Generator[Session, None, None]:
    """
    Context manager for explicit database transactions.
    Automatically commits on success or rolls back on error.

    Usage:
        with transaction(session) as tx_session:
            # perform multiple operations
            tx_session.add(model1)
            tx_session.add(model2)
            # auto-commit on successful exit
    """
    outermost = not session.info.get("transaction_depth", 0)
    session.info["transaction_depth"] = session.info.get("transaction_depth", 0) + 1
    try:
        yield session
        if outermost:
            session.commit()
        else:
            session.flush()
    except Exception as e:
        session.rollback()
        logger.error(f"Transaction failed: {e!s}")
        raise
    finally:
        session.info["transaction_depth"] -= 1


def keyset_page(session: Session, query, limit: int, cursor_of) -> tuple[list, Any]:
    """One page of an ordered, cursor-filtered query, plus the next cursor if more rows follow."""
    rows = session.exec(query.limit(limit + 1)).all()
    page = rows[:limit]
    return page, cursor_of(page[-1]) if len(rows) > limit else None
