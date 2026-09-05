"""Worker-owned loops, vault reads and fenced production case effects."""

from contextlib import contextmanager
from dataclasses import asdict, replace
from threading import Event, Thread

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.database.models import PluginExecution, User
from app.executions.effects import CaseEffects
from app.executions.ownership import (
    HEARTBEAT_SECONDS,
    OwnershipLost,
    append_result,
    claim,
    fail_execution,
    heartbeat,
)
from app.executions.service import authorize_execution
from app.plugins.plugin_context import (
    ProductionPluginRunAdapter,
)
from app.plugins.plugin_registry import PluginRegistry
from app.plugins.plugin_runner import PluginRunner
from app.plugins.plugin_types import EntityWrite, EvidenceWrite
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


class WorkerEvidenceSink:
    """Sanitize evidence before it reaches case services or file storage."""

    def __init__(self, sink: CaseEffects, vault: WorkerVault, case_id: int, user: User):
        self.sink, self.vault, self.case_id, self.user = sink, vault, case_id, user

    async def write(self, request: EvidenceWrite, user: User) -> None:
        if request.case_id != self.case_id:
            raise ValueError("Evidence must belong to the execution case")
        sanitized = EvidenceWrite(**self.vault.redact(asdict(request)))
        await self.sink.evidence(sanitized)


class WorkerEntitySink:
    """Sanitize discovered entity fields while fixing case and attribution."""

    def __init__(self, sink: CaseEffects, vault: WorkerVault, case_id: int, user: User):
        self.sink, self.vault, self.case_id, self.user = sink, vault, case_id, user

    async def write(self, request: EntityWrite, case_id: int, user: User) -> None:
        if case_id != self.case_id:
            raise ValueError("Entities must belong to the execution case")
        sanitized = type(request)(**self.vault.redact(asdict(request)))
        await self.sink.entity(sanitized)


@contextmanager
def worker_resources(engine: Engine, ownership):
    """Own heartbeat, vault and fenced effect sessions for either execution kind."""
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
        yield vault, session_factory, lease_lost
    finally:
        stop.set()
        thread.join(timeout=2)


def worker_adapter(session_factory, vault, ownership):
    class SanitizedAdapter(ProductionPluginRunAdapter):
        @contextmanager
        def open(self, *, user, case_id, save_to_case, operation_id="plugin"):
            with super().open(
                user=user, case_id=case_id, save_to_case=save_to_case
            ) as run:
                effects = CaseEffects(
                    session_factory,
                    ownership,
                    operation_id,
                    case_id,
                    user,
                    save_to_case,
                )
                yield replace(
                    run,
                    execution_id=ownership.control_id,
                    operation_id=operation_id,
                    evidence=WorkerEvidenceSink(effects, vault, case_id, user),
                    entities=WorkerEntitySink(effects, vault, case_id, user),
                )

    return SanitizedAdapter(session_factory, lambda _: vault)


class WorkerPluginRunner(PluginRunner):
    """Release provider session reads at each event boundary in worker runs."""

    async def run(self, name, params, context):
        async for result in super().run(name, params, context):
            context.session.rollback()
            yield result


async def execute(engine: Engine, registry: PluginRegistry, execution_id: int) -> None:
    with Session(engine) as db:
        ownership = claim(db, execution_id)
    if ownership is None:
        return
    with worker_resources(engine, ownership) as (vault, session_factory, lease_lost):
        await execute_plugin_run(
            engine, registry, ownership, vault, session_factory, lease_lost
        )


async def execute_plugin_run(
    engine, registry, ownership, vault, session_factory, lease_lost
):
    try:
        with Session(engine) as db:
            _, execution = ownership.lock(db)
            assert isinstance(execution, PluginExecution)
            user = authorize_execution(db, execution)
            name, params, case_id, save = (
                execution.plugin_name,
                execution.parameters,
                execution.case_id,
                execution.save_to_case,
            )
            db.expunge(user)
        adapter = worker_adapter(session_factory, vault, ownership)
        with adapter.open(user=user, case_id=case_id, save_to_case=save) as run:
            operation_index = 0
            async for result in WorkerPluginRunner(registry).run(name, params, run):
                if lease_lost.is_set():
                    raise OwnershipLost()
                with Session(engine) as db:
                    append_result(
                        db,
                        ownership,
                        vault.redact(result.to_wire()),
                        operation_index=operation_index,
                    )
                operation_index += 1
    except OwnershipLost:
        pass
    except Exception:  # noqa: BLE001 - isolate execution failures
        # Provider exceptions are normalized by PluginRunner. Never expose raw
        # infrastructure exceptions (connection URLs, SQL params, credentials).
        try:
            with Session(engine) as db:
                fail_execution(db, ownership)
        except OwnershipLost:
            pass
