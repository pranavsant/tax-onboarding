# Tax Profile Schema — Canonical Contract

> **⚠ CONTRACT NOTICE**
>
> This document and the companion Python module
> `src/application/dto/tax_profile_dto.py` together define the **canonical
> output contract** for the tax onboarding pipeline.  All downstream workflows
> — distribution characterization, withholding calculation, document
> generation, and compliance reporting — **must** consume `TaxProfileDTO` as
> their source of truth for an investor's current tax standing.
>
> Any field rename, type change, addition or removal of an allowed enum value
> is a **breaking change** and requires coordinated updates across all
> consumers.  Treat this schema the same way you would treat a versioned
> REST API contract.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Top-level: `TaxProfileDTO`](#2-top-level-taxprofiledto)
3. [Sub-object: `InvestorDTO`](#3-sub-object-investordto)
4. [Sub-object: `TaxResidencyDTO`](#4-sub-object-taxresidencydto)
5. [Sub-object: `TaxStatusSummaryDTO`](#5-sub-object-taxstatussummarydto)
6. [Sub-object: `FormOnFileDTO`](#6-sub-object-formondfiledto)
7. [Sub-object: `TreatyStatusDTO`](#7-sub-object-treatystatusdto)
8. [Enumerations](#8-enumerations)
9. [Worked Examples (Seeded Personas)](#9-worked-examples-seeded-personas)
10. [Validation Use-Case Output Map](#10-validation-use-case-output-map)
11. [Design Decisions](#11-design-decisions)

---

## 1. Overview

`TaxProfileDTO` is the single object emitted by the (forthcoming)
`AssembleTaxProfileUseCase`.  It merges:

- **Investor identity** stored in the `investor_profiles` database table.
- **Form metadata** from the most recently submitted W-9 or W-8BEN.
- **Validation results** produced by the existing validator use cases:
  - `ValidateSignatureUseCase`
  - `ValidateTINUseCase`
  - `ValidateExpirationUseCase`
  - `ValidateTreatyClaimUseCase`
  - `DetectProfileMismatchUseCase`

The schema is defined as Python dataclasses in
`src/application/dto/tax_profile_dto.py`.  No infrastructure types, ORM
models, or Pydantic models appear in that file; it is a pure application-layer
DTO, consistent with the Clean Architecture conventions of this project.

---

## 2. Top-level: `TaxProfileDTO`

**Python class:** `src.application.dto.tax_profile_dto.TaxProfileDTO`

| Field | Type | Nullable | Description |
|---|---|---|---|
| `investor` | `InvestorDTO` | No | Legal identity section. |
| `tax_residency` | `TaxResidencyDTO` | No | Tax-residency details. |
| `tax_status` | `TaxStatusSummaryDTO` | No | Stored profile verification state. |
| `form_on_file` | `FormOnFileDTO \| None` | Yes | Most recent IRS tax form on file. `None` when no form has ever been submitted. |
| `treaty_status` | `TreatyStatusDTO` | No | US tax treaty claim status and withholding rate. |
| `withholding_rate` | `float \| None` | Yes | Applicable US withholding rate as a percentage. See rules below. |
| `status` | `ProfileStatus` | No | Overall readiness: `"READY"` / `"REVIEW_REQUIRED"` / `"INCOMPLETE"`. |
| `status_reason` | `str` | No | Human-readable explanation of `status`. Empty string when `status == "READY"`. |

### `withholding_rate` derivation rules

| Investor type | Condition | Value |
|---|---|---|
| US person (`us_person`) | Always | `None` — backup withholding rules from W-9 certification apply; this field is not used. |
| Foreign person | `treaty_status.claim_status == "CLAIMED_AND_VALIDATED"` | Reduced treaty rate (e.g. `15.0` for Germany). |
| Foreign person | All other treaty claim statuses | `30.0` — statutory NRA withholding rate (IRC § 1441). |

---

## 3. Sub-object: `InvestorDTO`

**Python class:** `src.application.dto.tax_profile_dto.InvestorDTO`

| Field | Type | Nullable | Allowed values / format | Description |
|---|---|---|---|---|
| `full_name` | `str` | No | Non-empty string | Legal name as shown on tax documents. |
| `address` | `str` | No | Non-empty string | Primary address on file. For W-9 filers: form box 5. For W-8BEN filers: permanent residence (line 3). |
| `investor_type` | `InvestorTypeValue` | No | `"us_person"`, `"foreign_person"` | IRS classification for withholding purposes. |
| `country` | `str \| None` | Yes | Country name string | Country of residence/citizenship. Required for foreign investors; `None` for US investors when not explicitly recorded. |

---

## 4. Sub-object: `TaxResidencyDTO`

**Python class:** `src.application.dto.tax_profile_dto.TaxResidencyDTO`

| Field | Type | Nullable | Allowed values / format | Description |
|---|---|---|---|---|
| `is_us_person` | `bool` | No | `true`, `false` | `true` when `investor_type == "us_person"`. |
| `country_of_citizenship` | `str \| None` | Yes | Country name string | Country of citizenship from W-8BEN line 2. `None` for US persons. |
| `foreign_tin` | `str \| None` | Yes | Country-specific format (e.g. Brazilian CPF `219.871.330-44`) | Foreign taxpayer identification number from W-8BEN line 6a. `None` for US persons and for investors who checked the "FTIN not legally required" box. |
| `ftin_not_required` | `bool` | No | `true`, `false` | `true` when the investor checked W-8BEN line 6b. Always `false` for US persons. |

---

## 5. Sub-object: `TaxStatusSummaryDTO`

**Python class:** `src.application.dto.tax_profile_dto.TaxStatusSummaryDTO`

Reflects the **stored** verification state of the investor profile record
(as persisted in the database), not the live outcome of a specific form
submission.

| Field | Type | Nullable | Allowed values | Description |
|---|---|---|---|---|
| `current_status` | `str` | No | `"PENDING"`, `"VERIFIED"`, `"EXPIRED"`, `"MISSING"` | Verification state. See table below. |
| `status_detail` | `str` | No | Any string; empty when verified | Human-readable explanation. Empty string when `current_status == "VERIFIED"`. |

### `current_status` values

| Value | Meaning |
|---|---|
| `"PENDING"` | Form received but not yet reviewed/verified by operations. |
| `"VERIFIED"` | Form reviewed and currently valid on record. |
| `"EXPIRED"` | Form on file has passed its validity window (W-8BEN: 3 calendar years; W-9: as re-requested by the withholding agent). |
| `"MISSING"` | No form has ever been submitted for this investor. |

---

## 6. Sub-object: `FormOnFileDTO`

**Python class:** `src.application.dto.tax_profile_dto.FormOnFileDTO`

Present at `TaxProfileDTO.form_on_file` when a form exists; `None` when the
investor has never submitted a form (corresponds to `tax_status.current_status == "MISSING"`).

| Field | Type | Nullable | Allowed values / format | Description |
|---|---|---|---|---|
| `form_code` | `FormCode` | No | `"W-9"`, `"W-8BEN"` | IRS form identifier. |
| `signed_date` | `str \| None` | Yes | ISO 8601 date `YYYY-MM-DD` | Date the form was signed. `None` when the signed date was not captured or is illegible. |
| `valid_through` | `str \| None` | Yes | ISO 8601 date `YYYY-12-31` | Computed expiry date. Only applicable to W-8BEN forms (31 December of the 3rd calendar year after signing). Always `None` for W-9 forms. `None` when `signed_date` is absent or unparseable. |
| `is_expired` | `bool` | No | `true`, `false` | `true` when `valid_through` is in the past. Always `false` for W-9 forms. `false` when expiry cannot be determined. |

### W-8BEN expiry calculation

```
valid_through = date(year(signed_date) + 3, 12, 31)
```

Example: signed `2025-01-20` → `valid_through = "2028-12-31"`.

---

## 7. Sub-object: `TreatyStatusDTO`

**Python class:** `src.application.dto.tax_profile_dto.TreatyStatusDTO`

For **US persons**, all fields carry their "not applicable" defaults:
`claim_status = "NOT_APPLICABLE"`, `has_treaty = false`,
`treaty_country = null`, `applied_withholding_rate_pct = null`.

| Field | Type | Nullable | Allowed values | Description |
|---|---|---|---|---|
| `claim_status` | `TreatyClaimStatus` | No | See enum table in §8 | Machine-readable outcome of the W-8BEN Part II review. |
| `has_treaty` | `bool` | No | `true`, `false` | `true` when the investor's country of citizenship has an active US income-tax treaty. |
| `treaty_country` | `str \| None` | Yes | Country name string | Country cited in the W-8BEN Part II claim (line 9). `None` when not applicable or not claimed. |
| `applied_withholding_rate_pct` | `float \| None` | Yes | Positive float, e.g. `15.0` | Reduced withholding rate from the treaty table. Present only when `claim_status == "CLAIMED_AND_VALIDATED"`. `None` in all other cases. |

---

## 8. Enumerations

### `InvestorTypeValue`

| Value | Meaning |
|---|---|
| `"us_person"` | US citizen, resident alien, or domestic entity. Certifies on Form W-9. |
| `"foreign_person"` | Non-US beneficial owner. Certifies on Form W-8BEN (individuals). |

### `FormCode`

| Value | IRS Form | Applicable to |
|---|---|---|
| `"W-9"` | Request for TIN and Certification | US persons |
| `"W-8BEN"` | Certificate of Foreign Status (individuals) | Foreign individual investors |

### `TreatyClaimStatus`

| Value | Meaning | `withholding_rate` at parent level |
|---|---|---|
| `"NOT_APPLICABLE"` | Investor is a US person; treaty claims are irrelevant. | `None` |
| `"NO_TREATY"` | Foreign investor from a country with no active US treaty. Statutory 30 % NRA rate applies. | `30.0` |
| `"CLAIMED_AND_VALIDATED"` | Country has a treaty; W-8BEN Part II is complete and validated. Reduced rate applies. | Reduced rate (e.g. `15.0`) |
| `"TREATY_AVAILABLE_CLAIM_MISSING"` | Country has a treaty but Part II is blank. Investor may be eligible; flag for review. | `30.0` (reduced rate not yet applied) |
| `"CLAIM_INCOMPLETE"` | Part II partially filled; one or more mandatory fields missing (treaty country, article, or rate). Requires follow-up. | `30.0` (reduced rate not yet applied) |

### `ProfileStatus`

| Value | Meaning |
|---|---|
| `"READY"` | All validation checks passed. Profile cleared for downstream workflows. |
| `"REVIEW_REQUIRED"` | At least one check flagged an issue requiring human review (e.g. expired W-8BEN, treaty mismatch, profile discrepancy). Downstream workflows should pause. |
| `"INCOMPLETE"` | Mandatory information is missing (e.g. no form on file, required identity fields absent). Onboarding workflow must collect missing data. |

---

## 9. Worked Examples (Seeded Personas)

These four personas are seeded by `seed_investor_profiles.py` and represent
the primary reference cases against which the schema was validated.

### 9.1 James Whitfield — US person, verified W-9

```json
{
  "investor": {
    "full_name": "James Whitfield",
    "address": "84 Pinecrest Drive, Austin, TX 78701",
    "investor_type": "us_person",
    "country": null
  },
  "tax_residency": {
    "is_us_person": true,
    "country_of_citizenship": null,
    "foreign_tin": null,
    "ftin_not_required": false
  },
  "tax_status": {
    "current_status": "VERIFIED",
    "status_detail": ""
  },
  "form_on_file": {
    "form_code": "W-9",
    "signed_date": "2023-04-10",
    "valid_through": null,
    "is_expired": false
  },
  "treaty_status": {
    "claim_status": "NOT_APPLICABLE",
    "has_treaty": false,
    "treaty_country": null,
    "applied_withholding_rate_pct": null
  },
  "withholding_rate": null,
  "status": "READY",
  "status_reason": ""
}
```

> **Notes:** `withholding_rate` is `null` — US persons are subject to backup
> withholding under the W-9 certification framework, not the NRA withholding
> rate reflected in this field.  `form_on_file.valid_through` is `null`
> because W-9 forms do not carry an automatic expiry date.

---

### 9.2 Mariana Costa Ribeiro — Foreign investor (Brazil), expired W-8BEN, no treaty

```json
{
  "investor": {
    "full_name": "Mariana Costa Ribeiro",
    "address": "Rua das Margaridas, 112, Rio de Janeiro, Brazil",
    "investor_type": "foreign_person",
    "country": "Brazil"
  },
  "tax_residency": {
    "is_us_person": false,
    "country_of_citizenship": "Brazil",
    "foreign_tin": "987.654.321-00",
    "ftin_not_required": false
  },
  "tax_status": {
    "current_status": "EXPIRED",
    "status_detail": "W-8BEN on file expired. A new form must be collected."
  },
  "form_on_file": {
    "form_code": "W-8BEN",
    "signed_date": "2021-03-15",
    "valid_through": "2024-12-31",
    "is_expired": true
  },
  "treaty_status": {
    "claim_status": "NO_TREATY",
    "has_treaty": false,
    "treaty_country": null,
    "applied_withholding_rate_pct": null
  },
  "withholding_rate": 30.0,
  "status": "REVIEW_REQUIRED",
  "status_reason": "W-8BEN expired on 2024-12-31. A new certification must be collected before distributions are processed."
}
```

> **Notes:** Brazil has no active US income-tax treaty, so `treaty_status.claim_status`
> is `"NO_TREATY"` and `withholding_rate` is `30.0` (statutory NRA rate).
> The expired form triggers `status == "REVIEW_REQUIRED"`.

---

### 9.3 Robert Nguyen — US person, PENDING, no form on file

```json
{
  "investor": {
    "full_name": "Robert Nguyen",
    "address": "910 Lakeview Terrace, Seattle, WA 98101",
    "investor_type": "us_person",
    "country": null
  },
  "tax_residency": {
    "is_us_person": true,
    "country_of_citizenship": null,
    "foreign_tin": null,
    "ftin_not_required": false
  },
  "tax_status": {
    "current_status": "PENDING",
    "status_detail": "W-9 has been requested but not yet received."
  },
  "form_on_file": null,
  "treaty_status": {
    "claim_status": "NOT_APPLICABLE",
    "has_treaty": false,
    "treaty_country": null,
    "applied_withholding_rate_pct": null
  },
  "withholding_rate": null,
  "status": "INCOMPLETE",
  "status_reason": "No W-9 on file. Investor must submit Form W-9 before onboarding can be completed."
}
```

> **Notes:** `form_on_file` is `null` because no form has been submitted yet.
> `status` is `"INCOMPLETE"` — downstream workflows must pause until the
> W-9 is received and verified.

---

### 9.4 Ingrid Weber — Foreign investor (Germany), verified W-8BEN, treaty claimed

```json
{
  "investor": {
    "full_name": "Ingrid Weber",
    "address": "Friedrichstraße 88, 10117 Berlin, Germany",
    "investor_type": "foreign_person",
    "country": "Germany"
  },
  "tax_residency": {
    "is_us_person": false,
    "country_of_citizenship": "Germany",
    "foreign_tin": "DE123456789",
    "ftin_not_required": false
  },
  "tax_status": {
    "current_status": "VERIFIED",
    "status_detail": ""
  },
  "form_on_file": {
    "form_code": "W-8BEN",
    "signed_date": "2024-07-22",
    "valid_through": "2027-12-31",
    "is_expired": false
  },
  "treaty_status": {
    "claim_status": "CLAIMED_AND_VALIDATED",
    "has_treaty": true,
    "treaty_country": "Germany",
    "applied_withholding_rate_pct": 15.0
  },
  "withholding_rate": 15.0,
  "status": "READY",
  "status_reason": ""
}
```

> **Notes:** Germany has an active US income-tax treaty.  Ingrid completed
> W-8BEN Part II, so `treaty_status.claim_status` is `"CLAIMED_AND_VALIDATED"`
> and the reduced 15 % rate is applied.  `withholding_rate == 15.0` is
> propagated directly from `treaty_status.applied_withholding_rate_pct`.

---

## 10. Validation Use-Case Output Map

This table shows how each existing validation use case's output DTO maps
into `TaxProfileDTO`.

| Use-Case output DTO | Field(s) mapped to in `TaxProfileDTO` |
|---|---|
| `SignatureValidationResultDTO.passed` | Contributes to `status` (failed → `REVIEW_REQUIRED`) and `status_reason`. |
| `SignatureValidationResultDTO.reason` | Appended to `status_reason` when `passed == false`. |
| `TINValidationResultDTO.passed` | Contributes to `status` (failed → `REVIEW_REQUIRED`) and `status_reason`. |
| `TINValidationResultDTO.reason` | Appended to `status_reason` when `passed == false`. |
| `ExpirationValidationResultDTO.passed` | Drives `form_on_file.is_expired` and contributes to `status`. |
| `ExpirationValidationResultDTO.valid_through` | Mapped to `form_on_file.valid_through`. |
| `ExpirationValidationResultDTO.reason` | Appended to `status_reason` when `passed == false`. |
| `TreatyClaimValidationResultDTO.passed` | Contributes to `status` (failed → `REVIEW_REQUIRED`). |
| `TreatyClaimValidationResultDTO.applied_withholding_rate_pct` | Mapped to `treaty_status.applied_withholding_rate_pct` and `withholding_rate`. |
| `TreatyClaimValidationResultDTO.reason` | Appended to `status_reason` when `passed == false`. |
| `ProfileMismatchResultDTO.has_mismatches` | Contributes to `status` (mismatch → `REVIEW_REQUIRED`). |
| `ProfileMismatchResultDTO.mismatches[].reason` | Appended to `status_reason` for each mismatch. |
| `InvestorProfile.full_name` | `investor.full_name` |
| `InvestorProfile.address` | `investor.address` |
| `InvestorProfile.investor_type` | `investor.investor_type`, `tax_residency.is_us_person` |
| `InvestorProfile.country` | `investor.country`, `tax_residency.country_of_citizenship` |
| `InvestorProfile.tax_status` | `tax_status.current_status` |
| `InvestorProfile.last_form_on_file` | `form_on_file.form_code` |
| `InvestorProfile.last_form_signed_date` | `form_on_file.signed_date` |
| `InvestorProfile.foreign_tin` | `tax_residency.foreign_tin` |
| `InvestorProfile.treaty_country` | `treaty_status.treaty_country` |

---

## 11. Design Decisions

### Why a separate `TaxProfileDTO` rather than extending existing DTOs?

The individual validation DTOs (`SignatureValidationResultDTO`, etc.) are
intentionally narrow — each captures a single check's outcome.  A downstream
workflow like withholding calculation must know *all* relevant facts about an
investor simultaneously.  A single aggregated object avoids having callers
assemble the picture themselves, which would scatter business logic across
workflow code.

### Why is `withholding_rate` at the top level and also in `TreatyStatusDTO`?

`treaty_status.applied_withholding_rate_pct` is the *treaty-specific* rate,
present only when a claim has been validated.  The top-level `withholding_rate`
is the *effective* rate to apply, which includes the statutory 30 % fallback
for non-treaty and unvalidated-claim cases.  Downstream callers that only need
to know "what rate do I apply?" can read `withholding_rate` without inspecting
`treaty_status`; callers auditing why a rate was chosen can inspect
`treaty_status.claim_status`.

### Why is `withholding_rate` `None` for US persons rather than a specific value?

US persons are subject to *backup withholding* (currently 24 %, IRC § 3406)
only in specific triggering conditions (e.g. failure to provide a TIN), not as
a standing deduction on all distributions.  Using `None` signals clearly that
this field does not govern US-person withholding and avoids encoding a rate
that may change independently.

### Why is `FormOnFileDTO.valid_through` always `None` for W-9?

W-9 certifications do not expire automatically.  A withholding agent may
*request* a new W-9 (e.g. if the taxpayer's name or TIN changes), but that is
a policy decision, not an IRS-mandated validity window.  Carrying `valid_through`
for W-9 would imply a false expiry guarantee.

### Why is `TaxStatusSummaryDTO` separate from `FormOnFileDTO`?

`tax_status.current_status` reflects the **database record** (set by an
operations team after reviewing a form) while `form_on_file.is_expired` is
the **computed** result of the expiration validator applied to the signed date.
These can diverge — e.g. a form may be computationally expired but the
database record not yet updated — and keeping them separate preserves that
distinction for audit purposes.
