import pytest

from backend.app.schemas.ticket import TicketPriority, TicketRequest
from backend.app.services.priority import priority_service
from backend.app.services.ticket_analyzer import ticket_analyzer_service


def test_supported_priorities() -> None:
    """Verify that all four required priorities are officially supported by domain service.

    Checks supported priority strings against expected Low, Medium, High, Critical constants.
    """
    supported = priority_service.get_supported_priorities()
    expected = ["Low", "Medium", "High", "Critical"]
    assert sorted(supported) == sorted(expected)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("subject", "description", "expected_priority"),
    [
        (
            "Major Outage - Production Down",
            "Emergency: complete system down and all users affected by production outage.",
            TicketPriority.CRITICAL,
        ),
        (
            "Urgent: Locked Out Before Major Deadline",
            "I need access immediately asap. My team is completely broken and blocked.",
            TicketPriority.HIGH,
        ),
        (
            "Slow loading times during peak hours",
            "We are noticing some minor delay and slow dashboard rendering during lunch.",
            TicketPriority.MEDIUM,
        ),
        (
            "Curious about future roadmap",
            "Just a low priority feature request and feedback about UI documentation.",
            TicketPriority.LOW,
        ),
    ],
)
async def test_all_four_priorities_detection(
    subject: str, description: str, expected_priority: TicketPriority
) -> None:
    """Verify accurate priority detection across all four priority tiers.

    Args:
        subject: Test ticket subject string.
        description: Test ticket description string.
        expected_priority: The expected TicketPriority enum value.
    """
    req = TicketRequest(subject=subject, description=description)
    res = await ticket_analyzer_service.analyze_ticket(req)

    assert res.priority == expected_priority
    assert res.priority in TicketPriority
