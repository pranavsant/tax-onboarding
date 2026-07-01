"""Tests for :class:`~src.application.use_cases.determine_status.DetermineStatusUseCase`.

These tests verify the use-case layer contracts — that inputs thread through
correctly to the domain service and that the result is wrapped in the correct
application-layer DTO.  Heavy scenario coverage lives in
``tests/domain/test_status_determinator.py``; this file focuses on the
application-layer surface.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.application.dto.tax_form_dto import (
    ExpirationValidationResultDTO,
    MismatchDetailDTO,
    ProfileMismatchResultDTO,
    SignatureValidationResultDTO,
    StatusDeterminationResultDTO,
    TINValidationResultDTO,
    TreatyClaimValidationResultDTO,
)
from src.application.dto.tax_profile_dto import ProfileStatus
from src.application.use_cases.determine_status import DetermineStatusUseCase


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def use_case() -> DetermineStatusUseCase:
    return DetermineStatusUseCase()


def _passing_sig() -> SignatureValidationResultDTO:
    return SignatureValidationResultDTO(passed=True, reason="")


def _failing_sig(reason: str = "Signature missing.") -> SignatureValidationResultDTO:
    return SignatureValidationResultDTO(passed=False, reason=reason)


def _passing_tin() -> TINValidationResultDTO:
    return TINValidationResultDTO(passed=True, reason="")


def _failing_tin(reason: str = "TIN invalid.") -> TINValidationResultDTO:
    return TINValidationResultDTO(passed=False, reason=reason)


def _passing_expiry() -> ExpirationValidationResultDTO:
    return ExpirationValidationResultDTO(passed=True, reason="", valid_through="2026-12-31")


def _failing_expiry(reason: str = "W-8BEN expired.") -> ExpirationValidationResultDTO:
    return ExpirationValidationResultDTO(passed=False, reason=reason, valid_through="2023-12-31")


def _passing_treaty() -> TreatyClaimValidationResultDTO:
    return TreatyClaimValidationResultDTO(passed=True, reason="", applied_withholding_rate_pct=15.0)


def _failing_treaty(reason: str = "Treaty claim missing.") -> TreatyClaimValidationResultDTO:
    return TreatyClaimValidationResultDTO(passed=False, reason=reason)


def _no_mismatches() -> ProfileMismatchResultDTO:
    return ProfileMismatchResultDTO(has_mismatches=False, mismatches=[])


def _one_mismatch(reason: str = "Name mismatch.") -> ProfileMismatchResultDTO:
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


# ---------------------------------------------------------------------------
# Return-type contract
# ---------------------------------------------------------------------------


class TestReturnType:
    def test_execute_returns_status_determination_result_dto(self, use_case):
        result = use_case.execute(form_submitted=False, is_us_person=True)
        assert isinstance(result, StatusDeterminationResultDTO)

    def test_result_status_is_profile_status_enum(self, use_case):
        result = use_case.execute(form_submitted=False, is_us_person=True)
        assert isinstance(result.status, ProfileStatus)

    def test_result_status_reason_is_str(self, use_case):
        result = use_case.execute(form_submitted=False, is_us_person=True)
        assert isinstance(result.status_reason, str)


# ---------------------------------------------------------------------------
# INCOMPLETE — no form submitted
# ---------------------------------------------------------------------------


class TestIncomplete:
    def test_no_form_us_person_returns_incomplete(self, use_case):
        result = use_case.execute(form_submitted=False, is_us_person=True)
        assert result.status == ProfileStatus.INCOMPLETE

    def test_no_form_foreign_person_returns_incomplete(self, use_case):
        result = use_case.execute(form_submitted=False, is_us_person=False)
        assert result.status == ProfileStatus.INCOMPLETE

    def test_no_form_us_person_status_reason_mentions_w9(self, use_case):
        result = use_case.execute(form_submitted=False, is_us_person=True)
        assert "W-9" in result.status_reason

    def test_no_form_foreign_person_status_reason_mentions_w8ben(self, use_case):
        result = use_case.execute(form_submitted=False, is_us_person=False)
        assert "W-8BEN" in result.status_reason

    def test_incomplete_status_reason_is_non_empty(self, use_case):
        result = use_case.execute(form_submitted=False, is_us_person=True)
        assert result.status_reason != ""


# ---------------------------------------------------------------------------
# READY — all checks pass
# ---------------------------------------------------------------------------


class TestReady:
    def test_all_passing_w9_returns_ready(self, use_case):
        result = use_case.execute(
            form_submitted=True,
            is_us_person=True,
            signature_result=_passing_sig(),
            tin_result=_passing_tin(),
            expiration_result=None,
            treaty_claim_result=None,
            mismatch_result=_no_mismatches(),
        )
        assert result.status == ProfileStatus.READY

    def test_ready_has_empty_status_reason(self, use_case):
        result = use_case.execute(
            form_submitted=True,
            is_us_person=True,
            signature_result=_passing_sig(),
            tin_result=_passing_tin(),
            mismatch_result=_no_mismatches(),
        )
        assert result.status_reason == ""

    def test_all_passing_w8ben_returns_ready(self, use_case):
        result = use_case.execute(
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

    def test_no_checks_supplied_returns_ready(self, use_case):
        """No checks supplied → no failures → READY."""
        result = use_case.execute(form_submitted=True, is_us_person=True)
        assert result.status == ProfileStatus.READY


# ---------------------------------------------------------------------------
# REVIEW_REQUIRED — individual check failures
# ---------------------------------------------------------------------------


class TestReviewRequiredSingleIssue:
    def test_failing_signature_returns_review_required(self, use_case):
        result = use_case.execute(
            form_submitted=True,
            is_us_person=True,
            signature_result=_failing_sig(),
        )
        assert result.status == ProfileStatus.REVIEW_REQUIRED

    def test_failing_signature_reason_propagated(self, use_case):
        reason = "Signature is absent."
        result = use_case.execute(
            form_submitted=True,
            is_us_person=True,
            signature_result=_failing_sig(reason),
        )
        assert reason in result.status_reason

    def test_failing_tin_returns_review_required(self, use_case):
        result = use_case.execute(
            form_submitted=True,
            is_us_person=True,
            tin_result=_failing_tin(),
        )
        assert result.status == ProfileStatus.REVIEW_REQUIRED

    def test_failing_expiration_returns_review_required(self, use_case):
        result = use_case.execute(
            form_submitted=True,
            is_us_person=False,
            expiration_result=_failing_expiry(),
        )
        assert result.status == ProfileStatus.REVIEW_REQUIRED

    def test_failing_treaty_claim_returns_review_required(self, use_case):
        result = use_case.execute(
            form_submitted=True,
            is_us_person=False,
            treaty_claim_result=_failing_treaty(),
        )
        assert result.status == ProfileStatus.REVIEW_REQUIRED

    def test_mismatch_returns_review_required(self, use_case):
        result = use_case.execute(
            form_submitted=True,
            is_us_person=True,
            mismatch_result=_one_mismatch(),
        )
        assert result.status == ProfileStatus.REVIEW_REQUIRED


# ---------------------------------------------------------------------------
# REVIEW_REQUIRED — multiple simultaneous issues
# ---------------------------------------------------------------------------


class TestReviewRequiredMultipleIssues:
    def test_two_failing_checks_both_reasons_in_status_reason(self, use_case):
        """Acceptance criterion: all failures captured, not just the first."""
        sig_reason = "Signature is missing."
        tin_reason = "TIN format is invalid."
        result = use_case.execute(
            form_submitted=True,
            is_us_person=True,
            signature_result=_failing_sig(sig_reason),
            tin_result=_failing_tin(tin_reason),
        )
        assert result.status == ProfileStatus.REVIEW_REQUIRED
        assert sig_reason in result.status_reason
        assert tin_reason in result.status_reason

    def test_all_five_checks_failing_all_reasons_present(self, use_case):
        sig_reason = "Signature absent."
        tin_reason = "TIN invalid."
        exp_reason = "Form expired."
        treaty_reason = "Treaty missing."
        name_reason = "Name mismatch."

        result = use_case.execute(
            form_submitted=True,
            is_us_person=False,
            signature_result=_failing_sig(sig_reason),
            tin_result=_failing_tin(tin_reason),
            expiration_result=_failing_expiry(exp_reason),
            treaty_claim_result=_failing_treaty(treaty_reason),
            mismatch_result=_one_mismatch(name_reason),
        )
        assert result.status == ProfileStatus.REVIEW_REQUIRED
        for r in [sig_reason, tin_reason, exp_reason, treaty_reason, name_reason]:
            assert r in result.status_reason, f"Missing: '{r}' in '{result.status_reason}'"

    def test_multiple_mismatches_all_reasons_present(self, use_case):
        name_reason = "Name on form 'A' does not match profile 'B'."
        address_reason = "Address on form 'X' does not match profile 'Y'."
        result = use_case.execute(
            form_submitted=True,
            is_us_person=True,
            mismatch_result=ProfileMismatchResultDTO(
                has_mismatches=True,
                mismatches=[
                    MismatchDetailDTO("name", "B", "A", name_reason),
                    MismatchDetailDTO("address", "Y", "X", address_reason),
                ],
            ),
        )
        assert name_reason in result.status_reason
        assert address_reason in result.status_reason

    def test_reasons_joined_with_pipe_separator(self, use_case):
        result = use_case.execute(
            form_submitted=True,
            is_us_person=True,
            signature_result=_failing_sig("Sig."),
            tin_result=_failing_tin("TIN."),
        )
        assert " | " in result.status_reason

    def test_single_failure_no_leading_or_trailing_pipe(self, use_case):
        reason = "Signature is missing."
        result = use_case.execute(
            form_submitted=True,
            is_us_person=True,
            signature_result=_failing_sig(reason),
        )
        assert result.status_reason == reason

    def test_passing_check_does_not_contribute_to_reason(self, use_case):
        """Passing checks must be silent."""
        tin_reason = "TIN invalid."
        result = use_case.execute(
            form_submitted=True,
            is_us_person=True,
            signature_result=_passing_sig(),
            tin_result=_failing_tin(tin_reason),
            mismatch_result=_no_mismatches(),
        )
        assert result.status_reason == tin_reason


# ---------------------------------------------------------------------------
# Delegation to domain service (structural test)
# ---------------------------------------------------------------------------


class TestDelegation:
    def test_execute_delegates_to_status_determinator(self, use_case):
        """The use case must delegate to StatusDeterminator rather than
        reimplementing status logic itself."""
        with patch(
            "src.application.use_cases.determine_status.StatusDeterminator.determine"
        ) as mock_determine:
            from src.domain.services.status_determinator import StatusDeterminationResult

            mock_determine.return_value = StatusDeterminationResult(
                status=ProfileStatus.READY,
                status_reason="",
            )

            sig = _passing_sig()
            tin = _passing_tin()
            result = use_case.execute(
                form_submitted=True,
                is_us_person=True,
                signature_result=sig,
                tin_result=tin,
            )

        mock_determine.assert_called_once_with(
            form_submitted=True,
            is_us_person=True,
            signature_result=sig,
            tin_result=tin,
            expiration_result=None,
            treaty_claim_result=None,
            mismatch_result=None,
        )
        assert isinstance(result, StatusDeterminationResultDTO)
        assert result.status == ProfileStatus.READY
        assert result.status_reason == ""
