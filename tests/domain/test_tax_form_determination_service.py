"""Unit tests for TaxFormDeterminationService.

Covers both form-determination branches, the missing-value guard, and
unrecognized investor_type values.
"""
import pytest

from src.domain.exceptions import UnrecognizedInvestorTypeError
from src.domain.services.tax_form_determination_service import (
    TaxFormCode,
    TaxFormDeterminationService,
)


class TestUsPerson:
    def test_us_person_requires_w9(self) -> None:
        result = TaxFormDeterminationService.determine_form("us_person")
        assert result == TaxFormCode.W9

    def test_us_person_form_code_value(self) -> None:
        result = TaxFormDeterminationService.determine_form("us_person")
        assert result.value == "W-9"


class TestForeignPerson:
    def test_foreign_person_requires_w8ben(self) -> None:
        result = TaxFormDeterminationService.determine_form("foreign_person")
        assert result == TaxFormCode.W8BEN

    def test_foreign_person_form_code_value(self) -> None:
        result = TaxFormDeterminationService.determine_form("foreign_person")
        assert result.value == "W-8BEN"


class TestMissingOrUnrecognizedInvestorType:
    def test_empty_string_raises_error(self) -> None:
        with pytest.raises(UnrecognizedInvestorTypeError):
            TaxFormDeterminationService.determine_form("")

    def test_whitespace_only_raises_error(self) -> None:
        with pytest.raises(UnrecognizedInvestorTypeError):
            TaxFormDeterminationService.determine_form("   ")

    def test_unrecognized_value_raises_error(self) -> None:
        with pytest.raises(UnrecognizedInvestorTypeError):
            TaxFormDeterminationService.determine_form("corporation")

    def test_error_message_contains_bad_value(self) -> None:
        with pytest.raises(UnrecognizedInvestorTypeError, match="corporation"):
            TaxFormDeterminationService.determine_form("corporation")

    def test_case_insensitive_us_person(self) -> None:
        """investor_type matching is case-insensitive for user convenience."""
        result = TaxFormDeterminationService.determine_form("US_PERSON")
        assert result == TaxFormCode.W9

    def test_case_insensitive_foreign_person(self) -> None:
        result = TaxFormDeterminationService.determine_form("FOREIGN_PERSON")
        assert result == TaxFormCode.W8BEN
