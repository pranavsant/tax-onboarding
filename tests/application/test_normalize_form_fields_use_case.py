"""Unit tests for NormalizeFormFieldsUseCase.

Verifies that:
- W-9 and W-8BEN input DTOs are correctly transformed into ParsedFormFieldsDTO
- Domain errors are surfaced as application-layer InvalidFormFieldsError
- The fixture JSON files round-trip successfully through the use case
"""
from __future__ import annotations

import json
import pathlib

import pytest

from src.application.dto.tax_form_dto import ParsedFormFieldsDTO, W8BENFieldsDTO, W9FieldsDTO
from src.application.exceptions import ApplicationError, InvalidFormFieldsError
from src.application.use_cases.normalize_form_fields import NormalizeFormFieldsUseCase

FIXTURES_DIR = pathlib.Path(__file__).parent.parent / "fixtures"


# =========================================================================
# Helpers
# =========================================================================


def _w9_dto(**overrides) -> W9FieldsDTO:
    defaults = dict(
        name="Jane A. Doe",
        federal_tax_classification="Individual/sole proprietor or single-member LLC",
        address="123 Main Street, Apt 4B",
        city_state_zip="Springfield, IL 62701",
        tin="123-45-6789",
        tin_type="SSN",
    )
    defaults.update(overrides)
    return W9FieldsDTO(**defaults)


def _w8ben_dto(**overrides) -> W8BENFieldsDTO:
    defaults = dict(
        name="Carlos M. Rodrigues",
        country_of_citizenship="Brazil",
        permanent_address="Rua das Flores, 42",
        permanent_address_city_country="São Paulo, SP, Brazil",
        foreign_tin="123.456.789-00",
    )
    defaults.update(overrides)
    return W8BENFieldsDTO(**defaults)


# =========================================================================
# W-9 use case
# =========================================================================


class TestNormalizeFormFieldsUseCaseW9:
    def setup_method(self) -> None:
        self.use_case = NormalizeFormFieldsUseCase()

    def test_returns_parsed_form_fields_dto(self) -> None:
        result = self.use_case.execute_w9(_w9_dto())
        assert isinstance(result, ParsedFormFieldsDTO)

    def test_form_type_is_w9(self) -> None:
        result = self.use_case.execute_w9(_w9_dto())
        assert result.form_type == "W-9"

    def test_name_is_preserved(self) -> None:
        result = self.use_case.execute_w9(_w9_dto())
        assert result.name == "Jane A. Doe"

    def test_tin_is_preserved(self) -> None:
        result = self.use_case.execute_w9(_w9_dto())
        assert result.tin == "123-45-6789"

    def test_tin_type_normalized_to_uppercase(self) -> None:
        result = self.use_case.execute_w9(_w9_dto(tin_type="ssn"))
        assert result.tin_type == "SSN"

    def test_federal_tax_classification_is_preserved(self) -> None:
        result = self.use_case.execute_w9(_w9_dto())
        assert result.federal_tax_classification == (
            "Individual/sole proprietor or single-member LLC"
        )

    def test_address_is_preserved(self) -> None:
        result = self.use_case.execute_w9(_w9_dto())
        assert result.address == "123 Main Street, Apt 4B"

    def test_optional_fields_are_none_by_default(self) -> None:
        result = self.use_case.execute_w9(_w9_dto())
        assert result.business_name is None
        assert result.account_numbers is None
        # W-8BEN fields must not be set
        assert result.country_of_citizenship is None

    def test_missing_required_field_raises_application_error(self) -> None:
        with pytest.raises(InvalidFormFieldsError):
            self.use_case.execute_w9(_w9_dto(name=""))

    def test_error_is_application_layer_type(self) -> None:
        with pytest.raises(ApplicationError):
            self.use_case.execute_w9(_w9_dto(tin_type="ITIN"))

    def test_invalid_tin_type_raises_application_error(self) -> None:
        with pytest.raises(InvalidFormFieldsError):
            self.use_case.execute_w9(_w9_dto(tin_type="ITIN"))


