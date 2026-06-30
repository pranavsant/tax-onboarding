"""Domain service that normalizes raw form field dicts into validated,
typed field sets.

Business rules enforced here:
  W-9
    - ``name``, ``federal_tax_classification``, ``address``,
      ``city_state_zip``, ``tin``, and ``tin_type`` are required.
    - ``tin_type`` must be ``'SSN'`` or ``'EIN'`` (case-insensitive).
    - ``tin`` must not be blank.

  W-8BEN
    - ``name``, ``country_of_citizenship``, ``permanent_address``, and
      ``permanent_address_city_country`` are required.
    - At least one identification number must be supplied: ``us_tin`` OR
      ``foreign_tin`` OR ``ftin_not_required`` must be set.

This logic lives in the domain layer because these are pure business rules
with no dependency on infrastructure or application concerns.
"""
from __future__ import annotations

from typing import Optional

from src.domain.exceptions import InvalidFormFieldsError


class W9Fields:
    """Validated, immutable W-9 field set produced by the normalizer."""

    VALID_TIN_TYPES = frozenset({"SSN", "EIN"})

    def __init__(
        self,
        *,
        name: str,
        federal_tax_classification: str,
        address: str,
        city_state_zip: str,
        tin: str,
        tin_type: str,
        business_name: Optional[str] = None,
        exempt_payee_code: Optional[str] = None,
        exemption_from_fatca_code: Optional[str] = None,
        account_numbers: Optional[str] = None,
    ) -> None:
        self.name = name
        self.federal_tax_classification = federal_tax_classification
        self.address = address
        self.city_state_zip = city_state_zip
        self.tin = tin
        self.tin_type = tin_type
        self.business_name = business_name
        self.exempt_payee_code = exempt_payee_code
        self.exemption_from_fatca_code = exemption_from_fatca_code
        self.account_numbers = account_numbers


class W8BENFields:
    """Validated, immutable W-8BEN field set produced by the normalizer."""

    def __init__(
        self,
        *,
        name: str,
        country_of_citizenship: str,
        permanent_address: str,
        permanent_address_city_country: str,
        mailing_address: Optional[str] = None,
        mailing_address_city_country: Optional[str] = None,
        us_tin: Optional[str] = None,
        foreign_tin: Optional[str] = None,
        ftin_not_required: Optional[bool] = None,
        reference_numbers: Optional[str] = None,
        date_of_birth: Optional[str] = None,
        treaty_country: Optional[str] = None,
        treaty_article: Optional[str] = None,
        withholding_rate: Optional[str] = None,
        income_type: Optional[str] = None,
        treaty_conditions: Optional[str] = None,
    ) -> None:
        self.name = name
        self.country_of_citizenship = country_of_citizenship
        self.permanent_address = permanent_address
        self.permanent_address_city_country = permanent_address_city_country
        self.mailing_address = mailing_address
        self.mailing_address_city_country = mailing_address_city_country
        self.us_tin = us_tin
        self.foreign_tin = foreign_tin
        self.ftin_not_required = ftin_not_required
        self.reference_numbers = reference_numbers
        self.date_of_birth = date_of_birth
        self.treaty_country = treaty_country
        self.treaty_article = treaty_article
        self.withholding_rate = withholding_rate
        self.income_type = income_type
        self.treaty_conditions = treaty_conditions


