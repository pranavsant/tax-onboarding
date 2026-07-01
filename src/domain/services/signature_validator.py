"""Domain service that validates the signature block of a tax form.

Business rules enforced here (apply to both W-9 and W-8BEN):
  - A visible signature must be present (``signature_present`` is ``True``).
  - A signature date must be supplied (``signature_date`` is not ``None``).
  - The signature date must be in exactly ``YYYY-MM-DD`` format AND
    represent a valid calendar date; any other ISO 8601 variants (year-only
    ``"2024"``, year-month ``"2024-03"``, week dates, etc.) are rejected,
    as is a syntactically plausible but non-existent date like ``"2024-02-30"``.

Design note — *flag, not crash*:
  Malformed or unparseable dates are treated as a validation **failure**
  with a descriptive reason string rather than raising an exception.
  This matches the null-over-failure convention used elsewhere in the
  pipeline and satisfies the acceptance criterion that malformed dates
  must be a flag, not a crash.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

# Strict YYYY-MM-DD pattern — the only format accepted on a signed tax form.
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class SignatureValidationResult:
    """Outcome of :meth:`SignatureValidator.validate`.

    Attributes:
        passed: ``True`` when the form carries a visible signature and a
            well-formed signed date; ``False`` otherwise.
        reason: Human-readable explanation of why validation failed.
            Empty string when ``passed`` is ``True``.
    """

    passed: bool
    reason: str


class SignatureValidator:
    """Stateless domain service that validates a form's signature block.

    Accepts the two signature fields from ``ParsedFormFieldsDTO`` directly
    so it remains decoupled from the DTO type itself — making it easy to
    test in isolation.
    """

    @staticmethod
    def validate(
        signature_present: bool | None,
        signature_date: str | None,
    ) -> SignatureValidationResult:
        """Validate signature presence and date for a tax form.

        Args:
            signature_present: ``True`` if a signature is visible on the
                form, ``False`` if the signature block is blank, ``None``
                if the extractor could not determine.
            signature_date: The signed date string as returned by the
                extractor.  Expected format: ``"YYYY-MM-DD"``.  May be
                ``None`` if absent or illegible.

        Returns:
            A :class:`SignatureValidationResult` with ``passed=True`` and
            an empty ``reason`` on success, or ``passed=False`` and a
            descriptive ``reason`` on failure.
        """
        # ---- 1. Signature presence check --------------------------------
        if not signature_present:
            if signature_present is False:
                reason = "Signature is missing: the signature field is blank."
            else:
                # None — extractor could not determine
                reason = (
                    "Signature presence could not be determined: "
                    "the signature field is absent or illegible."
                )
            return SignatureValidationResult(passed=False, reason=reason)

        # ---- 2. Signature date presence check ---------------------------
        if not signature_date or not signature_date.strip():
            return SignatureValidationResult(
                passed=False,
                reason="Signature date is missing: no date was found next to the signature.",
            )

        # ---- 3. Signature date format / validity check ------------------
        date_str = signature_date.strip()
        # First enforce that the string matches exactly YYYY-MM-DD.
        # Python 3.11 extended date.fromisoformat() to accept additional ISO
        # 8601 variants (e.g. year-only "2024", "YYYY-MM") — we deliberately
        # reject those here so only a fully-specified calendar date passes.
        if not _DATE_RE.match(date_str):
            return SignatureValidationResult(
                passed=False,
                reason=(
                    f"Signature date '{date_str}' is not a valid date. "
                    "Expected format: YYYY-MM-DD."
                ),
            )
        try:
            date.fromisoformat(date_str)
        except ValueError:
            return SignatureValidationResult(
                passed=False,
                reason=(
                    f"Signature date '{date_str}' is not a valid date. "
                    "Expected format: YYYY-MM-DD."
                ),
            )

        return SignatureValidationResult(passed=True, reason="")
