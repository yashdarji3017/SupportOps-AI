import pytest
from httpx import AsyncClient

from backend.app.services.mock_agent import MockClassifierAgent
from backend.app.services.ticket_analyzer import ticket_analyzer_service


@pytest.mark.asyncio
async def test_analyze_ticket_success(async_client: AsyncClient) -> None:
    """Verify successful ticket analysis via POST /api/v1/tickets/analyze.

    Tests normal flow producing category, priority, confidence, and safe reply.

    Args:
        async_client: Pytest fixture providing an ASGI test client.
    """
    payload = {
        "ticket_id": "TICKET-100",
        "subject": "Need help with subscription renewal invoice",
        "description": "Where can I download the official invoice for my monthly renewal?",
        "customer_name": "Sarah Connor",
    }
    response = await async_client.post("/api/v1/tickets/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["ticket_id"] == "TICKET-100"
    assert "request_id" in data
    assert data["category"] == "Billing"
    assert data["priority"] in ["Low", "Medium", "High", "Critical"]
    assert 0.0 <= data["confidence_score"] <= 1.0
    assert data["requires_human"] is False
    assert data["escalation_reason"] is None
    assert data["suggested_reply"] is not None
    assert "Sarah Connor" in data["suggested_reply"]


@pytest.mark.asyncio
async def test_analyze_ticket_escalated(async_client: AsyncClient) -> None:
    """Verify escalated ticket analysis via POST /api/v1/tickets/analyze.

    Tests security threat triggering mandatory human escalation with null reply.

    Args:
        async_client: Pytest fixture providing an ASGI test client.
    """
    payload = {
        "ticket_id": "TICKET-200",
        "subject": "Account hacked",
        "description": "My account was compromised by unauthorized login and stolen credentials.",
        "customer_name": "John Doe",
    }
    response = await async_client.post("/api/v1/tickets/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["ticket_id"] == "TICKET-200"
    assert data["requires_human"] is True
    assert data["suggested_reply"] is None
    assert data["escalation_reason"] is not None


@pytest.mark.asyncio
async def test_llm_provider_failure_graceful_escalation(async_client: AsyncClient) -> None:
    """Verify graceful escalation without response fabrication on provider failure.

    Simulates an upstream provider error and verifies that the bot routes to human
    support with a clear failure explanation.

    Args:
        async_client: Pytest fixture providing an ASGI test client.
    """
    failing_provider = MockClassifierAgent(simulate_failure=True)
    ticket_analyzer_service.agent = failing_provider

    payload = {
        "ticket_id": "TICKET-FAIL-01",
        "subject": "Cannot connect to server",
        "description": "Receiving connection refused when trying to reach database.",
    }
    response = await async_client.post("/api/v1/tickets/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["requires_human"] is True
    assert data["suggested_reply"] is None
    assert data["confidence_score"] == 0.0
    assert "provider failure" in data["escalation_reason"].lower()


@pytest.mark.asyncio
async def test_llm_invalid_response_graceful_escalation(async_client: AsyncClient) -> None:
    """Verify graceful escalation on unparseable or corrupted model output.

    Simulates malformed model output and verifies that human routing is initiated.

    Args:
        async_client: Pytest fixture providing an ASGI test client.
    """
    invalid_provider = MockClassifierAgent(simulate_invalid_json=True)
    ticket_analyzer_service.agent = invalid_provider

    payload = {
        "ticket_id": "TICKET-INVALID-01",
        "subject": "General question",
        "description": "Could you provide information about your API rates?",
    }
    response = await async_client.post("/api/v1/tickets/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["requires_human"] is True
    assert data["suggested_reply"] is None
    assert "provider failure" in data["escalation_reason"].lower()


@pytest.mark.asyncio
async def test_validation_error_on_blank_input(async_client: AsyncClient) -> None:
    """Verify input validation returns HTTP 422 on empty subject or description.

    Args:
        async_client: Pytest fixture providing an ASGI test client.
    """
    payload = {
        "subject": "   ",
        "description": "",
    }
    response = await async_client.post("/api/v1/tickets/analyze", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_health_endpoint(async_client: AsyncClient) -> None:
    """Verify GET /api/v1/health returns application health status and uptime.

    Args:
        async_client: Pytest fixture providing an ASGI test client.
    """
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "healthy"
    assert "version" in data
    assert "uptime_seconds" in data
    assert data["uptime_seconds"] >= 0.0
    assert "provider" in data


@pytest.mark.asyncio
async def test_metrics_endpoint(async_client: AsyncClient) -> None:
    """Verify GET /api/v1/metrics returns in-memory counters with zero PII retention.

    Args:
        async_client: Pytest fixture providing an ASGI test client.
    """
    await async_client.post(
        "/api/v1/tickets/analyze",
        json={"subject": "Billing issue", "description": "Need my invoice copy"},
    )

    response = await async_client.get("/api/v1/metrics")
    assert response.status_code == 200
    data = response.json()

    assert "active_requests" in data
    assert "max_concurrent_requests" in data
    assert "current_concurrent_requests" in data
    assert "total_processed_requests" in data
    assert "failed_requests" in data
    assert "escalated_requests" in data

    assert data["max_concurrent_requests"] == 5
    assert data["total_processed_requests"] >= 1

    data_str = str(data).lower()
    for forbidden in ["subject", "description", "customer_name", "sarah", "connor", "invoice"]:
        assert forbidden not in data_str


@pytest.mark.asyncio
async def test_swagger_documentation(async_client: AsyncClient) -> None:
    """Verify FastAPI OpenAPI documentation is accessible at /docs.

    Args:
        async_client: Pytest fixture providing an ASGI test client.
    """
    response = await async_client.get("/docs")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient) -> None:
    """Verify API root endpoint provides service descriptions and directory.

    Args:
        async_client: Pytest fixture providing an ASGI test client.
    """
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Customer Support Triage Bot"
    assert data["status"] == "operational"
    assert "description" in data
    assert "documentation" in data
    assert data["documentation"]["swagger_ui"] == "/docs"
    assert "endpoints" in data
    assert "Billing" in data["supported_categories"]
    assert "Critical" in data["supported_priorities"]
