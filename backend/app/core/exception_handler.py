"""HTTP translation for application domain exceptions."""

from fastapi import Request, status
from fastapi.responses import JSONResponse

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
from app.core.logging import get_security_logger

_STATUS_BY_EXCEPTION: tuple[tuple[type[DomainException], int], ...] = (
    (ResourceNotFoundException, status.HTTP_404_NOT_FOUND),
    (AuthorizationException, status.HTTP_403_FORBIDDEN),
    (AuthenticationException, status.HTTP_401_UNAUTHORIZED),
    (DuplicateResourceException, status.HTTP_400_BAD_REQUEST),
    (ValidationException, status.HTTP_422_UNPROCESSABLE_ENTITY),
    (RelatedResourceException, status.HTTP_409_CONFLICT),
)


async def handle_domain_exception(
    request: Request, exception: Exception
) -> JSONResponse:
    """Translate the core exception family at the HTTP boundary."""
    del request
    response_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail = "Internal server error"

    for exception_type, mapped_status in _STATUS_BY_EXCEPTION:
        if isinstance(exception, exception_type):
            response_status = mapped_status
            detail = str(exception)
            break

    if isinstance(exception, AuthorizationException):
        get_security_logger(
            event_type="authorization_failed", failure_reason="not_authorized"
        ).warning("Request authorization denied")

    return JSONResponse(status_code=response_status, content={"detail": detail})
