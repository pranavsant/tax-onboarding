"""Use case: extract and normalize tax form fields from a PDF upload.

Accepts raw PDF bytes (or any bytes the extractor can handle), delegates
extraction to a pluggable ``TaxFormExtractorPort``, then normalizes the
result into a ``ParsedFormFieldsDTO`` via ``NormalizeFormFieldsUseCase``.

This makes the PDF path produce the same normalized intermediate
representation as the JSON input path, so all downstream validation
logic is form-source-agnostic.

Both W-9 and W-8BEN paths build ``ParsedFormFieldsDTO`` directly from
the extractor's raw dict without running domain validation — PDF/OCR
extraction may legitimately produce null values for required fields.
Domain validation is reserved for the structured JSON input path.
"""
from __future__ import annotations

from src.application.dto.tax_form_dto import ParsedFormFieldsDTO
from src.application.exceptions import TaxFormExtractionError
from src.application.ports.tax_form_extractor import TaxFormExtractorPort


class ParsePdfFormFieldsUseCase:
    """Extract PDF form fields and normalize them into ``ParsedFormFieldsDTO``.

    The use case is intentionally thin: it stitches together the extractor
    port and the existing normalization use case so neither needs to know
    about the other.

    Args:
        extractor: A concrete implementation of ``TaxFormExtractorPort``.
            Injected at construction time by the composition root.
    """

    def __init__(
        self,
        extractor: TaxFormExtractorPort,
    ) -> None:
        self._extractor = extractor

    def execute(self, file_bytes: bytes, filename: str) -> ParsedFormFieldsDTO:
        """Extract fields from ``file_bytes`` and return normalized form data.

        Args:
            file_bytes: Raw bytes of the uploaded file.
            filename:   Original filename (used by some extractors as a hint).

        Returns:
            A ``ParsedFormFieldsDTO`` with ``form_type`` set to ``'W-9'`` or
            ``'W-8BEN'`` and all applicable fields populated.

        Raises:
            TaxFormExtractionError: If the extractor cannot parse the file or
                cannot determine the form type.
        """
        raw: dict = self._extractor.extract(file_bytes, filename)

        form_type: str = raw.get("form_type", "")
        if not form_type:
            raise TaxFormExtractionError(
                "Extractor did not return a 'form_type' field. "
                "Cannot determine whether this is a W-9 or W-8BEN."
            )

        if form_type == "W-9":
            return self._normalize_w9(raw)
        elif form_type == "W-8BEN":
            return self._normalize_w8ben(raw)
        else:
            raise TaxFormExtractionError(
                f"Unrecognised form_type '{form_type}'. "
                "Expected 'W-9' or 'W-8BEN'."
            )

    # ---------------------------------------------------------------- helpers

    def _normalize_w9(self, raw: dict) -> ParsedFormFieldsDTO:
        """Build a ``ParsedFormFieldsDTO`` from *raw* W-9 extractor output.

        PDF extractors (including AI-based ones) may legitimately return
        ``None`` for fields that are missing or illegible — the task spec
        explicitly requires that such fields be flagged ``null`` rather than
        causing a failure.  Therefore this method builds ``ParsedFormFieldsDTO``
        directly from the raw dict **without** running domain validation.

        Domain validation (which enforces that required fields are non-null) is
        reserved for the *structured JSON input path* where a human or upstream
        system is expected to supply complete data.
        """
        # tin_type normalization: upper-case when present, pass None through.
        raw_tin_type: str | None = raw.get("tin_type")
        tin_type = raw_tin_type.strip().upper() if raw_tin_type else None

        return ParsedFormFieldsDTO(
            form_type="W-9",
            name=raw.get("name") or None,
            federal_tax_classification=raw.get("federal_tax_classification") or None,
            address=raw.get("address") or None,
            city_state_zip=raw.get("city_state_zip") or None,
            tin=raw.get("tin") or None,
            tin_type=tin_type,
            business_name=raw.get("business_name") or None,
            exempt_payee_code=raw.get("exempt_payee_code") or None,
            exemption_from_fatca_code=raw.get("exemption_from_fatca_code") or None,
            account_numbers=raw.get("account_numbers") or None,
            signature_present=raw.get("signature_present"),
            signature_date=raw.get("signature_date") or None,
        )

    def _normalize_w8ben(self, raw: dict) -> ParsedFormFieldsDTO:
        """Build a ``ParsedFormFieldsDTO`` from *raw* W-8BEN extractor output.

        PDF extractors (including AI-based ones) may legitimately return
        ``None`` for fields that are missing or illegible — the task spec
        explicitly requires that such fields be flagged ``null`` rather than
        causing a failure.  Therefore this method builds ``ParsedFormFieldsDTO``
        directly from the raw dict **without** running domain validation.

        Domain validation (which enforces that required fields are non-null) is
        reserved for the *structured JSON input path* where a human or upstream
        system is expected to supply complete data.
        """
        return ParsedFormFieldsDTO(
            form_type="W-8BEN",
            name=raw.get("name") or None,
            country_of_citizenship=raw.get("country_of_citizenship") or None,
            permanent_address=raw.get("permanent_address") or None,
            permanent_address_city_country=raw.get("permanent_address_city_country") or None,
            mailing_address=raw.get("mailing_address") or None,
            mailing_address_city_country=raw.get("mailing_address_city_country") or None,
            us_tin=raw.get("us_tin") or None,
            foreign_tin=raw.get("foreign_tin") or None,
            ftin_not_required=raw.get("ftin_not_required"),
            reference_numbers=raw.get("reference_numbers") or None,
            date_of_birth=raw.get("date_of_birth") or None,
            treaty_country=raw.get("treaty_country") or None,
            treaty_article=raw.get("treaty_article") or None,
            withholding_rate=raw.get("withholding_rate") or None,
            income_type=raw.get("income_type") or None,
            treaty_conditions=raw.get("treaty_conditions") or None,
            signature_present=raw.get("signature_present"),
            signature_date=raw.get("signature_date") or None,
        )
