"""Unit tests for StubPdfExtractor.

Verifies that:
- Valid JSON bytes are decoded to a dict
- The dict is returned unchanged (no field validation here)
- Invalid UTF-8 raises TaxFormExtractionError
- Invalid JSON raises TaxFormExtractionError
- A non-object top-level JSON value raises TaxFormExtractionError
"""
from __future__ import annotations

import json

import pytest

from src.application.exceptions import TaxFormExtractionError
from src.infrastructure.pdf.stub_pdf_extractor import StubPdfExtractor


@pytest.fixture()
def extractor() -> StubPdfExtractor:
    return StubPdfExtractor()


class TestStubPdfExtractorSuccess:
    def test_returns_dict_for_valid_json_bytes(self, extractor: StubPdfExtractor) -> None:
        payload = {"form_type": "W-9", "name": "Jane Doe"}
        result = extractor.extract(json.dumps(payload).encode(), "w9.pdf")
        assert result == payload

    def test_form_type_preserved(self, extractor: StubPdfExtractor) -> None:
        payload = {"form_type": "W-8BEN", "name": "Carlos Rodrigues"}
        result = extractor.extract(json.dumps(payload).encode(), "w8ben.pdf")
        assert result["form_type"] == "W-8BEN"

    def test_filename_is_ignored(self, extractor: StubPdfExtractor) -> None:
        """StubPdfExtractor ignores the filename argument."""
        payload = {"form_type": "W-9", "name": "Jane Doe"}
        result_a = extractor.extract(json.dumps(payload).encode(), "anything.pdf")
        result_b = extractor.extract(json.dumps(payload).encode(), "")
        assert result_a == result_b

    def test_extra_keys_are_passed_through(self, extractor: StubPdfExtractor) -> None:
        payload = {"form_type": "W-9", "unexpected_field": "value"}
        result = extractor.extract(json.dumps(payload).encode(), "")
        assert result["unexpected_field"] == "value"

    def test_null_optional_fields_are_preserved(self, extractor: StubPdfExtractor) -> None:
        payload = {"form_type": "W-9", "business_name": None}
        result = extractor.extract(json.dumps(payload).encode(), "")
        assert result["business_name"] is None


class TestStubPdfExtractorErrors:
    def test_non_utf8_bytes_raise_extraction_error(self, extractor: StubPdfExtractor) -> None:
        bad_bytes = b"\xff\xfe invalid"
        with pytest.raises(TaxFormExtractionError, match="UTF-8"):
            extractor.extract(bad_bytes, "bad.pdf")

    def test_invalid_json_raises_extraction_error(self, extractor: StubPdfExtractor) -> None:
        with pytest.raises(TaxFormExtractionError, match="valid JSON"):
            extractor.extract(b"not json at all", "bad.pdf")

    def test_json_array_raises_extraction_error(self, extractor: StubPdfExtractor) -> None:
        with pytest.raises(TaxFormExtractionError, match="JSON object"):
            extractor.extract(b"[1, 2, 3]", "bad.pdf")

    def test_json_string_raises_extraction_error(self, extractor: StubPdfExtractor) -> None:
        with pytest.raises(TaxFormExtractionError, match="JSON object"):
            extractor.extract(b'"a string"', "bad.pdf")
