"""Use case: assemble a complete :class:`TaxProfileDTO` from upstream inputs.

This is the **canonical producer** of :class:`TaxProfileDTO` instances.  It
combines:

* An existing :class:`~src.domain.entities.investor_profile.InvestorProfile`
  (retrieved from the database) that carries investor identity, residency,
  and the last known form metadata.
* A :class:`~src.application.dto.tax_form_dto.ParsedFormFieldsDTO` representing
  the investor's most recently submitted (and normalized) W-9 or W-8BEN form.
* The outputs of the five upstream validation use cases, invoked internally in
  the correct order and with form-type guards applied:

  | Use case                     | W-9  | W-8BEN |
  |------------------------------|------|--------|
  | ValidateSignatureUseCase     | ✓    | ✓      |
  | ValidateTINUseCase           | ✓    | ✓      |
  | ValidateExpirationUseCase    | —    | ✓      |
  | ValidateTreatyClaimUseCase   | —    | ✓      |
  | DetectProfileMismatchUseCase | ✓    | ✓      |

Reporting-track derivation (informational)
------------------------------------------
The :class:`TaxProfileDTO` schema does not expose an explicit
``reporting_track`` field, but the track is unambiguously determinable from
the assembled profile:

* ``form_on_file.form_code == "W-9"``    → **1099-DIV** (US-person dividend
  reporting; Schedule B income categorization).
* ``form_on_file.form_code == "W-8BEN"`` → **1042-S** (NRA withholding
  reporting under Chapter 3 / IRC § 1461).

Downstream workflows (distribution characterization, document generation)
should derive the track from ``form_on_file.form_code`` as shown above.

Withholding-rate derivation (informational)
-------------------------------------------
* US persons → ``withholding_rate = None`` (backup withholding under W-9
  certification, IRC § 3406, is governed by the certifying form and is not
  a standing deduction on all distributions).
* Foreign persons, treaty claim validated → reduced treaty rate from the
  treaty reference table (e.g. ``15.0`` % for Germany and the UK).
* Foreign persons, all other cases → statutory 30 % NRA rate (IRC § 1441).

Clean-architecture note
-----------------------
The heavy assembly logic lives in the domain service
:class:`~src.domain.services.tax_profile_assembler.TaxProfileAssembler`.
This use case is a thin orchestration shim that:

1. Invokes the upstream validator use cases.
2. Passes their results — along with the :class:`InvestorProfile` — to the
   domain assembler.
3. Returns the fully populated :class:`TaxProfileDTO`.

Domain types (:class:`InvestorProfile`, :class:`InvestorType`, etc.) are
consumed inside this module but are **not** re-exported.  Callers in the
interfaces layer should only import from ``src.application``.
"""
from __future__ import annotations

import dataclasses

from src.application.dto.tax_form_dto import ParsedFormFieldsDTO
from src.application.dto.tax_profile_dto import TaxProfileDTO
from src.application.use_cases.detect_profile_mismatch import DetectProfileMismatchUseCase
from src.application.use_cases.validate_expiration import ValidateExpirationUseCase
from src.application.use_cases.validate_signature import ValidateSignatureUseCase
from src.application.use_cases.validate_tin import ValidateTINUseCase
from src.application.use_cases.validate_treaty_claim import ValidateTreatyClaimUseCase
from src.domain.entities.investor_profile import InvestorProfile
from src.domain.services.tax_profile_assembler import TaxProfileAssembler


