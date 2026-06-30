"""FastAPI dependency providers.

These extract use cases from the application container stored on
`app.state` (populated by the composition root). No infrastructure
types are referenced anywhere in this module.
"""
from __future__ import annotations

from fastapi import Request

from src.application.use_cases.add_client_document import AddClientDocumentUseCase
from src.application.use_cases.generate_tax_summary import GenerateTaxSummaryUseCase
from src.application.use_cases.get_client import GetClientUseCase
from src.application.use_cases.list_clients import ListClientsUseCase
from src.application.use_cases.onboard_client import OnboardClientUseCase
from src.interfaces.api.container import UseCaseContainer


def get_container(request: Request) -> UseCaseContainer:
    return request.app.state.container


def get_onboard_client_use_case(request: Request) -> OnboardClientUseCase:
    return get_container(request).onboard_client


def get_list_clients_use_case(request: Request) -> ListClientsUseCase:
    return get_container(request).list_clients


def get_get_client_use_case(request: Request) -> GetClientUseCase:
    return get_container(request).get_client


def get_add_document_use_case(request: Request) -> AddClientDocumentUseCase:
    return get_container(request).add_document


def get_generate_tax_summary_use_case(request: Request) -> GenerateTaxSummaryUseCase:
    return get_container(request).generate_tax_summary
