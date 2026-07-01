"""Domain service that assembles a :class:`TaxProfileDTO` from validated inputs.

This service is the *engine* behind :class:`AssembleTaxProfileUseCase`.  It
owns the business rules for:

* Mapping an :class:`~src.domain.entities.investor_profile.InvestorProfile`
  entity to the identity sub-objects (:class:`InvestorDTO`,
  :class:`TaxResidencyDTO`, :class:`TaxStatusSummaryDTO`).
* Building :class:`FormOnFileDTO` from the expiration validator output (W-8BEN)
  or from the profile metadata alone (W-9, which has no automatic expiry).
* Determining :class:`TreatyStatusDTO` from the treaty claim validator output
  and the treaty reference table.
* Deriving the effective ``withholding_rate``:
  - ``None`` for US persons (backup withholding under W-9 framework).
  - The reduced treaty rate (e.g. ``15.0``) when
    ``claim_status == CLAIMED_AND_VALIDATED``.
  - The statutory 30 % NRA rate (IRC § 1441) for all other foreign-investor
    cases.
* Computing the overall :class:`ProfileStatus` by collecting issues from all
  validation inputs:
  - ``INCOMPLETE``        — no form has been submitted (``form_on_file is None``).
  - ``REVIEW_REQUIRED``   — at least one validation check failed.
  - ``READY``             — all checks passed.

Reporting-track convention (informational)
------------------------------------------
The reporting track is **implicit** in the assembled :class:`TaxProfileDTO`:

* ``form_on_file.form_code == "W-9"``  → **1099-DIV** track (US-person
  dividend reporting).
* ``form_on_file.form_code == "W-8BEN"`` → **1042-S** track (foreign-person
  NRA withholding reporting).

The :class:`TaxProfileDTO` schema does not carry an explicit
``reporting_track`` field; downstream workflows derive it from
``form_on_file.form_code`` as shown above.

Design notes
------------
* This is a **stateless** service — all inputs are passed as arguments; there
  is no mutable class state.
* It does **not** invoke the validator use cases itself; pre-computed
  validation result DTOs are passed in.  This keeps the domain layer free of
  application-layer concerns.
* For W-9 forms, ``expiration_result`` and ``treaty_claim_result`` are
  irrelevant and must be ``None`` — they are silently ignored when present.
"""
from __future__ import annotations

from typing import Optional

from src.application.dto.tax_form_dto import (
    ExpirationValidationResultDTO,
    ProfileMismatchResultDTO,
    SignatureValidationResultDTO,
    TINValidationResultDTO,
    TreatyClaimValidationResultDTO,
)
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
from src.domain.entities.investor_profile import InvestorProfile
from src.domain.services.status_determinator import StatusDeterminator
from src.domain.services.tax_form_determination_service import InvestorType, TaxFormCode
from src.domain.services.treaty_table import TreatyTable

# Statutory NRA withholding rate (IRC § 1441).
_STATUTORY_RATE: float = 30.0


