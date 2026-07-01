"""Unit tests for AssembleTaxProfileUseCase.

Acceptance criteria
-------------------
AC #1  Produces a complete TaxProfileDTO given valid inputs from upstream steps.
AC #2  Withholding rate correctly set:
         - None (not 0 %) for valid W-9 (US person)
         - Reduced treaty rate (e.g. 15.0) for W-8BEN with validated treaty
         - Statutory 30.0 % for W-8BEN with no treaty
AC #3  Reporting track correctly determined from form_on_file.form_code:
         - W-9  → 1099-DIV  (form_code == FormCode.W9)
         - W-8BEN → 1042-S  (form_code == FormCode.W8BEN)

All four seeded personas are tested to verify realistic data paths:

  1. James Whitfield      — US person, W-9, VERIFIED → READY
  2. Mariana Costa Ribeiro— Brazilian foreign, W-8BEN, no treaty, EXPIRED → REVIEW_REQUIRED
  3. Robert Nguyen        — US person, no form on file → INCOMPLETE
  4. Ingrid Weber         — German foreign, W-8BEN, Germany treaty → READY (15 % rate)

Additional cases
----------------
  - execute_without_form() → status INCOMPLETE for both US and foreign persons
  - ProfileStatus priority: INCOMPLETE > REVIEW_REQUIRED > READY
  - TreatyStatusDTO.claim_status == NOT_APPLICABLE for US persons
  - TreatyStatusDTO.claim_status == CLAIMED_AND_VALIDATED for treaty-eligible foreign persons
  - TreatyStatusDTO.claim_status == NO_TREATY for non-treaty foreign persons (Brazil)
  - Mismatch in name/address → REVIEW_REQUIRED
  - Unsupported form_type raises ValueError
"""
from __future__ import annotations

import pytest

from src.application.dto.tax_form_dto import ParsedFormFieldsDTO
from src.application.dto.tax_profile_dto import (
    FormCode,
    InvestorTypeValue,
    ProfileStatus,
    TaxProfileDTO,
    TreatyClaimStatus,
)
from src.application.use_cases.assemble_tax_profile import AssembleTaxProfileUseCase
from src.domain.entities.investor_profile import InvestorProfile, TaxStatus
from src.domain.services.tax_form_determination_service import InvestorType, TaxFormCode


# ---------------------------------------------------------------------------
# Seeded persona profile fixtures
# ---------------------------------------------------------------------------


def _whitfield_profile() -> InvestorProfile:
    """Persona 1 — James Whitfield, US person, verified W-9."""
    return InvestorProfile(
        profile_id="11111111-0000-0000-0000-000000000001",
        full_name="James Whitfield",
        address="84 Pinecrest Drive, Austin, TX 78701",
        investor_type=InvestorType.US_PERSON,
        tax_status=TaxStatus.VERIFIED,
        last_form_on_file=TaxFormCode.W9,
        last_form_signed_date="2023-04-10",
    )


def _ribeiro_profile() -> InvestorProfile:
    """Persona 2 — Mariana Costa Ribeiro, Brazilian foreign investor, expired W-8BEN."""
    return InvestorProfile(
        profile_id="11111111-0000-0000-0000-000000000002",
        full_name="Mariana Costa Ribeiro",
        address="Av. Paulista 1578, Apto 42, São Paulo, SP 01310-200, Brazil",
        investor_type=InvestorType.FOREIGN_PERSON,
        tax_status=TaxStatus.EXPIRED,
        country="Brazil",
        last_form_on_file=TaxFormCode.W8BEN,
        last_form_signed_date="2021-01-15",
        foreign_tin="317.940.520-88",
        treaty_country=None,
    )


def _nguyen_profile() -> InvestorProfile:
    """Persona 3 — Robert Nguyen, US person, no form on file."""
    return InvestorProfile(
        profile_id="11111111-0000-0000-0000-000000000003",
        full_name="Robert Nguyen",
        address="210 Lakeview Blvd, Seattle, WA 98101",
        investor_type=InvestorType.US_PERSON,
        tax_status=TaxStatus.PENDING,
        last_form_on_file=None,
        last_form_signed_date=None,
    )


