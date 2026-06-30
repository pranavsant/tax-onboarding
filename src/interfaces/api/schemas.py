"""Pydantic schemas for HTTP request/response validation.

These are translated to/from application DTOs inside the controllers.
Only schema (shape/type) validation happens here — business rules are
enforced by the domain layer.
"""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, EmailStr, Field


class CreateClientRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=200)
    email: EmailStr
    tax_id: str = Field(..., description="SSN (XXX-XX-XXXX) or EIN (XX-XXXXXXX)")


class AddDocumentRequest(BaseModel):
    document_name: str = Field(..., min_length=1, max_length=100)


class TaxSummaryRequest(BaseModel):
    notes: str = ""


class ClientResponse(BaseModel):
    client_id: str
    full_name: str
    email: str
    tax_id_masked: str
    status: str
    submitted_documents: List[str]
    created_at: str


class TaxSummaryResponse(BaseModel):
    client_id: str
    summary: str


class ErrorResponse(BaseModel):
    detail: str


class DetermineFormRequest(BaseModel):
    investor_type: str = Field(
        ...,
        description="Investor residency type. Accepted values: 'us_person', 'foreign_person'.",
    )


class DetermineFormResponse(BaseModel):
    investor_type: str
    required_form: str = Field(
        ..., description="Required tax form code: 'W-9' (US) or 'W-8BEN' (foreign)."
    )
