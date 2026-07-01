"""Unit tests for TINValidator domain service.

Covers:
  validate_us_tin  (W-9 path)
    - Valid SSN in XXX-XX-XXXX format (including acceptance-criteria value 412-88-7693)
    - Valid EIN in XX-XXXXXXX format
    - Missing / empty TIN → fails
    - Wrong format (too few digits, letters, etc.) → fails (flag, NOT crash)
    - Leading/trailing whitespace is stripped before validation

  validate_foreign_tin  (W-8BEN path)
    - Present non-empty value → passes (including acceptance-criteria value 219.871.330-44)
    - Brazilian CPF format with dots/dash → passes (format tolerance)
    - Missing / None / blank → fails
    - Value with no alphanumeric characters → fails
"""
from __future__ import annotations

import pytest

from src.domain.services.tin_validator import TINValidationResult, TINValidator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_us(tin: str | None) -> TINValidationResult:
    return TINValidator.validate_us_tin(tin)


def _validate_foreign(foreign_tin: str | None) -> TINValidationResult:
    return TINValidator.validate_foreign_tin(foreign_tin)


# ===========================================================================
# validate_us_tin — happy path
# ===========================================================================


class TestValidateUSTINPassing:
    """Validation passes for well-formed SSN and EIN values."""

    def test_returns_tin_validation_result(self) -> None:
        result = _validate_us("412-88-7693")
        assert isinstance(result, TINValidationResult)

    def test_passed_is_true_for_valid_ssn(self) -> None:
        """Acceptance-criteria SSN: 412-88-7693."""
        result = _validate_us("412-88-7693")
        assert result.passed is True

    def test_reason_is_empty_on_pass(self) -> None:
        result = _validate_us("412-88-7693")
        assert result.reason == ""

    def test_passes_for_another_valid_ssn(self) -> None:
        result = _validate_us("123-45-6789")
        assert result.passed is True

    def test_passes_for_valid_ein(self) -> None:
        result = _validate_us("12-3456789")
        assert result.passed is True

    def test_passes_for_ssn_with_surrounding_whitespace(self) -> None:
        """Whitespace around the TIN is stripped before checking."""
        result = _validate_us("  412-88-7693  ")
        assert result.passed is True


# ===========================================================================
# validate_us_tin — failure cases
# ===========================================================================


class TestValidateUSTINFailing:
    """Validation fails for missing or malformed TINs — flag, not crash."""

    def test_fails_when_tin_is_none(self) -> None:
        result = _validate_us(None)
        assert result.passed is False

    def test_fails_when_tin_is_empty_string(self) -> None:
        result = _validate_us("")
        assert result.passed is False

    def test_fails_when_tin_is_whitespace_only(self) -> None:
        result = _validate_us("   ")
        assert result.passed is False

    def test_reason_mentions_missing_when_none(self) -> None:
        result = _validate_us(None)
        assert "missing" in result.reason.lower()

    def test_reason_is_non_empty_on_failure(self) -> None:
        result = _validate_us(None)
        assert result.reason != ""

    # --- malformed but syntactically close values ---

    def test_fails_for_ssn_without_dashes(self) -> None:
        result = _validate_us("412887693")
        assert result.passed is False

    def test_fails_for_ssn_with_wrong_grouping(self) -> None:
        """4-2-4 grouping is not XXX-XX-XXXX."""
        result = _validate_us("4128-8-7693")
        assert result.passed is False

    def test_fails_for_letters(self) -> None:
        result = _validate_us("AAA-BB-CCCC")
        assert result.passed is False

    def test_fails_for_partial_ssn(self) -> None:
        result = _validate_us("412-88")
        assert result.passed is False

    def test_reason_mentions_tin_value_on_format_error(self) -> None:
        result = _validate_us("412887693")
        assert "412887693" in result.reason

    def test_reason_mentions_ssn_format_on_format_error(self) -> None:
        result = _validate_us("bad-tin")
        assert "SSN" in result.reason or "XXX-XX-XXXX" in result.reason

    # --- does NOT raise ---

    def test_bad_format_does_not_raise(self) -> None:
        result = _validate_us("not-a-tin")
        assert isinstance(result, TINValidationResult)

    def test_none_does_not_raise(self) -> None:
        result = _validate_us(None)
        assert isinstance(result, TINValidationResult)


# ===========================================================================
# validate_foreign_tin — happy path
# ===========================================================================


class TestValidateForeignTINPassing:
    """Validation passes when a foreign TIN is present and non-empty."""

    def test_returns_tin_validation_result(self) -> None:
        result = _validate_foreign("219.871.330-44")
        assert isinstance(result, TINValidationResult)

    def test_passed_is_true_for_acceptance_criteria_value(self) -> None:
        """Acceptance-criteria Brazilian CPF: 219.871.330-44."""
        result = _validate_foreign("219.871.330-44")
        assert result.passed is True

    def test_reason_is_empty_on_pass(self) -> None:
        result = _validate_foreign("219.871.330-44")
        assert result.reason == ""

    def test_passes_for_alphanumeric_tin(self) -> None:
        result = _validate_foreign("A1234567B")
        assert result.passed is True

    def test_passes_for_numeric_only_tin(self) -> None:
        result = _validate_foreign("1234567890")
        assert result.passed is True

    def test_passes_for_tin_with_whitespace(self) -> None:
        """Surrounding whitespace is stripped; inner content still valid."""
        result = _validate_foreign("  219.871.330-44  ")
        assert result.passed is True

    def test_passes_for_tin_with_slashes(self) -> None:
        """Some countries use slashes in TIN formats."""
        result = _validate_foreign("DE/12345/2024")
        assert result.passed is True

    def test_passes_for_short_alphanumeric_tin(self) -> None:
        """Single character is still considered present."""
        result = _validate_foreign("X")
        assert result.passed is True


# ===========================================================================
# validate_foreign_tin — failure cases
# ===========================================================================


class TestValidateForeignTINFailing:
    """Validation fails when foreign TIN is absent or contains no alphanumeric chars."""

    def test_fails_when_foreign_tin_is_none(self) -> None:
        result = _validate_foreign(None)
        assert result.passed is False

    def test_fails_when_foreign_tin_is_empty_string(self) -> None:
        result = _validate_foreign("")
        assert result.passed is False

    def test_fails_when_foreign_tin_is_whitespace_only(self) -> None:
        result = _validate_foreign("    ")
        assert result.passed is False

    def test_fails_when_foreign_tin_has_no_alphanumeric(self) -> None:
        """A string of only punctuation has no valid TIN content."""
        result = _validate_foreign("---")
        assert result.passed is False

    def test_reason_is_non_empty_on_failure(self) -> None:
        result = _validate_foreign(None)
        assert result.reason != ""

    def test_reason_mentions_missing_when_none(self) -> None:
        result = _validate_foreign(None)
        assert "missing" in result.reason.lower()

    def test_reason_mentions_foreign_tin(self) -> None:
        result = _validate_foreign(None)
        assert "foreign tin" in result.reason.lower() or "foreign tax" in result.reason.lower()

    # --- does NOT raise ---

    def test_none_does_not_raise(self) -> None:
        result = _validate_foreign(None)
        assert isinstance(result, TINValidationResult)

    def test_empty_string_does_not_raise(self) -> None:
        result = _validate_foreign("")
        assert isinstance(result, TINValidationResult)

    def test_punctuation_only_does_not_raise(self) -> None:
        result = _validate_foreign("...")
        assert isinstance(result, TINValidationResult)
