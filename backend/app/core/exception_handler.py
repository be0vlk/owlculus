"""HTTP translation for application domain exceptions."""

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.exceptions import AuthorizationException, DomainException
from app.core.logging import get_security_logger


async def handle_domain_exception(
    request: Request, exception: Exception
) -> JSONResponse:
    """Translate domain exceptions, and hide anything unexpected as a JSON 500."""
    del request
    unmapped = DomainException.status_code
    response_status = (
        exception.status_code if isinstance(exception, DomainException) else unmapped
    )
    detail = str(exception) if response_status != unmapped else "Internal server error"
    content = {"detail": detail}
    if isinstance(exception, AuthorizationException):
        get_security_logger(
            event_type="authorization_failed", failure_reason="not_authorized"
        ).warning("Request authorization denied")
        if exception.code is not None:
            content["code"] = exception.code
    return JSONResponse(status_code=response_status, content=content)
