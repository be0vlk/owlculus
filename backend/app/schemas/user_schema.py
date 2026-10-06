"""User schemas."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr

from ..core.roles import UserRole


class UserBase(BaseModel):
    username: str
    email: EmailStr
    role: Literal[UserRole.ADMIN, UserRole.INVESTIGATOR, UserRole.ANALYST] = (
        UserRole.ANALYST
    )
    is_active: bool
    is_superadmin: bool = False


class UserCreate(UserBase):
    password: str


class BootstrapUserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    setup_token: str | None = None


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[Literal[UserRole.ADMIN, UserRole.INVESTIGATOR, UserRole.ANALYST]] = (
        None
    )
    is_active: Optional[bool] = None
    is_superadmin: Optional[bool] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class AdminPasswordReset(BaseModel):
    new_password: str


class User(UserBase):
    system_identity: str | None = None
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    created_at: datetime
    updated_at: datetime
