import asyncio
import re

from backend.app.schemas.classification import QueryClassification
from backend.app.schemas.ticket import TicketCategory, TicketPriority
from backend.app.services.classifier_agent import (
    ClassifierAgentProtocol,
    LLMInvalidResponseError,
    LLMProviderError,
    LLMTimeoutError,
)


class MockClassifierAgent(ClassifierAgentProtocol):
    """Deterministic mock classifier agent designed for test suites and concurrency testing."""

    LEGAL_RE: re.Pattern[str] = re.compile(
        r"\b(lawyer|sue|suing|lawsuit|attorney|court|legal action|litigation|subpoena)\b",
        re.IGNORECASE,
    )
    SECURITY_RE: re.Pattern[str] = re.compile(
        r"\b(hacked|security breach|unauthorized access|stolen credentials|account takeover|compromised password)\b",
        re.IGNORECASE,
    )
    HUMAN_RE: re.Pattern[str] = re.compile(
        r"\b(human agent|talk to human|real person|speak to a person|speak with a human|representative|transfer me to someone|supervisor|manager)\b",
        re.IGNORECASE,
    )
    FINANCIAL_RE: re.Pattern[str] = re.compile(
        r"\b(unauthorized charge|disputed charge|dispute transaction|chargeback|stolen card|wire transfer missing)\b",
        re.IGNORECASE,
    )
    POLICY_RE: re.Pattern[str] = re.compile(
        r"\b(source code|proprietary algorithm|bypass terms|bypass verification|bypass kyc|illegal)\b",
        re.IGNORECASE,
    )

    def __init__(
        self,
        simulate_delay: float = 0.0,
        simulate_failure: bool = False,
        simulate_timeout: bool = False,
        simulate_invalid_json: bool = False,
        simulate_low_confidence: bool = False,
    ) -> None:
        """Initialize mock classifier agent with test simulation configurations.

        Args:
            simulate_delay: Artificial sleep delay in seconds before responding.
            simulate_failure: Flag simulating an unexpected provider 500 error.
            simulate_timeout: Flag simulating a network timeout error.
            simulate_invalid_json: Flag simulating an unparseable response payload.
            simulate_low_confidence: Flag simulating low confidence model output.
        """
        self.simulate_delay: float = simulate_delay
        self.simulate_failure: bool = simulate_failure
        self.simulate_timeout: bool = simulate_timeout
        self.simulate_invalid_json: bool = simulate_invalid_json
        self.simulate_low_confidence: bool = simulate_low_confidence

        self._active_operations: int = 0
        self._max_observed_concurrency: int = 0
        self._total_operations: int = 0
        self._lock: asyncio.Lock = asyncio.Lock()

    @property
    def active_operations(self) -> int:
        """Return the number of analysis operations currently executing."""
        return self._active_operations

    @property
    def max_observed_concurrency(self) -> int:
        """Return peak simultaneous concurrent operations observed."""
        return self._max_observed_concurrency

    @property
    def total_operations(self) -> int:
        """Return the cumulative count of operations executed."""
        return self._total_operations

    async def reset_instrumentation(self) -> None:
        """Reset concurrency instrumentation counters to zero."""
        async with self._lock:
            self._active_operations = 0
            self._max_observed_concurrency = 0
            self._total_operations = 0

    async def run(self, query: str) -> QueryClassification:
        """Execute query classification via custom agent runner interface.

        Args:
            query: Non-empty query string.

        Returns:
            Structured QueryClassification output.
        """
        return await self.classify(query)

    async def classify(self, query: str) -> QueryClassification:
        """Parse natural-language query and return deterministic classification.

        Args:
            query: The input query string to classify.

        Returns:
            Structured QueryClassification output.

        Raises:
            ValueError: If query is empty or whitespace.
        """
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query must be a non-empty string.")

        subject = query
        description = query
        customer_name: str | None = None

        lines = query.split("\n")
        for line in lines:
            if line.startswith("Subject:"):
                subject = line.replace("Subject:", "").strip()
            elif line.startswith("Description:"):
                description = line.replace("Description:", "").strip()
            elif line.startswith("Customer Name:"):
                customer_name = line.replace("Customer Name:", "").strip()

        return await self.analyze_ticket(
            subject=subject,
            description=description,
            customer_name=customer_name,
        )

    async def analyze_ticket(
        self,
        subject: str,
        description: str,
        customer_name: str | None = None,
    ) -> QueryClassification:
        """Analyze ticket parameters and produce deterministic classification.

        Tracks active operations and tests concurrency limits.

        Args:
            subject: Ticket subject text.
            description: Ticket description text.
            customer_name: Optional customer name.

        Returns:
            Structured QueryClassification output.

        Raises:
            LLMTimeoutError: If simulate_timeout is set.
            LLMProviderError: If simulate_failure is set.
            LLMInvalidResponseError: If simulate_invalid_json is set.
        """
        async with self._lock:
            self._active_operations += 1
            if self._active_operations > self._max_observed_concurrency:
                self._max_observed_concurrency = self._active_operations
            self._total_operations += 1

        try:
            if self.simulate_delay > 0:
                await asyncio.sleep(self.simulate_delay)

            if self.simulate_timeout:
                raise LLMTimeoutError("Mock agent call timed out after configured duration.")

            if self.simulate_failure:
                raise LLMProviderError("Mock agent simulated unexpected upstream 500 error.")

            if self.simulate_invalid_json:
                raise LLMInvalidResponseError(
                    "Mock agent returned unparseable or corrupted response."
                )

            combined = f"{subject} {description}".lower()

            if (
                self.simulate_low_confidence
                or "low_confidence_trigger" in combined
                or "ambiguous" in combined
            ):
                return QueryClassification(
                    category=TicketCategory.GENERAL_INQUIRIES,
                    priority=TicketPriority.LOW,
                    confidence_score=0.45,
                    suggested_reply=None,
                    requires_human=True,
                    escalation_reason="Low model confidence score (0.45)",
                )

            category = self._detect_category(combined)
            priority = self._detect_priority(combined)
            requires_human, escalation_reason = self._detect_escalation(f"{subject} {description}")

            suggested_reply: str | None = None
            if not requires_human:
                greeting = (
                    f"Hello {customer_name.strip()},"
                    if customer_name and customer_name.strip()
                    else "Hello,"
                )
                suggested_reply = (
                    f"{greeting} Thank you for contacting our customer support team regarding '{subject.strip()}'. "
                    f"We have categorized your request under {category.value} with {priority.value} priority. "
                    "Our team is currently reviewing your issue and will assist you shortly. "
                    "If you have additional details to provide, please reply directly to this message."
                )

            return QueryClassification(
                category=category,
                priority=priority,
                confidence_score=0.94,
                suggested_reply=suggested_reply,
                requires_human=requires_human,
                escalation_reason=escalation_reason,
            )

        finally:
            async with self._lock:
                self._active_operations = max(0, self._active_operations - 1)

    def _detect_category(self, text: str) -> TicketCategory:
        """Detect category from text keywords.

        Args:
            text: Lowercased ticket text.

        Returns:
            The matched TicketCategory enum value.
        """
        if any(
            w in text
            for w in [
                "refund",
                "money back",
                "reimbursement",
                "return item",
                "refund policy",
            ]
        ):
            return TicketCategory.REFUND
        if any(
            w in text
            for w in [
                "invoice",
                "charge",
                "subscription",
                "payment",
                "billing",
                "credit card",
                "renew",
                "receipt",
            ]
        ):
            return TicketCategory.BILLING
        if any(
            w in text
            for w in [
                "password",
                "login",
                "account",
                "2fa",
                "mfa",
                "username",
                "profile",
                "locked out",
            ]
        ):
            return TicketCategory.ACCOUNT
        if any(
            w in text
            for w in [
                "error",
                "bug",
                "crash",
                "500",
                "latency",
                "slow",
                "api",
                "glitch",
                "technical",
                "stack trace",
                "timeout",
                "broken code",
            ]
        ):
            return TicketCategory.TECHNICAL
        if any(
            w in text
            for w in [
                "complaint",
                "terrible",
                "horrible",
                "unacceptable",
                "furious",
                "angry",
                "poor service",
                "rude",
                "dissatisfied",
            ]
        ):
            return TicketCategory.COMPLAINTS
        return TicketCategory.GENERAL_INQUIRIES

    def _detect_priority(self, text: str) -> TicketPriority:
        """Detect urgency priority tier from text keywords.

        Args:
            text: Lowercased ticket text.

        Returns:
            The matched TicketPriority enum value.
        """
        if re.search(
            r"\b(outage|system down|data breach|catastrophic|all users affected|production down|emergency|severity 1)\b",
            text,
        ):
            return TicketPriority.CRITICAL
        if re.search(
            r"\b(urgent|asap|broken|blocked|high priority|cannot work|deadline|immediate)\b",
            text,
        ):
            return TicketPriority.HIGH
        if re.search(r"\b(medium|slow|minor issue|delay|glitch)\b", text):
            return TicketPriority.MEDIUM
        if re.search(
            r"\b(general question|feature request|feedback|documentation|how to|low|curious)\b",
            text,
        ):
            return TicketPriority.LOW
        if re.search(r"\bcritical\b", text):
            return TicketPriority.CRITICAL
        return TicketPriority.MEDIUM

    def _detect_escalation(self, text: str) -> tuple[bool, str | None]:
        """Detect mandatory escalation conditions from text.

        Args:
            text: Raw ticket text.

        Returns:
            Tuple of (requires_human, escalation_reason).
        """
        if self.LEGAL_RE.search(text):
            return True, "Mandatory escalation: Legal issues or threats detected."
        if self.SECURITY_RE.search(text):
            return True, "Mandatory escalation: Fraud or security incident reported."
        if self.HUMAN_RE.search(text):
            return (
                True,
                "Mandatory escalation: Customer explicitly requested a human representative.",
            )
        if self.FINANCIAL_RE.search(text):
            return (
                True,
                "Mandatory escalation: Sensitive financial matter requires manual investigation.",
            )
        if self.POLICY_RE.search(text):
            return True, "Mandatory escalation: Request falls outside company policies."
        if len(text.strip()) <= 10 or text.strip() in [
            "help",
            "broken",
            "error",
            "not working",
            "test",
        ]:
            return (
                True,
                "Mandatory escalation: Insufficient information provided in ticket to resolve.",
            )
        return False, None


MockLLMProvider = MockClassifierAgent
