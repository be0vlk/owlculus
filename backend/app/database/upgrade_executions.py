"""Repeatable, versioned PostgreSQL upgrade for background plugin executions."""

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import SQLModel

from app.database.connection import engine
from app.database.models import (
    ExecutionControl,
    ExecutionEffect,
    ExecutionEvent,
    ExecutionOutbox,
    ExecutionSubmission,
    HuntStepResult,
    PluginExecution,
    PluginExecutionResult,
)

VERSION = "001_plugin_executions"


def upgrade_plugins(database_engine: Engine = engine) -> None:
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
            ExecutionEvent,
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


HUNT_VERSION = "002_hunt_executions"


def upgrade_hunts(database_engine: Engine = engine) -> None:
    upgrade_plugins(database_engine)
    with database_engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(827104001)"))
        if connection.execute(
            text("SELECT 1 FROM schema_upgrade WHERE version=:version"),
            {"version": HUNT_VERSION},
        ).first():
            return
        connection.execute(
            text(
                "ALTER TABLE huntexecution ADD COLUMN IF NOT EXISTS definition_snapshot JSON"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE huntexecution ADD COLUMN IF NOT EXISTS implementation_build VARCHAR"
            )
        )
        connection.execute(
            text("ALTER TABLE huntexecution ADD COLUMN IF NOT EXISTS error JSON")
        )
        connection.execute(
            text(
                "ALTER TABLE executioncontrol ALTER COLUMN plugin_execution_id DROP NOT NULL"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE executioncontrol ADD COLUMN IF NOT EXISTS hunt_execution_id INTEGER REFERENCES huntexecution(id) UNIQUE"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE executioncontrol DROP CONSTRAINT IF EXISTS execution_kind_xor"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE executioncontrol ADD CONSTRAINT execution_kind_xor CHECK ((plugin_execution_id IS NULL) <> (hunt_execution_id IS NULL))"
            )
        )
        connection.execute(text("""
            UPDATE huntexecution SET status='failed', completed_at=CURRENT_TIMESTAMP,
                error='{"code":"legacy_interrupted","message":"API-owned hunt interrupted during background-worker cutover; retained output is available. Submit a new hunt to run again."}'::json
            WHERE status IN ('pending', 'running') AND NOT EXISTS
                (SELECT 1 FROM executioncontrol WHERE hunt_execution_id=huntexecution.id)
        """))
        # Preserve numeric identities and all output. Give duplicate historical
        # associations an explicit, unused label before enforcing uniqueness.
        connection.execute(text("""
            DO $$ DECLARE
                duplicate_step RECORD;
                replacement TEXT;
            BEGIN
                FOR duplicate_step IN
                    SELECT id, execution_id, step_id FROM (
                        SELECT id, execution_id, step_id,
                            row_number() OVER (PARTITION BY execution_id, step_id ORDER BY id) AS occurrence
                        FROM huntstep
                    ) AS duplicates WHERE occurrence > 1 ORDER BY id
                LOOP
                    replacement := duplicate_step.step_id || '__legacy_duplicate_' || duplicate_step.id;
                    WHILE EXISTS (
                        SELECT 1 FROM huntstep
                        WHERE execution_id = duplicate_step.execution_id AND step_id = replacement
                    ) LOOP
                        replacement := replacement || '_';
                    END LOOP;
                    UPDATE huntstep SET step_id = replacement WHERE id = duplicate_step.id;
                END LOOP;
            END $$
        """))
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_hunt_step ON huntstep(execution_id, step_id)"
            )
        )
        connection.execute(text("""
            CREATE OR REPLACE FUNCTION protect_hunt_execution() RETURNS trigger AS $$
            BEGIN
                IF OLD.status IN ('completed','partial','failed','cancelled') AND row_to_json(NEW)::text IS DISTINCT FROM row_to_json(OLD)::text THEN
                    RAISE EXCEPTION 'Terminal execution is immutable';
                END IF;
                IF (NEW.case_id, NEW.created_by_id, NEW.hunt_id, NEW.initial_parameters::text, NEW.definition_snapshot::text, NEW.implementation_build)
                    IS DISTINCT FROM (OLD.case_id, OLD.created_by_id, OLD.hunt_id, OLD.initial_parameters::text, OLD.definition_snapshot::text, OLD.implementation_build) THEN
                    RAISE EXCEPTION 'Execution submission is immutable';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        """))
        connection.execute(
            text("DROP TRIGGER IF EXISTS hunt_execution_immutable ON huntexecution")
        )
        connection.execute(
            text(
                "CREATE TRIGGER hunt_execution_immutable BEFORE UPDATE ON huntexecution FOR EACH ROW EXECUTE FUNCTION protect_hunt_execution()"
            )
        )
        connection.execute(
            text("INSERT INTO schema_upgrade(version) VALUES (:version)"),
            {"version": HUNT_VERSION},
        )


SUBMISSION_VERSION = "003_reliable_submission"


