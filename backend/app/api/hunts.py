"""
Hunt Operations API for Owlculus OSINT Platform.

This module provides automated OSINT workflow execution capabilities through the hunt system,
enabling complex multi-step investigations with real-time monitoring and results tracking.
"""

from fastapi import (
    APIRouter,
    Depends,
    Header,
    Query,
    Response,
    WebSocket,
)
from sqlmodel import Session

from app.core.dependencies import get_current_user
from app.database import models
from app.database.connection import get_db
from app.executions.results import HuntResultReader
from app.executions.service import hunt_observation
from app.schemas import hunt_schema as schemas
from app.services.export_service import ExportService
from app.services.hunt_execution_export import HuntExecutionExportFormat
from app.services.hunt_service import HuntService

router = APIRouter()


@router.get("/", response_model=list[schemas.HuntResponse])
async def list_hunts(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all available hunts"""
    service = HuntService(db)
    hunts = await service.list_hunts(current_user=current_user)

    response = []
    for hunt in hunts:
        hunt_dict = hunt.__dict__.copy()
        if "definition_json" in hunt_dict and "steps" in hunt_dict["definition_json"]:
            hunt_dict["step_count"] = len(hunt_dict["definition_json"]["steps"])
        hunt_dict["initial_parameters"] = hunt_dict["definition_json"].get(
            "initial_parameters", {}
        )
        response.append(schemas.HuntResponse(**hunt_dict))

    return response


@router.get("/executions/{execution_id}/export")
async def export_execution(
    execution_id: int,
    format: HuntExecutionExportFormat,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download a backend-generated hunt execution export."""
    service = ExportService(db)
    artifact = service.export_hunt_execution(
        execution_id=execution_id,
        current_user=current_user,
        export_format=format,
    )

    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={"Content-Disposition": f'attachment; filename="{artifact.filename}"'},
    )


@router.get("/{hunt_id}", response_model=schemas.HuntResponse)
async def get_hunt(
    hunt_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get details of a specific hunt"""
    service = HuntService(db)
    hunt = await service.get_hunt(hunt_id, current_user=current_user)

    hunt_dict = hunt.__dict__.copy()
    if "definition_json" in hunt_dict and "steps" in hunt_dict["definition_json"]:
        hunt_dict["step_count"] = len(hunt_dict["definition_json"]["steps"])
    hunt_dict["initial_parameters"] = hunt_dict["definition_json"].get(
        "initial_parameters", {}
    )

    return schemas.HuntResponse(**hunt_dict)


@router.post(
    "/{hunt_id}/execute", response_model=schemas.HuntExecutionResponse, status_code=202
)
async def execute_hunt(
    hunt_id: int,
    request: schemas.HuntExecuteRequest,
    response: Response,
    idempotency_key: str | None = Header(None, max_length=200),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Start a new hunt execution

    Initiates an asynchronous hunt workflow for the specified case.
    The hunt will run in the background and progress can be monitored
    via the execution status endpoint or WebSocket.
    """
    service = HuntService(db)

    execution = await service.create_execution(
        hunt_id=hunt_id,
        case_id=request.case_id,
        initial_parameters=request.parameters,
        current_user=current_user,
        idempotency_key=idempotency_key,
    )

    hunt = db.get(models.Hunt, execution.hunt_id)

    response.headers["Location"] = f"/api/hunts/executions/{execution.id}"
    return schemas.HuntExecutionResponse(
        **hunt_observation(db, execution),
        **HuntResultReader(db, execution, current_user).hunt_view(),
        hunt=(
            schemas.HuntResponse(
                **hunt.__dict__,
                initial_parameters=hunt.definition_json.get("initial_parameters", {}),
            )
            if hunt
            else None
        ),
    )


@router.get("/executions/{execution_id}", response_model=schemas.HuntExecutionResponse)
async def get_execution_status(
    execution_id: int,
    include_steps: bool = False,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get hunt execution status and results

    Returns the current status of a hunt execution including progress,
    completed steps, and any results or errors.
    """
    service = HuntService(db)
    execution = await service.get_execution(execution_id, current_user=current_user)

    hunt = db.get(models.Hunt, execution.hunt_id)
    case = execution.case
    created_by = db.get(models.User, execution.created_by_id)
    steps = None

    if include_steps:
        steps = await service.get_execution_steps(
            execution_id, current_user=current_user
        )

    reader = HuntResultReader(db, execution, current_user, steps)
    response = schemas.HuntExecutionResponse(
        **hunt_observation(db, execution),
        **reader.hunt_view(),
        hunt=(
            schemas.HuntResponse(
                **hunt.__dict__,
                initial_parameters=hunt.definition_json.get("initial_parameters", {}),
            )
            if hunt
            else None
        ),
        steps=(
            [schemas.HuntStepResponse(**reader.step_view(step)) for step in steps]
            if steps
            else None
        ),
        case=(
            {"id": case.id, "title": case.title, "case_number": case.case_number}
            if case
            else None
        ),
        created_by=(
            {
                "id": created_by.id,
                "email": created_by.email,
                "username": created_by.username,
            }
            if created_by
            else None
        ),
    )

    return response


@router.get(
    "/cases/{case_id}/executions",
    response_model=list[schemas.HuntExecutionListResponse],
)
async def list_case_executions(
    case_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all hunt executions for a specific case"""
    service = HuntService(db)
    executions = await service.list_case_executions(case_id, current_user=current_user)

    response = []
    for execution in executions:
        hunt = db.get(models.Hunt, execution.hunt_id)
        exec_dict = execution.__dict__.copy()
        if hunt:
            exec_dict["hunt_display_name"] = hunt.display_name
            exec_dict["hunt_category"] = hunt.category
        response.append(schemas.HuntExecutionListResponse(**exec_dict))

    return response


@router.delete("/executions/{execution_id}")
async def cancel_execution(
    execution_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel a running hunt execution"""
    service = HuntService(db)

    execution = await service.cancel_execution(execution_id, current_user=current_user)
    return {
        "message": (
            "Cancellation requested"
            if execution.status == "cancelling"
            else "Execution stopped"
        ),
        "execution_id": execution.id,
        "status": execution.status,
        "revision": hunt_observation(db, execution)["revision"],
    }


@router.websocket("/executions/{execution_id}/stream")
async def stream_execution(
    websocket: WebSocket,
    execution_id: int,
    db: Session = Depends(get_db),
):
    from app.executions.observation import observe

    await observe(websocket, db.get_bind(), "hunt", execution_id)


@router.get("/executions/{execution_id}/steps/{step_id}/results")
async def get_step_results(
    execution_id: int,
    step_id: str,
    cursor: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: models.User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008 - FastAPI dependency
):
    from app.core.exceptions import ResourceNotFoundException

    steps = await HuntService(db).get_execution_steps(
        execution_id, current_user=current_user
    )
    step = next((step for step in steps if step.step_id == step_id), None)
    if step is None:
        raise ResourceNotFoundException("Hunt step not found")
    execution = await HuntService(db).get_execution(
        execution_id, current_user=current_user
    )
    return HuntResultReader(db, execution, current_user, steps).step_results(
        step, cursor, limit
    )
