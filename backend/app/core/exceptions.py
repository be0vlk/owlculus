"""
App-wide exceptions
"""


class DomainException(Exception):
    """Base of the domain exception family; unmapped failures surface as 500."""

    status_code = 500

    def __init__(self, message: str = "", *, retry_after: int | None = None):
        super().__init__(message)
        self.headers = (
            {"Retry-After": str(retry_after)} if retry_after is not None else None
        )


class ResourceNotFoundException(DomainException):
    """Raised when a requested resource is not found"""

    status_code = 404


class DuplicateResourceException(DomainException):
    """Raised when attempting to create a duplicate resource"""

    status_code = 400

    def __init__(self, message: str, *, field: str | None = None):
        super().__init__(message)
        self.field = field


class ValidationException(DomainException):
    """Raised when business validation fails"""

    status_code = 422


class RelatedResourceException(DomainException):
    """Raised when an operation fails due to related resources"""

    status_code = 409


class AuthenticationException(DomainException):
    """Raised when authentication fails"""

    status_code = 401


class AuthorizationException(DomainException):
    """Raised when user lacks authorization for an operation"""

    status_code = 403

    def __init__(self, message: str, *, code: str | None = None):
        super().__init__(message)
        self.code = code


class PayloadTooLargeException(DomainException):
    """Raised when a request carries more than the application accepts"""

    status_code = 413


class GoneException(DomainException):
    """Raised when a retired capability is still requested"""

    status_code = 410


class RateLimitException(DomainException):
    """Raised when an application-level request limit is exceeded."""

    status_code = 429


class ServiceUnavailableException(DomainException):
    """Raised when a dependency or capacity limit makes a retry worthwhile."""

    status_code = 503
