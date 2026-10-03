"""Worker-owned loops, vault reads and fenced production case effects."""

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, replace
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.database.models import PluginExecution
from app.executions.effects import CaseEffects
from app.executions.ownership import (
    OwnershipLost,
    append_result,
    fail_execution,
    start_operation,
)
from app.executions.service import authorize_execution
from app.plugins.output_limits import serialized_size
from app.plugins.plugin_context import (
    ProductionPluginRunAdapter,
)
from app.plugins.plugin_registry import PluginRegistry
from app.plugins.plugin_runner import PluginRunner
from app.plugins.plugin_types import ResultEvent
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


@dataclass(frozen=True)
class EffectSink:
    """Expose one CaseEffects write as a PluginRun evidence or entity sink."""

    write: Callable[..., Any]


@contextmanager
def worker_resources(engine: Engine, ownership):
    """Own vault and fenced effect sessions inside the supervised child."""

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

    yield vault, session_factory


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
                    vault,
                )
                yield replace(
                    run,
                    evidence=EffectSink(effects.evidence),
                    entities=EffectSink(effects.entity),
                )

    return SanitizedAdapter(session_factory, lambda _: vault)


class WorkerPluginRunner(PluginRunner):
    """Release provider session reads at each event boundary in worker runs."""

    def __init__(self, registry: PluginRegistry, vault: WorkerVault):
        super().__init__(registry)
        self.vault = vault

    def event_size(self, event: ResultEvent) -> int:
        return serialized_size(self.vault.redact(event.to_wire()))

    async def run(self, name, params, context):
        async for result in super().run(name, params, context):
            context.session.rollback()
            yield result


async def execute(engine: Engine, registry: PluginRegistry, ownership) -> None:
    with worker_resources(engine, ownership) as (vault, session_factory):
        await execute_plugin_run(engine, registry, ownership, vault, session_factory)


async def execute_plugin_run(engine, registry, ownership, vault, session_factory):
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
            with Session(engine) as db:
                start_operation(db, ownership, "plugin")
            operation_index = 0
            async for result in WorkerPluginRunner(registry, vault).run(
                name, params, run
            ):
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
