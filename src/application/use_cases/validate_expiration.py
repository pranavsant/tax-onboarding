"""Use case: validate whether a W-8BEN form has expired.

Accepts a ``ParsedFormFieldsDTO`` (the normalized intermediate representation
produced by both the JSON input path and the PDF extraction path) and
determines whether the form is still within its validity window.

IRS rule: a W-8BEN is valid from its signed date through the end of the
third calendar year after signing.  For example, a form signed on any date
in 2025 expires on 2028-12-31.

The expiration logic lives in the domain layer
(:class:`~src.domain.services.expiration_validator.ExpirationValidator`);
this use case is a thin translation shim that converts the domain result
into an application-layer DTO.

Applies to W-8BEN forms only (W-9 forms have no expiration requirement).
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from src.application.dto.tax_form_dto import ExpirationValidationResultDTO, ParsedFormFieldsDTO
from src.domain.services.expiration_validator import ExpirationValidator


class ValidateExpirationUseCase:
    """Validate the expiration status of a W-8BEN :class:`ParsedFormFieldsDTO`.

    This use case has no infrastructure dependency and can be instantiated
    directly — no dependency injection required.
    """

    def execute(
        self,
        dto: ParsedFormFieldsDTO,
        today: Optional[date] = None,
    ) -> ExpirationValidationResultDTO:
        """Check whether *dto* represents a W-8BEN that is still valid today.

        Args:
            dto: Normalized form fields.  ``dto.signature_date`` is used as
                the signed date; ``dto.form_type`` is not checked here so
                the caller is responsible for invoking this use case only on
                W-8BEN forms.
            today: Optional reference date used as "today".  Defaults to
                :func:`datetime.date.today` when ``None``.  Exposed for
                deterministic testing.

        Returns:
            :class:`~src.application.dto.tax_form_dto.ExpirationValidationResultDTO`
            with ``passed=True`` and ``reason=""`` when the form is still
            valid, or ``passed=False`` and a descriptive ``reason`` when it
            has expired or the signed date could not be parsed.
            ``valid_through`` carries the computed expiry date as a
            ``YYYY-MM-DD`` string when the signed date was parseable, or
            ``None`` otherwise.
        """
        domain_result = ExpirationValidator.validate(
            signed_date=dto.signature_date,
            today=today,
        )
        return ExpirationValidationResultDTO(
            passed=domain_result.passed,
            reason=domain_result.reason,
            valid_through=(
                domain_result.valid_through.isoformat()
                if domain_result.valid_through is not None
                else None
            ),
        )
