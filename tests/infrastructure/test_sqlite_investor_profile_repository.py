"""Integration tests for SqliteInvestorProfileRepository.

These tests use a real SQLite :memory: database (not mocks) to verify
the full persistence round-trip for both US and foreign investor profile
shapes.

Scenarios covered
-----------------
- save + get_by_id round-trip for a minimal US investor (W-9, no optional fields)
- save + get_by_id round-trip for a fully-populated US investor
- save + get_by_id round-trip for a foreign investor (W-8BEN with treaty fields)
- get_by_id returns None for an unknown profile_id
- list_all returns all saved profiles in most-recently-created-first order
- list_all returns an empty list when no profiles exist
- Nullable columns (country, last_form_on_file, etc.) survive a round-trip as None
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Generator
from unittest.mock import patch

import pytest

from src.domain.entities.investor_profile import InvestorProfile, TaxStatus
from src.domain.services.tax_form_determination_service import InvestorType, TaxFormCode
from src.infrastructure.db.sqlite_investor_profile_repository import (
    SqliteInvestorProfileRepository,
)


# ---------------------------------------------------------------------------
# Fixtures — in-memory SQLite so tests are hermetic and fast
# ---------------------------------------------------------------------------


@pytest.fixture()
def memory_db() -> Generator[sqlite3.Connection, None, None]:
    """Yield an in-memory SQLite connection, initialised with the full schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    # Initialise schema against the in-memory connection
    from src.infrastructure.db import database as db_module

    conn.executescript(db_module._SCHEMA)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture()
def repo(memory_db: sqlite3.Connection) -> Generator[SqliteInvestorProfileRepository, None, None]:
    """Return a repository wired to the in-memory database."""

    def _fake_closing_connection():  # type: ignore[return]
        @contextmanager
        def _ctx():  # type: ignore[return]
            yield memory_db

        return _ctx()

    with patch(
        "src.infrastructure.db.sqlite_investor_profile_repository.closing_connection",
        side_effect=_fake_closing_connection,
    ):
        yield SqliteInvestorProfileRepository()


# ---------------------------------------------------------------------------
# Helpers — explicit constructors so type-checker can validate arguments
# ---------------------------------------------------------------------------


def _minimal_us_profile() -> InvestorProfile:
    """US investor with only required fields set."""
    return InvestorProfile(
        full_name="Jane Doe",
        address="123 Main St, Springfield, IL 62701",
        investor_type=InvestorType.US_PERSON,
        tax_status=TaxStatus.VERIFIED,
    )


def _us_profile_with_form() -> InvestorProfile:
    """US investor with a W-9 on file."""
    return InvestorProfile(
        full_name="Alice Smith",
        address="456 Oak Ave, Boston, MA 02101",
        investor_type=InvestorType.US_PERSON,
        tax_status=TaxStatus.VERIFIED,
        last_form_on_file=TaxFormCode.W9,
        last_form_signed_date="2023-11-01",
    )


def _foreign_profile() -> InvestorProfile:
    """Foreign investor (Brazil, W-8BEN, no treaty)."""
    return InvestorProfile(
        full_name="Carlos Rodrigues",
        address="Rua das Flores 45, São Paulo, SP",
        investor_type=InvestorType.FOREIGN_PERSON,
        tax_status=TaxStatus.VERIFIED,
        country="Brazil",
        last_form_on_file=TaxFormCode.W8BEN,
        last_form_signed_date="2024-03-15",
        foreign_tin="219.871.330-44",
        treaty_country=None,
    )


def _foreign_profile_with_treaty() -> InvestorProfile:
    """Foreign investor (Germany, W-8BEN, treaty claimed)."""
    return InvestorProfile(
        full_name="Hans Müller",
        address="Hauptstraße 12, Berlin",
        investor_type=InvestorType.FOREIGN_PERSON,
        tax_status=TaxStatus.VERIFIED,
        country="Germany",
        last_form_on_file=TaxFormCode.W8BEN,
        last_form_signed_date="2024-01-10",
        treaty_country="Germany",
    )


# ---------------------------------------------------------------------------
# Round-trip tests — US investor
# ---------------------------------------------------------------------------


