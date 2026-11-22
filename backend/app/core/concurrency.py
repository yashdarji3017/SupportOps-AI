import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from backend.app.core.config import settings
from backend.app.core.logging import logger


class ConcurrencyLimiter:
    """Manages in-memory asynchronous concurrency permits for ticket processing."""

    def __init__(self, max_concurrent: int = settings.MAX_CONCURRENT_REQUESTS) -> None:
        """Initialize the concurrency limiter with a maximum capacity.

        Args:
            max_concurrent: Positive integer denoting max concurrent operations.

        Raises:
            ValueError: If max_concurrent is less than 1.
        """
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be at least 1")
        self._max_concurrent: int = max_concurrent
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(max_concurrent)
        self._current_concurrent: int = 0
        self._lock: asyncio.Lock = asyncio.Lock()

    @property
    def max_concurrent_requests(self) -> int:
        """Configured maximum concurrent requests allowed."""
        return self._max_concurrent

    @property
    def current_concurrent_requests(self) -> int:
        """Number of requests currently holding a concurrency permit."""
        return self._current_concurrent

    @asynccontextmanager
    async def acquire(
        self, timeout: float = settings.REQUEST_TIMEOUT_SECONDS
    ) -> AsyncIterator[None]:
        """Asynchronously acquire a concurrency permit with a timeout.

        Guarantees permit release across cancellation, exceptions, and timeouts.

        Args:
            timeout: Maximum wait time in seconds to acquire a permit.

        Yields:
            None once the permit is acquired.

        Raises:
            TimeoutError: If permit cannot be acquired within the timeout window.
        """
        acquired = False
        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=timeout)
            acquired = True

            async with self._lock:
                self._current_concurrent += 1

            logger.debug(
                "Concurrency slot acquired. Active: %d/%d",
                self._current_concurrent,
                self._max_concurrent,
            )
            yield

        except TimeoutError as exc:
            logger.error("Timed out waiting for concurrency permit after %.1fs", timeout)
            raise TimeoutError(
                f"Server busy: Concurrency permit could not be acquired within {timeout}s"
            ) from exc
        finally:
            if acquired:
                async with self._lock:
                    self._current_concurrent = max(0, self._current_concurrent - 1)
                self._semaphore.release()
                logger.debug(
                    "Concurrency slot released. Active: %d/%d",
                    self._current_concurrent,
                    self._max_concurrent,
                )


concurrency_limiter = ConcurrencyLimiter(max_concurrent=settings.MAX_CONCURRENT_REQUESTS)
