from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select
from functools import wraps


from app.core import security
from app.database import crud
from app.database.connection import get_db
from app.database.models import User, Case
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
        import inspect
        
        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                # Try to get current_user from kwargs first
                current_user = kwargs.get("current_user")
                
                # If not in kwargs, try to extract from positional args
                # For service methods, current_user is typically the last positional argument
                if not current_user and args:
                    # Look for User object in args
                    from app.database.models import User
                    for arg in args:
                        if isinstance(arg, User):
                            current_user = arg
                            break
                
                if not current_user:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorized"
                    )

                if current_user.role == "Analyst":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
                    )
                return await func(*args, **kwargs)
            
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                # Try to get current_user from kwargs first
                current_user = kwargs.get("current_user")
                
                # If not in kwargs, try to extract from positional args
                # For service methods, current_user is typically the last positional argument
                if not current_user and args:
                    # Look for User object in args
                    from app.database.models import User
                    for arg in args:
                        if isinstance(arg, User):
                            current_user = arg
                            break
                
                if not current_user:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorized"
                    )

                if current_user.role == "Analyst":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
                    )
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


def check_case_access(db: Session, case_id: int, current_user: User) -> Case:
    """
    Utility function to check if user has access to a case.
    
    Args:
        db: Database session
        case_id: ID of the case to check access for
        current_user: Current authenticated user
        
    Returns:
        Case object if user has access
        
    Raises:
        HTTPException: If case not found or user doesn't have access
    """
    # Check if case exists
    case = db.exec(select(Case).where(Case.id == case_id)).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Check if user has access to the case
    if current_user.role != "Admin" and current_user not in case.users:
        raise HTTPException(status_code=403, detail="Not authorized to access this case")
    
    return case


