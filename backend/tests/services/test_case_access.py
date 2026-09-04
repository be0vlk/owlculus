"""Behavioral contract for centralized case authorization."""

import ast
import inspect
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from textwrap import dedent

import pytest
from sqlalchemy import event
from sqlmodel import Session

from app.core.dependencies import admin_only, no_analyst
from app.core.exceptions import AuthorizationException
from app.database import models
from app.services.case_access import CaseAccess
from app.services.case_service import CaseService
from app.services.entity_service import EntityService
from app.services.export_service import ExportService
from app.services.hunt_service import HuntService


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
    ("case.list", "listed"),
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

SERVICE_ACCESS_POLICIES = [
    (CaseService, "create_case", "require_admin"),
    (CaseService, "get_cases", "is_admin"),
    (CaseService, "get_case", "readable"),
    (CaseService, "update_case", "writable"),
    (CaseService, "add_user_to_case", "require_admin"),
    (CaseService, "remove_user_from_case", "require_admin"),
    (CaseService, "update_case_user_lead_status", "require_admin"),
    (EntityService, "get_case_entities", "readable"),
    (EntityService, "get_entity", "readable"),
    (EntityService, "create_entity", "writable"),
    (EntityService, "update_entity", "writable"),
    (EntityService, "delete_entity", "writable"),
    (EntityService, "find_entity_by_ip_address", "readable"),
    (EntityService, "find_entity_by_domain", "readable"),
    (EntityService, "enrich_entity_description", "writable"),
    (ExportService, "export_entities", "readable"),
    (ExportService, "export_case_bundle", "readable"),
    (ExportService, "export_hunt_execution", "readable"),
    (HuntService, "create_execution", "writable"),
    (HuntService, "get_execution", "readable"),
    (HuntService, "list_case_executions", "readable"),
    (HuntService, "cancel_execution", "writable"),
    (HuntService, "get_execution_steps", "readable"),
]


@pytest.mark.parametrize(("service", "method_name", "policy"), SERVICE_ACCESS_POLICIES)
def test_service_operation_uses_one_declared_case_access_policy(
    service: type, method_name: str, policy: str
):
    """Guard policy count, authorization order, and resolved-case reuse."""
    tree = ast.parse(dedent(inspect.getsource(getattr(service, method_name))))
    function = tree.body[0]
    assert isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef))
    policy_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Attribute)
        and isinstance(node.func.value.value, ast.Name)
        and node.func.value.value.id == "self"
        and node.func.value.attr == "access"
        and node.func.attr
        in {"readable", "writable", "lead", "require_admin", "is_admin"}
    ]

    assert [call.func.attr for call in policy_calls] == [policy]
    policy_call = policy_calls[0]
    statements = [
        statement
        for statement in function.body
        if not (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        )
    ]
    policy_statement_index = next(
        index
        for index, statement in enumerate(statements)
        if policy_call in ast.walk(statement)
    )
    parent_lookup_methods = {
        (HuntService, "get_execution"),
        (HuntService, "cancel_execution"),
        (HuntService, "get_execution_steps"),
        (ExportService, "export_hunt_execution"),
    }
    if (service, method_name) in parent_lookup_methods:
        assert policy_statement_index == 2
        lookup, missing_guard = statements[:2]
        assert isinstance(lookup, ast.Assign)
        assert len(lookup.targets) == 1
        assert isinstance(lookup.targets[0], ast.Name)
        assert lookup.targets[0].id == "execution"
        assert isinstance(lookup.value, ast.Call)
        assert isinstance(lookup.value.func, ast.Attribute)
        assert ast.unparse(lookup.value.func) == "self.db.get"
        assert len(lookup.value.args) == 2
        assert ast.unparse(lookup.value.args[0]) in {
            "HuntExecution",
            "models.HuntExecution",
        }
        assert ast.unparse(lookup.value.args[1]) == "execution_id"

        assert isinstance(missing_guard, ast.If)
        assert ast.unparse(missing_guard.test) in {
            "execution is None",
            "not execution",
        }
        assert not missing_guard.orelse
        assert len(missing_guard.body) == 1
        assert isinstance(missing_guard.body[0], ast.Raise)
        assert isinstance(missing_guard.body[0].exc, ast.Call)
        assert ast.unparse(missing_guard.body[0].exc.func) == (
            "ResourceNotFoundException"
        )
    else:
        assert policy_statement_index == 0

    if policy in {"readable", "writable", "lead"}:
        assignment = next(
            (
                node
                for node in ast.walk(function)
                if isinstance(node, ast.Assign)
                and node.value is policy_call
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
            ),
            None,
        )
        assert assignment is not None
        resolved_case_name = assignment.targets[0].id
        assert any(
            isinstance(node, ast.Name)
            and node.id == resolved_case_name
            and isinstance(node.ctx, ast.Load)
            and node.lineno > assignment.lineno
            for node in ast.walk(function)
        )


@pytest.mark.parametrize(("operation", "policy"), OPERATION_POLICIES)
@pytest.mark.parametrize("role", ["admin", "investigator", "outsider", "analyst"])
@pytest.mark.asyncio
async def test_operation_permission_matrix(
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
    if policy == "listed":
        test_case.title = "Permission matrix case"
        session.add(test_case)
        session.commit()
        cases = await CaseService(session).get_cases(user)
        listed_case_ids = {case.id for case in cases}
        assert (test_case.id in listed_case_ids) is (role != "outsider"), operation
        return

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
