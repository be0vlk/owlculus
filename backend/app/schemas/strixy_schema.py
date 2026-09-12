"""
Pydantic schemas for Strixy service data validation.

This module defines request and response models for Strixy OSINT service
integration, including chat message structures and conversation handling.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    case_id: int = Field(gt=0)
    messages: list[ChatMessage]


class ChatResponse(BaseModel):
    message: str
    role: Literal["assistant"]
    timestamp: datetime


class SubmitMessage(BaseModel):
    model_config = {"extra": "forbid", "str_strip_whitespace": True}
    content: str = Field(min_length=1, max_length=16000)
