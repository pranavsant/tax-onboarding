"""Use case: generate an AI-assisted tax onboarding summary.

Orchestrates the ClientRepository (domain port) and the
AITaxAssistantPort (application port, implemented in infrastructure by
the Claude/Anthropic client) to produce a plain-language summary
grounded in the client's actual onboarding state.
"""
from __future__ import annotations

from typing import Optional

from src.application.dto.client_dto import TaxSummaryRequestDTO, TaxSummaryResponseDTO
from src.application.exceptions import AIAssistantError, ClientNotFoundError
from src.application.ports.ai_tax_assistant import AITaxAssistantPort
from src.domain.repositories.client_repository import ClientRepository
from src.domain.services.onboarding_eligibility_service import OnboardingEligibilityService


class GenerateTaxSummaryUseCase:
    def __init__(
        self,
        client_repository: ClientRepository,
        ai_assistant: AITaxAssistantPort,
        eligibility_service: Optional[OnboardingEligibilityService] = None,
    ) -> None:
        self._client_repository = client_repository
        self._ai_assistant = ai_assistant
        self._eligibility_service = eligibility_service or OnboardingEligibilityService()

    def execute(self, dto: TaxSummaryRequestDTO) -> TaxSummaryResponseDTO:
        client = self._client_repository.get_by_id(dto.client_id)
        if client is None:
            raise ClientNotFoundError(f"Client '{dto.client_id}' was not found")

        missing = self._eligibility_service.missing_documents(client)
        context = (
            f"Client name: {client.full_name}\n"
            f"Onboarding status: {client.status.value}\n"
            f"Documents submitted: {', '.join(client.submitted_documents) or 'none'}\n"
            f"Documents still missing: {', '.join(missing) or 'none'}\n"
            f"Additional notes: {dto.notes or 'none'}\n"
        )

        try:
            summary = self._ai_assistant.generate_summary(context)
        except Exception as exc:  # noqa: BLE001 - re-raised as application error
            raise AIAssistantError(f"Failed to generate tax summary: {exc}") from exc

        return TaxSummaryResponseDTO(client_id=client.client_id, summary=summary)