def upgrade_submissions(database_engine: Engine = engine) -> None:
    upgrade_hunts(database_engine)
    with database_engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(827104001)"))
        if connection.execute(
            text("SELECT 1 FROM schema_upgrade WHERE version=:version"),
            {"version": SUBMISSION_VERSION},
        ).first():
            return
        SQLModel.metadata.tables[ExecutionSubmission.__name__.lower()].create(
            connection, checkfirst=True
        )
        connection.execute(
            text(
                "ALTER TABLE executionoutbox ADD COLUMN IF NOT EXISTS last_attempt_at TIMESTAMP"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE executionoutbox ADD COLUMN IF NOT EXISTS last_error VARCHAR"
            )
        )
        connection.execute(
            text("INSERT INTO schema_upgrade(version) VALUES (:version)"),
            {"version": SUBMISSION_VERSION},
        )


RESULT_VERSION = "004_bounded_results_and_effects"


def upgrade_results(database_engine: Engine = engine) -> None:
    upgrade_submissions(database_engine)
    with database_engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(827104001)"))
        if connection.execute(
            text("SELECT 1 FROM schema_upgrade WHERE version=:version"),
            {"version": RESULT_VERSION},
        ).first():
            return
        connection.execute(
            text(
                "ALTER TABLE pluginexecutionresult ADD COLUMN IF NOT EXISTS operation_index INTEGER"
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_plugin_result_operation ON pluginexecutionresult(execution_id, operation_index)"
            )
        )
        for model in (ExecutionEffect, HuntStepResult):
            SQLModel.metadata.tables[model.__name__.lower()].create(
                connection, checkfirst=True
            )
        connection.execute(
            text(
                "ALTER TABLE executioncontrol ADD COLUMN IF NOT EXISTS cancellation_requested_at TIMESTAMP"
            )
        )
        connection.execute(
            text("INSERT INTO schema_upgrade(version) VALUES (:version)"),
            {"version": RESULT_VERSION},
        )


def upgrade(database_engine: Engine = engine) -> None:
    upgrade_results(database_engine)
    with database_engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(827104001)"))
        connection.execute(
            text(
                "ALTER TABLE executioneffect ADD COLUMN IF NOT EXISTS skipped BOOLEAN NOT NULL DEFAULT FALSE"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE executioncontrol ADD COLUMN IF NOT EXISTS deadline_at TIMESTAMP"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE executioncontrol ADD COLUMN IF NOT EXISTS pending_status VARCHAR"
            )
        )
        connection.execute(
            text(
                "INSERT INTO schema_upgrade(version) VALUES ('005_cancellation_deadlines') ON CONFLICT DO NOTHING"
            )
        )

        for name, sql_type in (
            ("operation_id", "VARCHAR"),
            ("operation_started_at", "TIMESTAMP"),
            ("recovered_at", "TIMESTAMP"),
            ("recovery_attempts", "INTEGER NOT NULL DEFAULT 0"),
        ):
            connection.execute(
                text(
                    f"ALTER TABLE executioncontrol ADD COLUMN IF NOT EXISTS {name} {sql_type}"
                )
            )
        # Old workers did not journal starts. Never interpret their missing intent
        # as proof of safety. Deploy only after stopping the previous workers.
        if not connection.execute(
            text("SELECT 1 FROM schema_upgrade WHERE version='006_worker_recovery'")
        ).first():
            connection.execute(text("""
                UPDATE executioncontrol SET operation_id='legacy_unknown',
                    operation_started_at=CURRENT_TIMESTAMP
                WHERE owner IS NOT NULL AND operation_id IS NULL
            """))
            connection.execute(
                text(
                    "INSERT INTO schema_upgrade(version) VALUES ('006_worker_recovery')"
                )
            )

        connection.execute(
            text(
                "ALTER TABLE executioncontrol ADD COLUMN IF NOT EXISTS event_publish_after TIMESTAMP"
            )
        )
        SQLModel.metadata.tables[ExecutionEvent.__name__.lower()].create(
            connection, checkfirst=True
        )
        if not connection.execute(
            text("SELECT 1 FROM schema_upgrade WHERE version='007_shared_observation'")
        ).first():
            connection.execute(
                text(
                    "INSERT INTO executionevent(control_id, revision) SELECT id, revision FROM executioncontrol ON CONFLICT DO NOTHING"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO schema_upgrade(version) VALUES ('007_shared_observation')"
                )
            )

        # main stored retries in a required column with only an ORM-side default.
        # New workers omit it. Keep historical values while allowing new inserts,
        # including installations that have already applied execution versions 1-7.
        connection.execute(text("""DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_attribute
                WHERE attrelid = 'huntstep'::regclass
                    AND attname = 'retry_count' AND NOT attisdropped
            ) THEN
                ALTER TABLE huntstep ALTER COLUMN retry_count SET DEFAULT 0;
            END IF;
        END $$"""))
        connection.execute(
            text(
                "INSERT INTO schema_upgrade(version) VALUES ('008_legacy_hunt_retries') ON CONFLICT DO NOTHING"
            )
        )


if __name__ == "__main__":
    upgrade()
