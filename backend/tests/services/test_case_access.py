"""Behavioral contract for centralized case authorization."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy import event
from sqlmodel import Session

from app.core.dependencies import admin_only, no_analyst
from app.core.exceptions import AuthorizationException
from app.database import models
from app.services.case_access import CaseAccess
from app.services.case_service import CaseService


@contextmanager
def recorded_sql(session: Session) -> Iterator[list[str]]:
    """Collect SQL issued through a session for a bounded assertion."""
    statements: list[str] = []

    def record_statement(*args):
        statements.append(args[2])

    bind = session.get_bind()
    event.listen(bind, "before_cursor_execute", record_statement)
    try:
        yield statements
    finally:
        event.remove(bind, "before_cursor_execute", record_statement)


@pytest.fixture(name="access_users")
def access_users_fixture(session: Session, test_case: models.Case):
    admin = models.User(
        username="matrix-admin",
        email="matrix-admin@example.com",
        password_hash="hash",
        role="Admin",
    )
    investigator = models.User(
        username="matrix-investigator",
        email="matrix-investigator@example.com",
        password_hash="hash",
        role="Investigator",
    )
    outsider = models.User(
        username="matrix-outsider",
        email="matrix-outsider@example.com",
        password_hash="hash",
        role="Investigator",
    )
    analyst = models.User(
        username="matrix-analyst",
        email="matrix-analyst@example.com",
        password_hash="hash",
        role="Analyst",
    )
    session.add_all([admin, investigator, outsider, analyst])
    session.commit()
    for user in (admin, investigator, outsider, analyst):
        session.refresh(user)
    session.add_all(
        [
            models.CaseUserLink(
                case_id=test_case.id, user_id=investigator.id, is_lead=True
            ),
            models.CaseUserLink(case_id=test_case.id, user_id=analyst.id),
        ]
    )
    session.commit()
    return {
        "admin": admin,
        "investigator": investigator,
        "outsider": outsider,
        "analyst": analyst,
    }


@pytest.mark.parametrize(
    ("verb", "allowed_roles"),
    [
        ("readable", {"admin", "investigator", "analyst"}),
        ("writable", {"admin", "investigator"}),
        ("lead", {"admin", "investigator"}),
    ],
)
def test_case_permission_matrix(
    session: Session,
    test_case: models.Case,
    access_users: dict[str, models.User],
    verb: str,
    allowed_roles: set[str],
):
    access = CaseAccess(session)
    authorize: Callable[[models.User, int], models.Case] = getattr(access, verb)

    for role, user in access_users.items():
        if role in allowed_roles:
            assert authorize(user, test_case.id).id == test_case.id
        else:
            with pytest.raises(AuthorizationException):
                authorize(user, test_case.id)


def test_admin_permission_matrix(
    session: Session, access_users: dict[str, models.User]
):
    access = CaseAccess(session)

    assert access.require_admin(access_users["admin"]) is access_users["admin"]
    for role in ("investigator", "outsider", "analyst"):
        with pytest.raises(AuthorizationException):
            access.require_admin(access_users[role])


def test_membership_authorization_uses_one_query(
    session: Session,
    test_case: models.Case,
    access_users: dict[str, models.User],
):
    case_id = test_case.id
    investigator = access_users["investigator"]
    assert investigator.id is not None

    with recorded_sql(session) as statements:
        resolved = CaseAccess(session).readable(investigator, case_id)

    assert resolved.id == case_id
    assert len(statements) == 1


@pytest.mark.parametrize(
    ("verb", "operation"), [("writable", "write"), ("lead", "lead")]
)
def test_denial_audit_records_attempted_operation(
    monkeypatch,
    session: Session,
    test_case: models.Case,
    access_users: dict[str, models.User],
    verb: str,
    operation: str,
):
    audit_context: dict[str, object] = {}

    class AuditLogger:
        def warning(self, message: str) -> None:
            assert message == "Case access denied"

    def capture_audit(**context):
        audit_context.update(context)
        return AuditLogger()

    monkeypatch.setattr("app.services.case_access.get_security_logger", capture_audit)

    with pytest.raises(AuthorizationException):
        getattr(CaseAccess(session), verb)(access_users["outsider"], test_case.id)

    assert audit_context["operation"] == operation


OPERATION_POLICIES = [
    ("case.create", "require_admin"),
    ("case.read", "readable"),
    ("case.update", "writable"),
    ("case.add_user", "require_admin"),
    ("case.remove_user", "require_admin"),
    ("case.update_lead", "require_admin"),
    ("entity.list", "readable"),
    ("entity.read", "readable"),
    ("entity.find_ip", "readable"),
    ("entity.find_domain", "readable"),
    ("entity.create", "writable"),
    ("entity.update", "writable"),
    ("entity.delete", "writable"),
    ("entity.enrich", "writable"),
    ("export.entities", "readable"),
    ("export.hunt", "readable"),
    ("export.case_bundle", "readable"),
    ("hunt.create_execution", "writable"),
    ("hunt.cancel_execution", "writable"),
    ("hunt.read_execution", "readable"),
    ("hunt.list_case_executions", "readable"),
    ("hunt.read_execution_steps", "readable"),
]


@pytest.mark.parametrize(("operation", "policy"), OPERATION_POLICIES)
@pytest.mark.parametrize("role", ["admin", "investigator", "outsider", "analyst"])
def test_operation_permission_matrix(
    session: Session,
    test_case: models.Case,
    access_users: dict[str, models.User],
    operation: str,
    policy: str,
    role: str,
):
    """Every case-scoped service operation maps to the shared role policy."""
    access = CaseAccess(session)
    user = access_users[role]
    allowed = (
        role == "admin"
        or (policy == "readable" and role in {"investigator", "analyst"})
        or (policy == "writable" and role == "investigator")
    )

    if allowed:
        if policy == "require_admin":
            assert access.require_admin(user) is user, operation
        else:
            assert getattr(access, policy)(user, test_case.id).id == test_case.id
    else:
        with pytest.raises(AuthorizationException):
            if policy == "require_admin":
                access.require_admin(user)
            else:
                getattr(access, policy)(user, test_case.id)


@pytest.mark.asyncio
async def test_legacy_role_decorators_accept_positional_current_user(
    session: Session, access_users: dict[str, models.User]
):
    @admin_only()
    async def admin_operation(current_user: models.User):
        return current_user

    @no_analyst()
    async def investigator_operation(current_user: models.User):
        return current_user

    assert await admin_operation(access_users["admin"]) is access_users["admin"]
    assert (
        await investigator_operation(access_users["investigator"])
        is access_users["investigator"]
    )


@pytest.mark.asyncio
async def test_case_list_with_users_has_constant_query_count(
    session: Session,
    test_case: models.Case,
    access_users: dict[str, models.User],
):
    test_case.title = "First query-count case"
    session.add(test_case)
    second_case = models.Case(
        case_number="QUERY-002",
        title="Second query-count case",
        status="Open",
        client_id=test_case.client_id,
    )
    session.add(second_case)
    session.commit()
    session.refresh(second_case)
    session.add(
        models.CaseUserLink(
            case_id=second_case.id,
            user_id=access_users["investigator"].id,
        )
    )
    session.commit()
    admin = access_users["admin"]
    assert admin.role == "Admin"
    with recorded_sql(session) as statements:
        cases = await CaseService(session).get_cases(admin)

    assert len(cases) == 2
    assert len(statements) == 2
