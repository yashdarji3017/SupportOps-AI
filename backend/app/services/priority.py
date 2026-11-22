from backend.app.schemas.ticket import TicketPriority


class PriorityService:
    """Service handling priority detection heuristics and validation."""

    PRIORITY_KEYWORDS: dict[TicketPriority, list[str]] = {
        TicketPriority.CRITICAL: [
            "outage",
            "system down",
            "data breach",
            "critical",
            "catastrophic",
            "production down",
            "all users affected",
            "security vulnerability",
            "server down",
            "emergency",
            "severity 1",
            "sev 1",
        ],
        TicketPriority.HIGH: [
            "urgent",
            "asap",
            "locked out",
            "cannot login",
            "payment failed",
            "broken",
            "immediately",
            "deadline",
            "blocking",
            "high priority",
            "unauthorized charge",
            "double charged",
        ],
        TicketPriority.MEDIUM: [
            "medium",
            "slow",
            "delay",
            "glitch",
            "inconvenience",
            "minor bug",
            "refund status",
            "update account",
        ],
        TicketPriority.LOW: [
            "general question",
            "feature request",
            "feedback",
            "suggestion",
            "documentation",
            "how to",
            "curious",
            "inquiry",
            "low priority",
        ],
    }

    @classmethod
    def get_supported_priorities(cls) -> list[str]:
        """Retrieve list of all supported priority string representations.

        Returns:
            List of supported priority string names.
        """
        return [p.value for p in TicketPriority]

    @classmethod
    def detect_priority_heuristics(cls, text: str) -> TicketPriority:
        """Detect urgency priority level based on keyword urgency signals.

        Args:
            text: Ticket text containing subject and description.

        Returns:
            The matched TicketPriority, defaulting to MEDIUM if no strong signal.
        """
        lower = text.lower()
        for priority in [
            TicketPriority.CRITICAL,
            TicketPriority.HIGH,
            TicketPriority.LOW,
        ]:
            if any(keyword in lower for keyword in cls.PRIORITY_KEYWORDS[priority]):
                return priority
        return TicketPriority.MEDIUM


priority_service: PriorityService = PriorityService()
