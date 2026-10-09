"""Orchestrator helpers (additive; never edits llm.py or workflow cores).

Agreed direction: Groq cloud chain first for script quality, Ollama local
only after cloud quota/budget is exhausted. llm.chat_json rotates within a
single provider, so cross-provider fallback lives here as a wrapper.
"""

from .fallback import cloud_first_chat

__all__ = ["cloud_first_chat"]
