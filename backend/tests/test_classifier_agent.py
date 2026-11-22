import pytest

from backend.app.schemas.classification import QueryClassification
from backend.app.schemas.ticket import TicketCategory, TicketPriority
from backend.app.services.classifier_agent import (
    ClassifierAgent,
    ClassifierAgentProtocol,
    clean_gemini_model_name,
    get_classifier_agent,
    set_classifier_agent,
)


def test_clean_gemini_model_name() -> None:
    """Verify provider prefix stripping for Gemini model identifiers.

    Ensures that prefixes such as 'google:' and 'google-cloud:' are removed
    while bare model names are preserved.
    """
    assert clean_gemini_model_name("google:gemini-1.5-flash") == "gemini-1.5-flash"
    assert clean_gemini_model_name("google-cloud:gemini-2.0-flash") == "gemini-2.0-flash"
    assert clean_gemini_model_name("gemini-1.5-pro") == "gemini-1.5-pro"


def test_classifier_agent_protocol_compliance() -> None:
    """Verify runtime checkability and protocol implementation on ClassifierAgent.

    Ensures that ClassifierAgent satisfies the ClassifierAgentProtocol interface.
    """
    agent = ClassifierAgent()
    assert isinstance(agent, ClassifierAgentProtocol)


@pytest.mark.asyncio
async def test_classifier_agent_empty_query_raises_value_error() -> None:
    """Verify that empty or whitespace-only queries raise a ValueError.

    Ensures input validation prevents empty queries from reaching downstream models.
    """
    agent = ClassifierAgent()
    with pytest.raises(ValueError, match="Query must be a non-empty string."):
        await agent.classify("   ")


@pytest.mark.asyncio
async def test_classifier_agent_with_custom_injected_agent() -> None:
    """Verify dependency injection with a custom agent implementing an async run method.

    Tests that ClassifierAgent correctly delegates to custom agent runners
    and normalizes structured output payloads.
    """
    expected_output = QueryClassification(
        category=TicketCategory.BILLING,
        priority=TicketPriority.HIGH,
        confidence_score=0.98,
        suggested_reply="Hello, your invoice issue is being processed.",
        requires_human=False,
        escalation_reason=None,
    )

    class CustomMockAgent:
        """Mock custom agent runner returning structured QueryClassification."""

        async def run(self, query: str) -> object:
            """Execute mock run returning output container.

            Args:
                query: Natural-language input query.

            Returns:
                An object with an output attribute holding the classification.
            """

            class Result:
                output: QueryClassification = expected_output

            return Result()

    agent = ClassifierAgent(custom_agent=CustomMockAgent())
    result = await agent.classify("Inquiry about missing invoice")

    assert result.category == TicketCategory.BILLING
    assert result.priority == TicketPriority.HIGH
    assert result.confidence_score == 0.98
    assert result.suggested_reply is not None


def test_get_and_set_classifier_agent() -> None:
    """Verify singleton accessor mechanics for runtime dependency injection and swapping.

    Ensures set_classifier_agent updates the active agent returned by get_classifier_agent.
    """

    class MockCustomAgent:
        """Custom agent implementing classify method."""

        async def classify(self, query: str) -> QueryClassification:
            """Classify test query.

            Args:
                query: Input query string.

            Returns:
                Hardcoded QueryClassification output.
            """
            return QueryClassification(
                category=TicketCategory.TECHNICAL,
                priority=TicketPriority.LOW,
                confidence_score=0.9,
                requires_human=False,
            )

    custom = MockCustomAgent()
    set_classifier_agent(custom)
    retrieved = get_classifier_agent()
    assert retrieved is custom
