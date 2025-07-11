from functools import wraps

from app.core import security
from app.core.config import settings
from app.core.exceptions import AuthorizationException, ResourceNotFoundException
from app.core.roles import UserRole
from app.database import crud
from app.database.connection import get_db
from app.database.models import Case, User
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    if request.client:
        return request.client.host

    return "unknown"


def get_user_agent(request: Request) -> str:
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

    # Check if user is active
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    return user


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
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorized"
                )

            if current_user.role != UserRole.ADMIN.value:
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

        def _check_analyst_permission(current_user):
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorized"
                )
            if current_user.role == UserRole.ANALYST.value:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
                )

        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                current_user = kwargs.get("current_user")
                _check_analyst_permission(current_user)
                return await func(*args, **kwargs)

            return async_wrapper
        else:

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                current_user = kwargs.get("current_user")
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
            CaseUserLink.case_id == case_id,
            CaseUserLink.user_id == current_user.id
        )
    ).first()

    return link and link.is_lead


def load_case_with_users(db: Session, case_id: int):
    """Load a case with users including is_lead information."""
    from app.database.models import CaseUserLink
    from app.schemas.case_schema import Case as CaseSchema, CaseUser

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
                CaseUserLink.case_id == case_id,
                CaseUserLink.user_id == user.id
            )
        ).first()

        # Create CaseUser with is_lead information
        case_user_data = user.model_dump()
        case_user_data['is_lead'] = link.is_lead if link else False
        case_users.append(CaseUser(**case_user_data))

    # Create a CaseSchema object with the enriched users
    case_data = case.model_dump()
    case_data['users'] = case_users
    return CaseSchema(**case_data)
