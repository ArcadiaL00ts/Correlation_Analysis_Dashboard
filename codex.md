# Codex Operating Guide

## Purpose

This repo maintains a research-grade correlation dashboard for the top 50 stocks in the NASDAQ-100 and exports both a polished Streamlit application and an Excel workbook.

## Default Workflow

1. Read `config/dashboard_config.json`.
2. Resolve the live NASDAQ-100 membership from the official Nasdaq weighting endpoint.
3. Use public Nasdaq data as the membership authority.
4. Use a ranked top-50 cut based on public weight proxies:
   - First choice: QQQM holdings export.
   - Fallback: Yahoo Finance market-cap ranking across the official membership list.
5. Refresh artifacts with `commands/update-dashboard.ps1` and choose the requested history horizon when prompted, unless an explicit CLI override is passed. Each successful refresh snapshots the current `latest_*` universe, correlation, and metadata artifacts into `previous_*` files before writing the new run, so the dashboard's correlation-delta view always compares against the immediately prior successful refresh.
6. Choose the cointegration analysis window separately when prompted, unless an explicit pairs-history CLI override is passed.
7. Open the app with `commands/open-dashboard.ps1`.
8. If source logic, workflow rules, or failure handling changes, update `prompts/nasdaq_correlation_dashboard_prompt.md` and the relevant skill files in `skills/`.
9. After any material run or workflow change, append a dated note to the troubleshooting log.

## Source Rules

- Universe authority: official Nasdaq NDX weighting data endpoint and supporting public NDX materials.
- Membership source: `https://indexes.nasdaq.com/Index/WeightingData` for `NDX`.
- Ranking preference: public QQQM holdings export when available.
- Ranking fallback: Yahoo Finance market-cap ranking across the official member set.
- Price history default: `yfinance` adjusted close daily data.
- Local fallback prices: `data/manual_prices/<TICKER>.csv`.
- Correlation must always be calculated locally from refreshed returns.
- Cointegration tests must run on price levels with a configurable trailing analysis window from `pairs_trading.history_period`.

## Parallel Workstreams

- Source and universe validation.
- Price acquisition and guardrails.
- Analytics and export generation.
- GUI polish, docs, and skill upkeep.

## Guardrails

- Do not silently change the universe policy or fallback order.
- Do not accept a universe smaller than 50 names.
- Do not claim a top-50 rank source if the metadata does not record the exact source and fallback reason.
- Do not report success if the universe csv, correlation csv, metadata json, and Excel workbook were not generated.
- Keep the heatmap locked to the `[-1, 1]` domain.
- Preserve the visual mapping: `-1 dark red`, `0 warm neutral`, `+1 green`.
- Keep the heatmap visually dominant: expand it full width, keep pair tables below it, and ensure the top y-axis ticker labels are not clipped.
- Keep the Heatmap tab ordered as: ticker price-action chart, heatmap, pair tables, rolling-average chart, with consistent vertical spacing between each section.
- Keep time-series charts on the dark theme readable with explicit left and bottom margins plus axis-title standoffs so the `Date`, `Correlation`, and `Z-score` titles never collide with tick labels or zero lines.
- Prefer a candlestick price-action panel on the Heatmap tab when OHLC data is available; if not, fall back to the refreshed local adjusted-close artifact rather than leaving the section blank.
- Default the Heatmap tab's historical-price ticker to `QQQM`, and keep the quick lookback selector available for `1y`, `6m`, `3m`, and `1w`.
- Label the rolling-average correlation chart as a universe-wide average, not as a specific ticker pair.
- Keep tab labels, slider labels, select-box labels, and chart titles readable against the dark background.
- Keep captions and helper copy bright enough to read cleanly against the dark background.
- If the primary price provider fails, capture the failure and record the fallback in metadata.
- Keep the cointegration tab grounded in generated pair-analysis artifacts, not workbook parsing or direct data fetches from the UI.
- Show threshold definitions in plain English on the cointegration tab so the stat filters remain interpretable.

## Expected Outputs

- `data/processed/latest_universe.csv`
- `data/processed/previous_universe.csv`
- `data/processed/latest_prices.csv`
- `data/processed/latest_returns.csv`
- `data/processed/latest_correlation.csv`
- `data/processed/previous_correlation.csv`
- `data/processed/latest_metadata.json`
- `data/processed/previous_metadata.json`
- `data/processed/latest_pairs_cointegration_all.csv`
- `data/processed/latest_pairs_cointegration_qualified.csv`
- `data/processed/latest_pairs_cointegration_spreads.csv`
- `data/processed/latest_pairs_cointegration_metadata.json`
- `exports/nasdaq_top50_correlation_dashboard.xlsx`
- `exports/pairs_cointegration_analysis.xlsx`

## Skills

