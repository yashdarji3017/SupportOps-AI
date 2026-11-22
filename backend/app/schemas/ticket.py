from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class TicketCategory(StrEnum):
    """Supported ticket categories."""

    BILLING = "Billing"
    TECHNICAL = "Technical"
    ACCOUNT = "Account"
    REFUND = "Refund"
    COMPLAINTS = "Complaints"
    GENERAL_INQUIRIES = "General Inquiries"


class TicketPriority(StrEnum):
    """Supported ticket urgency priority tiers."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class TicketRequest(BaseModel):
    """Single customer support ticket analysis request schema."""

    ticket_id: str | None = Field(
        default=None,
        description="Optional client-specified ticket ID. Generated automatically if omitted.",
        examples=["TICKET-001"],
    )
    subject: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Subject of the support ticket.",
        examples=["Cannot log in to my account"],
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Detailed description of the customer inquiry or issue.",
        examples=["I forgot my password and the reset email is not arriving."],
    )
    customer_name: str | None = Field(
        default=None,
        max_length=100,
        description="Optional customer name.",
        examples=["Jane Doe"],
    )

    @field_validator("subject", "description")
    @classmethod
    def validate_not_blank(cls, value: str) -> str:
        """Validate that text fields contain non-whitespace characters.

        Args:
            value: The string value to validate.

        Returns:
            The stripped, non-empty string.

        Raises:
            ValueError: If the trimmed string is empty.
        """
        if not value or not value.strip():
            raise ValueError("Field cannot be empty or purely whitespace.")
        return value.strip()


class BatchTicketRequest(BaseModel):
    """Batch container for multi-ticket concurrent analysis requests."""

    tickets: list[TicketRequest] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of tickets to process in batch (max 100 tickets).",
    )
