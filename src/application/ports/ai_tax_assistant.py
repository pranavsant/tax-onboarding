"""Port (abstraction) for an AI assistant capable of producing tax
onboarding summaries.

This interface is owned by the application layer. The concrete
implementation (e.g. the Claude/Anthropic API) lives in the
infrastructure layer and is injected via the use case constructor.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class AITaxAssistantPort(ABC):
    @abstractmethod
    def generate_summary(self, prompt_context: str) -> str:
        """Given a textual context describing a client's tax situation,
        return a plain-language onboarding summary.
        """