# =========================================================================
# W-8BEN use case
# =========================================================================


class TestNormalizeFormFieldsUseCaseW8BEN:
    def setup_method(self) -> None:
        self.use_case = NormalizeFormFieldsUseCase()

    def test_returns_parsed_form_fields_dto(self) -> None:
        result = self.use_case.execute_w8ben(_w8ben_dto())
        assert isinstance(result, ParsedFormFieldsDTO)

    def test_form_type_is_w8ben(self) -> None:
        result = self.use_case.execute_w8ben(_w8ben_dto())
        assert result.form_type == "W-8BEN"

    def test_name_is_preserved(self) -> None:
        result = self.use_case.execute_w8ben(_w8ben_dto())
        assert result.name == "Carlos M. Rodrigues"

    def test_country_of_citizenship_is_preserved(self) -> None:
        result = self.use_case.execute_w8ben(_w8ben_dto())
        assert result.country_of_citizenship == "Brazil"

    def test_foreign_tin_is_preserved(self) -> None:
        result = self.use_case.execute_w8ben(_w8ben_dto())
        assert result.foreign_tin == "123.456.789-00"

    def test_optional_treaty_fields_are_none_by_default(self) -> None:
        result = self.use_case.execute_w8ben(_w8ben_dto())
        assert result.treaty_country is None
        assert result.treaty_article is None

    def test_treaty_fields_are_preserved_when_provided(self) -> None:
        dto = _w8ben_dto(
            treaty_country="Brazil",
            treaty_article="Article 21",
            withholding_rate="15%",
            income_type="Dividends",
            treaty_conditions="Resident of Brazil.",
        )
        result = self.use_case.execute_w8ben(dto)
        assert result.treaty_country == "Brazil"
        assert result.treaty_article == "Article 21"
        assert result.withholding_rate == "15%"
        assert result.income_type == "Dividends"
        assert result.treaty_conditions == "Resident of Brazil."

    def test_w9_specific_fields_are_none(self) -> None:
        result = self.use_case.execute_w8ben(_w8ben_dto())
        assert result.tin is None
        assert result.tin_type is None
        assert result.federal_tax_classification is None

    def test_missing_required_field_raises_application_error(self) -> None:
        with pytest.raises(InvalidFormFieldsError):
            self.use_case.execute_w8ben(_w8ben_dto(name=""))

    def test_no_identification_raises_application_error(self) -> None:
        with pytest.raises(InvalidFormFieldsError):
            self.use_case.execute_w8ben(
                W8BENFieldsDTO(
                    name="Carlos M. Rodrigues",
                    country_of_citizenship="Brazil",
                    permanent_address="Rua das Flores, 42",
                    permanent_address_city_country="São Paulo, SP, Brazil",
                )
            )


# =========================================================================
# Fixture round-trip tests
# =========================================================================


class TestFixtureRoundTrip:
    """Ensure the sample fixture JSON files can be loaded and processed."""

    def setup_method(self) -> None:
        self.use_case = NormalizeFormFieldsUseCase()

    def test_w9_fixture_round_trips(self) -> None:
        raw = json.loads((FIXTURES_DIR / "w9_fields.json").read_text())
        raw.pop("_comment", None)
        dto = W9FieldsDTO(**raw)
        result = self.use_case.execute_w9(dto)
        assert result.form_type == "W-9"
        assert result.name == "Jane A. Doe"
        assert result.tin == "123-45-6789"
        assert result.tin_type == "SSN"

    def test_w8ben_fixture_round_trips(self) -> None:
        raw = json.loads((FIXTURES_DIR / "w8ben_fields.json").read_text())
        raw.pop("_comment", None)
        dto = W8BENFieldsDTO(**raw)
        result = self.use_case.execute_w8ben(dto)
        assert result.form_type == "W-8BEN"
        assert result.name == "Carlos M. Rodrigues"
        assert result.foreign_tin == "123.456.789-00"
        assert result.treaty_country == "Brazil"
