"""Authorize the intersection of human and permanent Analyst Case access."""

from sqlmodel import Session, select

from app.core.exceptions import AuthenticationException, AuthorizationException
from app.database.models import User
from app.services.case_access import CaseAccess


def require_strixy_access(db: Session, current_user: User, case_id: int) -> User:
    """Resolve both current accounts before any provider or configuration access."""
    db.refresh(current_user)
    if not current_user.is_active or current_user.system_identity is not None:
        raise AuthenticationException("An active human account is required")
    access = CaseAccess(db)
    access.readable(current_user, case_id)
    strixy = db.exec(
        select(User)
        .where(User.system_identity == "strixy")
        .execution_options(populate_existing=True)
    ).first()
    if strixy is None or not strixy.is_active:
        raise AuthorizationException(
            "Strixy is unavailable. Please contact your administrator.",
            code="strixy_unavailable",
        )
    try:
        access.readable(strixy, case_id)
    except AuthorizationException as error:
        raise AuthorizationException(
            "Strixy is not enabled on this case. Ask an administrator to enable it.",
            code="strixy_not_assigned",
        ) from error
    return strixy
