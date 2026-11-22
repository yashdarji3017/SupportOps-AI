from pydantic import BaseModel, Field

from backend.app.schemas.ticket import TicketCategory, TicketPriority


class QueryClassification(BaseModel):
    """Structured output schema returned by the query classification agent."""

    category: TicketCategory = Field(
        ...,
        description="Classified ticket category",
    )
    priority: TicketPriority = Field(
        ...,
        description="Assigned ticket priority level",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="AI model confidence score between 0.0 and 1.0",
    )
    suggested_reply: str | None = Field(
        default=None,
        description="Professional suggested reply for customer. Must be null if requires_human is true.",
    )
    requires_human: bool = Field(
        default=False,
        description="Flag indicating whether human agent intervention is required.",
    )
    escalation_reason: str | None = Field(
        default=None,
        description="Clear explanation if human escalation is required. Null otherwise.",
    )
    raw_response: str | None = Field(
        default=None,
        description="Raw model output or representation if available.",
    )
