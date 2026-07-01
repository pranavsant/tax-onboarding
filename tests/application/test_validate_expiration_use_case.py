"""Unit tests for ValidateExpirationUseCase.

Verifies that the use case correctly translates domain results into
ExpirationValidationResultDTO for W-8BEN ParsedFormFieldsDTOs.

Cases covered:
  - Not expired: passed=True, reason="", valid_through set correctly
  - Expired:     passed=False, reason non-empty, valid_through still present
  - Missing signed date: passed=False, valid_through=None
  - Malformed signed date: passed=False, valid_through=None (no crash)
  - valid_through is returned as an ISO string (YYYY-MM-DD)
  - Acceptance criterion: signed 2025-01-20 → valid_through "2028-12-31"
"""
from __future__ import annotations

from datetime import date

from src.application.dto.tax_form_dto import ExpirationValidationResultDTO, ParsedFormFieldsDTO
from src.application.use_cases.validate_expiration import ValidateExpirationUseCase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _w8ben_dto(**kwargs) -> ParsedFormFieldsDTO:
    """Minimal W-8BEN ParsedFormFieldsDTO with overridable signature fields."""
    defaults = {
        "form_type": "W-8BEN",
        "name": "Mariana Costa Ribeiro",
        "country_of_citizenship": "Brazil",
        "permanent_address": "Rua das Flores, 42",
        "permanent_address_city_country": "São Paulo, SP, Brazil",
        "foreign_tin": "219.871.330-44",
    }
    defaults.update(kwargs)
    return ParsedFormFieldsDTO(**defaults)


# ===========================================================================
# Return type
# ===========================================================================


class TestValidateExpirationUseCaseReturnType:
    def test_returns_expiration_validation_result_dto(self) -> None:
        uc = ValidateExpirationUseCase()
        result = uc.execute(
            _w8ben_dto(signature_date="2025-01-20"),
            today=date(2026, 6, 1),
        )
        assert isinstance(result, ExpirationValidationResultDTO)


# ===========================================================================
# Acceptance criterion
# ===========================================================================


class TestValidateExpirationUseCaseAcceptanceCriteria:
    """signed_date 2025-01-20 → valid_through "2028-12-31"."""

    def test_valid_through_for_2025_01_20(self) -> None:
        uc = ValidateExpirationUseCase()
        result = uc.execute(
            _w8ben_dto(signature_date="2025-01-20"),
            today=date(2025, 1, 21),
        )
        assert result.valid_through == "2028-12-31"

    def test_passed_for_2025_01_20_checked_in_2026(self) -> None:
        uc = ValidateExpirationUseCase()
        result = uc.execute(
            _w8ben_dto(signature_date="2025-01-20"),
            today=date(2026, 6, 1),
        )
        assert result.passed is True
        assert result.valid_through == "2028-12-31"


# ===========================================================================
# Not expired
# ===========================================================================


class TestValidateExpirationUseCaseNotExpired:
    """Forms within their validity window pass."""

    def setup_method(self) -> None:
        self.uc = ValidateExpirationUseCase()

    def test_passes_when_not_expired(self) -> None:
        result = self.uc.execute(
            _w8ben_dto(signature_date="2025-06-15"),
            today=date(2026, 1, 1),
        )
        assert result.passed is True

    def test_reason_is_empty_when_passed(self) -> None:
        result = self.uc.execute(
            _w8ben_dto(signature_date="2025-06-15"),
            today=date(2026, 1, 1),
        )
        assert result.reason == ""

    def test_valid_through_is_iso_string(self) -> None:
        result = self.uc.execute(
            _w8ben_dto(signature_date="2025-06-15"),
            today=date(2026, 1, 1),
        )
        # Must be a string in YYYY-MM-DD format, not a date object
        assert isinstance(result.valid_through, str)
        assert result.valid_through == "2028-12-31"

    def test_passes_on_exact_valid_through_date(self) -> None:
        """The last day of validity is still valid."""
        result = self.uc.execute(
            _w8ben_dto(signature_date="2025-01-20"),
            today=date(2028, 12, 31),
        )
        assert result.passed is True

    def test_passes_when_signed_dec_31_checked_before_expiry(self) -> None:
        result = self.uc.execute(
            _w8ben_dto(signature_date="2022-12-31"),
            today=date(2025, 12, 31),
        )
        assert result.passed is True
        assert result.valid_through == "2025-12-31"


# ===========================================================================
# Expired
# ===========================================================================


class TestValidateExpirationUseCaseExpired:
    """Forms past valid_through are flagged as expired."""

    def setup_method(self) -> None:
        self.uc = ValidateExpirationUseCase()

    def test_fails_when_expired(self) -> None:
        result = self.uc.execute(
            _w8ben_dto(signature_date="2025-01-20"),
            today=date(2029, 1, 1),
        )
        assert result.passed is False

    def test_reason_non_empty_when_expired(self) -> None:
        result = self.uc.execute(
            _w8ben_dto(signature_date="2025-01-20"),
            today=date(2029, 1, 1),
        )
        assert result.reason != ""

    def test_reason_mentions_expired(self) -> None:
        result = self.uc.execute(
            _w8ben_dto(signature_date="2025-01-20"),
            today=date(2029, 1, 1),
        )
        assert "expired" in result.reason.lower()

    def test_valid_through_still_populated_when_expired(self) -> None:
        result = self.uc.execute(
            _w8ben_dto(signature_date="2025-01-20"),
            today=date(2029, 1, 1),
        )
        assert result.valid_through == "2028-12-31"

    def test_expired_one_day_after_valid_through(self) -> None:
        """One day after valid_through is expired."""
        result = self.uc.execute(
            _w8ben_dto(signature_date="2022-12-31"),
            today=date(2026, 1, 1),
        )
        assert result.passed is False
        assert result.valid_through == "2025-12-31"


# ===========================================================================
# Missing / malformed signed date
# ===========================================================================


class TestValidateExpirationUseCaseMissingDate:
    """Absent or unparseable signature_date → failure, no crash."""

    def setup_method(self) -> None:
        self.uc = ValidateExpirationUseCase()

    def test_fails_when_signature_date_is_none(self) -> None:
        result = self.uc.execute(
            _w8ben_dto(signature_date=None),
            today=date(2025, 6, 1),
        )
        assert result.passed is False

    def test_valid_through_is_none_when_signature_date_missing(self) -> None:
        result = self.uc.execute(
            _w8ben_dto(signature_date=None),
            today=date(2025, 6, 1),
        )
        assert result.valid_through is None

    def test_fails_when_signature_date_is_malformed_no_crash(self) -> None:
        result = self.uc.execute(
            _w8ben_dto(signature_date="01/20/2025"),
            today=date(2025, 6, 1),
        )
        assert isinstance(result, ExpirationValidationResultDTO)
        assert result.passed is False

    def test_valid_through_is_none_when_malformed(self) -> None:
        result = self.uc.execute(
            _w8ben_dto(signature_date="not-a-date"),
            today=date(2025, 6, 1),
        )
        assert result.valid_through is None

    def test_reason_non_empty_when_date_missing(self) -> None:
        result = self.uc.execute(
            _w8ben_dto(signature_date=None),
            today=date(2025, 6, 1),
        )
        assert result.reason != ""

    def test_reason_non_empty_when_malformed(self) -> None:
        result = self.uc.execute(
            _w8ben_dto(signature_date="not-a-date"),
            today=date(2025, 6, 1),
        )
        assert result.reason != ""
