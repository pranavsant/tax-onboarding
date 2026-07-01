"""Domain service that validates TIN (Taxpayer Identification Number) fields.

Business rules
--------------
W-9 (US persons)
    ``tin`` must conform to one of two standard US formats:
      * **SSN** — Social Security Number: ``XXX-XX-XXXX``  (e.g. 412-88-7693)
      * **EIN** — Employer Identification Number: ``XX-XXXXXXX``
    The format is checked via the :class:`~src.domain.value_objects.tax_id.TaxId`
    value object which already encodes these patterns.

W-8BEN (foreign persons)
    ``foreign_tin`` must be **present and non-empty**.  Format requirements vary
    widely by country (e.g. Brazilian CPF uses ``219.871.330-44``), so only
    presence is enforced — no country-specific regex is applied.

    ``us_tin`` on a W-8BEN is optional.  When supplied it is validated the same
    way as a W-9 ``tin`` (must be a valid SSN or EIN).

Design note — *flag, not crash*:
    Malformed TINs are treated as validation **failures** with descriptive
    reason strings rather than raising exceptions.  This matches the
    null-over-failure convention used by :class:`SignatureValidator` and allows
    the interfaces layer to return structured error responses to callers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from src.domain.exceptions import InvalidTaxIdError
from src.domain.value_objects.tax_id import TaxId

# Minimum "presence" check for foreign TINs: at least one alphanumeric
# character, allowing digits, letters, spaces, and common separators
# (hyphens, dots, slashes) used in international tax identifiers.
_FOREIGN_TIN_RE = re.compile(r"[A-Za-z0-9]")


@dataclass(frozen=True)
class TINValidationResult:
    """Outcome of a :class:`TINValidator` validation call.

    Attributes:
        passed: ``True`` when the TIN satisfies the format rules for its
            form type; ``False`` otherwise.
        reason: Human-readable explanation of why validation failed.
            Empty string when ``passed`` is ``True``.
    """

    passed: bool
    reason: str


class TINValidator:
    """Stateless domain service that validates TIN fields on tax forms.

    All methods accept the raw field value so the service remains
    decoupled from DTO types — making it easy to test in isolation.
    """

    # ------------------------------------------------------------------ W-9

    @staticmethod
    def validate_us_tin(tin: str | None) -> TINValidationResult:
        """Validate a US TIN (SSN or EIN) as used on a W-9 form.

        The value must match either:
          * SSN format ``XXX-XX-XXXX``  (e.g. ``412-88-7693``)
          * EIN format ``XX-XXXXXXX``

        Args:
            tin: The raw TIN string from the form.  ``None`` or blank string
                indicates absence.

        Returns:
            :class:`TINValidationResult` with ``passed=True`` and ``reason=""``
            on success, or ``passed=False`` and a descriptive ``reason`` on
            failure.
        """
        if not tin or not tin.strip():
            return TINValidationResult(
                passed=False,
                reason="TIN is missing: no taxpayer identification number was provided.",
            )

        try:
            TaxId.create(tin.strip())
        except InvalidTaxIdError:
            return TINValidationResult(
                passed=False,
                reason=(
                    f"TIN '{tin.strip()}' is not a valid SSN (XXX-XX-XXXX) "
                    "or EIN (XX-XXXXXXX)."
                ),
            )

        return TINValidationResult(passed=True, reason="")

    # --------------------------------------------------------------- W-8BEN

    @staticmethod
    def validate_foreign_tin(foreign_tin: str | None) -> TINValidationResult:
        """Validate a foreign TIN as used on a W-8BEN form (line 6a).

        The only requirement is that the value is **present and non-empty**
        (contains at least one alphanumeric character).  No country-specific
        format is enforced because TIN structures vary significantly between
        jurisdictions (e.g. Brazilian CPF ``219.871.330-44``, UK UTR
        ``1234567890``, German Steuer-IdNr ``12345678901``).

        Args:
            foreign_tin: The raw foreign TIN string from the form.  ``None``
                or blank indicates absence.

        Returns:
            :class:`TINValidationResult` with ``passed=True`` when the value
            is present and contains at least one alphanumeric character.
        """
        if not foreign_tin or not foreign_tin.strip():
            return TINValidationResult(
                passed=False,
                reason=(
                    "Foreign TIN is missing: no foreign tax identifying number "
                    "was provided on line 6a of the W-8BEN."
                ),
            )

        cleaned = foreign_tin.strip()
        if not _FOREIGN_TIN_RE.search(cleaned):
            return TINValidationResult(
                passed=False,
                reason=(
                    f"Foreign TIN '{cleaned}' does not appear to be a valid "
                    "tax identifier: it contains no alphanumeric characters."
                ),
            )

        return TINValidationResult(passed=True, reason="")
