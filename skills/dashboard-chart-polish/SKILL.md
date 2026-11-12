---
name: dashboard-chart-polish
description: Polish the NASDAQ-100 correlation dashboard's chart layout and readability. Use when Plotly dates or axis titles are clipped, `Correlation` or `Z-score` labels sit on top of zero lines, dark-theme captions or helper text need brightening, section spacing between stacked dashboard blocks needs normalization, or the Heatmap tab needs the ticker price-action panel with yfinance OHLC fallback to local price artifacts.
---

# Dashboard Chart Polish

Follow this workflow:

1. Read `codex.md` before changing dashboard chart layout or styling.
2. Make chart-layout changes in `src/nasdaq_correlation_dashboard/dashboard.py` unless the user explicitly points to another active figure builder.
3. Give time-series charts enough left and bottom margin plus axis-title standoff so `Date`, `Correlation`, and `Z-score` titles stay clear of tick labels and zero lines.
4. Keep vertical spacing consistent between the Heatmap tab's price-action chart, heatmap, pair tables, and rolling-average chart.
5. Keep captions, helper copy, and other dimmed text bright enough to read cleanly on the dark theme.
6. Keep the Heatmap tab's historical-price panel above the correlation heatmap. Default it to `QQQM`, keep quick lookback controls for `1y`, `6m`, `3m`, and `1w`, prefer yfinance OHLC candlesticks when available, and fall back to the refreshed local adjusted-close artifact when OHLC data cannot be extracted.
7. Make sure rolling-average correlation titles describe the top-50 universe average rather than implying a single pair.
8. Do not unlock the heatmap's `[-1, 1]` range or change the red-neutral-green palette without explicit approval.
9. Update `codex.md`, `CLAUDE.md`, and any overlapping skill files after a durable chart-polish rule changes.
