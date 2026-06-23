"""Public list pricing for Anthropic, Gemini, and DeepSeek models.

All rates are USD per 1,000,000 tokens and reflect public list prices.
Spend is *estimated* from token usage; it will not match an invoice exactly
(it ignores enterprise discounts, batch pricing, etc.).

Update the tables below as vendors change pricing.
"""

from __future__ import annotations

from typing import Dict, Optional

# USD per 1M tokens. Keyed by a model "family" prefix; the longest key that is
# contained in the reported model snapshot name wins (so "gemini-1.5-flash" is
# matched before "gemini-1.5").
PRICING: Dict[str, Dict[str, Dict[str, float]]] = {
    "anthropic": {
        "claude-opus-4": {"input": 15.0, "output": 75.0},
        "claude-sonnet-4": {"input": 3.0, "output": 15.0},
        "claude-3-7-sonnet": {"input": 3.0, "output": 15.0},
        "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
        "claude-3-5-haiku": {"input": 0.80, "output": 4.0},
        "claude-3-opus": {"input": 15.0, "output": 75.0},
        "claude-3-sonnet": {"input": 3.0, "output": 15.0},
        "claude-3-haiku": {"input": 0.25, "output": 1.25},
    },
    "gemini": {
        "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
        "gemini-1.5-pro": {"input": 1.25, "output": 5.0},
        "gemini-1.5-flash-8b": {"input": 0.0375, "output": 0.15},
        "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    },
    "deepseek": {
        "deepseek-reasoner": {"input": 0.55, "output": 2.19},
        "deepseek-chat": {"input": 0.27, "output": 1.10},
        "deepseek-coder": {"input": 0.14, "output": 0.28},
    },
}

# Cache token cost multipliers relative to the input rate.
CACHE_MULTIPLIERS: Dict[str, Dict[str, float]] = {
    # Anthropic: reads are 0.1x input, writes (5m) are 1.25x input.
    "anthropic": {"cache_read": 0.10, "cache_write": 1.25},
    # Gemini: cached input is billed at ~0.25x input.
    "gemini": {"cache_read": 0.25, "cache_write": 1.0},
    # DeepSeek: cache hits are billed at ~0.25x input.
    "deepseek": {"cache_read": 0.25, "cache_write": 1.0},
}

_FALLBACK = {"input": 1.0, "output": 3.0}


def _match_rates(provider: str, model: str) -> Dict[str, float]:
    table = PRICING.get(provider, {})
    model_l = (model or "").lower()
    best_key: Optional[str] = None
    for key in table:
        if key in model_l and (best_key is None or len(key) > len(best_key)):
            best_key = key
    if best_key is None:
        return _FALLBACK
    return table[best_key]


def estimate_cost(
    provider: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """Estimate USD spend for a single (provider, model, day) usage record."""
    rates = _match_rates(provider, model)
    mult = CACHE_MULTIPLIERS.get(provider, {"cache_read": 1.0, "cache_write": 1.0})

    in_rate = rates["input"]
    out_rate = rates["output"]

    cost = (
        input_tokens * in_rate
        + output_tokens * out_rate
        + cache_read_tokens * in_rate * mult["cache_read"]
        + cache_write_tokens * in_rate * mult["cache_write"]
    ) / 1_000_000.0
    return round(cost, 6)


def is_known_model(provider: str, model: str) -> bool:
    return _match_rates(provider, model) is not _FALLBACK
