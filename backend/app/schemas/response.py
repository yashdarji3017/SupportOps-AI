from pydantic import BaseModel, Field, model_validator

from backend.app.schemas.ticket import TicketCategory, TicketPriority


class TicketAnalysisResponse(BaseModel):
    """Structured response produced for a single analyzed customer ticket."""

    ticket_id: str = Field(
        ...,
        description="Unique identifier for the ticket.",
        examples=["TICKET-001"],
    )
    request_id: str = Field(
        ...,
        description="Unique UUID generated for this request execution context.",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    category: TicketCategory = Field(
        ...,
        description="Classified ticket category.",
        examples=[TicketCategory.BILLING],
    )
    priority: TicketPriority = Field(
        ...,
        description="Assigned ticket priority level.",
        examples=[TicketPriority.HIGH],
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="AI confidence score between 0.0 and 1.0.",
        examples=[0.94],
    )
    suggested_reply: str | None = Field(
        default=None,
        description="Professional suggested reply for customer. Must be null if requires_human is true.",
        examples=["Thank you for contacting support..."],
    )
    requires_human: bool = Field(
        ...,
        description="Flag indicating whether human agent intervention/approval is required.",
        examples=[False],
    )
    escalation_reason: str | None = Field(
        default=None,
        description="Clear explanation if human escalation is required. Null otherwise.",
        examples=[None],
    )

    @model_validator(mode="after")
    def validate_escalation_consistency(self) -> "TicketAnalysisResponse":
        """Enforce strict invariant consistency between escalation and suggested reply.

        Guarantees that when human intervention is flagged, suggested replies are null
        and an explanatory reason is provided.

        Returns:
            The validated TicketAnalysisResponse instance.

        Raises:
            ValueError: If requires_human is True but suggested_reply is not None
                or escalation_reason is missing.
        """
        if self.requires_human:
            if self.suggested_reply is not None:
                raise ValueError("suggested_reply must be null (None) when requires_human is true.")
            if not self.escalation_reason:
                raise ValueError("escalation_reason must be provided when requires_human is true.")
        return self


class BatchItemFailure(BaseModel):
    """Failure representation for an individual ticket within a batch execution."""

    ticket_id: str | None = None
    request_id: str
    error: str


class BatchAnalysisResponse(BaseModel):
    """Aggregate response payload for multi-ticket batch processing."""

    total_tickets: int = Field(..., description="Total tickets received in batch.")
    successful_count: int = Field(..., description="Count of successfully analyzed tickets.")
    failed_count: int = Field(..., description="Count of failed ticket analyses.")
    results: list[TicketAnalysisResponse] = Field(
        default_factory=list,
        description="Analysis results for processed tickets.",
    )
    errors: list[BatchItemFailure] = Field(
        default_factory=list,
        description="Details of any tickets that failed processing.",
    )


class HealthResponse(BaseModel):
    """Application health and runtime status response schema."""

    status: str = Field(default="healthy", description="Application health status.")
    app_name: str = Field(..., description="Name of the application.")
    version: str = Field(..., description="Application version.")
    provider: str = Field(..., description="Active LLM provider name.")
    timestamp: str = Field(..., description="ISO 8601 server timestamp.")
    uptime_seconds: float = Field(..., description="Server uptime in seconds.")


class MetricsResponse(BaseModel):
    """In-memory operational metrics performance counters."""

    active_requests: int = Field(
        ..., description="Current in-flight requests being handled by the server."
    )
    max_concurrent_requests: int = Field(
        ..., description="Maximum allowed simultaneous processing operations per process."
    )
    current_concurrent_requests: int = Field(
        ..., description="Current processing operations actively holding concurrency semaphore."
    )
    total_processed_requests: int = Field(
        ..., description="Total lifetime processed tickets completed by this process."
    )
    failed_requests: int = Field(
        ..., description="Total lifetime requests that resulted in an error or failure."
    )
    escalated_requests: int = Field(
        ..., description="Total lifetime requests escalated to human agents."
    )
