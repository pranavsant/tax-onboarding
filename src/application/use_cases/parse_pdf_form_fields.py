"""Use case: extract and normalize tax form fields from a PDF upload.

Accepts raw PDF bytes (or any bytes the extractor can handle), delegates
extraction to a pluggable ``TaxFormExtractorPort``, then normalizes the
result into a ``ParsedFormFieldsDTO`` via ``NormalizeFormFieldsUseCase``.

This makes the PDF path produce the same normalized intermediate
representation as the JSON input path, so all downstream validation
logic is form-source-agnostic.

Domain errors are translated into application errors so the interfaces
layer never needs to import domain types directly.
"""
from __future__ import annotations

from src.application.dto.tax_form_dto import ParsedFormFieldsDTO, W8BENFieldsDTO
from src.application.exceptions import TaxFormExtractionError
from src.application.ports.tax_form_extractor import TaxFormExtractorPort
from src.application.use_cases.normalize_form_fields import NormalizeFormFieldsUseCase


class ParsePdfFormFieldsUseCase:
    """Extract PDF form fields and normalize them into ``ParsedFormFieldsDTO``.

    The use case is intentionally thin: it stitches together the extractor
    port and the existing normalization use case so neither needs to know
    about the other.

    Args:
        extractor: A concrete implementation of ``TaxFormExtractorPort``.
            Injected at construction time by the composition root.
        normalizer: An instance of ``NormalizeFormFieldsUseCase``.  Defaults
            to a fresh instance (which has no infrastructure dependency).
    """

    def __init__(
        self,
        extractor: TaxFormExtractorPort,
        normalizer: NormalizeFormFieldsUseCase | None = None,
    ) -> None:
        self._extractor = extractor
        self._normalizer = normalizer or NormalizeFormFieldsUseCase()

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
            InvalidFormFieldsError: If the extracted fields fail domain-level
                validation (e.g. missing required fields).
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
        """Build a W8BENFieldsDTO from *raw* and normalize it."""
        dto = W8BENFieldsDTO(
            name=raw.get("name", ""),
            country_of_citizenship=raw.get("country_of_citizenship", ""),
            permanent_address=raw.get("permanent_address", ""),
            permanent_address_city_country=raw.get("permanent_address_city_country", ""),
            mailing_address=raw.get("mailing_address"),
            mailing_address_city_country=raw.get("mailing_address_city_country"),
            us_tin=raw.get("us_tin"),
            foreign_tin=raw.get("foreign_tin"),
            ftin_not_required=raw.get("ftin_not_required"),
            reference_numbers=raw.get("reference_numbers"),
            date_of_birth=raw.get("date_of_birth"),
            treaty_country=raw.get("treaty_country"),
            treaty_article=raw.get("treaty_article"),
            withholding_rate=raw.get("withholding_rate"),
            income_type=raw.get("income_type"),
            treaty_conditions=raw.get("treaty_conditions"),
        )
        return self._normalizer.execute_w8ben(dto)
