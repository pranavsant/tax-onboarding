"""Unit tests for the TreatyTable domain service and TreatyEntry data class.

Covers:
  TreatyEntry
    - Is a frozen dataclass (immutable)
    - Carries country, has_treaty, withholding_rate_pct fields

  TreatyTable.lookup
    - Brazil  → no treaty, 30 % statutory rate
    - Germany → treaty, 15 % reduced rate
    - Israel  → treaty, 15 % reduced rate
    - UK (as 'UK' alias)               → treaty, 15 % reduced rate
    - UK (as 'United Kingdom')         → treaty, 15 % reduced rate
    - UK (as 'Great Britain' alias)    → treaty, 15 % reduced rate
    - Case-insensitive matching ('BRAZIL', 'germany', 'United Kingdom')
    - Surrounding whitespace is stripped before lookup
    - Unknown country → has_treaty=False, 30 % statutory rate, name preserved
    - Empty / whitespace-only country → raises ValueError

  TreatyTable.is_treaty_country
    - Returns True for treaty countries
    - Returns False for non-treaty countries
    - Returns False for unknown countries
    - Raises ValueError for empty input

  TreatyTable.known_countries
    - Returns a sorted list of canonical names
    - All four required countries are present
    - No duplicates (aliases collapsed to canonical name)
"""
from __future__ import annotations

import pytest

from src.domain.services.treaty_table import TreatyEntry, TreatyTable


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _lookup(country: str) -> TreatyEntry:
    return TreatyTable.lookup(country)


# ===========================================================================
# TreatyEntry — data class contract
# ===========================================================================


class TestTreatyEntry:
    """TreatyEntry is a frozen dataclass with the required fields."""

    def test_has_country_field(self) -> None:
        entry = TreatyEntry(country="Brazil", has_treaty=False, withholding_rate_pct=30.0)
        assert entry.country == "Brazil"

    def test_has_has_treaty_field(self) -> None:
        entry = TreatyEntry(country="Germany", has_treaty=True, withholding_rate_pct=15.0)
        assert entry.has_treaty is True

    def test_has_withholding_rate_pct_field(self) -> None:
        entry = TreatyEntry(country="Germany", has_treaty=True, withholding_rate_pct=15.0)
        assert entry.withholding_rate_pct == 15.0

    def test_is_immutable(self) -> None:
        """frozen=True means attribute assignment raises AttributeError."""
        entry = TreatyEntry(country="Brazil", has_treaty=False, withholding_rate_pct=30.0)
        with pytest.raises(AttributeError):
            entry.has_treaty = True  # type: ignore[misc]

    def test_equality_by_value(self) -> None:
        a = TreatyEntry(country="Brazil", has_treaty=False, withholding_rate_pct=30.0)
        b = TreatyEntry(country="Brazil", has_treaty=False, withholding_rate_pct=30.0)
        assert a == b


# ===========================================================================
# TreatyTable.lookup — required countries
# ===========================================================================


class TestTreatyTableLookupBrazil:
    """Brazil has no US tax treaty; statutory 30 % rate applies."""

    def test_returns_treaty_entry(self) -> None:
        assert isinstance(_lookup("Brazil"), TreatyEntry)

    def test_has_treaty_is_false(self) -> None:
        assert _lookup("Brazil").has_treaty is False

    def test_withholding_rate_is_30(self) -> None:
        assert _lookup("Brazil").withholding_rate_pct == 30.0

    def test_country_name_is_brazil(self) -> None:
        assert _lookup("Brazil").country == "Brazil"


class TestTreatyTableLookupGermany:
    """Germany has a US tax treaty; 15 % reduced withholding rate."""

    def test_returns_treaty_entry(self) -> None:
        assert isinstance(_lookup("Germany"), TreatyEntry)

    def test_has_treaty_is_true(self) -> None:
        assert _lookup("Germany").has_treaty is True

    def test_withholding_rate_is_15(self) -> None:
        assert _lookup("Germany").withholding_rate_pct == 15.0

    def test_country_name_is_germany(self) -> None:
        assert _lookup("Germany").country == "Germany"


class TestTreatyTableLookupIsrael:
    """Israel has a US tax treaty; 15 % reduced withholding rate."""

    def test_returns_treaty_entry(self) -> None:
        assert isinstance(_lookup("Israel"), TreatyEntry)

    def test_has_treaty_is_true(self) -> None:
        assert _lookup("Israel").has_treaty is True

    def test_withholding_rate_is_15(self) -> None:
        assert _lookup("Israel").withholding_rate_pct == 15.0

    def test_country_name_is_israel(self) -> None:
        assert _lookup("Israel").country == "Israel"


class TestTreatyTableLookupUK:
    """UK has a US tax treaty; 15 % reduced withholding rate.

    The table supports multiple spellings: 'UK', 'United Kingdom',
    'Great Britain'.
    """

    def test_returns_treaty_entry_for_uk_alias(self) -> None:
        assert isinstance(_lookup("UK"), TreatyEntry)

    def test_has_treaty_is_true_for_uk_alias(self) -> None:
        assert _lookup("UK").has_treaty is True

    def test_withholding_rate_is_15_for_uk_alias(self) -> None:
        assert _lookup("UK").withholding_rate_pct == 15.0

    def test_returns_treaty_entry_for_united_kingdom(self) -> None:
        assert isinstance(_lookup("United Kingdom"), TreatyEntry)

    def test_has_treaty_is_true_for_united_kingdom(self) -> None:
        assert _lookup("United Kingdom").has_treaty is True

    def test_withholding_rate_is_15_for_united_kingdom(self) -> None:
        assert _lookup("United Kingdom").withholding_rate_pct == 15.0

    def test_returns_treaty_entry_for_great_britain(self) -> None:
        assert isinstance(_lookup("Great Britain"), TreatyEntry)

    def test_has_treaty_is_true_for_great_britain(self) -> None:
        assert _lookup("Great Britain").has_treaty is True


