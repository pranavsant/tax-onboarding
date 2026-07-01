"""Domain service that validates whether a W-8BEN form has expired.

IRS rule: A W-8BEN is valid from the date it is signed through the end of
the **third calendar year** after signing.

Example:
  Signed 2025-01-20 → valid through 2028-12-31
  Signed 2025-12-31 → valid through 2028-12-31
  Signed 2022-03-15 → valid through 2025-12-31
    → expired as of 2026-01-01 (or any date after 2025-12-31)

Design notes:
  * The ``today`` parameter is injectable so tests can pin the current date
    without monkeypatching ``datetime.date.today``.
  * Malformed ``signed_date`` strings are treated as a validation failure
    with a descriptive reason, consistent with the null-over-failure
    convention used throughout the pipeline.
  * The strict ``YYYY-MM-DD`` regex guard mirrors
    :mod:`~src.domain.services.signature_validator` to defend against
    Python 3.11's extended ISO 8601 acceptance in ``date.fromisoformat``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

# Only YYYY-MM-DD is accepted — same guard used in SignatureValidator.
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class ExpirationValidationResult:
    """Outcome of :meth:`ExpirationValidator.validate`.

    Attributes:
        passed: ``True`` when the form has not yet expired as of *today*;
            ``False`` when it has expired or the signed date was absent /
            unparseable.
        reason: Human-readable explanation of the outcome.  Empty string
            when ``passed`` is ``True``.
        valid_through: The computed expiry date (always the last day of a
            calendar year), or ``None`` when the signed date could not be
            parsed.
    """

    passed: bool
    reason: str
    valid_through: Optional[date] = None


class ExpirationValidator:
    """Stateless domain service that checks W-8BEN form expiration.

    A W-8BEN is valid from the day it is signed through the last day of
    the third calendar year that follows the year of signing.  For example,
    a form signed on any date in 2025 expires on 2028-12-31.

    Usage::

        result = ExpirationValidator.validate(signed_date="2025-01-20")
        # result.valid_through → date(2028, 12, 31)
        # result.passed        → True  (assuming today < 2029-01-01)
    """

    @staticmethod
    def validate(
        signed_date: str | None,
        today: Optional[date] = None,
    ) -> ExpirationValidationResult:
        """Compute the expiry date and check whether the form has expired.

        Args:
            signed_date: The date the form was signed, expected in
                ``YYYY-MM-DD`` format (same as ``signature_date`` on
                :class:`~src.application.dto.tax_form_dto.ParsedFormFieldsDTO`).
                May be ``None`` if absent or illegible.
            today: The reference date used as "today".  Defaults to
                :func:`datetime.date.today` when ``None`` is passed,
                enabling deterministic testing without monkeypatching.

        Returns:
            An :class:`ExpirationValidationResult` with:

            * ``passed=True`` and empty ``reason`` when the form is still
              valid as of *today*.
            * ``passed=False`` and a descriptive ``reason`` when the form
              has expired or the signed date could not be parsed.
        """
        effective_today = today if today is not None else date.today()

        # ---- 1. Signed date presence check --------------------------------
        if not signed_date or not signed_date.strip():
            return ExpirationValidationResult(
                passed=False,
                reason=(
                    "W-8BEN expiration cannot be determined: "
                    "signed date is missing."
                ),
                valid_through=None,
            )

        date_str = signed_date.strip()

        # ---- 2. Strict format check (YYYY-MM-DD only) --------------------
        if not _DATE_RE.match(date_str):
            return ExpirationValidationResult(
                passed=False,
                reason=(
                    f"W-8BEN expiration cannot be determined: "
                    f"signed date '{date_str}' is not a valid date. "
                    "Expected format: YYYY-MM-DD."
                ),
                valid_through=None,
            )

        # ---- 3. Calendar validity check ----------------------------------
        try:
            parsed = date.fromisoformat(date_str)
        except ValueError:
            return ExpirationValidationResult(
                passed=False,
                reason=(
                    f"W-8BEN expiration cannot be determined: "
                    f"signed date '{date_str}' is not a valid date. "
                    "Expected format: YYYY-MM-DD."
                ),
                valid_through=None,
            )

        # ---- 4. Compute valid_through -------------------------------------
        # IRS rule: valid through the end of the third calendar year after
        # the year in which the form was signed.
        valid_through = date(parsed.year + 3, 12, 31)

        # ---- 5. Expiration check -----------------------------------------
        if effective_today > valid_through:
            return ExpirationValidationResult(
                passed=False,
                reason=(
                    f"W-8BEN form expired: it was valid through "
                    f"{valid_through.isoformat()} but today is "
                    f"{effective_today.isoformat()}."
                ),
                valid_through=valid_through,
            )

        return ExpirationValidationResult(
            passed=True,
            reason="",
            valid_through=valid_through,
        )
