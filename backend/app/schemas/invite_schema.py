from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, Literal
from datetime import datetime


class InviteCreate(BaseModel):
    role: Literal["Admin", "Investigator", "Analyst"]


class InviteResponse(BaseModel):
    id: int
    token: str
    role: str
    created_at: datetime
    expires_at: datetime
    used_at: Optional[datetime] = None
    created_by_id: int

    class Config:
        from_attributes = True


class InviteListResponse(BaseModel):
    id: int
    role: str
    created_at: datetime
    expires_at: datetime
    used_at: Optional[datetime] = None
    is_expired: bool
    is_used: bool

    class Config:
        from_attributes = True


class InviteValidation(BaseModel):
    valid: bool
    role: Optional[str] = None
    expires_at: Optional[datetime] = None
    error: Optional[str] = None


class UserRegistration(BaseModel):
    username: str
    email: EmailStr
    password: str
    token: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v):
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters long")
        if len(v) > 50:
            raise ValueError("Username must be less than 50 characters long")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v


class UserRegistrationResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: str
    created_at: datetime

    class Config:
        from_attributes = True
