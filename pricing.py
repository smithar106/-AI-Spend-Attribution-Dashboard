"""Public list pricing for Anthropic and OpenAI models.

All rates are USD per 1,000,000 tokens and reflect public list prices.
Spend is *estimated* from token usage; it will not match an invoice exactly
(it ignores enterprise discounts, batch pricing, etc.).

Update the tables below as vendors change pricing.
"""

from __future__ import annotations

from typing import Dict, Optional

# USD per 1M tokens. Keyed by a model "family" prefix; the longest key that is
# contained in the reported model snapshot name wins (so "gpt-4o-mini" is
# matched before "gpt-4o").
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
    "openai": {
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o": {"input": 2.50, "output": 10.0},
        "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
        "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
        "gpt-4.1": {"input": 2.0, "output": 8.0},
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "gpt-4": {"input": 30.0, "output": 60.0},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
        "o3-mini": {"input": 1.10, "output": 4.40},
        "o1-mini": {"input": 1.10, "output": 4.40},
        "o1": {"input": 15.0, "output": 60.0},
    },
}

# Cache token cost multipliers relative to the input rate.
CACHE_MULTIPLIERS: Dict[str, Dict[str, float]] = {
    # Anthropic: reads are 0.1x input, writes (5m) are 1.25x input.
    "anthropic": {"cache_read": 0.10, "cache_write": 1.25},
    # OpenAI: cached input is billed at 0.5x input.
    "openai": {"cache_read": 0.50, "cache_write": 1.0},
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
