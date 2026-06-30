"""Repository interface for TaxClient persistence.

This is an abstraction (port) — it describes WHAT operations are
needed, never HOW they are implemented. Concrete implementations live
in the infrastructure layer (e.g. SqliteClientRepository).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from src.domain.entities.client import TaxClient


class ClientRepository(ABC):
    """Abstraction over persistence of TaxClient entities."""

    @abstractmethod
    def save(self, client: TaxClient) -> TaxClient:
        """Persist a new client and return the stored entity."""

    @abstractmethod
    def get_by_id(self, client_id: str) -> Optional[TaxClient]:
        """Fetch a client by id, or None if not found."""

    @abstractmethod
    def list_all(self) -> List[TaxClient]:
        """Return all clients."""

    @abstractmethod
    def update(self, client: TaxClient) -> TaxClient:
        """Persist changes to an existing client."""
