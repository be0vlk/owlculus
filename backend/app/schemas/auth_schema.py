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
