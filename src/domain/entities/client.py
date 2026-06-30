"""TaxClient entity.

Represents a client moving through the tax onboarding workflow.
Entities own their invariants: invalid state can never be constructed,
and state transitions are exposed as explicit, intention-revealing
methods rather than free-form attribute mutation.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List

from src.domain.exceptions import InvalidClientDataError
from src.domain.value_objects.tax_id import TaxId


class OnboardingStatus(str, Enum):
    STARTED = "STARTED"
    DOCUMENTS_PENDING = "DOCUMENTS_PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    COMPLETED = "COMPLETED"


@dataclass
class TaxClient:
    """A client undergoing tax onboarding."""

    full_name: str
    email: str
    tax_id: TaxId
    client_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: OnboardingStatus = OnboardingStatus.STARTED
    submitted_documents: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not self.full_name or not self.full_name.strip():
            raise InvalidClientDataError("full_name must not be empty")
        if "@" not in self.email:
            raise InvalidClientDataError(f"'{self.email}' is not a valid email")

    def add_document(self, document_name: str) -> None:
        """Record a submitted document and advance status if applicable."""
        if document_name not in self.submitted_documents:
            self.submitted_documents.append(document_name)
        if self.status == OnboardingStatus.STARTED:
            self.status = OnboardingStatus.DOCUMENTS_PENDING

    def mark_under_review(self) -> None:
        self.status = OnboardingStatus.UNDER_REVIEW

    def mark_completed(self) -> None:
        self.status = OnboardingStatus.COMPLETED
