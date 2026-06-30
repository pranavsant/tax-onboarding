import pytest

from src.domain.exceptions import InvalidTaxIdError
from src.domain.value_objects.tax_id import TaxId


def test_valid_ssn_is_recognized() -> None:
    tax_id = TaxId.create("123-45-6789")
    assert tax_id.kind == "SSN"
    assert tax_id.masked() == "***-**-6789"


def test_valid_ein_is_recognized() -> None:
    tax_id = TaxId.create("12-3456789")
    assert tax_id.kind == "EIN"


def test_invalid_tax_id_raises_domain_error() -> None:
    with pytest.raises(InvalidTaxIdError):
        TaxId.create("not-a-tax-id")
