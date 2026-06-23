"""Demo usage data for the AI Spend Attribution dashboard.

This app does NOT call any admin / workspace-management APIs. Historical
org-wide usage reporting requires an admin key, which is intentionally out of
scope. Instead we generate a realistic, deterministic 30-day demo dataset so
every tool and the Spend Attribution page work out of the box.

The standard ``ANTHROPIC_API_KEY`` (a regular console.anthropic.com key) is only
ever used for live Claude inference elsewhere in the app -- never for usage
reporting.

The public shape (``UsageRecord`` + ``fetch_all``) is unchanged, so analytics
and the MCP tools are agnostic to where the data comes from.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

import pricing

DEMO_SEED = 42
DATA_SOURCE = "demo"

# Representative model mix per provider with rough daily token "scale" factors.
# (input_scale, output_scale) are base tokens/day before trend + noise.
_DEMO_MODELS = {
    "anthropic": [
        ("claude-3-5-sonnet-20241022", 9_000_000, 1_300_000),
        ("claude-3-5-haiku-20241022", 14_000_000, 2_000_000),
        ("claude-3-opus-20240229", 1_200_000, 220_000),
    ],
    "gemini": [
        ("gemini-2.0-flash-001", 20_000_000, 3_000_000),
        ("gemini-1.5-pro-002", 4_000_000, 600_000),
        ("gemini-1.5-flash-002", 18_000_000, 2_500_000),
    ],
    "deepseek": [
        ("deepseek-chat", 22_000_000, 3_200_000),
        ("deepseek-reasoner", 6_000_000, 2_400_000),
        ("deepseek-coder", 12_000_000, 1_500_000),
    ],
}


@dataclass
class UsageRecord:
    provider: str
    date: str  # YYYY-MM-DD (UTC)
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    cost_usd: float

    def as_dict(self) -> Dict:
        return asdict(self)


def _window(days: int) -> List[str]:
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)
    return [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]


def generate_demo(days: int = 30) -> List[UsageRecord]:
    """Deterministic, realistic demo usage with a mild upward trend, weekend
    dips, and a single injected spend spike (so anomaly detection has signal)."""
    rng = random.Random(DEMO_SEED)
    dates = _window(days)
    anomaly_index = max(days - 9, 0)  # one obvious spike late in the window

    records: List[UsageRecord] = []
    for i, date in enumerate(dates):
        weekday = datetime.strptime(date, "%Y-%m-%d").weekday()
        is_spike_day = i == anomaly_index
        weekend = 1.0 if is_spike_day else (0.55 if weekday >= 5 else 1.0)
        trend = 1.0 + 0.012 * i  # ~1.2% growth per day

        for provider, models in _DEMO_MODELS.items():
            spike = 3.0 if is_spike_day else 1.0
            for model, in_scale, out_scale in models:
                noise = rng.uniform(0.78, 1.22)
                factor = trend * weekend * noise * spike
                total_input = int(in_scale * factor)
                output_tokens = int(out_scale * factor)
                # cache_read is a portion of total input; the remainder is
                # billed as uncached input (pricing treats them as disjoint).
                cache_read = int(total_input * rng.uniform(0.0, 0.25))
                input_tokens = total_input - cache_read
                cost = pricing.estimate_cost(
                    provider, model, input_tokens, output_tokens, cache_read, 0
                )
                records.append(
                    UsageRecord(
                        provider=provider,
                        date=date,
                        model=model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cache_read_tokens=cache_read,
                        cache_write_tokens=0,
                        cost_usd=cost,
                    )
                )
    return records


def fetch_all(days: int = 30) -> Tuple[List[UsageRecord], Dict[str, str]]:
    """Return (records, errors). Demo data never errors, so errors is empty."""
    return generate_demo(days), {}
