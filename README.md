# coach

A deliberately small, read-only MCP server plus a two-subagent Claude Code workflow that
reviews my running week and plans the next one. Two tools, one resource, all maths done in
code. Built while preparing for the Claude Certified Architect – Foundations exam.

> **Why so small?** I have built large MCP servers before and watched agents get lost choosing
> between dozens of tools. This repo explores the opposite: the fewest pieces that still answer
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
| `.claude/agents/analyst.md` | Subagent (Haiku) that reads one week with 2 tools and returns a fixed JSON contract. |
| `.claude/agents/planner.md` | Subagent (Sonnet) that turns the analyst JSON and the race goal into a 7-day plan. |
| `.claude/skills/week/SKILL.md` | The `/week` command: runs analyst → planner and owns the report format. |
| `.claude/hooks/limit_activity_range.py` | PreToolUse hook that blocks `get_activities` calls over 14 days. |
| `.claude/hooks/check_python.py` | PostToolUse hook that runs ruff and mypy after every `.py` edit and reports failures to Claude. |
| `.claude/settings.json` | Wires the hooks, pre-approves the two read-only tools and denies reading `.env`. |
| `evals/` | Four `/week` cases run headless, with expected behaviour and saved reports. |
| `docs/overview.md` | Two-page overview (source of `docs/coach-overview.pdf`). |
| `ROADMAP.md` | Ideas left out on purpose. |

## How `/week` flows

```mermaid
flowchart TD
    U["/week 2026-W42"] --> S["Skill /week<br/>(orchestrator, owns report format)"]
    S -->|"prompt: ISO week"| A["analyst subagent · Haiku<br/>tools: get_weekly_load, get_activities"]
    A -->|"JSON contract"| S
    S -->|"prompt: analyst JSON, verbatim"| P["planner subagent · Sonnet<br/>tools: get_weekly_load, ReadMcpResourceTool"]
    P -->|"7-day plan + reasoning"| S
    S --> R["Report: Summary · What happened · Flags ·<br/>Next week plan · Data caveats"]

    A -. "get_activities" .-> H1{{"PreToolUse hook<br/>range ≤ 14 days?"}}
    H1 -->|"yes"| M
    H1 -->|"no: exit 2 + how to fix"| A
    A -. "get_weekly_load" .-> M[("coach MCP server<br/>read-only · 2 tools · 1 resource")]
    P -. "get_weekly_load, coach://goal" .-> M
    M --> D["Intervals.icu API<br/>or frozen fixtures"]

    E["Edit / Write of a .py file"] --> H2{{"PostToolUse hook<br/>ruff + mypy"}}
    H2 -->|"fail: exit 2, stderr to Claude"| E
```

## Example report (real data, 2026-W42)

Output of `claude -p "/week 2026-W42"` against `data/fixtures.json`
(saved in [`evals/results/case2_2026-W42.md`](evals/results/case2_2026-W42.md)):

> # Training week 2026-W42
>
> ## Summary
> Race week: a short shakeout on Tuesday, then the Bilbao Night Half Marathon on Saturday.
> The plan for the following week is recovery, with only short easy runs.
>
> ## What happened
> | Metric | Value |
> |---|---|
> | Distance | 24.8 km |
> | Runs | 2 |
> | Longest run | 22 km |
> | Change vs prior weeks' average | 481.3 % |
> | Consecutive 0 km weeks | 0 |
>
> Two runs: a 2.8 km shakeout on 2026-10-13 and the 22.0 km Bilbao Night Half Marathon on
> 2026-10-17. Heart rate is missing for both runs (missing_heart_rate = 2), so no HR values
> are reported. The week has no blocked activities.
>
> ## Flags
> - **load_spike**: this week's distance was far above the average of the weeks before it.
>   Here that comes from the race, not from a sudden jump in normal training.
> - **race_detected**: one of the runs was a race, the Bilbao Night Half Marathon.
> - **missing_hr**: neither run has heart rate data, so effort can't be judged from heart rate.
>
> ## Next week plan
> | Day | Session | Approx. km |
> |---|---|---|
> | Mon | Rest | 0 |
> | Tue | Easy run, conversational effort, flat terrain | 4 |
> | Wed | Rest | 0 |
> | Thu | Easy run, conversational effort | 5 |
> | Fri | Rest | 0 |
> | Sat | Easy run, relaxed and short of tired, no pushing the pace | 5 |
> | Sun | Very easy run or walk/jog, just loosening up | 3 |
>
> Reasoning: The reference week is 2026-W42 at 24.8 km. It included a 22 km half marathon and
> was flagged `load_spike` and `race_detected`, so next week is a recovery week at about 17 km,
> below the reference. It has no long run and no intensity, and the effort is described by
> feel because heart rate is missing. With 169 days to the Maratón de Madrid (25 April 2027),
> there is plenty of time to absorb the race and then build base mileage gradually. Nothing
> needs to be made up.
>
> ## Data caveats
> - Heart rate is missing for both runs.
> - The week after W42 is 2026-W43, which has already happened, so this plan describes what
>   recovery should have looked like rather than an upcoming week. The 169-day countdown is
>   counted from today (2026-11-07), not from W43.
> - The +481.3 % change compares a race week with lighter weeks before it, so it overstates
>   how much training load really rose.
> - The half marathon is recorded as 22.0 km, a bit over the official 21.1 km. This is
>   probably GPS overshoot.
> - No blocked activities; data is complete.
>
> ---
> *Not medical or coaching advice.*

