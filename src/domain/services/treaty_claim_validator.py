"""Domain service that validates Part II (treaty claim) of a W-8BEN form.

Business rules
--------------
A W-8BEN Part II contains five fields:

  * ``treaty_country``     — line 9, country whose treaty applies
  * ``treaty_article``     — line 10, article / paragraph of the treaty
  * ``withholding_rate``   — line 10, reduced rate claimed (e.g. "15%")
  * ``income_type``        — line 10, type of income (e.g. "Dividends")
  * ``treaty_conditions``  — line 10, additional conditions

The validation logic has three branches:

1. **Non-treaty country + blank Part II → pass**
   If the investor's country of citizenship does **not** have an active US
   income-tax treaty then completing Part II would be incorrect.  A blank
   Part II is the expected outcome and requires no action.

2. **Treaty country + blank Part II → flag for review**
   If the country *does* have a treaty and all Part II fields are absent,
   the investor may have failed to claim their reduced rate.  The form
   should be flagged so an operations team member can follow up.

3. **Treaty country + completed Part II → pass, return reduced rate**
   When the country has a treaty and the three mandatory Part II fields
   (``treaty_country``, ``treaty_article``, ``withholding_rate``) are
   non-empty, the claim is considered valid.  The applicable reduced
   withholding rate is taken from the treaty reference table and returned
   so downstream callers can apply it without re-querying the table.

"Blank Part II" is defined as all five Part II fields being ``None`` or
empty/whitespace-only strings.  "Completed Part II" requires at minimum the
three IRS-mandatory fields — ``treaty_country``, ``treaty_article``, and
``withholding_rate`` — to contain non-whitespace content.  The remaining two
fields (``income_type``, ``treaty_conditions``) are advisory and their
absence does not invalidate an otherwise complete claim.

Design note — *flag, not crash*:
    Invalid / unexpected states are returned as :class:`TreatyClaimValidationResult`
    with ``passed=False`` and a descriptive ``reason`` rather than raising
    exceptions.  This matches the null-over-failure convention used by the
    other validator domain services in this package.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.domain.services.treaty_table import TreatyTable


@dataclass(frozen=True)
class TreatyClaimValidationResult:
    """Outcome of :meth:`TreatyClaimValidator.validate`.

    Attributes:
        passed: ``True`` when the Part II state is consistent with the
            investor's country of citizenship; ``False`` when Part II is
            unexpectedly absent for a treaty country (flag for review).
        reason: Human-readable explanation of the outcome.  Empty string
            when ``passed`` is ``True``.
        applied_withholding_rate_pct: The reduced withholding rate from the
            treaty table when a completed treaty claim is accepted (e.g.
            ``15.0``).  ``None`` for non-treaty countries (no claim is
            possible) and for flagged forms (claim not validated).
    """

    passed: bool
    reason: str
    applied_withholding_rate_pct: Optional[float] = None


class TreatyClaimValidator:
    """Stateless domain service that validates Part II of a W-8BEN form.

    All inputs are accepted as raw strings (or ``None``) so this service
    remains decoupled from the DTO layer and is straightforward to test in
    isolation.
    """

    # The three fields whose presence is required for a valid treaty claim.
    # Source: IRS W-8BEN instructions (Rev. October 2021), page 8.
    _MANDATORY_CLAIM_FIELDS = ("treaty_country", "treaty_article", "withholding_rate")

    @staticmethod
    def _is_blank(value: Optional[str]) -> bool:
        """Return ``True`` if *value* is ``None`` or whitespace-only."""
        return not value or not value.strip()

    @classmethod
    def _part_ii_is_blank(
        cls,
        treaty_country: Optional[str],
        treaty_article: Optional[str],
        withholding_rate: Optional[str],
        income_type: Optional[str],
        treaty_conditions: Optional[str],
    ) -> bool:
        """Return ``True`` when every Part II field is absent or empty."""
        return all(
            cls._is_blank(v)
            for v in (
                treaty_country,
                treaty_article,
                withholding_rate,
                income_type,
                treaty_conditions,
            )
        )

    @classmethod
    def _part_ii_is_complete(
        cls,
        treaty_country: Optional[str],
        treaty_article: Optional[str],
        withholding_rate: Optional[str],
    ) -> bool:
        """Return ``True`` when the three mandatory Part II fields are present."""
        return all(
            not cls._is_blank(v)
            for v in (treaty_country, treaty_article, withholding_rate)
        )

    @classmethod
    def validate(
        cls,
        country_of_citizenship: str,
        treaty_country: Optional[str],
        treaty_article: Optional[str],
        withholding_rate: Optional[str],
        income_type: Optional[str],
        treaty_conditions: Optional[str],
    ) -> TreatyClaimValidationResult:
        """Validate the Part II treaty claim of a W-8BEN form.

        Args:
            country_of_citizenship: The investor's country of citizenship
                (W-8BEN line 2).  Used to determine treaty eligibility.
            treaty_country: Part II line 9 — country whose treaty applies.
                ``None`` if blank.
            treaty_article: Part II line 10 — treaty article / paragraph.
                ``None`` if blank.
            withholding_rate: Part II line 10 — reduced withholding rate
                claimed (e.g. ``"15%"``).  ``None`` if blank.
            income_type: Part II line 10 — type of income.  ``None`` if blank.
            treaty_conditions: Part II line 10 — additional conditions.
                ``None`` if blank.

        Returns:
            :class:`TreatyClaimValidationResult` describing the outcome.

        Raises:
            ValueError: If ``country_of_citizenship`` is ``None``, empty, or
                whitespace-only (propagated from :class:`TreatyTable`).
        """
        entry = TreatyTable.lookup(country_of_citizenship)
        part_ii_blank = cls._part_ii_is_blank(
            treaty_country, treaty_article, withholding_rate,
            income_type, treaty_conditions,
        )

        # ------------------------------------------------------------------
        # Branch 1: Non-treaty country — Part II should be blank.
        # ------------------------------------------------------------------
        if not entry.has_treaty:
            if part_ii_blank:
                # Correct — no treaty, no claim.
                return TreatyClaimValidationResult(
                    passed=True,
                    reason="",
                    applied_withholding_rate_pct=None,
                )
            else:
                # Investor from a non-treaty country has filled Part II.
                # Flag for review — the claim cannot be honoured.
                return TreatyClaimValidationResult(
                    passed=False,
                    reason=(
                        f"Part II (treaty claim) is filled in, but "
                        f"'{entry.country}' does not have an active US income-tax "
                        "treaty. The claim cannot be applied; please review."
                    ),
                    applied_withholding_rate_pct=None,
                )

        # ------------------------------------------------------------------
        # Branch 2: Treaty country — Part II is blank → flag for review.
        # ------------------------------------------------------------------
        if part_ii_blank:
            return TreatyClaimValidationResult(
                passed=False,
                reason=(
                    f"Part II (treaty claim) is blank, but '{entry.country}' "
                    "has an active US income-tax treaty. The investor may be "
                    "eligible for a reduced withholding rate. Please ask them "
                    "to complete Part II or confirm that they waive the treaty benefit."
                ),
                applied_withholding_rate_pct=None,
            )

        # ------------------------------------------------------------------
        # Branch 3: Treaty country — Part II is at least partially filled.
        # Require the three mandatory fields before accepting the claim.
        # ------------------------------------------------------------------
        if not cls._part_ii_is_complete(treaty_country, treaty_article, withholding_rate):
            missing: list[str] = []
            if cls._is_blank(treaty_country):
                missing.append("treaty country (line 9)")
            if cls._is_blank(treaty_article):
                missing.append("treaty article (line 10)")
            if cls._is_blank(withholding_rate):
                missing.append("withholding rate (line 10)")
            return TreatyClaimValidationResult(
                passed=False,
                reason=(
                    "Part II is partially completed but is missing required "
                    f"field(s): {', '.join(missing)}. Please review."
                ),
                applied_withholding_rate_pct=None,
            )

        # All three mandatory fields are present — accept the claim.
        return TreatyClaimValidationResult(
            passed=True,
            reason="",
            applied_withholding_rate_pct=entry.withholding_rate_pct,
        )
