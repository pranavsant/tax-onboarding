"""FastAPI application factory.

The composition root (root-level `main.py`) builds a `UseCaseContainer`
with concrete infrastructure implementations and passes it here. This
keeps the interfaces layer fully ignorant of infrastructure details —
it only ever depends on `application` types.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.interfaces.api.container import UseCaseContainer
from src.interfaces.api.controllers import client_controller, tax_assistant_controller


def create_app(container: UseCaseContainer, cors_origins: Optional[List[str]] = None) -> FastAPI:
    app = FastAPI(
        title="Tax Onboarding API",
        description="API for onboarding clients into a tax preparation workflow.",
        version="1.0.0",
    )

    app.state.container = container

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(client_controller.router, prefix="/api")
    app.include_router(tax_assistant_controller.router, prefix="/api")

    @app.get("/health", tags=["health"])
    def health_check() -> dict:
        return {"status": "ok"}

    return app