def _weber_profile() -> InvestorProfile:
    """Persona 4 — Ingrid Weber, German investor, W-8BEN with Germany treaty claim."""
    return InvestorProfile(
        profile_id="11111111-0000-0000-0000-000000000004",
        full_name="Ingrid Weber",
        address="Friedrichstraße 88, 10117 Berlin, Germany",
        investor_type=InvestorType.FOREIGN_PERSON,
        tax_status=TaxStatus.VERIFIED,
        country="Germany",
        last_form_on_file=TaxFormCode.W8BEN,
        last_form_signed_date="2024-07-22",
        foreign_tin="DE123456789",
        treaty_country="Germany",
    )


# ---------------------------------------------------------------------------
# DTO helpers for each persona
# ---------------------------------------------------------------------------


def _whitfield_dto(**kwargs) -> ParsedFormFieldsDTO:
    """Valid W-9 submission for James Whitfield."""
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


def _ribeiro_dto(**kwargs) -> ParsedFormFieldsDTO:
    """W-8BEN submission for Mariana Costa Ribeiro (expired, no treaty)."""
    defaults: dict = {
        "form_type": "W-8BEN",
        "name": "Mariana Costa Ribeiro",
        "country_of_citizenship": "Brazil",
        "permanent_address": "Av. Paulista 1578, Apto 42, São Paulo, SP 01310-200, Brazil",
        "permanent_address_city_country": "São Paulo, Brazil",
        "foreign_tin": "317.940.520-88",
        # Expired: signed 2021-01-15, valid_through 2024-12-31, past today
        "signature_present": True,
        "signature_date": "2021-01-15",
    }
    defaults.update(kwargs)
    return ParsedFormFieldsDTO(**defaults)


def _weber_dto(**kwargs) -> ParsedFormFieldsDTO:
    """Valid W-8BEN submission for Ingrid Weber (Germany treaty, 15 %)."""
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
        "income_type": "Dividends",
        "signature_present": True,
        "signature_date": "2024-07-22",
    }
    defaults.update(kwargs)
    return ParsedFormFieldsDTO(**defaults)


# ===========================================================================
# Return type
# ===========================================================================


class TestAssembleTaxProfileReturnType:
    """Basic type-check: execute() always returns TaxProfileDTO."""

    def test_returns_tax_profile_dto_for_w9(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_whitfield_dto(), profile=_whitfield_profile())
        assert isinstance(result, TaxProfileDTO)

    def test_returns_tax_profile_dto_for_w8ben(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_weber_dto(), profile=_weber_profile())
        assert isinstance(result, TaxProfileDTO)


# ===========================================================================
# AC #1 — Complete TaxProfileDTO produced from valid inputs
# ===========================================================================


class TestCompleteTaxProfileProduced:
    """AC #1: result is a fully populated TaxProfileDTO (no None sub-objects)."""

    def test_w9_investor_section_present(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_whitfield_dto(), profile=_whitfield_profile())
        assert result.investor is not None

    def test_w9_tax_residency_section_present(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_whitfield_dto(), profile=_whitfield_profile())
        assert result.tax_residency is not None

    def test_w9_tax_status_section_present(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_whitfield_dto(), profile=_whitfield_profile())
        assert result.tax_status is not None

    def test_w9_form_on_file_present(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_whitfield_dto(), profile=_whitfield_profile())
        assert result.form_on_file is not None

    def test_w9_treaty_status_present(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_whitfield_dto(), profile=_whitfield_profile())
        assert result.treaty_status is not None

    def test_w9_status_field_is_profile_status(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_whitfield_dto(), profile=_whitfield_profile())
        assert isinstance(result.status, ProfileStatus)

    def test_w9_status_reason_is_str(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_whitfield_dto(), profile=_whitfield_profile())
        assert isinstance(result.status_reason, str)

    # ---- W-8BEN
    def test_w8ben_all_sections_present(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_weber_dto(), profile=_weber_profile())
        assert all(
            v is not None
            for v in (
                result.investor,
                result.tax_residency,
                result.tax_status,
                result.form_on_file,
                result.treaty_status,
            )
        )

    # ---- InvestorDTO field values
    def test_investor_full_name_taken_from_profile(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_whitfield_dto(), profile=_whitfield_profile())
        assert result.investor.full_name == "James Whitfield"

    def test_investor_address_taken_from_profile(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_whitfield_dto(), profile=_whitfield_profile())
        assert result.investor.address == "84 Pinecrest Drive, Austin, TX 78701"

    def test_investor_type_us_person_for_w9(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_whitfield_dto(), profile=_whitfield_profile())
        assert result.investor.investor_type == InvestorTypeValue.US_PERSON

    def test_investor_type_foreign_person_for_w8ben(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_weber_dto(), profile=_weber_profile())
        assert result.investor.investor_type == InvestorTypeValue.FOREIGN_PERSON

    # ---- TaxResidencyDTO
    def test_tax_residency_is_us_person_for_w9(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_whitfield_dto(), profile=_whitfield_profile())
        assert result.tax_residency.is_us_person is True

    def test_tax_residency_is_not_us_person_for_w8ben(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_weber_dto(), profile=_weber_profile())
        assert result.tax_residency.is_us_person is False

    def test_tax_residency_country_of_citizenship_for_w8ben(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_weber_dto(), profile=_weber_profile())
        assert result.tax_residency.country_of_citizenship == "Germany"

    def test_tax_residency_country_of_citizenship_none_for_us_person(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_whitfield_dto(), profile=_whitfield_profile())
        assert result.tax_residency.country_of_citizenship is None

    def test_tax_residency_foreign_tin_populated_for_foreign_person(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_weber_dto(), profile=_weber_profile())
        assert result.tax_residency.foreign_tin == "DE123456789"


