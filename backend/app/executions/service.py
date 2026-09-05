"""Transactional acceptance, authorization and bounded durable observation."""

from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, col, select

from app.database.db_utils import transaction
from app.database.models import (
    ExecutionControl,
    ExecutionOutbox,
    Hunt,
    HuntExecution,
    PluginExecution,
    PluginExecutionResult,
    User,
)
from app.plugins.plugin_registry import PluginRegistry
from app.services.case_access import CaseAccess


def validate_parameters(registry: PluginRegistry, name: str, params: dict) -> dict:
    metadata = registry.metadata().get(name)
    if metadata is None:
        raise HTTPException(404, "Plugin not found")
    if not metadata["enabled"]:
        raise HTTPException(409, "Plugin is disabled")
    definitions = {
        k: v
        for k, v in metadata["parameters"].items()
        if k not in {"case_id", "save_to_case"}
    }
    return normalize_parameters(definitions, params)


def normalize_parameters(definitions: dict, params: dict) -> dict:
    if params.keys() - definitions.keys():
        raise HTTPException(422, "Unknown plugin parameters")
    normalized = dict(params)
    types = {
        "string": (str,),
        "boolean": (bool,),
        "integer": (int,),
        "float": (int, float),
        "number": (int, float),
        "list": (list,),
    }
    for key, definition in definitions.items():
        if key not in normalized and "default" in definition:
            normalized[key] = definition["default"]
        value = normalized.get(key)
        if value is None or value == "":
            if definition.get("required"):
                raise HTTPException(422, f"{key} is required")
            normalized.pop(key, None)
            continue
        if type(value) not in types.get(definition["type"], ()):
            raise HTTPException(422, f"Invalid type for {key}")
        options = definition.get("options")
        if options and value not in options:
            raise HTTPException(422, f"Invalid option for {key}")
    return normalized


def authorize_execution(
    db: Session, execution: PluginExecution | HuntExecution
) -> User:
    user = db.get(User, execution.created_by_id, populate_existing=True)
    if user is None or not user.is_active:
        raise HTTPException(403, "Initiating user is inactive")
    access = CaseAccess(db)
    access.require_non_analyst(user)
    if isinstance(execution, HuntExecution) or execution.save_to_case:
        access.writable(user, execution.case_id)
    else:
        access.readable(user, execution.case_id)
    return user


def accept(
    db: Session, user: User, registry: PluginRegistry, name: str, params: dict
) -> dict:
    CaseAccess(db).require_non_analyst(user)
    values = dict(params)
    case_id = values.pop("case_id", None)
    if type(case_id) is not int or case_id <= 0:
        raise HTTPException(422, "A positive integer case_id is required")
    save = values.pop("save_to_case", False)
    if type(save) is not bool:
        raise HTTPException(422, "save_to_case must be a boolean")
    normalized = validate_parameters(registry, name, values)
    execution = PluginExecution(
        case_id=case_id,
        created_by_id=cast(int, user.id),
        plugin_name=name,
        parameters=normalized,
        save_to_case=save,
    )
    try:
        authorize_execution(db, execution)
        with transaction(db):
            db.add(execution)
            db.flush()
            control = ExecutionControl(plugin_execution_id=cast(int, execution.id))
            db.add(control)
            db.flush()
            outbox = ExecutionOutbox(control_id=cast(int, control.id))
            db.add(outbox)
            # Build before commit so a post-commit read failure cannot hide acceptance.
            response = representation(execution, control, outbox)
        return response
    except SQLAlchemyError:
        raise HTTPException(503, "Execution could not be accepted") from None


def representation(
    execution: PluginExecution, control: ExecutionControl, outbox: ExecutionOutbox
) -> dict[str, Any]:
    base = f"/api/plugins/executions/{execution.id}"
    return {
        **execution.model_dump(),
        "kind": "plugin",
        "revision": control.revision,
        "dispatch_state": "published" if outbox.published_at else "pending",
        "links": {
            "detail": base,
            "results": f"{base}/results",
            "history": f"/api/plugins/executions/case/{execution.case_id}",
        },
    }


