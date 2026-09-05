"""One owned hunt per worker slot, with sequential in-process plugin steps."""

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.database.models import HuntExecution
from app.executions.ownership import OwnershipLost, claim, fail_execution
from app.executions.service import authorize_execution
from app.executions.worker import WorkerPluginRunner, worker_adapter, worker_resources
from app.hunts.hunt_executor import HuntExecutor
from app.plugins.plugin_registry import PluginRegistry


class DurableHuntNotifier:
    """Observation reads committed state until shared streaming is introduced."""

    async def broadcast(self, event):
        pass


async def execute(
    engine: Engine, registry: PluginRegistry, execution_id: int, *, ownership=None
) -> None:
    if ownership is None:
        with Session(engine) as db:
            ownership = claim(db, execution_id, kind="hunt")
    if ownership is None:
        return
    with (
        worker_resources(engine, ownership) as (vault, session_factory),
        Session(engine, expire_on_commit=False) as db,
    ):

        def fence(session):
            control, owned_execution = ownership.lock(session)
            authorize_execution(session, owned_execution)
            control.revision += 1
            if owned_execution.status in {"completed", "partial", "failed"}:
                control.pending_status = owned_execution.status
                owned_execution.status = "running"
                owned_execution.completed_at = None

        def before_step():
            with Session(engine) as check:
                _, execution = ownership.lock(check)
                authorize_execution(check, execution)

        event.listen(db, "before_commit", fence)
        try:
            _, execution = ownership.lock(db)
            assert isinstance(execution, HuntExecution)
            user = authorize_execution(db, execution)
            definition = execution.definition_snapshot
            assert definition is not None
            db.expunge(user)
            # End the initial read transaction without expiring the run data.
            db.commit()
            executor = HuntExecutor(
                db,
                DurableHuntNotifier(),
                plugin_runner=WorkerPluginRunner(registry, vault),
                run_adapter=worker_adapter(session_factory, vault, ownership),
                before_step=before_step,
                sanitize=vault.redact,
            )
            await executor.execute_hunt(execution, definition, user)
        except OwnershipLost:
            db.rollback()
        except Exception:  # noqa: BLE001 - record infrastructure failure safely
            db.rollback()
            try:
                with Session(engine) as failure_db:
                    fail_execution(failure_db, ownership)
            except OwnershipLost:
                db.rollback()