# ===========================================================================
# TreatyTable.lookup — case-insensitivity
# ===========================================================================


class TestTreatyTableLookupCaseInsensitive:
    """Lookups must succeed regardless of input capitalisation."""

    def test_uppercase_brazil(self) -> None:
        assert _lookup("BRAZIL").has_treaty is False

    def test_lowercase_germany(self) -> None:
        assert _lookup("germany").has_treaty is True

    def test_mixed_case_israel(self) -> None:
        assert _lookup("ISRAEL").has_treaty is True

    def test_mixed_case_united_kingdom(self) -> None:
        assert _lookup("united kingdom").has_treaty is True

    def test_uppercase_uk_alias(self) -> None:
        assert _lookup("uk").has_treaty is True

    def test_titlecase_brazil_rate(self) -> None:
        assert _lookup("Brazil").withholding_rate_pct == 30.0

    def test_lowercase_germany_rate(self) -> None:
        assert _lookup("germany").withholding_rate_pct == 15.0


# ===========================================================================
# TreatyTable.lookup — whitespace handling
# ===========================================================================


class TestTreatyTableLookupWhitespace:
    """Leading/trailing whitespace is stripped before lookup."""

    def test_strips_leading_whitespace(self) -> None:
        assert _lookup("  Brazil").has_treaty is False

    def test_strips_trailing_whitespace(self) -> None:
        assert _lookup("Germany  ").has_treaty is True

    def test_strips_both_sides(self) -> None:
        assert _lookup("  Israel  ").has_treaty is True

    def test_strips_whitespace_from_uk(self) -> None:
        assert _lookup("  UK  ").has_treaty is True


# ===========================================================================
# TreatyTable.lookup — unknown countries
# ===========================================================================


class TestTreatyTableLookupUnknownCountry:
    """Unknown countries fall back to the statutory 30 % rate."""

    def test_returns_treaty_entry_for_unknown(self) -> None:
        assert isinstance(_lookup("France"), TreatyEntry)

    def test_has_treaty_is_false_for_unknown(self) -> None:
        assert _lookup("France").has_treaty is False

    def test_withholding_rate_is_30_for_unknown(self) -> None:
        assert _lookup("France").withholding_rate_pct == 30.0

    def test_country_name_preserved_for_unknown(self) -> None:
        """The caller-supplied name is echoed back in the entry."""
        assert _lookup("Ruritania").country == "Ruritania"

    def test_whitespace_stripped_from_unknown_country_name(self) -> None:
        entry = _lookup("  Ruritania  ")
        assert entry.country == "Ruritania"


# ===========================================================================
# TreatyTable.lookup — invalid input raises ValueError
# ===========================================================================


class TestTreatyTableLookupInvalidInput:
    """Empty or whitespace-only country names raise ValueError."""

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError):
            _lookup("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError):
            _lookup("   ")

    def test_error_message_is_informative(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            _lookup("")


# ===========================================================================
# TreatyTable.is_treaty_country
# ===========================================================================


class TestIsTreatyCountry:
    """Convenience method that returns a plain bool."""

    def test_returns_true_for_germany(self) -> None:
        assert TreatyTable.is_treaty_country("Germany") is True

    def test_returns_true_for_israel(self) -> None:
        assert TreatyTable.is_treaty_country("Israel") is True

    def test_returns_true_for_uk(self) -> None:
        assert TreatyTable.is_treaty_country("UK") is True

    def test_returns_true_for_united_kingdom(self) -> None:
        assert TreatyTable.is_treaty_country("United Kingdom") is True

    def test_returns_false_for_brazil(self) -> None:
        assert TreatyTable.is_treaty_country("Brazil") is False

    def test_returns_false_for_unknown_country(self) -> None:
        assert TreatyTable.is_treaty_country("Ruritania") is False

    def test_case_insensitive_true(self) -> None:
        assert TreatyTable.is_treaty_country("GERMANY") is True

    def test_case_insensitive_false(self) -> None:
        assert TreatyTable.is_treaty_country("brazil") is False

    def test_raises_for_empty_string(self) -> None:
        with pytest.raises(ValueError):
            TreatyTable.is_treaty_country("")


# ===========================================================================
# TreatyTable.known_countries
# ===========================================================================


class TestKnownCountries:
    """known_countries() returns a sorted list of canonical names."""

    def test_returns_list(self) -> None:
        assert isinstance(TreatyTable.known_countries(), list)

    def test_brazil_is_present(self) -> None:
        assert "Brazil" in TreatyTable.known_countries()

    def test_germany_is_present(self) -> None:
        assert "Germany" in TreatyTable.known_countries()

    def test_israel_is_present(self) -> None:
        assert "Israel" in TreatyTable.known_countries()

    def test_united_kingdom_is_present(self) -> None:
        assert "United Kingdom" in TreatyTable.known_countries()

    def test_no_duplicates(self) -> None:
        names = TreatyTable.known_countries()
        assert len(names) == len(set(names))

    def test_is_sorted(self) -> None:
        names = TreatyTable.known_countries()
        assert names == sorted(names)

    def test_aliases_are_collapsed(self) -> None:
        """'UK' and 'Great Britain' aliases must NOT appear as separate entries."""
        names = TreatyTable.known_countries()
        assert "UK" not in names
        assert "Great Britain" not in names

    def test_contains_at_least_four_countries(self) -> None:
        assert len(TreatyTable.known_countries()) >= 4
