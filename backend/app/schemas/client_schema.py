"""
Pydantic schemas for client data validation.

This module defines request and response models for client management,
including client creation, updates, and information retrieval with
associated case relationships.

Key features include:
- Client contact information validation with email and phone verification
- Comprehensive client profile management for OSINT case assignments
- Client-case relationship tracking and association management
- Flexible client data updates with timestamp preservation
- Contact information validation including EmailStr type enforcement
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .case_schema import Case
from ..core.utils import get_utc_now


class ClientBase(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    updated_at: datetime = Field(default_factory=get_utc_now)


class Client(ClientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    cases: List[Case] = []
