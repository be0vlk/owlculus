"""Task and task template routes."""

from typing import List

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app import schemas
from app.core.database_boundary import DatabaseRoute
from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.database.models import User
from app.services.task_service import TaskService

router = APIRouter(route_class=DatabaseRoute)


@router.get("/templates", response_model=List[schemas.TaskTemplateResponse])
async def list_templates(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await TaskService(db).get_templates(
        include_inactive, current_user=current_user
    )


@router.post("/templates", response_model=schemas.TaskTemplateResponse)
async def create_template(
    template: schemas.TaskTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await TaskService(db).create_custom_template(
        template.model_dump(), current_user=current_user
    )


@router.put("/templates/{template_id}", response_model=schemas.TaskTemplateResponse)
async def update_template(
    template_id: int,
    updates: schemas.TaskTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    return await TaskService(db).update_template(
        template_id, update_data, current_user=current_user
    )


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    success = await TaskService(db).delete_template(
        template_id, current_user=current_user
    )
    if success:
        return {"message": "Template deleted successfully"}


@router.get("/", response_model=List[schemas.TaskResponse])
async def list_tasks(
    filters: schemas.TaskFilter = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await TaskService(db).get_tasks(
        current_user=current_user,
        case_id=filters.case_id,
        assigned_to_id=filters.assigned_to_id,
        status=filters.status,
        priority=filters.priority,
        skip=filters.skip,
        limit=filters.limit,
    )


@router.post("/", response_model=schemas.TaskResponse)
async def create_task(
    task: schemas.TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await TaskService(db).create_task(
        case_id=task.case_id,
        task_data=task.model_dump(exclude={"case_id"}),
        current_user=current_user,
    )


@router.post("/bulk/assign", response_model=List[schemas.TaskResponse])
async def bulk_assign_tasks(
    data: schemas.BulkTaskAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await TaskService(db).bulk_assign(
        data.task_ids, data.user_id, current_user=current_user
    )


@router.post("/bulk/status", response_model=List[schemas.TaskResponse])
async def bulk_update_status(
    data: schemas.BulkTaskStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await TaskService(db).bulk_update_status(
        data.task_ids, data.status, current_user=current_user
    )


@router.get("/{task_id}", response_model=schemas.TaskResponse)
async def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await TaskService(db).get_task(task_id, current_user=current_user)


@router.put("/{task_id}", response_model=schemas.TaskResponse)
async def update_task(
    task_id: int,
    updates: schemas.TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    return await TaskService(db).update_task(
        task_id, update_data, current_user=current_user
    )


@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    success = await TaskService(db).delete_task(task_id, current_user=current_user)
    if success:
        return {"message": "Task deleted successfully"}


@router.post("/{task_id}/assign", response_model=schemas.TaskResponse)
async def assign_task(
    task_id: int,
    user_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await TaskService(db).assign_task(
        task_id, user_id, current_user=current_user
    )


@router.put("/{task_id}/status", response_model=schemas.TaskResponse)
async def update_task_status(
    task_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await TaskService(db).update_status(
        task_id, status, current_user=current_user
    )
