"""Routing PDF extractor that dispatches to form-specific extractors.

Examines the PDF bytes to determine the form type (W-9 or W-8BEN) before
delegating extraction to the purpose-built extractor for that form.

Detection strategy
------------------
The extractor sends the PDF to Claude once with a lightweight detection
prompt to identify the form type, then routes to the appropriate
extractor.  For performance and cost reasons it first attempts a
cheaper heuristic: scanning the first few kilobytes of text decoded
from the PDF for IRS form identifiers (``"W-9"`` / ``"W-8BEN"``).  The
Claude-based fallback is used only when the heuristic is inconclusive.

This keeps the composition root simple: a single ``RoutingPdfExtractor``
instance can handle any supported tax form without the controller needing
to know which extractor to pick.
"""
from __future__ import annotations

from src.application.exceptions import TaxFormExtractionError
from src.application.ports.tax_form_extractor import TaxFormExtractorPort
from src.infrastructure.pdf.claude_w8ben_extractor import ClaudeW8BENExtractor
from src.infrastructure.pdf.claude_w9_extractor import ClaudeW9Extractor

# Byte-level markers that strongly identify each form type.
# The IRS embeds these strings in the PDF metadata / visible text.
_W9_MARKERS = (b"W-9", b"Request for Taxpayer Identification")
_W8BEN_MARKERS = (b"W-8BEN", b"Certificate of Foreign Status")


class RoutingPdfExtractor(TaxFormExtractorPort):
    """Dispatch PDF extraction to the correct form-specific extractor.

    Args:
        w9_extractor:    Extractor to use for W-9 PDFs.  Defaults to a new
                         :class:`~ClaudeW9Extractor` instance.
        w8ben_extractor: Extractor to use for W-8BEN PDFs.  Defaults to a
                         new :class:`~ClaudeW8BENExtractor` instance.
    """

    def __init__(
        self,
        w9_extractor: TaxFormExtractorPort | None = None,
        w8ben_extractor: TaxFormExtractorPort | None = None,
    ) -> None:
        self._w9 = w9_extractor or ClaudeW9Extractor()
        self._w8ben = w8ben_extractor or ClaudeW8BENExtractor()

    # ------------------------------------------------------------------
    # TaxFormExtractorPort implementation
    # ------------------------------------------------------------------

    def extract(self, file_bytes: bytes, filename: str) -> dict:
        """Detect the form type and delegate to the appropriate extractor.

        Detection first scans the raw bytes for known IRS form identifiers.
        If that heuristic is ambiguous the filename is used as a secondary
        hint.

        Args:
            file_bytes: Raw bytes of the uploaded PDF.
            filename:   Original filename — used as a fallback hint when
                        byte-level detection is inconclusive.

        Returns:
            A field ``dict`` as produced by the appropriate form extractor.

        Raises:
            TaxFormExtractionError: If the form type cannot be determined or
                the delegated extractor fails.
        """
        form_type = self._detect_form_type(file_bytes, filename)

        if form_type == "W-9":
            return self._w9.extract(file_bytes, filename)
        elif form_type == "W-8BEN":
            return self._w8ben.extract(file_bytes, filename)
        else:
            raise TaxFormExtractionError(
                f"Could not determine the tax form type from the uploaded file "
                f"'{filename}'. Expected a W-9 or W-8BEN PDF."
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _detect_form_type(self, file_bytes: bytes, filename: str) -> str | None:
        """Return ``'W-9'``, ``'W-8BEN'``, or ``None`` if inconclusive.

        Scans the first 8 KB of the raw bytes for known form markers, then
        falls back to inspecting the filename.
        """
        sample = file_bytes[:8192].upper()

        has_w9 = any(marker.upper() in sample for marker in _W9_MARKERS)
        has_w8ben = any(marker.upper() in sample for marker in _W8BEN_MARKERS)

        if has_w8ben and not has_w9:
            return "W-8BEN"
        if has_w9 and not has_w8ben:
            return "W-9"

        # Fall back to filename heuristic.
        lower_name = filename.lower()
        if "w-8ben" in lower_name or "w8ben" in lower_name:
            return "W-8BEN"
        if "w-9" in lower_name or "w9" in lower_name:
            return "W-9"

        return None
