"""Domain service that compares submitted form data against a stored investor profile.

Business rules
--------------
When an investor re-submits a tax form, the fields on the new submission are
compared against the profile record that exists in the system.  If any key
identity field has changed, the discrepancy is flagged so that an operations
team member can verify the change before updating the stored profile.

Fields compared
~~~~~~~~~~~~~~~
* **Name** — ``InvestorProfile.full_name`` vs ``ParsedFormFields.name``.
  The submitted name is trimmed and compared case-insensitively.  A change in
  name (e.g. after a marriage or legal name change) must be reviewed.

* **Address** — ``InvestorProfile.address`` vs the submission address field:

    - W-9: ``ParsedFormFields.address``
    - W-8BEN: ``ParsedFormFields.permanent_address``

  The submitted address is trimmed and compared case-insensitively.

Comparison semantics
~~~~~~~~~~~~~~~~~~~~
Comparisons are **normalised** (strip whitespace, case-fold) so that trivial
formatting differences (trailing spaces, mixed case) are not reported as
mismatches.  Structural / substantial differences are flagged.

If a submitted field is ``None`` or empty it is treated as "not provided on
the submitted form" — this is reported as a mismatch only when the profile
holds a non-empty value for that field.

Design note — *flag, not crash*:
    Like all other domain validators in this package,
    :class:`ProfileMismatchDetector` never raises exceptions for invalid /
    unexpected field states.  Comparison outcomes are always returned as
    :class:`ProfileMismatchResult` instances.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.domain.entities.investor_profile import InvestorProfile


@dataclass(frozen=True)
class MismatchDetail:
    """A single field discrepancy between a form submission and a stored profile.

    Attributes:
        field: Logical name of the differing field (``"name"`` or
            ``"address"``).
        profile_value: The value currently held in the stored investor profile.
        submitted_value: The value supplied on the submitted form.
        reason: Human-readable description of the mismatch suitable for
            display in an operations review queue.
    """

    field: str
    profile_value: str
    submitted_value: str
    reason: str


@dataclass(frozen=True)
class ProfileMismatchResult:
    """Outcome of :meth:`ProfileMismatchDetector.compare`.

    Attributes:
        has_mismatches: ``True`` when at least one field in the submission
            differs from the stored investor profile; ``False`` when all
            compared fields match exactly.
        mismatches: Ordered list of :class:`MismatchDetail` instances, one
            per differing field.  Empty when ``has_mismatches`` is ``False``.
    """

    has_mismatches: bool
    mismatches: list = field(default_factory=list)  # list[MismatchDetail]


class ProfileMismatchDetector:
    """Stateless domain service that compares a tax form submission against a
    stored :class:`~src.domain.entities.investor_profile.InvestorProfile`.

    Usage::

        result = ProfileMismatchDetector.compare(
            profile=investor_profile,
            submitted_name="James Whitfield",
            submitted_address="84 Pinecrest Drive, Austin, TX 78701",
        )
        if result.has_mismatches:
            for m in result.mismatches:
                print(m.reason)
    """

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise(value: Optional[str]) -> str:
        """Return a normalised (stripped, case-folded) version of *value*.

        ``None`` and empty / whitespace-only strings all normalise to ``""``.
        """
        if not value:
            return ""
        return value.strip().casefold()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def compare(
        cls,
        profile: "InvestorProfile",
        submitted_name: Optional[str],
        submitted_address: Optional[str],
    ) -> ProfileMismatchResult:
        """Compare submitted identity fields against a stored investor profile.

        Args:
            profile: The :class:`~src.domain.entities.investor_profile.InvestorProfile`
                record that represents the investor's current state in the
                system.  Used as the **baseline** for comparison.
            submitted_name: The name as it appears on the newly submitted form
                (``name`` field from :class:`ParsedFormFieldsDTO`).  May be
                ``None`` if the field was absent or illegible.
            submitted_address: The address as it appears on the newly submitted
                form.  For W-9 forms this is the ``address`` field; for W-8BEN
                forms this is ``permanent_address``.  May be ``None`` if absent.

        Returns:
            :class:`ProfileMismatchResult` with ``has_mismatches=False`` and an
            empty ``mismatches`` list when all compared fields match exactly, or
            ``has_mismatches=True`` and a non-empty ``mismatches`` list when at
            least one field differs.
        """
        mismatches: list[MismatchDetail] = []

        # ------------------------------------------------------------------
        # 1. Name comparison
        # ------------------------------------------------------------------
        profile_name_norm = cls._normalise(profile.full_name)
        submitted_name_norm = cls._normalise(submitted_name)

        if profile_name_norm != submitted_name_norm:
            mismatches.append(
                MismatchDetail(
                    field="name",
                    profile_value=profile.full_name,
                    submitted_value=submitted_name or "",
                    reason=(
                        f"Name on submitted form ('{submitted_name or ''}') "
                        f"does not match the name on record "
                        f"('{profile.full_name}'). Please verify the change."
                    ),
                )
            )

        # ------------------------------------------------------------------
        # 2. Address comparison
        # ------------------------------------------------------------------
        profile_address_norm = cls._normalise(profile.address)
        submitted_address_norm = cls._normalise(submitted_address)

        if profile_address_norm != submitted_address_norm:
            mismatches.append(
                MismatchDetail(
                    field="address",
                    profile_value=profile.address,
                    submitted_value=submitted_address or "",
                    reason=(
                        f"Address on submitted form ('{submitted_address or ''}') "
                        f"does not match the address on record "
                        f"('{profile.address}'). Please verify the change."
                    ),
                )
            )

        return ProfileMismatchResult(
            has_mismatches=bool(mismatches),
            mismatches=mismatches,
        )
