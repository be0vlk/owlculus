"""Worker-owned loops, vault reads and fenced production case effects."""

from contextlib import contextmanager
from threading import Event, Thread

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.executions.ownership import (
    HEARTBEAT_SECONDS,
    OwnershipLost,
    append_result,
    claim,
    heartbeat,
)
from app.executions.service import authorize_execution
from app.plugins.plugin_context import ProductionPluginRunAdapter
from app.plugins.plugin_registry import PluginRegistry
from app.plugins.plugin_runner import PluginRunner
from app.services.api_key_vault import ConfigurationApiKeyVault, Provider


class WorkerVault:
    """Release the credential lookup transaction before returning to providers."""

    def __init__(self, engine: Engine):
        self.engine = engine
        self.secrets: set[str] = set()

    def get_key(self, provider: Provider) -> str | None:
        with Session(self.engine) as db:
            key = ConfigurationApiKeyVault(db).get_key(provider)
        if key:
            self.secrets.add(key)
        return key

    def is_configured(self, provider: Provider) -> bool:
        return self.get_key(provider) is not None

    def redact(self, value):
        if isinstance(value, str):
            for secret in self.secrets:
                value = value.replace(secret, "[redacted]")
            return value
        if isinstance(value, dict):
            return {self.redact(k): self.redact(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.redact(item) for item in value]
        return value


async def execute(engine: Engine, registry: PluginRegistry, execution_id: int) -> None:
    with Session(engine) as db:
        ownership = claim(db, execution_id)
    if ownership is None:
        return
    stop = Event()
    lease_lost = Event()

    def keep_alive():
        while not stop.wait(HEARTBEAT_SECONDS):
            try:
                with Session(engine) as db:
                    heartbeat(db, ownership)
            except Exception:  # noqa: BLE001 - isolate execution failures
                lease_lost.set()
                return

    thread = Thread(target=keep_alive, daemon=True)
    thread.start()
    vault = WorkerVault(engine)

    @contextmanager
    def session_factory():
        with Session(engine, expire_on_commit=False) as db:
            # Existing evidence/entity services own their transactions. Fence every
            # commit, including folder creation, in that same transaction.
            def guard(session):
                _, execution = ownership.lock(session)
                authorize_execution(session, execution)

            event.listen(db, "before_commit", guard)
            yield db

    try:
        with Session(engine) as db:
            _, execution = ownership.lock(db)
            user = authorize_execution(db, execution)
            name, params, case_id, save = (
                execution.plugin_name,
                execution.parameters,
                execution.case_id,
                execution.save_to_case,
            )
            db.expunge(user)
        adapter = ProductionPluginRunAdapter(session_factory, lambda _: vault)
        with adapter.open(user=user, case_id=case_id, save_to_case=save) as run:
            async for result in PluginRunner(registry).run(name, params, run):
                run.session.rollback()
                if lease_lost.is_set():
                    raise OwnershipLost()
                with Session(engine) as db:
                    append_result(db, ownership, vault.redact(result.to_wire()))
    except OwnershipLost:
        pass
    except Exception:  # noqa: BLE001 - isolate execution failures
        # Provider exceptions are normalized by PluginRunner. Never expose raw
        # infrastructure exceptions (connection URLs, SQL params, credentials).
        try:
            with Session(engine) as db:
                append_result(
                    db,
                    ownership,
                    {
                        "type": "error",
                        "data": {"message": "Execution could not finish"},
                    },
                )
                append_result(db, ownership, {"type": "complete", "data": {}})
        except OwnershipLost:
            pass
    finally:
        stop.set()
        thread.join(timeout=2)
