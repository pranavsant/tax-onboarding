"""Unit tests for FormFieldNormalizer domain service.

Covers required-field validation, tin_type normalization, W-8BEN
identification-number constraints, and whitespace trimming.
"""
import pytest

from src.domain.exceptions import InvalidFormFieldsError
from src.domain.services.form_field_normalizer import FormFieldNormalizer, W8BENFields, W9Fields


# =========================================================================
# W-9 normalization
# =========================================================================


class TestNormalizeW9RequiredFields:
    """Ensure each required W-9 field triggers an error when absent."""

    _VALID = dict(
        name="Jane Doe",
        federal_tax_classification="Individual",
        address="123 Main St",
        city_state_zip="Springfield, IL 62701",
        tin="123-45-6789",
        tin_type="SSN",
    )

    def test_valid_input_returns_w9_fields(self) -> None:
        result = FormFieldNormalizer.normalize_w9(**self._VALID)
        assert isinstance(result, W9Fields)

    def test_missing_name_raises_error(self) -> None:
        with pytest.raises(InvalidFormFieldsError, match="name"):
            FormFieldNormalizer.normalize_w9(**{**self._VALID, "name": ""})

    def test_missing_federal_tax_classification_raises_error(self) -> None:
        with pytest.raises(InvalidFormFieldsError, match="federal_tax_classification"):
            FormFieldNormalizer.normalize_w9(**{**self._VALID, "federal_tax_classification": ""})

    def test_missing_address_raises_error(self) -> None:
        with pytest.raises(InvalidFormFieldsError, match="address"):
            FormFieldNormalizer.normalize_w9(**{**self._VALID, "address": ""})

    def test_missing_city_state_zip_raises_error(self) -> None:
        with pytest.raises(InvalidFormFieldsError, match="city_state_zip"):
            FormFieldNormalizer.normalize_w9(**{**self._VALID, "city_state_zip": ""})

    def test_missing_tin_raises_error(self) -> None:
        with pytest.raises(InvalidFormFieldsError, match="tin"):
            FormFieldNormalizer.normalize_w9(**{**self._VALID, "tin": ""})

    def test_missing_tin_type_raises_error(self) -> None:
        with pytest.raises(InvalidFormFieldsError, match="tin_type"):
            FormFieldNormalizer.normalize_w9(**{**self._VALID, "tin_type": ""})

    def test_none_name_raises_error(self) -> None:
        with pytest.raises(InvalidFormFieldsError):
            FormFieldNormalizer.normalize_w9(**{**self._VALID, "name": None})


class TestNormalizeW9TinType:
    _VALID = dict(
        name="Jane Doe",
        federal_tax_classification="Individual",
        address="123 Main St",
        city_state_zip="Springfield, IL 62701",
        tin="123-45-6789",
        tin_type="SSN",
    )

    def test_ssn_accepted(self) -> None:
        result = FormFieldNormalizer.normalize_w9(**self._VALID)
        assert result.tin_type == "SSN"

    def test_ein_accepted(self) -> None:
        result = FormFieldNormalizer.normalize_w9(**{**self._VALID, "tin_type": "EIN"})
        assert result.tin_type == "EIN"

    def test_lowercase_ssn_normalized_to_uppercase(self) -> None:
        result = FormFieldNormalizer.normalize_w9(**{**self._VALID, "tin_type": "ssn"})
        assert result.tin_type == "SSN"

    def test_lowercase_ein_normalized_to_uppercase(self) -> None:
        result = FormFieldNormalizer.normalize_w9(**{**self._VALID, "tin_type": "ein"})
        assert result.tin_type == "EIN"

    def test_invalid_tin_type_raises_error(self) -> None:
        with pytest.raises(InvalidFormFieldsError, match="tin_type"):
            FormFieldNormalizer.normalize_w9(**{**self._VALID, "tin_type": "ITIN"})

    def test_error_message_contains_bad_value(self) -> None:
        with pytest.raises(InvalidFormFieldsError, match="ITIN"):
            FormFieldNormalizer.normalize_w9(**{**self._VALID, "tin_type": "ITIN"})


class TestNormalizeW9OptionalFields:
    _VALID = dict(
        name="Jane Doe",
        federal_tax_classification="Individual",
        address="123 Main St",
        city_state_zip="Springfield, IL 62701",
        tin="123-45-6789",
        tin_type="SSN",
    )

    def test_optional_fields_default_to_none(self) -> None:
        result = FormFieldNormalizer.normalize_w9(**self._VALID)
        assert result.business_name is None
        assert result.exempt_payee_code is None
        assert result.exemption_from_fatca_code is None
        assert result.account_numbers is None

    def test_optional_fields_are_stored_when_provided(self) -> None:
        result = FormFieldNormalizer.normalize_w9(
            **self._VALID,
            business_name="Acme LLC",
            account_numbers="ACC-001",
        )
        assert result.business_name == "Acme LLC"
        assert result.account_numbers == "ACC-001"

    def test_whitespace_in_name_is_stripped(self) -> None:
        result = FormFieldNormalizer.normalize_w9(**{**self._VALID, "name": "  Jane Doe  "})
        assert result.name == "Jane Doe"


