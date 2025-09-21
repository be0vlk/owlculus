"""
Task-related Pydantic schemas for request/response validation
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict

from .user_schema import User
from ..core.enums import TaskPriority, TaskStatus


# TaskTemplate Schemas
class TaskTemplateBase(BaseModel):
    name: str
    display_name: str
    description: str
    category: str
    is_active: bool = True
    definition_json: Dict[str, Any]


class TaskTemplateCreate(TaskTemplateBase):
    pass


class TaskTemplateUpdate(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None
    definition_json: Optional[Dict[str, Any]] = None


class TaskTemplateResponse(TaskTemplateBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    creator: Optional[User] = None


# Task Schemas
class TaskBase(BaseModel):
    title: str
    description: str
    priority: str = TaskPriority.MEDIUM.value
    template_id: Optional[int] = None
    assigned_to_id: Optional[int] = None
    due_date: Optional[datetime] = None
    custom_fields: Optional[Dict[str, Any]] = None


class TaskCreate(TaskBase):
    case_id: int


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    assigned_to_id: Optional[int] = None
    due_date: Optional[datetime] = None
    custom_fields: Optional[Dict[str, Any]] = None


class TaskResponse(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_id: int
    status: str = TaskStatus.NOT_STARTED.value
    assigned_by_id: int
    completed_at: Optional[datetime] = None
    completed_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    # Relationships
    template: Optional[TaskTemplateResponse] = None
    assigned_to: Optional[User] = None
    assigned_by: User
    completed_by: Optional[User] = None


# Bulk operation schemas
class BulkTaskAssign(BaseModel):
    task_ids: List[int]
    user_id: Optional[int] = None  # None to unassign


class BulkTaskStatusUpdate(BaseModel):
    task_ids: List[int]
    status: str


# Filter schemas
class TaskFilter(BaseModel):
    case_id: Optional[int] = None
    assigned_to_id: Optional[int] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    skip: int = 0
    limit: int = 100
