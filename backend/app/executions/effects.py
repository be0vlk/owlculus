"""Atomic, generation-fenced case effects through existing domain services."""

from contextlib import contextmanager
from dataclasses import dataclass, replace
from uuid import NAMESPACE_URL, uuid5

from sqlmodel import Session, select

from app.database.db_utils import transaction
from app.database.models import Case, ExecutionEffect, HuntExecution
from app.executions.service import authorize_execution
from app.hunts.correlation_scope import HuntCorrelationScope
from app.plugins.plugin_context import ServiceEntitySink, ServiceEvidenceSink
from app.plugins.plugin_types import ENTITY_SAVE_SKIPPED


@dataclass
class EffectOperation:
    db: Session
    receipt: ExecutionEffect
    replayed: bool = False


class CaseEffects:
    """One stable operation namespace per plugin invocation or hunt step."""

    def __init__(
        self, session_factory, ownership, operation_id, case_id, user, enabled
    ):
        self.session_factory = session_factory
        self.ownership = ownership
        self.operation_id = operation_id
        self.case_id = case_id
        self.user = user
        self.enabled = enabled
        self.counts = {"evidence": 0, "entity": 0}

    @contextmanager
    def operation(self, kind):
        index = self.counts[kind]
        self.counts[kind] += 1
        operation_id = f"{self.operation_id}:{kind}:{index}"
        with self.session_factory() as db, transaction(db):
            _, execution = self.ownership.lock(db)
            authorize_execution(db, execution)
            if execution.case_id != self.case_id:
                raise ValueError("Effects must belong to the execution case")
            # Serialize find/create and enrichment for this case, including runs
            # with different control records. No transaction spans provider work.
            db.exec(select(Case).where(Case.id == self.case_id).with_for_update()).one()
            receipt = db.exec(
                select(ExecutionEffect).where(
                    ExecutionEffect.control_id == self.ownership.control_id,
                    ExecutionEffect.operation_id == operation_id,
                )
            ).first()
            if not self.enabled:
                yield None
                return
            if receipt is not None:
                yield EffectOperation(db, receipt, replayed=True)
                return
            artifact_id = (
                f"{self.ownership.control_id}-{uuid5(NAMESPACE_URL, operation_id)}"
                if kind == "evidence"
                else None
            )
            db.info["effect_kind"] = kind
            receipt = ExecutionEffect(
                control_id=self.ownership.control_id,
                operation_id=operation_id,
                artifact_id=artifact_id,
            )
            db.add(receipt)
            yield EffectOperation(db, receipt)

    async def evidence(self, request):
        with self.operation("evidence") as operation:
            if operation is not None and not operation.replayed:
                db, artifact_id = operation.db, operation.receipt.artifact_id
                scope = self._correlation_scope(db)
                if scope is not None:
                    request = replace(request, correlation_case_ids=scope)
                await ServiceEvidenceSink(db, artifact_id).write(request, self.user)

    async def entity(self, request) -> str | None:
        with self.operation("entity") as operation:
            if operation is None:
                return None
            db, receipt = operation.db, operation.receipt
            if not operation.replayed:
                scope = self._correlation_scope(db)
                receipt.skipped = scope is not None and scope != (self.case_id,)
                if not receipt.skipped:
                    await ServiceEntitySink(db).write(request, self.case_id, self.user)
            # The receipt commits before feedback escapes, including skipped effects.
            warning = ENTITY_SAVE_SKIPPED if receipt.skipped else None
        return warning

    def _correlation_scope(self, db: Session) -> tuple[int, ...] | None:
        _, execution = self.ownership.lock(db)
        if isinstance(execution, HuntExecution):
            return HuntCorrelationScope(db, execution).inherited(self.operation_id)
        return None
