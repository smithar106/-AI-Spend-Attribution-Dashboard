"""Analytics over normalized usage records: summaries, anomalies, trajectory."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List

from usage import UsageRecord


def _date_range(dates: List[str]) -> List[str]:
    """Return a continuous list of YYYY-MM-DD strings between min and max."""
    valid = sorted(d for d in dates if d and d != "unknown")
    if not valid:
        return []
    start = datetime.strptime(valid[0], "%Y-%m-%d")
    end = datetime.strptime(valid[-1], "%Y-%m-%d")
    out, cur = [], start
    while cur <= end:
        out.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return out


def daily_totals(records: List[UsageRecord]) -> Dict[str, float]:
    """Total spend per day across all providers, zero-filled and sorted."""
    raw: Dict[str, float] = defaultdict(float)
    for r in records:
        raw[r.date] += r.cost_usd
    return {d: round(raw.get(d, 0.0), 4) for d in _date_range(list(raw.keys()))}


def daily_by_provider(records: List[UsageRecord]) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for r in records:
        out[r.provider][r.date] += r.cost_usd
    return {p: {d: round(c, 4) for d, c in days.items()} for p, days in out.items()}


def total_by_provider(records: List[UsageRecord]) -> Dict[str, float]:
    out: Dict[str, float] = defaultdict(float)
    for r in records:
        out[r.provider] += r.cost_usd
    return {p: round(c, 2) for p, c in out.items()}


def cost_by_model(records: List[UsageRecord]) -> List[Dict]:
    agg: Dict[tuple, Dict] = defaultdict(
        lambda: {"cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0}
    )
    for r in records:
        key = (r.provider, r.model)
        agg[key]["cost_usd"] += r.cost_usd
        agg[key]["input_tokens"] += r.input_tokens
        agg[key]["output_tokens"] += r.output_tokens
    rows = [
        {
            "provider": p,
            "model": m,
            "cost_usd": round(v["cost_usd"], 2),
            "input_tokens": v["input_tokens"],
            "output_tokens": v["output_tokens"],
        }
        for (p, m), v in agg.items()
    ]
    return sorted(rows, key=lambda x: x["cost_usd"], reverse=True)


def trajectory(daily: Dict[str, float]) -> str:
    """Compare the mean spend of the second half vs the first half of the window."""
    series = [daily[d] for d in sorted(daily.keys())]
    if len(series) < 4:
        return "insufficient_data"
    mid = len(series) // 2
    first = series[:mid]
    second = series[mid:]
    first_avg = sum(first) / len(first) if first else 0.0
    second_avg = sum(second) / len(second) if second else 0.0
    if first_avg == 0:
        return "increasing" if second_avg > 0 else "flat"
    change = (second_avg - first_avg) / first_avg
    if change > 0.10:
        return "increasing"
    if change < -0.10:
        return "decreasing"
    return "flat"


def detect_anomalies(
    records: List[UsageRecord], multiplier: float = 2.0, window: int = 7
) -> List[Dict]:
    """Flag days whose total spend exceeds ``multiplier`` x the trailing
    ``window``-day rolling average (calendar days, zero-filled)."""
    daily = daily_totals(records)
    days = sorted(daily.keys())
    anomalies: List[Dict] = []
    for i, day in enumerate(days):
        prior = [daily[d] for d in days[max(0, i - window):i]]
        if len(prior) < window:
            continue  # not enough history to judge
        avg = sum(prior) / len(prior)
        threshold = avg * multiplier
        spend = daily[day]
        if avg > 0 and spend > threshold:
            anomalies.append(
                {
                    "date": day,
                    "spend_usd": round(spend, 2),
                    "rolling_avg_usd": round(avg, 2),
                    "threshold_usd": round(threshold, 2),
                    "ratio": round(spend / avg, 2),
                }
            )
    return anomalies


def spend_summary(records: List[UsageRecord]) -> Dict:
    by_provider = total_by_provider(records)
    models = cost_by_model(records)
    daily = daily_totals(records)
    total = round(sum(by_provider.values()), 2)
    return {
        "window_days": len(daily),
        "total_spend_usd": total,
        "spend_by_provider": by_provider,
        "most_expensive_model": models[0] if models else None,
        "top_models": models[:5],
        "trajectory": trajectory(daily),
        "anomaly_count": len(detect_anomalies(records)),
    }


def compare_providers(records: List[UsageRecord]) -> Dict:
    by_provider = total_by_provider(records)
    by_prov_daily = daily_by_provider(records)
    out: Dict[str, Dict] = {}
    for provider in sorted({r.provider for r in records}):
        recs = [r for r in records if r.provider == provider]
        daily = {d: c for d, c in by_prov_daily.get(provider, {}).items()}
        out[provider] = {
            "total_spend_usd": by_provider.get(provider, 0.0),
            "active_days": len(daily),
            "trajectory": trajectory(daily) if daily else "no_data",
            "top_model": (cost_by_model(recs)[0] if recs else None),
        }
    totals = {p: out[p]["total_spend_usd"] for p in out}
    leader = max(totals, key=totals.get) if any(totals.values()) else None
    out["summary"] = {
        "higher_spend_provider": leader,
        "total_combined_usd": round(sum(totals.values()), 2),
    }
    return out
