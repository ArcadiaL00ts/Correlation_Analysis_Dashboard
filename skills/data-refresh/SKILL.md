---
name: data-refresh
description: Refresh the top-50 universe, price data, returns, and correlation artifacts for the NASDAQ-100 dashboard. Use when data is stale, a provider is failing, or the output artifacts need to be regenerated.
---

# Data Refresh

Follow this workflow:

1. Read `codex.md` for the current source and fallback rules.
2. Load `config/dashboard_config.json` and treat its universe policy as the source of truth.
3. Run the full pipeline with `python scripts/update_dashboard.py`.
4. If the universe resolver fails:
   - Confirm the official Nasdaq endpoint still returns membership data.
   - Confirm whether the QQQM holdings export redirected or changed format.
   - Fall back to Yahoo Finance market-cap ranking only if the configured resolver does so and metadata records the reason.
5. If yfinance price loading fails:
   - Check for provider outages or schema drift.
   - Fall back to `csv_directory` by placing CSV files in `data/manual_prices/<TICKER>.csv`.
6. Verify outputs:
   - `data/processed/latest_universe.csv`
   - `data/processed/latest_correlation.csv`
   - `data/processed/latest_metadata.json`
   - `exports/nasdaq_top50_correlation_dashboard.xlsx`
7. Append a dated troubleshooting entry to `codex.md` if anything failed or required a new workaround.
