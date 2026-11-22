import re

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.schemas.classification import QueryClassification


class EscalationPolicyEngine:
    """Independent policy engine that evaluates support tickets against safety gates."""

    LEGAL_PATTERNS: re.Pattern[str] = re.compile(
        r"\b(lawsuit|sue|suing|lawyer|attorney|court|legal action|litigation|"
        r"subpoena|arbitration|legal counsel|legal department|compliance violation|"
        r"retain counsel|file a suit)\b",
        re.IGNORECASE,
    )

    SECURITY_PATTERNS: re.Pattern[str] = re.compile(
        r"\b(hacked|security breach|unauthorized access|stolen credentials|"
        r"account takeover|compromised password|compromised account|phishing|"
        r"malware|ransomware|data leak|identity theft|credential stuffing|"
        r"suspicious login from)\b",
        re.IGNORECASE,
    )

    HUMAN_REQUEST_PATTERNS: re.Pattern[str] = re.compile(
        r"\b(speak to a human|talk to a human|human agent|real person|"
        r"human representative|speak with a human|transfer me to someone|"
        r"talk to a person|agent please|talk to a supervisor|talk to a manager|"
        r"get me a human|connect me to an agent|escalate to a human)\b",
        re.IGNORECASE,
    )

    FINANCIAL_PATTERNS: re.Pattern[str] = re.compile(
        r"\b(unauthorized charge|unauthorized transaction|disputed charge|"
        r"dispute transaction|chargeback|wire transfer missing|bank investigation|"
        r"stolen credit card|credit card fraud|financial audit|unrecognized charge|"
        r"fraudulent charge)\b",
        re.IGNORECASE,
    )

    POLICY_VIOLATION_PATTERNS: re.Pattern[str] = re.compile(
        r"\b(source code|proprietary algorithm|bypass terms|bypass verification|"
        r"bypass kyc|illegal|reverse engineer|trade secret|leak confidential|"
        r"disclose nda|jailbreak|exploit system)\b",
        re.IGNORECASE,
    )

    TRIVIAL_WORDS: set[str] = {
        "help",
        "broken",
        "it's broken",
        "its broken",
        "error",
        "issue",
        "bug",
        "please",
        "doesn't work",
        "doesnt work",
        "not working",
        "test",
        "hi",
        "hello",
    }

    def check_insufficient_information(self, subject: str, description: str) -> bool:
        """Determine whether the ticket lacks sufficient informative context for automated triage.

        Args:
            subject: Ticket subject text.
            description: Ticket description text.

        Returns:
            True if text is trivial, blank, or lacks detail, otherwise False.
        """
        cleaned_sub = re.sub(r"[^\w\s]", "", subject).strip().lower()
        cleaned_desc = re.sub(r"[^\w\s]", "", description).strip().lower()
        combined = f"{cleaned_sub} {cleaned_desc}".strip()

        if len(combined) < 12:
            return True

        if combined in self.TRIVIAL_WORDS:
            return True

        if cleaned_desc in self.TRIVIAL_WORDS and (
            not cleaned_sub or cleaned_sub in self.TRIVIAL_WORDS
        ):
            return True

        return False

    def evaluate_ticket_content(self, subject: str, description: str) -> tuple[bool, str | None]:
        """Evaluate ticket text against content-based mandatory escalation rules.

        Checks for legal threats, security incidents, human representative requests,
        insufficient detail, sensitive financial disputes, and company policy violations.

        Args:
            subject: Ticket subject text.
            description: Ticket description text.

        Returns:
            Tuple of (requires_human, escalation_reason).
        """
        full_text = f"{subject} {description}"

        if self.LEGAL_PATTERNS.search(full_text):
            return True, "Mandatory escalation: Legal issues or legal threats involved."

        if self.SECURITY_PATTERNS.search(full_text):
            return True, "Mandatory escalation: Fraud or security incident reported."

        if self.HUMAN_REQUEST_PATTERNS.search(full_text):
            return True, "Mandatory escalation: Customer explicitly requested a human agent."

        if self.check_insufficient_information(subject, description):
            return (
                True,
                "Mandatory escalation: Insufficient information provided in ticket to resolve.",
            )

        if self.FINANCIAL_PATTERNS.search(full_text):
            return (
                True,
                "Mandatory escalation: Sensitive financial matter requiring investigation.",
            )

        if self.POLICY_VIOLATION_PATTERNS.search(full_text):
            return True, "Mandatory escalation: Request falls outside company policies."

        return False, None

    def evaluate_confidence(
        self,
        confidence_score: float,
        threshold: float = settings.CONFIDENCE_THRESHOLD,
    ) -> tuple[bool, str | None]:
        """Verify whether AI model confidence meets the required quality threshold.

        Args:
            confidence_score: Model confidence score float between 0.0 and 1.0.
            threshold: Minimum acceptable confidence threshold.

        Returns:
            Tuple of (is_below_threshold, escalation_reason).
        """
        if confidence_score < threshold:
            return True, (
                f"Mandatory escalation: AI confidence score ({confidence_score:.2f}) is "
                f"below configured threshold ({threshold:.2f})."
            )
        return False, None

    def enforce_policy(
        self,
        subject: str,
        description: str,
        llm_result: QueryClassification,
        threshold: float = settings.CONFIDENCE_THRESHOLD,
    ) -> tuple[bool, str | None]:
        """Enforce complete escalation policy combining content rules, confidence, and model flags.

        Guarantees that deterministic mandatory rules cannot be overridden by model outputs.

        Args:
            subject: Ticket subject text.
            description: Ticket description text.
            llm_result: Structured classification output from the AI agent.
            threshold: Minimum acceptable confidence score threshold.

        Returns:
            Tuple of (requires_human, escalation_reason).
        """
        content_escalated, content_reason = self.evaluate_ticket_content(subject, description)
        if content_escalated:
            logger.info("Escalation triggered by content rule: %s", content_reason)
            return True, content_reason

        confidence_escalated, confidence_reason = self.evaluate_confidence(
            llm_result.confidence_score, threshold=threshold
        )
        if confidence_escalated:
            logger.info("Escalation triggered by confidence threshold: %s", confidence_reason)
            return True, confidence_reason

        if llm_result.requires_human:
            reason = llm_result.escalation_reason or "Escalated by AI analysis recommendation."
            logger.info("Escalation triggered by LLM provider: %s", reason)
            return True, reason

        return False, None


escalation_engine: EscalationPolicyEngine = EscalationPolicyEngine()
