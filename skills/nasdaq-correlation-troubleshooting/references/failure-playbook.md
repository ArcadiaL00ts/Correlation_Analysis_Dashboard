# Failure Playbook

## Universe Resolution

- Official Nasdaq membership endpoint returns no data.
- Official endpoint schema changes and `Name` or `Symbol` columns disappear.
- Fewer than 50 ranked names can be built from the configured fallback chain.

## Ranking Fallbacks

- QQQM holdings export redirects to a generic ETF page.
- QQQM holdings export downloads but changes symbol or weight column names.
- Yahoo Finance ranking returns no usable market-cap fields.

## Environment And Dependencies

- `python` is not on PATH but `py -3` is available, so wrapper scripts may work differently than direct shell commands.
- `streamlit` or `openpyxl` are missing, so the dashboard cannot run or export the workbook.
- `pandas` fails during import because the environment exposes a broken `pyarrow` module without a valid `__version__`.
- Streamlit exits immediately with a first-run onboarding prompt in a non-interactive shell until `~/.streamlit/config.toml` and `credentials.toml` are created.

## Artifacts And UI

- Universe csv, correlation csv, metadata json, or workbook missing after refresh.
- Metadata exists but does not capture fallback reason or source URL.
- Dashboard loads with missing or stale artifacts and should fail loudly instead of rendering partial views.
