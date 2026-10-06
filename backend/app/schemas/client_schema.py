"""Client schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr

from .case_schema import Case


class ClientCreate(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class Client(ClientCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    cases: List[Case] = []
