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


class UnrecognizedInvestorTypeError(ApplicationError):
    """Raised when investor_type is missing or does not match a known value."""


class InvalidFormFieldsError(ApplicationError):
    """Raised when a submitted form field payload is missing required fields
    or contains values that fail domain-level validation."""


class TaxFormExtractionError(ApplicationError):
    """Raised when a PDF extractor cannot parse the uploaded file or cannot
    determine the tax form type from its contents."""
