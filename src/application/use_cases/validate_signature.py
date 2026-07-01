"""Use case: validate the signature block of a parsed tax form.

Accepts a ``ParsedFormFieldsDTO`` (the normalized intermediate
representation produced by both the JSON input path and the PDF
extraction path) and checks that a visible signature and a valid signed
date are present.

The validation logic lives in the domain layer
(:class:`~src.domain.services.signature_validator.SignatureValidator`);
this use case is a thin translation shim that converts the domain result
into an application-layer DTO.

Applies to both W-9 and W-8BEN forms.
"""
from __future__ import annotations

from src.application.dto.tax_form_dto import ParsedFormFieldsDTO, SignatureValidationResultDTO
from src.domain.services.signature_validator import SignatureValidator


class ValidateSignatureUseCase:
    """Validate the signature block of a :class:`ParsedFormFieldsDTO`.

    This use case has no infrastructure dependency and can be instantiated
    directly — no dependency injection required.
    """

    def execute(self, dto: ParsedFormFieldsDTO) -> SignatureValidationResultDTO:
        """Check that *dto* carries a valid signature and signed date.

        Args:
            dto: Normalized form fields for a W-9 or W-8BEN.

        Returns:
            :class:`~src.application.dto.tax_form_dto.SignatureValidationResultDTO`
            with ``passed=True`` and ``reason=""`` when validation succeeds,
            or ``passed=False`` and a descriptive ``reason`` when it fails.
        """
        domain_result = SignatureValidator.validate(
            signature_present=dto.signature_present,
            signature_date=dto.signature_date,
        )
        return SignatureValidationResultDTO(
            passed=domain_result.passed,
            reason=domain_result.reason,
        )
