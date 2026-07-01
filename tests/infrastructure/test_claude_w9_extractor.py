"""Unit tests for ClaudeW9Extractor.

All tests mock the Anthropic client so no real API calls are made.

Verifies that:
- A well-formed Claude response is parsed into the expected dict.
- Missing / null fields in Claude's response are returned as None.
- Markdown code-fence wrapping is stripped before JSON parsing.
- An Anthropic APIError is translated into TaxFormExtractionError.
- A non-JSON Claude response raises TaxFormExtractionError.
- form_type is always forced to "W-9".
- The James Whitfield fixture case produces the expected output when
  wired through the full ParsePdfFormFieldsUseCase pipeline.
"""
from __future__ import annotations

import json
import pathlib
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.application.exceptions import TaxFormExtractionError
from src.application.use_cases.parse_pdf_form_fields import ParsePdfFormFieldsUseCase
from src.infrastructure.pdf.claude_w9_extractor import ClaudeW9Extractor

FIXTURES_DIR = pathlib.Path(__file__).parent.parent / "fixtures"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FULL_W9_RESPONSE: dict[str, Any] = {
    "form_type": "W-9",
    "name": "James Whitfield",
    "business_name": None,
    "federal_tax_classification": "Individual/sole proprietor or single-member LLC",
    "exempt_payee_code": None,
    "exemption_from_fatca_code": None,
    "address": "4821 Elmwood Drive",
    "city_state_zip": "Austin, TX 78701",
    "account_numbers": None,
    "tin": "512-74-9301",
    "tin_type": "SSN",
    "signature_present": True,
    "signature_date": "2024-03-15",
}


def _make_extractor(claude_text_response: str) -> ClaudeW9Extractor:
    """Return a ClaudeW9Extractor whose Anthropic client is fully mocked."""
    extractor = ClaudeW9Extractor(
        api_key="test-key",
        model="claude-3-5-sonnet-20241022",
        fallback_to_text=True,
    )
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = claude_text_response

    mock_response = MagicMock()
    mock_response.content = [mock_block]

    extractor._client = MagicMock()
    extractor._client.messages.create.return_value = mock_response
    return extractor


def _json_response(data: dict) -> str:
    return json.dumps(data)


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


class TestClaudeW9ExtractorHappyPath:
    def test_returns_dict(self) -> None:
        extractor = _make_extractor(_json_response(_FULL_W9_RESPONSE))
        result = extractor.extract(b"dummy pdf bytes", "w9.pdf")
        assert isinstance(result, dict)

    def test_form_type_is_w9(self) -> None:
        extractor = _make_extractor(_json_response(_FULL_W9_RESPONSE))
        result = extractor.extract(b"dummy pdf bytes", "w9.pdf")
        assert result["form_type"] == "W-9"

    def test_name_is_extracted(self) -> None:
        extractor = _make_extractor(_json_response(_FULL_W9_RESPONSE))
        result = extractor.extract(b"dummy pdf bytes", "w9.pdf")
        assert result["name"] == "James Whitfield"

    def test_tin_is_extracted(self) -> None:
        extractor = _make_extractor(_json_response(_FULL_W9_RESPONSE))
        result = extractor.extract(b"dummy pdf bytes", "w9.pdf")
        assert result["tin"] == "512-74-9301"

    def test_tin_type_is_extracted(self) -> None:
        extractor = _make_extractor(_json_response(_FULL_W9_RESPONSE))
        result = extractor.extract(b"dummy pdf bytes", "w9.pdf")
        assert result["tin_type"] == "SSN"

    def test_federal_tax_classification_is_extracted(self) -> None:
        extractor = _make_extractor(_json_response(_FULL_W9_RESPONSE))
        result = extractor.extract(b"dummy pdf bytes", "w9.pdf")
        assert result["federal_tax_classification"] == (
            "Individual/sole proprietor or single-member LLC"
        )

    def test_signature_present_is_extracted(self) -> None:
        extractor = _make_extractor(_json_response(_FULL_W9_RESPONSE))
        result = extractor.extract(b"dummy pdf bytes", "w9.pdf")
        assert result["signature_present"] is True

    def test_signature_date_is_extracted(self) -> None:
        extractor = _make_extractor(_json_response(_FULL_W9_RESPONSE))
        result = extractor.extract(b"dummy pdf bytes", "w9.pdf")
        assert result["signature_date"] == "2024-03-15"

    def test_exempt_payee_code_none_when_null_in_response(self) -> None:
        extractor = _make_extractor(_json_response(_FULL_W9_RESPONSE))
        result = extractor.extract(b"dummy pdf bytes", "w9.pdf")
        assert result["exempt_payee_code"] is None

    def test_business_name_none_when_null_in_response(self) -> None:
        extractor = _make_extractor(_json_response(_FULL_W9_RESPONSE))
        result = extractor.extract(b"dummy pdf bytes", "w9.pdf")
        assert result["business_name"] is None


