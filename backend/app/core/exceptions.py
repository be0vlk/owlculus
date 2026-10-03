"""
App-wide exceptions
"""


class DomainException(Exception):
    """Base of the domain exception family; unmapped failures surface as 500."""

    status_code = 500


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


class RateLimitException(DomainException):
    """Raised when an application-level request limit is exceeded."""

    status_code = 429
