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
8. If source logic, workflow rules, or failure handling changes, update `prompts/nasdaq_correlation_dashboard_prompt.md` and the relevant skill files in `.claude/skills/` (also reachable as `skills/`, a directory junction).
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
- Preserve the configured heatmap mapping (`visuals.heatmap_min/mid/max_color`): currently `-1 #7D3A4A muted red`, `0 #DCE7F6 pale neutral`, `+1 #1C8BC4 blue`.
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

Canonical location is `.claude/skills/` (loaded by Claude Code). `skills/` is a directory junction to the same folder so Codex paths keep resolving; each skill keeps its `agents/openai.yaml`.

- Refresh pipeline, universe and price providers: `skills/nasdaq-correlation-ops/`
- Troubleshooting and failure playbook: `skills/troubleshooting/`
- Dashboard UI, charts, theme and chart polish: `skills/dashboard-ui/`
- Pairs-trading cointegration: `skills/pairs-cointegration-ops/`
- Prior-run correlation deltas: `skills/correlation-delta-tracking/`

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

### 2026-11-13 — Repository reorganization

Recovery point: git commit `a5e03e2` ("Baseline before reorg") holds the full pre-reorg tree. Restore any file with `git checkout a5e03e2 -- <path>`. No universe policy, fallback order, analytics output or visual value was changed.

- **Version control:** initialized git. `*.pptx`, `.claude/settings.local.json` and the `skills/` junction are gitignored; `data/processed/` and `exports/` already were.
- **Root cleanup:** `Correlation_Dashboard.pptx` → `docs/presentations/`; `Pinescript/` → `tradingview/pinescript/` (unchanged, not used by the dashboard); deleted the empty `Claude_Version/`.
- **Removed unused modules:** `analytics.py`, `clustering.py` and `visualizations.py` (PCA, eigenvalues, regime detection, absorption ratio, dendrograms; see the 2026-03-10 entry). Nothing imported them, their config keys never existed in `dashboard_config.json`, and `visualizations.py` imported a `sector_colors()` that `universe.py` never defined, so it could not even be imported. Dropped `scikit-learn` and the explicit `scipy` pin from `requirements.txt`; `scipy` still installs as a `statsmodels` dependency.
- **Code tidy-ups (no behaviour change):**
  - New `cli.py` holds the single `resolve_history_period()` that `update_dashboard.py` (price horizon + cointegration window) and `run_pairs_cointegration.py` now share; three copies were removed. Error messages now read `Unsupported <label> '<value>'`.
  - `universe_fetcher.py` folded into `universe.py` as `refresh_universe()`; the always-empty `diff`/`applied`/`warning`/`dry_run` fields were dropped.
  - Theme tokens, Plotly palette and the ~380-line injected CSS moved from `dashboard.py` into `theme.py` (`TERMINAL_VISUAL_DEFAULTS`, `resolve_theme_tokens`, `resolve_visual_float`, `plotly_theme`, `inject_styles`). `dashboard.py` went from 1465 to ~1000 lines.
  - `excel_export.py` now uses relative imports. `dashboard.py` keeps absolute imports because Streamlit runs it as a script.
  - Added a minimal `pyproject.toml` (src layout). `requirements.txt`, the scripts' `sys.path` bootstrap and `commands/*.ps1` are unchanged, so no reinstall is needed.
- **Skills 9 → 5, now in `.claude/skills/`:** `nasdaq-correlation-ops` absorbed `data-refresh`; `troubleshooting` absorbed `nasdaq-correlation-troubleshooting` (kept `references/failure-playbook.md`); new `dashboard-ui` merged `dashboard-build`, `visualization-update` and `dashboard-chart-polish`. `pairs-cointegration-ops` and `correlation-delta-tracking` were kept, with their descriptions rewritten for Claude Code triggering.
- **Doc drift fixed:** CLAUDE.md's Visual Identity table and the heatmap guardrail described an older palette (`#570B12`/`#E7D9C8`/`#0D8F61`, Cormorant Garamond/IBM Plex Sans). They now document the values that actually render (`#7D3A4A`/`#DCE7F6`/`#1C8BC4`, Bebas Neue/Sora/JetBrains Mono). Only the docs changed, not the rendered colours. The File Map, Skill Index and Commands now match the tree.
- `resolve_visual_float()` (moved into `theme.py`) has no callers. It was left in place, flagged as a candidate for removal.
- **Verification:** package imports, `compileall`, `unittest` (2/2), the `--help` output of both pipeline scripts, and a headless Streamlit `AppTest` of `dashboard.py` all passed (5 tabs, 0 exceptions). The moved theme/CSS code was checked byte-for-byte against `a5e03e2`, allowing only for the renames.
- **New failure mode, unresolved: HTTPS fails machine-wide.** Every `requests` call (Nasdaq and Google alike) raises `SSLCertVerificationError: unable to get local issuer certificate`, inside and outside the Claude Code sandbox. Effects: `scripts/refresh_universe.py` and a full refresh cannot run, and the Heatmap QQQM OHLC fetch fails (the panel falls back to local prices as designed). It is environmental, not caused by the reorg; installed `certifi` is `2024.02.02`. Next steps: `py -3 -m pip install --upgrade certifi`; if that is not enough, check for antivirus/proxy HTTPS inspection and install `pip-system-certs` so Python trusts the Windows certificate store.
