"""
Hunt Operations API for Owlculus OSINT Platform.

This module provides automated OSINT workflow execution capabilities through the hunt system,
enabling complex multi-step investigations with real-time monitoring and results tracking.

Key features include:
- Hunt definition management with customizable workflow parameters
- Asynchronous hunt execution with progress tracking and status updates
- Real-time WebSocket streaming for live hunt monitoring and results
- Case-integrated hunt results with automatic evidence and entity creation
- Multi-step workflow coordination with conditional execution paths
- Secure hunt execution with role-based permissions and access controls
"""

from typing import List

from app.core.dependencies import get_current_user, get_db, no_analyst
from app.core.websocket_manager import websocket_manager
from app.database import models
from app.schemas import hunt_schema as schemas
from app.services.hunt_service import HuntService
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlmodel import Session

router = APIRouter()


@router.get("/", response_model=List[schemas.HuntResponse])
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


@router.get("/{hunt_id}", response_model=schemas.HuntResponse)
async def get_hunt(
    hunt_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get details of a specific hunt"""
    service = HuntService(db)
    hunt = await service.get_hunt(hunt_id, current_user=current_user)

    if not hunt:
        raise HTTPException(status_code=404, detail="Hunt not found")

    hunt_dict = hunt.__dict__.copy()
    if "definition_json" in hunt_dict and "steps" in hunt_dict["definition_json"]:
        hunt_dict["step_count"] = len(hunt_dict["definition_json"]["steps"])
    hunt_dict["initial_parameters"] = hunt_dict["definition_json"].get(
        "initial_parameters", {}
    )

    return schemas.HuntResponse(**hunt_dict)


@router.post("/{hunt_id}/execute", response_model=schemas.HuntExecutionResponse)
@no_analyst()
async def execute_hunt(
    hunt_id: int,
    request: schemas.HuntExecuteRequest,
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

    try:
        execution = await service.create_execution(
            hunt_id=hunt_id,
            case_id=request.case_id,
            initial_parameters=request.parameters,
            current_user=current_user,
        )

        hunt = db.get(models.Hunt, execution.hunt_id)

        response = schemas.HuntExecutionResponse(
            **execution.__dict__,
            hunt=(
                schemas.HuntResponse(
                    **hunt.__dict__,
                    initial_parameters=hunt.definition_json.get(
                        "initial_parameters", {}
                    )
                )
                if hunt
                else None
            )
        )

        return response

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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

    if not execution:
        raise HTTPException(status_code=404, detail="Hunt execution not found")

    hunt = db.get(models.Hunt, execution.hunt_id)
    case = db.get(models.Case, execution.case_id)
    created_by = db.get(models.User, execution.created_by_id)
    steps = None

    if include_steps:
        steps = await service.get_execution_steps(
            execution_id, current_user=current_user
        )

    response = schemas.HuntExecutionResponse(
        **execution.__dict__,
        hunt=(
            schemas.HuntResponse(
                **hunt.__dict__,
                initial_parameters=hunt.definition_json.get("initial_parameters", {})
            )
            if hunt
            else None
        ),
        steps=(
            [schemas.HuntStepResponse(**step.__dict__) for step in steps]
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
        )
    )

    return response


@router.get(
    "/cases/{case_id}/executions",
    response_model=List[schemas.HuntExecutionListResponse],
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
@no_analyst()
async def cancel_execution(
    execution_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel a running hunt execution"""
    service = HuntService(db)

    try:
        execution = await service.cancel_execution(
            execution_id, current_user=current_user
        )
        return {"message": "Hunt execution cancelled", "execution_id": execution.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.websocket("/executions/{execution_id}/stream")
async def stream_execution(
    websocket: WebSocket,
    execution_id: int,
    db: Session = Depends(get_db),
):
    """
    WebSocket endpoint for real-time hunt execution updates

    Streams progress events as the hunt executes including:
    - Step start/complete events
    - Progress updates
    - Error notifications
    - Final results

    Authentication: Pass ephemeral token as query parameter ?token=<ephemeral_token>
    The token must be obtained from POST /api/auth/websocket-token endpoint
    """
    token = websocket.query_params.get("token")

    if not token:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required"
        )
        return

    try:
        from app.core import security
        from app.database.models import User

        user_id = security.ephemeral_token_manager.validate_token(token, execution_id)

        if not user_id:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired token"
            )
            return

        current_user = db.get(User, user_id)
        if not current_user or not current_user.is_active:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Invalid user"
            )
            return

    except Exception:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Authentication failed"
        )
        return

    await websocket.accept()

    try:
        await websocket_manager.connect(execution_id, websocket)

        await websocket.send_json(
            {
                "execution_id": execution_id,
                "event_type": "connected",
                "message": "WebSocket connection established",
            }
        )

        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        websocket_manager.disconnect(execution_id, websocket)
    except Exception:
        await websocket.send_json(
            {"event_type": "error", "message": "Connection error"}
        )
        websocket_manager.disconnect(execution_id, websocket)
        await websocket.close()
