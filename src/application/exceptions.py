"""Application-level exceptions surfaced to the interfaces layer.

Use cases translate domain exceptions (and infrastructure failures
reported through ports) into these application exceptions so that the
interfaces layer never needs to know about domain types directly.
"""


class ApplicationError(Exception):
    """Base class for all application exceptions."""


class ClientNotFoundError(ApplicationError):
    """Raised when a requested client cannot be found."""


class InvalidClientRequestError(ApplicationError):
    """Raised when a use case input fails domain validation."""


class AIAssistantError(ApplicationError):
    """Raised when the AI tax assistant fails to produce a response."""
