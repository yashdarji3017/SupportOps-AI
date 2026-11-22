from backend.app.schemas.ticket import TicketCategory


class ClassificationService:
    """Service handling category classification heuristics and validation."""

    CATEGORY_KEYWORDS: dict[TicketCategory, list[str]] = {
        TicketCategory.REFUND: [
            "refund",
            "money back",
            "reimbursement",
            "return item",
            "refund policy",
            "cancel order refund",
            "refund status",
            "credit back",
        ],
        TicketCategory.BILLING: [
            "invoice",
            "billing",
            "charged twice",
            "charge",
            "subscription",
            "credit card",
            "payment failed",
            "pricing",
            "renew",
            "receipt",
            "overcharged",
        ],
        TicketCategory.ACCOUNT: [
            "password",
            "login",
            "account",
            "2fa",
            "mfa",
            "username",
            "profile",
            "locked out",
            "reset password",
            "change email",
            "delete account",
        ],
        TicketCategory.TECHNICAL: [
            "error",
            "bug",
            "crash",
            "500",
            "latency",
            "slow",
            "api",
            "glitch",
            "stack trace",
            "timeout",
            "not loading",
            "failed to connect",
            "broken",
        ],
        TicketCategory.COMPLAINTS: [
            "complaint",
            "terrible",
            "horrible",
            "unacceptable",
            "furious",
            "angry",
            "poor service",
            "rude support",
            "dissatisfied",
            "worst experience",
            "bad service",
        ],
        TicketCategory.GENERAL_INQUIRIES: [
            "hours",
            "pricing question",
            "feature inquiry",
            "documentation",
            "how to",
            "sales",
            "general information",
            "help center",
        ],
    }

    @classmethod
    def get_supported_categories(cls) -> list[str]:
        """Retrieve list of all supported category string representations.

        Returns:
            List of supported category string names.
        """
        return [c.value for c in TicketCategory]

    @classmethod
    def classify_heuristics(cls, text: str) -> TicketCategory:
        """Classify input text using deterministic keyword matching heuristics.

        Args:
            text: Combined ticket subject and description text.

        Returns:
            The matched TicketCategory, defaulting to GENERAL_INQUIRIES if no match.
        """
        lower = text.lower()
        for category in [
            TicketCategory.REFUND,
            TicketCategory.BILLING,
            TicketCategory.ACCOUNT,
            TicketCategory.TECHNICAL,
            TicketCategory.COMPLAINTS,
        ]:
            if any(keyword in lower for keyword in cls.CATEGORY_KEYWORDS[category]):
                return category
        return TicketCategory.GENERAL_INQUIRIES


classification_service: ClassificationService = ClassificationService()
