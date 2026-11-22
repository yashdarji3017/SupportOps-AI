from fastapi import APIRouter, status

from backend.app.schemas.response import MetricsResponse
from backend.app.services.metrics import metrics_service

router = APIRouter(tags=["Metrics"])


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Operational Metrics",
    description="Retrieves in-memory statistics including active requests, concurrency semaphore status, processed, failed, and escalated counts.",
)
async def get_metrics() -> MetricsResponse:
    """Retrieve runtime in-memory operational metrics counters.

    Fetches thread-safe metrics regarding active and total processed requests,
    failures, human escalations, and active concurrency permits without
    retaining or exposing any customer PII.

    Returns:
        A validated MetricsResponse schema containing current performance counters.
    """
    return await metrics_service.get_metrics()
