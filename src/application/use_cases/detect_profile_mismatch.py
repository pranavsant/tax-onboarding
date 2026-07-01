"""Use case: compare a submitted tax form against a stored investor profile.

Accepts a :class:`~src.application.dto.tax_form_dto.ParsedFormFieldsDTO`
(the normalized intermediate representation produced by both the JSON input
path and the PDF extraction path) together with an
:class:`~src.domain.entities.investor_profile.InvestorProfile` and returns a
:class:`~src.application.dto.tax_form_dto.ProfileMismatchResultDTO` describing
any field-level discrepancies.

Fields compared
~~~~~~~~~~~~~~~
* **Name** — profile ``full_name`` vs form ``name``.
* **Address** — profile ``address`` vs:

  - W-9: form ``address``
  - W-8BEN: form ``permanent_address``

The comparison logic lives in the domain layer
(:class:`~src.domain.services.profile_mismatch_detector.ProfileMismatchDetector`);
this use case is a thin translation shim that selects the correct submitted
address field based on ``form_type`` and converts the domain result into
application-layer DTOs.

Applies to both W-9 and W-8BEN forms.
"""
from __future__ import annotations

from src.application.dto.tax_form_dto import (
    MismatchDetailDTO,
    ParsedFormFieldsDTO,
    ProfileMismatchResultDTO,
)
from src.domain.entities.investor_profile import InvestorProfile
from src.domain.services.profile_mismatch_detector import ProfileMismatchDetector


class DetectProfileMismatchUseCase:
    """Compare a submitted :class:`ParsedFormFieldsDTO` against a stored
    :class:`InvestorProfile` and surface any identity-field discrepancies.

    This use case has no infrastructure dependency and can be instantiated
    directly — no dependency injection required.
    """

    def execute(
        self,
        dto: ParsedFormFieldsDTO,
        profile: InvestorProfile,
    ) -> ProfileMismatchResultDTO:
        """Compare *dto* against *profile* and return the mismatch report.

        Args:
            dto: Normalized form fields from the investor's submission.
                ``dto.form_type`` determines which address field is used
                (``address`` for W-9, ``permanent_address`` for W-8BEN).
            profile: The stored investor profile that acts as the comparison
                baseline.

        Returns:
            :class:`~src.application.dto.tax_form_dto.ProfileMismatchResultDTO`
            with ``has_mismatches=False`` and an empty ``mismatches`` list when
            the submission matches the profile, or ``has_mismatches=True`` and a
            non-empty ``mismatches`` list when at least one field differs.

        Raises:
            ValueError: If ``dto.form_type`` is not ``"W-9"`` or ``"W-8BEN"``.
        """
        if dto.form_type not in ("W-9", "W-8BEN"):
            raise ValueError(
                f"DetectProfileMismatchUseCase: unsupported form_type "
                f"'{dto.form_type}'. Expected 'W-9' or 'W-8BEN'."
            )

        # Select the address field that corresponds to this form type.
        if dto.form_type == "W-9":
            submitted_address = dto.address
        else:
            # W-8BEN uses permanent_address for the primary residence.
            submitted_address = dto.permanent_address

        domain_result = ProfileMismatchDetector.compare(
            profile=profile,
            submitted_name=dto.name,
            submitted_address=submitted_address,
        )

        return ProfileMismatchResultDTO(
            has_mismatches=domain_result.has_mismatches,
            mismatches=[
                MismatchDetailDTO(
                    field=m.field,
                    profile_value=m.profile_value,
                    submitted_value=m.submitted_value,
                    reason=m.reason,
                )
                for m in domain_result.mismatches
            ],
        )
