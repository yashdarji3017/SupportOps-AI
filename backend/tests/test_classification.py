import pytest

from backend.app.schemas.ticket import TicketCategory, TicketRequest
from backend.app.services.classification import classification_service
from backend.app.services.ticket_analyzer import ticket_analyzer_service


def test_supported_categories() -> None:
    """Verify that all six mandatory ticket categories are supported by the domain service.

    Checks the list of supported category string representations against expected
    domain category constants.
    """
    supported = classification_service.get_supported_categories()
    expected = [
        "Billing",
        "Technical",
        "Account",
        "Refund",
        "Complaints",
        "General Inquiries",
    ]
    assert sorted(supported) == sorted(expected)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("subject", "description", "expected_category"),
    [
        (
            "Monthly Subscription Invoice",
            "I was charged twice on my credit card for the monthly subscription renew invoice.",
            TicketCategory.BILLING,
        ),
        (
            "System API Returning 500",
            "Our team is getting an HTTP 500 crash error and latency timeout on the REST API.",
            TicketCategory.TECHNICAL,
        ),
        (
            "Forgot Account Password",
            "I need to reset my password and update my 2FA authentication profile username.",
            TicketCategory.ACCOUNT,
        ),
        (
            "Request for Return Reimbursement",
            "I returned the item last week and would like my refund money back.",
            TicketCategory.REFUND,
        ),
        (
            "Terrible customer service experience",
            "Your representative was rude and unacceptable. I am furious with this horrible service.",
            TicketCategory.COMPLAINTS,
        ),
        (
            "Question regarding business hours",
            "Could you tell me what your support hours are and share documentation on features?",
            TicketCategory.GENERAL_INQUIRIES,
        ),
    ],
)
async def test_all_six_categories_classification(
    subject: str, description: str, expected_category: TicketCategory
) -> None:
    """Verify accurate end-to-end classification across all six mandatory ticket categories.

    Args:
        subject: The test ticket subject text.
        description: The test ticket body description.
        expected_category: The expected TicketCategory enum value.
    """
    req = TicketRequest(subject=subject, description=description)
    res = await ticket_analyzer_service.analyze_ticket(req)

    assert res.category == expected_category
    assert res.category in TicketCategory
