"""Unit tests for ValidateSignatureUseCase.

Verifies that the use case correctly translates domain results into
SignatureValidationResultDTO for both W-9 and W-8BEN ParsedFormFieldsDTOs.

Cases covered:
  - W-9: signature present + valid date  → passes
  - W-9: signature absent               → fails
  - W-9: signature present, date missing → fails
  - W-9: signature present, date malformed → fails (no crash)
  - W-8BEN: same four cases (form type does not change validation rules)
  - Result type is always SignatureValidationResultDTO
"""
from __future__ import annotations

from src.application.dto.tax_form_dto import ParsedFormFieldsDTO, SignatureValidationResultDTO
from src.application.use_cases.validate_signature import ValidateSignatureUseCase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _w9_dto(**kwargs) -> ParsedFormFieldsDTO:
    """Minimal W-9 ParsedFormFieldsDTO with signature fields overridden."""
    defaults = {
        "form_type": "W-9",
        "name": "Jane Doe",
        "federal_tax_classification": "Individual",
        "address": "123 Main St",
        "city_state_zip": "Springfield, IL 62701",
        "tin": "123-45-6789",
        "tin_type": "SSN",
    }
    defaults.update(kwargs)
    return ParsedFormFieldsDTO(**defaults)


def _w8ben_dto(**kwargs) -> ParsedFormFieldsDTO:
    """Minimal W-8BEN ParsedFormFieldsDTO with signature fields overridden."""
    defaults = {
        "form_type": "W-8BEN",
        "name": "Carlos Rodrigues",
        "country_of_citizenship": "Brazil",
        "permanent_address": "Rua das Flores, 42",
        "permanent_address_city_country": "São Paulo, SP, Brazil",
        "foreign_tin": "123.456.789-00",
    }
    defaults.update(kwargs)
    return ParsedFormFieldsDTO(**defaults)


# ===========================================================================
# Return type
# ===========================================================================


class TestValidateSignatureUseCaseReturnType:
    def test_returns_signature_validation_result_dto(self) -> None:
        uc = ValidateSignatureUseCase()
        result = uc.execute(_w9_dto(signature_present=True, signature_date="2024-03-15"))
        assert isinstance(result, SignatureValidationResultDTO)

    def test_w8ben_also_returns_signature_validation_result_dto(self) -> None:
        uc = ValidateSignatureUseCase()
        result = uc.execute(_w8ben_dto(signature_present=True, signature_date="2024-06-20"))
        assert isinstance(result, SignatureValidationResultDTO)


# ===========================================================================
# W-9 cases
# ===========================================================================


class TestValidateSignatureUseCaseW9:
    """Signature validation on W-9 ParsedFormFieldsDTOs."""

    def setup_method(self) -> None:
        self.uc = ValidateSignatureUseCase()

    def test_passes_when_signature_present_and_date_valid(self) -> None:
        result = self.uc.execute(_w9_dto(signature_present=True, signature_date="2024-03-15"))
        assert result.passed is True
        assert result.reason == ""

    def test_fails_when_signature_is_false(self) -> None:
        result = self.uc.execute(_w9_dto(signature_present=False, signature_date="2024-03-15"))
        assert result.passed is False
        assert result.reason != ""

    def test_fails_when_signature_is_none(self) -> None:
        result = self.uc.execute(_w9_dto(signature_present=None, signature_date="2024-03-15"))
        assert result.passed is False
        assert result.reason != ""

    def test_fails_when_date_is_none(self) -> None:
        result = self.uc.execute(_w9_dto(signature_present=True, signature_date=None))
        assert result.passed is False
        assert result.reason != ""

    def test_fails_when_date_is_malformed_no_crash(self) -> None:
        result = self.uc.execute(_w9_dto(signature_present=True, signature_date="not-a-date"))
        assert result.passed is False
        assert result.reason != ""

    def test_reason_contains_bad_date_on_malformed(self) -> None:
        result = self.uc.execute(_w9_dto(signature_present=True, signature_date="03/15/2024"))
        assert "03/15/2024" in result.reason

    def test_fails_when_date_out_of_range(self) -> None:
        """Feb 30 is syntactically close to ISO 8601 but is an invalid calendar date."""
        result = self.uc.execute(_w9_dto(signature_present=True, signature_date="2024-02-30"))
        assert result.passed is False


# ===========================================================================
# W-8BEN cases
# ===========================================================================


class TestValidateSignatureUseCaseW8BEN:
    """Signature validation on W-8BEN ParsedFormFieldsDTOs."""

    def setup_method(self) -> None:
        self.uc = ValidateSignatureUseCase()

    def test_passes_when_signature_present_and_date_valid(self) -> None:
        result = self.uc.execute(_w8ben_dto(signature_present=True, signature_date="2024-06-20"))
        assert result.passed is True
        assert result.reason == ""

    def test_fails_when_signature_is_false(self) -> None:
        result = self.uc.execute(_w8ben_dto(signature_present=False, signature_date="2024-06-20"))
        assert result.passed is False
        assert result.reason != ""

    def test_fails_when_signature_is_none(self) -> None:
        result = self.uc.execute(_w8ben_dto(signature_present=None, signature_date="2024-06-20"))
        assert result.passed is False
        assert result.reason != ""

    def test_fails_when_date_is_none(self) -> None:
        result = self.uc.execute(_w8ben_dto(signature_present=True, signature_date=None))
        assert result.passed is False
        assert result.reason != ""

    def test_fails_when_date_is_malformed_no_crash(self) -> None:
        result = self.uc.execute(_w8ben_dto(signature_present=True, signature_date="2024/06/20"))
        assert result.passed is False
        assert result.reason != ""

    def test_reason_mentions_format_on_malformed_date(self) -> None:
        result = self.uc.execute(_w8ben_dto(signature_present=True, signature_date="20-06-2024"))
        assert "YYYY-MM-DD" in result.reason

    def test_fails_when_date_out_of_range(self) -> None:
        result = self.uc.execute(_w8ben_dto(signature_present=True, signature_date="2024-13-01"))
        assert result.passed is False

    def test_both_signature_and_date_missing_fails(self) -> None:
        """When both are missing, the signature check fires first."""
        result = self.uc.execute(_w8ben_dto(signature_present=None, signature_date=None))
        assert result.passed is False
        assert result.reason != ""
