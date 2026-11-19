"""Case schemas."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

from .user_schema import User


class CaseUser(User):
    """User with case-specific information"""

    is_lead: bool = False


class CaseCreate(BaseModel):
    client_id: int
    title: str
    status: Literal["Open", "Closed"] = "Open"
    case_number: Optional[str] = None
    notes: Optional[str] = None


class CaseUpdate(BaseModel):
    client_id: Optional[int] = None
    title: Optional[str] = None
    status: Literal["Open", "Closed"] = "Open"
    case_number: Optional[str] = None
    notes: Optional[str] = None


class Case(CaseCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    users: list[CaseUser] = []


class CaseUserUpdate(BaseModel):
    """Schema for updating a user's case role"""

    is_lead: bool
