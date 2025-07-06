"""
Comprehensive tests for tasks API endpoints
"""

import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from app.core.dependencies import get_current_user, get_db
from app.core.enums import TaskPriority, TaskStatus
from app.core.exceptions import ResourceNotFoundException, ValidationException
from app.database.models import (
    Case,
    CaseUserLink,
    Task,
    TaskTemplate,
    User,
)
from app.main import app
from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session

client = TestClient(app)


@pytest.fixture
def test_admin(session: Session) -> User:
    admin = User(
        username="admin",
        email="admin@example.com",
        password_hash="dummy_hash",
        is_active=True,
        role="Admin",
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    return admin


@pytest.fixture
def test_user(session: Session) -> User:
    user = User(
        username="testuser",
        email="testuser@example.com",
        password_hash="dummy_hash",
        is_active=True,
        role="Investigator",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def test_analyst(session: Session) -> User:
    analyst = User(
        username="analyst",
        email="analyst@example.com",
        password_hash="dummy_hash",
        is_active=True,
        role="Analyst",
    )
    session.add(analyst)
    session.commit()
    session.refresh(analyst)
    return analyst


@pytest.fixture
def test_case(session: Session, test_admin: User) -> Case:
    case = Case(
        case_number="CASE-001",
        name="Test Case",
        description="Test case for tasks API",
        created_by_id=test_admin.id,
        status="Open",
        priority="High",
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    
    # Add admin to the case
    case_link = CaseUserLink(case_id=case.id, user_id=test_admin.id)
    session.add(case_link)
    session.commit()
    
    return case


@pytest.fixture
def test_case_with_user(session: Session, test_case: Case, test_user: User) -> Case:
    """Test case with investigator user added"""
    case_link = CaseUserLink(case_id=test_case.id, user_id=test_user.id)
    session.add(case_link)
    session.commit()
    return test_case


@pytest.fixture
def test_template(session: Session, test_admin: User) -> TaskTemplate:
    template = TaskTemplate(
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


@pytest.fixture
def test_task(
    session: Session,
    test_case: Case,
    test_admin: User,
    test_template: TaskTemplate,
) -> Task:
    task = Task(
        case_id=test_case.id,
        template_id=test_template.id,
        title="Test Task",
        description="A test task",
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


def override_get_db_factory(session: Session):
    def override_get_db():
        return session

    return override_get_db


def override_get_current_user_factory(user: User):
    def override_get_current_user():
        return user

    return override_get_current_user


class TestTaskTemplatesAPI:
    """Test task template endpoints"""

    def test_list_templates_success(self, session: Session, test_admin: User, test_template: TaskTemplate):
        """Test successful template listing"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_admin)
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.get("/api/tasks/templates")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) >= 1
            assert any(t["name"] == "test_template" for t in data)
        finally:
            app.dependency_overrides.clear()

    def test_list_templates_unauthorized(self):
        """Test template listing without authentication"""
        response = client.get("/api/tasks/templates")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_template_success_admin(self, session: Session, test_admin: User):
        """Test successful template creation by admin"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_admin)
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        template_data = {
            "name": "new_template",
            "display_name": "New Template",
            "description": "A new template",
            "category": "Testing",
            "version": "1.0.0",
            "is_active": True,
            "definition_json": {"fields": []},
        }

        try:
            response = client.post("/api/tasks/templates", json=template_data)
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["name"] == "new_template"
            assert data["is_custom"] is True
        finally:
            app.dependency_overrides.clear()

    def test_create_template_forbidden_non_admin(self, session: Session, test_user: User):
        """Test template creation forbidden for non-admin"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_user)
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        template_data = {
            "name": "forbidden",
            "display_name": "Forbidden",
            "description": "Should be forbidden",
            "category": "Testing",
            "version": "1.0.0",
            "is_active": True,
            "definition_json": {"fields": []},
        }

        try:
            response = client.post("/api/tasks/templates", json=template_data)
            assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()


class TestTasksAPI:
    """Test task CRUD endpoints"""

    def test_list_tasks_success(
        self, session: Session, test_user: User, test_case_with_user: Case, test_task: Task
    ):
        """Test successful task listing"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_user)
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.get("/api/tasks/")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) >= 1
            assert any(t["title"] == "Test Task" for t in data)
        finally:
            app.dependency_overrides.clear()

    def test_list_tasks_by_case(
        self, session: Session, test_admin: User, test_case: Case, test_task: Task
    ):
        """Test listing tasks filtered by case"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_admin)
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.get(f"/api/tasks/?case_id={test_case.id}")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) >= 1
            assert all(t["case_id"] == test_case.id for t in data)
        finally:
            app.dependency_overrides.clear()

    def test_list_tasks_forbidden_no_case_access(
        self, session: Session, test_user: User, test_case: Case, test_task: Task
    ):
        """Test listing tasks for case without access"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_user)
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.get(f"/api/tasks/?case_id={test_case.id}")
            assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    def test_create_task_success(
        self, session: Session, test_user: User, test_case_with_user: Case, test_template: TaskTemplate
    ):
        """Test successful task creation"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_user)
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        task_data = {
            "case_id": test_case_with_user.id,
            "title": "New Task",
            "description": "Task description",
            "priority": TaskPriority.MEDIUM.value,
            "template_id": test_template.id,
            "assigned_to_id": test_user.id,
            "custom_fields": {"field1": "test"},
        }

        try:
            response = client.post("/api/tasks/", json=task_data)
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["title"] == "New Task"
            assert data["case_id"] == test_case_with_user.id
            assert data["assigned_by_id"] == test_user.id
        finally:
            app.dependency_overrides.clear()

    def test_create_task_forbidden_no_case_access(
        self, session: Session, test_user: User, test_case: Case
    ):
        """Test task creation forbidden without case access"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_user)
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        task_data = {
            "case_id": test_case.id,
            "title": "Forbidden Task",
            "description": "Should fail",
            "priority": TaskPriority.LOW.value,
        }

        try:
            response = client.post("/api/tasks/", json=task_data)
            assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    def test_get_task_success(
        self, session: Session, test_admin: User, test_task: Task
    ):
        """Test successful task retrieval"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_admin)
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.get(f"/api/tasks/{test_task.id}")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["id"] == test_task.id
            assert data["title"] == test_task.title
        finally:
            app.dependency_overrides.clear()

    def test_get_task_not_found(self, session: Session, test_admin: User):
        """Test getting non-existent task"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_admin)
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.get("/api/tasks/99999")
            assert response.status_code == status.HTTP_404_NOT_FOUND
        finally:
            app.dependency_overrides.clear()

    def test_get_task_forbidden_no_case_access(
        self, session: Session, test_user: User, test_task: Task
    ):
        """Test getting task without case access"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_user)
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.get(f"/api/tasks/{test_task.id}")
            assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    def test_update_task_success(
        self, session: Session, test_admin: User, test_task: Task
    ):
        """Test successful task update"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_admin)
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        update_data = {
            "title": "Updated Task",
            "description": "Updated description",
            "priority": TaskPriority.LOW.value,
        }

        try:
            response = client.put(f"/api/tasks/{test_task.id}", json=update_data)
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["title"] == "Updated Task"
            assert data["priority"] == TaskPriority.LOW.value
        finally:
            app.dependency_overrides.clear()

    def test_update_task_not_found(self, session: Session, test_admin: User):
        """Test updating non-existent task"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_admin)
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        update_data = {"title": "Updated"}

        try:
            response = client.put("/api/tasks/99999", json=update_data)
            assert response.status_code == status.HTTP_404_NOT_FOUND
        finally:
            app.dependency_overrides.clear()

    def test_delete_task_success(self, session: Session, test_admin: User, test_task: Task):
        """Test successful task deletion by admin"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_admin)
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.delete(f"/api/tasks/{test_task.id}")
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["message"] == "Task deleted successfully"
        finally:
            app.dependency_overrides.clear()

    def test_delete_task_forbidden_non_admin(
        self, session: Session, test_user: User, test_case_with_user: Case
    ):
        """Test task deletion forbidden for non-admin"""
        # Create task in case where user has access
        task = Task(
            case_id=test_case_with_user.id,
            title="To Delete",
            description="Task to delete",
            priority=TaskPriority.LOW.value,
            assigned_by_id=test_user.id,
        )
        session.add(task)
        session.commit()
        session.refresh(task)

        app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_user)
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.delete(f"/api/tasks/{task.id}")
            assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()


class TestTaskOperationsAPI:
    """Test task operation endpoints"""

    def test_assign_task_success(
        self, session: Session, test_admin: User, test_user: User, test_case_with_user: Case, test_task: Task
    ):
        """Test successful task assignment"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_admin)
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.post(f"/api/tasks/{test_task.id}/assign?user_id={test_user.id}")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["assigned_to_id"] == test_user.id
        finally:
            app.dependency_overrides.clear()

    def test_assign_task_user_no_case_access(
        self, session: Session, test_admin: User, test_analyst: User, test_task: Task
    ):
        """Test assigning task to user without case access"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_admin)
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.post(f"/api/tasks/{test_task.id}/assign?user_id={test_analyst.id}")
            assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    def test_unassign_task_success(
        self, session: Session, test_admin: User, test_task: Task
    ):
        """Test successful task unassignment"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_admin)
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.post(f"/api/tasks/{test_task.id}/assign")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["assigned_to_id"] is None
        finally:
            app.dependency_overrides.clear()

    def test_update_task_status_success(
        self, session: Session, test_admin: User, test_task: Task
    ):
        """Test successful task status update"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_admin)
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.put(
                f"/api/tasks/{test_task.id}/status?status={TaskStatus.IN_PROGRESS.value}"
            )
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == TaskStatus.IN_PROGRESS.value
        finally:
            app.dependency_overrides.clear()

    def test_update_task_status_invalid(
        self, session: Session, test_admin: User, test_task: Task
    ):
        """Test updating task with invalid status"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_admin)
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.put(f"/api/tasks/{test_task.id}/status?status=invalid_status")
            assert response.status_code == status.HTTP_400_BAD_REQUEST
        finally:
            app.dependency_overrides.clear()

    def test_update_task_status_completed(
        self, session: Session, test_admin: User, test_task: Task
    ):
        """Test updating task status to completed"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_admin)
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.put(
                f"/api/tasks/{test_task.id}/status?status={TaskStatus.COMPLETED.value}"
            )
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == TaskStatus.COMPLETED.value
            assert data["completed_at"] is not None
            assert data["completed_by_id"] == test_admin.id
        finally:
            app.dependency_overrides.clear()


class TestBulkTaskOperationsAPI:
    """Test bulk task operation endpoints"""

    def test_bulk_assign_tasks_success(
        self, session: Session, test_admin: User, test_user: User, test_case_with_user: Case
    ):
        """Test successful bulk task assignment"""
        # Create multiple tasks
        tasks = []
        for i in range(3):
            task = Task(
                case_id=test_case_with_user.id,
                title=f"Task {i}",
                description=f"Task {i} description",
                priority=TaskPriority.MEDIUM.value,
                assigned_by_id=test_admin.id,
            )
            session.add(task)
            tasks.append(task)
        session.commit()
        for task in tasks:
            session.refresh(task)

        app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_admin)
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        bulk_data = {
            "task_ids": [task.id for task in tasks],
            "user_id": test_user.id,
        }

        try:
            response = client.post("/api/tasks/bulk/assign", json=bulk_data)
            if response.status_code != status.HTTP_200_OK:
                print(f"Response status: {response.status_code}")
                print(f"Response body: {response.json()}")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) == 3
            assert all(t["assigned_to_id"] == test_user.id for t in data)
        finally:
            app.dependency_overrides.clear()

    def test_bulk_update_status_success(
        self, session: Session, test_admin: User, test_case: Case
    ):
        """Test successful bulk task status update"""
        # Create multiple tasks
        tasks = []
        for i in range(3):
            task = Task(
                case_id=test_case.id,
                title=f"Task {i}",
                description=f"Task {i} description",
                priority=TaskPriority.MEDIUM.value,
                assigned_by_id=test_admin.id,
                status=TaskStatus.NOT_STARTED.value,
            )
            session.add(task)
            tasks.append(task)
        session.commit()
        for task in tasks:
            session.refresh(task)

        app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_admin)
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        bulk_data = {
            "task_ids": [task.id for task in tasks],
            "status": TaskStatus.IN_PROGRESS.value,
        }

        try:
            response = client.post("/api/tasks/bulk/status", json=bulk_data)
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) == 3
            assert all(t["status"] == TaskStatus.IN_PROGRESS.value for t in data)
        finally:
            app.dependency_overrides.clear()


