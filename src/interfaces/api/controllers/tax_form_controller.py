"""HTTP controller for tax form determination.

Thin layer: validate input -> call use case -> serialize output.
Business rules are never evaluated here.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from src.application.dto.tax_form_dto import DetermineFormDTO
from src.application.exceptions import UnrecognizedInvestorTypeError
from src.application.use_cases.determine_required_form import DetermineRequiredFormUseCase
from src.interfaces.api.schemas import DetermineFormRequest, DetermineFormResponse

router = APIRouter(prefix="/tax-forms", tags=["tax-forms"])

# This use case is instantiated directly (no infrastructure dependency).
_use_case = DetermineRequiredFormUseCase()


@router.post(
    "/required",
    response_model=DetermineFormResponse,
    status_code=status.HTTP_200_OK,
    summary="Determine the required tax form for an investor",
    description=(
        "Returns 'W-9' for US persons and 'W-8BEN' for foreign persons. "
        "Raises 422 if investor_type is missing or unrecognized."
    ),
)
def determine_required_form(payload: DetermineFormRequest) -> DetermineFormResponse:
    try:
        result = _use_case.execute(DetermineFormDTO(investor_type=payload.investor_type))
    except UnrecognizedInvestorTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return DetermineFormResponse(**result.__dict__)