class TaxProfileAssembler:
    """Stateless domain service that assembles a :class:`TaxProfileDTO`.

    All methods are class methods or static methods; no instance state is
    used.  The primary entry point is :meth:`assemble`.
    """

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    @classmethod
    def assemble(
        cls,
        profile: InvestorProfile,
        *,
        signature_result: Optional[SignatureValidationResultDTO],
        tin_result: Optional[TINValidationResultDTO],
        expiration_result: Optional[ExpirationValidationResultDTO],
        treaty_claim_result: Optional[TreatyClaimValidationResultDTO],
        mismatch_result: Optional[ProfileMismatchResultDTO],
    ) -> TaxProfileDTO:
        """Assemble a complete :class:`TaxProfileDTO` from an investor profile
        and pre-computed validation results.

        For **W-9** profiles:
          * ``expiration_result`` and ``treaty_claim_result`` must be ``None``
            (W-9 has no expiry and no treaty claim section).
          * ``signature_result``, ``tin_result``, and ``mismatch_result`` are
            relevant; pass ``None`` to skip that specific check contribution.

        For **W-8BEN** profiles:
          * All five parameters may be supplied.
          * ``expiration_result`` drives ``form_on_file.is_expired`` and
            ``form_on_file.valid_through``.
          * ``treaty_claim_result`` drives ``treaty_status`` and
            ``withholding_rate``.

        When a form has **never been submitted** (``profile.last_form_on_file``
        is ``None``), all validation result parameters should be ``None`` as
        well; the assembled profile will have ``form_on_file=None`` and
        ``status=INCOMPLETE``.

        Args:
            profile: The stored investor profile entity (source of identity,
                residency, and baseline status data).
            signature_result: Output of
                :class:`~src.application.use_cases.validate_signature.ValidateSignatureUseCase`.
                ``None`` when no form has been submitted or the check was not run.
            tin_result: Output of
                :class:`~src.application.use_cases.validate_tin.ValidateTINUseCase`.
                ``None`` when no form has been submitted or the check was not run.
            expiration_result: Output of
                :class:`~src.application.use_cases.validate_expiration.ValidateExpirationUseCase`.
                ``None`` for W-9 forms and when no form has been submitted.
            treaty_claim_result: Output of
                :class:`~src.application.use_cases.validate_treaty_claim.ValidateTreatyClaimUseCase`.
                ``None`` for W-9 forms and when no form has been submitted.
            mismatch_result: Output of
                :class:`~src.application.use_cases.detect_profile_mismatch.DetectProfileMismatchUseCase`.
                ``None`` when no form has been submitted or the check was not run.

        Returns:
            A fully populated :class:`TaxProfileDTO`.
        """
        investor_dto = cls._build_investor(profile)
        tax_residency_dto = cls._build_tax_residency(profile)
        tax_status_dto = cls._build_tax_status(profile)
        form_on_file_dto = cls._build_form_on_file(profile, expiration_result)
        treaty_status_dto = cls._build_treaty_status(profile, treaty_claim_result)
        withholding_rate = cls._derive_withholding_rate(profile, treaty_status_dto)
        status, status_reason = cls._derive_profile_status(
            profile=profile,
            form_on_file=form_on_file_dto,
            signature_result=signature_result,
            tin_result=tin_result,
            expiration_result=expiration_result,
            treaty_claim_result=treaty_claim_result,
            mismatch_result=mismatch_result,
        )

        return TaxProfileDTO(
            investor=investor_dto,
            tax_residency=tax_residency_dto,
            tax_status=tax_status_dto,
            form_on_file=form_on_file_dto,
            treaty_status=treaty_status_dto,
            withholding_rate=withholding_rate,
            status=status,
            status_reason=status_reason,
        )

    # ------------------------------------------------------------------
    # Sub-object builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_investor(profile: InvestorProfile) -> InvestorDTO:
        """Map :class:`InvestorProfile` identity fields to :class:`InvestorDTO`."""
        investor_type = (
            InvestorTypeValue.FOREIGN_PERSON
            if profile.investor_type == InvestorType.FOREIGN_PERSON
            else InvestorTypeValue.US_PERSON
        )
        return InvestorDTO(
            full_name=profile.full_name,
            address=profile.address,
            investor_type=investor_type,
            country=profile.country,
        )

    @staticmethod
    def _build_tax_residency(profile: InvestorProfile) -> TaxResidencyDTO:
        """Map :class:`InvestorProfile` residency fields to :class:`TaxResidencyDTO`."""
        is_us = profile.investor_type == InvestorType.US_PERSON
        return TaxResidencyDTO(
            is_us_person=is_us,
            country_of_citizenship=None if is_us else profile.country,
            foreign_tin=profile.foreign_tin,
            ftin_not_required=False,  # stored profile does not carry this flag
        )

    @staticmethod
    def _build_tax_status(profile: InvestorProfile) -> TaxStatusSummaryDTO:
        """Map the profile's :class:`TaxStatus` to :class:`TaxStatusSummaryDTO`."""
        status_str = profile.tax_status.value  # e.g. "VERIFIED", "EXPIRED", …
        if status_str == "VERIFIED":
            detail = ""
        elif status_str == "EXPIRED":
            detail = "W-8BEN on file expired. A new form must be collected."
        elif status_str == "PENDING":
            form_label = (
                profile.last_form_on_file.value
                if profile.last_form_on_file
                else "W-9" if profile.investor_type == InvestorType.US_PERSON else "W-8BEN"
            )
            detail = f"{form_label} has been requested but not yet received."
        else:  # MISSING
            detail = (
                "No form on file. Investor must submit the required tax form "
                "before onboarding can be completed."
            )
        return TaxStatusSummaryDTO(current_status=status_str, status_detail=detail)

    @staticmethod
    def _build_form_on_file(
        profile: InvestorProfile,
        expiration_result: Optional[ExpirationValidationResultDTO],
    ) -> Optional[FormOnFileDTO]:
        """Build :class:`FormOnFileDTO` or return ``None`` when no form exists."""
        if profile.last_form_on_file is None:
            return None

        # Map domain TaxFormCode to application FormCode.
        form_code = (
            FormCode.W9
            if profile.last_form_on_file == TaxFormCode.W9
            else FormCode.W8BEN
        )
        signed_date = profile.last_form_signed_date

        if form_code == FormCode.W9:
            # W-9 has no automatic expiry.
            return FormOnFileDTO(
                form_code=FormCode.W9,
                signed_date=signed_date,
                valid_through=None,
                is_expired=False,
            )

        # W-8BEN — derive expiry from the expiration validation result.
        if expiration_result is not None:
            return FormOnFileDTO(
                form_code=FormCode.W8BEN,
                signed_date=signed_date,
                valid_through=expiration_result.valid_through,
                is_expired=not expiration_result.passed,
            )

        # Expiration result not supplied — carry form metadata only.
        return FormOnFileDTO(
            form_code=FormCode.W8BEN,
            signed_date=signed_date,
            valid_through=None,
            is_expired=False,
        )

    @staticmethod
    def _build_treaty_status(
        profile: InvestorProfile,
        treaty_claim_result: Optional[TreatyClaimValidationResultDTO],
    ) -> TreatyStatusDTO:
        """Derive :class:`TreatyStatusDTO` from profile and treaty claim result."""
        is_us = profile.investor_type == InvestorType.US_PERSON

        # US persons: treaty status is always NOT_APPLICABLE.
        if is_us:
            return TreatyStatusDTO(
                claim_status=TreatyClaimStatus.NOT_APPLICABLE,
                has_treaty=False,
                treaty_country=None,
                applied_withholding_rate_pct=None,
            )

        # Foreign persons: consult the treaty table for the country.
        country = profile.country or ""
        try:
            treaty_entry = TreatyTable.lookup(country)
        except ValueError:
            # Unknown / missing country — treat as no treaty.
            treaty_entry = None  # type: ignore[assignment]

        has_treaty = treaty_entry.has_treaty if treaty_entry is not None else False

        # Determine claim_status from the treaty claim result.
        if treaty_claim_result is None:
            # No validation result supplied — derive from profile data only.
            if not has_treaty:
                claim_status = TreatyClaimStatus.NO_TREATY
            elif profile.treaty_country:
                # Treaty country recorded in the profile → assume claimed.
                claim_status = TreatyClaimStatus.CLAIMED_AND_VALIDATED
            else:
                claim_status = TreatyClaimStatus.TREATY_AVAILABLE_CLAIM_MISSING
            applied_rate: Optional[float] = (
                treaty_entry.withholding_rate_pct
                if has_treaty and profile.treaty_country and treaty_entry is not None
                else None
            )
            treaty_country_val = profile.treaty_country
        else:
            # Use the validated claim result.
            if not has_treaty:
                claim_status = TreatyClaimStatus.NO_TREATY
                applied_rate = None
                treaty_country_val = None
            elif treaty_claim_result.passed and treaty_claim_result.applied_withholding_rate_pct is not None:
                claim_status = TreatyClaimStatus.CLAIMED_AND_VALIDATED
                applied_rate = treaty_claim_result.applied_withholding_rate_pct
                treaty_country_val = profile.treaty_country
            elif not treaty_claim_result.passed:
                # Distinguish between "blank but treaty available" and "incomplete".
                # We use the reason text to distinguish: TreatyClaimValidator uses
                # specific phrasing ("is blank" vs "partially completed").
                reason = treaty_claim_result.reason.lower()
                if "partially completed" in reason or "missing required" in reason:
                    claim_status = TreatyClaimStatus.CLAIM_INCOMPLETE
                else:
                    claim_status = TreatyClaimStatus.TREATY_AVAILABLE_CLAIM_MISSING
                applied_rate = None
                treaty_country_val = None
            else:
                # passed=True but no applied rate → non-treaty country branch passed.
                claim_status = TreatyClaimStatus.NO_TREATY
                applied_rate = None
                treaty_country_val = None

        return TreatyStatusDTO(
            claim_status=claim_status,
            has_treaty=has_treaty,
            treaty_country=treaty_country_val,
            applied_withholding_rate_pct=applied_rate,
        )

    @staticmethod
    def _derive_withholding_rate(
        profile: InvestorProfile,
        treaty_status: TreatyStatusDTO,
    ) -> Optional[float]:
        """Derive the effective withholding rate per schema rules.

        Rules:
        * US person → ``None`` (backup withholding under W-9 framework).
        * Foreign / ``CLAIMED_AND_VALIDATED`` → treaty reduced rate from
          ``treaty_status.applied_withholding_rate_pct``.
        * Foreign / all other treaty claim statuses → 30.0 % (statutory NRA).
        """
        if profile.investor_type == InvestorType.US_PERSON:
            return None

        if (
            treaty_status.claim_status == TreatyClaimStatus.CLAIMED_AND_VALIDATED
            and treaty_status.applied_withholding_rate_pct is not None
        ):
            return treaty_status.applied_withholding_rate_pct

        return _STATUTORY_RATE

    # ------------------------------------------------------------------
    # Profile-status derivation
    # ------------------------------------------------------------------

    @classmethod
    def _derive_profile_status(
        cls,
        profile: InvestorProfile,
        form_on_file: Optional[FormOnFileDTO],
        signature_result: Optional[SignatureValidationResultDTO],
        tin_result: Optional[TINValidationResultDTO],
        expiration_result: Optional[ExpirationValidationResultDTO],
        treaty_claim_result: Optional[TreatyClaimValidationResultDTO],
        mismatch_result: Optional[ProfileMismatchResultDTO],
    ) -> tuple[ProfileStatus, str]:
        """Return ``(ProfileStatus, status_reason)`` for the assembled profile.

        Delegates entirely to
        :class:`~src.domain.services.status_determinator.StatusDeterminator`
        so that all status-determination logic lives in a single, independently
        testable domain service.

        Priority (highest → lowest):
        1. ``INCOMPLETE`` — no form has been submitted (``form_on_file is None``).
        2. ``REVIEW_REQUIRED`` — at least one validation check failed.
        3. ``READY`` — all supplied checks passed.
        """
        is_us_person = profile.investor_type == InvestorType.US_PERSON
        result = StatusDeterminator.determine(
            form_submitted=form_on_file is not None,
            is_us_person=is_us_person,
            signature_result=signature_result,
            tin_result=tin_result,
            expiration_result=expiration_result,
            treaty_claim_result=treaty_claim_result,
            mismatch_result=mismatch_result,
        )
        return result.status, result.status_reason
