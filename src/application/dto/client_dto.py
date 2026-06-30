"""Data Transfer Objects for client-related use cases.

DTOs are the only objects that cross the application/interfaces
boundary — domain entities never leak outward.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class CreateClientDTO:
    full_name: str
    email: str
    tax_id: str


@dataclass
class ClientDTO:
    client_id: str
    full_name: str
    email: str
    tax_id_masked: str
    status: str
    submitted_documents: List[str]
    created_at: str


@dataclass
class AddDocumentDTO:
    client_id: str
    document_name: str


@dataclass
class TaxSummaryRequestDTO:
    client_id: str
    notes: str = ""


@dataclass
class TaxSummaryResponseDTO:
    client_id: str
    summary: str
