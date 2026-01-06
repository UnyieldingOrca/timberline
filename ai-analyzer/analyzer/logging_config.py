"""Centralized logging configuration for AI Analyzer"""
import os
import sys
import logging
import json
from loguru import logger


class InterceptHandler(logging.Handler):
    """
    Intercept standard logging messages and route them through loguru.
    This ensures all logs (uvicorn, alembic, etc.) use the same format.
    """
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

def json_sink(message):
    """
    Custom sink for JSON Lines output.
    Extracts the record and serializes to clean JSON format.
    """
    record = message.record
    log_entry = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "logger": record["name"],
        "file": record["file"].name,
        "line": record["line"],
        "function": record["function"],
        "module": record["module"],
        "process_id": record["process"].id,
        "thread_id": record["thread"].id,
    }

    # Add exception info if present
    if record["exception"]:
        log_entry["exception"] = str(record["exception"])

    # Add extra data if present
    if record["extra"]:
        log_entry["extra"] = record["extra"]

    serialized = json.dumps(log_entry) + "\n"
    sys.stderr.write(serialized)
    sys.stderr.flush()


def configure_logging(
    level: str = None,
    json_format: bool = None,
    verbose: bool = False,
    quiet: bool = False
):
    """
    Configure loguru logger with JSON Lines format for structured logging.

    Uses standard loguru environment variables when available:
    - LOGURU_LEVEL: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - LOGURU_FORMAT: Custom format string (only for text mode)
    - LOG_FORMAT: Custom env var to control json vs text (json or text)

    Args:
        level: Logging level (default: from LOGURU_LEVEL or INFO)
        json_format: Use JSON Lines format (default: from LOG_FORMAT or True)
        verbose: Enable verbose debug logging (overrides level to DEBUG)
        quiet: Only log errors (overrides level to ERROR)
    """
    # Remove default handler
    logger.remove()

    # Determine log level with proper precedence:
    # 1. CLI flags (verbose/quiet)
    # 2. Function arguments
    # 3. LOGURU_LEVEL environment variable (loguru standard)
    # 4. Default to INFO
    if quiet:
        log_level = "ERROR"
    elif verbose:
        log_level = "DEBUG"
    elif level:
        log_level = level.upper()
    else:
        log_level = os.getenv("LOGURU_LEVEL", "INFO").upper()

    # Determine format: json or text
    # Check custom LOG_FORMAT env var if not specified
    if json_format is None:
        json_format = os.getenv("LOG_FORMAT", "json").lower() == "json"

    # Configure format
    if json_format:
        # JSON Lines format for structured logging using custom sink
        logger.add(
            json_sink,
            level=log_level,
            format="{message}",  # Use simple format, sink handles serialization
        )
    else:
        # Human-readable format
        # Check for LOGURU_FORMAT (standard loguru env var) or use defaults
        custom_format = os.getenv("LOGURU_FORMAT")

        if custom_format:
            format_str = custom_format
        elif verbose:
            # Detailed format for debugging
            format_str = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"
        else:
            # Simple format
            format_str = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}"

        logger.add(
            sys.stderr,
            level=log_level,
            format=format_str,
            backtrace=True,
            diagnose=False,
        )

    # Intercept standard library logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Intercept specific loggers
    for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access", "fastapi", "alembic"]:
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers = [InterceptHandler()]
        logging_logger.propagate = False

    logger.debug(f"Logging configured: level={log_level}, json_format={json_format}")


def get_logger():
    """Get the configured logger instance"""
    return logger
