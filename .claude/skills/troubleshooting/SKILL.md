---
name: troubleshooting
description: Diagnose and fix failures in the NASDAQ-100 top-50 correlation dashboard. Use when a refresh or dashboard launch errors out, Python or a dependency is missing or broken, the universe resolver or a ranking fallback fails, yfinance returns empty data, expected artifacts are missing or stale, metadata lacks provenance, or a Streamlit tab will not load.
---

# Troubleshooting

1. Read `codex.md` first; the failure may already be logged with a known fix.
2. Locate the failing stage: universe resolution → ranking fallback → price ingestion → correlation/pairs/export → dashboard rendering.
3. Check `data/processed/latest_metadata.json` to see whether the issue is already recorded as a fallback or partial failure.

## Environment

- Python 3.11+: `py -3 --version`. On this machine `python` may not be on PATH while `py -3` works; the `commands/*.ps1` wrappers handle both.
- Dependencies: `py -3 -m pip install -r requirements.txt` (pandas, numpy, plotly, streamlit, yfinance, openpyxl, requests, statsmodels).
- A broken `pyarrow` without `__version__` can make `pandas` fail at import.
- Streamlit can exit immediately in a non-interactive shell until `~/.streamlit/config.toml` and `credentials.toml` exist.
- Config: `config/dashboard_config.json` must be valid JSON and contain `universe_policy`.

## Common errors

| Symptom | Likely cause |
|---|---|
| `UniverseSourceError` from the Nasdaq endpoint | Official membership source down, stale endpoint, or schema change (`Name`/`Symbol` columns) |
| `UniverseSourceError` from QQQM holdings | Export redirected to a generic page or ranking columns renamed |
| Fewer than 50 ranked names | Fallback chain exhausted; never accept a smaller universe |
| `DataSourceError: yfinance returned empty data` | Provider outage, rate limiting, or symbol issue |
| `ModuleNotFoundError` | Missing dependency |
| `CERTIFICATE_VERIFY_FAILED` on every fetch | HTTPS inspection (proxy/antivirus). `net.configure_tls()` handles it on Windows automatically; elsewhere set `DASHBOARD_CA_BUNDLE` to the organisation's root PEM. Look for the `[tls]` stderr line |
| `X (rank N) first traded ..., replaced by Y` | A member listed after the window start; swapped for the next-ranked reserve name (`universe_policy.reserve_size`). `UniverseSourceError` if the reserve runs out |

## Artifacts

Confirm these exist and are fresh:

- `data/processed/latest_universe.csv`
- `data/processed/latest_correlation.csv`
- `data/processed/latest_metadata.json`
- `exports/nasdaq_top50_correlation_dashboard.xlsx`
- `data/processed/latest_pairs_cointegration_*.csv|json` for the Cointegration tab

## Closing out

- Do not call an issue fixed until the missing artifact or broken view is actually restored.
- Append a dated `codex.md` entry with the failure mode and the durable fix or guardrail.

Read [references/failure-playbook.md](references/failure-playbook.md) for the catalogue of known failure modes.
