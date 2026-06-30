"""Composition root for the onboarding CLI.

Like `main.py`, this file wires a concrete infrastructure
implementation into an interfaces-layer entry point, keeping the
layers themselves decoupled from one another.

Run with:
    python cli.py --name "Jane Doe" --email jane@example.com --tax-id 123-45-6789
"""
from __future__ import annotations

import sys

from src.application.use_cases.onboard_client import OnboardClientUseCase
from src.infrastructure.db.database import init_db
from src.infrastructure.db.sqlite_client_repository import SqliteClientRepository
from src.interfaces.cli.onboard_client_cli import run

if __name__ == "__main__":
    init_db()
    repository = SqliteClientRepository()
    use_case = OnboardClientUseCase(repository)
    sys.exit(run(use_case, sys.argv[1:]))
