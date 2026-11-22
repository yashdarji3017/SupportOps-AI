from fastapi import APIRouter, HTTPException, status

from backend.app.core.logging import logger
from backend.app.schemas.response import BatchAnalysisResponse, TicketAnalysisResponse
from backend.app.schemas.ticket import BatchTicketRequest, TicketRequest
from backend.app.services.metrics import metrics_service
from backend.app.services.ticket_analyzer import ticket_analyzer_service

router = APIRouter(prefix="/tickets", tags=["Tickets"])


@router.post(
    "/analyze",
    response_model=TicketAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze Customer Support Ticket",
    description="Categorizes ticket, detects priority, calculates confidence, checks escalation rules, and returns suggested reply if safe.",
)
async def analyze_ticket(request: TicketRequest) -> TicketAnalysisResponse:
    """Analyze a single customer support ticket.

    Performs category classification, priority assignment, confidence scoring,
    independent human escalation verification, and suggested reply sanitization
    within an isolated execution context.

    Args:
        request: The incoming ticket request containing subject, description,
            and optional customer metadata.

    Returns:
        A validated TicketAnalysisResponse with classification and escalation details.

    Raises:
        HTTPException: HTTP 504 on execution timeout or HTTP 500 on unexpected errors.
    """
    await metrics_service.increment_active()
    try:
        return await ticket_analyzer_service.analyze_ticket(request)
    except TimeoutError as exc:
        logger.error("Request timeout while analyzing ticket: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error("Internal server error analyzing ticket: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while analyzing the ticket: {exc}",
        ) from exc
    finally:
        await metrics_service.decrement_active()


@router.post(
    "/analyze/batch",
    response_model=BatchAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Batch Analyze Customer Support Tickets",
    description="Asynchronously analyzes multiple tickets while enforcing the concurrency limit and session isolation.",
)
async def analyze_tickets_batch(batch_request: BatchTicketRequest) -> BatchAnalysisResponse:
    """Analyze a batch of support tickets asynchronously.

    Dispatches analysis tasks concurrently for all tickets in the batch,
    ensuring each ticket maintains session isolation and respects the
    process-wide concurrency limit while isolating individual ticket errors.

    Args:
        batch_request: Batch container holding multiple TicketRequest items.

    Returns:
        A BatchAnalysisResponse containing per-ticket results and failure details.

    Raises:
        HTTPException: HTTP 500 on batch coordination failures.
    """
    await metrics_service.increment_active()
    try:
        return await ticket_analyzer_service.analyze_batch(batch_request)
    except Exception as exc:
        logger.error("Internal server error during batch analysis: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during batch analysis: {exc}",
        ) from exc
    finally:
        await metrics_service.decrement_active()
