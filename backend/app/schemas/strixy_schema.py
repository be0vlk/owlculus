"""
Pydantic schemas for Strixy service data validation.

This module defines request and response models for Strixy OSINT service
integration, including chat message structures and conversation handling.
"""

from datetime import datetime
from typing import List, Literal

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]


class ChatResponse(BaseModel):
    message: str
    role: Literal["assistant"]
    timestamp: datetime
