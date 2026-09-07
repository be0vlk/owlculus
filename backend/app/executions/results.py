"""Ordered hunt chunks and compatibility materialization for existing consumers."""

from sqlmodel import Session, col, select

from app.core.exceptions import ResourceNotFoundException
from app.database.models import (
    ExecutionControl,
    ExecutionEffect,
    HuntExecution,
    HuntStep,
    HuntStepResult,
    User,
)
from app.executions.correlation_visibility import (
    CORRELATION_ERROR,
    CORRELATION_PLUGIN,
    CorrelationVisibility,
    safe_error,
)
from app.hunts.correlation_scope import HuntCorrelationScope
from app.plugins.plugin_types import ENTITY_SAVE_SKIPPED
from app.services.case_access import CaseAccess


def _step_results(
    db: Session, step: HuntStep, cursor: int = 0, limit: int = 50
) -> dict:
    rows = db.exec(
        select(HuntStepResult)
        .where(HuntStepResult.step_id == step.id, HuntStepResult.sequence > cursor)
        .order_by(col(HuntStepResult.sequence))
        .limit(limit + 1)
    ).all()
    page = rows[:limit]
    return {
        "items": [row.payload for row in page],
        "cursor": page[-1].sequence if page else cursor,
        "next_cursor": page[-1].sequence if len(rows) > limit else None,
    }


def _stored_output(db: Session, step: HuntStep) -> dict | None:
    if step.output is not None:
        return step.output
    # Incremental chunks survive a worker dying before its final StepOutput commit.
    results, errors = [], []
    cursor = 0
    while True:
        page = _step_results(db, step, cursor, 200)
        for event in page["items"]:
            if event["type"] == "data":
                results.append(event["data"])
            elif event["type"] == "error":
                errors.append(event["data"])
        if page["next_cursor"] is None:
            break
        cursor = page["next_cursor"]
    if not results and not errors:
        return None
    return {
        "results": results,
        "result_count": len(results),
        "plugin": step.plugin_name,
        "errors": errors,
        "partial": True,
    }


def _readable_execution(db: Session, step: HuntStep, user: User) -> HuntExecution:
    execution = db.get(HuntExecution, step.execution_id)
    if execution is None:
        raise ResourceNotFoundException("Hunt execution not found")
    CaseAccess(db).readable(user, execution.case_id)
    return execution


def _skipped_entity_results(db: Session, step: HuntStep) -> list[dict]:
    # Trust only a durable receipt, never a provider's notice payload or message.
    receipt = db.exec(
        select(ExecutionEffect)
        .join(ExecutionControl, col(ExecutionControl.id) == ExecutionEffect.control_id)
        .where(
            ExecutionControl.hunt_execution_id == step.execution_id,
            ExecutionEffect.skipped == True,
            col(ExecutionEffect.operation_id).startswith(
                f"{step.step_id}:entity:", autoescape=True
            ),
        )
    ).first()
    return (
        [{"notice_type": "entity_save_skipped", "message": ENTITY_SAVE_SKIPPED}]
        if receipt
        else []
    )


def step_results(
    db: Session, step: HuntStep, user: User, cursor: int = 0, limit: int = 50
) -> dict:
    execution = _readable_execution(db, step, user)
    page = _step_results(db, step, cursor, limit)
    if not HuntCorrelationScope(db, execution).can_read(db, user, step.step_id):
        has_notice = any(
            event.get("type") == "data"
            and event.get("data", {}).get("notice_type") == "entity_save_skipped"
            for event in page["items"]
        )
        page["items"] = (
            [
                {"type": "data", "data": notice}
                for notice in _skipped_entity_results(db, step)
            ]
            if cursor == 0 or has_notice
            else []
        )
    elif step.plugin_name == CORRELATION_PLUGIN:
        page["items"] = CorrelationVisibility(db, user, execution.case_id).events(
            page["items"]
        )
    return page


def step_output(db: Session, step: HuntStep, user: User) -> dict | None:
    execution = _readable_execution(db, step, user)
    if not HuntCorrelationScope(db, execution).can_read(db, user, step.step_id):
        notices = _skipped_entity_results(db, step)
        return {
            "results": notices,
            "result_count": len(notices),
            "plugin": step.plugin_name,
            "errors": [],
        }
    output = _stored_output(db, step)
    if step.plugin_name == CORRELATION_PLUGIN:
        return CorrelationVisibility(db, user, execution.case_id).output(output)
    return output


def step_view(db: Session, step: HuntStep, user: User) -> dict:
    data = step.model_dump()
    data["output"] = step_output(db, step, user)
    scope = HuntCorrelationScope(db, _readable_execution(db, step, user))
    if not scope.can_read(db, user, step.step_id):
        data["parameters"] = {}
        data["error_details"] = None
    elif step.plugin_name == CORRELATION_PLUGIN:
        data["parameters"] = {}
        data["error_details"] = CORRELATION_ERROR if step.error_details else None
    return data


def hunt_view(db: Session, execution: HuntExecution, user: User) -> dict:
    CaseAccess(db).readable(user, execution.case_id)
    data = execution.model_dump()
    scope = HuntCorrelationScope(db, execution)
    context = execution.context_data or {}
    outputs = context.get("step_outputs", {})
    correlation_ids = scope.roots
    if correlation_ids or any(not scope.can_read(db, user, key) for key in outputs):
        visibility = CorrelationVisibility(db, user, execution.case_id)
        data["error"] = safe_error(execution.error)
        # Legacy metadata/evidence_refs have no verifiable Case scope. Rebuild
        # the context from its declared state and individually protected outputs.
        data["context_data"] = (
            {
                "initial_parameters": execution.initial_parameters,
                "step_outputs": {
                    key: visibility.output(value) if key in correlation_ids else value
                    for key, value in outputs.items()
                    if scope.can_read(db, user, key)
                },
                "failed_steps": context.get("failed_steps", []),
                "skipped_steps": context.get("skipped_steps", []),
            }
            if execution.context_data is not None
            else None
        )
    return data
