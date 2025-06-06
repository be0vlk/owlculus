from pydantic import EmailStr
from sqlmodel import Field, SQLModel, Relationship
from typing import List, Optional
from datetime import datetime
from sqlalchemy import Column, JSON

from ..core.utils import get_utc_now


class CaseUserLink(SQLModel, table=True):
    case_id: Optional[int] = Field(
        default=None, foreign_key="case.id", primary_key=True
    )
    user_id: Optional[int] = Field(
        default=None, foreign_key="user.id", primary_key=True
    )


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: EmailStr = Field(index=True, unique=True)
    password_hash: str
    role: str = Field(default="Investigator")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)
    cases: List["Case"] = Relationship(back_populates="users", link_model=CaseUserLink)


class Invite(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    token: str = Field(unique=True)
    email: EmailStr
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
    parent_folder: Optional["Evidence"] = Relationship(back_populates="subfolders", sa_relationship_kwargs={"remote_side": "Evidence.id"})
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
