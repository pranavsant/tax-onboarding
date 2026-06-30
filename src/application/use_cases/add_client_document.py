"""Use case: record a submitted onboarding document for a client."""
from __future__ import annotations

from src.application.dto.client_dto import AddDocumentDTO, ClientDTO
from src.application.exceptions import ClientNotFoundError
from src.application.mappers.client_mapper import to_dto
from src.domain.repositories.client_repository import ClientRepository


class AddClientDocumentUseCase:
    def __init__(self, client_repository: ClientRepository) -> None:
        self._client_repository = client_repository

    def execute(self, dto: AddDocumentDTO) -> ClientDTO:
        client = self._client_repository.get_by_id(dto.client_id)
        if client is None:
            raise ClientNotFoundError(f"Client '{dto.client_id}' was not found")

        client.add_document(dto.document_name)
        updated = self._client_repository.update(client)
        return to_dto(updated)
