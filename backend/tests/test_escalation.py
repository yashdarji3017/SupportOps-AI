import pytest

from backend.app.schemas.classification import QueryClassification
from backend.app.schemas.ticket import TicketCategory, TicketPriority, TicketRequest
from backend.app.services.escalation import escalation_engine
from backend.app.services.mock_agent import MockClassifierAgent
from backend.app.services.ticket_analyzer import ticket_analyzer_service


@pytest.mark.asyncio
async def test_legal_issue_escalation() -> None:
    """Verify tickets containing legal threats or attorney notices escalate to human agents.

    Checks that requires_human is set to True, suggested_reply is None, and
    a clear legal escalation reason is returned.
    """
    req = TicketRequest(
        subject="Breach of contract notice",
        description="Our lawyer is preparing a lawsuit and we will sue you in court if this is not resolved.",
    )
    res = await ticket_analyzer_service.analyze_ticket(req)

    assert res.requires_human is True
    assert res.suggested_reply is None
    assert res.escalation_reason is not None
    assert "legal" in res.escalation_reason.lower()


@pytest.mark.asyncio
async def test_fraud_and_security_escalation() -> None:
    """Verify tickets reporting compromised credentials or account takeovers escalate.

    Checks that security incidents trigger immediate human routing with a null reply.
    """
    req = TicketRequest(
        subject="Suspicious login alert",
        description="My account was hacked and unauthorized access was detected with stolen credentials.",
    )
    res = await ticket_analyzer_service.analyze_ticket(req)

    assert res.requires_human is True
    assert res.suggested_reply is None
    assert res.escalation_reason is not None
    assert any(term in res.escalation_reason.lower() for term in ["fraud", "security"])


@pytest.mark.asyncio
async def test_human_agent_request_escalation() -> None:
    """Verify tickets where customer explicitly requests a human agent escalate.

    Checks that requests to speak to a person, representative, or supervisor
    are respected and routed to human support.
    """
    req = TicketRequest(
        subject="Need human assistance",
        description="I do not want an automated bot. Please connect me to a human agent or real person immediately.",
    )
    res = await ticket_analyzer_service.analyze_ticket(req)

    assert res.requires_human is True
    assert res.suggested_reply is None
    assert res.escalation_reason is not None
    assert "human" in res.escalation_reason.lower()


@pytest.mark.asyncio
async def test_sensitive_financial_escalation() -> None:
    """Verify tickets involving disputed transactions or chargebacks escalate.

    Checks that sensitive financial matters trigger human intervention.
    """
    req = TicketRequest(
        subject="Disputed credit card charge",
        description="I see an unauthorized charge of $1500 and initiated a chargeback with my bank.",
    )
    res = await ticket_analyzer_service.analyze_ticket(req)

    assert res.requires_human is True
    assert res.suggested_reply is None
    assert res.escalation_reason is not None
    assert any(term in res.escalation_reason.lower() for term in ["financial", "investigation"])


@pytest.mark.asyncio
async def test_policy_violation_escalation() -> None:
    """Verify tickets requesting proprietary source code or policy bypass escalate.

    Checks that requests outside company policies are flagged for human review.
    """
    req = TicketRequest(
        subject="Request for backend proprietary algorithm",
        description="Please send me your proprietary algorithm source code so we can bypass verification.",
    )
    res = await ticket_analyzer_service.analyze_ticket(req)

    assert res.requires_human is True
    assert res.suggested_reply is None
    assert res.escalation_reason is not None
    assert "policies" in res.escalation_reason.lower()


@pytest.mark.asyncio
async def test_insufficient_information_escalation() -> None:
    """Verify vague or uninformative tickets escalate due to insufficient context.

    Checks that single-word or trivial text triggers mandatory human escalation.
    """
    req = TicketRequest(
        subject="help",
        description="broken",
    )
    res = await ticket_analyzer_service.analyze_ticket(req)

    assert res.requires_human is True
    assert res.suggested_reply is None
    assert res.escalation_reason is not None
    assert "insufficient" in res.escalation_reason.lower()


@pytest.mark.asyncio
async def test_low_confidence_escalation() -> None:
    """Verify tickets with model confidence below the threshold escalate.

    Configures a simulated low-confidence provider and asserts that low scores
    (< 0.75) trigger mandatory human routing.
    """
    low_conf_provider = MockClassifierAgent(simulate_low_confidence=True)
    ticket_analyzer_service.agent = low_conf_provider

    req = TicketRequest(
        subject="Ambiguous inquiry",
        description="Something feels a bit odd with how things are presented today.",
    )
    res = await ticket_analyzer_service.analyze_ticket(req)

    assert res.confidence_score < 0.75
    assert res.requires_human is True
    assert res.suggested_reply is None
    assert res.escalation_reason is not None
    assert "confidence" in res.escalation_reason.lower()


def test_llm_cannot_override_mandatory_escalation() -> None:
    """Verify that an AI model output cannot override deterministic mandatory escalation rules.

    Supplies an AI result that naively claims requires_human=False on a ticket
    with an account takeover and verifies that the policy engine overrides it.
    """
    naive_llm_result = QueryClassification(
        category=TicketCategory.ACCOUNT,
        priority=TicketPriority.CRITICAL,
        confidence_score=0.95,
        suggested_reply="Everything looks fine to me!",
        requires_human=False,
        escalation_reason=None,
    )

    subject = "Account Hacked"
    description = "Someone compromised my password and performed an account takeover."

    is_escalated, reason = escalation_engine.enforce_policy(
        subject=subject,
        description=description,
        llm_result=naive_llm_result,
        threshold=0.75,
    )

    assert is_escalated is True
    assert reason is not None
    assert "security" in reason.lower()
