# ai-spend-attribution

An [MCP](https://modelcontextprotocol.io) server that powers an **AI Spend
Attribution** dashboard. It analyzes daily token usage across **Anthropic** and
**OpenAI** models, estimates spend from public list pricing, detects spend
spikes, and exposes everything as MCP tools your assistant can call.

> **Data source:** this app runs on a built-in, realistic **demo dataset**
> (30 days, multiple models per provider). It makes **no admin / workspace-
> management or usage-reporting API calls**. The standard `ANTHROPIC_API_KEY`
> (a regular key from console.anthropic.com) is used only for live Claude
> inference elsewhere in the app — never for usage reporting.

## Features

- Realistic **30-day demo usage** across multiple Anthropic and OpenAI models
  (configurable window).
- Breaks usage down by **model**, **day**, and **cumulative spend**
  (computed from public pricing in `pricing.py`).
- **Anomaly detection** — flags any day where total spend exceeds **2x the
  7-day rolling average** (both configurable). The demo data includes one
  injected spike so this is visible out of the box.
- **Spend summary** — total spend by provider, the most expensive model, and
  the spend trajectory (increasing / decreasing / flat).

## MCP tools

| Tool | Description |
| --- | --- |
| `get_spend_summary` | Total spend by provider, most expensive model, trajectory, anomaly count. |
| `get_daily_breakdown` | Spend per day and per model (filter by `provider`). |
| `get_anomalies` | Days exceeding `multiplier`x the `window`-day rolling average. |
| `compare_providers` | Anthropic vs OpenAI: totals, trajectory, top model. |
| `get_raw_usage` | Normalized usage records as JSON (export / debugging). |

## Requirements

- **Python 3.10+** (required by the `mcp` SDK).
- *(Optional)* a standard **`ANTHROPIC_API_KEY`** — a regular key from
  <https://console.anthropic.com>. It is **not** needed to run the dashboard on
  demo data; it's only used if/when the app makes live Claude calls. **No admin
  key is required.**

## Setup

```bash
git clone https://github.com/smithar106/-AI-Spend-Attribution-Dashboard.git
cd -AI-Spend-Attribution-Dashboard

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env   # optional: add your regular ANTHROPIC_API_KEY
```

### Environment variables

| Variable | Required | Notes |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | optional | Regular key (`sk-ant-...`) for live Claude calls. Not used for usage data. |
| `LOOKBACK_DAYS` | optional | Demo lookback window (defaults to 30). |

## Running

Run directly over stdio (how MCP clients launch it):

```bash
python server.py
```

### Register with an MCP client (e.g. Claude Desktop)

Add this to your client's MCP config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "ai-spend-attribution": {
      "command": "python",
      "args": ["/absolute/path/to/ai-spend-attribution/server.py"],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

## Example output

`get_spend_summary` (demo data):

```
# AI Spend Summary (last 30 days)

Total estimated spend: $4,182.55
Trajectory: increasing
Anomalous days: 1

## Spend by provider
- openai: $2,560.10
- anthropic: $1,622.45

## Most expensive model
- openai / gpt-4o-2024-08-06: $1,910.22

## Top models
- openai / gpt-4o-2024-08-06: $1,910.22 (612,400,000 in / 88,100,000 out)
- anthropic / claude-3-5-sonnet-20241022: $1,204.10 (310,500,000 in / 41,200,000 out)
- openai / gpt-4o-mini-2024-07-18: $649.88 (3,210,000,000 in / 410,000,000 out)
- anthropic / claude-3-5-haiku-20241022: $418.35 (402,100,000 in / 60,400,000 out)

_Source: built-in demo data (no admin/usage API calls)._
```

`get_anomalies`:

```
# Spend Anomalies (2.0x over 7-day rolling avg)

- 2025-06-13: $498.20 (rolling avg $121.40, 4.1x)

_Source: built-in demo data (no admin/usage API calls)._
```

## How spend is calculated

The demo dataset provides daily token counts per model; **dollar amounts are
estimated** from the public list prices in `pricing.py` (USD per 1M tokens),
including reduced rates for cached tokens. To wire this up to real data later,
replace `usage.py`'s `fetch_all()` with your own source — the rest of the app
(`analytics.py`, `server.py`) is agnostic to where records come from.

## Project layout

```
ai-spend-attribution/
├── server.py        # FastMCP server + tool definitions
├── usage.py         # demo usage data generator (UsageRecord, fetch_all)
├── analytics.py     # anomalies, summary, trajectory, comparison
├── pricing.py       # public pricing tables + cost estimation
├── requirements.txt
├── .env.example
└── README.md
```
