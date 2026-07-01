"""InvestorProfile entity.

Represents an existing investor's profile that is stored in the system
as the comparison baseline for the tax onboarding workflow.

An investor profile captures:
  - Identity information (name, address, country)
  - Classification (investor type: US person vs. foreign person)
  - Tax status (verification state of the profile record)
  - The last tax form on file and the date it was signed, which are used
    by downstream validation logic to detect stale / expired certifications

Both US (W-9) and foreign (W-8BEN) investor shapes are supported.
Foreign-specific fields (country_of_citizenship, foreign_tin,
treaty_country) are ``None`` for US investors.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from src.domain.exceptions import InvalidClientDataError
from src.domain.services.tax_form_determination_service import InvestorType, TaxFormCode


class TaxStatus(str, Enum):
    """Verification state of an investor's tax documentation on file."""

    PENDING = "PENDING"       # Form received but not yet verified
    VERIFIED = "VERIFIED"     # Form verified and currently valid
    EXPIRED = "EXPIRED"       # Form on file has passed its validity window
    MISSING = "MISSING"       # No form has ever been submitted


@dataclass
class InvestorProfile:
    """A persisted investor profile used as the comparison baseline.

    Required fields for both US and foreign investors
    --------------------------------------------------
    full_name       Legal name as it appears on tax documents.
    address         Street address.
    investor_type   ``InvestorType.US_PERSON`` or ``InvestorType.FOREIGN_PERSON``.
    tax_status      Current verification state of the tax documentation.

    Optional fields shared by both shapes
    --------------------------------------
    country         Country of residence / citizenship.  Required for
                    foreign investors; optional for US investors
                    (defaults to ``"US"`` when absent).
    last_form_on_file     Most recent tax form code (``'W-9'`` or ``'W-8BEN'``).
    last_form_signed_date ISO 8601 date (``'YYYY-MM-DD'``) the last form was signed.

    Foreign-investor-only fields (None for US investors)
    -----------------------------------------------------
    foreign_tin          Foreign taxpayer identification number.
    treaty_country       Country claimed under a US tax treaty (Part II of W-8BEN).
    """

    # ---- required identity fields ------------------------------------------
    full_name: str
    address: str
    investor_type: InvestorType
    tax_status: TaxStatus

    # ---- surrogate key / audit fields --------------------------------------
    profile_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)

    # ---- optional shared fields --------------------------------------------
    # Country of residence; "US" implied for US persons when omitted
    country: Optional[str] = None

    # Last IRS tax form on file — None means no form has been submitted yet
    last_form_on_file: Optional[TaxFormCode] = None
    # Date the last form was signed in YYYY-MM-DD format
    last_form_signed_date: Optional[str] = None

    # ---- foreign-investor-only fields (None for US persons) ----------------
    # Foreign taxpayer identification number (e.g. Brazilian CPF)
    foreign_tin: Optional[str] = None
    # Country invoked in a Part II treaty claim on the W-8BEN
    treaty_country: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.full_name or not self.full_name.strip():
            raise InvalidClientDataError("full_name must not be empty")
        if not self.address or not self.address.strip():
            raise InvalidClientDataError("address must not be empty")
        if self.investor_type == InvestorType.FOREIGN_PERSON and not self.country:
            raise InvalidClientDataError(
                "country is required for foreign investors"
            )

    # ---- convenience properties --------------------------------------------

    @property
    def required_form(self) -> TaxFormCode:
        """Return the IRS form code required for this investor type."""
        from src.domain.services.tax_form_determination_service import (
            TaxFormDeterminationService,
        )
        return TaxFormDeterminationService.determine_form(self.investor_type.value)

    @property
    def is_foreign(self) -> bool:
        """Return ``True`` when this profile represents a foreign investor."""
        return self.investor_type == InvestorType.FOREIGN_PERSON
