"""TaxId value object.

Represents a US tax identifier: either a Social Security Number (SSN)
in the form XXX-XX-XXXX, or an Employer Identification Number (EIN) in
the form XX-XXXXXXX. Value objects are immutable and compared by value,
and they protect their own invariants at construction time.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from src.domain.exceptions import InvalidTaxIdError

_SSN_PATTERN = re.compile(r"^\d{3}-\d{2}-\d{4}$")
_EIN_PATTERN = re.compile(r"^\d{2}-\d{7}$")


@dataclass(frozen=True)
class TaxId:
    """Immutable value object representing a validated tax identifier."""

    value: str
    kind: str  # "SSN" or "EIN"

    @staticmethod
    def create(raw_value: str) -> "TaxId":
        """Validate and construct a TaxId from a raw user-supplied string."""
        cleaned = raw_value.strip()

        if _SSN_PATTERN.match(cleaned):
            return TaxId(value=cleaned, kind="SSN")
        if _EIN_PATTERN.match(cleaned):
            return TaxId(value=cleaned, kind="EIN")

        raise InvalidTaxIdError(
            f"'{raw_value}' is not a valid SSN (XXX-XX-XXXX) or EIN (XX-XXXXXXX)"
        )

    def masked(self) -> str:
        """Return a masked representation safe for display or logging."""
        visible = self.value[-4:]
        return f"***-**-{visible}" if self.kind == "SSN" else f"**-***{visible}"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.masked()
