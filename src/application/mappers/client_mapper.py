"""Mapping between TaxClient domain entities and ClientDTOs.

Mappers keep use cases free of repetitive translation logic and
guarantee that domain entities never leak past the application layer.
"""
from __future__ import annotations

from src.application.dto.client_dto import ClientDTO
from src.domain.entities.client import TaxClient


def to_dto(client: TaxClient) -> ClientDTO:
    return ClientDTO(
        client_id=client.client_id,
        full_name=client.full_name,
        email=client.email,
        tax_id_masked=client.tax_id.masked(),
        status=client.status.value,
        submitted_documents=list(client.submitted_documents),
        created_at=client.created_at.isoformat(),
    )
