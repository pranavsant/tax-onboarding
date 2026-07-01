"""Unit tests for ParsePdfFormFieldsUseCase.

Verifies that:
- W-9 and W-8BEN payloads are correctly dispatched and normalized
- Missing form_type raises TaxFormExtractionError
- Unknown form_type raises TaxFormExtractionError
- Extraction failure propagates as TaxFormExtractionError
- Missing required fields are surfaced as InvalidFormFieldsError
- The fixture JSON files round-trip successfully through the use case
"""
from __future__ import annotations

import json
import pathlib
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.application.dto.tax_form_dto import ParsedFormFieldsDTO
from src.application.exceptions import InvalidFormFieldsError, TaxFormExtractionError
from src.application.ports.tax_form_extractor import TaxFormExtractorPort
from src.application.use_cases.parse_pdf_form_fields import ParsePdfFormFieldsUseCase
from src.infrastructure.pdf.stub_pdf_extractor import StubPdfExtractor

FIXTURES_DIR = pathlib.Path(__file__).parent.parent / "fixtures"

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_W9_FIELDS: dict[str, Any] = {
    "form_type": "W-9",
    "name": "Jane A. Doe",
    "federal_tax_classification": "Individual/sole proprietor or single-member LLC",
    "address": "123 Main Street, Apt 4B",
    "city_state_zip": "Springfield, IL 62701",
    "tin": "123-45-6789",
    "tin_type": "SSN",
}

_W8BEN_FIELDS: dict[str, Any] = {
    "form_type": "W-8BEN",
    "name": "Carlos M. Rodrigues",
    "country_of_citizenship": "Brazil",
    "permanent_address": "Rua das Flores, 42",
    "permanent_address_city_country": "São Paulo, SP, Brazil",
    "foreign_tin": "123.456.789-00",
}


def _stub_use_case(fields: dict) -> tuple[ParsePdfFormFieldsUseCase, TaxFormExtractorPort]:
    """Return a use case wired to a mock extractor that returns *fields*."""
    mock_extractor = MagicMock(spec=TaxFormExtractorPort)
    mock_extractor.extract.return_value = fields
    return ParsePdfFormFieldsUseCase(mock_extractor), mock_extractor


# ---------------------------------------------------------------------------
# W-9 happy path
# ---------------------------------------------------------------------------


class TestParsePdfFormFieldsUseCaseW9:
    def test_returns_parsed_form_fields_dto(self) -> None:
        use_case, _ = _stub_use_case(_W9_FIELDS)
        result = use_case.execute(b"ignored", "w9.pdf")
        assert isinstance(result, ParsedFormFieldsDTO)

    def test_form_type_is_w9(self) -> None:
        use_case, _ = _stub_use_case(_W9_FIELDS)
        result = use_case.execute(b"ignored", "w9.pdf")
        assert result.form_type == "W-9"

    def test_name_is_mapped(self) -> None:
        use_case, _ = _stub_use_case(_W9_FIELDS)
        result = use_case.execute(b"ignored", "w9.pdf")
        assert result.name == "Jane A. Doe"

    def test_tin_is_mapped(self) -> None:
        use_case, _ = _stub_use_case(_W9_FIELDS)
        result = use_case.execute(b"ignored", "w9.pdf")
        assert result.tin == "123-45-6789"

    def test_tin_type_normalized_to_uppercase(self) -> None:
        fields = {**_W9_FIELDS, "tin_type": "ssn"}
        use_case, _ = _stub_use_case(fields)
        result = use_case.execute(b"ignored", "w9.pdf")
        assert result.tin_type == "SSN"

    def test_w8ben_fields_are_none(self) -> None:
        use_case, _ = _stub_use_case(_W9_FIELDS)
        result = use_case.execute(b"ignored", "w9.pdf")
        assert result.country_of_citizenship is None
        assert result.foreign_tin is None

    def test_extractor_is_called_with_bytes_and_filename(self) -> None:
        use_case, mock_extractor = _stub_use_case(_W9_FIELDS)
        use_case.execute(b"some bytes", "my_w9.pdf")
        mock_extractor.extract.assert_called_once_with(b"some bytes", "my_w9.pdf")


# ---------------------------------------------------------------------------
# W-8BEN happy path
# ---------------------------------------------------------------------------