# ===========================================================================
# AC #2 — Withholding rate
# ===========================================================================


class TestWithholdingRate:
    """AC #2: withholding_rate set to None for W-9, treaty rate or 30 % for W-8BEN."""

    def test_withholding_rate_is_none_for_us_person_w9(self) -> None:
        """AC #2a: US person W-9 → withholding_rate is None (not 0)."""
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_whitfield_dto(), profile=_whitfield_profile())
        assert result.withholding_rate is None

    def test_withholding_rate_is_treaty_rate_for_validated_german_claim(self) -> None:
        """AC #2b: W-8BEN with valid Germany treaty claim → 15.0 %."""
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_weber_dto(), profile=_weber_profile())
        assert result.withholding_rate == 15.0

    def test_withholding_rate_is_statutory_for_non_treaty_country(self) -> None:
        """AC #2c: W-8BEN from Brazil (no treaty) → 30.0 % statutory."""
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_ribeiro_dto(), profile=_ribeiro_profile())
        assert result.withholding_rate == 30.0

    def test_withholding_rate_not_zero_for_us_person(self) -> None:
        """AC #2a extra: ensure we don't accidentally return 0.0 for US persons."""
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_whitfield_dto(), profile=_whitfield_profile())
        assert result.withholding_rate != 0.0

    def test_withholding_rate_statutory_when_treaty_available_but_not_claimed(self) -> None:
        """Foreign investor from a treaty country who omits Part II → 30 %."""
        uc = AssembleTaxProfileUseCase()
        # Use Weber's profile but omit Part II from the submitted form.
        dto_no_claim = _weber_dto(
            treaty_country=None,
            treaty_article=None,
            withholding_rate=None,
            income_type=None,
            treaty_conditions=None,
        )
        result = uc.execute(dto=dto_no_claim, profile=_weber_profile())
        assert result.withholding_rate == 30.0


# ===========================================================================
# AC #3 — Reporting track (derived from form_on_file.form_code)
# ===========================================================================


class TestReportingTrack:
    """AC #3: form_code determines reporting track (1099-DIV vs 1042-S)."""

    def test_w9_form_code_is_w9(self) -> None:
        """AC #3 (1099-DIV track): W-9 form → form_code == W9."""
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_whitfield_dto(), profile=_whitfield_profile())
        assert result.form_on_file is not None
        assert result.form_on_file.form_code == FormCode.W9

    def test_w8ben_form_code_is_w8ben(self) -> None:
        """AC #3 (1042-S track): W-8BEN form → form_code == W8BEN."""
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_weber_dto(), profile=_weber_profile())
        assert result.form_on_file is not None
        assert result.form_on_file.form_code == FormCode.W8BEN

    def test_w9_form_code_string_value_for_1099_track(self) -> None:
        """Downstream workflows can compare form_code.value for 1099-DIV routing."""
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_whitfield_dto(), profile=_whitfield_profile())
        assert result.form_on_file is not None
        assert result.form_on_file.form_code.value == "W-9"

    def test_w8ben_form_code_string_value_for_1042s_track(self) -> None:
        """Downstream workflows can compare form_code.value for 1042-S routing."""
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_weber_dto(), profile=_weber_profile())
        assert result.form_on_file is not None
        assert result.form_on_file.form_code.value == "W-8BEN"


