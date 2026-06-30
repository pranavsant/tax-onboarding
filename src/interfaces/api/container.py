"""Composition container for the API.

Holds concrete use case instances injected at application startup by
the composition root (see root-level `main.py`). The interfaces layer
only ever depends on these through their application-layer types, so
it never needs to import infrastructure directly.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.application.use_cases.add_client_document import AddClientDocumentUseCase
from src.application.use_cases.generate_tax_summary import GenerateTaxSummaryUseCase
from src.application.use_cases.get_client import GetClientUseCase
from src.application.use_cases.list_clients import ListClientsUseCase
from src.application.use_cases.onboard_client import OnboardClientUseCase


@dataclass(frozen=True)
class UseCaseContainer:
    onboard_client: OnboardClientUseCase
    list_clients: ListClientsUseCase
    get_client: GetClientUseCase
    add_document: AddClientDocumentUseCase
    generate_tax_summary: GenerateTaxSummaryUseCase
