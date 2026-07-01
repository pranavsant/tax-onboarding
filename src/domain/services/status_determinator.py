"""Domain service that determines the overall tax-profile status from all
validation results.

This service is the single authoritative source of truth for:

* **Tax Ready** (``ProfileStatus.READY``) — all supplied validation checks
  passed and a form is on file.
* **Flagged for Review** (``ProfileStatus.REVIEW_REQUIRED``) — at least one
  validation check failed; *every* failing check contributes a human-readable
  reason to the output so the operations team has full context.
* **Incomplete** (``ProfileStatus.INCOMPLETE``) — no form has ever been
  submitted by the investor; highest-priority short-circuit.

Business rules
--------------
1. ``INCOMPLETE`` takes precedence over all other statuses.  When
   ``form_submitted`` is ``False``, the method returns immediately with a
   human-readable message naming the required form.

2. All five validation checks are evaluated, and **every** failure is
   collected.  The final ``status_reason`` is the concatenation of all
   individual failure reasons joined by ``" | "``.  This satisfies the
   acceptance criterion that *multiple simultaneous issues are all captured*
   in the reason (not just the first one found).

3. When all supplied checks pass (or no checks are supplied), the status is
   ``READY`` with an empty string reason.

Validation checks evaluated (in order)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* Signature validity (``signature_result``)
* TIN format (``tin_result``)
* W-8BEN expiration (``expiration_result``) — ``None`` for W-9 forms
* Treaty claim correctness (``treaty_claim_result``) — ``None`` for W-9 forms
* Profile comparison / name-address mismatch (``mismatch_result``)

When a result is ``None`` it is silently skipped — the corresponding
validation was either not applicable to the form type or was not run.

Design notes
------------
* **Stateless** — all inputs are method arguments; no instance state is used.
* The service accepts application-layer DTOs directly rather than domain
  entities; this is the same accepted pattern used by
  :class:`~src.domain.services.tax_profile_assembler.TaxProfileAssembler`.
  Domain errors are always translated to application-layer DTOs before they
  reach this service.
* The mismatch result carries a *list* of :class:`MismatchDetailDTO` objects;
  each one contributes a separate reason string so no granularity is lost
  when multiple fields mismatch simultaneously.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.application.dto.tax_form_dto import (
    ExpirationValidationResultDTO,
    ProfileMismatchResultDTO,
    SignatureValidationResultDTO,
    TINValidationResultDTO,
    TreatyClaimValidationResultDTO,
)
from src.application.dto.tax_profile_dto import ProfileStatus


@dataclass(frozen=True)
class StatusDeterminationResult:
    """Outcome of :meth:`StatusDeterminator.determine`.

    Attributes:
        status: The overall readiness of the tax profile.

            ``READY``
                All validation checks passed.  The profile is cleared for
                downstream workflows (withholding, distribution, document
                generation).

            ``REVIEW_REQUIRED``
                At least one validation check flagged an issue that requires
                human review.  ``status_reason`` contains the full, joined set
                of failure messages.

            ``INCOMPLETE``
                No form has been submitted.  ``status_reason`` names the form
                the investor must supply.

        status_reason: Human-readable explanation of the status.  Empty string
            when ``status`` is ``READY``; a pipe-delimited (``" | "``)
            concatenation of all individual failure reasons otherwise.
    """

    status: ProfileStatus
    status_reason: str


class StatusDeterminator:
    """Stateless domain service that aggregates all validation results into a
    single :class:`StatusDeterminationResult`.

    All logic is implemented as a single static method so the service can be
    used without instantiation::

        result = StatusDeterminator.determine(
            form_submitted=True,
            is_us_person=True,
            signature_result=sig_dto,
            tin_result=tin_dto,
            expiration_result=None,  # W-9 — no expiry check
            treaty_claim_result=None,  # W-9 — no treaty check
            mismatch_result=mismatch_dto,
        )
        # result.status == ProfileStatus.READY or REVIEW_REQUIRED or INCOMPLETE
        # result.status_reason == "" or "Reason A | Reason B"
    """

    @staticmethod
    def determine(
        *,
        form_submitted: bool,
        is_us_person: bool,
        signature_result: Optional[SignatureValidationResultDTO] = None,
        tin_result: Optional[TINValidationResultDTO] = None,
        expiration_result: Optional[ExpirationValidationResultDTO] = None,
        treaty_claim_result: Optional[TreatyClaimValidationResultDTO] = None,
        mismatch_result: Optional[ProfileMismatchResultDTO] = None,
    ) -> StatusDeterminationResult:
        """Determine the overall tax-profile status from all validation results.

        Args:
            form_submitted: ``True`` when the investor has a form on file;
                ``False`` when no form has ever been submitted.  When
                ``False``, returns ``INCOMPLETE`` immediately without
                evaluating any validation results.
            is_us_person: ``True`` for US persons (W-9 filers); ``False`` for
                foreign persons (W-8BEN filers).  Used only in the
                ``INCOMPLETE`` reason string to name the correct required form.
            signature_result: Output of
                :class:`~src.application.use_cases.validate_signature.ValidateSignatureUseCase`.
                ``None`` to skip this check.
            tin_result: Output of
                :class:`~src.application.use_cases.validate_tin.ValidateTINUseCase`.
                ``None`` to skip this check.
            expiration_result: Output of
                :class:`~src.application.use_cases.validate_expiration.ValidateExpirationUseCase`.
                Should be ``None`` for W-9 forms (no automatic expiry).
            treaty_claim_result: Output of
                :class:`~src.application.use_cases.validate_treaty_claim.ValidateTreatyClaimUseCase`.
                Should be ``None`` for W-9 forms (no treaty claim section).
            mismatch_result: Output of
                :class:`~src.application.use_cases.detect_profile_mismatch.DetectProfileMismatchUseCase`.
                ``None`` to skip this check.

        Returns:
            A :class:`StatusDeterminationResult` with:

            * ``status == INCOMPLETE`` when ``form_submitted`` is ``False``.
            * ``status == REVIEW_REQUIRED`` when at least one check failed,
              with all failure reasons joined by ``" | "`` in
              ``status_reason``.
            * ``status == READY`` with ``status_reason == ""`` when all
              supplied checks passed.
        """
        # ------------------------------------------------------------------
        # Priority 1 — No form on file → INCOMPLETE
        # ------------------------------------------------------------------
        if not form_submitted:
            required_form = "W-9" if is_us_person else "W-8BEN"
            return StatusDeterminationResult(
                status=ProfileStatus.INCOMPLETE,
                status_reason=(
                    f"No {required_form} on file. Investor must submit Form {required_form} "
                    "before onboarding can be completed."
                ),
            )

        # ------------------------------------------------------------------
        # Priority 2 — Collect ALL failure reasons from every validation check
        # ------------------------------------------------------------------
        issues: list[str] = []

        # Check 1 — Signature and date validity
        if signature_result is not None and not signature_result.passed:
            issues.append(signature_result.reason)

        # Check 2 — TIN format (SSN/EIN for W-9; foreign TIN presence for W-8BEN)
        if tin_result is not None and not tin_result.passed:
            issues.append(tin_result.reason)

        # Check 3 — W-8BEN expiration (None for W-9 — silently skipped)
        if expiration_result is not None and not expiration_result.passed:
            issues.append(expiration_result.reason)

        # Check 4 — Treaty claim correctness (None for W-9 — silently skipped)
        if treaty_claim_result is not None and not treaty_claim_result.passed:
            issues.append(treaty_claim_result.reason)

        # Check 5 — Profile comparison (name / address mismatch)
        if mismatch_result is not None and mismatch_result.has_mismatches:
            for mismatch in mismatch_result.mismatches:
                # Each mismatched field contributes its own reason string so
                # the reviewer can see every discrepancy at a glance.
                issues.append(mismatch.reason)

        if issues:
            return StatusDeterminationResult(
                status=ProfileStatus.REVIEW_REQUIRED,
                status_reason=" | ".join(issues),
            )

        # ------------------------------------------------------------------
        # Priority 3 — All checks passed → READY
        # ------------------------------------------------------------------
        return StatusDeterminationResult(
            status=ProfileStatus.READY,
            status_reason="",
        )
