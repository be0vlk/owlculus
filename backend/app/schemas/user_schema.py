from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from ..core.roles import UserRole
from ..core.utils import get_utc_now


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


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[Literal[UserRole.ADMIN, UserRole.INVESTIGATOR, UserRole.ANALYST]] = (
        None
    )
    is_active: Optional[bool] = None
    is_superadmin: Optional[bool] = None
    updated_at: datetime = Field(default_factory=get_utc_now)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class AdminPasswordReset(BaseModel):
    new_password: str


class User(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)
