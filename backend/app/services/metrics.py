import asyncio

from backend.app.core.concurrency import concurrency_limiter
from backend.app.schemas.response import MetricsResponse


class MetricsService:
    """Thread-safe, in-memory metrics collector for tracking throughput and performance."""

    def __init__(self) -> None:
        """Initialize operational metric counters and synchronization primitives."""
        self._lock: asyncio.Lock = asyncio.Lock()
        self._active_requests: int = 0
        self._total_processed: int = 0
        self._failed_requests: int = 0
        self._escalated_requests: int = 0

    async def increment_active(self) -> None:
        """Increment count of currently active in-flight HTTP requests."""
        async with self._lock:
            self._active_requests += 1

    async def decrement_active(self) -> None:
        """Decrement count of currently active in-flight HTTP requests."""
        async with self._lock:
            self._active_requests = max(0, self._active_requests - 1)

    async def record_processed(self, is_escalated: bool) -> None:
        """Record completion of a ticket analysis operation.

        Args:
            is_escalated: Flag indicating whether the ticket required human escalation.
        """
        async with self._lock:
            self._total_processed += 1
            if is_escalated:
                self._escalated_requests += 1

    async def record_failure(self) -> None:
        """Record an unexpected execution failure or exception."""
        async with self._lock:
            self._failed_requests += 1

    async def reset(self) -> None:
        """Reset all in-memory operational metrics to zero."""
        async with self._lock:
            self._active_requests = 0
            self._total_processed = 0
            self._failed_requests = 0
            self._escalated_requests = 0

    def get_metrics_sync(self) -> MetricsResponse:
        """Generate a synchronous snapshot of operational performance metrics.

        Returns:
            A validated MetricsResponse schema containing current metric counters.
        """
        return MetricsResponse(
            active_requests=self._active_requests,
            max_concurrent_requests=concurrency_limiter.max_concurrent_requests,
            current_concurrent_requests=concurrency_limiter.current_concurrent_requests,
            total_processed_requests=self._total_processed,
            failed_requests=self._failed_requests,
            escalated_requests=self._escalated_requests,
        )

    async def get_metrics(self) -> MetricsResponse:
        """Generate an asynchronous concurrency-safe snapshot of operational metrics.

        Returns:
            A validated MetricsResponse schema containing current metric counters.
        """
        async with self._lock:
            return self.get_metrics_sync()


metrics_service: MetricsService = MetricsService()
