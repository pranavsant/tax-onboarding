"""Composition root for the Tax Onboarding API.

This is the only file in the project allowed to wire concrete
infrastructure implementations into interface-layer entry points.
It deliberately sits outside `src/domain`, `src/application`,
`src/infrastructure`, and `src/interfaces` so that none of those
layers ever need to depend on each other directly, in line with the
absolute dependency rule:

    interfaces -> application -> domain
    infrastructure -> application -> domain

Run with:
    uvicorn main:app --reload
"""
from __future__ import annotations

from src.application.use_cases.add_client_document import AddClientDocumentUseCase
from src.application.use_cases.generate_tax_summary import GenerateTaxSummaryUseCase
from src.application.use_cases.get_client import GetClientUseCase
from src.application.use_cases.list_clients import ListClientsUseCase
from src.application.use_cases.onboard_client import OnboardClientUseCase
from src.application.use_cases.parse_pdf_form_fields import ParsePdfFormFieldsUseCase
from src.infrastructure.config import get_settings
from src.infrastructure.db.database import init_db
from src.infrastructure.db.sqlite_client_repository import SqliteClientRepository
from src.infrastructure.llm.claude_tax_assistant import ClaudeTaxAssistant
from src.infrastructure.pdf.routing_pdf_extractor import RoutingPdfExtractor
from src.interfaces.api.app import create_app
from src.interfaces.api.container import UseCaseContainer

settings = get_settings()
init_db()

client_repository = SqliteClientRepository()
ai_assistant = ClaudeTaxAssistant()
pdf_extractor = RoutingPdfExtractor()

container = UseCaseContainer(
    onboard_client=OnboardClientUseCase(client_repository),
    list_clients=ListClientsUseCase(client_repository),
    get_client=GetClientUseCase(client_repository),
    add_document=AddClientDocumentUseCase(client_repository),
    generate_tax_summary=GenerateTaxSummaryUseCase(client_repository, ai_assistant),
    parse_pdf_form_fields=ParsePdfFormFieldsUseCase(pdf_extractor),
)

app = create_app(container, cors_origins=settings.cors_origins)
