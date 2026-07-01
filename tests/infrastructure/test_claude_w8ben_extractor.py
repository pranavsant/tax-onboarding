"""Unit tests for ClaudeW8BENExtractor.

All tests mock the Anthropic client so no real API calls are made.

Verifies that:
- A well-formed Claude response is parsed into the expected dict.
- Missing / null fields in Claude's response are returned as None.
- Part II treaty section returns all null fields when entirely blank.
- Markdown code-fence wrapping is stripped before JSON parsing.
- An Anthropic APIError is translated into TaxFormExtractionError.
- A non-JSON Claude response raises TaxFormExtractionError.
- form_type is always forced to "W-8BEN".
- The Mariana Costa Ribeiro fixture case produces the expected output
  when wired through the full ParsePdfFormFieldsUseCase pipeline.
"""
from __future__ import annotations

import json
import pathlib
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.application.exceptions import TaxFormExtractionError
from src.application.use_cases.parse_pdf_form_fields import ParsePdfFormFieldsUseCase
from src.infrastructure.pdf.claude_w8ben_extractor import ClaudeW8BENExtractor

FIXTURES_DIR = pathlib.Path(__file__).parent.parent / "fixtures"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FULL_W8BEN_RESPONSE: dict[str, Any] = {
    "form_type": "W-8BEN",
    "name": "Mariana Costa Ribeiro",
    "country_of_citizenship": "Brazil",
    "permanent_address": "Avenida Paulista, 1578, Apto 42",
    "permanent_address_city_country": "São Paulo, SP, Brazil",
    "mailing_address": None,
    "mailing_address_city_country": None,
    "us_tin": None,
    "foreign_tin": "987.654.321-00",
    "ftin_not_required": None,
    "reference_numbers": None,
    "date_of_birth": "1990-04-22",
    "treaty_country": "Brazil",
    "treaty_article": "Article 11",
    "withholding_rate": "15%",
    "income_type": "Dividends",
    "treaty_conditions": (
        "The beneficial owner is a resident of Brazil within the meaning of "
        "the income tax convention between Brazil and the United States."
    ),
    "signature_present": True,
    "signature_date": "2024-06-10",
}