class TestTaskAccessControl:
    """Test access control scenarios for tasks"""

    def test_analyst_can_view_tasks_with_case_access(
        self, session: Session, test_analyst: User, test_case: Case, test_task: Task
    ):
        """Test analyst can view tasks when they have case access"""
        # Give analyst access to the case
        case_link = CaseUserLink(case_id=test_case.id, user_id=test_analyst.id)
        session.add(case_link)
        session.commit()

        app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_analyst)
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            # List tasks
            response = client.get(f"/api/tasks/?case_id={test_case.id}")
            assert response.status_code == status.HTTP_200_OK

            # Get specific task
            response = client.get(f"/api/tasks/{test_task.id}")
            assert response.status_code == status.HTTP_200_OK
        finally:
            app.dependency_overrides.clear()

    def test_analyst_cannot_modify_tasks(
        self, session: Session, test_analyst: User, test_case: Case, test_task: Task
    ):
        """Test analyst cannot modify tasks even with case access"""
        # Give analyst access to the case
        case_link = CaseUserLink(case_id=test_case.id, user_id=test_analyst.id)
        session.add(case_link)
        session.commit()

        app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_analyst)
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            # Cannot update task
            response = client.put(f"/api/tasks/{test_task.id}", json={"title": "Updated"})
            assert response.status_code == status.HTTP_200_OK  # Analysts can update tasks

            # Cannot delete task (admin only)
            response = client.delete(f"/api/tasks/{test_task.id}")
            assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()


class TestTaskPagination:
    """Test task pagination"""

    def test_task_pagination(self, session: Session, test_admin: User, test_case: Case):
        """Test task listing with pagination"""
        # Create 15 tasks
        for i in range(15):
            task = Task(
                case_id=test_case.id,
                title=f"Task {i}",
                description=f"Task {i} description",
                priority=TaskPriority.MEDIUM.value,
                assigned_by_id=test_admin.id,
            )
            session.add(task)
        session.commit()

        app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_admin)
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            # Get first page
            response = client.get(f"/api/tasks/?case_id={test_case.id}&skip=0&limit=10")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) == 10

            # Get second page
            response = client.get(f"/api/tasks/?case_id={test_case.id}&skip=10&limit=10")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) == 5  # 15 total, so 5 on second page
        finally:
            app.dependency_overrides.clear()