def detail(db: Session, user: User, execution_id: int) -> dict:
    execution = db.get(PluginExecution, execution_id)
    if execution is None:
        raise HTTPException(404, "Execution not found")
    CaseAccess(db).readable(user, execution.case_id)
    control = db.exec(
        select(ExecutionControl).where(
            ExecutionControl.plugin_execution_id == execution_id
        )
    ).one()
    outbox = db.exec(
        select(ExecutionOutbox).where(ExecutionOutbox.control_id == control.id)
    ).one()
    return representation(execution, control, outbox)


def history(db: Session, user: User, case_id: int, cursor: int, limit: int) -> dict:
    CaseAccess(db).readable(user, case_id)
    query = (
        select(PluginExecution, ExecutionControl, ExecutionOutbox)
        .join(
            ExecutionControl,
            col(ExecutionControl.plugin_execution_id) == PluginExecution.id,
        )
        .join(ExecutionOutbox, col(ExecutionOutbox.control_id) == ExecutionControl.id)
        .where(PluginExecution.case_id == case_id)
    )
    if cursor:
        query = query.where(col(PluginExecution.id) < cursor)
    rows = db.exec(
        query.order_by(col(PluginExecution.id).desc()).limit(limit + 1)
    ).all()
    return {
        "items": [
            representation(execution, control, outbox)
            for execution, control, outbox in rows[:limit]
        ],
        "next_cursor": rows[limit - 1][0].id if len(rows) > limit else None,
    }


def results(
    db: Session, user: User, execution_id: int, cursor: int, limit: int
) -> dict:
    state = detail(db, user, execution_id)
    rows = db.exec(
        select(PluginExecutionResult)
        .where(
            PluginExecutionResult.execution_id == execution_id,
            PluginExecutionResult.sequence > cursor,
        )
        .order_by(col(PluginExecutionResult.sequence))
        .limit(limit + 1)
    ).all()
    page = rows[:limit]
    return {
        "items": [row.payload for row in page],
        "cursor": page[-1].sequence if page else cursor,
        "next_cursor": page[-1].sequence if len(rows) > limit else None,
        "revision": state["revision"],
    }


def accept_hunt(db: Session, user: User, hunt: Hunt, params: dict) -> HuntExecution:
    """Persist accepted work and its dispatch intent in the same transaction."""
    from copy import deepcopy

    from app.executions.build import implementation_build

    execution = HuntExecution(
        hunt_id=hunt.id,
        case_id=params["case_id"],
        created_by_id=user.id,
        initial_parameters=params["parameters"],
        definition_snapshot=deepcopy(hunt.definition_json),
        implementation_build=implementation_build(),
    )
    try:
        authorize_execution(db, execution)
        with transaction(db):
            db.add(execution)
            db.flush()
            control = ExecutionControl(hunt_execution_id=execution.id)
            db.add(control)
            db.flush()
            db.add(ExecutionOutbox(control_id=control.id))
            db.expunge(execution)
        return execution
    except SQLAlchemyError:
        raise HTTPException(503, "Execution could not be accepted") from None


def hunt_observation(db: Session, execution: HuntExecution) -> dict:
    rows = db.exec(
        select(ExecutionControl, ExecutionOutbox)
        .join(ExecutionOutbox, col(ExecutionOutbox.control_id) == ExecutionControl.id)
        .where(ExecutionControl.hunt_execution_id == execution.id)
    ).first()
    base = f"/api/hunts/executions/{execution.id}"
    return {
        "kind": "hunt",
        "revision": rows[0].revision if rows else 0,
        "dispatch_state": (
            ("published" if rows[1].published_at else "pending") if rows else "legacy"
        ),
        "links": {
            "detail": base,
            "history": f"/api/hunts/cases/{execution.case_id}/executions",
            "export": f"{base}/export",
        },
    }


def plugin_catalogue(db: Session, user: User, registry: PluginRegistry, api_keys):
    """Keep catalogue authorization at the same service boundary as execution."""
    CaseAccess(db).require_non_analyst(user)
    return registry.metadata(api_keys)
