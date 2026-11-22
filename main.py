from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler

from backend.app.core.logging import logger
from backend.app.core.config import settings
from backend.app.api.routes import health_router, metrics_router, tickets_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle events.

    Performs configuration validation at startup, ensuring that external provider
    credentials are supplied when required, and logs operational bounds.

    Args:
        app: The FastAPI application instance.

    Yields:
        None while the application is active.

    Raises:
        ValueError: If provider settings fail initialization validation.
    """
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)
    logger.info("Active LLM Provider: %s", settings.LLM_PROVIDER)
    logger.info("Concurrency Limit: %d requests/process", settings.MAX_CONCURRENT_REQUESTS)
    logger.info("Confidence Threshold: %.2f", settings.CONFIDENCE_THRESHOLD)

    if settings.LLM_PROVIDER == "gemini" and not settings.GEMINI_API_KEY:
        logger.error("Startup validation failure: GEMINI_API_KEY required for gemini provider.")
        raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER is 'gemini'.")

    yield

    logger.info("Shutting down %s", settings.APP_NAME)


API_DESCRIPTION: str = """
## AI-Powered Customer Support Triage Bot — Backend API

An enterprise-grade, backend-only triage service that analyzes incoming customer support tickets to:
* **Classify Categories:** Billing, Technical, Account, Refund, Complaints, General Inquiries.
* **Detect Priority:** Low, Medium, High, Critical.
* **Calculate Confidence:** Calibrated score between `0.0` and `1.0`.
* **Generate Safe Replies:** Context-aware suggested responses with automatic compliance sanitization.
* **Enforce Mandatory Escalation:** Independent policy engine that the LLM cannot override for legal threats, security incidents, explicit human requests, and sensitive financial disputes.

### Documentation & Exploration:
* **Interactive Swagger UI:** [/docs](/docs)
* **ReDoc Documentation:** [/redoc](/redoc)
* **OpenAPI JSON Specification:** [/openapi.json](/openapi.json)
"""

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=API_DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


@app.get(
    "/",
    tags=["Root"],
    summary="API Root Information and Directory",
    description="Provides an overview of the Customer Support Triage Bot service, its purpose, documentation links, and available endpoints.",
)
async def root() -> dict[str, object]:
    """Provide service description, documentation links, and available endpoints."""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "description": (
            "Backend-only AI-powered Customer Support Triage Bot that automatically classifies support tickets, "
            "identifies priority levels, calculates confidence scores, generates safe contextual replies, "
            "and enforces mandatory human escalation for sensitive or legal issues."
        ),
        "documentation": {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "openapi_json": "/openapi.json",
        },
        "endpoints": {
            "root": "/",
            "health": "/health",
            "metrics": "/metrics",
            "analyze_ticket": "/tickets/analyze",
            "batch_analyze_tickets": "/tickets/analyze/batch",
            "api_v1_prefix": "/api/v1",
        },
        "supported_categories": [
            "Billing",
            "Technical",
            "Account",
            "Refund",
            "Complaints",
            "General Inquiries",
        ],
        "supported_priorities": ["Low", "Medium", "High", "Critical"],
        "concurrency_limit": settings.MAX_CONCURRENT_REQUESTS,
        "confidence_threshold": settings.CONFIDENCE_THRESHOLD,
        "active_provider": settings.LLM_PROVIDER,
    }


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> Response:
    """Handle incoming request payload schema validation errors.

    Logs request validation failures and returns a standard HTTP 422
    JSON response detailing the validation errors.

    Args:
        request: The incoming HTTP request.
        exc: Validation error details raised by Pydantic.

    Returns:
        A standard HTTP 422 JSON response.
    """
    logger.warning("Request validation error on %s: %s", request.url.path, exc.errors())
    return await request_validation_exception_handler(request, exc)


@app.exception_handler(TimeoutError)
async def timeout_exception_handler(request: Request, exc: TimeoutError) -> JSONResponse:
    """Handle processing timeouts across async ticket execution pipelines.

    Args:
        request: The incoming HTTP request.
        exc: The timeout exception encountered.

    Returns:
        JSONResponse with HTTP 504 Gateway Timeout status.
    """
    logger.error("Timeout processing request on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        content={"detail": "Processing timed out. Please try again."},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all exception handler for unhandled server exceptions.

    Safely logs the exception trace without leaking sensitive internals
    or customer PII to the client.

    Args:
        request: The incoming HTTP request.
        exc: The unhandled exception.

    Returns:
        JSONResponse with HTTP 500 Internal Server Error status.
    """
    logger.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred while processing the request."},
    )


app.include_router(tickets_router, prefix="/api/v1")
app.include_router(health_router, prefix="/api/v1")
app.include_router(metrics_router, prefix="/api/v1")


app.include_router(tickets_router, include_in_schema=False)
app.include_router(health_router, include_in_schema=False)
app.include_router(metrics_router, include_in_schema=False)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
