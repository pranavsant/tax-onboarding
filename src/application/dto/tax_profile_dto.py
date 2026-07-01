"""Structured Tax Profile schema — the unified output contract for the tax
onboarding pipeline.

.. important::
   **This module defines the canonical contract** for the ``TaxProfile``
   object.  All downstream workflows — distribution characterization,
   withholding calculation, document generation, compliance reporting —
   **must** consume this schema and must not reach into the individual
   validation result DTOs directly.  Any breaking change to field names,
   types, or allowed enum values in this file constitutes a contract change
   and requires coordinated updates across all consumers.

Purpose
-------
The individual validation use cases (signature, TIN, expiration, treaty
claim, profile mismatch) each produce narrow, single-concern DTOs.  This
module assembles those results — together with the investor identity and
residency data already stored in the investor profile — into one coherent
``TaxProfileDTO`` that downstream workflows can rely on as a single source
of truth for a given investor's current tax standing.

Schema overview
---------------
The top-level :class:`TaxProfileDTO` is composed of the following sections:

``investor``      — :class:`InvestorDTO`
    Legal identity: name, address, investor classification (US vs. foreign),
    and home country.

``tax_residency`` — :class:`TaxResidencyDTO`
    Country of citizenship / tax residency, foreign TIN, whether the investor
    is a US person.

``tax_status``    — :class:`TaxStatusSummaryDTO`
    Aggregate validation status: the investor's overall onboarding status
    (``VERIFIED`` / ``PENDING`` / ``EXPIRED`` / ``MISSING``), and a
    human-readable explanation when not verified.

``form_on_file``  — :class:`FormOnFileDTO` | ``None``
    The most recent IRS tax form on file (W-9 or W-8BEN), its signed date,
    and its expiry date (W-8BEN only).  ``None`` when no form has been
    submitted yet.

``treaty_status`` — :class:`TreatyStatusDTO`
    For foreign investors: whether the investor's country has an active US
    income-tax treaty, the claim status, and the applicable withholding rate.
    Populated with the statutory 30 % rate for non-treaty countries and
    ``None`` for US persons.

``withholding_rate`` — ``float | None``
    The applicable US withholding rate as a percentage (e.g. ``30.0`` for
    30 %, ``15.0`` for 15 %).  Derived from ``treaty_status`` for foreign
    investors; ``None`` for US persons (backup withholding rules apply
    instead and are governed by W-9 certification, not this field).

``status``        — :class:`ProfileStatus`
    The machine-readable overall readiness status of this tax profile:
    ``"READY"`` when all validations pass, ``"REVIEW_REQUIRED"`` when at
    least one check flags an issue (e.g. expired form, treaty mismatch),
    ``"INCOMPLETE"`` when mandatory information is missing.

``status_reason`` — ``str``
    A human-readable explanation of the current ``status``.  Empty string
    when ``status`` is ``"READY"``.

Reference test cases
--------------------
The schema has been reviewed against the four seeded investor personas and
against the outputs of all validation use cases.  See
``docs/tax_profile_schema.md`` for the full field reference and worked
examples for each persona.

Producers
~~~~~~~~~
* Future :class:`AssembleTaxProfileUseCase` (not yet implemented) will be
  the canonical producer of :class:`TaxProfileDTO` instances.
* Test utilities may construct instances directly for fixtures.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class InvestorTypeValue(str, Enum):
    """Classification of an investor for US tax withholding purposes.

    Allowed values
    --------------
    ``"us_person"``
        A US person as defined by IRC § 7701(a)(30): US citizens, resident
        aliens, domestic corporations / partnerships / estates / trusts.
        Certifies status on **Form W-9**.

    ``"foreign_person"``
        A non-US beneficial owner.  Certifies status on **Form W-8BEN**
        (individuals) or the appropriate W-8 variant for entities.
    """

    US_PERSON = "us_person"
    FOREIGN_PERSON = "foreign_person"


class FormCode(str, Enum):
    """IRS tax form code identifying the certification on file.

    Allowed values
    --------------
    ``"W-9"``      Request for Taxpayer Identification Number and Certification.
                   Filed by US persons.
    ``"W-8BEN"``   Certificate of Foreign Status of Beneficial Owner (individuals).
                   Filed by foreign individual investors.
    """

    W9 = "W-9"
    W8BEN = "W-8BEN"


class TreatyClaimStatus(str, Enum):
    """Describes the outcome of the W-8BEN Part II (treaty claim) review.

    Allowed values
    --------------
    ``"NOT_APPLICABLE"``
        The investor is a US person; treaty claims do not apply.

    ``"NO_TREATY"``
        The investor is a foreign person whose country of citizenship does
        **not** have an active US income-tax treaty.  The statutory 30 %
        NRA withholding rate applies.

    ``"CLAIMED_AND_VALIDATED"``
        The investor's country has a treaty and a complete, valid Part II
        claim was found on the W-8BEN.  The reduced withholding rate
        specified by the treaty applies (reflected in ``withholding_rate``).

    ``"TREATY_AVAILABLE_CLAIM_MISSING"``
        The investor's country has a treaty but Part II of the W-8BEN is
        blank.  The investor may be eligible for a reduced rate but has not
        claimed it; the form should be flagged for operations review.

    ``"CLAIM_INCOMPLETE"``
        Part II is partially filled but is missing one or more mandatory
        fields (treaty country, treaty article, or withholding rate).
        Requires follow-up before the reduced rate can be applied.
    """

    NOT_APPLICABLE = "NOT_APPLICABLE"
    NO_TREATY = "NO_TREATY"
    CLAIMED_AND_VALIDATED = "CLAIMED_AND_VALIDATED"
    TREATY_AVAILABLE_CLAIM_MISSING = "TREATY_AVAILABLE_CLAIM_MISSING"
    CLAIM_INCOMPLETE = "CLAIM_INCOMPLETE"


class ProfileStatus(str, Enum):
    """Overall readiness status of a :class:`TaxProfileDTO`.

    Allowed values
    --------------
    ``"READY"``
        All validation checks passed.  The profile is cleared for downstream
        workflows (withholding, distribution, document generation).

    ``"REVIEW_REQUIRED"``
        At least one validation check flagged an issue that requires human
        review — e.g. an expired W-8BEN, a treaty claim mismatch, or a name/
        address discrepancy against the stored investor profile.  Downstream
        workflows should pause until the issue is resolved.

    ``"INCOMPLETE"``
        Mandatory information is missing — e.g. no form has ever been
        submitted (``form_on_file`` is ``None``) or required identity fields
        are absent.  The onboarding workflow must collect the missing data
        before proceeding.
    """

    READY = "READY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    INCOMPLETE = "INCOMPLETE"


# ---------------------------------------------------------------------------
# Sub-object DTOs
# ---------------------------------------------------------------------------


@dataclass
class InvestorDTO:
    """Legal identity section of a :class:`TaxProfileDTO`.

    Fields
    ------
    full_name : str
        Legal name exactly as it appears on the most recently submitted tax
        form and as stored in the investor profile.

    address : str
        Primary street address on file.  For W-9 filers this is the address
        from the form; for W-8BEN filers this is the permanent residence
        address (line 3).

    investor_type : InvestorTypeValue
        Classification — ``"us_person"`` or ``"foreign_person"``.

    country : str | None
        Country of residence / citizenship.  Always present for foreign
        persons; ``None`` for US persons when not explicitly recorded (the
        US is implied).
    """

    full_name: str
    address: str
    investor_type: InvestorTypeValue
    country: Optional[str] = None


@dataclass
class TaxResidencyDTO:
    """Tax-residency section of a :class:`TaxProfileDTO`.

    Fields
    ------
    country_of_citizenship : str | None
        Country of citizenship as declared on the W-8BEN (line 2).  ``None``
        for US persons.

    foreign_tin : str | None
        Foreign taxpayer identification number (W-8BEN line 6a), e.g. a
        Brazilian CPF or a German Steuer-Identifikationsnummer.  ``None``
        for US persons and for foreign persons who checked the "FTIN not
        legally required" box.

    ftin_not_required : bool
        ``True`` when the investor checked the W-8BEN line 6b box indicating
        that a foreign TIN is not legally required in their country.
        Always ``False`` for US persons.

    is_us_person : bool
        Convenience flag; ``True`` when ``investor_type`` is
        ``"us_person"``.  Equivalent to
        ``investor_type == InvestorTypeValue.US_PERSON``.
    """

    is_us_person: bool
    country_of_citizenship: Optional[str] = None
    foreign_tin: Optional[str] = None
    ftin_not_required: bool = False


@dataclass
class TaxStatusSummaryDTO:
    """Aggregate tax-status section of a :class:`TaxProfileDTO`.

    This reflects the **stored** verification state of the investor profile
    (as persisted in the database), not the outcome of live validation checks
    on a specific submitted form.  Live validation outcomes feed into
    ``form_on_file``, ``treaty_status``, and the top-level ``status`` /
    ``status_reason`` fields.

    Fields
    ------
    current_status : str
        One of ``"PENDING"``, ``"VERIFIED"``, ``"EXPIRED"``, ``"MISSING"``.

        ``"PENDING"``    Form received but not yet reviewed by operations.
        ``"VERIFIED"``   Form reviewed and currently valid.
        ``"EXPIRED"``    Form on file has passed its validity window
                         (W-8BEN: 3 calendar years after the year of
                         signing; W-9: no automatic expiry but may be
                         re-requested).
        ``"MISSING"``    No form has ever been submitted for this investor.

    status_detail : str
        Human-readable explanation of the current status.  Empty string
        when ``current_status`` is ``"VERIFIED"``.
    """

    current_status: str  # "PENDING" | "VERIFIED" | "EXPIRED" | "MISSING"
    status_detail: str = ""


@dataclass
class FormOnFileDTO:
    """Describes the most recent IRS tax form on file.

    ``None`` at the parent (:class:`TaxProfileDTO`) level when no form has
    been submitted yet.

    Fields
    ------
    form_code : FormCode
        The IRS form code — ``"W-9"`` or ``"W-8BEN"``.

    signed_date : str | None
        Date the form was signed in ISO 8601 format (``YYYY-MM-DD``).
        ``None`` when the signed date was not captured or is illegible.

    valid_through : str | None
        The computed expiry date in ``YYYY-MM-DD`` format.  Only applicable
        to W-8BEN forms (valid through 31 December of the third calendar year
        following the year of signing).  Always ``None`` for W-9 forms (W-9
        certifications do not carry an automatic expiry date under IRS rules).

    is_expired : bool
        ``True`` when ``valid_through`` is in the past relative to the
        current date.  Always ``False`` for W-9 forms (no automatic expiry).
        ``False`` when ``valid_through`` is ``None`` and expiry cannot be
        determined.
    """

    form_code: FormCode
    signed_date: Optional[str] = None
    valid_through: Optional[str] = None
    is_expired: bool = False


@dataclass
class TreatyStatusDTO:
    """US tax treaty status section of a :class:`TaxProfileDTO`.

    For **US persons** all fields carry their "not applicable" defaults:
    ``claim_status = TreatyClaimStatus.NOT_APPLICABLE``,
    ``has_treaty = False``, ``treaty_country = None``,
    ``applied_withholding_rate_pct = None``.

    Fields
    ------
    claim_status : TreatyClaimStatus
        Machine-readable outcome of the W-8BEN Part II treaty claim review.
        See :class:`TreatyClaimStatus` for allowed values and their meanings.

    has_treaty : bool
        ``True`` when the investor's country of citizenship has an active US
        income-tax treaty.  Always ``False`` for US persons and for foreign
        investors from non-treaty countries.

    treaty_country : str | None
        The country cited in the W-8BEN Part II treaty claim (line 9).
        ``None`` when no claim was made, when the claim is not applicable,
        or for US persons.

    applied_withholding_rate_pct : float | None
        The reduced withholding rate from the applicable tax treaty, expressed
        as a percentage (e.g. ``15.0`` for 15 %).  Present only when
        ``claim_status`` is ``"CLAIMED_AND_VALIDATED"``.  ``None`` in all
        other cases — even when ``has_treaty`` is ``True`` but the investor
        has not (yet) completed Part II.
    """

    claim_status: TreatyClaimStatus = TreatyClaimStatus.NOT_APPLICABLE
    has_treaty: bool = False
    treaty_country: Optional[str] = None
    applied_withholding_rate_pct: Optional[float] = None


# ---------------------------------------------------------------------------
# Top-level contract
# ---------------------------------------------------------------------------


@dataclass
class TaxProfileDTO:
    """Unified tax profile — the **canonical output contract** of the tax
    onboarding pipeline.

    This is the single object that downstream workflows (distribution
    characterization, withholding calculation, document generation, compliance
    reporting) must consume.  It aggregates investor identity, tax-residency
    data, form-on-file state, treaty status, and the overall profile readiness
    into one coherent, versioned data structure.

    .. important::
       This schema is the **authoritative contract** for the tax onboarding
       pipeline.  Any field rename, type change, or removal of an allowed enum
       value is a breaking change.  See ``docs/tax_profile_schema.md`` for the
       full field reference, allowed values, worked examples, and migration
       guidance.

    Fields
    ------
    investor : InvestorDTO
        Legal identity — name, address, investor type, home country.

    tax_residency : TaxResidencyDTO
        Tax-residency details — country of citizenship, foreign TIN, US-person
        flag.

    tax_status : TaxStatusSummaryDTO
        Stored verification state of the investor profile
        (``PENDING`` / ``VERIFIED`` / ``EXPIRED`` / ``MISSING``).

    form_on_file : FormOnFileDTO | None
        Most recent IRS tax form on file and its validity window.
        ``None`` when the investor has never submitted a form.

    treaty_status : TreatyStatusDTO
        US tax treaty claim status and applicable withholding rate (foreign
        investors only; defaults to "NOT_APPLICABLE" for US persons).

    withholding_rate : float | None
        Applicable US withholding rate as a percentage:

        * US persons — ``None`` (backup withholding under the W-9
          certification framework does not use this field).
        * Foreign persons, treaty claim validated — the reduced treaty rate
          (e.g. ``15.0``), taken from ``treaty_status.applied_withholding_rate_pct``.
        * Foreign persons, no treaty or claim not validated — the statutory
          NRA rate of ``30.0`` (IRC § 1441).

    status : ProfileStatus
        Overall readiness of the profile: ``"READY"`` / ``"REVIEW_REQUIRED"``
        / ``"INCOMPLETE"``.

    status_reason : str
        Human-readable explanation of ``status``.  Empty string when
        ``status`` is ``"READY"``.
    """

    investor: InvestorDTO
    tax_residency: TaxResidencyDTO
    tax_status: TaxStatusSummaryDTO
    form_on_file: Optional[FormOnFileDTO]
    treaty_status: TreatyStatusDTO
    withholding_rate: Optional[float]
    status: ProfileStatus
    status_reason: str = field(default="")
