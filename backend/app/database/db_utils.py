"""
Database utilities for session management and transactions
"""

from contextlib import contextmanager
from typing import Any, Callable, Generator, TypeVar

from app.core.logging import get_logger_with_context
from app.database.connection import engine
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

logger = get_logger_with_context(module="db_utils")

T = TypeVar("T")


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    Ensures proper session cleanup and error handling.

    Usage:
        with get_session() as session:
            # perform database operations
            session.add(model)
            session.commit()
    """
    session = Session(engine)
    try:
        yield session
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Database error: {str(e)}")
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
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Transaction failed: {str(e)}")
        raise


def execute_in_transaction(
    session: Session,
    operation: Callable[[Session], T],
    error_message: str = "Database operation failed",
) -> T:
    """
    Execute a database operation within a transaction.

    Args:
        session: Database session
        operation: Function that performs database operations
        error_message: Custom error message for HTTP exceptions

    Returns:
        Result of the operation

    Raises:
        HTTPException: If the operation fails
    """
    try:
        with transaction(session):
            return operation(session)
    except SQLAlchemyError as e:
        logger.error(f"{error_message}: {str(e)}")
        raise HTTPException(status_code=500, detail=error_message)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=error_message)


def bulk_save(session: Session, models: list[Any]) -> None:
    """
    Efficiently save multiple models in a single transaction.

    Args:
        session: Database session
        models: List of models to save
    """
    try:
        with transaction(session):
            for model in models:
                session.add(model)
    except SQLAlchemyError as e:
        logger.error(f"Bulk save failed: {str(e)}")
        raise


def bulk_delete(session: Session, models: list[Any]) -> None:
    """
    Efficiently delete multiple models in a single transaction.

    Args:
        session: Database session
        models: List of models to delete
    """
    try:
        with transaction(session):
            for model in models:
                session.delete(model)
    except SQLAlchemyError as e:
        logger.error(f"Bulk delete failed: {str(e)}")
        raise


def refresh_model(session: Session, model: Any) -> Any:
    """
    Refresh a model instance from the database.
    Useful after commits or to get updated data.

    Args:
        session: Database session
        model: Model instance to refresh

    Returns:
        Refreshed model instance
    """
    try:
        session.refresh(model)
        return model
    except SQLAlchemyError as e:
        logger.error(f"Failed to refresh model: {str(e)}")
        raise
