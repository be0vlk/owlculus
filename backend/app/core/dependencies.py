"""
FastAPI dependency injection utilities and authentication middleware.

This module provides authentication dependencies, authorization decorators,
role-based access control, and case access validation utilities for the
FastAPI application. It handles JWT token validation and user permissions.
"""

from ipaddress import ip_address, ip_network
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select

from app.core import security
from app.core.config import settings
from app.core.exceptions import AuthenticationException
from app.database.connection import get_db as _get_db
from app.database.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")
optional_oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False
)


async def _resolve_current_user(db: Session, token: str) -> User:
    """Resolve and validate a bearer token into an active user."""
    credentials_exception = AuthenticationException("Could not validate credentials")
    identity, version = security.verify_access_token(token, credentials_exception)
    user = db.exec(
        select(User)
        .where(User.auth_identity == identity)
        .execution_options(populate_existing=True)
    ).first()
    if user is None or user.session_version != version:
        raise credentials_exception

    if not user.is_active:
        raise AuthenticationException("Inactive user")

    return user


def get_client_ip(request: Request) -> str:
    """Return a forwarded address only when the socket peer is trusted."""
    if not request.client:
        return "unknown"

    peer_address = request.client.host
    if not _is_trusted_proxy(peer_address):
        return peer_address

    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        forwarded_addresses = [
            address.strip() for address in forwarded_for.split(",") if address.strip()
        ]
        for forwarded_address in reversed(forwarded_addresses):
            normalized_address = _normalize_ip_address(forwarded_address)
            if normalized_address is None:
                return peer_address
            if not _is_trusted_proxy(normalized_address):
                return normalized_address
        if forwarded_addresses:
            return _normalize_ip_address(forwarded_addresses[0]) or peer_address

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return _normalize_ip_address(real_ip.strip()) or peer_address

    return peer_address


def _normalize_ip_address(address: str) -> str | None:
    try:
        return str(ip_address(address))
    except ValueError:
        return None


def _is_trusted_proxy(address: str) -> bool:
    normalized_address = _normalize_ip_address(address)
    if normalized_address is None:
        return False

    trusted_proxies = [
        proxy.strip()
        for proxy in settings.FORWARDED_ALLOW_IPS.split(",")
        if proxy.strip()
    ]
    if "*" in trusted_proxies:
        return True

    client_address = ip_address(normalized_address)
    for trusted_proxy in trusted_proxies:
        try:
            if client_address in ip_network(trusted_proxy, strict=False):
                return True
        except ValueError:
            continue

    return False


def get_user_agent(request: Request) -> str:
    user_agent = request.headers.get("User-Agent")
    return user_agent if user_agent else "unknown"


async def get_current_user(
    db: Annotated[Session, Depends(_get_db)],
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    return await _resolve_current_user(db, token)


async def get_optional_current_user(
    db: Annotated[Session, Depends(_get_db)],
    token: Annotated[str | None, Depends(optional_oauth2_scheme)],
) -> User | None:
    """Return no user when a bearer token is absent, while rejecting invalid tokens."""
    if token is None:
        return None
    return await _resolve_current_user(db, token)
