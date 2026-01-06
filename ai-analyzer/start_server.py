#!/usr/bin/env python3
"""
Startup script for AI Analyzer API server.
Configures logging before running migrations and starting uvicorn.
"""
import os
import sys
from pathlib import Path

# Disable alembic's own logging config (we'll intercept it)
os.environ["SKIP_ALEMBIC_LOGGING"] = "1"

# Configure logging FIRST, before any other imports
from analyzer.logging_config import configure_logging
configure_logging()

from loguru import logger
from alembic import command
from alembic.config import Config
import uvicorn


def run_migrations():
    """Run database migrations using Alembic"""
    logger.info("Running database migrations")

    alembic_ini = Path(__file__).parent / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini))

    try:
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations completed successfully")
    except Exception as e:
        logger.error(f"Database migration failed: {e}")
        sys.exit(1)


def main():
    """Main entry point"""
    # Run migrations
    run_migrations()

    # Start uvicorn server
    logger.info("Starting AI Analyzer API server...")

    # Get configuration from environment
    host = os.getenv("UVICORN_HOST", "0.0.0.0")
    port = int(os.getenv("UVICORN_PORT", "8000"))
    workers = int(os.getenv("UVICORN_WORKERS", "4"))

    # Configure uvicorn to use minimal logging (we intercept it anyway)
    uvicorn.run(
        "analyzer.api.main:app",
        host=host,
        port=port,
        workers=workers,
        log_config=None,  # Disable uvicorn's log config (we handle it)
        access_log=True,
    )


if __name__ == "__main__":
    main()