# ---------------------------------------------------------------------------
# Missing / illegible field handling
# ---------------------------------------------------------------------------


class TestClaudeW9ExtractorMissingFields:
    def test_missing_tin_returns_none(self) -> None:
        data = {**_FULL_W9_RESPONSE, "tin": None}
        extractor = _make_extractor(_json_response(data))
        result = extractor.extract(b"dummy", "w9.pdf")
        assert result["tin"] is None

    def test_missing_signature_date_returns_none(self) -> None:
        data = {**_FULL_W9_RESPONSE, "signature_date": None}
        extractor = _make_extractor(_json_response(data))
        result = extractor.extract(b"dummy", "w9.pdf")
        assert result["signature_date"] is None

    def test_signature_present_false_when_unsigned(self) -> None:
        data = {**_FULL_W9_RESPONSE, "signature_present": False, "signature_date": None}
        extractor = _make_extractor(_json_response(data))
        result = extractor.extract(b"dummy", "w9.pdf")
        assert result["signature_present"] is False
        assert result["signature_date"] is None

    def test_signature_present_null_when_illegible(self) -> None:
        data = {**_FULL_W9_RESPONSE, "signature_present": None}
        extractor = _make_extractor(_json_response(data))
        result = extractor.extract(b"dummy", "w9.pdf")
        assert result["signature_present"] is None

    def test_tin_type_null_for_illegible_tin(self) -> None:
        data = {**_FULL_W9_RESPONSE, "tin": None, "tin_type": None}
        extractor = _make_extractor(_json_response(data))
        result = extractor.extract(b"dummy", "w9.pdf")
        assert result["tin"] is None
        assert result["tin_type"] is None

    def test_form_type_forced_to_w9_even_if_claude_returns_other(self) -> None:
        data = {**_FULL_W9_RESPONSE, "form_type": "W-8BEN"}
        extractor = _make_extractor(_json_response(data))
        result = extractor.extract(b"dummy", "w9.pdf")
        # The extractor always overwrites form_type to "W-9".
        assert result["form_type"] == "W-9"


# ---------------------------------------------------------------------------
# Markdown code-fence stripping
# ---------------------------------------------------------------------------


class TestClaudeW9ExtractorCodeFenceStripping:
    def test_json_fenced_with_backticks_is_parsed(self) -> None:
        fenced = "```json\n" + _json_response(_FULL_W9_RESPONSE) + "\n```"
        extractor = _make_extractor(fenced)
        result = extractor.extract(b"dummy", "w9.pdf")
        assert result["name"] == "James Whitfield"

    def test_json_fenced_without_language_tag_is_parsed(self) -> None:
        fenced = "```\n" + _json_response(_FULL_W9_RESPONSE) + "\n```"
        extractor = _make_extractor(fenced)
        result = extractor.extract(b"dummy", "w9.pdf")
        assert result["name"] == "James Whitfield"


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestClaudeW9ExtractorErrorCases:
    def test_non_json_response_raises_extraction_error(self) -> None:
        extractor = _make_extractor("Sorry, I cannot read this PDF.")
        with pytest.raises(TaxFormExtractionError, match="not valid JSON"):
            extractor.extract(b"dummy", "w9.pdf")

    def test_json_array_response_raises_extraction_error(self) -> None:
        extractor = _make_extractor("[1, 2, 3]")
        with pytest.raises(TaxFormExtractionError, match="list"):
            extractor.extract(b"dummy", "w9.pdf")

    def test_anthropic_api_error_raises_extraction_error(self) -> None:
        from anthropic import APIError

        extractor = ClaudeW9Extractor(
            api_key="test-key",
            model="claude-3-5-sonnet-20241022",
            fallback_to_text=True,
        )
        extractor._client = MagicMock()
        extractor._client.messages.create.side_effect = APIError(
            message="Rate limit exceeded",
            request=MagicMock(),
            body=None,
        )
        with pytest.raises(TaxFormExtractionError, match="Anthropic API error"):
            extractor.extract(b"dummy", "w9.pdf")

    def test_unicode_decode_error_in_text_fallback_raises_extraction_error(self) -> None:
        extractor = ClaudeW9Extractor(
            api_key="test-key",
            model="claude-3-5-sonnet-20241022",
            fallback_to_text=True,
        )
        # Non-UTF-8 bytes to force a UnicodeDecodeError in text-fallback mode.
        with pytest.raises(TaxFormExtractionError, match="UTF-8"):
            extractor.extract(b"\xff\xfe not utf-8", "w9.pdf")


