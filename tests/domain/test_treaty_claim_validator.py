"""Unit tests for TreatyClaimValidator domain service.

Covers all three business-rule branches and edge cases:

  Branch 1 — Non-treaty country (Brazil)
    - Blank Part II → passes, no withholding rate returned
    - Filled Part II → fails (country has no treaty)

  Branch 2 — Treaty country (Germany) + blank Part II
    - All five fields None → fails, flagged for review
    - All five fields empty-string → fails (blank equivalent)
    - Whitespace-only values → fails (blank equivalent)

  Branch 3 — Treaty country + completed Part II
    - Three mandatory fields present → passes, reduced rate returned
    - All five fields present → passes, reduced rate returned
    - Missing treaty_article → fails (incomplete claim)
    - Missing withholding_rate → fails (incomplete claim)
    - Missing treaty_country → fails (incomplete claim)

  Acceptance-criteria cases:
    - Brazil + blank Part II → passes (AC #1 / #2)
    - Germany + blank Part II → fails / flagged (AC #3)
    - Germany + completed Part II → passes, 15 % rate (AC #4)

  Additional cases:
    - Israel → treaty country, same logic as Germany
    - United Kingdom / UK aliases → treaty country
    - Unknown country → treated as non-treaty country (30 %)

  Error handling:
    - Empty country_of_citizenship raises ValueError
    - None country_of_citizenship raises ValueError (propagated from TreatyTable)
"""
from __future__ import annotations

import pytest

from src.domain.services.treaty_claim_validator import (
    TreatyClaimValidationResult,
    TreatyClaimValidator,
)


# ---------------------------------------------------------------------------
# Helper — call validate() with sensible defaults
# ---------------------------------------------------------------------------


def _validate(
    country_of_citizenship: str = "Brazil",
    treaty_country: str | None = None,
    treaty_article: str | None = None,
    withholding_rate: str | None = None,
    income_type: str | None = None,
    treaty_conditions: str | None = None,
) -> TreatyClaimValidationResult:
    return TreatyClaimValidator.validate(
        country_of_citizenship=country_of_citizenship,
        treaty_country=treaty_country,
        treaty_article=treaty_article,
        withholding_rate=withholding_rate,
        income_type=income_type,
        treaty_conditions=treaty_conditions,
    )


# Completed Part II fixture fields for a German investor
_GERMANY_PART_II = {
    "treaty_country": "Germany",
    "treaty_article": "Article 10",
    "withholding_rate": "15%",
    "income_type": "Dividends",
    "treaty_conditions": None,
}


# ===========================================================================
# Return type
# ===========================================================================


class TestTreatyClaimValidatorReturnType:
    def test_returns_treaty_claim_validation_result(self) -> None:
        result = _validate("Brazil")
        assert isinstance(result, TreatyClaimValidationResult)


# ===========================================================================
# Branch 1 — Non-treaty country (Brazil) + blank Part II
# Acceptance criterion #2: Brazil + blank Part II → validated as correct, no flag
# ===========================================================================


class TestNonTreatyCountryBlankPartII:
    """Brazil (no treaty) with blank Part II should pass — this is correct behaviour."""

    def test_brazil_blank_part_ii_passes(self) -> None:
        """Acceptance criterion #2: Brazil + blank Part II → no flag."""
        result = _validate("Brazil")
        assert result.passed is True

    def test_reason_is_empty_on_pass(self) -> None:
        result = _validate("Brazil")
        assert result.reason == ""

    def test_applied_withholding_rate_is_none_for_non_treaty_country(self) -> None:
        result = _validate("Brazil")
        assert result.applied_withholding_rate_pct is None

    def test_unknown_country_blank_part_ii_passes(self) -> None:
        """Unknown countries are treated as non-treaty — blank Part II is correct."""
        result = _validate("Atlantis")
        assert result.passed is True
        assert result.applied_withholding_rate_pct is None

    def test_country_lookup_is_case_insensitive(self) -> None:
        result = _validate("brazil")
        assert result.passed is True

    def test_country_lookup_strips_whitespace(self) -> None:
        result = _validate("  Brazil  ")
        assert result.passed is True


