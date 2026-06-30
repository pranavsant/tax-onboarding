"""Data Transfer Objects for tax form determination.

DTOs are the only objects that cross the application/interfaces
boundary — domain types never leak outward.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DetermineFormDTO:
    """Input DTO carrying the raw investor_type string from the caller."""

    investor_type: str


@dataclass
class FormDeterminationResultDTO:
    """Output DTO returned by :class:`DetermineRequiredFormUseCase`."""

    investor_type: str
    required_form: str
