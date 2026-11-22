import logging


def get_logger(name: str = "triage_bot") -> logging.Logger:
    """Retrieve a named application logger instance.

    Args:
        name: The logger namespace name, defaulting to 'triage_bot'.

    Returns:
        A standard logging.Logger instance.
    """
    return logging.getLogger(name)
