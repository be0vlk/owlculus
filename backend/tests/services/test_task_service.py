"""
Comprehensive tests for TaskService
"""

from datetime import datetime, timedelta

import pytest
from app.core.enums import TaskPriority, TaskStatus
from app.database import models
from app.services.task_service import TaskService
from fastapi import HTTPException
from sqlmodel import Session


@pytest.fixture(name="task_service")
def task_service_fixture(session: Session):
    """Create TaskService instance"""
    return TaskService(session)


@pytest.fixture(name="task_template")
def task_template_fixture(session: Session, test_admin: models.User):
    """Create a test task template"""
    template = models.TaskTemplate(
        name="test_template",
        display_name="Test Template",
        description="A test task template",
        category="Testing",
        version="1.0.0",
        is_active=True,
        is_custom=True,
        created_by_id=test_admin.id,
        definition_json={
            "fields": [
                {"name": "field1", "type": "string", "required": True},
                {"name": "field2", "type": "number", "required": False},
            ]
        },
    )
    session.add(template)
    session.commit()
    session.refresh(template)
    return template


@pytest.fixture(name="inactive_template")
def inactive_template_fixture(session: Session):
    """Create an inactive task template"""
    template = models.TaskTemplate(
        name="inactive_template",
        display_name="Inactive Template",
        description="An inactive template",
        category="Testing",
        version="1.0.0",
        is_active=False,
        is_custom=False,
        definition_json={},
    )
    session.add(template)
    session.commit()
    session.refresh(template)
    return template


