"""Hunt catalogue, execution and result routes."""

from fastapi import (
    APIRouter,
    Depends,
    Header,
    Query,
    Response,
    WebSocket,
)
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.core.database_boundary import DatabaseRoute
from app.core.dependencies import get_current_user
from app.database import models
from app.database.connection import get_db, get_observation_engine
from app.executions.results import HuntResultReader
from app.executions.service import hunt_observation
from app.schemas import hunt_schema as schemas
from app.services.export_service import ExportService
from app.services.hunt_execution_export import HuntExecutionExportFormat
from app.services.hunt_service import HuntService

router = APIRouter(route_class=DatabaseRoute)


def _hunt_response(hunt: models.Hunt) -> schemas.HuntResponse:
    definition = hunt.definition_json
    return schemas.HuntResponse(
        **hunt.model_dump(),
        initial_parameters=definition.get("initial_parameters", {}),
        step_count=len(definition["steps"]) if "steps" in definition else None,
    )


@router.get("/", response_model=list[schemas.HuntResponse])
async def list_hunts(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all available hunts"""
    hunts = await HuntService(db).list_hunts(current_user=current_user)
    return [_hunt_response(hunt) for hunt in hunts]


@router.get("/executions/{execution_id}/export")
async def export_execution(
    execution_id: int,
    format: HuntExecutionExportFormat,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download a backend-generated hunt execution export."""
    artifact = ExportService(db).export_hunt_execution(
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
    return _hunt_response(
        await HuntService(db).get_hunt(hunt_id, current_user=current_user)
    )


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
    execution = await HuntService(db).create_execution(
        hunt_id=hunt_id,
        case_id=request.case_id,
        initial_parameters=request.parameters,
        current_user=current_user,
        idempotency_key=idempotency_key,
    )

    response.headers["Location"] = f"/api/hunts/executions/{execution.id}"
    return schemas.HuntExecutionResponse(
        **hunt_observation(db, execution),
        **HuntResultReader(db, execution, current_user).hunt_view(),
        # Acceptance hands back a detached execution, so load the hunt explicitly.
        hunt=_hunt_response(db.get_one(models.Hunt, execution.hunt_id)),
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
    steps = (
        await service.get_execution_steps(execution_id, current_user=current_user)
        if include_steps
        else None
    )
    reader = HuntResultReader(db, execution, current_user, steps)
    case = execution.case
    creator = execution.creator
    return schemas.HuntExecutionResponse(
        **hunt_observation(db, execution),
        **reader.hunt_view(),
        hunt=_hunt_response(execution.hunt),
        steps=(
            [schemas.HuntStepResponse(**reader.step_view(step)) for step in steps]
            if steps
            else None
        ),
        case={"id": case.id, "title": case.title, "case_number": case.case_number},
        created_by={
            "id": creator.id,
            "email": creator.email,
            "username": creator.username,
        },
    )


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
    executions = await HuntService(db).list_case_executions(
        case_id, current_user=current_user
    )
    return [
        schemas.HuntExecutionListResponse(
            **execution.model_dump(),
            hunt_display_name=execution.hunt.display_name,
            hunt_category=execution.hunt.category,
        )
        for execution in executions
    ]


@router.delete("/executions/{execution_id}")
async def cancel_execution(
    execution_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel a running hunt execution"""
    execution = await HuntService(db).cancel_execution(
        execution_id, current_user=current_user
    )
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
    database_engine: Engine = Depends(get_observation_engine),
):
    from app.executions.observation import observe

    await observe(websocket, database_engine, "hunt", execution_id)


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
