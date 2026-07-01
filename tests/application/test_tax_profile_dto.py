"""Unit tests for TaxProfileDTO and its supporting dataclasses / enumerations.

Verifies that:
  - All DTO classes instantiate correctly for representative scenarios.
  - Field defaults behave as documented.
  - Enum values match the allowed-values contract defined in
    docs/tax_profile_schema.md.
  - All four seeded investor personas can be expressed as valid TaxProfileDTO
    instances (schema completeness review).
  - ``withholding_rate`` derivation rules are correctly representable.

Seeded personas exercised
--------------------------
  1. James Whitfield     — US person, VERIFIED, W-9
  2. Mariana Costa Ribeiro — Foreign (Brazil), EXPIRED, W-8BEN, no treaty
  3. Robert Nguyen       — US person, PENDING, no form on file
  4. Ingrid Weber        — Foreign (Germany), VERIFIED, W-8BEN, treaty claimed
"""
from __future__ import annotations

from src.application.dto.tax_profile_dto import (
    FormCode,
    FormOnFileDTO,
    InvestorDTO,
    InvestorTypeValue,
    ProfileStatus,
    TaxProfileDTO,
    TaxResidencyDTO,
    TaxStatusSummaryDTO,
    TreatyClaimStatus,
    TreatyStatusDTO,
)


# ---------------------------------------------------------------------------
# Persona helpers — mirror the seeded investor profiles
# ---------------------------------------------------------------------------


def _whitfield_profile() -> TaxProfileDTO:
    """Persona 1: James Whitfield — US person, VERIFIED, W-9."""
    return TaxProfileDTO(
        investor=InvestorDTO(
            full_name="James Whitfield",
            address="84 Pinecrest Drive, Austin, TX 78701",
            investor_type=InvestorTypeValue.US_PERSON,
            country=None,
        ),
        tax_residency=TaxResidencyDTO(
            is_us_person=True,
            country_of_citizenship=None,
            foreign_tin=None,
            ftin_not_required=False,
        ),
        tax_status=TaxStatusSummaryDTO(
            current_status="VERIFIED",
            status_detail="",
        ),
        form_on_file=FormOnFileDTO(
            form_code=FormCode.W9,
            signed_date="2023-04-10",
            valid_through=None,
            is_expired=False,
        ),
        treaty_status=TreatyStatusDTO(
            claim_status=TreatyClaimStatus.NOT_APPLICABLE,
            has_treaty=False,
            treaty_country=None,
            applied_withholding_rate_pct=None,
        ),
        withholding_rate=None,
        status=ProfileStatus.READY,
        status_reason="",
    )


def _mariana_profile() -> TaxProfileDTO:
    """Persona 2: Mariana Costa Ribeiro — Foreign (Brazil), EXPIRED, W-8BEN."""
    return TaxProfileDTO(
        investor=InvestorDTO(
            full_name="Mariana Costa Ribeiro",
            address="Rua das Margaridas, 112, Rio de Janeiro, Brazil",
            investor_type=InvestorTypeValue.FOREIGN_PERSON,
            country="Brazil",
        ),
        tax_residency=TaxResidencyDTO(
            is_us_person=False,
            country_of_citizenship="Brazil",
            foreign_tin="987.654.321-00",
            ftin_not_required=False,
        ),
        tax_status=TaxStatusSummaryDTO(
            current_status="EXPIRED",
            status_detail="W-8BEN on file expired. A new form must be collected.",
        ),
        form_on_file=FormOnFileDTO(
            form_code=FormCode.W8BEN,
            signed_date="2021-03-15",
            valid_through="2024-12-31",
            is_expired=True,
        ),
        treaty_status=TreatyStatusDTO(
            claim_status=TreatyClaimStatus.NO_TREATY,
            has_treaty=False,
            treaty_country=None,
            applied_withholding_rate_pct=None,
        ),
        withholding_rate=30.0,
        status=ProfileStatus.REVIEW_REQUIRED,
        status_reason="W-8BEN expired on 2024-12-31. A new certification must be collected.",
    )


