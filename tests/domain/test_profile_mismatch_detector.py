"""Unit tests for ProfileMismatchDetector domain service.

Covers:
  - Matching submission → no mismatches (acceptance criterion: profile = submission)
  - Changed name → mismatch flagged with clear reason
  - Changed address → mismatch flagged with clear reason
  - Both name and address changed → two mismatches
  - Case-insensitive and whitespace-normalised matching (no false positives)
  - None / empty submitted fields treated as absent → mismatch when profile non-empty
  - has_mismatches reflects mismatch list length correctly
  - Return type is always ProfileMismatchResult
"""
from __future__ import annotations

from src.domain.entities.investor_profile import InvestorProfile, TaxStatus
from src.domain.services.profile_mismatch_detector import (
    MismatchDetail,
    ProfileMismatchDetector,
    ProfileMismatchResult,
)
from src.domain.services.tax_form_determination_service import InvestorType, TaxFormCode


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _us_profile(**kwargs) -> InvestorProfile:
    """Return a US-person InvestorProfile with sane defaults."""
    defaults = dict(
        profile_id="11111111-0000-0000-0000-000000000001",
        full_name="James Whitfield",
        address="84 Pinecrest Drive, Austin, TX 78701",
        investor_type=InvestorType.US_PERSON,
        tax_status=TaxStatus.VERIFIED,
        last_form_on_file=TaxFormCode.W9,
        last_form_signed_date="2023-04-10",
    )
    defaults.update(kwargs)
    return InvestorProfile(**defaults)


