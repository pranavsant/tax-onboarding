"""Domain-level exceptions.

These represent violations of business invariants and are raised by
entities, value objects, and domain services. They must never leak
framework or infrastructure details, and they contain zero third-party
dependencies.
"""


class DomainError(Exception):
    """Base class for all domain exceptions."""


class InvalidTaxIdError(DomainError):
    """Raised when a Tax ID does not satisfy the required format."""


class InvalidClientDataError(DomainError):
    """Raised when client data violates a business invariant."""


class IneligibleForOnboardingError(DomainError):
    """Raised when a client does not meet onboarding requirements."""


class UnrecognizedInvestorTypeError(DomainError):
    """Raised when an investor_type value is not 'us_person' or 'foreign_person'."""


class InvalidFormFieldsError(DomainError):
    """Raised when submitted form fields fail domain-level validation."""
