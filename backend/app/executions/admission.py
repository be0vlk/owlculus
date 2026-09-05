"""Serialize durable acceptance and scope retry identities in PostgreSQL."""

import os

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


def previous(
    db: Session, user_id: int, kind: str, endpoint: str, key: str | None, payload: dict
):
    if key is None:
        return None
    if not key.strip() or len(key) > 200:
        raise HTTPException(422, "Idempotency-Key must contain 1–200 characters")
    submission = db.exec(
        select(ExecutionSubmission).where(
            ExecutionSubmission.user_id == user_id,
            ExecutionSubmission.kind == kind,
            ExecutionSubmission.endpoint == endpoint,
            ExecutionSubmission.key == key,
        )
    ).first()
    if submission is None:
        return None
    if submission.payload != payload:
        raise HTTPException(
            409,
            "Idempotency-Key was already used with a different case or payload. Start a new run for changed input.",
        )
    control = db.get(ExecutionControl, submission.control_id)
    assert control is not None
    return db.get(
        HuntExecution if kind == "hunt" else PluginExecution,
        control.hunt_execution_id if kind == "hunt" else control.plugin_execution_id,
    )


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


def remember(
    db: Session,
    control: ExecutionControl,
    user_id: int,
    kind: str,
    endpoint: str,
    key: str | None,
    payload: dict,
) -> None:
    if key is not None:
        db.add(
            ExecutionSubmission(
                user_id=user_id,
                kind=kind,
                endpoint=endpoint,
                key=key,
                payload=payload,
                control_id=control.id,
            )
        )
