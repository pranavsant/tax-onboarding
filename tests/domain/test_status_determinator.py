"""Tests for :class:`~src.domain.services.status_determinator.StatusDeterminator`.

These tests exercise the domain service directly, verifying all three status
outcomes (READY, REVIEW_REQUIRED, INCOMPLETE) and the acceptance criterion
that *every* failing check contributes its reason to the final ``status_reason``
string when multiple issues exist simultaneously.
"""
from __future__ import annotations

import pytest

from src.application.dto.tax_form_dto import (
    ExpirationValidationResultDTO,
    MismatchDetailDTO,
    ProfileMismatchResultDTO,
    SignatureValidationResultDTO,
    TINValidationResultDTO,
    TreatyClaimValidationResultDTO,
)
from src.application.dto.tax_profile_dto import ProfileStatus
from src.domain.services.status_determinator import StatusDeterminator, StatusDeterminationResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _passing_sig() -> SignatureValidationResultDTO:
    return SignatureValidationResultDTO(passed=True, reason="")


def _failing_sig(reason: str = "Signature is missing from the form.") -> SignatureValidationResultDTO:
    return SignatureValidationResultDTO(passed=False, reason=reason)


def _passing_tin() -> TINValidationResultDTO:
    return TINValidationResultDTO(passed=True, reason="")


def _failing_tin(reason: str = "TIN format is invalid.") -> TINValidationResultDTO:
    return TINValidationResultDTO(passed=False, reason=reason)


def _passing_expiry() -> ExpirationValidationResultDTO:
    return ExpirationValidationResultDTO(passed=True, reason="", valid_through="2026-12-31")


def _failing_expiry(reason: str = "W-8BEN expired on 2023-12-31.") -> ExpirationValidationResultDTO:
    return ExpirationValidationResultDTO(passed=False, reason=reason, valid_through="2023-12-31")


def _passing_treaty() -> TreatyClaimValidationResultDTO:
    return TreatyClaimValidationResultDTO(passed=True, reason="", applied_withholding_rate_pct=15.0)


def _failing_treaty(reason: str = "Treaty claim is missing from W-8BEN Part II.") -> TreatyClaimValidationResultDTO:
    return TreatyClaimValidationResultDTO(passed=False, reason=reason)


def _no_mismatches() -> ProfileMismatchResultDTO:
    return ProfileMismatchResultDTO(has_mismatches=False, mismatches=[])


def _one_mismatch(reason: str = "Name on form does not match profile.") -> ProfileMismatchResultDTO:
    return ProfileMismatchResultDTO(
        has_mismatches=True,
        mismatches=[
            MismatchDetailDTO(
                field="name",
                profile_value="John Smith",
                submitted_value="Jon Smith",
                reason=reason,
            )
        ],
    )


