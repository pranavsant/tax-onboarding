"""Use case: determine the required tax form for an investor.

Accepts an investor type string and returns the appropriate form code
(W-9 for US persons, W-8BEN for foreign persons). Domain errors are
translated into application errors so the interfaces layer never
needs to import domain types directly.
"""
from __future__ import annotations

from src.application.dto.tax_form_dto import DetermineFormDTO, FormDeterminationResultDTO
from src.application.exceptions import UnrecognizedInvestorTypeError
from src.domain.exceptions import UnrecognizedInvestorTypeError as DomainUnrecognizedInvestorTypeError
from src.domain.services.tax_form_determination_service import TaxFormDeterminationService


class DetermineRequiredFormUseCase:
    """Maps an investor_type string to the required tax form code.

    This use case has no repository dependency; the determination is a
    pure domain rule encapsulated in :class:`TaxFormDeterminationService`.
    """

    def execute(self, dto: DetermineFormDTO) -> FormDeterminationResultDTO:
        try:
            form_code = TaxFormDeterminationService.determine_form(dto.investor_type)
        except DomainUnrecognizedInvestorTypeError as exc:
            raise UnrecognizedInvestorTypeError(str(exc)) from exc

        return FormDeterminationResultDTO(
            investor_type=dto.investor_type,
            required_form=form_code.value,
        )