@pytest.fixture(name="sample_task")
def sample_task_fixture(
    session: Session,
    test_case: models.Case,
    test_admin: models.User,
    task_template: models.TaskTemplate,
):
    """Create a sample task"""
    task = models.Task(
        case_id=test_case.id,
        template_id=task_template.id,
        title="Test Task",
        description="A test task description",
        priority=TaskPriority.HIGH.value,
        status=TaskStatus.NOT_STARTED.value,
        assigned_to_id=test_admin.id,
        assigned_by_id=test_admin.id,
        due_date=datetime.utcnow() + timedelta(days=7),
        custom_fields={"field1": "value1", "field2": 42},
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@pytest.fixture(name="multiple_tasks")
def multiple_tasks_fixture(
    session: Session,
    test_case: models.Case,
    test_admin: models.User,
    test_investigator: models.User,
):
    """Create multiple tasks with different statuses and priorities"""
    tasks = []
    
    # Task 1: High priority, not started
    task1 = models.Task(
        case_id=test_case.id,
        title="High Priority Task",
        description="Urgent task",
        priority=TaskPriority.HIGH.value,
        status=TaskStatus.NOT_STARTED.value,
        assigned_to_id=test_admin.id,
        assigned_by_id=test_admin.id,
    )
    tasks.append(task1)
    
    # Task 2: Medium priority, in progress
    task2 = models.Task(
        case_id=test_case.id,
        title="In Progress Task",
        description="Working on it",
        priority=TaskPriority.MEDIUM.value,
        status=TaskStatus.IN_PROGRESS.value,
        assigned_to_id=test_investigator.id,
        assigned_by_id=test_admin.id,
    )
    tasks.append(task2)
    
    # Task 3: Low priority, completed
    task3 = models.Task(
        case_id=test_case.id,
        title="Completed Task",
        description="Done",
        priority=TaskPriority.LOW.value,
        status=TaskStatus.COMPLETED.value,
        assigned_to_id=test_investigator.id,
        assigned_by_id=test_admin.id,
        completed_at=datetime.utcnow(),
        completed_by_id=test_investigator.id,
    )
    tasks.append(task3)
    
    # Task 4: Blocked task
    task4 = models.Task(
        case_id=test_case.id,
        title="Blocked Task",
        description="Waiting for dependencies",
        priority=TaskPriority.HIGH.value,
        status=TaskStatus.BLOCKED.value,
        assigned_by_id=test_admin.id,
    )
    tasks.append(task4)
    
    for task in tasks:
        session.add(task)
    session.commit()
    
    for task in tasks:
        session.refresh(task)
    
    return tasks


class TestTaskTemplateOperations:
    """Test task template operations"""
    
    @pytest.mark.asyncio
    async def test_get_templates_all(
        self, task_service: TaskService, task_template: models.TaskTemplate,
        inactive_template: models.TaskTemplate, test_admin: models.User
    ):
        """Test getting all templates including inactive ones"""
        templates = await task_service.get_templates(
            include_inactive=True, current_user=test_admin
        )
        assert len(templates) == 2
        assert task_template in templates
        assert inactive_template in templates
    
    @pytest.mark.asyncio
    async def test_get_templates_active_only(
        self, task_service: TaskService, task_template: models.TaskTemplate,
        inactive_template: models.TaskTemplate, test_admin: models.User
    ):
        """Test getting only active templates"""
        templates = await task_service.get_templates(
            include_inactive=False, current_user=test_admin
        )
        assert len(templates) == 1
        assert task_template in templates
        assert inactive_template not in templates
    
    @pytest.mark.asyncio
    async def test_create_custom_template(
        self, task_service: TaskService, test_admin: models.User
    ):
        """Test creating a custom template"""
        template_data = {
            "name": "custom_test",
            "display_name": "Custom Test Template",
            "description": "A custom template for testing",
            "category": "Custom",
            "version": "2.0.0",
            "is_active": True,
            "definition_json": {"fields": []},
        }
        
        template = await task_service.create_custom_template(
            template_data, test_admin
        )
        
        assert template.name == "custom_test"
        assert template.display_name == "Custom Test Template"
        assert template.is_custom is True
        assert template.created_by_id == test_admin.id
        assert template.version == "2.0.0"


class TestTaskCRUDOperations:
    """Test basic task CRUD operations"""
    
    @pytest.mark.asyncio
    async def test_create_task(
        self, task_service: TaskService, test_case: models.Case,
        test_admin: models.User, task_template: models.TaskTemplate
    ):
        """Test creating a new task"""
        # Ensure admin is assigned to the case
        case_link = models.CaseUserLink(case_id=test_case.id, user_id=test_admin.id)
        task_service.db.add(case_link)
        task_service.db.commit()
        
        task_data = {
            "title": "New Test Task",
            "description": "Testing task creation",
            "priority": TaskPriority.HIGH.value,
            "template_id": task_template.id,
            "assigned_to_id": test_admin.id,
            "due_date": datetime.utcnow() + timedelta(days=3),
            "custom_fields": {"field1": "test"},
        }
        
        task = await task_service.create_task(
            test_case.id, task_data, test_admin
        )
        
        assert task.title == "New Test Task"
        assert task.case_id == test_case.id
        assert task.priority == TaskPriority.HIGH.value
        assert task.assigned_to_id == test_admin.id
        assert task.assigned_by_id == test_admin.id
        assert task.status == TaskStatus.NOT_STARTED.value
    
    @pytest.mark.asyncio
    async def test_create_task_no_access(
        self, task_service: TaskService, test_case: models.Case,
        test_investigator: models.User
    ):
        """Test creating task without case access"""
        task_data = {
            "title": "Unauthorized Task",
            "description": "Should fail",
            "priority": TaskPriority.LOW.value,
        }
        
        with pytest.raises(HTTPException) as exc_info:
            await task_service.create_task(
                test_case.id, task_data, test_investigator
            )
        assert exc_info.value.status_code == 403
    
    @pytest.mark.asyncio
    async def test_get_task(
        self, task_service: TaskService, sample_task: models.Task,
        test_admin: models.User
    ):
        """Test getting a specific task"""
        task = await task_service.get_task(sample_task.id, test_admin)
        assert task.id == sample_task.id
        assert task.title == sample_task.title
    
    @pytest.mark.asyncio
    async def test_get_task_not_found(
        self, task_service: TaskService, test_admin: models.User
    ):
        """Test getting non-existent task"""
        with pytest.raises(HTTPException) as exc_info:
            await task_service.get_task(99999, test_admin)
        assert exc_info.value.status_code == 404
    
    @pytest.mark.asyncio
    async def test_update_task(
        self, task_service: TaskService, sample_task: models.Task,
        test_admin: models.User
    ):
        """Test updating a task"""
        updates = {
            "title": "Updated Task Title",
            "description": "Updated description",
            "priority": TaskPriority.HIGH.value,
        }
        
        updated_task = await task_service.update_task(
            sample_task.id, updates, test_admin
        )
        
        assert updated_task.title == "Updated Task Title"
        assert updated_task.description == "Updated description"
        assert updated_task.priority == TaskPriority.HIGH.value
        # The updated_at should be changed
        assert updated_task.updated_at is not None
    
    @pytest.mark.asyncio
    async def test_delete_task(
        self, task_service: TaskService, sample_task: models.Task,
        test_admin: models.User
    ):
        """Test deleting a task"""
        result = await task_service.delete_task(sample_task.id, test_admin)
        assert result is True
        
        # Verify task is deleted
        deleted_task = task_service.db.get(models.Task, sample_task.id)
        assert deleted_task is None


class TestTaskFiltering:
    """Test task filtering and querying"""
    
    @pytest.mark.asyncio
    async def test_get_tasks_by_case(
        self, task_service: TaskService, test_case: models.Case,
        multiple_tasks: list, test_admin: models.User
    ):
        """Test getting tasks filtered by case"""
        tasks = await task_service.get_tasks(
            current_user=test_admin,
            case_id=test_case.id
        )
        assert len(tasks) == 4
    
    @pytest.mark.asyncio
    async def test_get_tasks_by_assignee(
        self, task_service: TaskService, multiple_tasks: list,
        test_admin: models.User, test_investigator: models.User
    ):
        """Test getting tasks filtered by assignee"""
        tasks = await task_service.get_tasks(
            current_user=test_admin,
            assigned_to_id=test_investigator.id
        )
        assert len(tasks) == 2
        for task in tasks:
            assert task.assigned_to_id == test_investigator.id
    
    @pytest.mark.asyncio
    async def test_get_tasks_by_status(
        self, task_service: TaskService, multiple_tasks: list,
        test_admin: models.User
    ):
        """Test getting tasks filtered by status"""
        # Get completed tasks
        tasks = await task_service.get_tasks(
            current_user=test_admin,
            status=TaskStatus.COMPLETED.value
        )
        assert len(tasks) == 1
        assert tasks[0].status == TaskStatus.COMPLETED.value
        
        # Get in-progress tasks
        tasks = await task_service.get_tasks(
            current_user=test_admin,
            status=TaskStatus.IN_PROGRESS.value
        )
        assert len(tasks) == 1
        assert tasks[0].status == TaskStatus.IN_PROGRESS.value
    
    @pytest.mark.asyncio
    async def test_get_tasks_by_priority(
        self, task_service: TaskService, multiple_tasks: list,
        test_admin: models.User
    ):
        """Test getting tasks filtered by priority"""
        tasks = await task_service.get_tasks(
            current_user=test_admin,
            priority=TaskPriority.HIGH.value
        )
        assert len(tasks) == 2
        for task in tasks:
            assert task.priority == TaskPriority.HIGH.value
    
    @pytest.mark.asyncio
    async def test_get_tasks_pagination(
        self, task_service: TaskService, multiple_tasks: list,
        test_admin: models.User
    ):
        """Test task pagination"""
        # Get first 2 tasks
        tasks = await task_service.get_tasks(
            current_user=test_admin,
            skip=0,
            limit=2
        )
        assert len(tasks) == 2
        
        # Get next 2 tasks
        tasks = await task_service.get_tasks(
            current_user=test_admin,
            skip=2,
            limit=2
        )
        assert len(tasks) == 2
    
    @pytest.mark.asyncio
    async def test_get_tasks_non_admin_no_case_access(
        self, task_service: TaskService, multiple_tasks: list,
        test_analyst: models.User
    ):
        """Test non-admin user with no case access gets no tasks"""
        tasks = await task_service.get_tasks(current_user=test_analyst)
        assert len(tasks) == 0


class TestTaskAssignment:
    """Test task assignment operations"""
    
    @pytest.mark.asyncio
    async def test_assign_task(
        self, task_service: TaskService, sample_task: models.Task,
        test_admin: models.User, test_investigator: models.User
    ):
        """Test assigning a task to a user"""
        # First ensure investigator has access to the case
        case_link = models.CaseUserLink(
            case_id=sample_task.case_id,
            user_id=test_investigator.id
        )
        task_service.db.add(case_link)
        task_service.db.commit()
        
        task = await task_service.assign_task(
            sample_task.id, test_investigator.id, test_admin
        )
        
        assert task.assigned_to_id == test_investigator.id
    
    @pytest.mark.asyncio
    async def test_unassign_task(
        self, task_service: TaskService, sample_task: models.Task,
        test_admin: models.User
    ):
        """Test unassigning a task"""
        task = await task_service.assign_task(
            sample_task.id, None, test_admin
        )
        assert task.assigned_to_id is None
    
    @pytest.mark.asyncio
    async def test_assign_task_user_no_case_access(
        self, task_service: TaskService, sample_task: models.Task,
        test_admin: models.User, test_analyst: models.User
    ):
        """Test assigning task to user without case access"""
        with pytest.raises(HTTPException) as exc_info:
            await task_service.assign_task(
                sample_task.id, test_analyst.id, test_admin
            )
        assert exc_info.value.status_code == 403
    
    @pytest.mark.asyncio
    async def test_bulk_assign_tasks(
        self, task_service: TaskService, multiple_tasks: list,
        test_admin: models.User, test_investigator: models.User
    ):
        """Test bulk assigning tasks"""
        # Ensure investigator has case access
        case_link = models.CaseUserLink(
            case_id=multiple_tasks[0].case_id,
            user_id=test_investigator.id
        )
        task_service.db.add(case_link)
        task_service.db.commit()
        
        task_ids = [task.id for task in multiple_tasks[:3]]
        updated_tasks = await task_service.bulk_assign(
            task_ids, test_investigator.id, test_admin
        )
        
        assert len(updated_tasks) == 3
        for task in updated_tasks:
            assert task.assigned_to_id == test_investigator.id


class TestTaskStatusOperations:
    """Test task status update operations"""
    
    @pytest.mark.asyncio
    async def test_update_status_to_completed(
        self, task_service: TaskService, sample_task: models.Task,
        test_admin: models.User
    ):
        """Test updating task status to completed"""
        task = await task_service.update_status(
            sample_task.id, TaskStatus.COMPLETED.value, test_admin
        )
        
        assert task.status == TaskStatus.COMPLETED.value
        assert task.completed_at is not None
        assert task.completed_by_id == test_admin.id
    
    @pytest.mark.asyncio
    async def test_update_status_from_completed(
        self, task_service: TaskService, test_case: models.Case,
        test_admin: models.User
    ):
        """Test moving task away from completed status"""
        # Create a completed task
        task = models.Task(
            case_id=test_case.id,
            title="Completed Task",
            description="Was completed",
            priority=TaskPriority.MEDIUM.value,
            status=TaskStatus.COMPLETED.value,
            assigned_by_id=test_admin.id,
            completed_at=datetime.utcnow(),
            completed_by_id=test_admin.id,
        )
        task_service.db.add(task)
        task_service.db.commit()
        task_service.db.refresh(task)
        
        # Move to in-progress
        updated_task = await task_service.update_status(
            task.id, TaskStatus.IN_PROGRESS.value, test_admin
        )
        
        assert updated_task.status == TaskStatus.IN_PROGRESS.value
        assert updated_task.completed_at is None
        assert updated_task.completed_by_id is None
    
    @pytest.mark.asyncio
    async def test_update_status_invalid(
        self, task_service: TaskService, sample_task: models.Task,
        test_admin: models.User
    ):
        """Test updating task with invalid status"""
        with pytest.raises(HTTPException) as exc_info:
            await task_service.update_status(
                sample_task.id, "invalid_status", test_admin
            )
        assert exc_info.value.status_code == 400
    
    @pytest.mark.asyncio
    async def test_bulk_update_status(
        self, task_service: TaskService, multiple_tasks: list,
        test_admin: models.User
    ):
        """Test bulk updating task status"""
        # Get tasks that are not completed
        task_ids = [
            task.id for task in multiple_tasks
            if task.status != TaskStatus.COMPLETED.value
        ][:2]
        
        updated_tasks = await task_service.bulk_update_status(
            task_ids, TaskStatus.IN_PROGRESS.value, test_admin
        )
        
        assert len(updated_tasks) == 2
        for task in updated_tasks:
            assert task.status == TaskStatus.IN_PROGRESS.value


class TestTaskAccessControl:
    """Test access control for task operations"""
    
    @pytest.mark.asyncio
    async def test_analyst_read_access(
        self, task_service: TaskService, sample_task: models.Task,
        test_analyst: models.User
    ):
        """Test analyst can read tasks they have access to"""
        # Give analyst access to the case
        case_link = models.CaseUserLink(
            case_id=sample_task.case_id,
            user_id=test_analyst.id
        )
        task_service.db.add(case_link)
        task_service.db.commit()
        
        task = await task_service.get_task(sample_task.id, test_analyst)
        assert task.id == sample_task.id
    
    @pytest.mark.asyncio
    async def test_investigator_full_access(
        self, task_service: TaskService, test_case: models.Case,
        test_investigator: models.User
    ):
        """Test investigator can create and modify tasks"""
        # Give investigator access to the case
        case_link = models.CaseUserLink(
            case_id=test_case.id,
            user_id=test_investigator.id
        )
        task_service.db.add(case_link)
        task_service.db.commit()
        
        # Create task
        task_data = {
            "title": "Investigator Task",
            "description": "Created by investigator",
            "priority": TaskPriority.MEDIUM.value,
        }
        
        task = await task_service.create_task(
            test_case.id, task_data, test_investigator
        )
        assert task.assigned_by_id == test_investigator.id
        
        # Update task
        updates = {"title": "Updated by Investigator"}
        updated_task = await task_service.update_task(
            task.id, updates, test_investigator
        )
        assert updated_task.title == "Updated by Investigator"


class TestTaskWithCustomFields:
    """Test tasks with custom fields from templates"""
    
    @pytest.mark.asyncio
    async def test_create_task_with_custom_fields(
        self, task_service: TaskService, test_case: models.Case,
        test_admin: models.User, task_template: models.TaskTemplate
    ):
        """Test creating task with custom fields from template"""
        # Ensure admin has case access
        case_link = models.CaseUserLink(case_id=test_case.id, user_id=test_admin.id)
        task_service.db.add(case_link)
        task_service.db.commit()
        
        task_data = {
            "title": "Task with Custom Fields",
            "description": "Testing custom fields",
            "priority": TaskPriority.MEDIUM.value,
            "template_id": task_template.id,
            "custom_fields": {
                "field1": "custom value",
                "field2": 123,
                "extra_field": "not in template"
            }
        }
        
        task = await task_service.create_task(
            test_case.id, task_data, test_admin
        )
        
        assert task.template_id == task_template.id
        assert task.custom_fields["field1"] == "custom value"
        assert task.custom_fields["field2"] == 123
        assert task.custom_fields["extra_field"] == "not in template"
    
    @pytest.mark.asyncio
    async def test_update_custom_fields(
        self, task_service: TaskService, sample_task: models.Task,
        test_admin: models.User
    ):
        """Test updating custom fields in a task"""
        updates = {
            "custom_fields": {
                "field1": "updated value",
                "field3": "new field"
            }
        }
        
        updated_task = await task_service.update_task(
            sample_task.id, updates, test_admin
        )
        
        assert updated_task.custom_fields["field1"] == "updated value"
        assert updated_task.custom_fields["field3"] == "new field"


class TestTaskDueDates:
    """Test task due date handling"""
    
    @pytest.mark.asyncio
    async def test_create_task_with_due_date(
        self, task_service: TaskService, test_case: models.Case,
        test_admin: models.User
    ):
        """Test creating task with due date"""
        # Ensure admin has case access
        case_link = models.CaseUserLink(case_id=test_case.id, user_id=test_admin.id)
        task_service.db.add(case_link)
        task_service.db.commit()
        
        due_date = datetime.utcnow() + timedelta(days=5)
        task_data = {
            "title": "Task with Due Date",
            "description": "Has a deadline",
            "priority": TaskPriority.HIGH.value,
            "due_date": due_date,
        }
        
        task = await task_service.create_task(
            test_case.id, task_data, test_admin
        )
        
        assert task.due_date is not None
        assert abs((task.due_date - due_date).total_seconds()) < 1
    
    @pytest.mark.asyncio
    async def test_update_due_date(
        self, task_service: TaskService, sample_task: models.Task,
        test_admin: models.User
    ):
        """Test updating task due date"""
        new_due_date = datetime.utcnow() + timedelta(days=10)
        updates = {"due_date": new_due_date}
        
        updated_task = await task_service.update_task(
            sample_task.id, updates, test_admin
        )
        
        assert updated_task.due_date is not None
        assert abs((updated_task.due_date - new_due_date).total_seconds()) < 1