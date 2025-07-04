"""
Task management API endpoints
"""

from typing import List

from app import schemas
from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.database.models import User
from app.services.task_service import TaskService
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

router = APIRouter()


# Template endpoints
@router.get("/templates", response_model=List[schemas.TaskTemplateResponse])
async def list_templates(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all available task templates"""
    service = TaskService(db)
    templates = await service.get_templates(include_inactive, current_user)
    return templates


@router.post("/templates", response_model=schemas.TaskTemplateResponse)
async def create_template(
    template: schemas.TaskTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a custom task template (Admin only)"""
    service = TaskService(db)
    return await service.create_custom_template(template.model_dump(), current_user)


# Task CRUD endpoints
@router.get("/", response_model=List[schemas.TaskResponse])
async def list_tasks(
    filters: schemas.TaskFilter = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List tasks with optional filters"""
    service = TaskService(db)
    tasks = await service.get_tasks(
        current_user=current_user,
        case_id=filters.case_id,
        assigned_to_id=filters.assigned_to_id,
        status=filters.status,
        priority=filters.priority,
        skip=filters.skip,
        limit=filters.limit,
    )
    return tasks


@router.post("/", response_model=schemas.TaskResponse)
async def create_task(
    task: schemas.TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new task for a case"""
    service = TaskService(db)
    return await service.create_task(
        case_id=task.case_id,
        task_data=task.model_dump(exclude={"case_id"}),
        current_user=current_user,
    )


@router.get("/{task_id}", response_model=schemas.TaskResponse)
async def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific task by ID"""
    service = TaskService(db)
    return await service.get_task(task_id, current_user)


@router.put("/{task_id}", response_model=schemas.TaskResponse)
async def update_task(
    task_id: int,
    updates: schemas.TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a task"""
    service = TaskService(db)
    # Filter out None values to only update provided fields
    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    return await service.update_task(task_id, update_data, current_user)


@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a task (Admin only)"""
    service = TaskService(db)
    success = await service.delete_task(task_id, current_user)
    if success:
        return {"message": "Task deleted successfully"}
    raise HTTPException(status_code=500, detail="Failed to delete task")


# Task operation endpoints
@router.post("/{task_id}/assign", response_model=schemas.TaskResponse)
async def assign_task(
    task_id: int,
    user_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Assign or unassign a task to/from a user"""
    service = TaskService(db)
    return await service.assign_task(task_id, user_id, current_user)


@router.put("/{task_id}/status", response_model=schemas.TaskResponse)
async def update_task_status(
    task_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update task status"""
    service = TaskService(db)
    return await service.update_status(task_id, status, current_user)


# Bulk operation endpoints
@router.post("/bulk/assign", response_model=List[schemas.TaskResponse])
async def bulk_assign_tasks(
    data: schemas.BulkTaskAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bulk assign tasks to a user"""
    service = TaskService(db)
    return await service.bulk_assign(data.task_ids, data.user_id, current_user)


@router.post("/bulk/status", response_model=List[schemas.TaskResponse])
async def bulk_update_status(
    data: schemas.BulkTaskStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bulk update task status"""
    service = TaskService(db)
    return await service.bulk_update_status(data.task_ids, data.status, current_user)
