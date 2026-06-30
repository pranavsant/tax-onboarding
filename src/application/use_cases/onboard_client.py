"""Use case: onboard a new tax client.

Each use case is a single class with an `execute(dto)` method. It
receives its dependencies (repository/port interfaces) via the
constructor, and returns DTOs — never domain entities.
"""
from __future__ import annotations

from src.application.dto.client_dto import ClientDTO, CreateClientDTO
from src.application.exceptions import InvalidClientRequestError
from src.application.mappers.client_mapper import to_dto
from src.domain.entities.client import TaxClient
from src.domain.exceptions import DomainError
from src.domain.repositories.client_repository import ClientRepository
from src.domain.value_objects.tax_id import TaxId


class OnboardClientUseCase:
    """Creates and persists a new TaxClient."""

    def __init__(self, client_repository: ClientRepository) -> None:
        self._client_repository = client_repository

    def execute(self, dto: CreateClientDTO) -> ClientDTO:
        try:
            tax_id = TaxId.create(dto.tax_id)
            client = TaxClient(full_name=dto.full_name, email=dto.email, tax_id=tax_id)
        except DomainError as exc:
            # Translate domain errors into application errors so that
            # the interfaces layer never needs to know about domain types.
            raise InvalidClientRequestError(str(exc)) from exc

        saved = self._client_repository.save(client)
        return to_dto(saved)
