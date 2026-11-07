# Eval cases for `/week`

Each case runs `/week <week>` headless against a frozen fixture. Flags (`load_spike`,
`layoff`, `incomplete_data`, `missing_hr`) and the next-week ceiling come from the server;
only `race_detected` is the analyst's inference. `run_evals.sh` checks the
deterministic markers (grep); a human review checks the judgement (tone, plan, reasoning).
Results and the pass/fail table live in the README.

| # | Week | Fixture | Data |
|---|---|---|---|
| 1 | 2026-W38 | `data/fixtures.json` | real |
| 2 | 2026-W42 | `data/fixtures.json` | real |
| 3 | 2026-W45 | `data/fixtures.json` | real |
| 4 | 2026-W30 | `evals/synthetic/build_week.json` | **synthetic** |

## 1. 2026-W38: low, irregular volume

Two short runs (4.1 km and 4.2 km, 8.3 km total). The fixture has no earlier runs, so the
previous weeks read as 0 km and the % change is undefined.

Expected:
- Numbers copied from the server: 8.3 km, 2 runs, longest 4.2 km.
- `change_vs_prior_avg_pct` is null and the report says why (prior weeks at 0 km). No % invented.
- Flags: `missing_hr` only. No `load_spike`, no `layoff`.
- Tone: states the facts without alarm (no "warning", "danger", "concerning").
- Ceiling 9.1 km (max(recent average 2.1, target 8.3) × 1.10); the plan stays at or below it.

Markers: `8.3`, `9.1`, `missing_hr`, `Not medical or coaching advice`; must NOT contain `load_spike` or `layoff`.

## 2. 2026-W42: Bilbao Night Half Marathon

A 2.8 km shakeout and the 22 km Bilbao Night Half Marathon after weeks of very low volume.

Expected:
- Server flags: `load_spike` (+481.3 %) and `missing_hr`; inferred: `race_detected`, marked
  as an inference.
- Ceiling 9.4 km (recent average, no increase after a spike); the plan is a recovery week at
  or below it, all easy, no long run, no intensity.
- Reasoning mentions the race and `days_to_race` counted from 2026-10-19 (188 days).

Markers: `race_detected`, `inferred`, `load_spike`, `481.3`, `9.4`, `recovery` (case-insensitive), `Not medical or coaching advice`.

## 3. 2026-W45: three weeks at 0 km

No runs in W43, W44 or W45 after the half marathon.

Expected:
- `zero_weeks_streak` = 3 and the `layoff` flag.
- The plan asks the runner, explicitly, why they stopped (injury, illness, holidays…)
  before adding load.
- Ceiling 6.2 km (recent average, no increase after a layoff); progressive return at or below it.
- Never tries to make up lost kilometres.
- Data caveats say W45 is still in progress (the eval runs before Sunday 2026-11-08).

Markers: `layoff`, `6.2`, `?` in the plan section, `Not medical or coaching advice`.

## 4. 2026-W30: normal build week (SYNTHETIC)

Synthetic data: four weeks at 30, 32, 33 and 35 km, four runs a week, heart rate recorded.
The target week is +10.5 % vs the previous three weeks' average.

Expected:
- No flags at all (no spike: +10.5 % is under the 30 % threshold; HR present).
- Ceiling 38.5 km (35 × 1.10); the plan keeps building at or below it, includes a long run,
  no recovery week, no question for the runner.

Markers: `35`, `10.5`, `38.5`, `Not medical or coaching advice`; must NOT contain `load_spike`, `layoff`, `missing_hr`.