def _nguyen_profile() -> TaxProfileDTO:
    """Persona 3: Robert Nguyen — US person, PENDING, no form on file."""
    return TaxProfileDTO(
        investor=InvestorDTO(
            full_name="Robert Nguyen",
            address="910 Lakeview Terrace, Seattle, WA 98101",
            investor_type=InvestorTypeValue.US_PERSON,
            country=None,
        ),
        tax_residency=TaxResidencyDTO(
            is_us_person=True,
            country_of_citizenship=None,
            foreign_tin=None,
            ftin_not_required=False,
        ),
        tax_status=TaxStatusSummaryDTO(
            current_status="PENDING",
            status_detail="W-9 has been requested but not yet received.",
        ),
        form_on_file=None,
        treaty_status=TreatyStatusDTO(
            claim_status=TreatyClaimStatus.NOT_APPLICABLE,
            has_treaty=False,
            treaty_country=None,
            applied_withholding_rate_pct=None,
        ),
        withholding_rate=None,
        status=ProfileStatus.INCOMPLETE,
        status_reason="No W-9 on file. Investor must submit Form W-9 before onboarding can be completed.",
    )


def _weber_profile() -> TaxProfileDTO:
    """Persona 4: Ingrid Weber — Foreign (Germany), VERIFIED, W-8BEN, treaty claimed."""
    return TaxProfileDTO(
        investor=InvestorDTO(
            full_name="Ingrid Weber",
            address="Friedrichstraße 88, 10117 Berlin, Germany",
            investor_type=InvestorTypeValue.FOREIGN_PERSON,
            country="Germany",
        ),
        tax_residency=TaxResidencyDTO(
            is_us_person=False,
            country_of_citizenship="Germany",
            foreign_tin="DE123456789",
            ftin_not_required=False,
        ),
        tax_status=TaxStatusSummaryDTO(
            current_status="VERIFIED",
            status_detail="",
        ),
        form_on_file=FormOnFileDTO(
            form_code=FormCode.W8BEN,
            signed_date="2024-07-22",
            valid_through="2027-12-31",
            is_expired=False,
        ),
        treaty_status=TreatyStatusDTO(
            claim_status=TreatyClaimStatus.CLAIMED_AND_VALIDATED,
            has_treaty=True,
            treaty_country="Germany",
            applied_withholding_rate_pct=15.0,
        ),
        withholding_rate=15.0,
        status=ProfileStatus.READY,
        status_reason="",
    )


# ===========================================================================
# Enum contract
# ===========================================================================


class TestInvestorTypeValueEnum:
    """InvestorTypeValue must expose exactly the allowed values from the schema."""

    def test_us_person_value(self) -> None:
        assert InvestorTypeValue.US_PERSON.value == "us_person"

    def test_foreign_person_value(self) -> None:
        assert InvestorTypeValue.FOREIGN_PERSON.value == "foreign_person"

    def test_exactly_two_members(self) -> None:
        assert len(InvestorTypeValue) == 2


class TestFormCodeEnum:
    """FormCode must match the IRS form identifiers."""

    def test_w9_value(self) -> None:
        assert FormCode.W9.value == "W-9"

    def test_w8ben_value(self) -> None:
        assert FormCode.W8BEN.value == "W-8BEN"

    def test_exactly_two_members(self) -> None:
        assert len(FormCode) == 2


class TestTreatyClaimStatusEnum:
    """TreatyClaimStatus must expose the five documented values."""

    def test_not_applicable_value(self) -> None:
        assert TreatyClaimStatus.NOT_APPLICABLE.value == "NOT_APPLICABLE"

    def test_no_treaty_value(self) -> None:
        assert TreatyClaimStatus.NO_TREATY.value == "NO_TREATY"

    def test_claimed_and_validated_value(self) -> None:
        assert TreatyClaimStatus.CLAIMED_AND_VALIDATED.value == "CLAIMED_AND_VALIDATED"

    def test_treaty_available_claim_missing_value(self) -> None:
        assert TreatyClaimStatus.TREATY_AVAILABLE_CLAIM_MISSING.value == "TREATY_AVAILABLE_CLAIM_MISSING"

    def test_claim_incomplete_value(self) -> None:
        assert TreatyClaimStatus.CLAIM_INCOMPLETE.value == "CLAIM_INCOMPLETE"

    def test_exactly_five_members(self) -> None:
        assert len(TreatyClaimStatus) == 5


class TestProfileStatusEnum:
    """ProfileStatus must expose the three documented values."""

    def test_ready_value(self) -> None:
        assert ProfileStatus.READY.value == "READY"

    def test_review_required_value(self) -> None:
        assert ProfileStatus.REVIEW_REQUIRED.value == "REVIEW_REQUIRED"

    def test_incomplete_value(self) -> None:
        assert ProfileStatus.INCOMPLETE.value == "INCOMPLETE"

    def test_exactly_three_members(self) -> None:
        assert len(ProfileStatus) == 3


