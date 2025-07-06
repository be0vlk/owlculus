from datetime import datetime
from typing import List, Optional

from pydantic import EmailStr
from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel

from ..core.enums import TaskPriority, TaskStatus
from ..core.utils import get_utc_now


class CaseUserLink(SQLModel, table=True):
    case_id: Optional[int] = Field(
        default=None, foreign_key="case.id", primary_key=True
    )
    user_id: Optional[int] = Field(
        default=None, foreign_key="user.id", primary_key=True
    )
    is_lead: bool = Field(default=False)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: EmailStr = Field(index=True, unique=True)
    password_hash: str
    role: str = Field(default="Investigator")
    is_active: bool = Field(default=True)
    is_superadmin: bool = Field(default=False)
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)
    cases: List["Case"] = Relationship(back_populates="users", link_model=CaseUserLink)


class Invite(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    token: str = Field(unique=True)
    role: str
    created_at: datetime = Field(default_factory=get_utc_now)
    expires_at: datetime
    used_at: Optional[datetime] = None
    created_by_id: int = Field(foreign_key="user.id")

    creator: "User" = Relationship()


class Client(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)
    cases: List["Case"] = Relationship(back_populates="client")


class Evidence(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="case.id")
    title: str
    description: Optional[str] = None
    evidence_type: str
    category: str = Field(default="Other")
    content: str
    file_hash: Optional[str] = Field(default=None, max_length=64)
    folder_path: Optional[str] = Field(default=None, max_length=500)
    is_folder: bool = Field(default=False)
    parent_folder_id: Optional[int] = Field(default=None, foreign_key="evidence.id")
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)
    created_by_id: int = Field(foreign_key="user.id")
    case: "Case" = Relationship(back_populates="evidence")
    creator: "User" = Relationship()
    parent_folder: Optional["Evidence"] = Relationship(
        back_populates="subfolders",
        sa_relationship_kwargs={"remote_side": "Evidence.id"},
    )
    subfolders: List["Evidence"] = Relationship(back_populates="parent_folder")


class Entity(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="case.id")
    entity_type: str = Field(index=True)
    data: dict = Field(sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)
    created_by_id: int = Field(foreign_key="user.id")

    case: "Case" = Relationship(back_populates="entities")
    creator: "User" = Relationship()


class SystemConfiguration(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    case_number_template: str = Field(default="YYMM-NN")
    case_number_prefix: Optional[str] = Field(default=None)
    api_keys: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    evidence_folder_templates: Optional[dict] = Field(
        default=None, sa_column=Column(JSON)
    )
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)


class Case(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: Optional[int] = Field(default=None, foreign_key="client.id")
    case_number: str
    title: Optional[str] = None
    status: str = Field(default="Open")
    notes: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)
    client: Optional[Client] = Relationship(back_populates="cases")
    users: List["User"] = Relationship(back_populates="cases", link_model=CaseUserLink)
    evidence: List["Evidence"] = Relationship(back_populates="case")
    entities: List["Entity"] = Relationship(back_populates="case")
    hunt_executions: List["HuntExecution"] = Relationship(back_populates="case")
    tasks: List["Task"] = Relationship(back_populates="case")


class Hunt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    display_name: str
    description: str
    category: str
    version: str = Field(default="1.0.0")
    definition_json: dict = Field(sa_column=Column(JSON))
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)

    executions: List["HuntExecution"] = Relationship(back_populates="hunt")


class HuntExecution(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hunt_id: int = Field(foreign_key="hunt.id")
    case_id: int = Field(foreign_key="case.id")
    status: str = Field(default="pending")
    progress: float = Field(default=0.0)
    initial_parameters: dict = Field(sa_column=Column(JSON))
    context_data: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=get_utc_now)
    created_by_id: int = Field(foreign_key="user.id")

    hunt: Hunt = Relationship(back_populates="executions")
    case: Case = Relationship(back_populates="hunt_executions")
    creator: User = Relationship()
    steps: List["HuntStep"] = Relationship(back_populates="execution")


class HuntStep(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    execution_id: int = Field(foreign_key="huntexecution.id")
    step_id: str
    plugin_name: str
    status: str = Field(default="pending")
    parameters: dict = Field(sa_column=Column(JSON))
    output: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    error_details: Optional[str] = None
    retry_count: int = Field(default=0)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    execution: HuntExecution = Relationship(back_populates="steps")


class TaskTemplate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    display_name: str
    description: str
    category: str
    is_active: bool = Field(default=True)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    definition_json: dict = Field(sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)

    creator: Optional[User] = Relationship()
    tasks: List["Task"] = Relationship(back_populates="template")


class Task(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="case.id")
    template_id: Optional[int] = Field(default=None, foreign_key="tasktemplate.id")
    title: str
    description: str
    priority: str = Field(default=TaskPriority.MEDIUM.value)
    status: str = Field(default=TaskStatus.NOT_STARTED.value)
    assigned_to_id: Optional[int] = Field(default=None, foreign_key="user.id")
    assigned_by_id: int = Field(foreign_key="user.id")
    due_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    completed_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    custom_fields: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)

    case: Case = Relationship(back_populates="tasks")
    template: Optional[TaskTemplate] = Relationship(back_populates="tasks")
    assigned_to: Optional[User] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Task.assigned_to_id]"}
    )
    assigned_by: User = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Task.assigned_by_id]"}
    )
    completed_by: Optional[User] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Task.completed_by_id]"}
    )
