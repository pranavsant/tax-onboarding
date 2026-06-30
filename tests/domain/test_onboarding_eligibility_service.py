from src.domain.entities.client import TaxClient
from src.domain.services.onboarding_eligibility_service import OnboardingEligibilityService
from src.domain.value_objects.tax_id import TaxId


def _make_client() -> TaxClient:
    return TaxClient(
        full_name="Jane Doe",
        email="jane@example.com",
        tax_id=TaxId.create("123-45-6789"),
    )


def test_client_is_not_eligible_without_documents() -> None:
    client = _make_client()
    service = OnboardingEligibilityService()

    assert service.is_eligible_for_review(client) is False
    assert len(service.missing_documents(client)) == 3


def test_client_becomes_eligible_after_all_documents_submitted() -> None:
    client = _make_client()
    service = OnboardingEligibilityService()

    for document in ["government_id", "prior_year_return", "w2_or_1099"]:
        client.add_document(document)

    assert service.is_eligible_for_review(client) is True
    assert service.missing_documents(client) == []
