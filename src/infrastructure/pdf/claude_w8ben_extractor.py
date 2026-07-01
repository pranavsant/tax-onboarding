"""Claude-based W-8BEN PDF extractor.

Uses the Anthropic API to extract structured fields from a W-8BEN PDF or
scan.  The PDF bytes are sent to Claude as a base64-encoded document
block; Claude returns a JSON object with all recognised W-8BEN fields plus
extraction-time fields (``signature_present`` and ``signature_date``).

Design decisions
----------------
- **Null-over-failure**: any field that is missing, blank, or illegible
  in the source document is returned as ``null`` in Claude's JSON
  response rather than causing an extraction failure.  This lets
  downstream validation distinguish "field was absent on the form" from
  "field was never asked for".
- **Part II treaty section**: Claude is instructed to return each Part II
  field individually.  When the entire Part II section is blank, all treaty
  fields (``treaty_country``, ``treaty_article``, ``withholding_rate``,
  ``income_type``, ``treaty_conditions``) are returned as ``null``.  This
  matches the ``ParsedFormFieldsDTO`` treaty field set so no additional
  translation is required.
- **Strict JSON output**: the prompt instructs Claude to respond with
  *only* a JSON object and no surrounding prose.  A ``json.JSONDecodeError``
  is surfaced as ``TaxFormExtractionError`` so callers always deal with a
  single exception type for extraction failures.
- **Form-type assumption**: this extractor always sets ``form_type`` to
  ``"W-8BEN"`` because it is purpose-built for that form.
- **PDF document blocks**: the Anthropic Messages API (model
  ``claude-3-5-sonnet-20241022`` and later) accepts PDF files directly via
  ``{"type": "document", "source": {"type": "base64", …}}``.  For older
  models, or when ``fallback_to_text=True`` is set, the extractor falls
  back to treating the bytes as UTF-8 text (useful for testing with
  text-encoded fixtures).
"""
from __future__ import annotations

import base64
import json
from typing import Any, Optional

from anthropic import Anthropic, APIError

from src.application.exceptions import TaxFormExtractionError
from src.application.ports.tax_form_extractor import TaxFormExtractorPort
from src.infrastructure.config import get_settings

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a precise document data-extraction assistant. "
    "Extract structured fields from IRS tax forms exactly as they appear. "
    "Return ONLY a valid JSON object — no markdown, no explanation, no preamble. "
    "Use null (JSON null, not the string \"null\") for any field that is missing, "
    "blank, or illegible."
)

_EXTRACTION_PROMPT = """Extract every field from this W-8BEN (Certificate of Foreign Status of \
Beneficial Owner for United States Tax Withholding and Reporting) form and return a single JSON \
object with EXACTLY these keys:

{
  "form_type": "W-8BEN",
  "name": <string or null>,
  "country_of_citizenship": <string or null>,
  "permanent_address": <string or null>,
  "permanent_address_city_country": <string or null>,
  "mailing_address": <string or null>,
  "mailing_address_city_country": <string or null>,
  "us_tin": <string or null>,
  "foreign_tin": <string or null>,
  "ftin_not_required": <true | false | null>,
  "reference_numbers": <string or null>,
  "date_of_birth": <"YYYY-MM-DD" | null>,
  "treaty_country": <string or null>,
  "treaty_article": <string or null>,
  "withholding_rate": <string or null>,
  "income_type": <string or null>,
  "treaty_conditions": <string or null>,
  "signature_present": <true | false | null>,
  "signature_date": <"YYYY-MM-DD" | null>
}

Rules:
- "name" is Line 1 (the individual's legal name exactly as printed).
- "country_of_citizenship" is Line 2 (country of citizenship).
- "permanent_address" is Line 3 (street, apt, suite; city or town).
- "permanent_address_city_country" is Line 3 continued (state or \
province, postal code, country).
- "mailing_address" is Line 4 (if different from line 3 — street, \
apt, suite; city or town); null if blank.
- "mailing_address_city_country" is Line 4 continued; null if blank.
- "us_tin" is Line 5 (U.S. taxpayer identification number — SSN or \
ITIN); null if blank.
- "foreign_tin" is Line 6a (foreign tax identifying number); null if \
blank.
- "ftin_not_required" is true if the Line 6b checkbox is checked, \
false if explicitly unchecked, null if indeterminate.
- "reference_numbers" is Line 7; null if blank.
- "date_of_birth" is Line 8 in ISO 8601 format (YYYY-MM-DD); null if \
absent or illegible.
- Part II (Claim of Tax Treaty Benefits):
  - "treaty_country" is Line 9 (country for treaty claim); null if \
Part II is entirely blank.
  - "treaty_article" is Line 10 (article of the treaty); null if \
Part II is blank or not completed.
  - "withholding_rate" is Line 10 (withholding rate percentage, e.g. \
"15%"); null if not completed.
  - "income_type" is Line 10 (type of income); null if not completed.
  - "treaty_conditions" is Line 10 (additional conditions or \
explanations from the treaty); null if not completed.
  If the entire Part II section is blank or absent, set all five \
treaty fields to null.
- "signature_present" is true if a handwritten or electronic signature \
is visible in the certification section; false if the signature line is \
blank; null if you cannot determine.
- "signature_date" is the date written next to the signature in \
ISO 8601 format (YYYY-MM-DD); null if absent or illegible.
- Return null for any field you cannot read or that does not appear on \
the form.
- Do NOT add extra keys.
- Respond with ONLY the JSON object."""


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------