class TestParsePdfFormFieldsUseCaseW8BEN:
    def test_returns_parsed_form_fields_dto(self) -> None:
        use_case, _ = _stub_use_case(_W8BEN_FIELDS)
        result = use_case.execute(b"ignored", "w8ben.pdf")
        assert isinstance(result, ParsedFormFieldsDTO)

    def test_form_type_is_w8ben(self) -> None:
        use_case, _ = _stub_use_case(_W8BEN_FIELDS)
        result = use_case.execute(b"ignored", "w8ben.pdf")
        assert result.form_type == "W-8BEN"

    def test_name_is_mapped(self) -> None:
        use_case, _ = _stub_use_case(_W8BEN_FIELDS)
        result = use_case.execute(b"ignored", "w8ben.pdf")
        assert result.name == "Carlos M. Rodrigues"

    def test_foreign_tin_is_mapped(self) -> None:
        use_case, _ = _stub_use_case(_W8BEN_FIELDS)
        result = use_case.execute(b"ignored", "w8ben.pdf")
        assert result.foreign_tin == "123.456.789-00"

    def test_w9_fields_are_none(self) -> None:
        use_case, _ = _stub_use_case(_W8BEN_FIELDS)
        result = use_case.execute(b"ignored", "w8ben.pdf")
        assert result.tin is None
        assert result.tin_type is None
        assert result.federal_tax_classification is None

    def test_optional_treaty_fields_mapped_when_present(self) -> None:
        fields = {
            **_W8BEN_FIELDS,
            "treaty_country": "Brazil",
            "treaty_article": "Article 21",
            "withholding_rate": "15%",
        }
        use_case, _ = _stub_use_case(fields)
        result = use_case.execute(b"ignored", "w8ben.pdf")
        assert result.treaty_country == "Brazil"
        assert result.treaty_article == "Article 21"
        assert result.withholding_rate == "15%"


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestParsePdfFormFieldsUseCaseErrors:
    def test_missing_form_type_raises_extraction_error(self) -> None:
        fields = {k: v for k, v in _W9_FIELDS.items() if k != "form_type"}
        use_case, _ = _stub_use_case(fields)
        with pytest.raises(TaxFormExtractionError, match="form_type"):
            use_case.execute(b"ignored", "w9.pdf")

    def test_empty_form_type_raises_extraction_error(self) -> None:
        use_case, _ = _stub_use_case({**_W9_FIELDS, "form_type": ""})
        with pytest.raises(TaxFormExtractionError):
            use_case.execute(b"ignored", "w9.pdf")

    def test_unknown_form_type_raises_extraction_error(self) -> None:
        use_case, _ = _stub_use_case({**_W9_FIELDS, "form_type": "1099"})
        with pytest.raises(TaxFormExtractionError, match="1099"):
            use_case.execute(b"ignored", "1099.pdf")

    def test_extractor_exception_propagates(self) -> None:
        mock_extractor = MagicMock(spec=TaxFormExtractorPort)
        mock_extractor.extract.side_effect = TaxFormExtractionError("corrupt file")
        use_case = ParsePdfFormFieldsUseCase(mock_extractor)
        with pytest.raises(TaxFormExtractionError, match="corrupt file"):
            use_case.execute(b"bad data", "corrupt.pdf")

    def test_missing_required_w9_field_raises_invalid_form_fields_error(self) -> None:
        fields = {**_W9_FIELDS, "name": ""}
        use_case, _ = _stub_use_case(fields)
        with pytest.raises(InvalidFormFieldsError):
            use_case.execute(b"ignored", "w9.pdf")

    def test_missing_required_w8ben_field_raises_invalid_form_fields_error(self) -> None:
        fields = {**_W8BEN_FIELDS, "name": ""}
        use_case, _ = _stub_use_case(fields)
        with pytest.raises(InvalidFormFieldsError):
            use_case.execute(b"ignored", "w8ben.pdf")

    def test_w8ben_no_identification_raises_invalid_form_fields_error(self) -> None:
        fields = {k: v for k, v in _W8BEN_FIELDS.items() if k != "foreign_tin"}
        use_case, _ = _stub_use_case(fields)
        with pytest.raises(InvalidFormFieldsError):
            use_case.execute(b"ignored", "w8ben.pdf")


# ---------------------------------------------------------------------------
# Fixture round-trip tests (using StubPdfExtractor)
# ---------------------------------------------------------------------------


class TestFixtureRoundTripViaPdf:
    """Ensure fixture JSONs can flow through the full PDF path end-to-end."""

    def setup_method(self) -> None:
        self.extractor = StubPdfExtractor()
        self.use_case = ParsePdfFormFieldsUseCase(self.extractor)

    def test_w9_fixture_round_trips(self) -> None:
        fixture_path = FIXTURES_DIR / "w9_fields.json"
        raw = json.loads(fixture_path.read_text())
        raw.pop("_comment", None)
        raw["form_type"] = "W-9"
        file_bytes = json.dumps(raw).encode()
        result = self.use_case.execute(file_bytes, "w9_fields.json")
        assert result.form_type == "W-9"
        assert result.name == "Jane A. Doe"
        assert result.tin == "123-45-6789"
        assert result.tin_type == "SSN"

    def test_w8ben_fixture_round_trips(self) -> None:
        fixture_path = FIXTURES_DIR / "w8ben_fields.json"
        raw = json.loads(fixture_path.read_text())
        raw.pop("_comment", None)
        raw["form_type"] = "W-8BEN"
        file_bytes = json.dumps(raw).encode()
        result = self.use_case.execute(file_bytes, "w8ben_fields.json")
        assert result.form_type == "W-8BEN"
        assert result.name == "Carlos M. Rodrigues"
        assert result.foreign_tin == "123.456.789-00"
        assert result.treaty_country == "Brazil"
