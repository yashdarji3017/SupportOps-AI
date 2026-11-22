import re

from backend.app.core.logging import logger
from backend.app.schemas.ticket import TicketCategory


class ReplySafetyService:
    """Validates and sanitizes AI-generated suggested customer replies."""

    UNAUTHORIZED_REFUND_CLAIMS: re.Pattern[str] = re.compile(
        r"\b(refund has been approved|refunded your|credited your account|"
        r"processed your refund of|money has been sent back|refund is complete)\b",
        re.IGNORECASE,
    )

    UNSUPPORTED_RESOLUTION_CLAIMS: re.Pattern[str] = re.compile(
        r"\b(issue is now resolved|bug has been fixed|problem is solved|"
        r"we have fixed the error|system is restored)\b",
        re.IGNORECASE,
    )

    @classmethod
    def sanitize_reply(
        cls,
        reply: str | None,
        requires_human: bool,
        category: TicketCategory,
    ) -> str | None:
        """Sanitize AI suggested reply against compliance and policy rules.

        Ensures that suggested_reply is strictly None when escalation applies,
        and sanitizes unauthorized financial commitments or premature resolution
        declarations.

        Args:
            reply: The raw suggested reply string, or None.
            requires_human: Flag indicating whether human escalation applies.
            category: Classified ticket category.

        Returns:
            The sanitized reply string, or None if escalation applies or input is empty.
        """
        if requires_human:
            return None

        if not reply or not reply.strip():
            return None

        cleaned = reply.strip()

        if cls.UNAUTHORIZED_REFUND_CLAIMS.search(cleaned):
            logger.warning("Suggested reply contained unauthorized refund approval. Sanitizing.")
            cleaned = cls.UNAUTHORIZED_REFUND_CLAIMS.sub(
                "request has been forwarded to our finance department for review", cleaned
            )

        if cls.UNSUPPORTED_RESOLUTION_CLAIMS.search(cleaned):
            logger.warning("Suggested reply contained premature resolution claim. Sanitizing.")
            cleaned = cls.UNSUPPORTED_RESOLUTION_CLAIMS.sub(
                "team is actively investigating this report", cleaned
            )

        return cleaned


reply_safety_service: ReplySafetyService = ReplySafetyService()
