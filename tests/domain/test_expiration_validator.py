"""Unit tests for ExpirationValidator domain service.

Covers the following scenarios:

  Happy-path (not expired):
    - Signed early in the year, checked well before expiry → passes
    - Signed late in the year (Dec 31), checked just before expiry → passes
    - Checked exactly on valid_through date (boundary: last day still valid) → passes

  Acceptance-criterion smoke test:
    - signed_date=2025-01-20 → valid_through=2028-12-31

  Expired forms:
    - Checked one day after valid_through → fails
    - Signed Dec 31 of some year, checked in the year after expiry → fails
    - Old form signed several years ago → fails

  Missing / malformed signed_date:
    - None  → fails (no crash)
    - empty string → fails (no crash)
    - whitespace-only → fails (no crash)
    - non-ISO garbage → fails (no crash)
    - US date format (MM/DD/YYYY) → fails (no crash)
    - Year-only → fails (no crash)
    - Invalid calendar date (Feb 30) → fails (no crash)

  valid_through value:
    - Always Dec 31 of year_signed + 3
    - Returned as a date object in domain result
    - None when signed_date is unparseable
"""
from __future__ import annotations

from datetime import date

from src.domain.services.expiration_validator import ExpirationValidationResult, ExpirationValidator


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _validate(
    signed_date: str | None = None,
    today: date | None = None,
) -> ExpirationValidationResult:
    return ExpirationValidator.validate(signed_date=signed_date, today=today)


# ===========================================================================
# Acceptance-criterion smoke test
# ===========================================================================


class TestExpirationValidatorAcceptanceCriteria:
    """IRS rule: signed 2025-01-20 → valid_through 2028-12-31."""

    def test_valid_through_for_2025_01_20(self) -> None:
        result = _validate(signed_date="2025-01-20", today=date(2025, 1, 21))
        assert result.valid_through == date(2028, 12, 31)

    def test_valid_through_is_always_dec_31(self) -> None:
        result = _validate(signed_date="2025-01-20", today=date(2025, 1, 21))
        assert result.valid_through is not None
        assert result.valid_through.month == 12
        assert result.valid_through.day == 31


# ===========================================================================
# valid_through computation — boundary cases
# ===========================================================================


class TestExpirationValidatorValidThrough:
    """Computed valid_through is always Dec 31 of (year_signed + 3)."""

    def test_signed_early_in_year(self) -> None:
        result = _validate(signed_date="2022-01-01", today=date(2022, 1, 2))
        assert result.valid_through == date(2025, 12, 31)

    def test_signed_mid_year(self) -> None:
        result = _validate(signed_date="2022-06-15", today=date(2022, 6, 16))
        assert result.valid_through == date(2025, 12, 31)

    def test_signed_late_in_year(self) -> None:
        result = _validate(signed_date="2022-12-30", today=date(2022, 12, 31))
        assert result.valid_through == date(2025, 12, 31)

    def test_signed_on_dec_31(self) -> None:
        """Boundary: signed on the last day of the year — still +3 years."""
        result = _validate(signed_date="2022-12-31", today=date(2023, 1, 1))
        assert result.valid_through == date(2025, 12, 31)

    def test_signed_in_different_year(self) -> None:
        result = _validate(signed_date="2020-03-05", today=date(2020, 3, 6))
        assert result.valid_through == date(2023, 12, 31)


# ===========================================================================
# Happy path — not expired
# ===========================================================================


class TestExpirationValidatorNotExpired:
    """Forms that have not yet expired must pass."""

    def test_returns_expiration_validation_result(self) -> None:
        result = _validate(signed_date="2025-01-20", today=date(2026, 6, 1))
        assert isinstance(result, ExpirationValidationResult)

    def test_passed_is_true_when_not_expired(self) -> None:
        result = _validate(signed_date="2025-01-20", today=date(2026, 6, 1))
        assert result.passed is True

    def test_reason_is_empty_when_passed(self) -> None:
        result = _validate(signed_date="2025-01-20", today=date(2026, 6, 1))
        assert result.reason == ""

    def test_checked_on_first_day_of_validity(self) -> None:
        """Form is valid on the day it is signed."""
        result = _validate(signed_date="2025-01-20", today=date(2025, 1, 20))
        assert result.passed is True

    def test_checked_on_exact_valid_through_date(self) -> None:
        """The day of expiry (Dec 31) is still within the validity window."""
        result = _validate(signed_date="2025-01-20", today=date(2028, 12, 31))
        assert result.passed is True

    def test_signed_dec_31_checked_before_expiry(self) -> None:
        """Signed Dec 31 2022 → valid through 2025-12-31; check mid-2025 → passes."""
        result = _validate(signed_date="2022-12-31", today=date(2025, 6, 15))
        assert result.passed is True

    def test_signed_dec_31_checked_on_last_valid_day(self) -> None:
        """Signed Dec 31 2022 → valid through 2025-12-31; check on 2025-12-31 → passes."""
        result = _validate(signed_date="2022-12-31", today=date(2025, 12, 31))
        assert result.passed is True


# ===========================================================================
# Expired forms
# ===========================================================================


