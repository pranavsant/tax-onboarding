"""CLI entry point for onboarding a client from the terminal.

Thin adapter: parses args, builds a DTO, calls the use case, prints
the result. No business logic lives here — see the root-level
`cli.py` composition root for how this is wired to a concrete
repository implementation.
"""
from __future__ import annotations

import argparse
from typing import List, Optional

from src.application.dto.client_dto import CreateClientDTO
from src.application.exceptions import InvalidClientRequestError
from src.application.use_cases.onboard_client import OnboardClientUseCase


def run(use_case: OnboardClientUseCase, argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Onboard a new tax client")
    parser.add_argument("--name", required=True, help="Client full name")
    parser.add_argument("--email", required=True, help="Client email")
    parser.add_argument(
        "--tax-id", required=True, help="SSN (XXX-XX-XXXX) or EIN (XX-XXXXXXX)"
    )
    args = parser.parse_args(argv)

    try:
        result = use_case.execute(
            CreateClientDTO(full_name=args.name, email=args.email, tax_id=args.tax_id)
        )
    except InvalidClientRequestError as exc:
        print(f"Error: {exc}")
        return 1

    print(f"Client onboarded: {result.client_id} ({result.status})")
    return 0