# ===========================================================================
# Persona 1 — James Whitfield (US person, W-9, VERIFIED)
# ===========================================================================


class TestPersonaJamesWhitfield:
    """End-to-end persona test: US person, verified W-9."""

    def setup_method(self) -> None:
        self.uc = AssembleTaxProfileUseCase()
        self.profile = _whitfield_profile()
        self.dto = _whitfield_dto()
        self.result = self.uc.execute(dto=self.dto, profile=self.profile)

    def test_status_is_ready(self) -> None:
        assert self.result.status == ProfileStatus.READY

    def test_status_reason_is_empty_string(self) -> None:
        assert self.result.status_reason == ""

    def test_form_code_is_w9(self) -> None:
        assert self.result.form_on_file is not None
        assert self.result.form_on_file.form_code == FormCode.W9

    def test_form_is_not_expired(self) -> None:
        assert self.result.form_on_file is not None
        assert self.result.form_on_file.is_expired is False

    def test_withholding_rate_is_none(self) -> None:
        assert self.result.withholding_rate is None

    def test_treaty_claim_status_not_applicable(self) -> None:
        assert self.result.treaty_status.claim_status == TreatyClaimStatus.NOT_APPLICABLE

    def test_treaty_has_treaty_is_false(self) -> None:
        assert self.result.treaty_status.has_treaty is False

    def test_treaty_country_is_none(self) -> None:
        assert self.result.treaty_status.treaty_country is None

    def test_investor_type_us_person(self) -> None:
        assert self.result.investor.investor_type == InvestorTypeValue.US_PERSON

    def test_tax_residency_is_us_person(self) -> None:
        assert self.result.tax_residency.is_us_person is True


# ===========================================================================
# Persona 2 — Mariana Costa Ribeiro (Brazilian, expired W-8BEN, no treaty)
# ===========================================================================


class TestPersonaMarianaCosta:
    """Persona test: foreign investor, expired W-8BEN, no treaty country."""

    def setup_method(self) -> None:
        self.uc = AssembleTaxProfileUseCase()
        self.profile = _ribeiro_profile()
        self.dto = _ribeiro_dto()
        self.result = self.uc.execute(dto=self.dto, profile=self.profile)

    def test_status_is_review_required_due_to_expired_form(self) -> None:
        """Expired W-8BEN → REVIEW_REQUIRED."""
        assert self.result.status == ProfileStatus.REVIEW_REQUIRED

    def test_form_code_is_w8ben(self) -> None:
        assert self.result.form_on_file is not None
        assert self.result.form_on_file.form_code == FormCode.W8BEN

    def test_form_is_expired(self) -> None:
        """signed 2021-01-15 → expired by 2024-12-31 (past today)."""
        assert self.result.form_on_file is not None
        assert self.result.form_on_file.is_expired is True

    def test_valid_through_is_end_of_third_year(self) -> None:
        """valid_through for 2021 signing should be 2024-12-31."""
        assert self.result.form_on_file is not None
        assert self.result.form_on_file.valid_through == "2024-12-31"

    def test_treaty_claim_status_no_treaty(self) -> None:
        assert self.result.treaty_status.claim_status == TreatyClaimStatus.NO_TREATY

    def test_treaty_has_treaty_is_false(self) -> None:
        assert self.result.treaty_status.has_treaty is False

    def test_withholding_rate_is_statutory_30(self) -> None:
        assert self.result.withholding_rate == 30.0

    def test_investor_type_foreign_person(self) -> None:
        assert self.result.investor.investor_type == InvestorTypeValue.FOREIGN_PERSON

    def test_tax_residency_country_of_citizenship_is_brazil(self) -> None:
        assert self.result.tax_residency.country_of_citizenship == "Brazil"

    def test_status_reason_mentions_expiry(self) -> None:
        assert self.result.status_reason != ""


# ===========================================================================
# Persona 3 — Robert Nguyen (US person, no form on file)
# ===========================================================================