# ===========================================================================
# Sub-object instantiation and defaults
# ===========================================================================


class TestInvestorDTO:
    def test_required_fields_accepted(self) -> None:
        dto = InvestorDTO(
            full_name="Jane Doe",
            address="123 Main St",
            investor_type=InvestorTypeValue.US_PERSON,
        )
        assert dto.full_name == "Jane Doe"
        assert dto.address == "123 Main St"
        assert dto.investor_type == InvestorTypeValue.US_PERSON

    def test_country_defaults_to_none(self) -> None:
        dto = InvestorDTO(
            full_name="Jane Doe",
            address="123 Main St",
            investor_type=InvestorTypeValue.US_PERSON,
        )
        assert dto.country is None

    def test_country_can_be_set(self) -> None:
        dto = InvestorDTO(
            full_name="Hans Müller",
            address="Bahnhofstr. 1",
            investor_type=InvestorTypeValue.FOREIGN_PERSON,
            country="Germany",
        )
        assert dto.country == "Germany"


class TestTaxResidencyDTO:
    def test_defaults(self) -> None:
        dto = TaxResidencyDTO(is_us_person=True)
        assert dto.country_of_citizenship is None
        assert dto.foreign_tin is None
        assert dto.ftin_not_required is False

    def test_foreign_person_fields(self) -> None:
        dto = TaxResidencyDTO(
            is_us_person=False,
            country_of_citizenship="Brazil",
            foreign_tin="219.871.330-44",
        )
        assert dto.is_us_person is False
        assert dto.country_of_citizenship == "Brazil"
        assert dto.foreign_tin == "219.871.330-44"

    def test_ftin_not_required_flag(self) -> None:
        dto = TaxResidencyDTO(is_us_person=False, ftin_not_required=True)
        assert dto.ftin_not_required is True


class TestTaxStatusSummaryDTO:
    def test_verified_with_empty_detail(self) -> None:
        dto = TaxStatusSummaryDTO(current_status="VERIFIED")
        assert dto.current_status == "VERIFIED"
        assert dto.status_detail == ""

    def test_expired_with_detail(self) -> None:
        dto = TaxStatusSummaryDTO(
            current_status="EXPIRED",
            status_detail="Form expired 2024-12-31.",
        )
        assert dto.current_status == "EXPIRED"
        assert "expired" in dto.status_detail.lower()

    def test_all_allowed_status_values_are_storable(self) -> None:
        for status in ("PENDING", "VERIFIED", "EXPIRED", "MISSING"):
            dto = TaxStatusSummaryDTO(current_status=status)
            assert dto.current_status == status


class TestFormOnFileDTO:
    def test_w9_defaults(self) -> None:
        dto = FormOnFileDTO(form_code=FormCode.W9)
        assert dto.form_code == FormCode.W9
        assert dto.signed_date is None
        assert dto.valid_through is None
        assert dto.is_expired is False

    def test_w8ben_with_expiry(self) -> None:
        dto = FormOnFileDTO(
            form_code=FormCode.W8BEN,
            signed_date="2021-03-15",
            valid_through="2024-12-31",
            is_expired=True,
        )
        assert dto.form_code == FormCode.W8BEN
        assert dto.signed_date == "2021-03-15"
        assert dto.valid_through == "2024-12-31"
        assert dto.is_expired is True

    def test_valid_through_none_for_w9(self) -> None:
        """W-9 forms carry no automatic expiry date."""
        dto = FormOnFileDTO(
            form_code=FormCode.W9,
            signed_date="2023-04-10",
            valid_through=None,
        )
        assert dto.valid_through is None
        assert dto.is_expired is False


