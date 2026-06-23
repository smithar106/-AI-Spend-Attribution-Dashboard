# ai-spend-attribution

An [MCP](https://modelcontextprotocol.io) server that powers an **AI Spend
Attribution** dashboard. It analyzes daily token usage across **Anthropic**,
**Gemini**, and **DeepSeek** models, estimates spend from public list pricing,
detects spend spikes, and exposes everything as MCP tools your assistant can call.

> **Data source:** this app runs on a built-in, realistic **demo dataset**
> (30 days, multiple models per provider). It makes **no admin / workspace-
> management or usage-reporting API calls**. The standard `ANTHROPIC_API_KEY`
> (a regular key from console.anthropic.com) is used only for live Claude
> inference elsewhere in the app — never for usage reporting.

## Features

- Realistic **30-day demo usage** across multiple Anthropic, Gemini, and
  DeepSeek models (configurable window).
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
| `compare_providers` | Per provider (Anthropic, Gemini, DeepSeek): totals, trajectory, top model. |
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

Total estimated spend: $4,204.48
Trajectory: increasing
Anomalous days: 1

## Spend by provider
- anthropic: $3,143.77
- deepseek: $645.73
- gemini: $414.98

## Most expensive model
- anthropic / claude-3-5-sonnet-20241022: $1,418.41

## Top models
- anthropic / claude-3-5-sonnet-20241022: $1,418.41 (254,770,435 in / 42,778,781 out)
- anthropic / claude-3-opus-20240229: $1,103.05 (36,460,577 in / 7,343,358 out)
- anthropic / claude-3-5-haiku-20241022: $622.31 (423,377,749 in / 69,622,527 out)
- deepseek / deepseek-chat: $307.97 (668,793,053 in / 110,314,862 out)
- deepseek / deepseek-reasoner: $274.63 (173,719,211 in / 80,108,310 out)

_Source: built-in demo data (no admin/usage API calls)._
```

`get_anomalies`:

```
# Spend Anomalies (2.0x over 7-day rolling avg)

- 2026-06-14: $448.06 (rolling avg $131.37, 3.41x)

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
