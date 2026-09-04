"""Contract tests for application-wide domain exception translation."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user
from app.core.exceptions import (
    AuthenticationException,
    AuthorizationException,
    DuplicateResourceException,
    RelatedResourceException,
    ResourceNotFoundException,
    ValidationException,
)
from app.core.exceptions import (
    BaseException as DomainException,
)
from app.main import app


@pytest.mark.parametrize(
    ("exception", "status_code", "detail"),
    [
        (ResourceNotFoundException("missing"), 404, "missing"),
        (AuthorizationException("denied"), 403, "denied"),
        (AuthenticationException("sign in"), 401, "sign in"),
        (DuplicateResourceException("duplicate"), 400, "duplicate"),
        (ValidationException("invalid"), 422, "invalid"),
        (RelatedResourceException("conflict"), 409, "conflict"),
        (DomainException("secret detail"), 500, "Internal server error"),
    ],
)
def test_domain_exception_family_is_translated_by_one_application_handler(
    client: TestClient,
    test_admin,
    exception: DomainException,
    status_code: int,
    detail: str,
):
    app.dependency_overrides[get_current_user] = lambda: test_admin
    try:
        with patch(
            "app.services.evidence_service.EvidenceService.get_case_evidence",
            side_effect=exception,
        ):
            response = client.get("/api/evidence/case/1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_authorization_denial_is_audited_once_by_the_handler(
    client: TestClient, test_admin
):
    app.dependency_overrides[get_current_user] = lambda: test_admin
    try:
        with (
            patch(
                "app.services.evidence_service.EvidenceService.get_case_evidence",
                side_effect=AuthorizationException("denied"),
            ),
            patch("app.core.exception_handler.get_security_logger") as logger_factory,
        ):
            response = client.get("/api/evidence/case/1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    logger_factory.assert_called_once_with(
        event_type="authorization_failed", failure_reason="not_authorized"
    )
    logger_factory.return_value.warning.assert_called_once_with(
        "Request authorization denied"
    )


def test_handler_is_registered_for_the_core_exception_family():
    assert DomainException in app.exception_handlers