def _foreign_profile(**kwargs) -> InvestorProfile:
    """Return a FOREIGN-person InvestorProfile with sane defaults."""
    defaults = dict(
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
    defaults.update(kwargs)
    return InvestorProfile(**defaults)


# ===========================================================================
# Return type
# ===========================================================================


class TestProfileMismatchDetectorReturnType:
    def test_returns_profile_mismatch_result(self) -> None:
        profile = _us_profile()
        result = ProfileMismatchDetector.compare(
            profile=profile,
            submitted_name="James Whitfield",
            submitted_address="84 Pinecrest Drive, Austin, TX 78701",
        )
        assert isinstance(result, ProfileMismatchResult)

    def test_mismatches_is_a_list(self) -> None:
        profile = _us_profile()
        result = ProfileMismatchDetector.compare(
            profile=profile,
            submitted_name="James Whitfield",
            submitted_address="84 Pinecrest Drive, Austin, TX 78701",
        )
        assert isinstance(result.mismatches, list)


# ===========================================================================
# Acceptance criterion: matching submission → no mismatches
# ===========================================================================


class TestMatchingSubmission:
    """Acceptance criterion: profile == submission → no mismatch flags raised."""

    def test_exact_match_has_no_mismatches(self) -> None:
        profile = _us_profile()
        result = ProfileMismatchDetector.compare(
            profile=profile,
            submitted_name="James Whitfield",
            submitted_address="84 Pinecrest Drive, Austin, TX 78701",
        )
        assert result.has_mismatches is False

    def test_exact_match_mismatches_list_is_empty(self) -> None:
        profile = _us_profile()
        result = ProfileMismatchDetector.compare(
            profile=profile,
            submitted_name="James Whitfield",
            submitted_address="84 Pinecrest Drive, Austin, TX 78701",
        )
        assert result.mismatches == []

    def test_exact_match_foreign_investor(self) -> None:
        profile = _foreign_profile()
        result = ProfileMismatchDetector.compare(
            profile=profile,
            submitted_name="Ingrid Weber",
            submitted_address="Friedrichstraße 88, 10117 Berlin, Germany",
        )
        assert result.has_mismatches is False
        assert result.mismatches == []

    def test_case_insensitive_name_match_is_clean(self) -> None:
        """Mixed-case submission is NOT flagged as a mismatch."""
        profile = _us_profile()
        result = ProfileMismatchDetector.compare(
            profile=profile,
            submitted_name="james whitfield",  # lower-case
            submitted_address="84 Pinecrest Drive, Austin, TX 78701",
        )
        assert result.has_mismatches is False

    def test_whitespace_trimmed_name_match_is_clean(self) -> None:
        profile = _us_profile()
        result = ProfileMismatchDetector.compare(
            profile=profile,
            submitted_name="  James Whitfield  ",
            submitted_address="84 Pinecrest Drive, Austin, TX 78701",
        )
        assert result.has_mismatches is False

    def test_case_insensitive_address_match_is_clean(self) -> None:
        profile = _us_profile()
        result = ProfileMismatchDetector.compare(
            profile=profile,
            submitted_name="James Whitfield",
            submitted_address="84 pinecrest drive, austin, tx 78701",
        )
        assert result.has_mismatches is False

    def test_whitespace_trimmed_address_match_is_clean(self) -> None:
        profile = _us_profile()
        result = ProfileMismatchDetector.compare(
            profile=profile,
            submitted_name="James Whitfield",
            submitted_address="  84 Pinecrest Drive, Austin, TX 78701  ",
        )
        assert result.has_mismatches is False


# ===========================================================================
# Changed name → mismatch flagged
# ===========================================================================


class TestNameMismatch:
    """A changed name is flagged with a clear reason."""

    def setup_method(self) -> None:
        self.profile = _us_profile()

    def test_changed_name_has_mismatches(self) -> None:
        result = ProfileMismatchDetector.compare(
            profile=self.profile,
            submitted_name="James Whitfield Jr.",
            submitted_address="84 Pinecrest Drive, Austin, TX 78701",
        )
        assert result.has_mismatches is True

    def test_changed_name_yields_one_mismatch(self) -> None:
        result = ProfileMismatchDetector.compare(
            profile=self.profile,
            submitted_name="James Whitfield Jr.",
            submitted_address="84 Pinecrest Drive, Austin, TX 78701",
        )
        assert len(result.mismatches) == 1

    def test_changed_name_mismatch_field_is_name(self) -> None:
        result = ProfileMismatchDetector.compare(
            profile=self.profile,
            submitted_name="James Whitfield Jr.",
            submitted_address="84 Pinecrest Drive, Austin, TX 78701",
        )
        assert result.mismatches[0].field == "name"

    def test_changed_name_mismatch_contains_profile_value(self) -> None:
        result = ProfileMismatchDetector.compare(
            profile=self.profile,
            submitted_name="James Whitfield Jr.",
            submitted_address="84 Pinecrest Drive, Austin, TX 78701",
        )
        assert result.mismatches[0].profile_value == "James Whitfield"

    def test_changed_name_mismatch_contains_submitted_value(self) -> None:
        result = ProfileMismatchDetector.compare(
            profile=self.profile,
            submitted_name="James Whitfield Jr.",
            submitted_address="84 Pinecrest Drive, Austin, TX 78701",
        )
        assert result.mismatches[0].submitted_value == "James Whitfield Jr."

    def test_changed_name_reason_is_non_empty(self) -> None:
        result = ProfileMismatchDetector.compare(
            profile=self.profile,
            submitted_name="James Whitfield Jr.",
            submitted_address="84 Pinecrest Drive, Austin, TX 78701",
        )
        assert result.mismatches[0].reason != ""

    def test_changed_name_reason_mentions_name(self) -> None:
        result = ProfileMismatchDetector.compare(
            profile=self.profile,
            submitted_name="James Whitfield Jr.",
            submitted_address="84 Pinecrest Drive, Austin, TX 78701",
        )
        reason = result.mismatches[0].reason.lower()
        assert "name" in reason

    def test_changed_name_reason_mentions_both_values(self) -> None:
        result = ProfileMismatchDetector.compare(
            profile=self.profile,
            submitted_name="James Whitfield Jr.",
            submitted_address="84 Pinecrest Drive, Austin, TX 78701",
        )
        reason = result.mismatches[0].reason
        assert "James Whitfield" in reason
        assert "James Whitfield Jr." in reason

    def test_mismatch_detail_is_correct_type(self) -> None:
        result = ProfileMismatchDetector.compare(
            profile=self.profile,
            submitted_name="James Whitfield Jr.",
            submitted_address="84 Pinecrest Drive, Austin, TX 78701",
        )
        assert isinstance(result.mismatches[0], MismatchDetail)


# ===========================================================================
# Changed address → mismatch flagged
# ===========================================================================


class TestAddressMismatch:
    """A changed address is flagged with a clear reason."""

    def setup_method(self) -> None:
        self.profile = _us_profile()

    def test_changed_address_has_mismatches(self) -> None:
        result = ProfileMismatchDetector.compare(
            profile=self.profile,
            submitted_name="James Whitfield",
            submitted_address="99 New Street, Austin, TX 78702",
        )
        assert result.has_mismatches is True

    def test_changed_address_yields_one_mismatch(self) -> None:
        result = ProfileMismatchDetector.compare(
            profile=self.profile,
            submitted_name="James Whitfield",
            submitted_address="99 New Street, Austin, TX 78702",
        )
        assert len(result.mismatches) == 1

    def test_changed_address_mismatch_field_is_address(self) -> None:
        result = ProfileMismatchDetector.compare(
            profile=self.profile,
            submitted_name="James Whitfield",
            submitted_address="99 New Street, Austin, TX 78702",
        )
        assert result.mismatches[0].field == "address"

    def test_changed_address_mismatch_contains_profile_value(self) -> None:
        result = ProfileMismatchDetector.compare(
            profile=self.profile,
            submitted_name="James Whitfield",
            submitted_address="99 New Street, Austin, TX 78702",
        )
        assert result.mismatches[0].profile_value == "84 Pinecrest Drive, Austin, TX 78701"

    def test_changed_address_mismatch_contains_submitted_value(self) -> None:
        result = ProfileMismatchDetector.compare(
            profile=self.profile,
            submitted_name="James Whitfield",
            submitted_address="99 New Street, Austin, TX 78702",
        )
        assert result.mismatches[0].submitted_value == "99 New Street, Austin, TX 78702"

    def test_changed_address_reason_is_non_empty(self) -> None:
        result = ProfileMismatchDetector.compare(
            profile=self.profile,
            submitted_name="James Whitfield",
            submitted_address="99 New Street, Austin, TX 78702",
        )
        assert result.mismatches[0].reason != ""

    def test_changed_address_reason_mentions_address(self) -> None:
        result = ProfileMismatchDetector.compare(
            profile=self.profile,
            submitted_name="James Whitfield",
            submitted_address="99 New Street, Austin, TX 78702",
        )
        reason = result.mismatches[0].reason.lower()
        assert "address" in reason

    def test_changed_address_reason_mentions_both_values(self) -> None:
        result = ProfileMismatchDetector.compare(
            profile=self.profile,
            submitted_name="James Whitfield",
            submitted_address="99 New Street, Austin, TX 78702",
        )
        reason = result.mismatches[0].reason
        assert "84 Pinecrest Drive" in reason
        assert "99 New Street" in reason


# ===========================================================================
# Both name and address changed → two mismatches
# ===========================================================================


class TestBothFieldsMismatched:
    def test_both_fields_changed_yields_two_mismatches(self) -> None:
        profile = _us_profile()
        result = ProfileMismatchDetector.compare(
            profile=profile,
            submitted_name="James Whitfield Jr.",
            submitted_address="99 New Street, Austin, TX 78702",
        )
        assert result.has_mismatches is True
        assert len(result.mismatches) == 2

    def test_both_fields_changed_fields_are_name_and_address(self) -> None:
        profile = _us_profile()
        result = ProfileMismatchDetector.compare(
            profile=profile,
            submitted_name="James Whitfield Jr.",
            submitted_address="99 New Street, Austin, TX 78702",
        )
        fields = {m.field for m in result.mismatches}
        assert fields == {"name", "address"}


# ===========================================================================
# None / empty submitted fields
# ===========================================================================


class TestNoneSubmittedFields:
    """Missing / None submitted fields are treated as absent and flagged when
    the stored profile holds a non-empty value."""

    def test_none_name_flags_mismatch(self) -> None:
        profile = _us_profile()
        result = ProfileMismatchDetector.compare(
            profile=profile,
            submitted_name=None,
            submitted_address="84 Pinecrest Drive, Austin, TX 78701",
        )
        assert result.has_mismatches is True

    def test_none_name_mismatch_submitted_value_is_empty_string(self) -> None:
        profile = _us_profile()
        result = ProfileMismatchDetector.compare(
            profile=profile,
            submitted_name=None,
            submitted_address="84 Pinecrest Drive, Austin, TX 78701",
        )
        assert result.mismatches[0].submitted_value == ""

    def test_none_address_flags_mismatch(self) -> None:
        profile = _us_profile()
        result = ProfileMismatchDetector.compare(
            profile=profile,
            submitted_name="James Whitfield",
            submitted_address=None,
        )
        assert result.has_mismatches is True

    def test_empty_string_name_flags_mismatch(self) -> None:
        profile = _us_profile()
        result = ProfileMismatchDetector.compare(
            profile=profile,
            submitted_name="",
            submitted_address="84 Pinecrest Drive, Austin, TX 78701",
        )
        assert result.has_mismatches is True