## Evals

Four cases, defined in [`evals/cases.md`](evals/cases.md). `evals/run_evals.sh` runs each one
headless (`claude -p "/week <week>"` with `COACH_FIXTURES_PATH` pointing at its fixture),
saves the report to `evals/results/`, and greps the deterministic markers. I then reviewed
every report by hand against the expected behaviour.

| # | Week | Data | Expected | Markers | Review | Result |
|---|---|---|---|---|---|---|
| 1 | 2026-W38 | real | Low irregular volume stated calmly; null % change explained; plan stays ~8 km | PASS | 8.3 km, `missing_hr` only, no alarm words, plan ≈ 8 km | **PASS** |
| 2 | 2026-W42 | real | Race + spike detected; recovery week | PASS | `race_detected` + `load_spike`, plan ≈ 17 km all easy, no long run | **PASS** |
| 3 | 2026-W45 | real | `layoff`, progressive return, question about the cause | PASS | streak 3, question asked first, plan ≈ 10 km, "week in progress" caveat | **PASS** |
| 4 | 2026-W30 | **synthetic** | Normal build: no flags, ≤ ~10 % increase, long run kept | PASS | no flags, plan ≈ 36 km (cap ≈ 38.5), long run 14 km | **PASS** |

> **Case 4 uses synthetic data.** `evals/synthetic/build_week.json` is invented (four weeks of
> 30, 32, 33 and 35 km with heart rate) to cover the "everything is normal" path, which my
> real data does not have. Cases 1–3 use my real runs in `data/fixtures.json`.

Caveat from case 1: the fixture starts on 2026-09-15, so the agent reads the earlier weeks as
0 km and calls W38 "a return to running". That is what the data says, not what happened;
see `ROADMAP.md`.

## Hooks and permissions

Rules that must always hold live in code that runs on every call, not in prompts.

- **PreToolUse, `mcp__coach__get_activities`**: blocks (exit 2) any range over 14 days, with a
  message that says how to fix the call.
- **PostToolUse, `Edit|Write`**: after any `.py` edit, runs `uv run ruff check` and
  `uv run mypy src`; on failure it exits 2 and Claude sees the errors and fixes them.
- **`permissions.deny: Read(./.env)`**: the agent cannot open the file that holds the API key.
  (The rule covers the Read tool; it does not stop a shell command such as `cat`.)

**Server limit (31 days) vs hook limit (14 days).** They answer different questions. The
server validates that a request is *valid*: anything up to 31 days is a correct call and the
server will answer it, for any client. The hook is a *client policy* of this Claude Code
setup: a 31-day list of runs is valid but would flood the agent's context, so this client
refuses anything over 14 days and points to `get_weekly_load` for longer trends. The server
stays general; the client is stricter for its own reasons.

Both hooks were tested with a passing and a failing case, standalone and inside a live
`claude -p` session (the PreToolUse hook stopped a 31-day call before it reached the server;
the PostToolUse hook made Claude remove an unused import and add type hints).

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
- **Why two subagents: context isolation.** The analyst's raw tool output (weekly summaries,
  every run) stays in its own context window; the planner only sees a compact JSON. Each one
  also gets the model it needs: Haiku for extraction, Sonnet for planning.
- **Why tool allowlists.** A subagent without a `tools` field inherits every tool, Bash and
  Write included. The analyst gets exactly two read-only tools; the planner gets one tool and
  the resource reader. Least privilege is declared, not hoped for.
- **Why hooks and not prompts for guarantees.** A prompt is a request the model usually
  follows; a hook is code the harness runs on every call. The 14-day limit and the lint/type
  checks must hold every time, so they are hooks.
- **Why the hand-off is a JSON with a contract.** Subagents share no memory. A fixed set of
  keys makes the hand-off explicit, checkable by the orchestrator and easy to test, and keeps
  numbers copied from the server instead of retold in prose.
- **Why the report format lives in the skill.** Progressive disclosure: it loads only when
  `/week` runs, instead of sitting in `CLAUDE.md` in every session.
- **How the planner reads the goal.** Subagents can read MCP resources through the built-in
  `ReadMcpResourceTool`, so it is in the planner's allowlist. If that ever fails, the planner
  accepts a `goal` object pasted in its prompt by the orchestrator.

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
Accept the workspace trust dialog once: until then Claude Code ignores the project's
`permissions.allow` rules (deny rules and hooks still apply).

Offline demo without any account:

```bash
COACH_FIXTURES_PATH=data/fixtures.json claude
> /week 2026-W42
```

Evals and the PDF overview:

```bash
evals/run_evals.sh                                   # all cases, or: evals/run_evals.sh 2
uv run --with markdown-pdf python docs/build_pdf.py  # builds and checks docs/coach-overview.pdf
```

## Stack

Python 3.12 · MCP Python SDK v2 (`MCPServer`) · Pydantic V2 · httpx · pytest · ruff · mypy --strict ·
Claude Code subagents, skills and hooks

---
*Not medical or coaching advice. It is a learning project about agent architecture.*
