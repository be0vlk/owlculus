"""
Pydantic schemas for authentication-related data validation.

This module defines request and response models for login, token generation,
and authentication data structures used throughout the application.
"""

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class WebSocketToken(BaseModel):
    token: str
    execution_id: int
    expires_in: int


class SetupStatus(BaseModel):
    setup_required: bool