class TestTreatyStatusDTO:
    def test_defaults_represent_not_applicable(self) -> None:
        """Default TreatyStatusDTO represents the US-person 'not applicable' state."""
        dto = TreatyStatusDTO()
        assert dto.claim_status == TreatyClaimStatus.NOT_APPLICABLE
        assert dto.has_treaty is False
        assert dto.treaty_country is None
        assert dto.applied_withholding_rate_pct is None

    def test_no_treaty_country(self) -> None:
        dto = TreatyStatusDTO(
            claim_status=TreatyClaimStatus.NO_TREATY,
            has_treaty=False,
        )
        assert dto.claim_status == TreatyClaimStatus.NO_TREATY
        assert dto.has_treaty is False
        assert dto.applied_withholding_rate_pct is None

    def test_claimed_and_validated(self) -> None:
        dto = TreatyStatusDTO(
            claim_status=TreatyClaimStatus.CLAIMED_AND_VALIDATED,
            has_treaty=True,
            treaty_country="Germany",
            applied_withholding_rate_pct=15.0,
        )
        assert dto.claim_status == TreatyClaimStatus.CLAIMED_AND_VALIDATED
        assert dto.has_treaty is True
        assert dto.treaty_country == "Germany"
        assert dto.applied_withholding_rate_pct == 15.0

    def test_treaty_available_claim_missing(self) -> None:
        dto = TreatyStatusDTO(
            claim_status=TreatyClaimStatus.TREATY_AVAILABLE_CLAIM_MISSING,
            has_treaty=True,
            treaty_country=None,
            applied_withholding_rate_pct=None,
        )
        assert dto.claim_status == TreatyClaimStatus.TREATY_AVAILABLE_CLAIM_MISSING
        assert dto.applied_withholding_rate_pct is None

    def test_claim_incomplete(self) -> None:
        dto = TreatyStatusDTO(
            claim_status=TreatyClaimStatus.CLAIM_INCOMPLETE,
            has_treaty=True,
        )
        assert dto.claim_status == TreatyClaimStatus.CLAIM_INCOMPLETE


# ===========================================================================
# Top-level TaxProfileDTO — instantiation
# ===========================================================================


class TestTaxProfileDTOInstantiation:
    def test_returns_correct_type(self) -> None:
        assert isinstance(_whitfield_profile(), TaxProfileDTO)

    def test_all_persona_profiles_instantiate_without_error(self) -> None:
        """All four seeded personas must be expressible as TaxProfileDTO."""
        for profile in (
            _whitfield_profile(),
            _mariana_profile(),
            _nguyen_profile(),
            _weber_profile(),
        ):
            assert isinstance(profile, TaxProfileDTO)

    def test_status_reason_defaults_to_empty_string(self) -> None:
        """status_reason has a default of empty string."""
        profile = TaxProfileDTO(
            investor=InvestorDTO(
                full_name="Test User",
                address="1 Test St",
                investor_type=InvestorTypeValue.US_PERSON,
            ),
            tax_residency=TaxResidencyDTO(is_us_person=True),
            tax_status=TaxStatusSummaryDTO(current_status="VERIFIED"),
            form_on_file=None,
            treaty_status=TreatyStatusDTO(),
            withholding_rate=None,
            status=ProfileStatus.READY,
        )
        assert profile.status_reason == ""


# ===========================================================================
# Seeded persona — field-level assertions
# ===========================================================================


class TestJamesWhitfieldPersona:
    """Persona 1: US person, VERIFIED, W-9."""

    def setup_method(self) -> None:
        self.profile = _whitfield_profile()

    def test_investor_type_is_us_person(self) -> None:
        assert self.profile.investor.investor_type == InvestorTypeValue.US_PERSON

    def test_is_us_person_flag_is_true(self) -> None:
        assert self.profile.tax_residency.is_us_person is True

    def test_country_of_citizenship_is_none(self) -> None:
        assert self.profile.tax_residency.country_of_citizenship is None

    def test_foreign_tin_is_none(self) -> None:
        assert self.profile.tax_residency.foreign_tin is None

    def test_tax_status_is_verified(self) -> None:
        assert self.profile.tax_status.current_status == "VERIFIED"

    def test_form_on_file_is_w9(self) -> None:
        assert self.profile.form_on_file is not None
        assert self.profile.form_on_file.form_code == FormCode.W9

    def test_w9_valid_through_is_none(self) -> None:
        assert self.profile.form_on_file is not None
        assert self.profile.form_on_file.valid_through is None

    def test_w9_is_not_expired(self) -> None:
        assert self.profile.form_on_file is not None
        assert self.profile.form_on_file.is_expired is False

    def test_treaty_claim_status_is_not_applicable(self) -> None:
        assert self.profile.treaty_status.claim_status == TreatyClaimStatus.NOT_APPLICABLE

    def test_withholding_rate_is_none_for_us_person(self) -> None:
        assert self.profile.withholding_rate is None

    def test_overall_status_is_ready(self) -> None:
        assert self.profile.status == ProfileStatus.READY

    def test_status_reason_is_empty_when_ready(self) -> None:
        assert self.profile.status_reason == ""


