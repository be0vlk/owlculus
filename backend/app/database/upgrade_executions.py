"""Repeatable, versioned PostgreSQL upgrade for background plugin executions."""

from collections.abc import Callable

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlmodel import SQLModel

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

Statement = str | Callable[[Connection], None]


def _tables(*models: type[SQLModel]) -> Callable[[Connection], None]:
    def create(connection: Connection) -> None:
        for model in models:
            SQLModel.metadata.tables[model.__name__.lower()].create(
                connection, checkfirst=True
            )

    return create


def _lock(connection: Connection) -> None:
    connection.execute(text("SELECT pg_advisory_xact_lock(827104001)"))
    connection.execute(
        text(
            "CREATE TABLE IF NOT EXISTS schema_upgrade (version TEXT PRIMARY KEY, applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
    )


def _run(connection: Connection, statements: tuple[Statement, ...]) -> None:
    for statement in statements:
        if isinstance(statement, str):
            connection.execute(text(statement))
        else:
            statement(connection)


def _apply(
    connection: Connection, version: str, statements: tuple[Statement, ...]
) -> None:
    """Run one version's statements once, serialized against concurrent upgrades."""
    _lock(connection)
    if connection.execute(
        text("SELECT 1 FROM schema_upgrade WHERE version = :version"),
        {"version": version},
    ).first():
        return
    _run(connection, statements)
    connection.execute(
        text("INSERT INTO schema_upgrade(version) VALUES (:version)"),
        {"version": version},
    )


PLUGIN_EXECUTIONS: tuple[Statement, ...] = (
    _tables(
        PluginExecution,
        ExecutionControl,
        ExecutionEvent,
        ExecutionOutbox,
        PluginExecutionResult,
    ),
    """
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
    """,
    "DROP TRIGGER IF EXISTS plugin_execution_immutable ON pluginexecution",
    "CREATE TRIGGER plugin_execution_immutable BEFORE UPDATE ON pluginexecution FOR EACH ROW EXECUTE FUNCTION protect_plugin_execution()",
)

HUNT_EXECUTIONS: tuple[Statement, ...] = (
    "ALTER TABLE huntexecution ADD COLUMN IF NOT EXISTS definition_snapshot JSON",
    "ALTER TABLE huntexecution ADD COLUMN IF NOT EXISTS implementation_build VARCHAR",
    "ALTER TABLE huntexecution ADD COLUMN IF NOT EXISTS error JSON",
    "ALTER TABLE executioncontrol ALTER COLUMN plugin_execution_id DROP NOT NULL",
    "ALTER TABLE executioncontrol ADD COLUMN IF NOT EXISTS hunt_execution_id INTEGER REFERENCES huntexecution(id) UNIQUE",
    "ALTER TABLE executioncontrol DROP CONSTRAINT IF EXISTS execution_kind_xor",
    "ALTER TABLE executioncontrol ADD CONSTRAINT execution_kind_xor CHECK ((plugin_execution_id IS NULL) <> (hunt_execution_id IS NULL))",
    """
    UPDATE huntexecution SET status='failed', completed_at=CURRENT_TIMESTAMP,
        error='{"code":"legacy_interrupted","message":"API-owned hunt interrupted during background-worker cutover; retained output is available. Submit a new hunt to run again."}'::json
    WHERE status IN ('pending', 'running') AND NOT EXISTS
        (SELECT 1 FROM executioncontrol WHERE hunt_execution_id=huntexecution.id)
    """,
    # Preserve numeric identities and all output. Give duplicate historical
    # associations an explicit, unused label before enforcing uniqueness.
    """
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
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_hunt_step ON huntstep(execution_id, step_id)",
    """
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
    """,
    "DROP TRIGGER IF EXISTS hunt_execution_immutable ON huntexecution",
    "CREATE TRIGGER hunt_execution_immutable BEFORE UPDATE ON huntexecution FOR EACH ROW EXECUTE FUNCTION protect_hunt_execution()",
)

RELIABLE_SUBMISSION: tuple[Statement, ...] = (
    _tables(ExecutionSubmission),
    "ALTER TABLE executionoutbox ADD COLUMN IF NOT EXISTS last_attempt_at TIMESTAMP",
    "ALTER TABLE executionoutbox ADD COLUMN IF NOT EXISTS last_error VARCHAR",
)

BOUNDED_RESULTS: tuple[Statement, ...] = (
    "ALTER TABLE pluginexecutionresult ADD COLUMN IF NOT EXISTS operation_index INTEGER",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_plugin_result_operation ON pluginexecutionresult(execution_id, operation_index)",
    _tables(ExecutionEffect, HuntStepResult),
    "ALTER TABLE executioncontrol ADD COLUMN IF NOT EXISTS cancellation_requested_at TIMESTAMP",
)

CANCELLATION_DEADLINES: tuple[Statement, ...] = (
    "ALTER TABLE executioneffect ADD COLUMN IF NOT EXISTS skipped BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE executioncontrol ADD COLUMN IF NOT EXISTS deadline_at TIMESTAMP",
    "ALTER TABLE executioncontrol ADD COLUMN IF NOT EXISTS pending_status VARCHAR",
)

WORKER_RECOVERY: tuple[Statement, ...] = (
    "ALTER TABLE executioncontrol ADD COLUMN IF NOT EXISTS operation_id VARCHAR",
    "ALTER TABLE executioncontrol ADD COLUMN IF NOT EXISTS operation_started_at TIMESTAMP",
    "ALTER TABLE executioncontrol ADD COLUMN IF NOT EXISTS recovered_at TIMESTAMP",
    "ALTER TABLE executioncontrol ADD COLUMN IF NOT EXISTS recovery_attempts INTEGER NOT NULL DEFAULT 0",
)

# Old workers did not journal starts. Never interpret their missing intent
# as proof of safety. Deploy only after stopping the previous workers.
WORKER_RECOVERY_BACKFILL: tuple[Statement, ...] = (
    """
    UPDATE executioncontrol SET operation_id='legacy_unknown',
        operation_started_at=CURRENT_TIMESTAMP
    WHERE owner IS NOT NULL AND operation_id IS NULL
    """,
)

SHARED_OBSERVATION: tuple[Statement, ...] = (
    "ALTER TABLE executioncontrol ADD COLUMN IF NOT EXISTS event_publish_after TIMESTAMP",
    _tables(ExecutionEvent),
)
SHARED_OBSERVATION_BACKFILL: tuple[Statement, ...] = (
    "INSERT INTO executionevent(control_id, revision) SELECT id, revision FROM executioncontrol ON CONFLICT DO NOTHING",
)

# main stored retries in a required column with only an ORM-side default.
# New workers omit it. Keep historical values while allowing new inserts,
# including installations that have already applied execution versions 1-7.
LEGACY_HUNT_RETRIES: tuple[Statement, ...] = (
    """
    DO $$ BEGIN
        IF EXISTS (
            SELECT 1 FROM pg_attribute
            WHERE attrelid = 'huntstep'::regclass
                AND attname = 'retry_count' AND NOT attisdropped
        ) THEN
            ALTER TABLE huntstep ALTER COLUMN retry_count SET DEFAULT 0;
        END IF;
    END $$
    """,
)


def upgrade(database_engine: Engine) -> None:
    # Versions 001-004 commit separately; 005-008 share one transaction.
    for version, statements in (
        ("001_plugin_executions", PLUGIN_EXECUTIONS),
        ("002_hunt_executions", HUNT_EXECUTIONS),
        ("003_reliable_submission", RELIABLE_SUBMISSION),
        ("004_bounded_results_and_effects", BOUNDED_RESULTS),
    ):
        with database_engine.begin() as connection:
            _apply(connection, version, statements)
    with database_engine.begin() as connection:
        _lock(connection)
        # Idempotent schema repairs run on every upgrade; only backfills run once.
        for version, repairs, backfill in (
            ("005_cancellation_deadlines", CANCELLATION_DEADLINES, ()),
            ("006_worker_recovery", WORKER_RECOVERY, WORKER_RECOVERY_BACKFILL),
            ("007_shared_observation", SHARED_OBSERVATION, SHARED_OBSERVATION_BACKFILL),
            ("008_legacy_hunt_retries", LEGACY_HUNT_RETRIES, ()),
        ):
            _run(connection, repairs)
            _apply(connection, version, backfill)
