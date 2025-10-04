"""FastAPI application entry point"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from ..config.settings import Settings
from .routes import logs, analyses


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("Starting AI Analyzer API")
    yield
    logger.info("Shutting down AI Analyzer API")


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""

    # Initialize settings
    settings = Settings()

    # Create FastAPI app
    app = FastAPI(
        title="Timberline AI Analyzer API",
        description="AI-powered log analysis API for Kubernetes environments",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure based on environment
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store settings in app state
    app.state.settings = settings

    # Include routers
    app.include_router(logs.router, prefix="/api/v1", tags=["logs"])
    app.include_router(analyses.router, prefix="/api/v1", tags=["analyses"])

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "service": "ai-analyzer-api"}

    return app


app = create_app()
