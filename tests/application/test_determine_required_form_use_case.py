"""Unit tests for DetermineRequiredFormUseCase.

Verifies that the use case correctly translates investor_type strings to
form codes and that domain errors are surfaced as application exceptions.
"""
import pytest

from src.application.dto.tax_form_dto import DetermineFormDTO
from src.application.exceptions import UnrecognizedInvestorTypeError
from src.application.use_cases.determine_required_form import DetermineRequiredFormUseCase


class TestDetermineRequiredFormUseCaseSuccess:
    def setup_method(self) -> None:
        self.use_case = DetermineRequiredFormUseCase()

    def test_us_person_returns_w9(self) -> None:
        result = self.use_case.execute(DetermineFormDTO(investor_type="us_person"))
        assert result.required_form == "W-9"

    def test_us_person_result_contains_investor_type(self) -> None:
        result = self.use_case.execute(DetermineFormDTO(investor_type="us_person"))
        assert result.investor_type == "us_person"

    def test_foreign_person_returns_w8ben(self) -> None:
        result = self.use_case.execute(DetermineFormDTO(investor_type="foreign_person"))
        assert result.required_form == "W-8BEN"

    def test_foreign_person_result_contains_investor_type(self) -> None:
        result = self.use_case.execute(DetermineFormDTO(investor_type="foreign_person"))
        assert result.investor_type == "foreign_person"


class TestDetermineRequiredFormUseCaseErrors:
    def setup_method(self) -> None:
        self.use_case = DetermineRequiredFormUseCase()

    def test_empty_investor_type_raises_application_error(self) -> None:
        with pytest.raises(UnrecognizedInvestorTypeError):
            self.use_case.execute(DetermineFormDTO(investor_type=""))

    def test_unrecognized_investor_type_raises_application_error(self) -> None:
        with pytest.raises(UnrecognizedInvestorTypeError):
            self.use_case.execute(DetermineFormDTO(investor_type="partnership"))

    def test_error_is_application_layer_type(self) -> None:
        """Ensure the domain exception is translated, not leaked directly."""
        from src.application.exceptions import ApplicationError

        with pytest.raises(ApplicationError):
            self.use_case.execute(DetermineFormDTO(investor_type="unknown"))
