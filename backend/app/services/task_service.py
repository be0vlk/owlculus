"""
Task service layer handling all task-related business logic
"""

from datetime import datetime
from typing import List, Optional

from app.core.dependencies import check_case_access
from app.core.enums import TaskStatus
from app.core.logging import get_security_logger
from app.database import models
from fastapi import HTTPException
from sqlmodel import Session, select


class TaskService:
    def __init__(self, db: Session):
        self.db = db

    # Template Management
    async def get_templates(
        self, include_inactive: bool = False, current_user: models.User = None
    ) -> List[models.TaskTemplate]:
        """Get all task templates"""
        query = select(models.TaskTemplate)
        if not include_inactive:
            query = query.where(models.TaskTemplate.is_active == True)

        templates = self.db.exec(query).all()
        return templates

    async def create_custom_template(
        self, template_data: dict, current_user: models.User
    ) -> models.TaskTemplate:
        """Create a custom task template (Admin only)"""
        template = models.TaskTemplate(
            **template_data, is_custom=True, created_by_id=current_user.id
        )
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)

        # Log the action
        logger = get_security_logger(
            admin_user_id=current_user.id,
            action="create_task_template",
            template_name=template.name,
            event_type="task_template_created",
        )
        logger.info(f"Custom task template '{template.name}' created")

        return template

    # Task CRUD Operations
    async def create_task(
        self, case_id: int, task_data: dict, current_user: models.User
    ) -> models.Task:
        """Create a new task for a case"""
        # Check case access
        check_case_access(self.db, case_id, current_user)

        # Create the task
        task = models.Task(case_id=case_id, assigned_by_id=current_user.id, **task_data)

        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        # Log the action
        logger = get_security_logger(
            user_id=current_user.id,
            action="create_task",
            case_id=case_id,
            task_id=task.id,
            event_type="task_created",
        )
        logger.info(f"Task '{task.title}' created for case {case_id}")

        return task

    async def get_tasks(
        self,
        current_user: models.User,
        case_id: Optional[int] = None,
        assigned_to_id: Optional[int] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[models.Task]:
        """Get tasks with filters"""
        query = select(models.Task)

        # Filter by case if specified
        if case_id:
            check_case_access(self.db, case_id, current_user)
            query = query.where(models.Task.case_id == case_id)
        else:
            # If no specific case, filter by cases user has access to
            if current_user.role != "Admin":
                user_cases = self.db.exec(
                    select(models.CaseUserLink.case_id).where(
                        models.CaseUserLink.user_id == current_user.id
                    )
                ).all()
                if user_cases:
                    query = query.where(models.Task.case_id.in_(user_cases))
                else:
                    return []  # User has no assigned cases

        # Apply other filters
        if assigned_to_id:
            query = query.where(models.Task.assigned_to_id == assigned_to_id)
        if status:
            query = query.where(models.Task.status == status)
        if priority:
            query = query.where(models.Task.priority == priority)

        # Apply pagination
        query = query.offset(skip).limit(limit)

        tasks = self.db.exec(query).all()
        return tasks

    async def get_task(self, task_id: int, current_user: models.User) -> models.Task:
        """Get a specific task by ID"""
        task = self.db.get(models.Task, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        # Check case access
        check_case_access(self.db, task.case_id, current_user)

        return task

    async def update_task(
        self, task_id: int, updates: dict, current_user: models.User
    ) -> models.Task:
        """Update a task"""
        task = await self.get_task(task_id, current_user)

        # Update fields
        for key, value in updates.items():
            if hasattr(task, key):
                setattr(task, key, value)

        task.updated_at = datetime.utcnow()

        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        # Log the action
        logger = get_security_logger(
            user_id=current_user.id,
            action="update_task",
            task_id=task_id,
            event_type="task_updated",
        )
        logger.info(f"Task {task_id} updated")

        return task

    async def delete_task(self, task_id: int, current_user: models.User) -> bool:
        """Delete a task (Admin only)"""
        task = await self.get_task(task_id, current_user)

        self.db.delete(task)
        self.db.commit()

        # Log the action
        logger = get_security_logger(
            admin_user_id=current_user.id,
            action="delete_task",
            task_id=task_id,
            event_type="task_deleted",
        )
        logger.info(f"Task {task_id} deleted")

        return True

    # Task Operations
    async def assign_task(
        self, task_id: int, user_id: Optional[int], current_user: models.User
    ) -> models.Task:
        """Assign or unassign a task to a user"""
        task = await self.get_task(task_id, current_user)

        # If assigning to someone, verify they have access to the case
        if user_id:
            user = self.db.get(models.User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            # Check if user has access to the case
            check_case_access(self.db, task.case_id, user)

        task.assigned_to_id = user_id
        task.updated_at = datetime.utcnow()

        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        # Log the action
        logger = get_security_logger(
            user_id=current_user.id,
            action="assign_task",
            task_id=task_id,
            assigned_to_id=user_id,
            event_type="task_assigned",
        )
        logger.info(f"Task {task_id} assigned to user {user_id}")

        return task

    async def update_status(
        self, task_id: int, status: str, current_user: models.User
    ) -> models.Task:
        """Update task status"""
        # Validate status
        if status not in [s.value for s in TaskStatus]:
            raise HTTPException(status_code=400, detail="Invalid status")

        task = await self.get_task(task_id, current_user)

        task.status = status
        task.updated_at = datetime.utcnow()

        # If marking as completed, set completion info
        if status == TaskStatus.COMPLETED.value:
            task.completed_at = datetime.utcnow()
            task.completed_by_id = current_user.id
        else:
            # If moving away from completed, clear completion info
            task.completed_at = None
            task.completed_by_id = None

        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        # Log the action
        logger = get_security_logger(
            user_id=current_user.id,
            action="update_task_status",
            task_id=task_id,
            new_status=status,
            event_type="task_status_updated",
        )
        logger.info(f"Task {task_id} status updated to {status}")

        return task

    async def bulk_assign(
        self, task_ids: List[int], user_id: Optional[int], current_user: models.User
    ) -> List[models.Task]:
        """Bulk assign tasks to a user"""
        updated_tasks = []

        for task_id in task_ids:
            try:
                task = await self.assign_task(task_id, user_id, current_user)
                updated_tasks.append(task)
            except HTTPException:
                # Skip tasks that can't be assigned (e.g., no access)
                continue

        return updated_tasks

    async def bulk_update_status(
        self, task_ids: List[int], status: str, current_user: models.User
    ) -> List[models.Task]:
        """Bulk update task status"""
        updated_tasks = []

        for task_id in task_ids:
            try:
                task = await self.update_status(task_id, status, current_user)
                updated_tasks.append(task)
            except HTTPException:
                # Skip tasks that can't be updated (e.g., no access)
                continue

        return updated_tasks
