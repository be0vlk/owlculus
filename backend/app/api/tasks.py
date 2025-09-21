"""
Task Management API for Owlculus OSINT Platform.

This module provides comprehensive task management capabilities for OSINT investigations,
enabling structured workflow coordination and team collaboration within cases.
"""

from typing import List

from app import schemas
from app.core.dependencies import (
	admin_only,
	check_case_access,
	get_current_user,
	is_case_lead,
)
from app.core.exceptions import (
	AuthorizationException,
	BaseException,
	ResourceNotFoundException,
	ValidationException,
)
from app.core.roles import UserRole
from app.database.connection import get_db
from app.database.models import User
from app.services.task_service import TaskService
from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlmodel import Session

router = APIRouter()


@router.get("/templates", response_model=List[schemas.TaskTemplateResponse])
async def list_templates(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TaskService(db)
    try:
        templates = await service.get_templates(
            include_inactive, current_user=current_user
        )
        return templates
    except BaseException as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/templates", response_model=schemas.TaskTemplateResponse)
@admin_only()
async def create_template(
    template: schemas.TaskTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TaskService(db)
    try:
        return await service.create_custom_template(
            template.model_dump(), current_user=current_user
        )
    except BaseException as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put("/templates/{template_id}", response_model=schemas.TaskTemplateResponse)
@admin_only()
async def update_template(
    template_id: int,
    updates: schemas.TaskTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TaskService(db)
    try:
        update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
        return await service.update_template(
            template_id, update_data, current_user=current_user
        )
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(e))
    except BaseException as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.delete("/templates/{template_id}")
@admin_only()
async def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TaskService(db)
    try:
        success = await service.delete_template(template_id, current_user=current_user)
        if success:
            return {"message": "Template deleted successfully"}
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(e))
    except BaseException as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/", response_model=List[schemas.TaskResponse])
async def list_tasks(
    filters: schemas.TaskFilter = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TaskService(db)
    if filters.case_id:
        try:
            check_case_access(db, filters.case_id, current_user)
        except AuthorizationException:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this case",
            )
        except ResourceNotFoundException as e:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND, detail=str(e)
            )

    try:
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
    except BaseException as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/", response_model=schemas.TaskResponse)
async def create_task(
    task: schemas.TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not is_case_lead(db, task.case_id, current_user):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Only admins or case leads can create tasks",
        )

    service = TaskService(db)
    try:
        return await service.create_task(
            case_id=task.case_id,
            task_data=task.model_dump(exclude={"case_id"}),
            current_user=current_user,
        )
    except BaseException as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/bulk/assign", response_model=List[schemas.TaskResponse])
async def bulk_assign_tasks(
    data: schemas.BulkTaskAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TaskService(db)
    try:
        return await service.bulk_assign(
            data.task_ids, data.user_id, current_user=current_user
        )
    except BaseException as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/bulk/status", response_model=List[schemas.TaskResponse])
async def bulk_update_status(
    data: schemas.BulkTaskStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TaskService(db)
    try:
        return await service.bulk_update_status(
            data.task_ids, data.status, current_user=current_user
        )
    except BaseException as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/{task_id}", response_model=schemas.TaskResponse)
async def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TaskService(db)
    try:
        task = await service.get_task(task_id, current_user=current_user)
        try:
            check_case_access(db, task.case_id, current_user)
        except AuthorizationException:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this case",
            )
        except ResourceNotFoundException as e:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND, detail=str(e)
            )
        return task
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(e))
    except BaseException as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put("/{task_id}", response_model=schemas.TaskResponse)
async def update_task(
    task_id: int,
    updates: schemas.TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TaskService(db)
    try:
        task = await service.get_task(task_id, current_user=current_user)
        check_case_access(db, task.case_id, current_user)
    except AuthorizationException:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this case",
        )
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(e))
    is_admin_or_lead = current_user.role == UserRole.ADMIN.value or is_case_lead(
        db, task.case_id, current_user
    )
    is_assignee = task.assigned_to_id == current_user.id

    if not is_admin_or_lead and not is_assignee:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Only admins, case leads, or the assigned user can update this task",
        )

    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    if is_assignee and not is_admin_or_lead:
        allowed_fields = {"status", "custom_fields"}
        restricted_updates = {
            k: v for k, v in update_data.items() if k in allowed_fields
        }

        if len(restricted_updates) != len(update_data):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Assigned users can only update status and custom fields",
            )

        update_data = restricted_updates

    try:
        return await service.update_task(
            task_id, update_data, current_user=current_user
        )
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(e))
    except BaseException as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.delete("/{task_id}")
@admin_only()
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TaskService(db)
    try:
        success = await service.delete_task(task_id, current_user=current_user)
        if success:
            return {"message": "Task deleted successfully"}
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(e))
    except BaseException as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/{task_id}/assign", response_model=schemas.TaskResponse)
async def assign_task(
    task_id: int,
    user_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TaskService(db)
    try:
        task = await service.get_task(task_id, current_user=current_user)

        if not is_case_lead(db, task.case_id, current_user):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Only admins or case leads can assign tasks",
            )
        if user_id:
            user = db.get(User, user_id)
            if user:
                check_case_access(db, task.case_id, user)
    except AuthorizationException:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this case",
        )
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(e))

    try:
        return await service.assign_task(task_id, user_id, current_user=current_user)
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(e))
    except BaseException as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put("/{task_id}/status", response_model=schemas.TaskResponse)
async def update_task_status(
    task_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TaskService(db)
    try:
        task = await service.get_task(task_id, current_user=current_user)
        check_case_access(db, task.case_id, current_user)
    except AuthorizationException:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this case",
        )
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(e))

    try:
        return await service.update_status(task_id, status, current_user=current_user)
    except ValidationException as e:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(e))
    except BaseException as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
