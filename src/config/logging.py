"""Structured logging: JSON lines to stdout (ready for CloudWatch later)."""

from typing import Any

import structlog

SHARED_PROCESSORS: list[Any] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.StackInfoRenderer(),
]


def build_logging_config(level: str = "INFO", fmt: str = "json") -> dict[str, Any]:
    renderer: Any = (
        structlog.processors.JSONRenderer()
        if fmt == "json"
        else structlog.dev.ConsoleRenderer(colors=False)
    )
    structlog.configure(
        processors=[
            *SHARED_PROCESSORS,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "structured": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processors": [
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    structlog.processors.format_exc_info,
                    renderer,
                ],
                "foreign_pre_chain": SHARED_PROCESSORS,
            }
        },
        "handlers": {"stdout": {"class": "logging.StreamHandler", "formatter": "structured"}},
        "root": {"handlers": ["stdout"], "level": level},
        "loggers": {
            "django": {"handlers": ["stdout"], "level": level, "propagate": False},
            # Never log request bodies; 4xx noise kept at WARNING.
            "django.request": {"handlers": ["stdout"], "level": "WARNING", "propagate": False},
            "django.db.backends": {"handlers": ["stdout"], "level": "WARNING", "propagate": False},
            "apscheduler": {"handlers": ["stdout"], "level": "WARNING", "propagate": False},
        },
    }
