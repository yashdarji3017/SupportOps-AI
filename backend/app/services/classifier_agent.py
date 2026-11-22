from typing import Protocol, runtime_checkable

from backend.app.constants.prompts import CLASSIFIER_SYSTEM_PROMPT
from backend.app.core.config import (
    Settings,
    get_gemini_model_name,
    get_google_api_key,
    get_settings,
)
from backend.app.core.logger import get_logger
from backend.app.schemas.classification import QueryClassification

logger = get_logger(__name__)


class AgentError(Exception):
    """Base exception for classification agent errors."""


LLMProviderError = AgentError


class AgentTimeoutError(AgentError):
    """Raised when an agent call times out."""


LLMTimeoutError = AgentTimeoutError


class AgentInvalidResponseError(AgentError):
    """Raised when an agent returns an invalid or unparseable response."""


LLMInvalidResponseError = AgentInvalidResponseError


@runtime_checkable
class ClassifierAgentProtocol(Protocol):
    """Interface protocol required for query classification agents."""

    async def classify(self, query: str) -> QueryClassification:
        """Classify a natural-language query into structured triage fields.

        Args:
            query: User query to classify.

        Returns:
            QueryClassification containing category, priority, and escalation status.
        """
        ...


def clean_gemini_model_name(model_name: str) -> str:
    """Remove provider prefixes from a Gemini model identifier.

    Supports model names prefixed with 'google:' or 'google-cloud:' so the
    underlying Google model name can be used directly with the provider API.

    Args:
        model_name: Original Gemini model identifier.

    Returns:
        Model name without recognized provider prefixes.
    """
    return model_name.replace("google:", "").replace("google-cloud:", "")


class ClassifierAgent:
    """Classify customer queries using a Google Gemini model via Pydantic AI."""

    def __init__(
        self,
        model_name: str | None = None,
        settings: Settings | None = None,
        custom_agent: object | None = None,
    ) -> None:
        """Initialize the classifier with configuration or a custom agent.

        Args:
            model_name: Optional Gemini model name override.
            settings: Optional application settings instance.
            custom_agent: Optional preconfigured agent implementing an async run method.
        """
        self._settings: Settings = settings or get_settings()
        self._model_name: str = model_name or self._settings.gemini_model
        self._agent: object | None = custom_agent

        if self._agent is None:
            self._init_gemini_agent()

    def _init_gemini_agent(self) -> None:
        """Initialize the Pydantic AI agent with Google Gemini.

        Prefers the explicit Google provider API and falls back to string-based
        model formatting when direct imports are unavailable.
        """
        try:
            from pydantic_ai import Agent

            api_key = self._settings.google_api_key or get_google_api_key()
            raw_model = self._model_name or get_gemini_model_name()
            clean_model = clean_gemini_model_name(raw_model)

            try:
                from pydantic_ai.models.google import GoogleModel
                from pydantic_ai.providers.google import GoogleProvider

                if api_key and str(api_key).strip():
                    provider = GoogleProvider(api_key=str(api_key).strip())
                    model = GoogleModel(clean_model, provider=provider)
                else:
                    model = GoogleModel(clean_model)

                self._agent = Agent(
                    model,
                    system_prompt=CLASSIFIER_SYSTEM_PROMPT,
                    output_type=QueryClassification,
                )
                logger.info(
                    "Initialized classifier agent with Google Gemini: model=%s", clean_model
                )

            except (ImportError, AttributeError):
                target_model = (
                    f"google-gla:{clean_model}"
                    if not clean_model.startswith("google")
                    else clean_model
                )
                self._agent = Agent(
                    target_model,
                    system_prompt=CLASSIFIER_SYSTEM_PROMPT,
                    output_type=QueryClassification,
                )
                logger.info("Initialized classifier agent using model identifier: %s", target_model)

        except ImportError:
            logger.warning(
                "Pydantic AI is not installed; classifier initialization is unavailable."
            )
            self._agent = None
        except Exception as exc:
            logger.exception("Failed to initialize Google Gemini classifier agent: %s", exc)
            self._agent = None

    async def classify(self, query: str) -> QueryClassification:
        """Classify a query string and return a validated structured result.

        Args:
            query: Non-empty natural-language query to classify.

        Returns:
            Validated QueryClassification output.

        Raises:
            ValueError: If the query is empty or the model returns an unsupported format.
            RuntimeError: If the Gemini agent cannot be initialized.
        """
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query must be a non-empty string.")

        try:
            if self._agent is None:
                self._init_gemini_agent()

                if self._agent is None:
                    raise RuntimeError("Google Gemini Pydantic AI agent is not initialized.")

            run_method = getattr(self._agent, "run", None)
            if not callable(run_method):
                raise RuntimeError("Configured agent does not provide a callable run method.")

            result = await run_method(query)

            extracted = getattr(
                result,
                "output",
                getattr(result, "data", result),
            )

            if isinstance(extracted, QueryClassification):
                return extracted

            if isinstance(extracted, dict):
                return QueryClassification(**extracted)

            raise ValueError(
                f"Classifier returned an unsupported response format: {type(extracted).__name__}"
            )

        except (ValueError, RuntimeError):
            raise
        except Exception as exc:
            logger.exception(
                "Query classification failed: model=%s, error=%s", self._model_name, exc
            )
            raise

    async def analyze_ticket(
        self,
        subject: str,
        description: str,
        customer_name: str | None = None,
    ) -> QueryClassification:
        """Adapt ticket fields into a formatted prompt query and classify.

        Args:
            subject: Ticket subject text.
            description: Ticket description text.
            customer_name: Optional customer name string.

        Returns:
            Validated QueryClassification output.
        """
        name_str = (
            f"Customer Name: {customer_name.strip()}\n"
            if customer_name and customer_name.strip()
            else ""
        )
        query = f"{name_str}Subject: {subject.strip()}\nDescription: {description.strip()}"
        return await self.classify(query)


_classifier_instance: ClassifierAgentProtocol | None = None


def get_classifier_agent(
    settings: Settings | None = None,
) -> ClassifierAgentProtocol:
    """Retrieve or lazily initialize the shared classifier agent singleton.

    Args:
        settings: Optional application Settings override.

    Returns:
        The configured ClassifierAgentProtocol instance.
    """
    global _classifier_instance

    if _classifier_instance is None:
        cfg = settings or get_settings()
        if cfg.LLM_PROVIDER == "mock":
            from backend.app.services.mock_agent import MockClassifierAgent

            _classifier_instance = MockClassifierAgent()
        else:
            _classifier_instance = ClassifierAgent(settings=cfg)
        logger.debug("Created shared classifier agent instance.")

    return _classifier_instance


def set_classifier_agent(agent: ClassifierAgentProtocol) -> None:
    """Register or replace the shared classifier agent singleton instance.

    Args:
        agent: The ClassifierAgentProtocol instance to register.
    """
    global _classifier_instance
    _classifier_instance = agent
    logger.info("Shared classifier agent instance updated.")
