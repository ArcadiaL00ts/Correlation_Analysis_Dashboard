# Failure Playbook

## Universe Resolution

- Official Nasdaq membership endpoint returns no data.
- Official endpoint schema changes and `Name` or `Symbol` columns disappear.
- Fewer than 50 ranked names can be built from the configured fallback chain.
- A member started trading after the lookback start (e.g. SPCX, listed 2026-06-12). `apply_history_coverage` swaps it for the next-ranked name with full history and records `history_substitutions` in metadata.

## Ranking Fallbacks

- QQQM holdings export redirects to a generic ETF page.
- QQQM holdings export downloads but changes symbol or weight column names.
- Yahoo Finance ranking returns no usable market-cap fields.

## Environment And Dependencies

- HTTPS inspection by a proxy or antivirus makes every fetch fail with `CERTIFICATE_VERIFY_FAILED`. Every entry point calls `net.configure_tls()`: `DASHBOARD_CA_BUNDLE` wins; otherwise on Windows a bundle of certifi + the Windows ROOT/CA stores is cached at `%LOCALAPPDATA%/nasdaq-correlation-dashboard/ca_bundle.pem`. Never disable verification.
- `python` is not on PATH but `py -3` is available, so wrapper scripts may work differently than direct shell commands.
- `streamlit` or `openpyxl` are missing, so the dashboard cannot run or export the workbook.
- `pandas` fails during import because the environment exposes a broken `pyarrow` module without a valid `__version__`.
- Streamlit exits immediately with a first-run onboarding prompt in a non-interactive shell until `~/.streamlit/config.toml` and `credentials.toml` are created.

## Artifacts And UI

- Universe csv, correlation csv, metadata json, or workbook missing after refresh.
- Metadata exists but does not capture fallback reason or source URL.
- Dashboard loads with missing or stale artifacts and should fail loudly instead of rendering partial views.
