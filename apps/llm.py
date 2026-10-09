from __future__ import annotations

"""Generic local/cloud model transport.

The engine stays provider-agnostic: the provider is configuration (spec
section 2), never architecture. Ollama remains the default; any
OpenAI-compatible endpoint works by changing .env only. Secrets live in the
environment, never in logs, results, or Git.
"""

import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_BUDGET_USD_PER_RUN = 0.25

# Indicative prices in USD per 1M tokens (input, output). Providers change
# prices; override exact numbers with LLM_PRICE_PER_M_IN/OUT when needed.
_INDICATIVE_PRICES = {
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-4o-mini": (0.15, 0.60),
    "deepseek-chat": (0.27, 1.10),
}


class LLMError(RuntimeError):
    """A model call failed; never carries credentials."""


def load_config(root: Path | None = None, env: dict[str, str] | None = None) -> dict[str, str]:
    """Merge process env with the project .env file (.env never wins)."""
    values = dict(env if env is not None else os.environ)
    if root is not None:
        env_file = root / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8-sig").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values.setdefault(key.strip(), value.strip().strip("\"'"))
    values.setdefault("LLM_PROVIDER", "ollama")
    values.setdefault("LLM_MODEL", "qwen3.5:2b")
    values.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
    return values


def _extract_json(text: str) -> dict[str, Any] | None:
    """Parse a model reply, tolerating ```json fences some models add."""
    try:
        body = json.loads(text)
        return body if isinstance(body, dict) else None
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        while lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        try:
            body = json.loads("\n".join(lines))
            return body if isinstance(body, dict) else None
        except (json.JSONDecodeError, TypeError, ValueError):
            return None
    return None


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(4 * 1024 * 1024)
    except HTTPError as error:
        raise LLMError(f"Model endpoint returned HTTP {error.code}.") from error
    except (URLError, TimeoutError, OSError) as error:
        raise LLMError(f"Model endpoint unreachable: {type(error).__name__}.") from error
    try:
        result = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise LLMError("Model endpoint returned invalid JSON.") from error
    if not isinstance(result, dict):
        raise LLMError("Model endpoint returned an unexpected response.")
    return result


def _ollama_chat(config: dict[str, str], system: str, user_payload: dict[str, Any],
                 num_predict: int, timeout: int) -> tuple[dict[str, Any], dict[str, int]]:
    model = config.get("LLM_MODEL", "").strip() or "qwen3.5:2b"
    base_url = config.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    result = _post_json(
        f"{base_url}/api/chat",
        {
            "model": model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            "options": {"temperature": 0.35, "num_ctx": 4096,
                        "num_predict": num_predict, "low_vram": True},
            "keep_alive": 0,
        },
        {"Content-Type": "application/json"},
        timeout,
    )
    try:
        text = result["message"]["content"]
    except (KeyError, TypeError) as error:
        raise LLMError("Ollama reply had no message content.") from error
    body = _extract_json(str(text))
    if body is None:
        raise LLMError("Ollama reply was not a JSON object.")
    usage = {
        "prompt_tokens": int(result.get("prompt_eval_count") or 0),
        "completion_tokens": int(result.get("eval_count") or 0),
    }
    return body, usage


def _openai_compatible_chat(config: dict[str, str], system: str, user_payload: dict[str, Any],
                            num_predict: int, timeout: int) -> tuple[dict[str, Any], dict[str, int]]:
    model = config.get("LLM_MODEL", "").strip()
    base_url = config.get("LLM_BASE_URL", "").strip().rstrip("/")
    api_key = config.get("LLM_API_KEY", "").strip()
    if not model or not base_url or not api_key:
        raise LLMError("OpenAI-compatible provider needs LLM_MODEL, LLM_BASE_URL, and LLM_API_KEY.")
    result = _post_json(
        f"{base_url}/chat/completions",
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            "temperature": 0.35,
            "max_tokens": num_predict,
            "response_format": {"type": "json_object"},
        },
        {"Content-Type": "application/json", "Authorization": "Bearer " + api_key},
        timeout,
    )
    try:
        text = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise LLMError("Provider reply had no message content.") from error
    body = _extract_json(str(text))
    if body is None:
        raise LLMError("Provider reply was not a JSON object.")
    usage_raw = result.get("usage", {})
    if not isinstance(usage_raw, dict):
        usage_raw = {}
    try:
        usage = {
            "prompt_tokens": int(usage_raw.get("prompt_tokens") or 0),
            "completion_tokens": int(usage_raw.get("completion_tokens") or 0),
        }
    except (TypeError, ValueError):
        usage = {"prompt_tokens": 0, "completion_tokens": 0}
    return body, usage


def chat_json(config: dict[str, str], system: str, user_payload: dict[str, Any],
              *, num_predict: int, timeout: int) -> tuple[dict[str, Any] | None, dict[str, int]]:
    """One bounded model call. Returns (body, usage); None body means failure."""
    provider = config.get("LLM_PROVIDER", "ollama").strip().lower()
    try:
        if provider == "openai_compatible":
            return _openai_compatible_chat(config, system, user_payload, num_predict, timeout)
        if provider == "ollama":
            return _ollama_chat(config, system, user_payload, num_predict, timeout)
        return None, {"prompt_tokens": 0, "completion_tokens": 0}
    except LLMError:
        return None, {"prompt_tokens": 0, "completion_tokens": 0}


def price_per_million(config: dict[str, str]) -> tuple[float, float, bool]:
    """(input_price, output_price, priced). Env overrides beat the table."""
    raw_in = config.get("LLM_PRICE_PER_M_IN")
    raw_out = config.get("LLM_PRICE_PER_M_OUT")
    if raw_in is not None or raw_out is not None:
        try:
            return float(raw_in or 0), float(raw_out or 0), True
        except (TypeError, ValueError):
            pass
    model = config.get("LLM_MODEL", "").strip().lower()
    for name, prices in _INDICATIVE_PRICES.items():
        if name in model:
            return prices[0], prices[1], True
    if config.get("LLM_PROVIDER", "ollama").strip().lower() == "ollama":
        return 0.0, 0.0, True
    return 0.0, 0.0, False


def cost_usd(config: dict[str, str], usage: dict[str, int]) -> tuple[float, bool]:
    price_in, price_out, priced = price_per_million(config)
    cost = (usage.get("prompt_tokens", 0) * price_in
            + usage.get("completion_tokens", 0) * price_out) / 1_000_000
    return round(cost, 6), priced


def budget_usd_per_run(config: dict[str, str]) -> float:
    try:
        return max(0.0, float(config.get("LLM_BUDGET_USD_PER_RUN", DEFAULT_BUDGET_USD_PER_RUN)))
    except (TypeError, ValueError):
        return DEFAULT_BUDGET_USD_PER_RUN