def _two_mismatches() -> ProfileMismatchResultDTO:
    return ProfileMismatchResultDTO(
        has_mismatches=True,
        mismatches=[
            MismatchDetailDTO(
                field="name",
                profile_value="John Smith",
                submitted_value="Jon Smith",
                reason="Name on form 'Jon Smith' does not match profile 'John Smith'.",
            ),
            MismatchDetailDTO(
                field="address",
                profile_value="123 Main St",
                submitted_value="456 Elm Ave",
                reason="Address on form '456 Elm Ave' does not match profile '123 Main St'.",
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Return-type contract
# ---------------------------------------------------------------------------


class TestReturnType:
    def test_returns_status_determination_result(self):
        result = StatusDeterminator.determine(form_submitted=False, is_us_person=True)
        assert isinstance(result, StatusDeterminationResult)

    def test_result_is_frozen(self):
        result = StatusDeterminator.determine(form_submitted=False, is_us_person=True)
        with pytest.raises((AttributeError, TypeError)):
            result.status = ProfileStatus.READY  # type: ignore[misc]


# ---------------------------------------------------------------------------
# INCOMPLETE — no form submitted
# ---------------------------------------------------------------------------


class TestIncomplete:
    def test_no_form_us_person_returns_incomplete(self):
        result = StatusDeterminator.determine(form_submitted=False, is_us_person=True)
        assert result.status == ProfileStatus.INCOMPLETE

    def test_no_form_foreign_person_returns_incomplete(self):
        result = StatusDeterminator.determine(form_submitted=False, is_us_person=False)
        assert result.status == ProfileStatus.INCOMPLETE

    def test_no_form_us_person_names_w9_in_reason(self):
        result = StatusDeterminator.determine(form_submitted=False, is_us_person=True)
        assert "W-9" in result.status_reason
        assert result.status_reason  # non-empty

    def test_no_form_foreign_person_names_w8ben_in_reason(self):
        result = StatusDeterminator.determine(form_submitted=False, is_us_person=False)
        assert "W-8BEN" in result.status_reason
        assert result.status_reason  # non-empty

    def test_incomplete_ignores_validation_results(self):
        """INCOMPLETE must short-circuit — validation results should be ignored."""
        result = StatusDeterminator.determine(
            form_submitted=False,
            is_us_person=True,
            signature_result=_passing_sig(),
            tin_result=_passing_tin(),
            mismatch_result=_no_mismatches(),
        )
        assert result.status == ProfileStatus.INCOMPLETE

    def test_incomplete_ignores_failing_validation_results(self):
        """Even failing checks must be ignored when no form is on file."""
        result = StatusDeterminator.determine(
            form_submitted=False,
            is_us_person=False,
            signature_result=_failing_sig(),
            tin_result=_failing_tin(),
            expiration_result=_failing_expiry(),
            treaty_claim_result=_failing_treaty(),
            mismatch_result=_one_mismatch(),
        )
        assert result.status == ProfileStatus.INCOMPLETE


# ---------------------------------------------------------------------------
# READY — all checks pass
# ---------------------------------------------------------------------------


class TestReady:
    def test_all_passing_checks_returns_ready(self):
        result = StatusDeterminator.determine(
            form_submitted=True,
            is_us_person=True,
            signature_result=_passing_sig(),
            tin_result=_passing_tin(),
            mismatch_result=_no_mismatches(),
        )
        assert result.status == ProfileStatus.READY

    def test_ready_has_empty_status_reason(self):
        result = StatusDeterminator.determine(
            form_submitted=True,
            is_us_person=True,
            signature_result=_passing_sig(),
            tin_result=_passing_tin(),
            mismatch_result=_no_mismatches(),
        )
        assert result.status_reason == ""

    def test_no_checks_supplied_returns_ready(self):
        """When no checks are passed, there are no failures — status is READY."""
        result = StatusDeterminator.determine(form_submitted=True, is_us_person=True)
        assert result.status == ProfileStatus.READY

    def test_w8ben_all_passing_returns_ready(self):
        result = StatusDeterminator.determine(
            form_submitted=True,
            is_us_person=False,
            signature_result=_passing_sig(),
            tin_result=_passing_tin(),
            expiration_result=_passing_expiry(),
            treaty_claim_result=_passing_treaty(),
            mismatch_result=_no_mismatches(),
        )
        assert result.status == ProfileStatus.READY
        assert result.status_reason == ""

    def test_none_checks_are_skipped(self):
        """``None`` values for inapplicable checks must not cause failures."""
        result = StatusDeterminator.determine(
            form_submitted=True,
            is_us_person=True,
            signature_result=_passing_sig(),
            tin_result=_passing_tin(),
            expiration_result=None,    # W-9 — no expiry check
            treaty_claim_result=None,  # W-9 — no treaty check
            mismatch_result=None,      # skipped
        )
        assert result.status == ProfileStatus.READY


# ---------------------------------------------------------------------------
# REVIEW_REQUIRED — individual check failures
# ---------------------------------------------------------------------------


class TestReviewRequiredSingleIssue:
    def test_failing_signature_returns_review_required(self):
        result = StatusDeterminator.determine(
            form_submitted=True,
            is_us_person=True,
            signature_result=_failing_sig("Signature is missing."),
            tin_result=_passing_tin(),
            mismatch_result=_no_mismatches(),
        )
        assert result.status == ProfileStatus.REVIEW_REQUIRED

    def test_failing_signature_reason_in_status_reason(self):
        sig_reason = "Signature is missing from the form."
        result = StatusDeterminator.determine(
            form_submitted=True,
            is_us_person=True,
            signature_result=_failing_sig(sig_reason),
        )
        assert sig_reason in result.status_reason

    def test_failing_tin_returns_review_required(self):
        result = StatusDeterminator.determine(
            form_submitted=True,
            is_us_person=True,
            signature_result=_passing_sig(),
            tin_result=_failing_tin("TIN '12345' is not a valid SSN or EIN."),
            mismatch_result=_no_mismatches(),
        )
        assert result.status == ProfileStatus.REVIEW_REQUIRED

    def test_failing_tin_reason_in_status_reason(self):
        tin_reason = "TIN '12345' is not a valid SSN or EIN."
        result = StatusDeterminator.determine(
            form_submitted=True,
            is_us_person=True,
            tin_result=_failing_tin(tin_reason),
        )
        assert tin_reason in result.status_reason

    def test_failing_expiration_returns_review_required(self):
        result = StatusDeterminator.determine(
            form_submitted=True,
            is_us_person=False,
            expiration_result=_failing_expiry("W-8BEN expired on 2023-12-31."),
        )
        assert result.status == ProfileStatus.REVIEW_REQUIRED

    def test_failing_expiration_reason_in_status_reason(self):
        exp_reason = "W-8BEN expired on 2023-12-31. A new form must be collected."
        result = StatusDeterminator.determine(
            form_submitted=True,
            is_us_person=False,
            expiration_result=_failing_expiry(exp_reason),
        )
        assert exp_reason in result.status_reason

    def test_failing_treaty_claim_returns_review_required(self):
        result = StatusDeterminator.determine(
            form_submitted=True,
            is_us_person=False,
            treaty_claim_result=_failing_treaty("Treaty claim Part II is blank."),
        )
        assert result.status == ProfileStatus.REVIEW_REQUIRED

    def test_failing_treaty_claim_reason_in_status_reason(self):
        treaty_reason = "Treaty claim Part II is blank despite treaty eligibility."
        result = StatusDeterminator.determine(
            form_submitted=True,
            is_us_person=False,
            treaty_claim_result=_failing_treaty(treaty_reason),
        )
        assert treaty_reason in result.status_reason

    def test_one_mismatch_returns_review_required(self):
        result = StatusDeterminator.determine(
            form_submitted=True,
            is_us_person=True,
            mismatch_result=_one_mismatch("Name on form does not match profile."),
        )
        assert result.status == ProfileStatus.REVIEW_REQUIRED

    def test_one_mismatch_reason_in_status_reason(self):
        mismatch_reason = "Name on form 'Jon Smith' does not match profile 'John Smith'."
        result = StatusDeterminator.determine(
            form_submitted=True,
            is_us_person=True,
            mismatch_result=_one_mismatch(mismatch_reason),
        )
        assert mismatch_reason in result.status_reason


# ---------------------------------------------------------------------------
# REVIEW_REQUIRED — multiple simultaneous issues (acceptance criterion)
# ---------------------------------------------------------------------------


class TestReviewRequiredMultipleIssues:
    def test_two_failing_checks_both_reasons_present(self):
        """Acceptance criterion: all failures are captured, not just the first."""
        sig_reason = "Signature is missing from the form."
        tin_reason = "TIN is not a valid SSN format."
        result = StatusDeterminator.determine(
            form_submitted=True,
            is_us_person=True,
            signature_result=_failing_sig(sig_reason),
            tin_result=_failing_tin(tin_reason),
            mismatch_result=_no_mismatches(),
        )
        assert result.status == ProfileStatus.REVIEW_REQUIRED
        assert sig_reason in result.status_reason
        assert tin_reason in result.status_reason

    def test_two_mismatches_both_reasons_present(self):
        """Each mismatch field contributes its own reason."""
        result = StatusDeterminator.determine(
            form_submitted=True,
            is_us_person=True,
            mismatch_result=_two_mismatches(),
        )
        assert result.status == ProfileStatus.REVIEW_REQUIRED
        assert "Name on form" in result.status_reason
        assert "Address on form" in result.status_reason

    def test_all_five_checks_failing_all_reasons_present(self):
        """When every check fails, every reason must appear in status_reason."""
        sig_reason = "Signature is missing."
        tin_reason = "TIN format is invalid."
        exp_reason = "W-8BEN expired on 2023-12-31."
        treaty_reason = "Treaty claim is blank."
        name_reason = "Name on form 'A' does not match profile 'B'."
        address_reason = "Address on form 'X' does not match profile 'Y'."

        result = StatusDeterminator.determine(
            form_submitted=True,
            is_us_person=False,
            signature_result=_failing_sig(sig_reason),
            tin_result=_failing_tin(tin_reason),
            expiration_result=_failing_expiry(exp_reason),
            treaty_claim_result=_failing_treaty(treaty_reason),
            mismatch_result=ProfileMismatchResultDTO(
                has_mismatches=True,
                mismatches=[
                    MismatchDetailDTO("name", "B", "A", name_reason),
                    MismatchDetailDTO("address", "Y", "X", address_reason),
                ],
            ),
        )
        assert result.status == ProfileStatus.REVIEW_REQUIRED
        for expected in [sig_reason, tin_reason, exp_reason, treaty_reason, name_reason, address_reason]:
            assert expected in result.status_reason, (
                f"Expected '{expected}' in status_reason but got: '{result.status_reason}'"
            )

    def test_reasons_joined_with_pipe_separator(self):
        """Multiple reasons must be joined with ' | '."""
        sig_reason = "Signature is missing."
        tin_reason = "TIN is invalid."
        result = StatusDeterminator.determine(
            form_submitted=True,
            is_us_person=True,
            signature_result=_failing_sig(sig_reason),
            tin_result=_failing_tin(tin_reason),
        )
        assert " | " in result.status_reason

    def test_single_failing_check_no_pipe_separator(self):
        """A single failure must not have a trailing ' | ' separator."""
        sig_reason = "Signature is missing."
        result = StatusDeterminator.determine(
            form_submitted=True,
            is_us_person=True,
            signature_result=_failing_sig(sig_reason),
        )
        assert result.status_reason == sig_reason

    def test_sig_and_mismatch_reasons_both_present(self):
        """Mix of validator failure and mismatch failure are both captured."""
        sig_reason = "Signed date is not a valid date."
        mismatch_reason = "Name on form 'Jon' does not match profile 'John'."
        result = StatusDeterminator.determine(
            form_submitted=True,
            is_us_person=True,
            signature_result=_failing_sig(sig_reason),
            mismatch_result=_one_mismatch(mismatch_reason),
        )
        assert result.status == ProfileStatus.REVIEW_REQUIRED
        assert sig_reason in result.status_reason
        assert mismatch_reason in result.status_reason

    def test_passing_checks_do_not_contribute_to_reason(self):
        """Passing checks must not add anything to status_reason."""
        tin_reason = "TIN is invalid."
        result = StatusDeterminator.determine(
            form_submitted=True,
            is_us_person=True,
            signature_result=_passing_sig(),   # passes — silent
            tin_result=_failing_tin(tin_reason),
            mismatch_result=_no_mismatches(),  # passes — silent
        )
        assert result.status_reason == tin_reason


# ---------------------------------------------------------------------------
# Priority: INCOMPLETE beats REVIEW_REQUIRED
# ---------------------------------------------------------------------------


class TestPriority:
    def test_incomplete_has_higher_priority_than_review_required(self):
        """INCOMPLETE must be returned even when every validation check fails."""
        result = StatusDeterminator.determine(
            form_submitted=False,
            is_us_person=False,
            signature_result=_failing_sig(),
            tin_result=_failing_tin(),
            expiration_result=_failing_expiry(),
            treaty_claim_result=_failing_treaty(),
            mismatch_result=_two_mismatches(),
        )
        assert result.status == ProfileStatus.INCOMPLETE

    def test_incomplete_reason_names_required_form_not_validation_failures(self):
        """The INCOMPLETE reason must mention the required form, not the
        individual validation failures that were passed in."""
        result = StatusDeterminator.determine(
            form_submitted=False,
            is_us_person=False,
            signature_result=_failing_sig("Signature is missing."),
        )
        assert "W-8BEN" in result.status_reason
        assert "Signature is missing." not in result.status_reason
