from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, EmailStr, ConfigDict, Field
from ..core.utils import get_utc_now


class UserBase(BaseModel):
    username: str
    email: EmailStr
    role: Literal["Admin", "Investigator", "Analyst"] = "Analyst"
    is_active: bool


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[Literal["Admin", "Investigator", "Analyst"]] = None
    is_active: Optional[bool] = None
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
