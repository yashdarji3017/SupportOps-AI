import contextvars
import logging
import sys

current_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_request_id", default=None
)


class RequestContextFilter(logging.Filter):
    """Filter that injects the current execution request_id into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Inject active task request identifier into the logging record.

        Args:
            record: The logging LogRecord to be formatted.

        Returns:
            Always returns True to allow record processing.
        """
        request_id = current_request_id_var.get()
        record.request_id = request_id if request_id else "-"  # type: ignore[attr-defined]
        return True


def setup_logging(debug: bool = False) -> logging.Logger:
    """Configure structured console logging with request ID tracking.

    Args:
        debug: Boolean flag indicating whether DEBUG level logs should be emitted.

    Returns:
        Configured Logger instance for the triage application.
    """
    app_logger = logging.getLogger("triage_bot")
    app_logger.setLevel(logging.DEBUG if debug else logging.INFO)

    if not app_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG if debug else logging.INFO)

        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [req:%(request_id)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        handler.setFormatter(formatter)
        handler.addFilter(RequestContextFilter())
        app_logger.addHandler(handler)

    return app_logger


logger: logging.Logger = setup_logging()
