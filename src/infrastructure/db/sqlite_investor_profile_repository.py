"""SQLite implementation of the InvestorProfileRepository port.

Maps DB rows to/from InvestorProfile domain entities.  No business
logic lives here — only persistence concerns.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import List, Optional

from src.domain.entities.investor_profile import InvestorProfile, TaxStatus
from src.domain.repositories.investor_profile_repository import InvestorProfileRepository
from src.domain.services.tax_form_determination_service import InvestorType, TaxFormCode
from src.infrastructure.db.database import closing_connection


class SqliteInvestorProfileRepository(InvestorProfileRepository):
    """Persists InvestorProfile entities in the local SQLite database."""

    def save(self, profile: InvestorProfile) -> InvestorProfile:
        with closing_connection() as conn:
            conn.execute(
                """
                INSERT INTO investor_profiles (
                    profile_id,
                    full_name,
                    address,
                    investor_type,
                    tax_status,
                    country,
                    last_form_on_file,
                    last_form_signed_date,
                    foreign_tin,
                    treaty_country,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.profile_id,
                    profile.full_name,
                    profile.address,
                    profile.investor_type.value,
                    profile.tax_status.value,
                    profile.country,
                    profile.last_form_on_file.value if profile.last_form_on_file else None,
                    profile.last_form_signed_date,
                    profile.foreign_tin,
                    profile.treaty_country,
                    profile.created_at.isoformat(),
                ),
            )
            conn.commit()
        return profile

    def get_by_id(self, profile_id: str) -> Optional[InvestorProfile]:
        with closing_connection() as conn:
            row = conn.execute(
                "SELECT * FROM investor_profiles WHERE profile_id = ?",
                (profile_id,),
            ).fetchone()
        return _row_to_entity(row) if row else None

    def list_all(self) -> List[InvestorProfile]:
        with closing_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM investor_profiles ORDER BY created_at DESC"
            ).fetchall()
        return [_row_to_entity(row) for row in rows]


def _row_to_entity(row: sqlite3.Row) -> InvestorProfile:
    last_form_raw: Optional[str] = row["last_form_on_file"]
    return InvestorProfile(
        profile_id=row["profile_id"],
        full_name=row["full_name"],
        address=row["address"],
        investor_type=InvestorType(row["investor_type"]),
        tax_status=TaxStatus(row["tax_status"]),
        country=row["country"],
        last_form_on_file=TaxFormCode(last_form_raw) if last_form_raw else None,
        last_form_signed_date=row["last_form_signed_date"],
        foreign_tin=row["foreign_tin"],
        treaty_country=row["treaty_country"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )
