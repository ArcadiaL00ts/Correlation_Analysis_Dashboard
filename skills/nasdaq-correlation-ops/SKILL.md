---
name: nasdaq-correlation-ops
description: Build, refresh, troubleshoot, or extend the NASDAQ-100 top-50 correlation dashboard. Use when Codex needs to resolve the official NASDAQ-100 membership, rank the top 50 with documented fallback sources, refresh price history, recalculate returns or correlations, export the Excel workbook, update the Streamlit research dashboard, or append workflow guidance to codex.md.
---

# NASDAQ Correlation Ops

Follow this workflow:

1. Read `codex.md` before changing code so the latest operating rules stay in force.
2. Load `config/dashboard_config.json` and treat its universe policy as the current source of truth.
3. Resolve the official NASDAQ-100 membership from Nasdaq public data before using any fallback ranking source.
4. Use QQQM holdings as the preferred ranking proxy only when public Nasdaq weight rank is not available.
5. Use Yahoo Finance market-cap ranking only when QQQM public holdings are unavailable and record the fallback reason in metadata.
6. Run `commands/update-dashboard.ps1` when the environment is ready, or patch `scripts/update_dashboard.py` if the refresh pipeline needs changes.
7. Preserve the interactive history-horizon prompt on refresh runs unless the caller passed an explicit CLI override.
8. Preserve the separate cointegration analysis-window prompt or override for pairs trading so correlation refresh and pairs testing can use different historical spans.
9. Keep the dashboard gradient fixed to `-1 dark red`, `0 warm neutral`, `+1 green`.
10. Recompute returns and correlation locally from price history; do not rely on external correlation values.
11. Keep the cointegration dashboard tab driven by generated csv/json artifacts and refresh those artifacts during the main update flow.
12. Keep time-series chart margins, bottom padding, and axis-title standoffs generous enough that date labels and `Correlation` or `Z-score` titles are never clipped or parked on top of the zero line.
13. Keep the Heatmap tab's historical-price panel above the correlation map, default it to `QQQM`, preserve quick lookback controls for `1y`, `6m`, `3m`, and `1w`, and let it use yfinance OHLC candlesticks when available with local adjusted-close fallback from the refreshed price artifact.
14. Label rolling-average correlation charts as top-50 universe averages so users do not mistake them for a single pair.
15. After resolving a bug or environment issue, append a dated troubleshooting note to `codex.md`.

Read [references/source-policy.md](references/source-policy.md) when changing universe resolution, ranking fallbacks, or price providers.