# =========================================================================
# W-8BEN normalization
# =========================================================================


class TestNormalizeW8BENRequiredFields:
    _VALID = dict(
        name="Carlos Rodrigues",
        country_of_citizenship="Brazil",
        permanent_address="Rua das Flores, 42",
        permanent_address_city_country="São Paulo, SP, Brazil",
        foreign_tin="123.456.789-00",
    )

    def test_valid_input_returns_w8ben_fields(self) -> None:
        result = FormFieldNormalizer.normalize_w8ben(**self._VALID)
        assert isinstance(result, W8BENFields)

    def test_missing_name_raises_error(self) -> None:
        with pytest.raises(InvalidFormFieldsError, match="name"):
            FormFieldNormalizer.normalize_w8ben(**{**self._VALID, "name": ""})

    def test_missing_country_of_citizenship_raises_error(self) -> None:
        with pytest.raises(InvalidFormFieldsError, match="country_of_citizenship"):
            FormFieldNormalizer.normalize_w8ben(
                **{**self._VALID, "country_of_citizenship": ""}
            )

    def test_missing_permanent_address_raises_error(self) -> None:
        with pytest.raises(InvalidFormFieldsError, match="permanent_address"):
            FormFieldNormalizer.normalize_w8ben(**{**self._VALID, "permanent_address": ""})

    def test_missing_permanent_address_city_country_raises_error(self) -> None:
        with pytest.raises(InvalidFormFieldsError, match="permanent_address_city_country"):
            FormFieldNormalizer.normalize_w8ben(
                **{**self._VALID, "permanent_address_city_country": ""}
            )


class TestNormalizeW8BENIdentification:
    _BASE = dict(
        name="Carlos Rodrigues",
        country_of_citizenship="Brazil",
        permanent_address="Rua das Flores, 42",
        permanent_address_city_country="São Paulo, SP, Brazil",
    )

    def test_foreign_tin_satisfies_identification(self) -> None:
        result = FormFieldNormalizer.normalize_w8ben(**self._BASE, foreign_tin="123.456.789-00")
        assert result.foreign_tin == "123.456.789-00"

    def test_us_tin_satisfies_identification(self) -> None:
        result = FormFieldNormalizer.normalize_w8ben(**self._BASE, us_tin="123-45-6789")
        assert result.us_tin == "123-45-6789"

    def test_ftin_not_required_flag_satisfies_identification(self) -> None:
        result = FormFieldNormalizer.normalize_w8ben(**self._BASE, ftin_not_required=True)
        assert result.ftin_not_required is True

    def test_no_identification_raises_error(self) -> None:
        with pytest.raises(InvalidFormFieldsError, match="us_tin"):
            FormFieldNormalizer.normalize_w8ben(**self._BASE)

    def test_empty_foreign_tin_without_others_raises_error(self) -> None:
        with pytest.raises(InvalidFormFieldsError):
            FormFieldNormalizer.normalize_w8ben(**self._BASE, foreign_tin="   ")

    def test_ftin_not_required_false_without_tin_raises_error(self) -> None:
        """ftin_not_required=False does not satisfy the identification requirement."""
        with pytest.raises(InvalidFormFieldsError):
            FormFieldNormalizer.normalize_w8ben(**self._BASE, ftin_not_required=False)


class TestNormalizeW8BENOptionalFields:
    _VALID = dict(
        name="Carlos Rodrigues",
        country_of_citizenship="Brazil",
        permanent_address="Rua das Flores, 42",
        permanent_address_city_country="São Paulo, SP, Brazil",
        foreign_tin="123.456.789-00",
    )

    def test_optional_fields_default_to_none(self) -> None:
        result = FormFieldNormalizer.normalize_w8ben(**self._VALID)
        assert result.treaty_country is None
        assert result.treaty_article is None
        assert result.withholding_rate is None
        assert result.income_type is None
        assert result.date_of_birth is None

    def test_treaty_fields_are_stored_when_provided(self) -> None:
        result = FormFieldNormalizer.normalize_w8ben(
            **self._VALID,
            treaty_country="Brazil",
            treaty_article="Article 21",
            withholding_rate="15%",
            income_type="Dividends",
        )
        assert result.treaty_country == "Brazil"
        assert result.treaty_article == "Article 21"
        assert result.withholding_rate == "15%"
        assert result.income_type == "Dividends"

    def test_whitespace_in_name_is_stripped(self) -> None:
        result = FormFieldNormalizer.normalize_w8ben(
            **{**self._VALID, "name": "  Carlos Rodrigues  "}
        )
        assert result.name == "Carlos Rodrigues"