# ---------------------------------------------------------------------------
# James Whitfield full-pipeline test
# ---------------------------------------------------------------------------


class TestJamesWhitfieldCase:
    """Verify the James Whitfield fixture flows end-to-end through the PDF
    extraction use case via the ClaudeW9Extractor (with mocked Claude)."""

    def _make_use_case(self, claude_response: dict) -> ParsePdfFormFieldsUseCase:
        extractor = _make_extractor(_json_response(claude_response))
        return ParsePdfFormFieldsUseCase(extractor)

    def test_james_whitfield_fixture_can_be_loaded(self) -> None:
        fixture_path = FIXTURES_DIR / "w9_james_whitfield.json"
        assert fixture_path.exists(), "w9_james_whitfield.json fixture is missing"
        data = json.loads(fixture_path.read_text())
        assert data["name"] == "James Whitfield"

    def test_james_whitfield_full_pipeline_returns_w9(self) -> None:
        use_case = self._make_use_case(_FULL_W9_RESPONSE)
        result = use_case.execute(b"fake pdf bytes", "w9_james_whitfield.pdf")
        assert result.form_type == "W-9"

    def test_james_whitfield_name_is_preserved(self) -> None:
        use_case = self._make_use_case(_FULL_W9_RESPONSE)
        result = use_case.execute(b"fake pdf bytes", "w9_james_whitfield.pdf")
        assert result.name == "James Whitfield"

    def test_james_whitfield_tin_is_preserved(self) -> None:
        use_case = self._make_use_case(_FULL_W9_RESPONSE)
        result = use_case.execute(b"fake pdf bytes", "w9_james_whitfield.pdf")
        assert result.tin == "512-74-9301"

    def test_james_whitfield_tin_type_is_ssn(self) -> None:
        use_case = self._make_use_case(_FULL_W9_RESPONSE)
        result = use_case.execute(b"fake pdf bytes", "w9_james_whitfield.pdf")
        assert result.tin_type == "SSN"

    def test_james_whitfield_classification_is_individual(self) -> None:
        use_case = self._make_use_case(_FULL_W9_RESPONSE)
        result = use_case.execute(b"fake pdf bytes", "w9_james_whitfield.pdf")
        assert "Individual" in (result.federal_tax_classification or "")

    def test_james_whitfield_signature_present(self) -> None:
        use_case = self._make_use_case(_FULL_W9_RESPONSE)
        result = use_case.execute(b"fake pdf bytes", "w9_james_whitfield.pdf")
        assert result.signature_present is True

    def test_james_whitfield_signature_date(self) -> None:
        use_case = self._make_use_case(_FULL_W9_RESPONSE)
        result = use_case.execute(b"fake pdf bytes", "w9_james_whitfield.pdf")
        assert result.signature_date == "2024-03-15"

    def test_james_whitfield_no_exemptions_are_none(self) -> None:
        use_case = self._make_use_case(_FULL_W9_RESPONSE)
        result = use_case.execute(b"fake pdf bytes", "w9_james_whitfield.pdf")
        assert result.exempt_payee_code is None
        assert result.exemption_from_fatca_code is None

    def test_james_whitfield_partial_data_signature_null(self) -> None:
        """Verify that a partially-filled form (no signature) does not fail."""
        partial = {
            **_FULL_W9_RESPONSE,
            "signature_present": False,
            "signature_date": None,
        }
        use_case = self._make_use_case(partial)
        result = use_case.execute(b"fake pdf bytes", "w9_james_whitfield_unsigned.pdf")
        assert result.signature_present is False
        assert result.signature_date is None

    def test_james_whitfield_illegible_tin_does_not_raise(self) -> None:
        """A null TIN should NOT raise — it is flagged null, not an error."""
        illegible = {
            **_FULL_W9_RESPONSE,
            "tin": None,
            "tin_type": None,
        }
        use_case = self._make_use_case(illegible)
        result = use_case.execute(b"fake pdf bytes", "w9_james_whitfield_no_tin.pdf")
        assert result.tin is None
        assert result.tin_type is None
