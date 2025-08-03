"""
Pydantic schemas for user data validation.

This module defines request and response models for user management,
profiles, authentication, password changes, and role-based access control.

Key features include:
- Role-based user validation with OSINT platform access levels
- User profile management with email validation and activity status
- Password change and admin reset functionality with security validation
- User creation and update schemas with timestamp tracking
- Comprehensive role enforcement for investigator, analyst, and admin access
"""

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
