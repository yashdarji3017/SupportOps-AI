import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from backend.app.core.logging import current_request_id_var, logger


@dataclass
class RequestContext:
    """Isolated per-request execution context bound to an async task."""

    request_id: str
    ticket_id: str
    start_time: float
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def elapsed_ms(self) -> float:
        """Calculate elapsed execution duration in milliseconds since session creation.

        Returns:
            Float representing elapsed duration in milliseconds.
        """
        return (time.time() - self.start_time) * 1000.0


_active_request_context_var: ContextVar[RequestContext | None] = ContextVar(
    "active_request_context", default=None
)


class SessionManager:
    """Manages creation, binding, and cleanup of per-request execution sessions."""

    @classmethod
    def get_current_context(cls) -> RequestContext | None:
        """Retrieve the RequestContext bound to the current async task execution.

        Returns:
            The active RequestContext instance if currently inside a session, else None.
        """
        return _active_request_context_var.get()

    @classmethod
    @asynccontextmanager
    async def create_session(cls, ticket_id: str | None = None) -> AsyncIterator[RequestContext]:
        """Create an isolated request session with a unique UUID and bound ContextVars.

        Ensures full lifecycle tracking and resource cleanup on completion.

        Args:
            ticket_id: Optional client-specified ticket ID. Automatically generates
                a prefixed ticket ID if omitted.

        Yields:
            An active, isolated RequestContext instance.
        """
        request_id = str(uuid.uuid4())
        assigned_ticket_id = (
            ticket_id.strip()
            if ticket_id and ticket_id.strip()
            else f"TICKET-{request_id[:8].upper()}"
        )

        ctx = RequestContext(
            request_id=request_id,
            ticket_id=assigned_ticket_id,
            start_time=time.time(),
        )

        token_id = current_request_id_var.set(request_id)
        token_ctx = _active_request_context_var.set(ctx)

        logger.debug("Session started for ticket %s", assigned_ticket_id)
        try:
            yield ctx
        finally:
            logger.debug(
                "Session completed for ticket %s in %.1fms",
                assigned_ticket_id,
                ctx.elapsed_ms,
            )
            ctx.metadata.clear()
            current_request_id_var.reset(token_id)
            _active_request_context_var.reset(token_ctx)


session_manager: SessionManager = SessionManager()
