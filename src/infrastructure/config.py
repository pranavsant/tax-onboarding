"""Centralized environment configuration for infrastructure adapters.

Per architecture rules, environment variables are only ever read here
— never in domain or application code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class Settings:
    database_path: str
    anthropic_api_key: str
    anthropic_model: str
    cors_origins: List[str] = field(default_factory=list)


def get_settings() -> Settings:
    return Settings(
        database_path=os.getenv("DATABASE_PATH", "tax_onboarding.db"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
        cors_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    )