class TestSaveAndGetUSInvestor:
    def test_get_by_id_returns_saved_profile(self, repo: SqliteInvestorProfileRepository) -> None:
        profile = _minimal_us_profile()
        repo.save(profile)
        result = repo.get_by_id(profile.profile_id)
        assert result is not None
        assert result.profile_id == profile.profile_id

    def test_full_name_survives_round_trip(self, repo: SqliteInvestorProfileRepository) -> None:
        profile = _minimal_us_profile()
        repo.save(profile)
        result = repo.get_by_id(profile.profile_id)
        assert result is not None
        assert result.full_name == "Jane Doe"

    def test_address_survives_round_trip(self, repo: SqliteInvestorProfileRepository) -> None:
        profile = _us_profile_with_form()
        repo.save(profile)
        result = repo.get_by_id(profile.profile_id)
        assert result is not None
        assert result.address == "456 Oak Ave, Boston, MA 02101"

    def test_investor_type_is_us_person(self, repo: SqliteInvestorProfileRepository) -> None:
        profile = _minimal_us_profile()
        repo.save(profile)
        result = repo.get_by_id(profile.profile_id)
        assert result is not None
        assert result.investor_type == InvestorType.US_PERSON

    def test_tax_status_pending_survives_round_trip(
        self, repo: SqliteInvestorProfileRepository
    ) -> None:
        profile = InvestorProfile(
            full_name="Pending Person",
            address="789 Elm St",
            investor_type=InvestorType.US_PERSON,
            tax_status=TaxStatus.PENDING,
        )
        repo.save(profile)
        result = repo.get_by_id(profile.profile_id)
        assert result is not None
        assert result.tax_status == TaxStatus.PENDING

    def test_tax_status_expired_survives_round_trip(
        self, repo: SqliteInvestorProfileRepository
    ) -> None:
        profile = InvestorProfile(
            full_name="Expired Person",
            address="789 Elm St",
            investor_type=InvestorType.US_PERSON,
            tax_status=TaxStatus.EXPIRED,
        )
        repo.save(profile)
        result = repo.get_by_id(profile.profile_id)
        assert result is not None
        assert result.tax_status == TaxStatus.EXPIRED

    def test_tax_status_missing_survives_round_trip(
        self, repo: SqliteInvestorProfileRepository
    ) -> None:
        profile = InvestorProfile(
            full_name="Missing Person",
            address="789 Elm St",
            investor_type=InvestorType.US_PERSON,
            tax_status=TaxStatus.MISSING,
        )
        repo.save(profile)
        result = repo.get_by_id(profile.profile_id)
        assert result is not None
        assert result.tax_status == TaxStatus.MISSING

    def test_last_form_on_file_w9_survives_round_trip(
        self, repo: SqliteInvestorProfileRepository
    ) -> None:
        profile = _us_profile_with_form()
        repo.save(profile)
        result = repo.get_by_id(profile.profile_id)
        assert result is not None
        assert result.last_form_on_file == TaxFormCode.W9
        assert result.last_form_signed_date == "2023-11-01"

    def test_nullable_fields_are_none_for_minimal_us_investor(
        self, repo: SqliteInvestorProfileRepository
    ) -> None:
        """country, last_form_on_file, foreign_tin, treaty_country default to None."""
        profile = _minimal_us_profile()
        repo.save(profile)
        result = repo.get_by_id(profile.profile_id)
        assert result is not None
        assert result.country is None
        assert result.last_form_on_file is None
        assert result.last_form_signed_date is None
        assert result.foreign_tin is None
        assert result.treaty_country is None

    def test_created_at_survives_round_trip(self, repo: SqliteInvestorProfileRepository) -> None:
        ts = datetime(2024, 6, 15, 10, 30, 0)
        profile = InvestorProfile(
            full_name="Jane Doe",
            address="123 Main St",
            investor_type=InvestorType.US_PERSON,
            tax_status=TaxStatus.VERIFIED,
            created_at=ts,
        )
        repo.save(profile)
        result = repo.get_by_id(profile.profile_id)
        assert result is not None
        assert result.created_at == ts

    def test_is_foreign_property_false_for_us_investor(
        self, repo: SqliteInvestorProfileRepository
    ) -> None:
        profile = _minimal_us_profile()
        repo.save(profile)
        result = repo.get_by_id(profile.profile_id)
        assert result is not None
        assert result.is_foreign is False

    def test_required_form_is_w9_for_us_investor(
        self, repo: SqliteInvestorProfileRepository
    ) -> None:
        profile = _minimal_us_profile()
        repo.save(profile)
        result = repo.get_by_id(profile.profile_id)
        assert result is not None
        assert result.required_form == TaxFormCode.W9


# ---------------------------------------------------------------------------
# Round-trip tests — foreign investor (W-8BEN shape)
# ---------------------------------------------------------------------------


