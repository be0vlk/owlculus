"""Central case authorization policy.

Case existence is disclosed to authenticated users: a missing case raises 404, while
an existing case denied by membership or role raises 403.  Administrators bypass
case membership, analysts may read assigned cases but may not write or lead them,
and every case verb returns the case resolved by its single authorization query.
"""

from typing import NoReturn

from sqlmodel import Session, col, select

from app.core.exceptions import (
    AuthenticationException,
    AuthorizationException,
    ResourceNotFoundException,
    ValidationException,
)
from app.core.logging import get_security_logger
from app.core.roles import UserRole
from app.database.models import Case, CaseUserLink, Evidence, User


class CaseAccess:
    """Answer all role and case-membership authorization questions."""

    def __init__(self, db: Session | None = None):
        self.db = db

    def readable(self, user: User, case_id: int) -> Case:
        case, _ = self._case_membership(user, case_id, operation="read")
        return case

    def readable_case_ids(self, user: User) -> list[int]:
        """Return the complete case scope the user may read."""
        if self.db is None:
            raise RuntimeError("A database session is required for case authorization")
        if self.is_admin(user):
            statement = select(Case.id)
        else:
            statement = select(CaseUserLink.case_id).where(
                CaseUserLink.user_id == user.id
            )
        return [case_id for case_id in self.db.exec(statement).all() if case_id]

    def evidence_parent(self, case_id: int, parent_id: int | None) -> Evidence | None:
        """Resolve a folder only after checking its entire ancestry stays in the Case."""
        if parent_id is None:
            return None
        if self.db is None:
            raise RuntimeError("A database session is required for case authorization")
        parent = self.db.get(Evidence, parent_id)
        if parent is None:
            raise ResourceNotFoundException("Parent folder not found")
        ancestor: Evidence | None = parent
        seen: set[int] = set()
        while ancestor is not None:
            if (
                ancestor.case_id != case_id
                or not ancestor.is_folder
                or ancestor.id in seen
            ):
                raise ValidationException("Invalid parent folder")
            if ancestor.id is not None:
                seen.add(ancestor.id)
            if ancestor.parent_folder_id is None:
                break
            ancestor = self.db.get(Evidence, ancestor.parent_folder_id)
            if ancestor is None:
                raise ValidationException("Invalid parent folder")
        return parent

    def eligible_evidence_parent_id(
        self, case_id: int, parent_id: int | None
    ) -> int | None:
        """Suppress invalid historical parent references on reads and exports."""
        try:
            self.evidence_parent(case_id, parent_id)
        except (ResourceNotFoundException, ValidationException):
            return None
        return parent_id

    def assignee(self, case_id: int, user_id: int | None) -> User | None:
        """Resolve an assignment using the same eligibility as Case readers."""
        if user_id is None:
            return None
        if self.db is None:
            raise RuntimeError("A database session is required for case authorization")
        user = self.db.get(User, user_id)
        if user is None:
            raise ResourceNotFoundException("User not found")
        self.readable(user, case_id)
        return user

    def eligible_assignee(self, case_id: int, user_id: int | None) -> User | None:
        """Hide historical assignments that no longer satisfy the read policy."""
        try:
            return self.assignee(case_id, user_id)
        except (ResourceNotFoundException, AuthorizationException):
            return None

    def writable(self, user: User, case_id: int) -> Case:
        case, _ = self._case_membership(user, case_id, operation="write")
        if user.role == UserRole.ANALYST.value:
            self._deny(user, case_id, "write", "analyst_read_only")
        return case

    def lead(self, user: User, case_id: int) -> Case:
        case, is_lead = self._case_membership(user, case_id, operation="lead")
        if user.role != UserRole.ADMIN.value and not is_lead:
            self._deny(user, case_id, "lead", "not_case_lead")
        return case

    def require_admin(self, user: User | None) -> User:
        if user is None:
            raise AuthenticationException("Not authorized")
        if user.role != UserRole.ADMIN.value:
            self._deny(user, None, "admin", "not_admin", message="Not authorized")
        return user

    @staticmethod
    def is_admin(user: User) -> bool:
        return user.role == UserRole.ADMIN.value

    def require_non_analyst(self, user: User | None) -> User:
        """Authorize global write-like operations that investigators may perform."""
        if user is None:
            raise AuthenticationException("Not authorized")
        if user.role == UserRole.ANALYST.value:
            self._deny(
                user,
                None,
                "write",
                "analyst_read_only",
                message="Not authorized",
            )
        return user

    @staticmethod
    def validate_lead_assignment(user: User, *, is_lead: bool) -> User:
        """Reject assigning the read-only analyst role as a case lead."""
        if is_lead and user.role == UserRole.ANALYST.value:
            raise ValidationException("Analysts cannot be set as case leads")
        return user

    def _case_membership(
        self, user: User, case_id: int, *, operation: str
    ) -> tuple[Case, bool]:
        if self.db is None:
            raise RuntimeError("A database session is required for case authorization")

        statement = (
            select(Case, CaseUserLink.is_lead)
            .join(
                CaseUserLink,
                (col(CaseUserLink.case_id) == Case.id)
                & (col(CaseUserLink.user_id) == user.id),
                isouter=True,
            )
            .where(Case.id == case_id)
        )
        row = self.db.exec(statement).first()
        if row is None:
            raise ResourceNotFoundException("Case not found")

        case, is_lead = row
        if user.role != UserRole.ADMIN.value and is_lead is None:
            self._deny(user, case_id, operation, "not_case_member")
        return case, bool(is_lead)

    @staticmethod
    def _deny(
        user: User,
        case_id: int | None,
        operation: str,
        reason: str,
        *,
        message: str = "Not authorized to access this case",
    ) -> NoReturn:
        get_security_logger(
            user_id=user.id,
            case_id=case_id,
            operation=operation,
            event_type="case_access_denied",
            failure_reason=reason,
        ).warning("Case access denied")
        raise AuthorizationException(message)
