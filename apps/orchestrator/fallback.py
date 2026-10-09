from __future__ import annotations

from pathlib import Path
from typing import Any

from apps.llm import budget_usd_per_run, chat_json, cost_usd, load_config


def ollama_fallback_model(root: Path | None = None) -> str:
    """Local model id used only after the cloud chain is exhausted."""
    config = load_config(root)
    value = str(config.get("LLM_OLLAMA_MODEL", "") or "").strip()
    return value or "qwen3.5:2b"


def cloud_first_chat(
    root: Path | None,
    system: str,
    user_payload: dict[str, Any],
    *,
    num_predict: int,
    timeout: int,
) -> tuple[dict[str, Any] | None, dict[str, Any], dict[str, Any]]:
    """Try Groq/cloud chain first, fall back to Ollama once.

    Returns (body, usage, ledger_entry) where ledger_entry records which
    tier answered (cloud|ollama_fallback|none) plus cost. Never raises on
    provider failure; callers degrade to outline like _ollama_call does.
    Respects LLM_BUDGET_USD_PER_RUN across both tiers combined.
    """
    config = load_config(root)
    budget = budget_usd_per_run(config)
    spent = 0.0

    cloud_body, cloud_usage = chat_json(
        config, system, user_payload, num_predict=num_predict, timeout=timeout
    )
    cloud_cost, _ = cost_usd(config, cloud_usage)
    spent = round(spent + cloud_cost, 6)
    if cloud_body is not None:
        return cloud_body, cloud_usage, {
            "tier": "cloud",
            "model": cloud_usage.get("model", ""),
            "cost_usd": cloud_cost,
            "spent_usd": spent,
        }

    if budget > 0 and spent >= budget:
        return None, {"prompt_tokens": 0, "completion_tokens": 0, "model": ""}, {
            "tier": "none",
            "model": "",
            "cost_usd": 0.0,
            "spent_usd": spent,
            "reason": "budget_exhausted_before_fallback",
        }

    ollama_config = dict(config)
    ollama_config["LLM_PROVIDER"] = "ollama"
    ollama_config["LLM_MODEL"] = ollama_fallback_model(root)
    ollama_config["LLM_MODELS"] = ollama_config["LLM_MODEL"]
    local_body, local_usage = chat_json(
        ollama_config, system, user_payload, num_predict=num_predict, timeout=timeout
    )
    local_cost, _ = cost_usd(ollama_config, local_usage)
    spent = round(spent + local_cost, 6)
    if local_body is not None:
        return local_body, local_usage, {
            "tier": "ollama_fallback",
            "model": local_usage.get("model", ""),
            "cost_usd": local_cost,
            "spent_usd": spent,
        }
    return None, {"prompt_tokens": 0, "completion_tokens": 0, "model": ""}, {
        "tier": "none",
        "model": "",
        "cost_usd": 0.0,
        "spent_usd": spent,
        "reason": "cloud_and_ollama_failed",
    }
