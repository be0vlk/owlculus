from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session
from functools import wraps


from app.core import security
from app.database import crud
from app.database.connection import get_db
from app.database.models import User
from app.core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request, handling proxies."""
    # Check for X-Forwarded-For header (common with reverse proxies)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain (original client)
        return forwarded_for.split(",")[0].strip()

    # Check for X-Real-IP header (another common proxy header)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Fall back to direct client IP
    if request.client:
        return request.client.host

    return "unknown"


def get_user_agent(request: Request) -> str:
    """Extract user agent from request headers."""
    user_agent = request.headers.get("User-Agent")
    return user_agent if user_agent else "unknown"


async def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"Authorization": "Bearer"},
    )
    username = security.verify_access_token(token, credentials_exception)
    user = await crud.get_user_by_username(db, username=username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


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
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorized"
                )

            if current_user.role != "Admin":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
                )
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def no_analyst():
    """Decorator to check if user is not an analyst"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorized"
                )

            if current_user.role == "Analyst":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
                )
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def case_must_be_open():
    """Decorator to check if a case is open before allowing operations."""

    def decorator(func):
        @wraps(func)
        async def wrapper(
            self, case_id: int, *args, current_user: User = None, **kwargs
        ):
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            case = await crud.get_case(self.db, case_id=case_id)
            if not case:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Case not found",
                )

            if case.status != "Open":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only cases with 'Open' status can be modified",
                )

            return await func(self, case_id, *args, current_user=current_user, **kwargs)

        return wrapper

    return decorator
