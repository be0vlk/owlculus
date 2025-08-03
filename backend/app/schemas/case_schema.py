"""
Pydantic schemas for case management data validation.

This module defines request and response models for case creation, updates,
retrieval, and user assignment functionality including case lead management.

Key features include:
- OSINT case lifecycle management with status tracking
- Case-user assignment models with lead investigator designation
- Comprehensive case metadata validation including client associations
- Flexible case updates with timestamp tracking
- Role-based case access control and user management
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .user_schema import User
from ..core.utils import get_utc_now


class CaseUser(User):
    """User with case-specific information"""

    is_lead: bool = False


class CaseBase(BaseModel):
    client_id: int
    title: str
    status: Literal["Open", "Closed"] = "Open"
    case_number: Optional[str] = None
    notes: Optional[str] = None


class CaseOptional(BaseModel):
    client_id: Optional[int] = None
    title: Optional[str] = None
    status: Literal["Open", "Closed"] = "Open"
    case_number: Optional[str] = None
    notes: Optional[str] = None


class CaseCreate(CaseBase):
    pass


class CaseUpdate(CaseOptional):
    updated_at: datetime = Field(default_factory=get_utc_now)


class Case(CaseBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)
    users: list[CaseUser] = []


class CaseUserAdd(BaseModel):
    """Schema for adding a user to a case"""

    user_id: int
    is_lead: bool = False


class CaseUserUpdate(BaseModel):
    """Schema for updating a user's case role"""

    is_lead: bool
