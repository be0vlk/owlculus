"""
App-wide exceptions
"""


class BaseException(Exception):
    """Base exception class"""

    pass


class ResourceNotFoundException(BaseException):
    """Raised when a requested resource is not found"""

    pass


class DuplicateResourceException(BaseException):
    """Raised when attempting to create a duplicate resource"""

    pass


class ValidationException(BaseException):
    """Raised when business validation fails"""

    pass


class RelatedResourceException(BaseException):
    """Raised when an operation fails due to related resources"""

    pass


class AuthenticationException(BaseException):
    """Raised when authentication fails"""

    pass


class AuthorizationException(BaseException):
    """Raised when user lacks authorization for an operation"""

    pass
