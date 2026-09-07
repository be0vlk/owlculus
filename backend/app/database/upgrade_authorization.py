"""Repeatable account authentication cutover for existing PostgreSQL installations."""

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.database.connection import engine


def upgrade(database_engine: Engine = engine) -> None:
    """Preserve users and relationships while enforcing identity and role invariants."""
    with database_engine.begin() as connection:
        if database_engine.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(827104001)"))
            connection.execute(
                text(
                    'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS auth_identity VARCHAR'
                )
            )
            connection.execute(
                text(
                    'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS session_version INTEGER'
                )
            )
            connection.execute(
                text(
                    'UPDATE "user" SET auth_identity = gen_random_uuid()::text WHERE auth_identity IS NULL'
                )
            )
            connection.execute(
                text(
                    'UPDATE "user" SET session_version = 0 WHERE session_version IS NULL'
                )
            )
            connection.execute(
                text(
                    'ALTER TABLE "user" ALTER COLUMN auth_identity SET NOT NULL, ALTER COLUMN auth_identity SET DEFAULT gen_random_uuid()::text, ALTER COLUMN session_version SET NOT NULL, ALTER COLUMN session_version SET DEFAULT 0'
                )
            )
            connection.execute(
                text(
                    'CREATE UNIQUE INDEX IF NOT EXISTS user_auth_identity_unique ON "user" (auth_identity)'
                )
            )
            connection.execute(text("""DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = '"user"'::regclass AND conname = 'user_session_version_nonnegative') THEN
                    ALTER TABLE "user" ADD CONSTRAINT user_session_version_nonnegative CHECK (session_version >= 0);
                END IF;
            END $$"""))
        connection.execute(
            text(
                """UPDATE caseuserlink SET is_lead = false
            WHERE user_id IN (SELECT id FROM "user" WHERE role = 'Analyst') AND is_lead = true"""
            )
        )


if __name__ == "__main__":
    upgrade()