def _make_extractor(claude_text_response: str) -> ClaudeW8BENExtractor:
    """Return a ClaudeW8BENExtractor whose Anthropic client is fully mocked."""
    extractor = ClaudeW8BENExtractor(
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


class TestClaudeW8BENExtractorHappyPath:
    def test_returns_dict(self) -> None:
        extractor = _make_extractor(_json_response(_FULL_W8BEN_RESPONSE))
        result = extractor.extract(b"dummy pdf bytes", "w8ben.pdf")
        assert isinstance(result, dict)

    def test_form_type_is_w8ben(self) -> None:
        extractor = _make_extractor(_json_response(_FULL_W8BEN_RESPONSE))
        result = extractor.extract(b"dummy pdf bytes", "w8ben.pdf")
        assert result["form_type"] == "W-8BEN"

    def test_name_is_extracted(self) -> None:
        extractor = _make_extractor(_json_response(_FULL_W8BEN_RESPONSE))
        result = extractor.extract(b"dummy pdf bytes", "w8ben.pdf")
        assert result["name"] == "Mariana Costa Ribeiro"

    def test_country_of_citizenship_is_extracted(self) -> None:
        extractor = _make_extractor(_json_response(_FULL_W8BEN_RESPONSE))
        result = extractor.extract(b"dummy pdf bytes", "w8ben.pdf")
        assert result["country_of_citizenship"] == "Brazil"

    def test_permanent_address_is_extracted(self) -> None:
        extractor = _make_extractor(_json_response(_FULL_W8BEN_RESPONSE))
        result = extractor.extract(b"dummy pdf bytes", "w8ben.pdf")
        assert result["permanent_address"] == "Avenida Paulista, 1578, Apto 42"

    def test_permanent_address_city_country_is_extracted(self) -> None:
        extractor = _make_extractor(_json_response(_FULL_W8BEN_RESPONSE))
        result = extractor.extract(b"dummy pdf bytes", "w8ben.pdf")
        assert result["permanent_address_city_country"] == "São Paulo, SP, Brazil"

    def test_foreign_tin_is_extracted(self) -> None:
        extractor = _make_extractor(_json_response(_FULL_W8BEN_RESPONSE))
        result = extractor.extract(b"dummy pdf bytes", "w8ben.pdf")
        assert result["foreign_tin"] == "987.654.321-00"

    def test_date_of_birth_is_extracted(self) -> None:
        extractor = _make_extractor(_json_response(_FULL_W8BEN_RESPONSE))
        result = extractor.extract(b"dummy pdf bytes", "w8ben.pdf")
        assert result["date_of_birth"] == "1990-04-22"

    def test_treaty_country_is_extracted(self) -> None:
        extractor = _make_extractor(_json_response(_FULL_W8BEN_RESPONSE))
        result = extractor.extract(b"dummy pdf bytes", "w8ben.pdf")
        assert result["treaty_country"] == "Brazil"

    def test_treaty_article_is_extracted(self) -> None:
        extractor = _make_extractor(_json_response(_FULL_W8BEN_RESPONSE))
        result = extractor.extract(b"dummy pdf bytes", "w8ben.pdf")
        assert result["treaty_article"] == "Article 11"

    def test_withholding_rate_is_extracted(self) -> None:
        extractor = _make_extractor(_json_response(_FULL_W8BEN_RESPONSE))
        result = extractor.extract(b"dummy pdf bytes", "w8ben.pdf")
        assert result["withholding_rate"] == "15%"

    def test_income_type_is_extracted(self) -> None:
        extractor = _make_extractor(_json_response(_FULL_W8BEN_RESPONSE))
        result = extractor.extract(b"dummy pdf bytes", "w8ben.pdf")
        assert result["income_type"] == "Dividends"

    def test_treaty_conditions_is_extracted(self) -> None:
        extractor = _make_extractor(_json_response(_FULL_W8BEN_RESPONSE))
        result = extractor.extract(b"dummy pdf bytes", "w8ben.pdf")
        assert result["treaty_conditions"] is not None
        assert "Brazil" in result["treaty_conditions"]

    def test_signature_present_is_extracted(self) -> None:
        extractor = _make_extractor(_json_response(_FULL_W8BEN_RESPONSE))
        result = extractor.extract(b"dummy pdf bytes", "w8ben.pdf")
        assert result["signature_present"] is True

    def test_signature_date_is_extracted(self) -> None:
        extractor = _make_extractor(_json_response(_FULL_W8BEN_RESPONSE))
        result = extractor.extract(b"dummy pdf bytes", "w8ben.pdf")
        assert result["signature_date"] == "2024-06-10"

    def test_optional_fields_none_when_null_in_response(self) -> None:
        extractor = _make_extractor(_json_response(_FULL_W8BEN_RESPONSE))
        result = extractor.extract(b"dummy pdf bytes", "w8ben.pdf")
        assert result["mailing_address"] is None
        assert result["us_tin"] is None
        assert result["reference_numbers"] is None


# ---------------------------------------------------------------------------
# Part II treaty section handling
# ---------------------------------------------------------------------------


class TestClaudeW8BENExtractorTreatySection:
    def test_blank_part_ii_all_treaty_fields_are_null(self) -> None:
        """When the entire Part II is blank, all five treaty fields are null."""
        data = {
            **_FULL_W8BEN_RESPONSE,
            "treaty_country": None,
            "treaty_article": None,
            "withholding_rate": None,
            "income_type": None,
            "treaty_conditions": None,
        }
        extractor = _make_extractor(_json_response(data))
        result = extractor.extract(b"dummy", "w8ben.pdf")
        assert result["treaty_country"] is None
        assert result["treaty_article"] is None
        assert result["withholding_rate"] is None
        assert result["income_type"] is None
        assert result["treaty_conditions"] is None

    def test_partial_part_ii_only_filled_fields_are_non_null(self) -> None:
        """Partial Part II (country only, rest blank) is allowed."""
        data = {
            **_FULL_W8BEN_RESPONSE,
            "treaty_country": "Brazil",
            "treaty_article": None,
            "withholding_rate": None,
            "income_type": None,
            "treaty_conditions": None,
        }
        extractor = _make_extractor(_json_response(data))
        result = extractor.extract(b"dummy", "w8ben.pdf")
        assert result["treaty_country"] == "Brazil"
        assert result["treaty_article"] is None

    def test_full_part_ii_returns_all_treaty_fields(self) -> None:
        extractor = _make_extractor(_json_response(_FULL_W8BEN_RESPONSE))
        result = extractor.extract(b"dummy", "w8ben.pdf")
        assert result["treaty_country"] == "Brazil"
        assert result["treaty_article"] == "Article 11"
        assert result["withholding_rate"] == "15%"
        assert result["income_type"] == "Dividends"
        assert result["treaty_conditions"] is not None


# ---------------------------------------------------------------------------
# Missing / illegible field handling
# ---------------------------------------------------------------------------


class TestClaudeW8BENExtractorMissingFields:
    def test_missing_foreign_tin_returns_none(self) -> None:
        data = {**_FULL_W8BEN_RESPONSE, "foreign_tin": None}
        extractor = _make_extractor(_json_response(data))
        result = extractor.extract(b"dummy", "w8ben.pdf")
        assert result["foreign_tin"] is None

    def test_missing_date_of_birth_returns_none(self) -> None:
        data = {**_FULL_W8BEN_RESPONSE, "date_of_birth": None}
        extractor = _make_extractor(_json_response(data))
        result = extractor.extract(b"dummy", "w8ben.pdf")
        assert result["date_of_birth"] is None

    def test_signature_present_false_when_unsigned(self) -> None:
        data = {**_FULL_W8BEN_RESPONSE, "signature_present": False, "signature_date": None}
        extractor = _make_extractor(_json_response(data))
        result = extractor.extract(b"dummy", "w8ben.pdf")
        assert result["signature_present"] is False
        assert result["signature_date"] is None

    def test_signature_present_null_when_illegible(self) -> None:
        data = {**_FULL_W8BEN_RESPONSE, "signature_present": None}
        extractor = _make_extractor(_json_response(data))
        result = extractor.extract(b"dummy", "w8ben.pdf")
        assert result["signature_present"] is None

    def test_ftin_not_required_true(self) -> None:
        data = {**_FULL_W8BEN_RESPONSE, "foreign_tin": None, "ftin_not_required": True}
        extractor = _make_extractor(_json_response(data))
        result = extractor.extract(b"dummy", "w8ben.pdf")
        assert result["ftin_not_required"] is True
        assert result["foreign_tin"] is None

    def test_form_type_forced_to_w8ben_even_if_claude_returns_other(self) -> None:
        data = {**_FULL_W8BEN_RESPONSE, "form_type": "W-9"}
        extractor = _make_extractor(_json_response(data))
        result = extractor.extract(b"dummy", "w8ben.pdf")
        # The extractor always overwrites form_type to "W-8BEN".
        assert result["form_type"] == "W-8BEN"


# ---------------------------------------------------------------------------
# Markdown code-fence stripping
# ---------------------------------------------------------------------------


class TestClaudeW8BENExtractorCodeFenceStripping:
    def test_json_fenced_with_backticks_is_parsed(self) -> None:
        fenced = "```json\n" + _json_response(_FULL_W8BEN_RESPONSE) + "\n```"
        extractor = _make_extractor(fenced)
        result = extractor.extract(b"dummy", "w8ben.pdf")
        assert result["name"] == "Mariana Costa Ribeiro"

    def test_json_fenced_without_language_tag_is_parsed(self) -> None:
        fenced = "```\n" + _json_response(_FULL_W8BEN_RESPONSE) + "\n```"
        extractor = _make_extractor(fenced)
        result = extractor.extract(b"dummy", "w8ben.pdf")
        assert result["name"] == "Mariana Costa Ribeiro"


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestClaudeW8BENExtractorErrorCases:
    def test_non_json_response_raises_extraction_error(self) -> None:
        extractor = _make_extractor("Sorry, I cannot read this PDF.")
        with pytest.raises(TaxFormExtractionError, match="not valid JSON"):
            extractor.extract(b"dummy", "w8ben.pdf")

    def test_json_array_response_raises_extraction_error(self) -> None:
        extractor = _make_extractor("[1, 2, 3]")
        with pytest.raises(TaxFormExtractionError, match="list"):
            extractor.extract(b"dummy", "w8ben.pdf")

    def test_anthropic_api_error_raises_extraction_error(self) -> None:
        from anthropic import APIError

        extractor = ClaudeW8BENExtractor(
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
            extractor.extract(b"dummy", "w8ben.pdf")

    def test_unicode_decode_error_in_text_fallback_raises_extraction_error(self) -> None:
        extractor = ClaudeW8BENExtractor(
            api_key="test-key",
            model="claude-3-5-sonnet-20241022",
            fallback_to_text=True,
        )
        # Non-UTF-8 bytes to force a UnicodeDecodeError in text-fallback mode.
        with pytest.raises(TaxFormExtractionError, match="UTF-8"):
            extractor.extract(b"\xff\xfe not utf-8", "w8ben.pdf")


# ---------------------------------------------------------------------------
# Mariana Costa Ribeiro full-pipeline test
# ---------------------------------------------------------------------------


class TestMarianaCostRibeiroCase:
    """Verify the Mariana Costa Ribeiro fixture flows end-to-end through the
    PDF extraction use case via the ClaudeW8BENExtractor (with mocked Claude).
    """

    def _make_use_case(self, claude_response: dict) -> ParsePdfFormFieldsUseCase:
        extractor = _make_extractor(_json_response(claude_response))
        return ParsePdfFormFieldsUseCase(extractor)

    def test_mariana_fixture_can_be_loaded(self) -> None:
        fixture_path = FIXTURES_DIR / "w8ben_mariana_costa_ribeiro.json"
        assert fixture_path.exists(), "w8ben_mariana_costa_ribeiro.json fixture is missing"
        data = json.loads(fixture_path.read_text())
        assert data["name"] == "Mariana Costa Ribeiro"

    def test_mariana_full_pipeline_returns_w8ben(self) -> None:
        use_case = self._make_use_case(_FULL_W8BEN_RESPONSE)
        result = use_case.execute(b"fake pdf bytes", "w8ben_mariana_costa_ribeiro.pdf")
        assert result.form_type == "W-8BEN"

    def test_mariana_name_is_preserved(self) -> None:
        use_case = self._make_use_case(_FULL_W8BEN_RESPONSE)
        result = use_case.execute(b"fake pdf bytes", "w8ben_mariana_costa_ribeiro.pdf")
        assert result.name == "Mariana Costa Ribeiro"

    def test_mariana_country_of_citizenship_is_brazil(self) -> None:
        use_case = self._make_use_case(_FULL_W8BEN_RESPONSE)
        result = use_case.execute(b"fake pdf bytes", "w8ben_mariana_costa_ribeiro.pdf")
        assert result.country_of_citizenship == "Brazil"

    def test_mariana_foreign_tin_is_preserved(self) -> None:
        use_case = self._make_use_case(_FULL_W8BEN_RESPONSE)
        result = use_case.execute(b"fake pdf bytes", "w8ben_mariana_costa_ribeiro.pdf")
        assert result.foreign_tin == "987.654.321-00"

    def test_mariana_treaty_country_is_brazil(self) -> None:
        use_case = self._make_use_case(_FULL_W8BEN_RESPONSE)
        result = use_case.execute(b"fake pdf bytes", "w8ben_mariana_costa_ribeiro.pdf")
        assert result.treaty_country == "Brazil"

    def test_mariana_treaty_article_is_article_11(self) -> None:
        use_case = self._make_use_case(_FULL_W8BEN_RESPONSE)
        result = use_case.execute(b"fake pdf bytes", "w8ben_mariana_costa_ribeiro.pdf")
        assert result.treaty_article == "Article 11"

    def test_mariana_withholding_rate_is_15_percent(self) -> None:
        use_case = self._make_use_case(_FULL_W8BEN_RESPONSE)
        result = use_case.execute(b"fake pdf bytes", "w8ben_mariana_costa_ribeiro.pdf")
        assert result.withholding_rate == "15%"

    def test_mariana_income_type_is_dividends(self) -> None:
        use_case = self._make_use_case(_FULL_W8BEN_RESPONSE)
        result = use_case.execute(b"fake pdf bytes", "w8ben_mariana_costa_ribeiro.pdf")
        assert result.income_type == "Dividends"

    def test_mariana_treaty_conditions_contains_brazil(self) -> None:
        use_case = self._make_use_case(_FULL_W8BEN_RESPONSE)
        result = use_case.execute(b"fake pdf bytes", "w8ben_mariana_costa_ribeiro.pdf")
        assert result.treaty_conditions is not None
        assert "Brazil" in result.treaty_conditions

    def test_mariana_signature_present(self) -> None:
        use_case = self._make_use_case(_FULL_W8BEN_RESPONSE)
        result = use_case.execute(b"fake pdf bytes", "w8ben_mariana_costa_ribeiro.pdf")
        assert result.signature_present is True

    def test_mariana_signature_date(self) -> None:
        use_case = self._make_use_case(_FULL_W8BEN_RESPONSE)
        result = use_case.execute(b"fake pdf bytes", "w8ben_mariana_costa_ribeiro.pdf")
        assert result.signature_date == "2024-06-10"

    def test_mariana_no_us_tin(self) -> None:
        use_case = self._make_use_case(_FULL_W8BEN_RESPONSE)
        result = use_case.execute(b"fake pdf bytes", "w8ben_mariana_costa_ribeiro.pdf")
        assert result.us_tin is None

    def test_mariana_blank_part_ii_does_not_fail(self) -> None:
        """Verify that a W-8BEN with no treaty claim (blank Part II) works."""
        no_treaty = {
            **_FULL_W8BEN_RESPONSE,
            "treaty_country": None,
            "treaty_article": None,
            "withholding_rate": None,
            "income_type": None,
            "treaty_conditions": None,
        }
        use_case = self._make_use_case(no_treaty)
        result = use_case.execute(b"fake pdf bytes", "w8ben_mariana_no_treaty.pdf")
        assert result.form_type == "W-8BEN"
        assert result.treaty_country is None
        assert result.treaty_article is None

    def test_mariana_illegible_foreign_tin_does_not_raise(self) -> None:
        """A null foreign TIN should NOT raise — it is flagged null."""
        no_tin = {
            **_FULL_W8BEN_RESPONSE,
            "foreign_tin": None,
            "ftin_not_required": None,
        }
        use_case = self._make_use_case(no_tin)
        result = use_case.execute(b"fake pdf bytes", "w8ben_mariana_no_tin.pdf")
        assert result.foreign_tin is None

    def test_mariana_partial_data_signature_null(self) -> None:
        """Verify that a partially-filled form (no signature) does not fail."""
        partial = {
            **_FULL_W8BEN_RESPONSE,
            "signature_present": False,
            "signature_date": None,
        }
        use_case = self._make_use_case(partial)
        result = use_case.execute(b"fake pdf bytes", "w8ben_mariana_unsigned.pdf")
        assert result.signature_present is False
        assert result.signature_date is None

    def test_mariana_fixture_matches_full_response(self) -> None:
        """Fixture JSON and the _FULL_W8BEN_RESPONSE constant agree on key fields."""
        fixture_path = FIXTURES_DIR / "w8ben_mariana_costa_ribeiro.json"
        data = json.loads(fixture_path.read_text())
        assert data["name"] == _FULL_W8BEN_RESPONSE["name"]
        assert data["country_of_citizenship"] == _FULL_W8BEN_RESPONSE["country_of_citizenship"]
        assert data["foreign_tin"] == _FULL_W8BEN_RESPONSE["foreign_tin"]
        assert data["treaty_country"] == _FULL_W8BEN_RESPONSE["treaty_country"]
        assert data["treaty_article"] == _FULL_W8BEN_RESPONSE["treaty_article"]
        assert data["signature_present"] == _FULL_W8BEN_RESPONSE["signature_present"]
        assert data["signature_date"] == _FULL_W8BEN_RESPONSE["signature_date"]
