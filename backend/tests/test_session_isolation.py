import asyncio
import uuid

import pytest

from backend.app.core.logging import current_request_id_var
from backend.app.schemas.ticket import TicketRequest
from backend.app.services.session_manager import session_manager
from backend.app.services.ticket_analyzer import ticket_analyzer_service


@pytest.mark.asyncio
async def test_unique_request_ids_generated() -> None:
    """Verify that every incoming request receives an independent, distinct UUID4 identifier.

    Processes two sequential tickets and asserts that distinct valid UUIDs are assigned.
    """
    req1 = TicketRequest(subject="First ticket", description="Description for first request")
    req2 = TicketRequest(subject="Second ticket", description="Description for second request")

    res1 = await ticket_analyzer_service.analyze_ticket(req1)
    res2 = await ticket_analyzer_service.analyze_ticket(req2)

    assert res1.request_id != res2.request_id
    uuid.UUID(res1.request_id)
    uuid.UUID(res2.request_id)


@pytest.mark.asyncio
async def test_session_context_cleanup() -> None:
    """Verify that temporary ContextVars are completely unbound after request execution.

    Checks that before and after ticket execution, request contexts are unset.
    """
    assert current_request_id_var.get() is None
    assert session_manager.get_current_context() is None

    req = TicketRequest(subject="Context test", description="Testing context lifecycle")
    res = await ticket_analyzer_service.analyze_ticket(req)

    assert res.request_id is not None
    assert current_request_id_var.get() is None
    assert session_manager.get_current_context() is None


@pytest.mark.asyncio
async def test_cross_request_data_leakage_prevention() -> None:
    """Verify that concurrent requests with distinct customer data do not leak or cross-pollinate.

    Dispatches concurrent requests with different customer identities and asserts
    that each response strictly matches its corresponding customer input.
    """
    customers = [
        ("Alice Cooper", "TICKET-ALICE", "Billing question from Alice regarding invoice"),
        ("Bob Smith", "TICKET-BOB", "Technical issue from Bob regarding database error"),
        ("Charlie Brown", "TICKET-CHARLIE", "Account password reset for Charlie"),
        ("Diana Prince", "TICKET-DIANA", "Refund reimbursement inquiry for Diana"),
    ]

    async def _analyze(name: str, tid: str, desc: str) -> object:
        """Helper to dispatch single ticket analysis."""
        req = TicketRequest(
            ticket_id=tid,
            customer_name=name,
            subject=f"Inquiry from {name}",
            description=desc,
        )
        return await ticket_analyzer_service.analyze_ticket(req)

    tasks = [_analyze(name, tid, desc) for name, tid, desc in customers]
    responses = await asyncio.gather(*tasks)

    seen_request_ids: set[str] = set()
    for idx, (expected_name, expected_tid, _) in enumerate(customers):
        res = responses[idx]
        assert hasattr(res, "ticket_id")
        assert res.ticket_id == expected_tid
        req_id = getattr(res, "request_id", "")
        assert req_id not in seen_request_ids
        seen_request_ids.add(req_id)

        reply = getattr(res, "suggested_reply", None)
        if reply:
            assert expected_name in reply
            for other_name, _, _ in customers:
                if other_name != expected_name:
                    assert other_name not in reply