class TestMarianaCostaPRibeiroPersona:
    """Persona 2: Foreign (Brazil), EXPIRED, W-8BEN, no treaty."""

    def setup_method(self) -> None:
        self.profile = _mariana_profile()

    def test_investor_type_is_foreign_person(self) -> None:
        assert self.profile.investor.investor_type == InvestorTypeValue.FOREIGN_PERSON

    def test_is_us_person_flag_is_false(self) -> None:
        assert self.profile.tax_residency.is_us_person is False

    def test_country_of_citizenship_is_brazil(self) -> None:
        assert self.profile.tax_residency.country_of_citizenship == "Brazil"

    def test_foreign_tin_is_set(self) -> None:
        assert self.profile.tax_residency.foreign_tin == "987.654.321-00"

    def test_tax_status_is_expired(self) -> None:
        assert self.profile.tax_status.current_status == "EXPIRED"

    def test_form_on_file_is_w8ben(self) -> None:
        assert self.profile.form_on_file is not None
        assert self.profile.form_on_file.form_code == FormCode.W8BEN

    def test_form_is_expired(self) -> None:
        assert self.profile.form_on_file is not None
        assert self.profile.form_on_file.is_expired is True

    def test_valid_through_set(self) -> None:
        assert self.profile.form_on_file is not None
        assert self.profile.form_on_file.valid_through == "2024-12-31"

    def test_treaty_claim_status_is_no_treaty(self) -> None:
        assert self.profile.treaty_status.claim_status == TreatyClaimStatus.NO_TREATY

    def test_has_treaty_is_false_for_brazil(self) -> None:
        assert self.profile.treaty_status.has_treaty is False

    def test_withholding_rate_is_30_pct(self) -> None:
        """Statutory NRA rate applies when no treaty."""
        assert self.profile.withholding_rate == 30.0

    def test_overall_status_is_review_required(self) -> None:
        assert self.profile.status == ProfileStatus.REVIEW_REQUIRED

    def test_status_reason_is_non_empty(self) -> None:
        assert self.profile.status_reason != ""


class TestRobertNguyenPersona:
    """Persona 3: US person, PENDING, no form on file."""

    def setup_method(self) -> None:
        self.profile = _nguyen_profile()

    def test_investor_type_is_us_person(self) -> None:
        assert self.profile.investor.investor_type == InvestorTypeValue.US_PERSON

    def test_tax_status_is_pending(self) -> None:
        assert self.profile.tax_status.current_status == "PENDING"

    def test_form_on_file_is_none(self) -> None:
        """No form submitted yet."""
        assert self.profile.form_on_file is None

    def test_treaty_claim_is_not_applicable(self) -> None:
        assert self.profile.treaty_status.claim_status == TreatyClaimStatus.NOT_APPLICABLE

    def test_withholding_rate_is_none(self) -> None:
        assert self.profile.withholding_rate is None

    def test_overall_status_is_incomplete(self) -> None:
        assert self.profile.status == ProfileStatus.INCOMPLETE

    def test_status_reason_is_non_empty(self) -> None:
        assert self.profile.status_reason != ""


