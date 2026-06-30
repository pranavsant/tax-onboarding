"""Domain service that determines the required tax form for an investor.

Business rule:
  - US persons           → W-9
  - Foreign persons      → W-8BEN
  - Anything else        → UnrecognizedInvestorTypeError

This logic lives in the domain layer because it is a pure business
rule with no dependency on infrastructure or application concerns.
"""
from __future__ import annotations

from enum import Enum

from src.domain.exceptions import UnrecognizedInvestorTypeError


class InvestorType(str, Enum):
    US_PERSON = "us_person"
    FOREIGN_PERSON = "foreign_person"


class TaxFormCode(str, Enum):
    W9 = "W-9"
    W8BEN = "W-8BEN"


class TaxFormDeterminationService:
    """Stateless domain service mapping investor type to required tax form."""

    _FORM_MAP: dict[InvestorType, TaxFormCode] = {
        InvestorType.US_PERSON: TaxFormCode.W9,
        InvestorType.FOREIGN_PERSON: TaxFormCode.W8BEN,
    }

    @classmethod
    def determine_form(cls, investor_type: str) -> TaxFormCode:
        """Return the required tax form code for the given investor_type string.

        Args:
            investor_type: Raw string supplied by the caller
                           (expected: 'us_person' or 'foreign_person').

        Returns:
            The appropriate :class:`TaxFormCode`.

        Raises:
            UnrecognizedInvestorTypeError: If *investor_type* is ``None``,
                empty, or does not match a known value.
        """
        if not investor_type or not investor_type.strip():
            raise UnrecognizedInvestorTypeError(
                "investor_type must not be empty"
            )

        try:
            typed = InvestorType(investor_type.strip().lower())
        except ValueError:
            raise UnrecognizedInvestorTypeError(
                f"Unrecognized investor_type '{investor_type}'. "
                f"Accepted values: {[e.value for e in InvestorType]}"
            )

        return cls._FORM_MAP[typed]
