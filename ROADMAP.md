# Roadmap

Ideas that came up but were out of scope. Each one would widen the project, so it waits here.

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
- **Fixture start is invisible.** Weeks before the first fixture run read as 0 km, so the
  agent can call W38 "a return after three zero weeks" when the data simply starts there.
  A `history_start` field would let it say "no earlier data" instead.
- **More eval cases:** a week with blocked (Strava) activities, a week with heart rate,
  a taper week close to race day.

## Done

- [x] **Move the judgement thresholds into code.** `get_weekly_load` now returns deterministic
  `flags` (`load_spike`, `layoff`, `incomplete_data`, `missing_hr`) and
  `suggested_max_next_week_km`, computed and tested in `analytics.py` from settings
  (`spike_threshold_pct`, `layoff_min_zero_weeks`, `max_weekly_increase_pct`). The analyst
  copies them; only `race_detected` stays a model inference, in `inferred_flags`.
  The evals then caught a bug: the trend depended on the caller's `n_weeks`, so the planner
  got a different ceiling than the analyst. Now a fixed `trend_window_weeks=4` drives the
  % change, flags and ceiling, with a regression test.
- [x] **`days_to_race` relative to the planned week.** `get_weekly_load` returns
  `next_week_start`, and the resource template `coach://goal/{as_of}` counts the days from
  that Monday in code. The model only copies a date string.
