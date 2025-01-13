from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field
from .user_schema import User
from ..core.utils import get_utc_now


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
    users: list[User] = []
