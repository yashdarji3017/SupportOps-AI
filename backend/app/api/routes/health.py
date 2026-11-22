import time
from datetime import UTC, datetime

from fastapi import APIRouter, status

from backend.app.core.config import settings
from backend.app.schemas.response import HealthResponse

router = APIRouter(tags=["Health"])

START_TIME: float = time.time()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Application Health Check",
    description="Returns current status, uptime, and runtime metadata of the triage bot service.",
)
async def get_health() -> HealthResponse:
    """Retrieve service health status, provider details, and uptime metrics.

    Calculates application uptime since process initialization and builds
    a timestamped health status payload.

    Returns:
        A validated HealthResponse schema with system health metadata.
    """
    uptime = time.time() - START_TIME
    return HealthResponse(
        status="healthy",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        provider=settings.LLM_PROVIDER,
        timestamp=datetime.now(UTC).isoformat(),
        uptime_seconds=round(uptime, 2),
    )
