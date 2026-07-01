"""Claude-based W-9 PDF extractor.

Uses the Anthropic API to extract structured fields from a W-9 PDF or
scan.  The PDF bytes are sent to Claude as a base64-encoded document
block; Claude returns a JSON object with all recognised W-9 fields plus
two additional extraction-time fields (``signature_present`` and
``signature_date``).

Design decisions
----------------
- **Null-over-failure**: any field that is missing, blank, or illegible
  in the source document is returned as ``null`` in Claude's JSON
  response rather than causing an extraction failure.  This lets
  downstream validation distinguish "field was absent on the form" from
  "field was never asked for".
- **Strict JSON output**: the prompt instructs Claude to respond with
  *only* a JSON object and no surrounding prose.  A ``json.JSONDecodeError``
  is surfaced as ``TaxFormExtractionError`` so callers always deal with a
  single exception type for extraction failures.
- **Form-type assumption**: this extractor always sets ``form_type`` to
  ``"W-9"`` because it is purpose-built for that form.  A general-purpose
  extractor that also handles W-8BEN would need form-type detection logic.
- **PDF document blocks**: the Anthropic Messages API (model
  ``claude-3-5-sonnet-20241022`` and later) accepts PDF files directly via
  ``{"type": "document", "source": {"type": "base64", …}}``.  For older
  models, or when ``fallback_to_text=True`` is set, the extractor falls
  back to treating the bytes as UTF-8 text (useful for testing with
  text-encoded PDFs).
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

_EXTRACTION_PROMPT = """Extract every field from this W-9 (Request for Taxpayer Identification \
Number and Certification) form and return a single JSON object with EXACTLY these keys:

{
  "form_type": "W-9",
  "name": <string or null>,
  "business_name": <string or null>,
  "federal_tax_classification": <string or null>,
  "exempt_payee_code": <string or null>,
  "exemption_from_fatca_code": <string or null>,
  "address": <string or null>,
  "city_state_zip": <string or null>,
  "account_numbers": <string or null>,
  "tin": <string or null>,
  "tin_type": <"SSN" | "EIN" | null>,
  "signature_present": <true | false | null>,
  "signature_date": <"YYYY-MM-DD" | null>
}

Rules:
- "name" is Box 1 (the individual or entity name exactly as printed).
- "business_name" is Box 2 (disregarded entity name); null if blank.
- "federal_tax_classification" is the checked option in Box 3 \
(e.g. "Individual/sole proprietor", "C Corporation", "S Corporation", \
"Partnership", "Trust/estate", "LLC", "Other").
- "tin" is the raw number as printed (digits, hyphens); null if blank.
- "tin_type" is "SSN" if the SSN box is checked, "EIN" if the EIN box \
is checked, null if neither or illegible.
- "signature_present" is true if a handwritten or electronic signature \
is visible in the signature line; false if the signature line is blank; \
null if you cannot determine.
- "signature_date" is the date written next to the signature in \
ISO 8601 format (YYYY-MM-DD); null if absent or illegible.
- Return null for any field you cannot read or that does not appear on \
the form.
- Do NOT add extra keys.
- Respond with ONLY the JSON object."""


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------


class ClaudeW9Extractor(TaxFormExtractorPort):
    """Extract W-9 form fields from a PDF using the Claude API.

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

        The returned dictionary always contains ``"form_type": "W-9"`` and
        the keys listed in ``_EXTRACTION_PROMPT``.  Any field that Claude
        could not determine is ``None``.

        Args:
            file_bytes: Raw bytes of the W-9 PDF (or UTF-8 text when
                        ``fallback_to_text=True``).
            filename:   Ignored; present to satisfy the port contract.

        Returns:
            A ``dict`` with ``"form_type"`` and all W-9 field keys.

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
                f"Anthropic API error while extracting W-9 fields: {exc}"
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

        # Ensure form_type is always set to "W-9" regardless of what Claude
        # returned — this extractor is W-9-specific.
        data["form_type"] = "W-9"
        return data