class TestExpirationValidatorExpired:
    """Forms past valid_through must be flagged as expired."""

    def test_passed_is_false_when_expired(self) -> None:
        # Signed 2025-01-20, valid through 2028-12-31; check on 2029-01-01
        result = _validate(signed_date="2025-01-20", today=date(2029, 1, 1))
        assert result.passed is False

    def test_reason_is_non_empty_when_expired(self) -> None:
        result = _validate(signed_date="2025-01-20", today=date(2029, 1, 1))
        assert result.reason != ""

    def test_reason_mentions_expired(self) -> None:
        result = _validate(signed_date="2025-01-20", today=date(2029, 1, 1))
        assert "expired" in result.reason.lower()

    def test_reason_mentions_valid_through_date(self) -> None:
        result = _validate(signed_date="2025-01-20", today=date(2029, 1, 1))
        assert "2028-12-31" in result.reason

    def test_expired_one_day_after_valid_through(self) -> None:
        """The day after valid_through is the first day the form is invalid."""
        result = _validate(signed_date="2025-01-20", today=date(2029, 1, 1))
        assert result.passed is False

    def test_expired_dec_31_boundary(self) -> None:
        """Signed Dec 31 2022 → valid_through 2025-12-31; check 2026-01-01 → expired."""
        result = _validate(signed_date="2022-12-31", today=date(2026, 1, 1))
        assert result.passed is False

    def test_expired_valid_through_still_returned_when_expired(self) -> None:
        """valid_through is still populated even when the form has expired."""
        result = _validate(signed_date="2022-12-31", today=date(2026, 1, 1))
        assert result.valid_through == date(2025, 12, 31)

    def test_old_form_is_expired(self) -> None:
        """A form signed in 2018 is clearly expired by 2025."""
        result = _validate(signed_date="2018-05-10", today=date(2025, 1, 1))
        assert result.passed is False
        assert result.valid_through == date(2021, 12, 31)


# ===========================================================================
# Missing / malformed signed_date — flag, NOT a crash
# ===========================================================================


class TestExpirationValidatorMissingSigned:
    """Absent or unparseable signed_date → failure, never an exception."""

    # --- must NOT raise ---

    def test_none_does_not_raise(self) -> None:
        result = _validate(signed_date=None, today=date(2025, 6, 1))
        assert isinstance(result, ExpirationValidationResult)

    def test_empty_string_does_not_raise(self) -> None:
        result = _validate(signed_date="", today=date(2025, 6, 1))
        assert isinstance(result, ExpirationValidationResult)

    def test_whitespace_only_does_not_raise(self) -> None:
        result = _validate(signed_date="   ", today=date(2025, 6, 1))
        assert isinstance(result, ExpirationValidationResult)

    def test_garbage_string_does_not_raise(self) -> None:
        result = _validate(signed_date="not-a-date", today=date(2025, 6, 1))
        assert isinstance(result, ExpirationValidationResult)

    def test_us_format_does_not_raise(self) -> None:
        result = _validate(signed_date="01/20/2025", today=date(2025, 6, 1))
        assert isinstance(result, ExpirationValidationResult)

    def test_year_only_does_not_raise(self) -> None:
        result = _validate(signed_date="2025", today=date(2025, 6, 1))
        assert isinstance(result, ExpirationValidationResult)

    def test_invalid_calendar_date_does_not_raise(self) -> None:
        result = _validate(signed_date="2025-02-30", today=date(2025, 6, 1))
        assert isinstance(result, ExpirationValidationResult)

    # --- must return passed=False ---

    def test_none_fails(self) -> None:
        result = _validate(signed_date=None, today=date(2025, 6, 1))
        assert result.passed is False

    def test_empty_string_fails(self) -> None:
        result = _validate(signed_date="", today=date(2025, 6, 1))
        assert result.passed is False

    def test_whitespace_only_fails(self) -> None:
        result = _validate(signed_date="   ", today=date(2025, 6, 1))
        assert result.passed is False

    def test_garbage_string_fails(self) -> None:
        result = _validate(signed_date="not-a-date", today=date(2025, 6, 1))
        assert result.passed is False

    def test_us_format_fails(self) -> None:
        result = _validate(signed_date="01/20/2025", today=date(2025, 6, 1))
        assert result.passed is False

    def test_year_only_fails(self) -> None:
        result = _validate(signed_date="2025", today=date(2025, 6, 1))
        assert result.passed is False

    def test_invalid_calendar_date_fails(self) -> None:
        result = _validate(signed_date="2025-02-30", today=date(2025, 6, 1))
        assert result.passed is False

    # --- valid_through is None when unparseable ---

    def test_valid_through_is_none_when_signed_date_is_none(self) -> None:
        result = _validate(signed_date=None, today=date(2025, 6, 1))
        assert result.valid_through is None

    def test_valid_through_is_none_when_signed_date_is_garbage(self) -> None:
        result = _validate(signed_date="bad", today=date(2025, 6, 1))
        assert result.valid_through is None

    # --- reason strings mention the problem ---

    def test_reason_mentions_missing_when_none(self) -> None:
        result = _validate(signed_date=None, today=date(2025, 6, 1))
        assert "missing" in result.reason.lower() or "cannot be determined" in result.reason.lower()

    def test_reason_mentions_bad_value_when_garbage(self) -> None:
        result = _validate(signed_date="not-a-date", today=date(2025, 6, 1))
        assert "not-a-date" in result.reason

    def test_reason_mentions_expected_format_when_malformed(self) -> None:
        result = _validate(signed_date="01/20/2025", today=date(2025, 6, 1))
        assert "YYYY-MM-DD" in result.reason
