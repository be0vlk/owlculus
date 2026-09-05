"""Serialize durable acceptance and scope retry identities in PostgreSQL."""

import os
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import func, text
from sqlmodel import Session, col, select

from app.database.models import (
    ExecutionControl,
    ExecutionSubmission,
    HuntExecution,
    PluginExecution,
)

TERMINAL = {"completed", "partial", "failed", "cancelled"}


def lock_acceptance(db: Session) -> None:
    # One short transaction lock covers all three counters and idempotency scopes.
    # Counts derive from authoritative domain state, so terminal writes release
    # capacity without maintaining a second, potentially divergent counter.
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(827104003)"))


def require_capacity(db: Session, case_id: int, user_id: int) -> None:
    limits = [
        ("deployment", int(os.environ.get("EXECUTION_LIMIT_GLOBAL", "1000"))),
        ("case", int(os.environ.get("EXECUTION_LIMIT_CASE", "100"))),
        ("user", int(os.environ.get("EXECUTION_LIMIT_USER", "25"))),
    ]
    for scope, limit in limits:
        count = 0
        for model in (PluginExecution, HuntExecution):
            query = (
                select(func.count())
                .select_from(model)
                .where(col(model.status).not_in(TERMINAL))
            )
            if scope == "case":
                query = query.where(model.case_id == case_id)
            if scope == "user":
                query = query.where(model.created_by_id == user_id)
            count += db.exec(query).one()
        if count >= limit:
            raise HTTPException(
                429,
                f"Execution capacity is full for this {scope}. Wait for queued work to finish, then retry.",
                headers={"Retry-After": "10"},
            )


@dataclass(frozen=True)
class SubmissionRequest:
    user_id: int
    kind: str
    endpoint: str
    key: str | None
    payload: dict

    def previous(self, db: Session, normalize: Callable[[dict, dict], dict]):
        if self.key is None:
            return None
        if not self.key.strip() or len(self.key) > 200:
            raise HTTPException(422, "Idempotency-Key must contain 1–200 characters")
        submission = db.exec(
            select(ExecutionSubmission).where(
                ExecutionSubmission.user_id == self.user_id,
                ExecutionSubmission.kind == self.kind,
                ExecutionSubmission.endpoint == self.endpoint,
                ExecutionSubmission.key == self.key,
            )
        ).first()
        if submission is None:
            return None
        try:
            normalized = normalize(
                submission.parameter_definitions, self.payload["parameters"]
            )
        except HTTPException:
            raise HTTPException(
                409,
                "Idempotency-Key was already used with different input. Start a new run for changed input.",
            ) from None
        if submission.payload != {**self.payload, "parameters": normalized}:
            raise HTTPException(
                409,
                "Idempotency-Key was already used with a different case or payload. Start a new run for changed input.",
            )
        control = db.get(ExecutionControl, submission.control_id)
        assert control is not None
        return db.get(
            HuntExecution if self.kind == "hunt" else PluginExecution,
            (
                control.hunt_execution_id
                if self.kind == "hunt"
                else control.plugin_execution_id
            ),
        )

    def remember(
        self,
        db: Session,
        control: ExecutionControl,
        parameters: dict,
        definitions: dict,
    ) -> None:
        if self.key is not None:
            db.add(
                ExecutionSubmission(
                    user_id=self.user_id,
                    kind=self.kind,
                    endpoint=self.endpoint,
                    key=self.key,
                    payload={**self.payload, "parameters": parameters},
                    parameter_definitions=definitions,
                    control_id=control.id,
                )
            )
