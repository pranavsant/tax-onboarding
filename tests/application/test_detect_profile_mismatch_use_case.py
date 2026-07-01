"""Unit tests for DetectProfileMismatchUseCase.

Acceptance criteria:
  AC #1 — Matching submission and profile → no mismatch flags raised
  AC #2 — Changed name → mismatch is flagged with a clear reason
  AC #3 — Changed address → mismatch is flagged with a clear reason

Seeded persona parity:
  The test helpers mirror the seeded mock profiles (James Whitfield, Ingrid
  Weber) so the acceptance-criterion test cases exercise realistic data:
    - James Whitfield: US person, W-9, address "84 Pinecrest Drive, …"
    - Ingrid Weber: German foreign person, W-8BEN, "Friedrichstraße 88 …"

Additional cases:
  - W-8BEN form uses permanent_address (not address) for comparison
  - Both name and address changed → two mismatches
  - Result type is always ProfileMismatchResultDTO
  - Mismatch items are MismatchDetailDTO instances
  - Unsupported form_type raises ValueError
"""
from __future__ import annotations

import pytest

from src.application.dto.tax_form_dto import (
    MismatchDetailDTO,
    ParsedFormFieldsDTO,
    ProfileMismatchResultDTO,
)
from src.application.use_cases.detect_profile_mismatch import DetectProfileMismatchUseCase
from src.domain.entities.investor_profile import InvestorProfile, TaxStatus
from src.domain.services.tax_form_determination_service import InvestorType, TaxFormCode


# ---------------------------------------------------------------------------
# Profile fixtures (mirror seeded personas)
# ---------------------------------------------------------------------------


def _whitfield_profile() -> InvestorProfile:
    """James Whitfield — US person, verified W-9."""
    return InvestorProfile(
        profile_id="11111111-0000-0000-0000-000000000001",
        full_name="James Whitfield",
        address="84 Pinecrest Drive, Austin, TX 78701",
        investor_type=InvestorType.US_PERSON,
        tax_status=TaxStatus.VERIFIED,
        last_form_on_file=TaxFormCode.W9,
        last_form_signed_date="2023-04-10",
    )


def _weber_profile() -> InvestorProfile:
    """Ingrid Weber — German foreign investor, W-8BEN with treaty claim."""
    return InvestorProfile(
        profile_id="11111111-0000-0000-0000-000000000004",
        full_name="Ingrid Weber",
        address="Friedrichstraße 88, 10117 Berlin, Germany",
        investor_type=InvestorType.FOREIGN_PERSON,
        tax_status=TaxStatus.VERIFIED,
        country="Germany",
        last_form_on_file=TaxFormCode.W8BEN,
        last_form_signed_date="2024-07-22",
        treaty_country="Germany",
    )


# ---------------------------------------------------------------------------
# DTO helpers
# ---------------------------------------------------------------------------


def _w9_dto(**kwargs) -> ParsedFormFieldsDTO:
    """Return a minimal W-9 ParsedFormFieldsDTO matching James Whitfield."""
    defaults: dict = {
        "form_type": "W-9",
        "name": "James Whitfield",
        "address": "84 Pinecrest Drive, Austin, TX 78701",
        "city_state_zip": "Austin, TX 78701",
        "tin": "412-88-7693",
        "tin_type": "SSN",
        "federal_tax_classification": "Individual",
        "signature_present": True,
        "signature_date": "2023-04-10",
    }
    defaults.update(kwargs)
    return ParsedFormFieldsDTO(**defaults)


def _w8ben_dto(**kwargs) -> ParsedFormFieldsDTO:
    """Return a minimal W-8BEN ParsedFormFieldsDTO matching Ingrid Weber."""
    defaults: dict = {
        "form_type": "W-8BEN",
        "name": "Ingrid Weber",
        "country_of_citizenship": "Germany",
        "permanent_address": "Friedrichstraße 88, 10117 Berlin, Germany",
        "permanent_address_city_country": "Berlin, Germany",
        "foreign_tin": "DE123456789",
        "treaty_country": "Germany",
        "treaty_article": "Article 10",
        "withholding_rate": "15%",
        "signature_present": True,
        "signature_date": "2024-07-22",
    }
    defaults.update(kwargs)
    return ParsedFormFieldsDTO(**defaults)


# ===========================================================================
# Return type
# ===========================================================================


class TestDetectProfileMismatchUseCaseReturnType:
    def test_returns_profile_mismatch_result_dto(self) -> None:
        uc = DetectProfileMismatchUseCase()
        result = uc.execute(_w9_dto(), _whitfield_profile())
        assert isinstance(result, ProfileMismatchResultDTO)

    def test_mismatches_is_a_list(self) -> None:
        uc = DetectProfileMismatchUseCase()
        result = uc.execute(_w9_dto(), _whitfield_profile())
        assert isinstance(result.mismatches, list)


