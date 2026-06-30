"""HTTP controller for tax form determination and field normalization.

Thin layer: validate input -> call use case -> serialize output.
Business rules are never evaluated here.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from src.application.dto.tax_form_dto import (
    DetermineFormDTO,
    W8BENFieldsDTO,
    W9FieldsDTO,
)
from src.application.exceptions import InvalidFormFieldsError, UnrecognizedInvestorTypeError
from src.application.use_cases.determine_required_form import DetermineRequiredFormUseCase
from src.application.use_cases.normalize_form_fields import NormalizeFormFieldsUseCase
from src.interfaces.api.schemas import (
    DetermineFormRequest,
    DetermineFormResponse,
    ParsedFormFieldsResponse,
    W8BENFieldsRequest,
    W9FieldsRequest,
)

router = APIRouter(prefix="/tax-forms", tags=["tax-forms"])

# These use cases have no infrastructure dependency — instantiate directly.
_determine_use_case = DetermineRequiredFormUseCase()
_normalize_use_case = NormalizeFormFieldsUseCase()


@router.post(
    "/required",
    response_model=DetermineFormResponse,
    status_code=status.HTTP_200_OK,
    summary="Determine the required tax form for an investor",
    description=(
        "Returns 'W-9' for US persons and 'W-8BEN' for foreign persons. "
        "Raises 422 if investor_type is missing or unrecognized."
    ),
)
def determine_required_form(payload: DetermineFormRequest) -> DetermineFormResponse:
    try:
        result = _determine_use_case.execute(DetermineFormDTO(investor_type=payload.investor_type))
    except UnrecognizedInvestorTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return DetermineFormResponse(**result.__dict__)


@router.post(
    "/parse-json/w9",
    response_model=ParsedFormFieldsResponse,
    status_code=status.HTTP_200_OK,
    summary="Normalize W-9 JSON fields into the intermediate representation",
    description=(
        "Accepts raw W-9 form fields as JSON and returns the same normalized "
        "intermediate representation that the PDF extraction path produces. "
        "Useful for testing downstream validation without running PDF extraction. "
        "Raises 422 if required fields are absent or tin_type is not 'SSN'/'EIN'."
    ),
)
def parse_w9_fields(payload: W9FieldsRequest) -> ParsedFormFieldsResponse:
    try:
        result = _normalize_use_case.execute_w9(
            W9FieldsDTO(
                name=payload.name,
                federal_tax_classification=payload.federal_tax_classification,
                address=payload.address,
                city_state_zip=payload.city_state_zip,
                tin=payload.tin,
                tin_type=payload.tin_type,
                business_name=payload.business_name,
                exempt_payee_code=payload.exempt_payee_code,
                exemption_from_fatca_code=payload.exemption_from_fatca_code,
                account_numbers=payload.account_numbers,
            )
        )
    except InvalidFormFieldsError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return ParsedFormFieldsResponse(**result.__dict__)


@router.post(
    "/parse-json/w8ben",
    response_model=ParsedFormFieldsResponse,
    status_code=status.HTTP_200_OK,
    summary="Normalize W-8BEN JSON fields into the intermediate representation",
    description=(
        "Accepts raw W-8BEN form fields as JSON and returns the same normalized "
        "intermediate representation that the PDF extraction path produces. "
        "Useful for testing downstream validation without running PDF extraction. "
        "Raises 422 if required fields are absent or identification number "
        "constraints are not satisfied."
    ),
)
def parse_w8ben_fields(payload: W8BENFieldsRequest) -> ParsedFormFieldsResponse:
    try:
        result = _normalize_use_case.execute_w8ben(
            W8BENFieldsDTO(
                name=payload.name,
                country_of_citizenship=payload.country_of_citizenship,
                permanent_address=payload.permanent_address,
                permanent_address_city_country=payload.permanent_address_city_country,
                mailing_address=payload.mailing_address,
                mailing_address_city_country=payload.mailing_address_city_country,
                us_tin=payload.us_tin,
                foreign_tin=payload.foreign_tin,
                ftin_not_required=payload.ftin_not_required,
                reference_numbers=payload.reference_numbers,
                date_of_birth=payload.date_of_birth,
                treaty_country=payload.treaty_country,
                treaty_article=payload.treaty_article,
                withholding_rate=payload.withholding_rate,
                income_type=payload.income_type,
                treaty_conditions=payload.treaty_conditions,
            )
        )
    except InvalidFormFieldsError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return ParsedFormFieldsResponse(**result.__dict__)
