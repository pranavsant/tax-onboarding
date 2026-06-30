"""Domain service determining onboarding eligibility.

This logic concerns a TaxClient but is not a natural responsibility of
the entity itself (it depends on a shared business policy — the list
of required documents) so it lives in a domain service instead.
"""
from __future__ import annotations

from typing import List

from src.domain.entities.client import TaxClient

REQUIRED_DOCUMENTS: List[str] = ["government_id", "prior_year_return", "w2_or_1099"]


class OnboardingEligibilityService:
    """Stateless domain service encapsulating onboarding business rules."""

    @staticmethod
    def missing_documents(client: TaxClient) -> List[str]:
        return [doc for doc in REQUIRED_DOCUMENTS if doc not in client.submitted_documents]

    def is_eligible_for_review(self, client: TaxClient) -> bool:
        return len(self.missing_documents(client)) == 0
