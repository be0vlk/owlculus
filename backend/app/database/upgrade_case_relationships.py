"""Repeatable relationship cleanup, independent of account schema upgrades.

Only invalid foreign keys are detached. Evidence storage paths, physical files,
Task history, and all underlying investigation records are preserved.
"""

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.database.connection import engine


def upgrade(database_engine: Engine = engine) -> None:
    """Normalize existing references using CaseAccess's folder and reader rules."""
    with database_engine.begin() as connection:
        if database_engine.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(827104001)"))
        connection.execute(text("""
                UPDATE evidence SET parent_folder_id = NULL
                WHERE parent_folder_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM evidence AS parent
                    WHERE parent.id = evidence.parent_folder_id
                    AND parent.case_id = evidence.case_id AND parent.is_folder = TRUE
                )
            """))
        # Match CaseAccess.readable: Admin bypass or membership, with no extra
        # activity/role restrictions. Use only columns predating the account upgrade.
        connection.execute(text("""
                UPDATE task SET assigned_to_id = NULL
                WHERE assigned_to_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM "user" AS assignee
                    WHERE assignee.id = task.assigned_to_id AND (
                        assignee.role = 'Admin' OR EXISTS (
                            SELECT 1 FROM caseuserlink AS membership
                            WHERE membership.case_id = task.case_id
                            AND membership.user_id = assignee.id
                        )
                    )
                )
            """))


if __name__ == "__main__":
    upgrade()