class ClaudeW8BENExtractor(TaxFormExtractorPort):
    """Extract W-8BEN form fields from a PDF using the Claude API.

    Args:
        api_key:          Anthropic API key.  Defaults to the value from
                          :func:`~src.infrastructure.config.get_settings`.
        model:            Claude model identifier.  Defaults to the value
                          from settings.
        max_tokens:       Maximum tokens in Claude's response.  1 024 is
                          ample for a JSON field listing.
        fallback_to_text: When ``True`` the extractor attempts to decode the
                          bytes as UTF-8 and passes them as a text message
                          instead of a PDF document block.  Useful when
                          testing with plain-text fixtures.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 1024,
        fallback_to_text: bool = False,
    ) -> None:
        settings = get_settings()
        self._client = Anthropic(api_key=api_key or settings.anthropic_api_key)
        self._model = model or settings.anthropic_model
        self._max_tokens = max_tokens
        self._fallback_to_text = fallback_to_text

    # ------------------------------------------------------------------
    # TaxFormExtractorPort implementation
    # ------------------------------------------------------------------

    def extract(self, file_bytes: bytes, filename: str) -> dict:  # noqa: ARG002
        """Send *file_bytes* to Claude and return a structured field dict.

        The returned dictionary always contains ``"form_type": "W-8BEN"``
        and the keys listed in ``_EXTRACTION_PROMPT``.  Any field that
        Claude could not determine is ``None``.

        Args:
            file_bytes: Raw bytes of the W-8BEN PDF (or UTF-8 text when
                        ``fallback_to_text=True``).
            filename:   Ignored; present to satisfy the port contract.

        Returns:
            A ``dict`` with ``"form_type"`` and all W-8BEN field keys.

        Raises:
            TaxFormExtractionError: If the Anthropic API call fails or
                Claude's response cannot be parsed as JSON.
        """
        user_content = self._build_user_content(file_bytes)
        raw_text = self._call_claude(user_content)
        return self._parse_response(raw_text)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_user_content(self, file_bytes: bytes) -> list[dict[str, Any]]:
        """Build the ``messages[0].content`` list for the Anthropic API."""
        if self._fallback_to_text:
            try:
                text = file_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise TaxFormExtractionError(
                    f"Could not decode file as UTF-8 for text fallback: {exc}"
                ) from exc
            return [
                {
                    "type": "text",
                    "text": f"{_EXTRACTION_PROMPT}\n\n---\n{text}",
                }
            ]

        # Primary path: send as a base64-encoded PDF document block.
        b64 = base64.standard_b64encode(file_bytes).decode("ascii")
        return [
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": b64,
                },
            },
            {
                "type": "text",
                "text": _EXTRACTION_PROMPT,
            },
        ]

    def _call_claude(self, user_content: list[dict[str, Any]]) -> str:
        """Invoke the Anthropic Messages API and return the text response."""
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
        except APIError as exc:
            raise TaxFormExtractionError(
                f"Anthropic API error while extracting W-8BEN fields: {exc}"
            ) from exc

        # Concatenate all text blocks in the response.
        return "".join(
            block.text
            for block in response.content
            if getattr(block, "type", "") == "text"
        )

    def _parse_response(self, raw_text: str) -> dict:
        """Parse *raw_text* as JSON and return the resulting ``dict``.

        Strips optional markdown code fences that some model versions may
        still emit despite the prompt instruction.
        """
        text = raw_text.strip()
        # Strip ```json … ``` or ``` … ``` fences if present.
        if text.startswith("```"):
            lines = text.splitlines()
            # Drop first line (``` or ```json) and last line (```)
            inner_lines = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            text = "\n".join(inner_lines).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise TaxFormExtractionError(
                f"Claude returned a response that is not valid JSON: {exc}. "
                f"Raw response (first 500 chars): {raw_text[:500]!r}"
            ) from exc

        if not isinstance(data, dict):
            raise TaxFormExtractionError(
                f"Claude returned a JSON value of type {type(data).__name__!r} "
                "instead of a JSON object."
            )

        # Ensure form_type is always set to "W-8BEN" regardless of what
        # Claude returned — this extractor is W-8BEN-specific.
        data["form_type"] = "W-8BEN"
        return data
