# Eval cases for `/week`

Each case runs `/week <week>` headless against a frozen fixture. `run_evals.sh` checks the
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
- The plan builds gently from about 8 km; no jump to a "normal" volume.

Markers: `8.3`, `missing_hr`, `Not medical or coaching advice`; must NOT contain `load_spike` or `layoff`.

## 2. 2026-W42: Bilbao Night Half Marathon

A 2.8 km shakeout and the 22 km Bilbao Night Half Marathon after weeks of very low volume.

Expected:
- Flags: `race_detected` and `load_spike` (+481.3 %), plus `missing_hr`.
- The plan is a recovery week: total below 24.8 km, all easy, no long run, no intensity.
- Reasoning mentions the race and `days_to_race` (Madrid Marathon).

Markers: `race_detected`, `load_spike`, `481.3`, `recovery` (case-insensitive), `Not medical or coaching advice`.

## 3. 2026-W45: three weeks at 0 km

No runs in W43, W44 or W45 after the half marathon.

Expected:
- `zero_weeks_streak` = 3 and the `layoff` flag.
- The plan asks the runner, explicitly, why they stopped (injury, illness, holidays…)
  before adding load.
- Progressive return: short easy runs, total well below the last normal week.
- Never tries to make up lost kilometres.
- Data caveats say W45 is still in progress (the eval runs before Sunday 2026-11-08).

Markers: `layoff`, `?` in the plan section, `Not medical or coaching advice`.

## 4. 2026-W30: normal build week (SYNTHETIC)

Synthetic data: four weeks at 30, 32, 33 and 35 km, four runs a week, heart rate recorded.
The target week is +10.5 % vs the previous three weeks' average.

Expected:
- No flags at all (no spike: +10.5 % is under the 30 % threshold; HR present).
- The plan keeps building: total at or below about 10 % above 35 km (≤ ~38.5 km), includes a
  long run, no recovery week, no question for the runner.

Markers: `35`, `10.5`, `Not medical or coaching advice`; must NOT contain `load_spike`, `layoff`, `missing_hr`.
