"""
FastAPI application entry point.

This module owns application setup only: app metadata, middleware, and router
registration. HTTP endpoints live under backend/api/routes.
"""

import io
import sys

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from core.config import config


if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="DuckDuckGo Search Agent", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)
