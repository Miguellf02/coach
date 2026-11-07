# Roadmap

Ideas that came up but were out of scope. Each one would widen the project, so it waits here.

- **Move the remaining judgement thresholds into code.** The analyst decides `load_spike`
  (> 30 %) and `layoff` (≥ 2 zero weeks) by comparing server numbers in its prompt, and the
  planner applies the ~10 % cap itself. Better: `get_weekly_load` returns `flags` and
  `max_next_week_km`, computed and tested in `analytics.py`. This is a server change, so it
  was left out on purpose.
- **Race detection in code.** `race_detected` is a keyword match on run names done by the
  model. An `is_race` field (Intervals.icu workout type, or a name rule in `analytics.py`)
  would make it deterministic.
- **Validate the analyst JSON with a schema.** Today the `/week` skill checks the keys by
  reading them. A `SubagentStop` hook (or a Pydantic model run by a hook) could reject a
  reply that breaks the contract before the planner ever sees it.
- **Automated judge for evals.** `run_evals.sh` only greps markers; tone and plan quality are
  reviewed by hand. An LLM-as-judge step with a rubric per case would scale better.
- **Workspace trust in scripts.** Project `permissions.allow` rules are ignored until the
  folder is trusted, so `run_evals.sh` passes `--allowedTools`. `--bare` with explicit
  `--mcp-config/--agents` would make evals more hermetic, but bare mode never runs hooks,
  so the evals would stop testing the hook guarantees. Not worth it yet.
- **`days_to_race` relative to the planned week.** The `coach://goal` resource counts days
  from today, so a report on a past week plans with today's countdown (the W38 eval report
  noticed this itself). A `?from=` parameter on the resource, or an `as_of` argument, would
  fix it.
- **Fixture start is invisible.** Weeks before the first fixture run read as 0 km, so the
  agent can call W38 "a return after three zero weeks" when the data simply starts there.
  A `history_start` field would let it say "no earlier data" instead.
- **More eval cases:** a week with blocked (Strava) activities, a week with heart rate,
  a taper week close to race day.
