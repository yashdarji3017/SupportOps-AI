"""API routes package exporting route modules."""

from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.metrics import router as metrics_router
from backend.app.api.routes.tickets import router as tickets_router

__all__ = ["health_router", "metrics_router", "tickets_router"]
