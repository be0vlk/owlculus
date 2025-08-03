"""
Pydantic schemas for authentication-related data validation.

This module defines request and response models for login, token generation,
and authentication data structures used throughout the application.

Key features include:
- JWT token response models for secure API authentication
- Login request validation with username and password fields
- Authentication token type specification for Bearer token handling
- Standardized authentication data structures for OSINT platform security
- Simple and secure authentication schema design
"""

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