# ===========================================================================
# Acceptance criterion #1 — matching submission and profile → no mismatches
# ===========================================================================


class TestAcceptanceCriteriaMatchingSubmission:
    """AC #1: given matching submission and profile, no mismatch flags raised."""

    def setup_method(self) -> None:
        self.uc = DetectProfileMismatchUseCase()

    # ---- W-9 (James Whitfield) ------------------------------------------

    def test_w9_exact_match_has_no_mismatches(self) -> None:
        """AC #1 (W-9): profile = submission → no mismatches."""
        result = self.uc.execute(_w9_dto(), _whitfield_profile())
        assert result.has_mismatches is False

    def test_w9_exact_match_mismatches_list_is_empty(self) -> None:
        result = self.uc.execute(_w9_dto(), _whitfield_profile())
        assert result.mismatches == []

    # ---- W-8BEN (Ingrid Weber) -------------------------------------------

    def test_w8ben_exact_match_has_no_mismatches(self) -> None:
        """AC #1 (W-8BEN): profile = submission → no mismatches."""
        result = self.uc.execute(_w8ben_dto(), _weber_profile())
        assert result.has_mismatches is False

    def test_w8ben_exact_match_mismatches_list_is_empty(self) -> None:
        result = self.uc.execute(_w8ben_dto(), _weber_profile())
        assert result.mismatches == []

    def test_case_insensitive_name_match_is_clean(self) -> None:
        result = self.uc.execute(
            _w9_dto(name="james whitfield"),
            _whitfield_profile(),
        )
        assert result.has_mismatches is False

    def test_whitespace_trimmed_address_match_is_clean(self) -> None:
        result = self.uc.execute(
            _w9_dto(address="  84 Pinecrest Drive, Austin, TX 78701  "),
            _whitfield_profile(),
        )
        assert result.has_mismatches is False


# ===========================================================================
# Acceptance criterion #2 — changed name → mismatch flagged with clear reason
# ===========================================================================


class TestAcceptanceCriteriaChangedName:
    """AC #2: given a changed name, mismatch is flagged with a clear reason."""

    def setup_method(self) -> None:
        self.uc = DetectProfileMismatchUseCase()

    def test_changed_name_w9_has_mismatches(self) -> None:
        """AC #2 (W-9): changed name is flagged."""
        result = self.uc.execute(
            _w9_dto(name="James Whitfield Jr."),
            _whitfield_profile(),
        )
        assert result.has_mismatches is True

    def test_changed_name_w9_yields_one_mismatch(self) -> None:
        result = self.uc.execute(
            _w9_dto(name="James Whitfield Jr."),
            _whitfield_profile(),
        )
        assert len(result.mismatches) == 1

    def test_changed_name_w9_mismatch_field_is_name(self) -> None:
        result = self.uc.execute(
            _w9_dto(name="James Whitfield Jr."),
            _whitfield_profile(),
        )
        assert result.mismatches[0].field == "name"

    def test_changed_name_w9_reason_is_non_empty(self) -> None:
        result = self.uc.execute(
            _w9_dto(name="James Whitfield Jr."),
            _whitfield_profile(),
        )
        assert result.mismatches[0].reason != ""

    def test_changed_name_w9_reason_mentions_name(self) -> None:
        result = self.uc.execute(
            _w9_dto(name="James Whitfield Jr."),
            _whitfield_profile(),
        )
        assert "name" in result.mismatches[0].reason.lower()

    def test_changed_name_w9_reason_mentions_both_name_values(self) -> None:
        result = self.uc.execute(
            _w9_dto(name="James Whitfield Jr."),
            _whitfield_profile(),
        )
        reason = result.mismatches[0].reason
        assert "James Whitfield" in reason
        assert "James Whitfield Jr." in reason

    def test_changed_name_mismatch_item_is_mismatch_detail_dto(self) -> None:
        result = self.uc.execute(
            _w9_dto(name="James Whitfield Jr."),
            _whitfield_profile(),
        )
        assert isinstance(result.mismatches[0], MismatchDetailDTO)

    def test_changed_name_w8ben_also_flagged(self) -> None:
        """AC #2 (W-8BEN): name change on W-8BEN also flagged."""
        result = self.uc.execute(
            _w8ben_dto(name="Ingrid Weber-Schmidt"),
            _weber_profile(),
        )
        assert result.has_mismatches is True
        assert result.mismatches[0].field == "name"

    def test_mismatch_detail_dto_profile_value_correct(self) -> None:
        result = self.uc.execute(
            _w9_dto(name="James Whitfield Jr."),
            _whitfield_profile(),
        )
        assert result.mismatches[0].profile_value == "James Whitfield"

    def test_mismatch_detail_dto_submitted_value_correct(self) -> None:
        result = self.uc.execute(
            _w9_dto(name="James Whitfield Jr."),
            _whitfield_profile(),
        )
        assert result.mismatches[0].submitted_value == "James Whitfield Jr."