# ===========================================================================
# Branch 1 — Non-treaty country with a FILLED Part II
# ===========================================================================


class TestNonTreatyCountryFilledPartII:
    """Non-treaty country with a filled Part II should fail — the claim is invalid."""

    def test_brazil_filled_part_ii_fails(self) -> None:
        result = _validate(
            "Brazil",
            treaty_country="Brazil",
            treaty_article="Article 1",
            withholding_rate="15%",
        )
        assert result.passed is False

    def test_reason_mentions_country(self) -> None:
        result = _validate(
            "Brazil",
            treaty_country="Brazil",
            treaty_article="Article 1",
            withholding_rate="15%",
        )
        assert "Brazil" in result.reason

    def test_reason_mentions_no_treaty(self) -> None:
        result = _validate(
            "Brazil",
            treaty_country="Brazil",
            treaty_article="Article 1",
            withholding_rate="15%",
        )
        assert "treaty" in result.reason.lower()

    def test_applied_withholding_rate_is_none_when_fails(self) -> None:
        result = _validate(
            "Brazil",
            treaty_country="Brazil",
            treaty_article="Article 1",
            withholding_rate="15%",
        )
        assert result.applied_withholding_rate_pct is None


# ===========================================================================
# Branch 2 — Treaty country (Germany) + blank Part II → flag for review
# Acceptance criterion #3: Treaty country + blank Part II → flagged for review
# ===========================================================================


class TestTreatyCountryBlankPartII:
    """Treaty country (Germany) with blank Part II should fail — flag for review."""

    def test_germany_blank_part_ii_fails(self) -> None:
        """Acceptance criterion #3: Treaty country + blank Part II → flagged."""
        result = _validate("Germany")
        assert result.passed is False

    def test_reason_is_non_empty(self) -> None:
        result = _validate("Germany")
        assert result.reason != ""

    def test_reason_mentions_country(self) -> None:
        result = _validate("Germany")
        assert "Germany" in result.reason

    def test_reason_mentions_treaty(self) -> None:
        result = _validate("Germany")
        assert "treaty" in result.reason.lower()

    def test_applied_withholding_rate_is_none_when_flagged(self) -> None:
        result = _validate("Germany")
        assert result.applied_withholding_rate_pct is None

    def test_empty_string_fields_treated_as_blank(self) -> None:
        """Empty strings in all Part II fields count as blank."""
        result = _validate(
            "Germany",
            treaty_country="",
            treaty_article="",
            withholding_rate="",
            income_type="",
            treaty_conditions="",
        )
        assert result.passed is False

    def test_whitespace_only_fields_treated_as_blank(self) -> None:
        """Whitespace-only strings count as blank."""
        result = _validate(
            "Germany",
            treaty_country="   ",
            treaty_article="   ",
            withholding_rate="   ",
        )
        assert result.passed is False

    def test_israel_blank_part_ii_also_fails(self) -> None:
        result = _validate("Israel")
        assert result.passed is False

    def test_uk_blank_part_ii_fails(self) -> None:
        result = _validate("United Kingdom")
        assert result.passed is False

    def test_uk_alias_blank_part_ii_fails(self) -> None:
        result = _validate("UK")
        assert result.passed is False


# ===========================================================================
# Branch 3 — Treaty country + completed Part II → pass, reduced rate returned
# Acceptance criterion #4: Treaty country + completed Part II → validated, rate applied
# ===========================================================================


