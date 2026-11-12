---
name: troubleshooting
description: Diagnose and fix issues with the NASDAQ-100 top-50 correlation dashboard. Use when Python, dependencies, universe resolution, data providers, generated artifacts, or dashboard loading are causing errors.
---

# Troubleshooting

Follow this diagnostic workflow:

1. Check Python: verify Python 3.11+ is available via `python --version` or `py -3 --version`.
2. Check dependencies against `requirements.txt`. Key packages: pandas, numpy, plotly, streamlit, yfinance, openpyxl, requests.
3. Validate config: ensure `config/dashboard_config.json` is valid JSON and contains `universe_policy`.
4. Check generated artifacts:
   - `data/processed/latest_universe.csv`
   - `data/processed/latest_correlation.csv`
   - `data/processed/latest_metadata.json`
   - `exports/nasdaq_top50_correlation_dashboard.xlsx`
5. Common errors:
   - `UniverseSourceError` from Nasdaq endpoint -> official membership source unavailable or schema changed.
   - `UniverseSourceError` from QQQM holdings -> export redirected or no usable ranking columns were found.
   - `DataSourceError: yfinance returned empty data` -> provider outage, rate limiting, or symbol issue.
   - `ModuleNotFoundError` -> missing dependency. Run `pip install -r requirements.txt`.
6. Always append findings to `codex.md` with the date and the durable fix or guardrail.