class AssembleTaxProfileUseCase:
    """Orchestrate the tax profile assembly pipeline.

    This use case has no infrastructure dependency and can be instantiated
    directly — no dependency injection required.

    Example usage::

        from src.application.use_cases.assemble_tax_profile import AssembleTaxProfileUseCase
        from src.application.dto.tax_form_dto import ParsedFormFieldsDTO
        # … retrieve `profile` from InvestorProfileRepository …
        # … obtain `dto` from NormalizeFormFieldsUseCase or ParsePdfFormFieldsUseCase …

        uc = AssembleTaxProfileUseCase()
        tax_profile = uc.execute(dto=dto, profile=profile)
    """

    def __init__(self) -> None:
        # Validator use cases — stateless, no external dependencies.
        self._validate_signature = ValidateSignatureUseCase()
        self._validate_tin = ValidateTINUseCase()
        self._validate_expiration = ValidateExpirationUseCase()
        self._validate_treaty_claim = ValidateTreatyClaimUseCase()
        self._detect_mismatch = DetectProfileMismatchUseCase()

    def execute(
        self,
        dto: ParsedFormFieldsDTO,
        profile: InvestorProfile,
    ) -> TaxProfileDTO:
        """Assemble and return a :class:`TaxProfileDTO` for *profile* / *dto*.

        Runs the appropriate validation use cases for the form type, then
        delegates final assembly to
        :class:`~src.domain.services.tax_profile_assembler.TaxProfileAssembler`.

        Args:
            dto: Normalized form fields (W-9 or W-8BEN) produced by either
                :class:`~src.application.use_cases.normalize_form_fields.NormalizeFormFieldsUseCase`
                (JSON path) or
                :class:`~src.application.use_cases.parse_pdf_form_fields.ParsePdfFormFieldsUseCase`
                (PDF path).
            profile: The stored investor profile entity loaded from the
                investor profile repository.

        Returns:
            A fully populated :class:`TaxProfileDTO` reflecting the current
            tax standing of the investor.

        Raises:
            ValueError: If ``dto.form_type`` is not ``"W-9"`` or ``"W-8BEN"``.
        """
        form_type = dto.form_type
        if form_type not in ("W-9", "W-8BEN"):
            raise ValueError(
                f"AssembleTaxProfileUseCase: unsupported form_type '{form_type}'. "
                "Expected 'W-9' or 'W-8BEN'."
            )

        # ------------------------------------------------------------------
        # Shared validations (both W-9 and W-8BEN)
        # ------------------------------------------------------------------
        signature_result = self._validate_signature.execute(dto)
        tin_result = self._validate_tin.execute(dto)
        mismatch_result = self._detect_mismatch.execute(dto=dto, profile=profile)

        # ------------------------------------------------------------------
        # W-8BEN-only validations
        # ------------------------------------------------------------------
        if form_type == "W-8BEN":
            expiration_result = self._validate_expiration.execute(dto)
            treaty_claim_result = self._validate_treaty_claim.execute(dto)
        else:
            # W-9 has no expiry and no treaty claim section.
            expiration_result = None
            treaty_claim_result = None

        # ------------------------------------------------------------------
        # Delegate assembly to the domain service
        # ------------------------------------------------------------------
        return TaxProfileAssembler.assemble(
            profile,
            signature_result=signature_result,
            tin_result=tin_result,
            expiration_result=expiration_result,
            treaty_claim_result=treaty_claim_result,
            mismatch_result=mismatch_result,
        )

    def execute_without_form(self, profile: InvestorProfile) -> TaxProfileDTO:
        """Assemble a :class:`TaxProfileDTO` for an investor who has not yet
        submitted any form.

        This is a convenience overload for the ``MISSING`` / ``PENDING``
        onboarding states where no form data is available.  All validation
        result inputs are ``None``; the resulting profile will have
        ``form_on_file = None`` and ``status = INCOMPLETE``.

        Even if the stored profile already references a previous form on file,
        this method treats the situation as "no current form" — it strips
        ``last_form_on_file`` and ``last_form_signed_date`` from the profile
        view passed to the assembler so that the output faithfully represents
        the "no form submitted yet" state.

        Args:
            profile: The stored investor profile entity.

        Returns:
            A :class:`TaxProfileDTO` with ``status == ProfileStatus.INCOMPLETE``.
        """
        # Strip form-on-file metadata so _build_form_on_file returns None and
        # _derive_profile_status correctly returns INCOMPLETE.
        no_form_profile = dataclasses.replace(
            profile,
            last_form_on_file=None,
            last_form_signed_date=None,
        )
        return TaxProfileAssembler.assemble(
            no_form_profile,
            signature_result=None,
            tin_result=None,
            expiration_result=None,
            treaty_claim_result=None,
            mismatch_result=None,
        )
