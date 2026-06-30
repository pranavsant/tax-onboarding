"""Claude (Anthropic) implementation of the AITaxAssistantPort.

Wraps the raw Anthropic SDK call behind the application-defined port
interface, so use cases never know which LLM vendor is being used.
"""
from __future__ import annotations

from typing import Optional

from anthropic import Anthropic

from src.application.ports.ai_tax_assistant import AITaxAssistantPort
from src.infrastructure.config import get_settings

_SYSTEM_PROMPT = (
    "You are a helpful tax onboarding assistant. Given structured context "
    "about a client's onboarding progress, write a concise, plain-language "
    "summary (3-5 sentences) of where they stand and what is needed next. "
    "Never give specific tax or legal advice; recommend consulting a "
    "licensed tax professional for advice."
)


class ClaudeTaxAssistant(AITaxAssistantPort):
    """Adapter wrapping the Anthropic SDK behind AITaxAssistantPort."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        settings = get_settings()
        self._client = Anthropic(api_key=api_key or settings.anthropic_api_key)
        self._model = model or settings.anthropic_model

    def generate_summary(self, prompt_context: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=500,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt_context}],
        )
        return "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )
