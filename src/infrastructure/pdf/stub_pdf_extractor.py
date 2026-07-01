"""Stub PDF extractor for development and testing.

Because integrating a real OCR / PDF-parsing library is out of scope
for the normalization task, this implementation treats the uploaded
bytes as UTF-8-encoded JSON containing the form fields directly.
This lets the full PDF path be exercised end-to-end in tests and
development without any external library dependency.

Production note
---------------
Replace this with a concrete implementation backed by a real PDF
parsing library (e.g. ``pdfplumber``, ``pypdf``, or an LLM-based
extractor) before using the ``/api/tax-forms/parse-pdf`` endpoint
in a real workflow.  The ``TaxFormExtractorPort`` contract guarantees
a clean swap — no application or domain code needs to change.
"""
from __future__ import annotations

import json

from src.application.exceptions import TaxFormExtractionError
from src.application.ports.tax_form_extractor import TaxFormExtractorPort


class StubPdfExtractor(TaxFormExtractorPort):
    """Extractor that reads form fields from JSON-encoded bytes.

    Accepts bytes that are valid UTF-8 JSON objects with a ``form_type``
    key (``"W-9"`` or ``"W-8BEN"``) plus the appropriate form fields.
    Useful for integration tests and local development.

    Example payload (as bytes)::

        {
            "form_type": "W-9",
            "name": "Jane A. Doe",
            "federal_tax_classification": "Individual/sole proprietor",
            "address": "123 Main Street",
            "city_state_zip": "Springfield, IL 62701",
            "tin": "123-45-6789",
            "tin_type": "SSN"
        }
    """

    def extract(self, file_bytes: bytes, filename: str) -> dict:  # noqa: ARG002
        """Decode *file_bytes* as JSON and return the resulting ``dict``.

        Args:
            file_bytes: UTF-8-encoded JSON bytes representing form fields.
            filename:   Ignored by this stub implementation.

        Returns:
            A ``dict`` containing at minimum ``"form_type"`` and the
            relevant form field keys.

        Raises:
            TaxFormExtractionError: If *file_bytes* cannot be decoded as
                valid UTF-8 or parsed as JSON.
        """
        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise TaxFormExtractionError(
                f"Could not decode uploaded file as UTF-8: {exc}"
            ) from exc

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise TaxFormExtractionError(
                f"Uploaded file is not valid JSON: {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise TaxFormExtractionError(
                "Expected a JSON object at the top level, "
                f"got {type(data).__name__}."
            )

        return data