class TestTreatyCountryCompletedPartII:
    """Treaty country (Germany) with a completed Part II should pass."""

    def test_germany_completed_part_ii_passes(self) -> None:
        """Acceptance criterion #4: Treaty country + completed Part II → validated."""
        result = _validate("Germany", **_GERMANY_PART_II)
        assert result.passed is True

    def test_reason_is_empty_on_pass(self) -> None:
        result = _validate("Germany", **_GERMANY_PART_II)
        assert result.reason == ""

    def test_applied_withholding_rate_is_15_for_germany(self) -> None:
        """Acceptance criterion #4: reduced rate is applied (15 % for Germany)."""
        result = _validate("Germany", **_GERMANY_PART_II)
        assert result.applied_withholding_rate_pct == 15.0

    def test_three_mandatory_fields_sufficient_for_pass(self) -> None:
        """income_type and treaty_conditions are optional for a valid claim."""
        result = _validate(
            "Germany",
            treaty_country="Germany",
            treaty_article="Article 10",
            withholding_rate="15%",
        )
        assert result.passed is True
        assert result.applied_withholding_rate_pct == 15.0

    def test_israel_completed_part_ii_passes(self) -> None:
        result = _validate(
            "Israel",
            treaty_country="Israel",
            treaty_article="Article 10",
            withholding_rate="15%",
        )
        assert result.passed is True
        assert result.applied_withholding_rate_pct == 15.0

    def test_uk_completed_part_ii_passes(self) -> None:
        result = _validate(
            "United Kingdom",
            treaty_country="United Kingdom",
            treaty_article="Article 10",
            withholding_rate="15%",
        )
        assert result.passed is True
        assert result.applied_withholding_rate_pct == 15.0


# ===========================================================================
# Branch 3 — Treaty country + partially filled Part II → fail
# ===========================================================================


class TestTreatyCountryPartialPartII:
    """Treaty country with some but not all mandatory Part II fields → fail."""

    def test_missing_treaty_article_fails(self) -> None:
        result = _validate(
            "Germany",
            treaty_country="Germany",
            treaty_article=None,
            withholding_rate="15%",
        )
        assert result.passed is False

    def test_missing_withholding_rate_fails(self) -> None:
        result = _validate(
            "Germany",
            treaty_country="Germany",
            treaty_article="Article 10",
            withholding_rate=None,
        )
        assert result.passed is False

    def test_missing_treaty_country_fails(self) -> None:
        result = _validate(
            "Germany",
            treaty_country=None,
            treaty_article="Article 10",
            withholding_rate="15%",
        )
        assert result.passed is False

    def test_reason_mentions_missing_field_treaty_article(self) -> None:
        result = _validate(
            "Germany",
            treaty_country="Germany",
            treaty_article=None,
            withholding_rate="15%",
        )
        assert "treaty article" in result.reason.lower()

    def test_reason_mentions_missing_field_withholding_rate(self) -> None:
        result = _validate(
            "Germany",
            treaty_country="Germany",
            treaty_article="Article 10",
            withholding_rate=None,
        )
        assert "withholding rate" in result.reason.lower()

    def test_reason_mentions_missing_field_treaty_country(self) -> None:
        result = _validate(
            "Germany",
            treaty_country=None,
            treaty_article="Article 10",
            withholding_rate="15%",
        )
        assert "treaty country" in result.reason.lower()

    def test_applied_withholding_rate_is_none_when_partial(self) -> None:
        result = _validate(
            "Germany",
            treaty_country="Germany",
            treaty_article=None,
            withholding_rate="15%",
        )
        assert result.applied_withholding_rate_pct is None

    def test_partial_does_not_raise(self) -> None:
        result = _validate(
            "Germany",
            treaty_country="Germany",
            treaty_article=None,
            withholding_rate=None,
        )
        assert isinstance(result, TreatyClaimValidationResult)


# ===========================================================================
# Error handling
# ===========================================================================


class TestTreatyClaimValidatorErrors:
    def test_empty_country_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            _validate(country_of_citizenship="")

    def test_whitespace_only_country_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            _validate(country_of_citizenship="   ")
