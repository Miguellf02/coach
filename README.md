# coach

A deliberately small, read-only MCP server that lets an AI agent analyse my running training.
Two tools, one resource, all maths done in code. Built while preparing for the
Claude Certified Architect – Foundations exam.

> **Why so small?** I have built large MCP servers before and watched agents get lost choosing
> between dozens of tools. This repo explores the opposite: the fewest tools that still answer
> "how was my week?" and "what should next week look like?".

## Every piece in one sentence

| Piece | What it does |
|---|---|
| `get_activities` (tool) | Lists individual runs in a date range (max 31 days). |
| `get_weekly_load` (tool) | Returns weekly totals plus trend, so the model never adds up kilometres itself. |
| `coach://goal` (resource) | Exposes the target race; it is static data, so it is a resource, not a tool. |
| `sources.py` | Hides *where* data comes from (live API or frozen fixtures) behind one `Protocol`. |
| `analytics.py` | Pure functions: every number the agent sees is computed and tested here. |
| `models.py` | Frozen Pydantic V2 models with units in every field name. |
| `data/fixtures.json` | My real runs, frozen, so tests and evals are reproducible offline. |

## Design decisions

- **Arithmetic in code, judgement in the model.** Load, pace, weekly change and zero-week
  streaks are computed in `analytics.py`. The LLM interprets; it does not calculate.
- **Read-only by construction.** The server only exposes GET calls and every tool is annotated
  `readOnlyHint=true`. Safety does not depend on a prompt.
- **Actionable errors.** A bad request returns `isError` with a message that tells the agent how
  to fix it (e.g. "Range is 152 days; max is 31. Narrow it, or use get_weekly_load").
- **Missing data is explicit.** I run without a heart-rate sensor, so HR is `null` and
  `missing_heart_rate` counts it. Load is estimated from pace instead (rTSS-like: one hour at
  threshold pace = 100).

## Known limitation: Strava

Intervals.icu does not expose Strava-synced activities through its API (Strava's terms forbid
re-distribution). Those come back as stubs with a `_note` field and no distance or time.

The server does not fail the whole request because of them, and it never lets them look like
rest days:

- `get_activities` returns the readable runs as usual, plus a `blocked` list (id, date and a
  reason explaining how to fix it) for the activities that exist but cannot be read.
- `get_weekly_load` reports `blocked_activities` per week (if > 0, that week's totals
  undercount) and `data_complete: false` when any returned week has one. In that case
  `change_vs_prior_avg_pct` is `null`, and a week with blocked activities breaks the
  `zero_weeks_streak`, so a blocked half marathon never shows up as a 0 km week.

Fix: import your Strava archive into Intervals.icu once, instead of syncing from Strava.

## Run it

```bash
uv sync
cp .env.example .env          # add your Intervals.icu API key, or use fixtures mode
uv run pytest                 # 10 tests, fully offline
```

With Claude Code, open the folder: `.mcp.json` registers the server automatically (project scope).

Offline demo without any account:

```bash
COACH_FIXTURES_PATH=data/fixtures.json claude
```

## Stack

Python 3.12 · MCP Python SDK v2 (`MCPServer`) · Pydantic V2 · httpx · pytest · ruff · mypy --strict

---
*Not medical or coaching advice. It is a learning project about agent architecture.*
