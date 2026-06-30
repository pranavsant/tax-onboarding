from typing import Dict, List, Optional

import pytest

from src.application.dto.client_dto import CreateClientDTO
from src.application.exceptions import InvalidClientRequestError
from src.application.use_cases.onboard_client import OnboardClientUseCase
from src.domain.entities.client import TaxClient
from src.domain.repositories.client_repository import ClientRepository


class InMemoryClientRepository(ClientRepository):
    """Test double satisfying the ClientRepository port."""

    def __init__(self) -> None:
        self._clients: Dict[str, TaxClient] = {}

    def save(self, client: TaxClient) -> TaxClient:
        self._clients[client.client_id] = client
        return client

    def get_by_id(self, client_id: str) -> Optional[TaxClient]:
        return self._clients.get(client_id)

    def list_all(self) -> List[TaxClient]:
        return list(self._clients.values())

    def update(self, client: TaxClient) -> TaxClient:
        self._clients[client.client_id] = client
        return client


def test_onboard_client_creates_and_persists_client() -> None:
    repository = InMemoryClientRepository()
    use_case = OnboardClientUseCase(repository)

    result = use_case.execute(
        CreateClientDTO(full_name="Jane Doe", email="jane@example.com", tax_id="123-45-6789")
    )

    assert result.full_name == "Jane Doe"
    assert result.status == "STARTED"
    assert repository.get_by_id(result.client_id) is not None


def test_onboard_client_rejects_invalid_tax_id() -> None:
    repository = InMemoryClientRepository()
    use_case = OnboardClientUseCase(repository)

    with pytest.raises(InvalidClientRequestError):
        use_case.execute(
            CreateClientDTO(full_name="Jane Doe", email="jane@example.com", tax_id="invalid")
        )
