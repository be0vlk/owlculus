"""Authentication schemas."""

from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str


class WebSocketToken(BaseModel):
    token: str
    execution_id: int
    expires_in: int


class SetupStatus(BaseModel):
    setup_required: bool
