#!/usr/bin/env bash
# Run every /week eval case headless, save each report to evals/results/, and check the
# deterministic markers from evals/cases.md. Judgement (tone, plan) is reviewed by hand.
#
# Usage: evals/run_evals.sh            # all cases
#        evals/run_evals.sh 2          # only case 2
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p evals/results

# Read-only coach tools only. Passed explicitly because project allow rules are ignored
# until the workspace is trusted, and -p denies anything that would prompt.
ALLOWED="mcp__coach__get_weekly_load,mcp__coach__get_activities,ReadMcpResourceTool"

# id | week | fixture | markers that must appear | markers that must NOT appear
CASES=(
  "1|2026-W38|data/fixtures.json|8.3;missing_hr|load_spike;layoff"
  "2|2026-W42|data/fixtures.json|race_detected;load_spike;481.3;recovery|"
  "3|2026-W45|data/fixtures.json|layoff;?|"
  "4|2026-W30|evals/synthetic/build_week.json|35;10.5|load_spike;layoff;missing_hr"
)
FOOTER="Not medical or coaching advice"

failed=0
for case in "${CASES[@]}"; do
  IFS='|' read -r id week fixture must must_not <<<"$case"
  [[ $# -gt 0 && "$1" != "$id" ]] && continue
  out="evals/results/case${id}_${week}.md"
  echo "== case $id: /week $week ($fixture)"
  COACH_FIXTURES_PATH="$fixture" claude -p "/week $week" \
    --allowedTools "$ALLOWED" </dev/null >"$out" 2>"evals/results/case${id}.stderr"

  status=PASS
  IFS=';' read -ra wanted <<<"$must;$FOOTER"
  for m in "${wanted[@]}"; do
    grep -qiF -- "$m" "$out" || { echo "   missing: $m"; status=FAIL; }
  done
  if [[ -n "$must_not" ]]; then
    IFS=';' read -ra banned <<<"$must_not"
    for m in "${banned[@]}"; do
      grep -qiF -- "$m" "$out" && { echo "   unexpected: $m"; status=FAIL; }
    done
  fi
  [[ $status == FAIL ]] && failed=1
  echo "   markers: $status -> $out"
done
exit $failed