class TestSaveAndGetForeignInvestor:
    def test_get_by_id_returns_saved_foreign_profile(
        self, repo: SqliteInvestorProfileRepository
    ) -> None:
        profile = _foreign_profile()
        repo.save(profile)
        result = repo.get_by_id(profile.profile_id)
        assert result is not None
        assert result.profile_id == profile.profile_id

    def test_investor_type_is_foreign_person(
        self, repo: SqliteInvestorProfileRepository
    ) -> None:
        profile = _foreign_profile()
        repo.save(profile)
        result = repo.get_by_id(profile.profile_id)
        assert result is not None
        assert result.investor_type == InvestorType.FOREIGN_PERSON

    def test_country_survives_round_trip(self, repo: SqliteInvestorProfileRepository) -> None:
        profile = _foreign_profile()
        repo.save(profile)
        result = repo.get_by_id(profile.profile_id)
        assert result is not None
        assert result.country == "Brazil"

    def test_last_form_on_file_w8ben_survives_round_trip(
        self, repo: SqliteInvestorProfileRepository
    ) -> None:
        profile = _foreign_profile()
        repo.save(profile)
        result = repo.get_by_id(profile.profile_id)
        assert result is not None
        assert result.last_form_on_file == TaxFormCode.W8BEN

    def test_last_form_signed_date_survives_round_trip(
        self, repo: SqliteInvestorProfileRepository
    ) -> None:
        profile = _foreign_profile()
        repo.save(profile)
        result = repo.get_by_id(profile.profile_id)
        assert result is not None
        assert result.last_form_signed_date == "2024-03-15"

    def test_foreign_tin_survives_round_trip(
        self, repo: SqliteInvestorProfileRepository
    ) -> None:
        profile = _foreign_profile()
        repo.save(profile)
        result = repo.get_by_id(profile.profile_id)
        assert result is not None
        assert result.foreign_tin == "219.871.330-44"

    def test_treaty_country_survives_round_trip(
        self, repo: SqliteInvestorProfileRepository
    ) -> None:
        profile = _foreign_profile_with_treaty()
        repo.save(profile)
        result = repo.get_by_id(profile.profile_id)
        assert result is not None
        assert result.treaty_country == "Germany"

    def test_treaty_country_is_none_when_not_set(
        self, repo: SqliteInvestorProfileRepository
    ) -> None:
        profile = _foreign_profile()  # Brazil — no treaty
        repo.save(profile)
        result = repo.get_by_id(profile.profile_id)
        assert result is not None
        assert result.treaty_country is None

    def test_is_foreign_property_true(self, repo: SqliteInvestorProfileRepository) -> None:
        profile = _foreign_profile()
        repo.save(profile)
        result = repo.get_by_id(profile.profile_id)
        assert result is not None
        assert result.is_foreign is True

    def test_required_form_is_w8ben(self, repo: SqliteInvestorProfileRepository) -> None:
        profile = _foreign_profile()
        repo.save(profile)
        result = repo.get_by_id(profile.profile_id)
        assert result is not None
        assert result.required_form == TaxFormCode.W8BEN

    def test_country_germany_with_treaty_survives_round_trip(
        self, repo: SqliteInvestorProfileRepository
    ) -> None:
        profile = _foreign_profile_with_treaty()
        repo.save(profile)
        result = repo.get_by_id(profile.profile_id)
        assert result is not None
        assert result.country == "Germany"
        assert result.treaty_country == "Germany"


# ---------------------------------------------------------------------------
# get_by_id — missing profile
# ---------------------------------------------------------------------------


class TestGetByIdMissing:
    def test_returns_none_for_unknown_id(self, repo: SqliteInvestorProfileRepository) -> None:
        result = repo.get_by_id("00000000-0000-0000-0000-000000000000")
        assert result is None

    def test_returns_none_after_saving_different_profile(
        self, repo: SqliteInvestorProfileRepository
    ) -> None:
        profile = _minimal_us_profile()
        repo.save(profile)
        result = repo.get_by_id("non-existent-id")
        assert result is None


# ---------------------------------------------------------------------------
# list_all
# ---------------------------------------------------------------------------


class TestListAll:
    def test_empty_when_no_profiles(self, repo: SqliteInvestorProfileRepository) -> None:
        assert repo.list_all() == []

    def test_returns_single_saved_profile(self, repo: SqliteInvestorProfileRepository) -> None:
        profile = _minimal_us_profile()
        repo.save(profile)
        results = repo.list_all()
        assert len(results) == 1
        assert results[0].profile_id == profile.profile_id

    def test_returns_all_saved_profiles(self, repo: SqliteInvestorProfileRepository) -> None:
        us = _minimal_us_profile()
        foreign = _foreign_profile()
        repo.save(us)
        repo.save(foreign)
        results = repo.list_all()
        assert len(results) == 2

    def test_list_contains_both_us_and_foreign_profiles(
        self, repo: SqliteInvestorProfileRepository
    ) -> None:
        us = _minimal_us_profile()
        foreign = _foreign_profile()
        repo.save(us)
        repo.save(foreign)
        ids = {p.profile_id for p in repo.list_all()}
        assert us.profile_id in ids
        assert foreign.profile_id in ids

    def test_list_all_ordered_most_recent_first(
        self, repo: SqliteInvestorProfileRepository
    ) -> None:
        older = InvestorProfile(
            full_name="Older Investor",
            address="1 Old St",
            investor_type=InvestorType.US_PERSON,
            tax_status=TaxStatus.VERIFIED,
            created_at=datetime(2024, 1, 1),
        )
        newer = InvestorProfile(
            full_name="Newer Investor",
            address="2 New St",
            investor_type=InvestorType.US_PERSON,
            tax_status=TaxStatus.VERIFIED,
            created_at=datetime(2024, 6, 1),
        )
        repo.save(older)
        repo.save(newer)
        results = repo.list_all()
        assert results[0].profile_id == newer.profile_id
        assert results[1].profile_id == older.profile_id