# ===========================================================================
# Acceptance criterion #3 — changed address → mismatch flagged with clear reason
# ===========================================================================


class TestAcceptanceCriteriaChangedAddress:
    """AC #3: given a changed address, mismatch is flagged with a clear reason."""

    def setup_method(self) -> None:
        self.uc = DetectProfileMismatchUseCase()

    def test_changed_address_w9_has_mismatches(self) -> None:
        """AC #3 (W-9): changed address is flagged."""
        result = self.uc.execute(
            _w9_dto(address="99 New Street, Austin, TX 78702"),
            _whitfield_profile(),
        )
        assert result.has_mismatches is True

    def test_changed_address_w9_yields_one_mismatch(self) -> None:
        result = self.uc.execute(
            _w9_dto(address="99 New Street, Austin, TX 78702"),
            _whitfield_profile(),
        )
        assert len(result.mismatches) == 1

    def test_changed_address_w9_mismatch_field_is_address(self) -> None:
        result = self.uc.execute(
            _w9_dto(address="99 New Street, Austin, TX 78702"),
            _whitfield_profile(),
        )
        assert result.mismatches[0].field == "address"

    def test_changed_address_w9_reason_is_non_empty(self) -> None:
        result = self.uc.execute(
            _w9_dto(address="99 New Street, Austin, TX 78702"),
            _whitfield_profile(),
        )
        assert result.mismatches[0].reason != ""

    def test_changed_address_w9_reason_mentions_address(self) -> None:
        result = self.uc.execute(
            _w9_dto(address="99 New Street, Austin, TX 78702"),
            _whitfield_profile(),
        )
        assert "address" in result.mismatches[0].reason.lower()

    def test_changed_address_w9_reason_mentions_both_address_values(self) -> None:
        result = self.uc.execute(
            _w9_dto(address="99 New Street, Austin, TX 78702"),
            _whitfield_profile(),
        )
        reason = result.mismatches[0].reason
        assert "84 Pinecrest Drive" in reason
        assert "99 New Street" in reason

    def test_changed_permanent_address_w8ben_flagged(self) -> None:
        """AC #3 (W-8BEN): changed permanent_address is flagged."""
        result = self.uc.execute(
            _w8ben_dto(permanent_address="Unter den Linden 10, 10117 Berlin, Germany"),
            _weber_profile(),
        )
        assert result.has_mismatches is True
        assert result.mismatches[0].field == "address"

    def test_w8ben_uses_permanent_address_not_address_field(self) -> None:
        """W-8BEN comparison must use permanent_address, ignoring address."""
        # Provide a wrong `address` field but correct `permanent_address`.
        # If the use case erroneously reads `address` instead of
        # `permanent_address`, it would flag a mismatch incorrectly.
        dto = _w8ben_dto(
            permanent_address="Friedrichstraße 88, 10117 Berlin, Germany",
        )
        # Manually set the unused `address` field to something different.
        dto.address = "Something Completely Different"
        result = self.uc.execute(dto, _weber_profile())
        # Should still match because permanent_address is correct.
        assert result.has_mismatches is False


# ===========================================================================
# Both name and address changed
# ===========================================================================


class TestBothFieldsChanged:
    def test_both_fields_changed_yields_two_mismatches(self) -> None:
        uc = DetectProfileMismatchUseCase()
        result = uc.execute(
            _w9_dto(
                name="James Whitfield Jr.",
                address="99 New Street, Austin, TX 78702",
            ),
            _whitfield_profile(),
        )
        assert result.has_mismatches is True
        assert len(result.mismatches) == 2

    def test_both_fields_changed_fields_are_name_and_address(self) -> None:
        uc = DetectProfileMismatchUseCase()
        result = uc.execute(
            _w9_dto(
                name="James Whitfield Jr.",
                address="99 New Street, Austin, TX 78702",
            ),
            _whitfield_profile(),
        )
        fields = {m.field for m in result.mismatches}
        assert fields == {"name", "address"}


# ===========================================================================
# Error handling
# ===========================================================================


class TestDetectProfileMismatchUseCaseErrors:
    def test_unsupported_form_type_raises_value_error(self) -> None:
        uc = DetectProfileMismatchUseCase()
        dto = ParsedFormFieldsDTO(form_type="W-8IMY")
        with pytest.raises(ValueError, match="W-8IMY"):
            uc.execute(dto, _whitfield_profile())
