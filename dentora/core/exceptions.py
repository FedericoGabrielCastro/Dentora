class DentoraError(Exception):
    """Base exception for all domain-level errors in Dentora."""


class ValidationError(DentoraError):
    """Raised when domain-level validation fails."""


class NotFoundError(DentoraError):
    """Raised when a requested resource does not exist."""


class ConflictError(DentoraError):
    """Raised when an operation conflicts with the current resource state."""
