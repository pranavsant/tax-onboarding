"""Use case: fetch a single client by id."""
from __future__ import annotations

from src.application.dto.client_dto import ClientDTO
from src.application.exceptions import ClientNotFoundError
from src.application.mappers.client_mapper import to_dto
from src.domain.repositories.client_repository import ClientRepository


class GetClientUseCase:
    def __init__(self, client_repository: ClientRepository) -> None:
        self._client_repository = client_repository

    def execute(self, client_id: str) -> ClientDTO:
        client = self._client_repository.get_by_id(client_id)
        if client is None:
            raise ClientNotFoundError(f"Client '{client_id}' was not found")
        return to_dto(client)
