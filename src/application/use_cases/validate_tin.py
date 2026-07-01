"""Use case: validate the TIN field(s) of a parsed tax form.

Accepts a ``ParsedFormFieldsDTO`` (the normalized intermediate
representation produced by both the JSON input path and the PDF
extraction path) and checks that the appropriate taxpayer identification
number is present and correctly formatted.

  * **W-9** — ``tin`` is validated as a US SSN (``XXX-XX-XXXX``) or EIN
    (``XX-XXXXXXX``) using :class:`~src.domain.value_objects.tax_id.TaxId`.
  * **W-8BEN** — ``foreign_tin`` is validated as present and non-empty;
    no country-specific format is enforced given international variance.
    If ``ftin_not_required`` is ``True`` the foreign TIN check is skipped.

The validation logic lives in the domain layer
(:class:`~src.domain.services.tin_validator.TINValidator`);
this use case is a thin translation shim that converts the domain result
into an application-layer DTO.
"""
from __future__ import annotations

from src.application.dto.tax_form_dto import ParsedFormFieldsDTO, TINValidationResultDTO
from src.domain.services.tin_validator import TINValidator


class ValidateTINUseCase:
    """Validate the TIN field(s) of a :class:`ParsedFormFieldsDTO`.

    This use case has no infrastructure dependency and can be instantiated
    directly — no dependency injection required.
    """

    def execute(self, dto: ParsedFormFieldsDTO) -> TINValidationResultDTO:
        """Check that *dto* carries a correctly formatted TIN.

        Dispatches to the appropriate validation rule based on
        ``dto.form_type``:

        * ``"W-9"``    → validate ``tin`` as SSN or EIN
        * ``"W-8BEN"`` → validate ``foreign_tin`` as present/non-empty
          (skipped when ``ftin_not_required`` is ``True``)

        Args:
            dto: Normalized form fields for a W-9 or W-8BEN.

        Returns:
            :class:`~src.application.dto.tax_form_dto.TINValidationResultDTO`
            with ``passed=True`` and ``reason=""`` when validation succeeds,
            or ``passed=False`` and a descriptive ``reason`` when it fails.

        Raises:
            ValueError: If ``dto.form_type`` is neither ``"W-9"`` nor
                ``"W-8BEN"``.
        """
        if dto.form_type == "W-9":
            domain_result = TINValidator.validate_us_tin(dto.tin)
        elif dto.form_type == "W-8BEN":
            # When the beneficial owner has certified that a foreign TIN is
            # not legally required (ftin_not_required=True), skip the check.
            if dto.ftin_not_required is True:
                return TINValidationResultDTO(passed=True, reason="")
            domain_result = TINValidator.validate_foreign_tin(dto.foreign_tin)
        else:
            raise ValueError(
                f"Unsupported form_type '{dto.form_type}': expected 'W-9' or 'W-8BEN'."
            )

        return TINValidationResultDTO(
            passed=domain_result.passed,
            reason=domain_result.reason,
        )