class TestIngridWeberPersona:
    """Persona 4: Foreign (Germany), VERIFIED, W-8BEN, treaty claimed."""

    def setup_method(self) -> None:
        self.profile = _weber_profile()

    def test_investor_type_is_foreign_person(self) -> None:
        assert self.profile.investor.investor_type == InvestorTypeValue.FOREIGN_PERSON

    def test_country_is_germany(self) -> None:
        assert self.profile.investor.country == "Germany"

    def test_country_of_citizenship_is_germany(self) -> None:
        assert self.profile.tax_residency.country_of_citizenship == "Germany"

    def test_foreign_tin_is_set(self) -> None:
        assert self.profile.tax_residency.foreign_tin == "DE123456789"

    def test_tax_status_is_verified(self) -> None:
        assert self.profile.tax_status.current_status == "VERIFIED"

    def test_form_on_file_is_w8ben(self) -> None:
        assert self.profile.form_on_file is not None
        assert self.profile.form_on_file.form_code == FormCode.W8BEN

    def test_form_is_not_expired(self) -> None:
        assert self.profile.form_on_file is not None
        assert self.profile.form_on_file.is_expired is False

    def test_valid_through_is_set(self) -> None:
        assert self.profile.form_on_file is not None
        assert self.profile.form_on_file.valid_through == "2027-12-31"

    def test_treaty_claim_is_claimed_and_validated(self) -> None:
        assert self.profile.treaty_status.claim_status == TreatyClaimStatus.CLAIMED_AND_VALIDATED

    def test_has_treaty_is_true(self) -> None:
        assert self.profile.treaty_status.has_treaty is True

    def test_treaty_country_is_germany(self) -> None:
        assert self.profile.treaty_status.treaty_country == "Germany"

    def test_applied_withholding_rate_is_15_pct(self) -> None:
        assert self.profile.treaty_status.applied_withholding_rate_pct == 15.0

    def test_top_level_withholding_rate_is_15_pct(self) -> None:
        """withholding_rate at the top level reflects the treaty-reduced rate."""
        assert self.profile.withholding_rate == 15.0

    def test_overall_status_is_ready(self) -> None:
        assert self.profile.status == ProfileStatus.READY

    def test_status_reason_is_empty_when_ready(self) -> None:
        assert self.profile.status_reason == ""


# ===========================================================================
# withholding_rate derivation rules
# ===========================================================================


class TestWithholdingRateDerivationRules:
    """Schema contract: withholding_rate semantics per investor type."""

    def test_us_person_withholding_rate_is_none(self) -> None:
        """US persons: withholding_rate is None (W-9 backup withholding governs)."""
        profile = _whitfield_profile()
        assert profile.withholding_rate is None

    def test_foreign_no_treaty_statutory_30_pct(self) -> None:
        """Foreign investor from non-treaty country → 30 % statutory rate."""
        profile = _mariana_profile()
        assert profile.withholding_rate == 30.0

    def test_foreign_treaty_validated_reduced_rate(self) -> None:
        """Foreign investor with validated treaty claim → reduced rate."""
        profile = _weber_profile()
        assert profile.withholding_rate == 15.0

    def test_foreign_treaty_available_but_claim_missing_statutory_rate(self) -> None:
        """Treaty available but Part II not completed → statutory 30 % until claim validated."""
        profile = TaxProfileDTO(
            investor=InvestorDTO(
                full_name="Klaus Fischer",
                address="Hauptstraße 5, Berlin",
                investor_type=InvestorTypeValue.FOREIGN_PERSON,
                country="Germany",
            ),
            tax_residency=TaxResidencyDTO(
                is_us_person=False,
                country_of_citizenship="Germany",
            ),
            tax_status=TaxStatusSummaryDTO(current_status="PENDING"),
            form_on_file=FormOnFileDTO(
                form_code=FormCode.W8BEN,
                signed_date="2024-01-15",
                valid_through="2027-12-31",
            ),
            treaty_status=TreatyStatusDTO(
                claim_status=TreatyClaimStatus.TREATY_AVAILABLE_CLAIM_MISSING,
                has_treaty=True,
                treaty_country=None,
                applied_withholding_rate_pct=None,
            ),
            withholding_rate=30.0,  # statutory until claim validated
            status=ProfileStatus.REVIEW_REQUIRED,
            status_reason="Part II (treaty claim) is blank for a treaty country.",
        )
        assert profile.withholding_rate == 30.0
        assert profile.treaty_status.claim_status == TreatyClaimStatus.TREATY_AVAILABLE_CLAIM_MISSING


# ===========================================================================
# ProfileStatus rules
# ===========================================================================


class TestProfileStatusRules:
    def test_ready_status_requires_empty_reason(self) -> None:
        """READY status is always paired with an empty status_reason."""
        profile = _whitfield_profile()
        assert profile.status == ProfileStatus.READY
        assert profile.status_reason == ""

    def test_review_required_has_non_empty_reason(self) -> None:
        """REVIEW_REQUIRED must carry a non-empty status_reason."""
        profile = _mariana_profile()
        assert profile.status == ProfileStatus.REVIEW_REQUIRED
        assert profile.status_reason != ""

    def test_incomplete_has_non_empty_reason(self) -> None:
        """INCOMPLETE must carry a non-empty status_reason."""
        profile = _nguyen_profile()
        assert profile.status == ProfileStatus.INCOMPLETE
        assert profile.status_reason != ""
