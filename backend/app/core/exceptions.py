"""
App-wide exceptions
"""


class BaseException(Exception):
    """Base exception class"""


class ResourceNotFoundException(BaseException):
    """Raised when a requested resource is not found"""


class DuplicateResourceException(BaseException):
    """Raised when attempting to create a duplicate resource"""

    def __init__(self, message: str, *, field: str | None = None):
        super().__init__(message)
        self.field = field


class ValidationException(BaseException):
    """Raised when business validation fails"""


class RelatedResourceException(BaseException):
    """Raised when an operation fails due to related resources"""


class AuthenticationException(BaseException):
    """Raised when authentication fails"""


class AuthorizationException(BaseException):
    """Raised when user lacks authorization for an operation"""


class RateLimitException(BaseException):
    """Raised when an application-level request limit is exceeded."""
