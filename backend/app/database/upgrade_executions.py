"""Repeatable, versioned PostgreSQL upgrade for background plugin executions."""

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import SQLModel

from app.database.connection import engine
from app.database.models import (
    ExecutionControl,
    ExecutionOutbox,
    PluginExecution,
    PluginExecutionResult,
)

VERSION = "001_plugin_executions"


def upgrade(database_engine: Engine = engine) -> None:
    with database_engine.begin() as connection:
        # Serialize concurrent upgrade commands without touching historical hunts.
        connection.execute(text("SELECT pg_advisory_xact_lock(827104001)"))
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_upgrade (version TEXT PRIMARY KEY, applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
        )
        if connection.execute(
            text("SELECT 1 FROM schema_upgrade WHERE version = :version"),
            {"version": VERSION},
        ).first():
            return
        for model in (
            PluginExecution,
            ExecutionControl,
            ExecutionOutbox,
            PluginExecutionResult,
        ):
            SQLModel.metadata.tables[model.__name__.lower()].create(
                connection, checkfirst=True
            )
        connection.execute(text("""
            CREATE OR REPLACE FUNCTION protect_plugin_execution() RETURNS trigger AS $$
            BEGIN
                IF OLD.status IN ('completed', 'failed', 'cancelled') AND row_to_json(NEW)::text IS DISTINCT FROM row_to_json(OLD)::text THEN
                    RAISE EXCEPTION 'Terminal execution is immutable';
                END IF;
                IF (NEW.case_id, NEW.created_by_id, NEW.plugin_name, NEW.parameters::text, NEW.save_to_case)
                    IS DISTINCT FROM (OLD.case_id, OLD.created_by_id, OLD.plugin_name, OLD.parameters::text, OLD.save_to_case) THEN
                    RAISE EXCEPTION 'Execution submission is immutable';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        """))
        connection.execute(
            text("DROP TRIGGER IF EXISTS plugin_execution_immutable ON pluginexecution")
        )
        connection.execute(
            text(
                "CREATE TRIGGER plugin_execution_immutable BEFORE UPDATE ON pluginexecution FOR EACH ROW EXECUTE FUNCTION protect_plugin_execution()"
            )
        )
        connection.execute(
            text("INSERT INTO schema_upgrade(version) VALUES (:version)"),
            {"version": VERSION},
        )


if __name__ == "__main__":
    upgrade()
