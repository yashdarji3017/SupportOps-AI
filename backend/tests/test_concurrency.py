import asyncio

import pytest

from backend.app.core.concurrency import concurrency_limiter
from backend.app.schemas.ticket import TicketRequest
from backend.app.services.mock_agent import MockClassifierAgent
from backend.app.services.ticket_analyzer import ticket_analyzer_service


@pytest.mark.asyncio
async def test_maximum_five_simultaneous_processing_operations() -> None:
    """Verify maximum five simultaneous processing operations under high concurrent load.

    Submits 12 concurrent requests through an instrumented mock agent with an
    artificial delay, verifying that active concurrent operations never exceed 5
    and that all submitted requests successfully complete.
    """
    instrumented_mock = MockClassifierAgent(simulate_delay=0.08)
    await instrumented_mock.reset_instrumentation()
    ticket_analyzer_service.agent = instrumented_mock

    num_requests = 12
    tickets = [
        TicketRequest(
            ticket_id=f"CONCURRENCY-TICKET-{i:03d}",
            subject=f"Concurrent Test Ticket {i}",
            description=f"Detailed description for concurrent load test ticket number {i}.",
            customer_name=f"User {i}",
        )
        for i in range(num_requests)
    ]

    tasks = [ticket_analyzer_service.analyze_ticket(t) for t in tickets]
    results = await asyncio.gather(*tasks)

    assert len(results) == num_requests
    for idx, res in enumerate(results):
        assert res.ticket_id == f"CONCURRENCY-TICKET-{idx:03d}"
        assert res.request_id is not None
        assert res.confidence_score > 0.0

    assert instrumented_mock.total_operations == num_requests
    assert instrumented_mock.active_operations == 0
    assert concurrency_limiter.current_concurrent_requests == 0
    assert instrumented_mock.max_observed_concurrency <= 5
    assert instrumented_mock.max_observed_concurrency > 1


@pytest.mark.asyncio
async def test_concurrency_limiter_releases_on_exception() -> None:
    """Verify that concurrency semaphore permits are guaranteed to be released on failure.

    Triggers a simulated provider failure and checks that active permit counts
    cleanly return to zero.
    """
    failing_provider = MockClassifierAgent(simulate_failure=True)
    ticket_analyzer_service.agent = failing_provider

    req = TicketRequest(
        subject="Failing request test",
        description="This ticket is designed to trigger an error and check permit release.",
    )

    res = await ticket_analyzer_service.analyze_ticket(req)

    assert res.requires_human is True
    assert res.escalation_reason is not None
    assert "provider failure" in res.escalation_reason.lower()
    assert concurrency_limiter.current_concurrent_requests == 0
