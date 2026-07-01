"""Use case: validate Part II (treaty claim) of a parsed W-8BEN form.

Accepts a ``ParsedFormFieldsDTO`` (the normalized intermediate
representation produced by both the JSON input path and the PDF
extraction path) and checks whether the Part II treaty-claim section is
consistent with the investor's country of citizenship.

Three outcomes are possible:

* **Non-treaty country + blank Part II** → ``passed=True``, no action required.
* **Treaty country + blank Part II** → ``passed=False``, flagged for review.
* **Treaty country + completed Part II** → ``passed=True``,
  ``applied_withholding_rate_pct`` carries the reduced rate from the
  treaty reference table.

The validation logic lives in the domain layer
(:class:`~src.domain.services.treaty_claim_validator.TreatyClaimValidator`);
this use case is a thin translation shim that converts the domain result
into an application-layer DTO.

Applies to **W-8BEN** forms only.  Passing a W-9 ``ParsedFormFieldsDTO``
raises :exc:`ValueError`.
"""
from __future__ import annotations

from src.application.dto.tax_form_dto import (
    ParsedFormFieldsDTO,
    TreatyClaimValidationResultDTO,
)
from src.domain.services.treaty_claim_validator import TreatyClaimValidator


class ValidateTreatyClaimUseCase:
    """Validate the Part II treaty claim of a :class:`ParsedFormFieldsDTO`.

    This use case has no infrastructure dependency and can be instantiated
    directly — no dependency injection required.
    """

    def execute(self, dto: ParsedFormFieldsDTO) -> TreatyClaimValidationResultDTO:
        """Check that the Part II treaty claim in *dto* is consistent with the
        investor's country of citizenship.

        Args:
            dto: Normalized form fields for a W-8BEN form.

        Returns:
            :class:`~src.application.dto.tax_form_dto.TreatyClaimValidationResultDTO`
            with ``passed=True`` and ``reason=""`` when validation succeeds,
            or ``passed=False`` and a descriptive ``reason`` when the claim
            should be flagged for review.  ``applied_withholding_rate_pct`` is
            set to the treaty reduced rate when a valid claim is present.

        Raises:
            ValueError: If ``dto.form_type`` is not ``"W-8BEN"``.
            ValueError: If ``dto.country_of_citizenship`` is ``None``, empty,
                or whitespace-only.
        """
        if dto.form_type != "W-8BEN":
            raise ValueError(
                f"ValidateTreatyClaimUseCase only applies to W-8BEN forms, "
                f"got form_type='{dto.form_type}'."
            )

        domain_result = TreatyClaimValidator.validate(
            country_of_citizenship=dto.country_of_citizenship or "",
            treaty_country=dto.treaty_country,
            treaty_article=dto.treaty_article,
            withholding_rate=dto.withholding_rate,
            income_type=dto.income_type,
            treaty_conditions=dto.treaty_conditions,
        )
        return TreatyClaimValidationResultDTO(
            passed=domain_result.passed,
            reason=domain_result.reason,
            applied_withholding_rate_pct=domain_result.applied_withholding_rate_pct,
        )
