"""Strixy schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class VisualInput(BaseModel):
    source_id: str
    field: str
    data: str


class ModelMessage(ChatMessage):
    """Internal provider input; never accepted as a client chat submission."""

    images: list[VisualInput]


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
    focus: list[str] = Field(default_factory=list, max_length=20)


class SourceQuery(BaseModel):
    model_config = {"extra": "forbid"}
    action: Literal["list", "search", "read"]
    source_id: str | None
    query: str | None = Field(max_length=200)


class SourceCitation(BaseModel):
    model_config = {"extra": "forbid"}
    source_id: str
    field: str
    excerpt: str


class GroundedAnswer(BaseModel):
    model_config = {"extra": "forbid"}
    content: str
    citations: list[SourceCitation]


class CreateShare(BaseModel):
    model_config = {"extra": "forbid"}
    through_message_id: str = Field(min_length=1, max_length=36)
