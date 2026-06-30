"""Use case: list all onboarded clients."""
from __future__ import annotations

from typing import List

from src.application.dto.client_dto import ClientDTO
from src.application.mappers.client_mapper import to_dto
from src.domain.repositories.client_repository import ClientRepository


class ListClientsUseCase:
    def __init__(self, client_repository: ClientRepository) -> None:
        self._client_repository = client_repository

    def execute(self) -> List[ClientDTO]:
        return [to_dto(client) for client in self._client_repository.list_all()]
