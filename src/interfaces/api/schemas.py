"""Pydantic schemas for HTTP request/response validation.

These are translated to/from application DTOs inside the controllers.
Only schema (shape/type) validation happens here — business rules are
enforced by the domain layer.
"""
from __future__ import annotations

from typing import List, Optional

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


# ---------------------------------------------------------------------------
# JSON input path — raw form field request schemas
# ---------------------------------------------------------------------------


class W9FieldsRequest(BaseModel):
    """JSON body for submitting extracted W-9 form fields.

    Required fields mirror IRS W-9 mandatory boxes.  Optional fields
    correspond to boxes that are conditionally required or informational.

    This schema is the JSON counterpart of what a PDF extractor would
    produce from a scanned W-9.
    """

    # Required fields
    name: str = Field(..., min_length=1, description="Box 1 — name as shown on income tax return.")
    federal_tax_classification: str = Field(
        ..., min_length=1, description="Box 3 — federal tax classification."
    )
    address: str = Field(..., min_length=1, description="Box 5 — street address.")
    city_state_zip: str = Field(..., min_length=1, description="Box 6 — city, state, ZIP code.")
    tin: str = Field(
        ...,
        min_length=1,
        description="Part I — taxpayer identification number (SSN or EIN).",
    )
    tin_type: str = Field(
        ...,
        description="Type of TIN supplied. Accepted values: 'SSN', 'EIN'.",
    )

    # Optional fields
    business_name: Optional[str] = Field(
        None, description="Box 2 — business name / disregarded entity name (if different)."
    )
    exempt_payee_code: Optional[str] = Field(None, description="Box 4 — exempt payee code.")
    exemption_from_fatca_code: Optional[str] = Field(
        None, description="Box 4 — exemption from FATCA reporting code."
    )
    account_numbers: Optional[str] = Field(
        None, description="Box 7 — list account number(s) here."
    )


class W8BENFieldsRequest(BaseModel):
    """JSON body for submitting extracted W-8BEN form fields.

    Required fields mirror IRS W-8BEN mandatory lines.  Optional fields
    correspond to Part II (treaty benefits) and other conditional lines.

    This schema is the JSON counterpart of what a PDF extractor would
    produce from a scanned W-8BEN.
    """

    # Required fields — Part I
    name: str = Field(
        ..., min_length=1, description="Line 1 — name of individual (beneficial owner)."
    )
    country_of_citizenship: str = Field(
        ..., min_length=1, description="Line 2 — country of citizenship."
    )
    permanent_address: str = Field(
        ..., min_length=1, description="Line 3 — permanent residence street address."
    )
    permanent_address_city_country: str = Field(
        ...,
        min_length=1,
        description="Line 3 — city / state / country for permanent address.",
    )

    # Identification — at least one must be supplied (enforced by domain)
    us_tin: Optional[str] = Field(None, description="Line 5 — US taxpayer identification number.")
    foreign_tin: Optional[str] = Field(
        None, description="Line 6a — foreign tax identifying number."
    )
    ftin_not_required: Optional[bool] = Field(
        None, description="Line 6b — check if FTIN not legally required."
    )

    # Optional fields
    mailing_address: Optional[str] = Field(
        None, description="Line 4 — mailing address street (if different from permanent)."
    )
    mailing_address_city_country: Optional[str] = Field(
        None, description="Line 4 — mailing address city / country."
    )
    reference_numbers: Optional[str] = Field(None, description="Line 7 — reference number(s).")
    date_of_birth: Optional[str] = Field(
        None, description="Line 8 — date of birth (YYYY-MM-DD)."
    )

    # Part II — tax treaty benefits (all optional)
    treaty_country: Optional[str] = Field(
        None, description="Line 9 — country whose treaty you are claiming."
    )
    treaty_article: Optional[str] = Field(
        None, description="Line 10 — treaty article number."
    )
    withholding_rate: Optional[str] = Field(
        None, description="Line 10 — withholding rate percentage."
    )
    income_type: Optional[str] = Field(None, description="Line 10 — type of income.")
    treaty_conditions: Optional[str] = Field(
        None, description="Line 10 — additional conditions in the treaty article."
    )


# ---------------------------------------------------------------------------
# Normalized intermediate representation response schema
# ---------------------------------------------------------------------------


class ParsedFormFieldsResponse(BaseModel):
    """Normalized intermediate representation returned by the JSON input path.

    Identical in shape to what the PDF extraction path will also return,
    allowing downstream validation logic to be form-source-agnostic.
    """

    form_type: str = Field(..., description="'W-9' or 'W-8BEN'.")

    # W-9 fields
    name: Optional[str] = None
    federal_tax_classification: Optional[str] = None
    address: Optional[str] = None
    city_state_zip: Optional[str] = None
    tin: Optional[str] = None
    tin_type: Optional[str] = None
    business_name: Optional[str] = None
    exempt_payee_code: Optional[str] = None
    exemption_from_fatca_code: Optional[str] = None
    account_numbers: Optional[str] = None
    signature_present: Optional[bool] = None
    signature_date: Optional[str] = None

    # W-8BEN fields
    country_of_citizenship: Optional[str] = None
    permanent_address: Optional[str] = None
    permanent_address_city_country: Optional[str] = None
    mailing_address: Optional[str] = None
    mailing_address_city_country: Optional[str] = None
    us_tin: Optional[str] = None
    foreign_tin: Optional[str] = None
    ftin_not_required: Optional[bool] = None
    reference_numbers: Optional[str] = None
    date_of_birth: Optional[str] = None
    treaty_country: Optional[str] = None
    treaty_article: Optional[str] = None
    withholding_rate: Optional[str] = None
    income_type: Optional[str] = None
    treaty_conditions: Optional[str] = None
