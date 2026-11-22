from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.app.services.metrics import metrics_service
from backend.app.services.mock_agent import MockClassifierAgent
from backend.app.services.ticket_analyzer import ticket_analyzer_service
from main import app


@pytest.fixture(autouse=True)
async def reset_state() -> AsyncIterator[None]:
    """Reset operational metrics and activate standard mock provider before each test.

    Yields:
        None while the test executes, resetting metrics again during teardown.
    """
    await metrics_service.reset()
    mock_prov = MockClassifierAgent()
    ticket_analyzer_service.agent = mock_prov
    yield
    await metrics_service.reset()


@pytest_asyncio.fixture
async def async_client() -> AsyncIterator[AsyncClient]:
    """Provide an isolated AsyncClient communicating directly with the ASGI application.

    Yields:
        An active AsyncClient instance configured with ASGITransport.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
