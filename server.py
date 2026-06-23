"""ai-spend-attribution: an MCP server for AI spend attribution.

Runs on built-in demo usage data (see usage.py) and estimates spend from public
pricing. It makes NO admin / workspace-management or usage-reporting API calls.
The standard ANTHROPIC_API_KEY is used only for live Claude inference elsewhere.
"""

from __future__ import annotations

import json
import os
import time
from typing import Dict, List, Optional, Tuple

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # dotenv is optional at runtime
    pass

from mcp.server.fastmcp import FastMCP

import analytics
from usage import UsageRecord, fetch_all

mcp = FastMCP("ai-spend-attribution")

_CACHE_TTL = 300  # seconds
_cache: Dict[int, Tuple[float, List[UsageRecord], Dict[str, str]]] = {}


def _default_days() -> int:
    try:
        return int(os.environ.get("LOOKBACK_DAYS", "30"))
    except ValueError:
        return 30


def _load(days: Optional[int]) -> Tuple[List[UsageRecord], Dict[str, str]]:
    days = days or _default_days()
    now = time.time()
    cached = _cache.get(days)
    if cached and (now - cached[0]) < _CACHE_TTL:
        return cached[1], cached[2]
    records, errors = fetch_all(days)
    _cache[days] = (now, records, errors)
    return records, errors


def _errors_note(errors: Dict[str, str]) -> str:
    lines = ["", "_Source: built-in demo data (no admin/usage API calls)._"]
    if errors:
        lines.append("")
        lines.append("> Warnings:")
        for provider, msg in errors.items():
            lines.append(f"> - {provider}: {msg}")
    return "\n".join(lines)


def _no_data(errors: Dict[str, str]) -> str:
    note = _errors_note(errors) or "\nNo records returned for the selected window."
    return "No usage data available." + note


@mcp.tool()
def get_spend_summary(days: int = 0) -> str:
    """Total spend by provider, most expensive model, and spend trajectory
    (increasing / decreasing / flat) over the lookback window.

    Args:
        days: Lookback window in days (defaults to LOOKBACK_DAYS or 30).
    """
    records, errors = _load(days or None)
    if not records:
        return _no_data(errors)

    s = analytics.spend_summary(records)
    lines = [
        f"# AI Spend Summary (last {s['window_days']} days)",
        "",
        f"Total estimated spend: ${s['total_spend_usd']:,.2f}",
        f"Trajectory: {s['trajectory']}",
        f"Anomalous days: {s['anomaly_count']}",
        "",
        "## Spend by provider",
    ]
    for provider, cost in sorted(s["spend_by_provider"].items(), key=lambda x: -x[1]):
        lines.append(f"- {provider}: ${cost:,.2f}")

    mem = s["most_expensive_model"]
    if mem:
        lines += [
            "",
            "## Most expensive model",
            f"- {mem['provider']} / {mem['model']}: ${mem['cost_usd']:,.2f}",
        ]
    lines += ["", "## Top models"]
    for m in s["top_models"]:
        lines.append(
            f"- {m['provider']} / {m['model']}: ${m['cost_usd']:,.2f} "
            f"({m['input_tokens']:,} in / {m['output_tokens']:,} out)"
        )
    return "\n".join(lines) + _errors_note(errors)


@mcp.tool()
def get_daily_breakdown(provider: str = "all", days: int = 0) -> str:
    """Daily spend broken down by day and model.

    Args:
        provider: "anthropic", "gemini", "deepseek", or "all" (default).
        days: Lookback window in days (defaults to LOOKBACK_DAYS or 30).
    """
    records, errors = _load(days or None)
    provider = (provider or "all").lower()
    available = sorted({r.provider for r in records})
    if provider not in (["all"] + available):
        opts = ", ".join(available + ["all"])
        return f"Unknown provider '{provider}'. Use one of: {opts}."
    if provider != "all":
        records = [r for r in records if r.provider == provider]
    if not records:
        return _no_data(errors)

    daily = analytics.daily_totals(records)
    by_model = analytics.cost_by_model(records)

    lines = [f"# Daily Breakdown ({provider}, {len(daily)} days)", "", "## Spend per day"]
    for day in sorted(daily.keys()):
        lines.append(f"- {day}: ${daily[day]:,.2f}")
    lines += ["", "## Spend per model"]
    for m in by_model:
        lines.append(
            f"- {m['provider']} / {m['model']}: ${m['cost_usd']:,.2f} "
            f"({m['input_tokens']:,} in / {m['output_tokens']:,} out)"
        )
    return "\n".join(lines) + _errors_note(errors)


@mcp.tool()
def get_anomalies(multiplier: float = 2.0, window: int = 7, days: int = 0) -> str:
    """Flag days whose total spend exceeds `multiplier` x the trailing
    `window`-day rolling average.

    Args:
        multiplier: Spike threshold multiplier (default 2.0).
        window: Rolling-average window in days (default 7).
        days: Lookback window in days (defaults to LOOKBACK_DAYS or 30).
    """
    records, errors = _load(days or None)
    if not records:
        return _no_data(errors)

    anomalies = analytics.detect_anomalies(records, multiplier=multiplier, window=window)
    if not anomalies:
        return (
            f"No anomalies detected (threshold: {multiplier}x the {window}-day "
            f"rolling average)." + _errors_note(errors)
        )

    lines = [
        f"# Spend Anomalies ({multiplier}x over {window}-day rolling avg)",
        "",
    ]
    for a in anomalies:
        lines.append(
            f"- {a['date']}: ${a['spend_usd']:,.2f} "
            f"(rolling avg ${a['rolling_avg_usd']:,.2f}, {a['ratio']}x)"
        )
    return "\n".join(lines) + _errors_note(errors)


@mcp.tool()
def compare_providers(days: int = 0) -> str:
    """Compare providers (Anthropic, Gemini, DeepSeek): total spend, trajectory,
    and top model.

    Args:
        days: Lookback window in days (defaults to LOOKBACK_DAYS or 30).
    """
    records, errors = _load(days or None)
    if not records:
        return _no_data(errors)

    cmp = analytics.compare_providers(records)
    summary = cmp.pop("summary")
    lines = ["# Provider Comparison", ""]
    for provider in sorted(cmp):
        info = cmp[provider]
        top = info.get("top_model")
        top_str = f"{top['model']} (${top['cost_usd']:,.2f})" if top else "n/a"
        lines += [
            f"## {provider}",
            f"- Total spend: ${info.get('total_spend_usd', 0.0):,.2f}",
            f"- Active days: {info.get('active_days', 0)}",
            f"- Trajectory: {info.get('trajectory', 'no_data')}",
            f"- Top model: {top_str}",
            "",
        ]
    lines += [
        "## Summary",
        f"- Combined spend: ${summary['total_combined_usd']:,.2f}",
        f"- Higher spend: {summary['higher_spend_provider'] or 'n/a'}",
    ]
    return "\n".join(lines) + _errors_note(errors)


@mcp.tool()
def get_raw_usage(days: int = 0) -> str:
    """Return the normalized usage records as JSON (debugging / export)."""
    records, errors = _load(days or None)
    payload = {
        "source": "demo",
        "records": [r.as_dict() for r in records],
        "errors": errors,
        "count": len(records),
    }
    return json.dumps(payload, indent=2)


if __name__ == "__main__":
    mcp.run()
