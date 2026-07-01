"""Unit tests for SignatureValidator domain service.

Covers the following scenarios for both W-9 and W-8BEN (the validator is
form-type-agnostic — the same rules apply to both):

  Signature present + valid date      → passes
  Signature absent (False)            → fails with descriptive reason
  Signature indeterminate (None)      → fails with descriptive reason
  Signature present + date missing    → fails
  Signature present + date malformed  → fails (flag, NOT a crash)
  Signature present + date invalid    → fails (e.g. Feb 30)
"""
from __future__ import annotations

from src.domain.services.signature_validator import SignatureValidationResult, SignatureValidator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate(
    signature_present: bool | None = None,
    signature_date: str | None = None,
) -> SignatureValidationResult:
    return SignatureValidator.validate(
        signature_present=signature_present,
        signature_date=signature_date,
    )


# ===========================================================================
# Happy path — signature present and date valid
# ===========================================================================


class TestSignatureValidatorPassing:
    """Validation passes when both signature and date are present and valid."""

    def test_returns_signature_validation_result(self) -> None:
        result = _validate(signature_present=True, signature_date="2024-03-15")
        assert isinstance(result, SignatureValidationResult)

    def test_passed_is_true(self) -> None:
        result = _validate(signature_present=True, signature_date="2024-03-15")
        assert result.passed is True

    def test_reason_is_empty_string_on_pass(self) -> None:
        result = _validate(signature_present=True, signature_date="2024-03-15")
        assert result.reason == ""

    def test_passes_for_w9_style_date(self) -> None:
        """W-9 typical date — should pass."""
        result = _validate(signature_present=True, signature_date="2023-12-31")
        assert result.passed is True

    def test_passes_for_w8ben_style_date(self) -> None:
        """W-8BEN typical date — same validator, should pass."""
        result = _validate(signature_present=True, signature_date="2024-01-08")
        assert result.passed is True

    def test_passes_for_date_with_leading_or_trailing_whitespace(self) -> None:
        """Whitespace around the date string should be stripped and still pass."""
        result = _validate(signature_present=True, signature_date="  2024-06-20  ")
        assert result.passed is True


# ===========================================================================
# Signature missing / indeterminate
# ===========================================================================


class TestSignatureValidatorMissingSignature:
    """Validation fails when signature_present is False or None."""

    def test_fails_when_signature_present_is_false(self) -> None:
        result = _validate(signature_present=False, signature_date="2024-03-15")
        assert result.passed is False

    def test_reason_mentions_blank_when_false(self) -> None:
        result = _validate(signature_present=False, signature_date="2024-03-15")
        assert "blank" in result.reason.lower() or "missing" in result.reason.lower()

    def test_fails_when_signature_present_is_none(self) -> None:
        result = _validate(signature_present=None, signature_date="2024-03-15")
        assert result.passed is False

    def test_reason_mentions_indeterminate_when_none(self) -> None:
        result = _validate(signature_present=None, signature_date="2024-03-15")
        assert "absent" in result.reason.lower() or "illegible" in result.reason.lower() or \
               "could not be determined" in result.reason.lower()

    def test_fails_regardless_of_date_when_no_signature(self) -> None:
        """Even a perfectly valid date cannot compensate for a missing signature."""
        result = _validate(signature_present=False, signature_date="2024-03-15")
        assert result.passed is False

    def test_reason_is_non_empty_when_signature_missing(self) -> None:
        result = _validate(signature_present=False, signature_date="2024-03-15")
        assert result.reason != ""


# ===========================================================================
# Signature date missing
# ===========================================================================


class TestSignatureValidatorMissingDate:
    """Validation fails when the date is absent even if signature is present."""

    def test_fails_when_signature_date_is_none(self) -> None:
        result = _validate(signature_present=True, signature_date=None)
        assert result.passed is False

    def test_fails_when_signature_date_is_empty_string(self) -> None:
        result = _validate(signature_present=True, signature_date="")
        assert result.passed is False

    def test_fails_when_signature_date_is_whitespace_only(self) -> None:
        result = _validate(signature_present=True, signature_date="   ")
        assert result.passed is False

    def test_reason_mentions_missing_date(self) -> None:
        result = _validate(signature_present=True, signature_date=None)
        assert "date" in result.reason.lower()
        assert "missing" in result.reason.lower() or "no date" in result.reason.lower()

    def test_reason_is_non_empty_when_date_missing(self) -> None:
        result = _validate(signature_present=True, signature_date=None)
        assert result.reason != ""


# ===========================================================================
# Malformed / unparseable dates — flag, NOT a crash
# ===========================================================================


class TestSignatureValidatorMalformedDate:
    """Malformed dates produce a failure result — they never raise an exception."""

    # --- these must NOT raise ---

    def test_garbage_string_does_not_raise(self) -> None:
        result = _validate(signature_present=True, signature_date="not-a-date")
        assert isinstance(result, SignatureValidationResult)

    def test_reversed_format_does_not_raise(self) -> None:
        result = _validate(signature_present=True, signature_date="15/03/2024")
        assert isinstance(result, SignatureValidationResult)

    def test_us_format_does_not_raise(self) -> None:
        result = _validate(signature_present=True, signature_date="03-15-2024")
        assert isinstance(result, SignatureValidationResult)

    def test_year_only_does_not_raise(self) -> None:
        result = _validate(signature_present=True, signature_date="2024")
        assert isinstance(result, SignatureValidationResult)

    def test_out_of_range_month_does_not_raise(self) -> None:
        result = _validate(signature_present=True, signature_date="2024-13-01")
        assert isinstance(result, SignatureValidationResult)

    def test_out_of_range_day_does_not_raise(self) -> None:
        result = _validate(signature_present=True, signature_date="2024-02-30")
        assert isinstance(result, SignatureValidationResult)

    # --- these must return passed=False ---

    def test_garbage_string_fails(self) -> None:
        result = _validate(signature_present=True, signature_date="not-a-date")
        assert result.passed is False

    def test_reversed_format_fails(self) -> None:
        result = _validate(signature_present=True, signature_date="15/03/2024")
        assert result.passed is False

    def test_us_format_fails(self) -> None:
        result = _validate(signature_present=True, signature_date="03-15-2024")
        assert result.passed is False

    def test_year_only_fails(self) -> None:
        result = _validate(signature_present=True, signature_date="2024")
        assert result.passed is False

    def test_out_of_range_month_fails(self) -> None:
        result = _validate(signature_present=True, signature_date="2024-13-01")
        assert result.passed is False

    def test_february_30_fails(self) -> None:
        result = _validate(signature_present=True, signature_date="2024-02-30")
        assert result.passed is False

    # --- reason strings for malformed dates ---

    def test_reason_mentions_bad_date_value(self) -> None:
        result = _validate(signature_present=True, signature_date="not-a-date")
        assert "not-a-date" in result.reason

    def test_reason_mentions_expected_format(self) -> None:
        result = _validate(signature_present=True, signature_date="03/15/2024")
        assert "YYYY-MM-DD" in result.reason

    def test_reason_is_non_empty_for_malformed_date(self) -> None:
        result = _validate(signature_present=True, signature_date="bad")
        assert result.reason != ""
