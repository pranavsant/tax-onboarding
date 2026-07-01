"""Unit tests for ValidateTINUseCase.

Verifies that the use case correctly dispatches to the right TINValidator
method based on form_type and returns TINValidationResultDTO instances.

Cases covered:
  W-9:
    - Valid SSN (412-88-7693) → passes
    - Valid EIN → passes
    - Missing TIN → fails
    - Malformed TIN → fails (no crash)
    - Result type is always TINValidationResultDTO

  W-8BEN:
    - Valid foreign TIN (219.871.330-44) → passes
    - Missing foreign TIN → fails
    - ftin_not_required=True → passes regardless of foreign_tin value
    - Result type is always TINValidationResultDTO

  Error handling:
    - Unknown form_type raises ValueError
"""
from __future__ import annotations

import pytest

from src.application.dto.tax_form_dto import ParsedFormFieldsDTO, TINValidationResultDTO
from src.application.use_cases.validate_tin import ValidateTINUseCase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _w9_dto(**kwargs) -> ParsedFormFieldsDTO:
    """Minimal W-9 ParsedFormFieldsDTO; TIN-related fields are overridden via kwargs."""
    defaults: dict = {
        "form_type": "W-9",
        "name": "James Whitfield",
        "federal_tax_classification": "Individual/sole proprietor",
        "address": "7842 Birchwood Lane",
        "city_state_zip": "Dallas, TX 75201",
        "tin": "412-88-7693",
        "tin_type": "SSN",
    }
    defaults.update(kwargs)
    return ParsedFormFieldsDTO(**defaults)


def _w8ben_dto(**kwargs) -> ParsedFormFieldsDTO:
    """Minimal W-8BEN ParsedFormFieldsDTO; TIN-related fields are overridden via kwargs."""
    defaults: dict = {
        "form_type": "W-8BEN",
        "name": "Mariana Costa Ribeiro",
        "country_of_citizenship": "Brazil",
        "permanent_address": "Rua das Margaridas, 112",
        "permanent_address_city_country": "Rio de Janeiro, RJ, Brazil",
        "foreign_tin": "219.871.330-44",
    }
    defaults.update(kwargs)
    return ParsedFormFieldsDTO(**defaults)


# ===========================================================================
# Return type
# ===========================================================================


class TestValidateTINUseCaseReturnType:
    def test_w9_returns_tin_validation_result_dto(self) -> None:
        uc = ValidateTINUseCase()
        result = uc.execute(_w9_dto())
        assert isinstance(result, TINValidationResultDTO)

    def test_w8ben_returns_tin_validation_result_dto(self) -> None:
        uc = ValidateTINUseCase()
        result = uc.execute(_w8ben_dto())
        assert isinstance(result, TINValidationResultDTO)


# ===========================================================================
# W-9 cases
# ===========================================================================


class TestValidateTINUseCaseW9:
    """TIN validation on W-9 ParsedFormFieldsDTOs."""

    def setup_method(self) -> None:
        self.uc = ValidateTINUseCase()

    def test_passes_for_acceptance_criteria_ssn(self) -> None:
        """412-88-7693 is the acceptance-criteria W-9 SSN."""
        result = self.uc.execute(_w9_dto(tin="412-88-7693", tin_type="SSN"))
        assert result.passed is True
        assert result.reason == ""

    def test_passes_for_valid_ein(self) -> None:
        result = self.uc.execute(_w9_dto(tin="12-3456789", tin_type="EIN"))
        assert result.passed is True

    def test_passes_for_another_valid_ssn(self) -> None:
        result = self.uc.execute(_w9_dto(tin="123-45-6789", tin_type="SSN"))
        assert result.passed is True

    def test_fails_when_tin_is_none(self) -> None:
        result = self.uc.execute(_w9_dto(tin=None))
        assert result.passed is False
        assert result.reason != ""

    def test_fails_when_tin_is_empty_string(self) -> None:
        result = self.uc.execute(_w9_dto(tin=""))
        assert result.passed is False

    def test_fails_when_tin_is_malformed(self) -> None:
        result = self.uc.execute(_w9_dto(tin="412887693"))
        assert result.passed is False
        assert result.reason != ""

    def test_malformed_tin_does_not_raise(self) -> None:
        result = self.uc.execute(_w9_dto(tin="not-a-tin"))
        assert isinstance(result, TINValidationResultDTO)

    def test_reason_contains_bad_value_on_format_error(self) -> None:
        result = self.uc.execute(_w9_dto(tin="WRONG-FORMAT"))
        assert "WRONG-FORMAT" in result.reason

    def test_reason_mentions_ssn_format(self) -> None:
        result = self.uc.execute(_w9_dto(tin="bad"))
        assert "SSN" in result.reason or "XXX-XX-XXXX" in result.reason


