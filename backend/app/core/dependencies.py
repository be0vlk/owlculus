"""
FastAPI dependency injection utilities and authentication middleware.

This module provides authentication dependencies, authorization decorators,
role-based access control, and case access validation utilities for the
FastAPI application. It handles JWT token validation and user permissions.
"""

from functools import wraps
from ipaddress import ip_address, ip_network

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select

from app.core import security
from app.core.config import settings
from app.core.exceptions import (
    AuthenticationException,
    AuthorizationException,
    ResourceNotFoundException,
)
from app.core.roles import UserRole
from app.database import crud
from app.database.connection import get_db
from app.database.models import Case, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")
optional_oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False
)


async def _resolve_current_user(db: Session, token: str) -> User:
    """Resolve and validate a bearer token into an active user."""
    credentials_exception = AuthenticationException("Could not validate credentials")
    username = security.verify_access_token(token, credentials_exception)
    user = await crud.get_user_by_username(db, username=username)
    if user is None:
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
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    return await _resolve_current_user(db, token)


async def get_optional_current_user(
    db: Session = Depends(get_db),
    token: str | None = Depends(optional_oauth2_scheme),
) -> User | None:
    """Return no user when a bearer token is absent, while rejecting invalid tokens."""
    if token is None:
        return None
    return await _resolve_current_user(db, token)


# async def get_current_active_user(
#     current_user: User = Depends(get_current_user),
# ) -> User:
#     if not current_user.is_active:
#         raise HTTPException(status_code=400, detail="Inactive user")
#     return current_user


def authorize(func):
    """Base decorator to check user authorization."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        current_user = kwargs.get("current_user")
        if not current_user:
            raise Exception("Current user not found in arguments")
        return await func(*args, **kwargs)

    return wrapper


def admin_only():
    """Decorator to check if user has Admin role."""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            if not current_user:
                raise AuthenticationException("Not authorized")

            if current_user.role != UserRole.ADMIN.value:
                raise AuthorizationException("Not authorized")
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def no_analyst(*, domain_exceptions: bool = True):
    """Decorator to check if user is not an analyst"""

    def decorator(func):
        import inspect

        signature = inspect.signature(func)

        def _check_analyst_permission(current_user):
            if not current_user:
                raise AuthenticationException("Not authorized")
            if current_user.role == UserRole.ANALYST.value:
                raise AuthorizationException("Not authorized")

        def _get_bound_current_user(args, kwargs):
            return signature.bind(*args, **kwargs).arguments.get("current_user")

        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                current_user = _get_bound_current_user(args, kwargs)
                _check_analyst_permission(current_user)
                return await func(*args, **kwargs)

            return async_wrapper
        else:

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                current_user = _get_bound_current_user(args, kwargs)
                _check_analyst_permission(current_user)
                return func(*args, **kwargs)

            return sync_wrapper

    return decorator


def case_must_be_open():
    """Decorator to check if a case is open before allowing operations."""

    def decorator(func):
        @wraps(func)
        async def wrapper(
            self, case_id: int, *args, current_user: User = None, **kwargs
        ):
            if not current_user:
                raise AuthenticationException("Authentication required")

            case = await crud.get_case(self.db, case_id=case_id)
            if not case:
                raise ResourceNotFoundException("Case not found")

            if case.status != "Open":
                raise AuthorizationException(
                    "Only cases with 'Open' status can be modified"
                )

            return await func(self, case_id, *args, current_user=current_user, **kwargs)

        return wrapper

    return decorator


def check_case_access(db: Session, case_id: int, current_user: User) -> Case:
    """Utility function to check if user has access to a case."""
    case = db.exec(select(Case).where(Case.id == case_id)).first()
    if not case:
        raise ResourceNotFoundException("Case not found")
    if current_user.role != UserRole.ADMIN.value and current_user not in case.users:
        raise AuthorizationException("Not authorized to access this case")

    return case


def is_case_lead(db: Session, case_id: int, current_user: User) -> bool:
    """Check if user is a lead for a specific case."""
    # Admins are always considered leads
    if current_user.role == UserRole.ADMIN.value:
        return True

    # Check the CaseUserLink table for is_lead flag
    from app.database.models import CaseUserLink

    link = db.exec(
        select(CaseUserLink).where(
            CaseUserLink.case_id == case_id, CaseUserLink.user_id == current_user.id
        )
    ).first()

    return link and link.is_lead


def load_case_with_users(db: Session, case_id: int):
    """Load a case with users including is_lead information."""
    from app.database.models import CaseUserLink
    from app.schemas.case_schema import Case as CaseSchema
    from app.schemas.case_schema import CaseUser

    # Load the case
    case = db.exec(select(Case).where(Case.id == case_id)).first()
    if not case:
        return None

    # Load case users with is_lead information
    case_users = []
    for user in case.users:
        # Get the is_lead flag from CaseUserLink
        link = db.exec(
            select(CaseUserLink).where(
                CaseUserLink.case_id == case_id, CaseUserLink.user_id == user.id
            )
        ).first()

        # Create CaseUser with is_lead information
        case_user_data = user.model_dump()
        case_user_data["is_lead"] = link.is_lead if link else False
        case_users.append(CaseUser(**case_user_data))

    # Create a CaseSchema object with the enriched users
    case_data = case.model_dump()
    case_data["users"] = case_users
    return CaseSchema(**case_data)
