"""HTTP controller for AI-assisted (Claude-powered) tax onboarding
summaries. Thin layer only: validate input -> call use case -> respond.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.application.dto.client_dto import TaxSummaryRequestDTO
from src.application.exceptions import AIAssistantError, ClientNotFoundError
from src.application.use_cases.generate_tax_summary import GenerateTaxSummaryUseCase
from src.interfaces.api.dependencies import get_generate_tax_summary_use_case
from src.interfaces.api.schemas import TaxSummaryRequest, TaxSummaryResponse

router = APIRouter(prefix="/clients", tags=["tax-assistant"])


@router.post("/{client_id}/tax-summary", response_model=TaxSummaryResponse)
def generate_tax_summary(
    client_id: str,
    payload: TaxSummaryRequest,
    use_case: GenerateTaxSummaryUseCase = Depends(get_generate_tax_summary_use_case),
) -> TaxSummaryResponse:
    try:
        result = use_case.execute(
            TaxSummaryRequestDTO(client_id=client_id, notes=payload.notes)
        )
    except ClientNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AIAssistantError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return TaxSummaryResponse(**result.__dict__)