# ===========================================================================
# W-8BEN cases
# ===========================================================================


class TestValidateTINUseCaseW8BEN:
    """TIN validation on W-8BEN ParsedFormFieldsDTOs."""

    def setup_method(self) -> None:
        self.uc = ValidateTINUseCase()

    def test_passes_for_acceptance_criteria_foreign_tin(self) -> None:
        """219.871.330-44 is the acceptance-criteria Brazilian CPF."""
        result = self.uc.execute(_w8ben_dto(foreign_tin="219.871.330-44"))
        assert result.passed is True
        assert result.reason == ""

    def test_passes_for_alphanumeric_foreign_tin(self) -> None:
        result = self.uc.execute(_w8ben_dto(foreign_tin="A1234567B"))
        assert result.passed is True

    def test_passes_for_numeric_foreign_tin(self) -> None:
        result = self.uc.execute(_w8ben_dto(foreign_tin="1234567890"))
        assert result.passed is True

    def test_fails_when_foreign_tin_is_none(self) -> None:
        result = self.uc.execute(_w8ben_dto(foreign_tin=None))
        assert result.passed is False
        assert result.reason != ""

    def test_fails_when_foreign_tin_is_empty(self) -> None:
        result = self.uc.execute(_w8ben_dto(foreign_tin=""))
        assert result.passed is False

    def test_fails_when_foreign_tin_is_whitespace_only(self) -> None:
        result = self.uc.execute(_w8ben_dto(foreign_tin="   "))
        assert result.passed is False

    def test_reason_mentions_missing_when_none(self) -> None:
        result = self.uc.execute(_w8ben_dto(foreign_tin=None))
        assert "missing" in result.reason.lower()

    def test_missing_foreign_tin_does_not_raise(self) -> None:
        result = self.uc.execute(_w8ben_dto(foreign_tin=None))
        assert isinstance(result, TINValidationResultDTO)

    # --- ftin_not_required bypass ---

    def test_passes_when_ftin_not_required_is_true(self) -> None:
        """When ftin_not_required=True the foreign TIN check is skipped."""
        result = self.uc.execute(
            _w8ben_dto(foreign_tin=None, ftin_not_required=True)
        )
        assert result.passed is True
        assert result.reason == ""

    def test_passes_when_ftin_not_required_true_and_tin_empty(self) -> None:
        result = self.uc.execute(
            _w8ben_dto(foreign_tin="", ftin_not_required=True)
        )
        assert result.passed is True

    def test_ftin_not_required_false_still_validates(self) -> None:
        """ftin_not_required=False does not bypass the check."""
        result = self.uc.execute(
            _w8ben_dto(foreign_tin=None, ftin_not_required=False)
        )
        assert result.passed is False

    def test_ftin_not_required_none_still_validates(self) -> None:
        """ftin_not_required=None does not bypass the check."""
        result = self.uc.execute(
            _w8ben_dto(foreign_tin=None, ftin_not_required=None)
        )
        assert result.passed is False


# ===========================================================================
# Unknown form type
# ===========================================================================


class TestValidateTINUseCaseUnknownFormType:
    def test_raises_value_error_for_unknown_form_type(self) -> None:
        uc = ValidateTINUseCase()
        dto = ParsedFormFieldsDTO(form_type="W-4", name="Someone")
        with pytest.raises(ValueError, match="Unsupported form_type"):
            uc.execute(dto)
