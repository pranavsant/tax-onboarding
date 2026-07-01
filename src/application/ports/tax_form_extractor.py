"""Port (abstraction) for extracting structured form fields from a PDF file.

This interface is owned by the application layer. Concrete
implementations (e.g., an OCR-backed extractor, a stub for testing)
live in the infrastructure layer and are injected via the use case
constructor, keeping the application layer free of any PDF or I/O
dependency.

Expected return shape
---------------------
The ``extract`` method returns a plain ``dict`` with the following
guaranteed key:

    ``form_type`` (str): ``"W-9"`` or ``"W-8BEN"``.

All other keys mirror the fields defined in ``W9FieldsDTO`` or
``W8BENFieldsDTO`` (see ``src/application/dto/tax_form_dto.py``).
Unknown keys are silently ignored by the use case; missing optional
fields default to ``None``.

Raises
------
``TaxFormExtractionError`` (application exception) if the file cannot
be parsed or the extractor cannot determine the form type.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class TaxFormExtractorPort(ABC):
    """Extract structured key-value fields from a PDF tax form."""

    @abstractmethod
    def extract(self, file_bytes: bytes, filename: str) -> dict:
        """Parse ``file_bytes`` and return a field-value mapping.

        Args:
            file_bytes: Raw bytes of the uploaded PDF (or test fixture).
            filename:   Original filename supplied by the caller; may be
                        used as a hint to identify the form type.

        Returns:
            A ``dict`` containing at minimum a ``"form_type"`` key whose
            value is ``"W-9"`` or ``"W-8BEN"``, plus zero or more field
            keys from the corresponding form field DTO.

        Raises:
            TaxFormExtractionError: If extraction fails for any reason
                (corrupt file, unrecognised form, etc.).
        """