- Primary orchestration: `skills/nasdaq-correlation-ops/`
- Dashboard build/rebuild: `skills/dashboard-build/`
- Data refresh + pipeline: `skills/data-refresh/`
- Prior-run correlation deltas: `skills/correlation-delta-tracking/`
- Troubleshooting (focused): `skills/nasdaq-correlation-troubleshooting/`
- Troubleshooting (general): `skills/troubleshooting/`
- Visualization updates: `skills/visualization-update/`
- Chart polish: `skills/dashboard-chart-polish/`
- Pairs-trading cointegration: `skills/pairs-cointegration-ops/`

## Troubleshooting Log

Each material entry should record:

- source snapshot used
- provider or fallback behavior
- broken assumptions found
- durable troubleshooting changes that should persist

### 2026-03-10

- Replaced the earlier pinned top-five workflow with a live top-50 universe resolver.
- Official Nasdaq public data exposes membership but not a reliable public weight ranking, so the project now uses QQQM holdings as the preferred ranking proxy and Yahoo Finance market-cap data as the guarded fallback.
- `python` is still not available on PATH, but `py -3` is installed and usable as the launcher in this environment.
- Repaired the Python environment by installing the required packages and a valid `pyarrow` wheel, which restored `pandas`, `yfinance`, `streamlit`, and `openpyxl`.
- A full artifact refresh completed successfully against the official Nasdaq membership snapshot dated `2026-03-09`.
- The QQQM holdings ranking path still did not yield a usable public export in this environment, so the latest successful run used the Yahoo Finance market-cap fallback and recorded that provenance in metadata.
- `requirements.txt` now constrains `numpy` below `2.0` to avoid conflicts with older scientific packages already present on this machine.
- Streamlit required user-level `~/.streamlit/config.toml` and `credentials.toml` files to bypass the first-run onboarding prompt in this non-interactive shell; after that, the dashboard served successfully on `http://localhost:8501`.
- The dashboard heatmap layout was widened, the strongest and weakest pair tables were moved below the map, and widget/chart text was explicitly brightened to stay legible on the dark theme.
- `scripts/update_dashboard.py` now prompts for the price-history horizon on interactive runs so the visible research window can be chosen at refresh time.
- Added a dedicated pairs-trading cointegration workflow via `scripts/run_pairs_cointegration.py` and `skills/pairs-cointegration-ops/`, using Engle-Granger plus residual ADF filtering on local processed price data.
- Added `statsmodels` to the repo dependency baseline for cointegration, OLS hedge-ratio estimation, and ADF testing.
- The pairs workflow now supports its own configurable historical test window, independent of the broader refresh horizon, and persists csv/json artifacts for dashboard consumption.
- The Streamlit dashboard now includes a cointegration tab that surfaces the top 10 qualified pairs, the thresholds they met, and concise threshold definitions for faster research triage.
- Added advanced quant analytics modules: `analytics.py` (PCA, eigenvalue decomposition, Marchenko-Pastur threshold, rolling pairwise correlations, regime detection via k-means, correlation stability via Frobenius norm, absorption ratio), `clustering.py` (hierarchical ordering via Ward's method, sector ordering, dendrogram visualization), `visualizations.py` (scree plot, biplot, rolling correlation charts, absorption ratio chart, stability chart, regime timeline).
- Added `CLAUDE.md` as the authoritative Claude Code instruction file. `codex.md` remains the human-readable operating guide and troubleshooting log.
- Created four additional skill directories: `dashboard-build`, `data-refresh`, `troubleshooting`, `visualization-update` alongside the existing `nasdaq-correlation-ops`, `nasdaq-correlation-troubleshooting`, and `pairs-cointegration-ops`.
- Added `scikit-learn>=1.4.0` and `scipy>=1.12.0` to `requirements.txt` for PCA, clustering, and eigenvalue decomposition.

### 2026-03-16

- Expanded the Streamlit chart margins and axis-title standoffs so rolling-correlation and cointegration z-score plots no longer clip date labels or place `Correlation` or `Z-score` on top of the zero line.
- Added a Heatmap-tab ticker price-action panel above the correlation heatmap. It prefers yfinance OHLC candlesticks when available and falls back to the refreshed local adjusted-close price artifact otherwise.
- Brightened caption text and normalized section spacing so the dark-theme dashboard reads more cleanly for new users.
- Set the Heatmap historical-price panel to default to `QQQM`, renamed it from price action to historical price, and added quick lookbacks for `1y`, `6m`, `3m`, and `1w`.
- Clarified the rolling-average correlation title so it reads as a top-50 universe average instead of implying a single pair.
- Added `skills/dashboard-chart-polish/` and updated the related dashboard and visualization skills so future UI polish requests preserve these layout rules.

### 2026-03-23

- `scripts/update_dashboard.py` now snapshots the prior universe, correlation matrix, and metadata before writing fresh `latest_*` artifacts so the GUI can compare against the last successful refresh.
- The Rolling Research tab now includes an interactive prior-run correlation delta view with largest-move, increase, and decrease filters plus pair-level detail.
- Added `skills/correlation-delta-tracking/` so future work on prior-run snapshots and dashboard delta views follows the same artifact-driven pattern.
