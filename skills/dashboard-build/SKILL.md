---
name: dashboard-build
description: Build, rebuild, or modify the Streamlit GUI for the NASDAQ-100 top-50 correlation dashboard. Use when changing the dashboard layout, adding or removing research views, updating CSS styles, or restructuring the current multi-tab interface in `dashboard.py`.
---

# Dashboard Build

Follow this workflow:

1. Read `codex.md` for current guardrails and visual expectations before touching the UI.
2. The active dashboard lives in `src/nasdaq_correlation_dashboard/dashboard.py`.
3. Keep the research layout centered on:
   - `QQQM` historical-price panel above the heatmap with quick lookback controls
   - static heatmap
   - rolling research views
   - universe provenance
   - run status
4. Preserve the premium Streamlit styling, the red-neutral-green heatmap scale, and the locked `[-1, 1]` correlation domain.
5. Keep section spacing consistent across stacked charts, tables, and card blocks.
6. Keep time-series chart axes readable by using enough left and bottom margin and title standoff that `Date`, `Correlation`, and `Z-score` labels are fully unobstructed.
7. Label rolling-average correlation charts as universe-wide averages so they are not mistaken for a single ticker pair.
8. Keep expensive calculations derived from generated artifacts rather than refetching sources in the UI layer, except when the user explicitly wants a live-data visualization fallback.
9. After changes, test with `streamlit run src/nasdaq_correlation_dashboard/dashboard.py`.
10. Document material layout changes in `codex.md`.
