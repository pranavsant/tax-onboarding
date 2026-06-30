"""Data Transfer Objects for tax form determination and field normalization.

DTOs are the only objects that cross the application/interfaces
boundary — domain types never leak outward.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class DetermineFormDTO:
    """Input DTO carrying the raw investor_type string from the caller."""

    investor_type: str


@dataclass
class FormDeterminationResultDTO:
    """Output DTO returned by :class:`DetermineRequiredFormUseCase`."""

    investor_type: str
    required_form: str


# ---------------------------------------------------------------------------
# W-9 / W-8BEN raw field input DTOs
# These mirror the fields a PDF extractor would pull from each form.
# ---------------------------------------------------------------------------


@dataclass
class W9FieldsDTO:
    """Raw extracted fields from a W-9 (Request for Taxpayer Identification
    Number and Certification) form.

    All string fields default to ``None`` because they may be absent in a
    partially-completed or OCR-scanned document.
    """

    # Box 1 — legal name as shown on income tax return
    name: str
    # Box 3 — federal tax classification
    federal_tax_classification: str
    # Box 5 — street address
    address: str
    # Box 6 — city, state, ZIP code
    city_state_zip: str
    # Part I — TIN (one of SSN or EIN must be present)
    tin: str
    # "SSN" or "EIN"
    tin_type: str

    # Optional fields
    # Box 2 — business name / disregarded entity name
    business_name: Optional[str] = None
    # Box 4 — exemption codes
    exempt_payee_code: Optional[str] = None
    exemption_from_fatca_code: Optional[str] = None
    # Box 7 — list account number(s) here
    account_numbers: Optional[str] = None


@dataclass
class W8BENFieldsDTO:
    """Raw extracted fields from a W-8BEN (Certificate of Foreign Status of
    Beneficial Owner for United States Tax Withholding and Reporting) form.

    Required fields are those mandated by IRS instructions for the form to
    be considered valid.
    """

    # Part I — Identification of Beneficial Owner
    # Line 1 — name of individual who is the beneficial owner
    name: str
    # Line 2 — country of citizenship
    country_of_citizenship: str
    # Line 3 — permanent residence address
    permanent_address: str
    # Line 3 — city / state / country (combined per IRS form layout)
    permanent_address_city_country: str

    # Optional fields
    # Line 4 — mailing address (if different from above)
    mailing_address: Optional[str] = None
    mailing_address_city_country: Optional[str] = None
    # Line 5 — US taxpayer identification number (SSN or ITIN)
    us_tin: Optional[str] = None
    # Line 6a — foreign tax identifying number
    foreign_tin: Optional[str] = None
    # Line 6b — check if FTIN not legally required
    ftin_not_required: Optional[bool] = None
    # Line 7 — reference number(s)
    reference_numbers: Optional[str] = None
    # Line 8 — date of birth (YYYY-MM-DD)
    date_of_birth: Optional[str] = None

    # Part II — Claim of Tax Treaty Benefits (optional)
    # Line 9 — country for treaty claim
    treaty_country: Optional[str] = None
    # Line 10 — article of the treaty
    treaty_article: Optional[str] = None
    # Line 10 — withholding rate %
    withholding_rate: Optional[str] = None
    # Line 10 — type of income
    income_type: Optional[str] = None
    # Line 10 — additional treaty conditions
    treaty_conditions: Optional[str] = None


# ---------------------------------------------------------------------------
# Normalized intermediate representation (output of both JSON and PDF paths)
# ---------------------------------------------------------------------------


@dataclass
class ParsedFormFieldsDTO:
    """Normalized intermediate representation of extracted tax form fields.

    Produced by both the JSON input path and the PDF extraction path so
    that downstream validation logic can be written once and tested
    against either source.

    ``form_type`` is ``'W-9'`` or ``'W-8BEN'``.  All form-specific fields
    are ``Optional``; the subset populated depends on ``form_type``.
    """

    form_type: str  # "W-9" or "W-8BEN"

    # ---- shared / W-9 fields ------------------------------------------------
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

    # ---- W-8BEN-specific fields ---------------------------------------------
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
