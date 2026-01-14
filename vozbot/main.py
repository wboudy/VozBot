"""VozBot FastAPI application entry point.

Provides the main FastAPI application with configured routes,
middleware, and static file serving for audio prompts.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from vozbot.telephony.webhooks.twilio_webhooks import router as twilio_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Handles startup and shutdown events for the FastAPI application.
    """
    # Startup
    logger.info("VozBot starting up...")
    logger.info(
        "Environment: %s",
        os.getenv("APP_ENV", "development"),
    )

    yield

    # Shutdown
    logger.info("VozBot shutting down...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="VozBot",
        description="Bilingual AI Receptionist for a Small Insurance Office",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Include routers
    app.include_router(twilio_router)

    # Mount static files for audio prompts
    static_dir = Path(__file__).parent.parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        logger.info("Static files mounted from %s", static_dir)

    @app.get("/health")
    async def health_check() -> dict:
        """Health check endpoint."""
        return {"status": "healthy", "service": "vozbot"}

    @app.get("/")
    async def root() -> dict:
        """Root endpoint with API information."""
        return {
            "service": "VozBot",
            "version": "0.1.0",
            "description": "Bilingual AI Receptionist",
            "endpoints": {
                "health": "/health",
                "webhooks": "/webhooks/twilio/voice",
            },
        }

    return app


# Create the application instance
app = create_app()
