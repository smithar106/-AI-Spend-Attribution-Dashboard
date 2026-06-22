"""Usage-API clients for Anthropic and OpenAI.

Both vendors expose org-level *admin* endpoints that report token usage in
daily buckets. We pull raw token counts and convert them into a normalized
``UsageRecord`` list; spend is estimated locally from ``pricing.py`` so the
numbers are consistent across providers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import requests

import pricing

ANTHROPIC_USAGE_URL = "https://api.anthropic.com/v1/organizations/usage_report/messages"
OPENAI_USAGE_URL = "https://api.openai.com/v1/organizations/usage/completions"
ANTHROPIC_VERSION = "2023-06-01"
REQUEST_TIMEOUT = 60


class UsageError(Exception):
    """Raised when a provider usage request fails."""


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


def _window(days: int) -> tuple:
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)
    return start, end


def _as_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _anthropic_cache_write(creation) -> int:
    """``cache_creation`` may be an int or a dict of ephemeral buckets."""
    if isinstance(creation, dict):
        return sum(_as_int(v) for v in creation.values())
    return _as_int(creation)


# --------------------------------------------------------------------------- #
# Anthropic
# --------------------------------------------------------------------------- #
def fetch_anthropic(days: int = 30) -> List[UsageRecord]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise UsageError("ANTHROPIC_API_KEY is not set")

    start, end = _window(days)
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    params = {
        "starting_at": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ending_at": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bucket_width": "1d",
        "group_by[]": "model",
        "limit": days + 1,
    }

    records: List[UsageRecord] = []
    page: Optional[str] = None
    while True:
        q = dict(params)
        if page:
            q["page"] = page
        resp = requests.get(ANTHROPIC_USAGE_URL, headers=headers, params=q, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 401:
            raise UsageError(
                "Anthropic returned 401. The usage report requires an ADMIN key "
                "(sk-ant-admin...), not a standard API key."
            )
        if resp.status_code >= 400:
            raise UsageError(f"Anthropic usage request failed ({resp.status_code}): {resp.text[:300]}")

        body = resp.json()
        for bucket in body.get("data", []):
            day = (bucket.get("starting_at") or "")[:10]
            for item in bucket.get("results", []):
                model = item.get("model") or "unknown"
                input_tokens = _as_int(item.get("uncached_input_tokens"))
                output_tokens = _as_int(item.get("output_tokens"))
                cache_read = _as_int(item.get("cache_read_input_tokens"))
                cache_write = _anthropic_cache_write(item.get("cache_creation"))
                cost = pricing.estimate_cost(
                    "anthropic", model, input_tokens, output_tokens, cache_read, cache_write
                )
                records.append(
                    UsageRecord(
                        provider="anthropic",
                        date=day,
                        model=model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cache_read_tokens=cache_read,
                        cache_write_tokens=cache_write,
                        cost_usd=cost,
                    )
                )
        if body.get("has_more") and body.get("next_page"):
            page = body["next_page"]
        else:
            break
    return records


# --------------------------------------------------------------------------- #
# OpenAI
# --------------------------------------------------------------------------- #
def fetch_openai(days: int = 30) -> List[UsageRecord]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise UsageError("OPENAI_API_KEY is not set")

    start, end = _window(days)
    headers = {"Authorization": f"Bearer {api_key}"}
    org_id = os.environ.get("OPENAI_ORG_ID")
    if org_id:
        headers["OpenAI-Organization"] = org_id

    params = {
        "start_time": int(start.timestamp()),
        "end_time": int(end.timestamp()),
        "bucket_width": "1d",
        "group_by[]": "model",
        "limit": days + 1,
    }

    records: List[UsageRecord] = []
    page: Optional[str] = None
    while True:
        q = dict(params)
        if page:
            q["page"] = page
        resp = requests.get(OPENAI_USAGE_URL, headers=headers, params=q, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 401:
            raise UsageError(
                "OpenAI returned 401. The usage endpoint requires an ADMIN key "
                "(sk-admin...) with api.usage.read scope."
            )
        if resp.status_code >= 400:
            raise UsageError(f"OpenAI usage request failed ({resp.status_code}): {resp.text[:300]}")

        body = resp.json()
        for bucket in body.get("data", []):
            ts = bucket.get("start_time")
            day = (
                datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                if ts
                else "unknown"
            )
            for item in bucket.get("results", []) or bucket.get("result", []):
                model = item.get("model") or "unknown"
                input_tokens = _as_int(item.get("input_tokens"))
                output_tokens = _as_int(item.get("output_tokens"))
                cache_read = _as_int(item.get("input_cached_tokens"))
                input_uncached = max(input_tokens - cache_read, 0)
                cost = pricing.estimate_cost(
                    "openai", model, input_uncached, output_tokens, cache_read, 0
                )
                records.append(
                    UsageRecord(
                        provider="openai",
                        date=day,
                        model=model,
                        input_tokens=input_uncached,
                        output_tokens=output_tokens,
                        cache_read_tokens=cache_read,
                        cache_write_tokens=0,
                        cost_usd=cost,
                    )
                )
        if body.get("has_more") and body.get("next_page"):
            page = body["next_page"]
        else:
            break
    return records


def fetch_all(days: int = 30) -> tuple:
    """Fetch both providers. Returns (records, errors_by_provider)."""
    records: List[UsageRecord] = []
    errors: Dict[str, str] = {}
    for name, fn in (("anthropic", fetch_anthropic), ("openai", fetch_openai)):
        try:
            records.extend(fn(days))
        except UsageError as exc:
            errors[name] = str(exc)
        except requests.RequestException as exc:
            errors[name] = f"network error: {exc}"
    return records, errors
