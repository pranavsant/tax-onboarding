"""Use case: normalize raw JSON form fields into the intermediate representation.

Accepts either a W-9 or W-8BEN field DTO and returns a
:class:`ParsedFormFieldsDTO` — the same normalized intermediate
representation that the PDF extraction path will also produce.  This
allows validation and downstream logic to be written once and tested
against JSON fixtures without running PDF extraction.

Domain errors are translated into application errors so the interfaces
layer never needs to import domain types directly.
"""
from __future__ import annotations

from src.application.dto.tax_form_dto import ParsedFormFieldsDTO, W8BENFieldsDTO, W9FieldsDTO
from src.application.exceptions import InvalidFormFieldsError
from src.domain.exceptions import InvalidFormFieldsError as DomainInvalidFormFieldsError
from src.domain.services.form_field_normalizer import FormFieldNormalizer


class NormalizeFormFieldsUseCase:
    """Convert raw form field DTOs into a :class:`ParsedFormFieldsDTO`.

    Instantiation requires no infrastructure dependency — the normalization
    is a pure domain rule.
    """

    def execute_w9(self, dto: W9FieldsDTO) -> ParsedFormFieldsDTO:
        """Validate and normalize a W-9 field payload.

        Args:
            dto: Raw W-9 fields as supplied by the caller.

        Returns:
            A fully populated :class:`ParsedFormFieldsDTO` with
            ``form_type='W-9'``.

        Raises:
            InvalidFormFieldsError: If required fields are absent or
                ``tin_type`` is not ``'SSN'`` or ``'EIN'``.
        """
        try:
            validated = FormFieldNormalizer.normalize_w9(
                name=dto.name,
                federal_tax_classification=dto.federal_tax_classification,
                address=dto.address,
                city_state_zip=dto.city_state_zip,
                tin=dto.tin,
                tin_type=dto.tin_type,
                business_name=dto.business_name,
                exempt_payee_code=dto.exempt_payee_code,
                exemption_from_fatca_code=dto.exemption_from_fatca_code,
                account_numbers=dto.account_numbers,
            )
        except DomainInvalidFormFieldsError as exc:
            raise InvalidFormFieldsError(str(exc)) from exc

        return ParsedFormFieldsDTO(
            form_type="W-9",
            name=validated.name,
            federal_tax_classification=validated.federal_tax_classification,
            address=validated.address,
            city_state_zip=validated.city_state_zip,
            tin=validated.tin,
            tin_type=validated.tin_type,
            business_name=validated.business_name,
            exempt_payee_code=validated.exempt_payee_code,
            exemption_from_fatca_code=validated.exemption_from_fatca_code,
            account_numbers=validated.account_numbers,
        )

    def execute_w8ben(self, dto: W8BENFieldsDTO) -> ParsedFormFieldsDTO:
        """Validate and normalize a W-8BEN field payload.

        Args:
            dto: Raw W-8BEN fields as supplied by the caller.

        Returns:
            A fully populated :class:`ParsedFormFieldsDTO` with
            ``form_type='W-8BEN'``.

        Raises:
            InvalidFormFieldsError: If required fields are absent or
                identification number constraints are not met.
        """
        try:
            validated = FormFieldNormalizer.normalize_w8ben(
                name=dto.name,
                country_of_citizenship=dto.country_of_citizenship,
                permanent_address=dto.permanent_address,
                permanent_address_city_country=dto.permanent_address_city_country,
                mailing_address=dto.mailing_address,
                mailing_address_city_country=dto.mailing_address_city_country,
                us_tin=dto.us_tin,
                foreign_tin=dto.foreign_tin,
                ftin_not_required=dto.ftin_not_required,
                reference_numbers=dto.reference_numbers,
                date_of_birth=dto.date_of_birth,
                treaty_country=dto.treaty_country,
                treaty_article=dto.treaty_article,
                withholding_rate=dto.withholding_rate,
                income_type=dto.income_type,
                treaty_conditions=dto.treaty_conditions,
            )
        except DomainInvalidFormFieldsError as exc:
            raise InvalidFormFieldsError(str(exc)) from exc

        return ParsedFormFieldsDTO(
            form_type="W-8BEN",
            name=validated.name,
            country_of_citizenship=validated.country_of_citizenship,
            permanent_address=validated.permanent_address,
            permanent_address_city_country=validated.permanent_address_city_country,
            mailing_address=validated.mailing_address,
            mailing_address_city_country=validated.mailing_address_city_country,
            us_tin=validated.us_tin,
            foreign_tin=validated.foreign_tin,
            ftin_not_required=validated.ftin_not_required,
            reference_numbers=validated.reference_numbers,
            date_of_birth=validated.date_of_birth,
            treaty_country=validated.treaty_country,
            treaty_article=validated.treaty_article,
            withholding_rate=validated.withholding_rate,
            income_type=validated.income_type,
            treaty_conditions=validated.treaty_conditions,
        )
