"""
Structured Logging Configuration with structlog
"""

import logging
import sys
from typing import Any, Dict

import structlog


def configure_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """
    Configure structlog for JSON structured logging

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Output format ("json" or "console")
    """
    # Set standard library logging level
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )

    # Configure structlog processors
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if log_format == "json":
        # JSON format for production
        processors = shared_processors + [
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Console format for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    """
    Bind context variables to all log messages in current context

    Args:
        **kwargs: Key-value pairs to add to log context
    """
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(**kwargs)


def log_event(
    logger: structlog.stdlib.BoundLogger,
    event: str,
    level: str = "info",
    **kwargs: Any,
) -> None:
    """
    Log a structured event with additional context

    Args:
        logger: Structlog logger instance
        event: Event name/description
        level: Log level (debug, info, warning, error, critical)
        **kwargs: Additional context fields
    """
    log_func = getattr(logger, level.lower())
    log_func(event, **kwargs)


def log_masked_field(
    logger: structlog.stdlib.BoundLogger,
    field_name: str,
    classification: str,
    masking_strategy: str,
    table_name: str,
    event_id: str,
) -> None:
    """
    Log PII/PHI field masking event (audit trail)

    Args:
        logger: Structlog logger
        field_name: Name of masked field
        classification: PII, PHI, or SENSITIVE
        masking_strategy: HASH, HMAC, or PASSTHROUGH
        table_name: Table containing the field
        event_id: Change event ID for correlation
    """
    logger.info(
        "field_masked",
        field_name=field_name,
        classification=classification,
        masking_strategy=masking_strategy,
        table_name=table_name,
        event_id=event_id,
    )


def log_replication_event(
    logger: structlog.stdlib.BoundLogger,
    event_id: str,
    table_name: str,
    destination: str,
    event_type: str,
    duration_ms: float,
    success: bool,
    error: str = None,
) -> None:
    """
    Log replication event (success or failure)

    Args:
        logger: Structlog logger
        event_id: Change event ID
        table_name: Source table name
        destination: Target warehouse (postgres, clickhouse, timescaledb)
        event_type: INSERT, UPDATE, or DELETE
        duration_ms: Replication duration in milliseconds
        success: Whether replication succeeded
        error: Error message if failed
    """
    log_data = {
        "event": "replication_completed" if success else "replication_failed",
        "event_id": event_id,
        "table_name": table_name,
        "destination": destination,
        "event_type": event_type,
        "duration_ms": duration_ms,
        "success": success,
    }

    if error:
        log_data["error"] = error

    if success:
        logger.info(**log_data)
    else:
        logger.error(**log_data)
