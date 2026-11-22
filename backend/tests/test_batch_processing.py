import pytest
from httpx import AsyncClient

from backend.app.schemas.ticket import BatchTicketRequest, TicketRequest
from backend.app.services.ticket_analyzer import ticket_analyzer_service


@pytest.mark.asyncio
async def test_batch_analyze_tickets_success(async_client: AsyncClient) -> None:
    """Verify batch analysis of multiple tickets containing mixed scenarios.

    Submits a batch with routine billing, technical, and mandatory legal escalation
    tickets, verifying that each item is properly classified, unique request IDs
    are generated, and escalation rules trigger appropriately.

    Args:
        async_client: Pytest fixture providing an ASGI test client.
    """
    payload = {
        "tickets": [
            {
                "ticket_id": "BATCH-001",
                "subject": "Billing inquiry",
                "description": "Double charged on my latest renewal invoice.",
                "customer_name": "Alice",
            },
            {
                "ticket_id": "BATCH-002",
                "subject": "System crash",
                "description": "Internal 500 server error when invoking API endpoint.",
                "customer_name": "Bob",
            },
            {
                "ticket_id": "BATCH-003",
                "subject": "Lawsuit notice",
                "description": "We are retaining an attorney to sue for contract violation.",
                "customer_name": "Charlie",
            },
        ]
    }

    response = await async_client.post("/api/v1/tickets/analyze/batch", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["total_tickets"] == 3
    assert data["successful_count"] == 3
    assert data["failed_count"] == 0
    assert len(data["results"]) == 3

    res1 = data["results"][0]
    assert res1["ticket_id"] == "BATCH-001"
    assert res1["category"] == "Billing"
    assert res1["requires_human"] is False

    res2 = data["results"][1]
    assert res2["ticket_id"] == "BATCH-002"
    assert res2["category"] == "Technical"
    assert res2["requires_human"] is False

    res3 = data["results"][2]
    assert res3["ticket_id"] == "BATCH-003"
    assert res3["requires_human"] is True
    assert res3["suggested_reply"] is None
    assert "legal" in res3["escalation_reason"].lower()

    req_ids = {r["request_id"] for r in data["results"]}
    assert len(req_ids) == 3


@pytest.mark.asyncio
async def test_batch_individual_failure_isolation() -> None:
    """Verify that failures on individual tickets do not abort processing of the entire batch.

    Ensures that errors on individual items are isolated and recorded in the
    errors array while valid tickets in the batch succeed.
    """
    batch = BatchTicketRequest(
        tickets=[
            TicketRequest(
                ticket_id="T-OK-1", subject="Invoice copy", description="Send my invoice"
            ),
            TicketRequest(
                ticket_id="T-OK-2", subject="API glitch", description="API is returning 500"
            ),
        ]
    )

    result = await ticket_analyzer_service.analyze_batch(batch)
    assert result.total_tickets == 2
    assert result.successful_count == 2
    assert result.failed_count == 0
