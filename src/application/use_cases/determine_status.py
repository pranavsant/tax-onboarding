"""Use case: determine the overall tax-profile status from all validation results.

Accepts pre-computed validation result DTOs from every upstream validation
check and returns a single :class:`~src.application.dto.tax_form_dto.StatusDeterminationResultDTO`
that captures both the machine-readable :class:`~src.application.dto.tax_profile_dto.ProfileStatus`
and a human-readable ``status_reason``.

Status rules (in priority order)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
1. ``INCOMPLETE`` — the investor has never submitted a form; ``form_submitted``
   is ``False``.  A specific message names the required form (W-9 or W-8BEN).
2. ``REVIEW_REQUIRED`` — at least one validation check failed.  **Every**
   failing check contributes its own reason string; they are joined with
   ``" | "`` so the operations team has full context at a glance.
3. ``READY`` — all supplied checks passed; ``status_reason`` is an empty
   string.

Design notes
------------
* This use case is a **thin shim**: all business logic lives in the domain
  service :class:`~src.domain.services.status_determinator.StatusDeterminator`.
  The use case's only job is to ferry application-layer DTOs into the domain
  service and wrap the result in the application output DTO.
* Passing ``None`` for any validation result DTO silently skips that check —
  useful when a check is not applicable for the given form type (e.g.
  ``expiration_result=None`` for W-9 forms).
* No infrastructure dependencies — can be instantiated directly without
  dependency injection.
"""
from __future__ import annotations

from typing import Optional

from src.application.dto.tax_form_dto import (
    ExpirationValidationResultDTO,
    ProfileMismatchResultDTO,
    SignatureValidationResultDTO,
    StatusDeterminationResultDTO,
    TINValidationResultDTO,
    TreatyClaimValidationResultDTO,
)
from src.domain.services.status_determinator import StatusDeterminator


class DetermineStatusUseCase:
    """Determine the overall tax-profile status from all validation results.

    This use case has no infrastructure dependency and can be instantiated
    directly — no dependency injection required::

        use_case = DetermineStatusUseCase()
        result = use_case.execute(
            form_submitted=True,
            is_us_person=True,
            signature_result=sig_dto,
            tin_result=tin_dto,
            expiration_result=None,
            treaty_claim_result=None,
            mismatch_result=mismatch_dto,
        )
        # result.status     → ProfileStatus.READY or REVIEW_REQUIRED or INCOMPLETE
        # result.status_reason → "" or "Reason A | Reason B"
    """

    def execute(
        self,
        *,
        form_submitted: bool,
        is_us_person: bool,
        signature_result: Optional[SignatureValidationResultDTO] = None,
        tin_result: Optional[TINValidationResultDTO] = None,
        expiration_result: Optional[ExpirationValidationResultDTO] = None,
        treaty_claim_result: Optional[TreatyClaimValidationResultDTO] = None,
        mismatch_result: Optional[ProfileMismatchResultDTO] = None,
    ) -> StatusDeterminationResultDTO:
        """Determine the status from all supplied validation results.

        Args:
            form_submitted: ``True`` when the investor has a tax form on file;
                ``False`` when no form has been submitted.  When ``False``,
                returns ``INCOMPLETE`` without evaluating any validation
                results.
            is_us_person: ``True`` for US persons (W-9 filers); ``False`` for
                foreign persons (W-8BEN filers).  Used only to name the
                correct form in the ``INCOMPLETE`` reason message.
            signature_result: Signature + date validation result.  ``None`` to
                skip this check.
            tin_result: TIN format validation result.  ``None`` to skip.
            expiration_result: W-8BEN expiration validation result.  Should be
                ``None`` for W-9 forms (no automatic expiry).
            treaty_claim_result: W-8BEN Part II treaty claim validation result.
                Should be ``None`` for W-9 forms.
            mismatch_result: Name / address profile comparison result.  Each
                mismatched field contributes its own reason string.  ``None``
                to skip.

        Returns:
            :class:`~src.application.dto.tax_form_dto.StatusDeterminationResultDTO`
            with:

            * ``status == INCOMPLETE`` when ``form_submitted`` is ``False``.
            * ``status == REVIEW_REQUIRED`` with all failure reasons joined by
              ``" | "`` in ``status_reason`` when at least one check failed.
            * ``status == READY`` with ``status_reason == ""`` when all
              supplied checks passed.
        """
        domain_result = StatusDeterminator.determine(
            form_submitted=form_submitted,
            is_us_person=is_us_person,
            signature_result=signature_result,
            tin_result=tin_result,
            expiration_result=expiration_result,
            treaty_claim_result=treaty_claim_result,
            mismatch_result=mismatch_result,
        )

        return StatusDeterminationResultDTO(
            status=domain_result.status,
            status_reason=domain_result.status_reason,
        )