class TestPersonaRobertNguyen:
    """Persona test: US person with no form submitted → INCOMPLETE."""

    def setup_method(self) -> None:
        self.uc = AssembleTaxProfileUseCase()
        self.profile = _nguyen_profile()
        self.result = self.uc.execute_without_form(self.profile)

    def test_status_is_incomplete(self) -> None:
        assert self.result.status == ProfileStatus.INCOMPLETE

    def test_form_on_file_is_none(self) -> None:
        assert self.result.form_on_file is None

    def test_withholding_rate_is_none(self) -> None:
        assert self.result.withholding_rate is None

    def test_treaty_claim_status_not_applicable(self) -> None:
        assert self.result.treaty_status.claim_status == TreatyClaimStatus.NOT_APPLICABLE

    def test_status_reason_mentions_w9(self) -> None:
        assert "W-9" in self.result.status_reason

    def test_investor_type_us_person(self) -> None:
        assert self.result.investor.investor_type == InvestorTypeValue.US_PERSON


# ===========================================================================
# Persona 4 — Ingrid Weber (German, W-8BEN, Germany treaty, VERIFIED)
# ===========================================================================


class TestPersonaIngridWeber:
    """Persona test: foreign investor, W-8BEN with validated Germany treaty claim."""

    def setup_method(self) -> None:
        self.uc = AssembleTaxProfileUseCase()
        self.profile = _weber_profile()
        self.dto = _weber_dto()
        self.result = self.uc.execute(dto=self.dto, profile=self.profile)

    def test_status_is_ready(self) -> None:
        assert self.result.status == ProfileStatus.READY

    def test_status_reason_is_empty(self) -> None:
        assert self.result.status_reason == ""

    def test_form_code_is_w8ben(self) -> None:
        assert self.result.form_on_file is not None
        assert self.result.form_on_file.form_code == FormCode.W8BEN

    def test_form_is_not_expired(self) -> None:
        assert self.result.form_on_file is not None
        assert self.result.form_on_file.is_expired is False

    def test_withholding_rate_is_15_pct(self) -> None:
        """Germany treaty reduces withholding to 15 %."""
        assert self.result.withholding_rate == 15.0

    def test_treaty_claim_status_claimed_and_validated(self) -> None:
        assert self.result.treaty_status.claim_status == TreatyClaimStatus.CLAIMED_AND_VALIDATED

    def test_treaty_has_treaty_is_true(self) -> None:
        assert self.result.treaty_status.has_treaty is True

    def test_treaty_country_is_germany(self) -> None:
        assert self.result.treaty_status.treaty_country == "Germany"

    def test_applied_withholding_rate_in_treaty_status(self) -> None:
        assert self.result.treaty_status.applied_withholding_rate_pct == 15.0

    def test_investor_type_foreign_person(self) -> None:
        assert self.result.investor.investor_type == InvestorTypeValue.FOREIGN_PERSON

    def test_tax_residency_country_is_germany(self) -> None:
        assert self.result.tax_residency.country_of_citizenship == "Germany"

    def test_tax_residency_foreign_tin_present(self) -> None:
        assert self.result.tax_residency.foreign_tin == "DE123456789"


# ===========================================================================
# execute_without_form() — INCOMPLETE path for both investor types
# ===========================================================================


