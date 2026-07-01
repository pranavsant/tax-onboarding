"""Unit tests for ValidateTreatyClaimUseCase.

Verifies that the use case correctly translates domain results into
TreatyClaimValidationResultDTO instances, and enforces form_type guard.

Acceptance-criteria cases:
  AC #2 — Brazil + blank Part II → passed=True, no flag
  AC #3 — Treaty country (Germany) + blank Part II → passed=False, flagged
  AC #4 — Treaty country + completed Part II → passed=True, reduced rate applied

Additional cases:
  - Result type is always TreatyClaimValidationResultDTO
  - W-9 form_type raises ValueError
  - Missing country_of_citizenship raises ValueError
  - Partial Part II (missing mandatory field) → passed=False
  - applied_withholding_rate_pct is None when not applicable
"""
from __future__ import annotations

import pytest

from src.application.dto.tax_form_dto import ParsedFormFieldsDTO, TreatyClaimValidationResultDTO
from src.application.use_cases.validate_treaty_claim import ValidateTreatyClaimUseCase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _w8ben_dto(**kwargs) -> ParsedFormFieldsDTO:
    """Return a minimal W-8BEN ParsedFormFieldsDTO; override fields via kwargs."""
    defaults: dict = {
        "form_type": "W-8BEN",
        "name": "Mariana Costa Ribeiro",
        "country_of_citizenship": "Brazil",
        "permanent_address": "Rua das Margaridas, 112",
        "permanent_address_city_country": "Rio de Janeiro, RJ, Brazil",
        "foreign_tin": "219.871.330-44",
        # Part II — all blank by default
        "treaty_country": None,
        "treaty_article": None,
        "withholding_rate": None,
        "income_type": None,
        "treaty_conditions": None,
    }
    defaults.update(kwargs)
    return ParsedFormFieldsDTO(**defaults)


def _germany_dto_completed() -> ParsedFormFieldsDTO:
    """Return a W-8BEN DTO for a German investor with a completed Part II."""
    return _w8ben_dto(
        name="Hans Müller",
        country_of_citizenship="Germany",
        treaty_country="Germany",
        treaty_article="Article 10",
        withholding_rate="15%",
        income_type="Dividends",
        treaty_conditions=None,
    )


# ===========================================================================
# Return type
# ===========================================================================


class TestValidateTreatyClaimUseCaseReturnType:
    def test_returns_treaty_claim_validation_result_dto(self) -> None:
        uc = ValidateTreatyClaimUseCase()
        result = uc.execute(_w8ben_dto())
        assert isinstance(result, TreatyClaimValidationResultDTO)


# ===========================================================================
# Acceptance criterion #2: Brazil + blank Part II → correct, no flag
# ===========================================================================


class TestAcceptanceCriteriaBrazilBlankPartII:
    """Brazil has no US income-tax treaty; blank Part II is correct behaviour."""

    def setup_method(self) -> None:
        self.uc = ValidateTreatyClaimUseCase()

    def test_brazil_blank_part_ii_passes(self) -> None:
        """AC #2: Brazil + blank Part II → validated as correct, no flag."""
        result = self.uc.execute(_w8ben_dto(country_of_citizenship="Brazil"))
        assert result.passed is True

    def test_reason_is_empty_for_brazil_blank(self) -> None:
        result = self.uc.execute(_w8ben_dto(country_of_citizenship="Brazil"))
        assert result.reason == ""

    def test_applied_withholding_rate_is_none_for_brazil_blank(self) -> None:
        result = self.uc.execute(_w8ben_dto(country_of_citizenship="Brazil"))
        assert result.applied_withholding_rate_pct is None


# ===========================================================================
# Acceptance criterion #3: Treaty country + blank Part II → flagged for review
# ===========================================================================


class TestAcceptanceCriteriaTreatyCountryBlankPartII:
    """Germany (treaty country) with blank Part II must be flagged for review."""

    def setup_method(self) -> None:
        self.uc = ValidateTreatyClaimUseCase()

    def test_germany_blank_part_ii_fails(self) -> None:
        """AC #3: Treaty country + blank Part II → flagged for review."""
        result = self.uc.execute(
            _w8ben_dto(country_of_citizenship="Germany")
        )
        assert result.passed is False

    def test_reason_is_non_empty(self) -> None:
        result = self.uc.execute(
            _w8ben_dto(country_of_citizenship="Germany")
        )
        assert result.reason != ""

    def test_reason_mentions_germany(self) -> None:
        result = self.uc.execute(
            _w8ben_dto(country_of_citizenship="Germany")
        )
        assert "Germany" in result.reason

    def test_reason_mentions_treaty(self) -> None:
        result = self.uc.execute(
            _w8ben_dto(country_of_citizenship="Germany")
        )
        assert "treaty" in result.reason.lower()

    def test_applied_withholding_rate_is_none_when_flagged(self) -> None:
        result = self.uc.execute(
            _w8ben_dto(country_of_citizenship="Germany")
        )
        assert result.applied_withholding_rate_pct is None

    def test_israel_blank_part_ii_also_fails(self) -> None:
        result = self.uc.execute(
            _w8ben_dto(country_of_citizenship="Israel")
        )
        assert result.passed is False

    def test_uk_blank_part_ii_fails(self) -> None:
        result = self.uc.execute(
            _w8ben_dto(country_of_citizenship="United Kingdom")
        )
        assert result.passed is False


