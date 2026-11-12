---
name: visualization-update
description: Modify or add chart types, change color schemes, update Plotly figures, or adjust the heatmap in the NASDAQ-100 top-50 correlation dashboard. Use when the user wants to change how the dashboard visualizes the correlation research outputs.
---

# Visualization Update

Follow this workflow:

1. Read `codex.md` for the current visual guardrails before changing charts.
2. The active Plotly figure builders live in `src/nasdaq_correlation_dashboard/dashboard.py`.
3. Keep the heatmap color scale aligned with config:
   - min: `heatmap_min_color`
   - mid: `heatmap_mid_color`
   - max: `heatmap_max_color`
4. Never change the heatmap color scale or unlock the `[-1, 1]` range without explicit user approval.
5. Keep the heatmap visually dominant on the Heatmap tab: let it span the full available width and place strongest or weakest pair tables underneath it instead of squeezing them to the right.
6. When the heatmap has many tickers, make layout or margin adjustments so the top y-axis label is fully visible and no tick labels are clipped.
7. For rolling-correlation and z-score charts, use enough left and bottom margin plus axis-title standoff that `Date`, `Correlation`, and `Z-score` labels stay clear of tick labels and the zero line.
8. Keep section spacing consistent when stacking multiple charts or tables inside one tab.
9. Keep tab labels, slider labels, select-box labels, chart titles, captions, and helper text bright enough to remain readable on the dark background.
10. Keep the Heatmap tab's historical-price panel above the heatmap. Default it to `QQQM`, keep quick lookback controls for `1y`, `6m`, `3m`, and `1w`, prefer yfinance OHLC candlesticks when available, and otherwise fall back to the refreshed local adjusted-close artifact.
11. Make rolling-average correlation titles read as top-50 universe averages instead of implying a single pair.
12. Keep new views grounded in generated artifacts and metadata rather than direct source fetches from the UI unless the user explicitly asks for a live-data fallback.
13. For the cointegration view, use the generated pair-analysis csv/json artifacts instead of reading the Excel workbook in Streamlit.
14. When adding quantitative diagnostics, present the key thresholds and concise plain-English definitions so the tab remains interpretable for decision-making, not just statistically dense.
15. If a new visualization requires new derived data, add the computation in the analytics/correlation layer before wiring it into the dashboard.
