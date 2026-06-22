# ai-spend-attribution

An [MCP](https://modelcontextprotocol.io) server that attributes your AI API
spend. It pulls **daily token usage** from the org-level **Anthropic** and
**OpenAI** usage APIs, estimates spend from public list pricing, detects spend
spikes, and exposes everything as MCP tools your assistant can call.

## Features

- Connects to the **Anthropic Usage API** and **OpenAI Usage API** with
  org-level admin keys.
- Pulls **daily token usage for the last 30 days** (configurable) from both
  providers.
- Breaks usage down by **model**, **day**, and **cumulative spend**
  (computed locally from public pricing in `pricing.py`).
- **Anomaly detection** — flags any day where total spend exceeds **2x the
  7-day rolling average** (both configurable).
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
- **Admin / org-level API keys** — the usage endpoints are *not* available to
  standard keys:
  - Anthropic: an **Admin key** (`sk-ant-admin...`) from
    <https://console.anthropic.com/settings/admin-keys>.
  - OpenAI: an **Admin key** (`sk-admin...`) with the `api.usage.read` scope
    from <https://platform.openai.com/settings/organization/admin-keys>.

## Setup

```bash
git clone https://github.com/smithar106/-AI-Spend-Attribution-Dashboard.git
cd -AI-Spend-Attribution-Dashboard

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# edit .env and add your admin keys
```

### Environment variables

| Variable | Required | Notes |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | yes* | Anthropic **admin** key (`sk-ant-admin...`). |
| `OPENAI_API_KEY` | yes* | OpenAI **admin** key (`sk-admin...`). |
| `ANTHROPIC_ORG_ID` | optional | Organization identifier. |
| `OPENAI_ORG_ID` | optional | Sent as the `OpenAI-Organization` header. |
| `LOOKBACK_DAYS` | optional | Default lookback window (defaults to 30). |

\* At least one provider's key is required. If only one is set, the server runs
with that provider and reports a warning for the other.

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
        "ANTHROPIC_API_KEY": "sk-ant-admin-...",
        "OPENAI_API_KEY": "sk-admin-...",
        "OPENAI_ORG_ID": "org-..."
      }
    }
  }
}
```

## Example output

`get_spend_summary`:

```
# AI Spend Summary (last 30 days)

Total estimated spend: $4,182.55
Trajectory: increasing
Anomalous days: 2

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
```

`get_anomalies`:

```
# Spend Anomalies (2.0x over 7-day rolling avg)

- 2025-06-12: $498.20 (rolling avg $121.40, 4.1x)
- 2025-06-19: $310.05 (rolling avg $140.10, 2.21x)
```

`compare_providers`:

```
# Provider Comparison

## anthropic
- Total spend: $1,622.45
- Active days: 30
- Trajectory: flat
- Top model: claude-3-5-sonnet-20241022 ($1,204.10)

## openai
- Total spend: $2,560.10
- Active days: 30
- Trajectory: increasing
- Top model: gpt-4o-2024-08-06 ($1,910.22)

## Summary
- Combined spend: $4,182.55
- Higher spend: openai
```

## How spend is calculated

Token counts come from the provider usage APIs; **dollar amounts are estimated
locally** from the public list prices in `pricing.py` (USD per 1M tokens),
including reduced rates for cached/prompt-caching tokens. These estimates do not
reflect enterprise discounts, batch pricing, or promotional credits and will not
match an invoice exactly. Update `pricing.py` when vendors change pricing.

## Project layout

```
ai-spend-attribution/
├── server.py        # FastMCP server + tool definitions
├── usage.py         # Anthropic + OpenAI usage API clients, normalized records
├── analytics.py     # anomalies, summary, trajectory, comparison
├── pricing.py       # public pricing tables + cost estimation
├── requirements.txt
├── .env.example
└── README.md
```
