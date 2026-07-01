"""Composition-root seed script for investor profile mock data.

Populates the ``investor_profiles`` table with a fixed set of test
personas used for comparison testing throughout the tax onboarding
workflow.  The script is **idempotent**: each profile is identified by
a stable, hardcoded ``profile_id``; profiles that already exist in the
database are skipped rather than re-inserted or overwritten.

Seed personas
-------------
1. James Whitfield       — US person, W-9 on file, VERIFIED.
2. Mariana Costa Ribeiro — Brazilian foreign investor, W-8BEN on file,
                           EXPIRED (tests the expiration-check path).
3. Robert Nguyen         — US person, no form yet, PENDING
                           (tests the missing-form path).
4. Ingrid Weber          — German foreign investor, W-8BEN on file,
                           treaty claim active, VERIFIED
                           (tests the treaty-claim path).

Run with:
    python seed_investor_profiles.py
"""
from __future__ import annotations

from datetime import datetime

from src.domain.entities.investor_profile import InvestorProfile, TaxStatus
from src.domain.services.tax_form_determination_service import InvestorType, TaxFormCode
from src.infrastructure.db.database import init_db
from src.infrastructure.db.sqlite_investor_profile_repository import (
    SqliteInvestorProfileRepository,
)

# ---------------------------------------------------------------------------
# Stable profile IDs — never change these; they are the idempotency keys.
# ---------------------------------------------------------------------------

_WHITFIELD_ID = "11111111-0000-0000-0000-000000000001"
_RIBEIRO_ID = "11111111-0000-0000-0000-000000000002"
_NGUYEN_ID = "11111111-0000-0000-0000-000000000003"
_WEBER_ID = "11111111-0000-0000-0000-000000000004"


def _seed_profiles(repo: SqliteInvestorProfileRepository) -> None:
    """Insert each mock profile if it does not already exist."""

    profiles: list[InvestorProfile] = [
        # ------------------------------------------------------------------
        # 1. James Whitfield — US person, verified W-9
        # ------------------------------------------------------------------
        InvestorProfile(
            profile_id=_WHITFIELD_ID,
            full_name="James Whitfield",
            address="84 Pinecrest Drive, Austin, TX 78701",
            investor_type=InvestorType.US_PERSON,
            tax_status=TaxStatus.VERIFIED,
            country=None,                        # Not required for US persons
            last_form_on_file=TaxFormCode.W9,
            last_form_signed_date="2023-04-10",
            foreign_tin=None,
            treaty_country=None,
            created_at=datetime(2023, 4, 10, 9, 0, 0),
        ),
        # ------------------------------------------------------------------
        # 2. Mariana Costa Ribeiro — Brazilian foreign investor, EXPIRED W-8BEN
        #    Exercises the expiration-check use case: a W-8BEN signed more
        #    than three years ago is considered expired.
        # ------------------------------------------------------------------
        InvestorProfile(
            profile_id=_RIBEIRO_ID,
            full_name="Mariana Costa Ribeiro",
            address="Av. Paulista 1578, Apto 42, São Paulo, SP 01310-200, Brazil",
            investor_type=InvestorType.FOREIGN_PERSON,
            tax_status=TaxStatus.EXPIRED,
            country="Brazil",
            last_form_on_file=TaxFormCode.W8BEN,
            last_form_signed_date="2021-01-15",  # > 3 years ago → EXPIRED
            foreign_tin="317.940.520-88",        # Brazilian CPF format
            treaty_country=None,                 # Brazil has no US tax treaty
            created_at=datetime(2021, 1, 15, 14, 30, 0),
        ),
        # ------------------------------------------------------------------
        # 3. Robert Nguyen — US person, no form on file (PENDING)
        #    Exercises the missing-form / PENDING status path.
        # ------------------------------------------------------------------
        InvestorProfile(
            profile_id=_NGUYEN_ID,
            full_name="Robert Nguyen",
            address="210 Lakeview Blvd, Seattle, WA 98101",
            investor_type=InvestorType.US_PERSON,
            tax_status=TaxStatus.PENDING,
            country=None,
            last_form_on_file=None,              # No form submitted yet
            last_form_signed_date=None,
            foreign_tin=None,
            treaty_country=None,
            created_at=datetime(2024, 3, 5, 11, 0, 0),
        ),
        # ------------------------------------------------------------------
        # 4. Ingrid Weber — German foreign investor, W-8BEN + treaty claim
        #    Exercises the treaty-claim validation path (Germany has a US
        #    income tax treaty; withholding rate is reduced to 15 %).
        # ------------------------------------------------------------------
        InvestorProfile(
            profile_id=_WEBER_ID,
            full_name="Ingrid Weber",
            address="Friedrichstraße 88, 10117 Berlin, Germany",
            investor_type=InvestorType.FOREIGN_PERSON,
            tax_status=TaxStatus.VERIFIED,
            country="Germany",
            last_form_on_file=TaxFormCode.W8BEN,
            last_form_signed_date="2024-07-22",
            foreign_tin="DE123456789",           # German Steuer-ID placeholder
            treaty_country="Germany",            # Part II treaty claim filed
            created_at=datetime(2024, 7, 22, 8, 45, 0),
        ),
    ]

    inserted = 0
    skipped = 0

    for profile in profiles:
        existing = repo.get_by_id(profile.profile_id)
        if existing is not None:
            print(f"  [skip]   {profile.full_name} (already exists)")
            skipped += 1
        else:
            repo.save(profile)
            print(f"  [insert] {profile.full_name}")
            inserted += 1

    print(f"\nDone — {inserted} inserted, {skipped} skipped.")


def main() -> None:
    print("Initialising database schema …")
    init_db()

    repo = SqliteInvestorProfileRepository()

    print("Seeding investor profiles …")
    _seed_profiles(repo)


if __name__ == "__main__":
    main()