class FormFieldNormalizer:
    """Stateless domain service that validates raw form field inputs.

    Raises :class:`~src.domain.exceptions.InvalidFormFieldsError` for any
    constraint violation so that callers never receive partially-valid data.
    """

    # ------------------------------------------------------------------ W-9

    @classmethod
    def normalize_w9(
        cls,
        *,
        name: Optional[str],
        federal_tax_classification: Optional[str],
        address: Optional[str],
        city_state_zip: Optional[str],
        tin: Optional[str],
        tin_type: Optional[str],
        business_name: Optional[str] = None,
        exempt_payee_code: Optional[str] = None,
        exemption_from_fatca_code: Optional[str] = None,
        account_numbers: Optional[str] = None,
    ) -> W9Fields:
        """Validate W-9 fields and return a :class:`W9Fields` instance.

        Raises:
            InvalidFormFieldsError: If any required field is absent/blank or
                ``tin_type`` is not ``'SSN'`` or ``'EIN'``.
        """
        required = {
            "name": name,
            "federal_tax_classification": federal_tax_classification,
            "address": address,
            "city_state_zip": city_state_zip,
            "tin": tin,
            "tin_type": tin_type,
        }
        cls._assert_required(required)

        # Safe to use assert here — _assert_required already guarantees non-None/non-blank
        normalized_tin_type = tin_type.strip().upper()  # type: ignore[union-attr]
        if normalized_tin_type not in W9Fields.VALID_TIN_TYPES:
            raise InvalidFormFieldsError(
                f"W-9 tin_type must be 'SSN' or 'EIN'; got '{tin_type}'."
            )

        return W9Fields(
            name=name.strip(),  # type: ignore[union-attr]
            federal_tax_classification=federal_tax_classification.strip(),  # type: ignore[union-attr]
            address=address.strip(),  # type: ignore[union-attr]
            city_state_zip=city_state_zip.strip(),  # type: ignore[union-attr]
            tin=tin.strip(),  # type: ignore[union-attr]
            tin_type=normalized_tin_type,
            business_name=business_name.strip() if business_name else None,
            exempt_payee_code=exempt_payee_code.strip() if exempt_payee_code else None,
            exemption_from_fatca_code=(
                exemption_from_fatca_code.strip() if exemption_from_fatca_code else None
            ),
            account_numbers=account_numbers.strip() if account_numbers else None,
        )

    # --------------------------------------------------------------- W-8BEN

    @classmethod
    def normalize_w8ben(
        cls,
        *,
        name: Optional[str],
        country_of_citizenship: Optional[str],
        permanent_address: Optional[str],
        permanent_address_city_country: Optional[str],
        mailing_address: Optional[str] = None,
        mailing_address_city_country: Optional[str] = None,
        us_tin: Optional[str] = None,
        foreign_tin: Optional[str] = None,
        ftin_not_required: Optional[bool] = None,
        reference_numbers: Optional[str] = None,
        date_of_birth: Optional[str] = None,
        treaty_country: Optional[str] = None,
        treaty_article: Optional[str] = None,
        withholding_rate: Optional[str] = None,
        income_type: Optional[str] = None,
        treaty_conditions: Optional[str] = None,
    ) -> W8BENFields:
        """Validate W-8BEN fields and return a :class:`W8BENFields` instance.

        Raises:
            InvalidFormFieldsError: If any required field is absent/blank, or
                none of us_tin / foreign_tin / ftin_not_required is supplied.
        """
        required = {
            "name": name,
            "country_of_citizenship": country_of_citizenship,
            "permanent_address": permanent_address,
            "permanent_address_city_country": permanent_address_city_country,
        }
        cls._assert_required(required)

        has_identification = (
            (us_tin is not None and us_tin.strip() != "")
            or (foreign_tin is not None and foreign_tin.strip() != "")
            or ftin_not_required is True
        )
        if not has_identification:
            raise InvalidFormFieldsError(
                "W-8BEN requires at least one of: 'us_tin', 'foreign_tin', "
                "or 'ftin_not_required' = true."
            )

        return W8BENFields(
            name=name.strip(),  # type: ignore[union-attr]
            country_of_citizenship=country_of_citizenship.strip(),  # type: ignore[union-attr]
            permanent_address=permanent_address.strip(),  # type: ignore[union-attr]
            permanent_address_city_country=permanent_address_city_country.strip(),  # type: ignore[union-attr]
            mailing_address=mailing_address.strip() if mailing_address else None,
            mailing_address_city_country=(
                mailing_address_city_country.strip() if mailing_address_city_country else None
            ),
            us_tin=us_tin.strip() if us_tin else None,
            foreign_tin=foreign_tin.strip() if foreign_tin else None,
            ftin_not_required=ftin_not_required,
            reference_numbers=reference_numbers.strip() if reference_numbers else None,
            date_of_birth=date_of_birth.strip() if date_of_birth else None,
            treaty_country=treaty_country.strip() if treaty_country else None,
            treaty_article=treaty_article.strip() if treaty_article else None,
            withholding_rate=withholding_rate.strip() if withholding_rate else None,
            income_type=income_type.strip() if income_type else None,
            treaty_conditions=treaty_conditions.strip() if treaty_conditions else None,
        )

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _assert_required(fields: dict) -> None:
        """Raise :class:`InvalidFormFieldsError` for any blank/absent field."""
        missing = [name for name, value in fields.items() if not value or not str(value).strip()]
        if missing:
            raise InvalidFormFieldsError(
                f"Missing required field(s): {', '.join(missing)}."
            )