# ===========================================================================
# Acceptance criterion #4: Treaty country + completed Part II → pass, rate applied
# ===========================================================================


class TestAcceptanceCriteriaTreatyCountryCompletedPartII:
    """Germany with a complete Part II must pass with the 15 % reduced rate."""

    def setup_method(self) -> None:
        self.uc = ValidateTreatyClaimUseCase()

    def test_germany_completed_part_ii_passes(self) -> None:
        """AC #4: Treaty country + completed Part II → validated, rate applied."""
        result = self.uc.execute(_germany_dto_completed())
        assert result.passed is True

    def test_reason_is_empty_on_pass(self) -> None:
        result = self.uc.execute(_germany_dto_completed())
        assert result.reason == ""

    def test_applied_withholding_rate_is_15_for_germany(self) -> None:
        """AC #4: reduced withholding rate is 15 % for Germany."""
        result = self.uc.execute(_germany_dto_completed())
        assert result.applied_withholding_rate_pct == 15.0

    def test_israel_completed_part_ii_passes(self) -> None:
        result = self.uc.execute(
            _w8ben_dto(
                country_of_citizenship="Israel",
                treaty_country="Israel",
                treaty_article="Article 10",
                withholding_rate="15%",
            )
        )
        assert result.passed is True
        assert result.applied_withholding_rate_pct == 15.0

    def test_three_mandatory_fields_sufficient(self) -> None:
        """income_type and treaty_conditions are optional for a valid claim."""
        result = self.uc.execute(
            _w8ben_dto(
                country_of_citizenship="Germany",
                treaty_country="Germany",
                treaty_article="Article 10",
                withholding_rate="15%",
                income_type=None,
                treaty_conditions=None,
            )
        )
        assert result.passed is True
        assert result.applied_withholding_rate_pct == 15.0


# ===========================================================================
# Partial Part II (treaty country but missing mandatory fields)
# ===========================================================================


class TestPartialPartII:
    """Partial Part II on a treaty-country form should be flagged."""

    def setup_method(self) -> None:
        self.uc = ValidateTreatyClaimUseCase()

    def test_missing_treaty_article_fails(self) -> None:
        result = self.uc.execute(
            _w8ben_dto(
                country_of_citizenship="Germany",
                treaty_country="Germany",
                treaty_article=None,
                withholding_rate="15%",
            )
        )
        assert result.passed is False

    def test_missing_withholding_rate_fails(self) -> None:
        result = self.uc.execute(
            _w8ben_dto(
                country_of_citizenship="Germany",
                treaty_country="Germany",
                treaty_article="Article 10",
                withholding_rate=None,
            )
        )
        assert result.passed is False

    def test_partial_does_not_raise(self) -> None:
        result = self.uc.execute(
            _w8ben_dto(
                country_of_citizenship="Germany",
                treaty_country="Germany",
                treaty_article=None,
                withholding_rate=None,
            )
        )
        assert isinstance(result, TreatyClaimValidationResultDTO)


# ===========================================================================
# Error handling
# ===========================================================================


class TestValidateTreatyClaimUseCaseErrors:
    def test_raises_value_error_for_w9_form_type(self) -> None:
        uc = ValidateTreatyClaimUseCase()
        dto = ParsedFormFieldsDTO(
            form_type="W-9",
            name="James Whitfield",
            tin="412-88-7693",
            tin_type="SSN",
        )
        with pytest.raises(ValueError, match="W-8BEN"):
            uc.execute(dto)

    def test_raises_value_error_for_missing_country(self) -> None:
        uc = ValidateTreatyClaimUseCase()
        dto = _w8ben_dto(country_of_citizenship=None)
        with pytest.raises(ValueError):
            uc.execute(dto)

    def test_raises_value_error_for_empty_country(self) -> None:
        uc = ValidateTreatyClaimUseCase()
        dto = _w8ben_dto(country_of_citizenship="")
        with pytest.raises(ValueError):
            uc.execute(dto)
