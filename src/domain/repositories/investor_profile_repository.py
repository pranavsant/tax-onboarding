"""Repository interface for InvestorProfile persistence.

This is a port (abstraction) — it expresses WHAT operations the
application needs, never HOW they are implemented.  The concrete
SQLite implementation lives in the infrastructure layer.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from src.domain.entities.investor_profile import InvestorProfile


class InvestorProfileRepository(ABC):
    """Abstraction over persistence of :class:`InvestorProfile` entities."""

    @abstractmethod
    def save(self, profile: InvestorProfile) -> InvestorProfile:
        """Persist a new investor profile and return the stored entity."""

    @abstractmethod
    def get_by_id(self, profile_id: str) -> Optional[InvestorProfile]:
        """Fetch a profile by its surrogate key, or ``None`` if not found."""

    @abstractmethod
    def list_all(self) -> List[InvestorProfile]:
        """Return all stored investor profiles, most-recently-created first."""
