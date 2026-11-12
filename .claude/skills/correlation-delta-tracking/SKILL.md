---
name: correlation-delta-tracking
description: Maintain the prior-run vs current-run correlation comparison in the NASDAQ-100 dashboard. Use when the user asks about the biggest correlation changes since the last refresh, when the correlation-delta panel is empty or stale, when previous_* snapshot artifacts need wiring or fixing, or when extending the UI that shows the largest increases, decreases, or absolute moves.
---

# Correlation Delta Tracking

Follow this workflow:

1. Read `codex.md` before changing prior-run comparison behavior so the current dashboard and refresh guardrails stay in force.
2. Load `config/dashboard_config.json` and treat the `paths` block as the source of truth for both `latest_*` and `previous_*` artifacts.
3. Keep the prior-run comparison grounded in generated artifacts, not ad hoc workbook parsing or live refetches from the Streamlit layer.
4. Preserve these snapshot files when the feature is active:
   - `data/processed/previous_universe.csv`
   - `data/processed/previous_correlation.csv`
   - `data/processed/previous_metadata.json`
5. Update `scripts/update_dashboard.py` when the delta basis changes. The refresh flow must snapshot the existing `latest_*` artifacts before writing new ones so each successful refresh compares against the immediately prior successful run.
6. Keep correlation deltas overlap-aware. Compare only ticker pairs present in both the current and prior correlation matrices so universe churn does not create bogus pair deltas.
7. Keep pairwise delta calculations in `src/nasdaq_correlation_dashboard/correlation.py` or another analytics-layer helper, not inline inside the dashboard UI.
8. Keep the interactive delta view in `src/nasdaq_correlation_dashboard/dashboard.py`, and present at least:
   - largest absolute correlation moves
   - largest increases
   - largest decreases
   - pair-level prior/current/detail readout
9. If the prior snapshot is missing, show a helpful dashboard message instead of failing. Explain that the comparison becomes active after the next successful refresh.
10. Preserve the existing visual guardrails for dark-theme readability, axis spacing, and artifact-driven UI behavior.
11. After changing the snapshot workflow or delta UI, run `py -3 scripts/update_dashboard.py` so the `previous_*` artifacts refresh and the dashboard has a real prior/current pair to compare.
12. Validate with at least:
   - `py -3 -m unittest discover -s tests -p "test_*.py"`
   - `py -3 -m compileall src scripts tests`
13. Document material workflow changes in `codex.md`, especially if the meaning of "prior run" or the preserved artifacts changes.
