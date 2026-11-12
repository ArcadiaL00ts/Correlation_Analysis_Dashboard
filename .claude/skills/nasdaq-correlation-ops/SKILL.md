---
name: nasdaq-correlation-ops
description: Refresh, maintain, or extend the NASDAQ-100 top-50 correlation dashboard pipeline. Use when the user asks to update or refresh the dashboard data, resolve the official NASDAQ-100 membership or top-50 ranking, change the Nasdaq → QQQM → Yahoo Finance fallback chain, fix stale or failed price fetches, recompute returns or correlations, regenerate the Excel workbook or processed CSV/JSON artifacts, or change scripts/update_dashboard.py.
---

# NASDAQ Correlation Ops

Covers the end-to-end refresh pipeline: universe → prices → returns/correlation → pairs → exports.

## Ground rules

1. Read `codex.md` before changing code so the latest operating rules and known failure modes stay in force.
2. Treat `config/dashboard_config.json` (`universe_policy`, `history`, `paths`, `pairs_trading`) as the source of truth.
3. Resolve official NASDAQ-100 membership from Nasdaq public data before any fallback ranking source.
4. Use QQQM holdings as the ranking proxy only when Nasdaq does not expose a public weight rank.
5. Use Yahoo Finance market-cap ranking only when QQQM holdings are unavailable, and record the fallback reason in metadata.
6. Never accept fewer than 50 ranked names, and never change the universe or fallback order without a `codex.md` entry.
7. Recompute returns and correlations locally from refreshed prices; never import external correlation values.

## Running a refresh

- Wrapper: `commands/update-dashboard.ps1` (prompts for the history horizon).
- Direct: `py -3 scripts/update_dashboard.py` or `py -3 scripts/update_dashboard.py --history-period 2y --pairs-history-period 1y`.
- Read-only universe preview: `py -3 scripts/refresh_universe.py`.
- Preserve both interactive prompts (price-history horizon and cointegration window) unless an explicit CLI override is passed. The shared prompt logic lives in `src/nasdaq_correlation_dashboard/cli.py`.
- The refresh snapshots `latest_*` to `previous_*` before writing new artifacts (see the `correlation-delta-tracking` skill).

## When a provider fails

- **Universe resolver** (`universe.py`): confirm the Nasdaq endpoint still returns membership data; check whether the QQQM holdings export redirected or changed columns; only fall back to Yahoo market-cap ranking via the configured chain, with the reason in metadata.
- **Prices** (`sources.py`): check for yfinance outages or schema drift. Manual fallback: drop `<TICKER>.csv` files into `data/manual_prices/` and use the `csv_directory` provider.

## Done means

Do not report success unless all of these were produced:

- `data/processed/latest_universe.csv`
- `data/processed/latest_correlation.csv`
- `data/processed/latest_metadata.json`
- `exports/nasdaq_top50_correlation_dashboard.xlsx`

After resolving a bug or environment issue, append a dated note to `codex.md`.

Read [references/source-policy.md](references/source-policy.md) when changing universe resolution, ranking fallbacks, or price providers.