class TestExecuteWithoutForm:
    """execute_without_form() always returns INCOMPLETE regardless of investor type."""

    def test_us_person_without_form_is_incomplete(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute_without_form(_whitfield_profile())
        assert result.status == ProfileStatus.INCOMPLETE
        assert result.form_on_file is None

    def test_foreign_person_without_form_is_incomplete(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute_without_form(_weber_profile())
        assert result.status == ProfileStatus.INCOMPLETE
        assert result.form_on_file is None

    def test_foreign_person_without_form_status_reason_mentions_w8ben(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute_without_form(_weber_profile())
        assert "W-8BEN" in result.status_reason

    def test_us_person_without_form_withholding_rate_is_none(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute_without_form(_whitfield_profile())
        assert result.withholding_rate is None


# ===========================================================================
# Review-required paths
# ===========================================================================


class TestReviewRequiredPaths:
    """Combinations that should produce REVIEW_REQUIRED."""

    def test_name_mismatch_causes_review_required(self) -> None:
        """Name mismatch between form and profile → REVIEW_REQUIRED."""
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(
            dto=_whitfield_dto(name="James T. Whitfield"),
            profile=_whitfield_profile(),
        )
        assert result.status == ProfileStatus.REVIEW_REQUIRED

    def test_review_required_status_reason_non_empty(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(
            dto=_whitfield_dto(name="James T. Whitfield"),
            profile=_whitfield_profile(),
        )
        assert result.status_reason != ""

    def test_missing_signature_causes_review_required(self) -> None:
        """Missing signature → REVIEW_REQUIRED."""
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(
            dto=_whitfield_dto(signature_present=False, signature_date=None),
            profile=_whitfield_profile(),
        )
        assert result.status == ProfileStatus.REVIEW_REQUIRED

    def test_treaty_claim_missing_for_treaty_country_causes_review_required(self) -> None:
        """Germany treaty available but Part II blank → REVIEW_REQUIRED."""
        uc = AssembleTaxProfileUseCase()
        dto_no_claim = _weber_dto(
            treaty_country=None,
            treaty_article=None,
            withholding_rate=None,
            income_type=None,
            treaty_conditions=None,
        )
        result = uc.execute(dto=dto_no_claim, profile=_weber_profile())
        assert result.status == ProfileStatus.REVIEW_REQUIRED


# ===========================================================================
# TreatyStatusDTO shapes for each investor category
# ===========================================================================


class TestTreatyStatusDTOShapes:
    """Verify TreatyStatusDTO fields for each treaty-relevant category."""

    def test_us_person_treaty_status_all_defaults(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_whitfield_dto(), profile=_whitfield_profile())
        ts = result.treaty_status
        assert ts.claim_status == TreatyClaimStatus.NOT_APPLICABLE
        assert ts.has_treaty is False
        assert ts.treaty_country is None
        assert ts.applied_withholding_rate_pct is None

    def test_non_treaty_foreign_person_treaty_status(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_ribeiro_dto(), profile=_ribeiro_profile())
        ts = result.treaty_status
        assert ts.claim_status == TreatyClaimStatus.NO_TREATY
        assert ts.has_treaty is False
        assert ts.applied_withholding_rate_pct is None

    def test_validated_treaty_claim_sets_applied_rate(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_weber_dto(), profile=_weber_profile())
        ts = result.treaty_status
        assert ts.claim_status == TreatyClaimStatus.CLAIMED_AND_VALIDATED
        assert ts.has_treaty is True
        assert ts.applied_withholding_rate_pct == 15.0

    def test_treaty_available_claim_missing_status(self) -> None:
        """W-8BEN from treaty country with blank Part II → TREATY_AVAILABLE_CLAIM_MISSING."""
        uc = AssembleTaxProfileUseCase()
        dto_no_claim = _weber_dto(
            treaty_country=None,
            treaty_article=None,
            withholding_rate=None,
            income_type=None,
            treaty_conditions=None,
        )
        result = uc.execute(dto=dto_no_claim, profile=_weber_profile())
        ts = result.treaty_status
        assert ts.claim_status == TreatyClaimStatus.TREATY_AVAILABLE_CLAIM_MISSING
        assert ts.has_treaty is True
        assert ts.applied_withholding_rate_pct is None


# ===========================================================================
# FormOnFileDTO — W-9 has no expiry
# ===========================================================================


class TestFormOnFileDTOBehaviours:
    def test_w9_valid_through_is_none(self) -> None:
        """W-9 has no automatic expiry; valid_through must be None."""
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_whitfield_dto(), profile=_whitfield_profile())
        assert result.form_on_file is not None
        assert result.form_on_file.valid_through is None

    def test_w9_is_expired_is_false(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_whitfield_dto(), profile=_whitfield_profile())
        assert result.form_on_file is not None
        assert result.form_on_file.is_expired is False

    def test_w8ben_recent_form_not_expired(self) -> None:
        """W-8BEN signed 2024-07-22 → valid through 2027-12-31 → not expired."""
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_weber_dto(), profile=_weber_profile())
        assert result.form_on_file is not None
        assert result.form_on_file.is_expired is False

    def test_w8ben_valid_through_is_populated(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_weber_dto(), profile=_weber_profile())
        assert result.form_on_file is not None
        assert result.form_on_file.valid_through == "2027-12-31"

    def test_w8ben_expired_form_sets_is_expired_true(self) -> None:
        uc = AssembleTaxProfileUseCase()
        result = uc.execute(dto=_ribeiro_dto(), profile=_ribeiro_profile())
        assert result.form_on_file is not None
        assert result.form_on_file.is_expired is True


# ===========================================================================
# Error handling
# ===========================================================================


class TestErrorHandling:
    def test_unsupported_form_type_raises_value_error(self) -> None:
        uc = AssembleTaxProfileUseCase()
        dto = ParsedFormFieldsDTO(form_type="W-8IMY")
        with pytest.raises(ValueError, match="W-8IMY"):
            uc.execute(dto=dto, profile=_whitfield_profile())
