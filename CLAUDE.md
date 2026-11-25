# CLAUDE.md — Authoritative Instructions for Claude Code

## Project Identity

**Name:** NASDAQ-100 Top-50 Correlation Dashboard
**Stack:** Python 3.11+ · Streamlit · Plotly · yfinance · requests · openpyxl · statsmodels
**Purpose:** Research-grade correlation analysis for the top 50 NASDAQ-100 constituents with explicit universe provenance, guarded fallback logic, rolling and prior-run correlation research, and Engle-Granger pairs cointegration.

## Current Operating Rules

- `config/dashboard_config.json` is the single source of truth for universe policy, analytics settings, paths, visuals, and pairs-trading config.
- Official Nasdaq public data (weighting endpoint) is the membership authority.
- QQQM holdings are the preferred public ranking proxy when Nasdaq does not expose a public weight rank.
- Yahoo Finance market-cap ranking is the guarded fallback when QQQM public holdings are unavailable.
- Returns and correlations are always computed locally from refreshed prices.
- `codex.md` is the active operating guide and troubleshooting log.
- `CLAUDE.md` (this file) is the authoritative instruction file for Claude Code.

## Architecture Rules

- **Config-driven:** All settings flow from `dashboard_config.json`.
- **Frozen dataclasses** for config wrappers (`DashboardConfig` in `settings.py`).
- **Provider abstraction:** Data sources are isolated in `sources.py` with fallback chain. Universe resolution is in `universe.py` with multi-source ranking.
- **Local computation only:** Returns, correlations, and cointegration tests are computed locally.
- **Metadata tracking:** Every artifact includes provenance metadata (source, timestamps, fallback reasons).
- **Defensive validation:** Fail fast on data quality issues (missing tickers, insufficient rows, excessive NaN ratio, insufficient ranked constituents).

## Code Conventions

- Every Python file starts with `from __future__ import annotations`.
- Use type hints everywhere. Prefer `list[str]` over `List[str]`, `dict[str, Any]` over `Dict[str, Any]`.
- Use `pathlib.Path` for all file operations.
- Use `frozen=True` on config-related dataclasses.
- Import heavy third-party libraries inside functions (e.g., `import yfinance as yf` inside fetch functions).
- Use relative imports inside the package. Exception: `dashboard.py` runs under Streamlit as a script and must keep absolute `nasdaq_correlation_dashboard.*` imports.
- Shared CLI helpers (history-period prompt) live in `cli.py`; do not re-implement them in scripts.

## Visual Identity

Values below are the defaults in `theme.py` (`TERMINAL_VISUAL_DEFAULTS`); `config/dashboard_config.json` → `visuals` overrides them at runtime.

| Element | Value |
|---------|-------|
| Heatmap min color (-1) | `#7D3A4A` (muted red) |
| Heatmap mid color (0) | `#DCE7F6` (pale neutral) |
| Heatmap max color (+1) | `#1C8BC4` (blue) |
| Background gradient | `#071222` → `#152B47` → `#030B15` (150°) |
| Panel background | `rgba(10, 22, 40, 0.78)` |
| Panel border | `rgba(122,157,205,0.34)` |
| Accents | cyan `#58C8FF`, secondary `#7BA9FF`, success `#22C55E`, danger `#FB7185` |
| Hero / heading font | Bebas Neue |
| UI / body font | Sora |
| Mono font (charts, tables) | JetBrains Mono |
| Text color | `#EAF2FF` primary, `#A4B8D7` muted |
| Header fill (Excel) | `#10243E` with white bold text |

These values must never be changed without explicit user approval.

## File Map

```
CLAUDE.md                          ← Authoritative Claude Code instructions (this file)
codex.md                           ← Human-readable operating guide + troubleshooting log
README.md / CONTRIBUTING.md / LICENSE (MIT)
.github/workflows/tests.yml        ← CI: offline tests on ubuntu + windows, Python 3.11/3.12
pyproject.toml                     ← Package metadata (src layout) + corrdash-* console scripts; requirements.txt mirrors deps
config/dashboard_config.json       ← Single source of truth for all settings

src/nasdaq_correlation_dashboard/
  settings.py                      ← DashboardConfig dataclass + load_config, project_root, default_config_path
  universe.py                      ← Live universe resolver (Nasdaq endpoint → QQQM → Yahoo Finance) + refresh_universe preview
  etf_universe.py                  ← ETF-holdings universe: parse issuer export, map to Yahoo symbols, derive per-ETF config
  sources.py                       ← Price data fetching (yfinance + CSV fallback)
  correlation.py                   ← Return/correlation computation, ranked_pairs, rolling avg corr, prior-run deltas
  pairs_cointegration.py           ← Engle-Granger cointegration analysis, spread z-scores, pairs workbook
  excel_export.py                  ← openpyxl workbook export with conditional formatting
  cli.py                           ← Shared history-period resolver for the pipeline scripts
  theme.py                         ← Theme tokens, Plotly palette, injected Streamlit CSS
  dashboard.py                     ← Streamlit multi-tab GUI (Heatmap, Rolling, Cointegration, Universe, Run Status)
  net.py                           ← configure_tls(): HTTPS behind proxies/antivirus (DASHBOARD_CA_BUNDLE, Windows store bundle)
  rerun_job.py                     ← Background re-run job for the dashboard (lock + status file + log)
  atomic_io.py                     ← Atomic CSV/JSON/workbook writes (temp file + os.replace)
  commands/                        ← Console-script implementations: update, etf, pairs, universe, app

scripts/                           ← Thin shims over nasdaq_correlation_dashboard.commands.* (no install needed)
  update_dashboard.py              ← Full pipeline orchestrator (universe → prices → correlation → pairs → export)
  run_pairs_cointegration.py       ← Standalone pairs cointegration run on local processed prices
  run_dashboard.py                 ← Streamlit launcher
  refresh_universe.py              ← Preview resolved universe (read-only)
  run_etf_correlation.py           ← Same pipeline on an ETF's top-N holdings by weight → data/etf/<ETF>/, exports/etf/<ETF>/

commands/
  update-dashboard.ps1             ← Windows PowerShell wrapper for update
  run-etf.ps1                      ← Prompt for an ETF + lookbacks, run on its holdings, open the dashboard
  open-dashboard.ps1               ← Windows PowerShell wrapper for dashboard launch
  *.sh (+ _python.sh)              ← macOS/Linux/Git Bash equivalents of the three .ps1 wrappers

.claude/skills/                    ← Project skills (canonical); skills/ is a junction to here for Codex
  nasdaq-correlation-ops/          ← Refresh pipeline, universe/price providers, artifact regeneration
  troubleshooting/                 ← Diagnostics: environment, providers, artifacts, failure playbook
  dashboard-ui/                    ← Streamlit tabs, Plotly charts, theme/CSS, chart-polish rules
  pairs-cointegration-ops/         ← Pairs trading cointegration workflow
  correlation-delta-tracking/      ← Prior-run snapshots and correlation-change views

tests/                             ← Offline unittest suite (py -3 -m unittest discover tests); __init__ blocks network
  fixture_artifacts.py             ← Builds a 5-ticker artifact set for the dashboard smoke test
  fixtures/holdings/               ← Invesco- and iShares-layout holdings fixtures
prompts/                           ← Prompt templates
docs/plans/                        ← Local planning notes (gitignored)
docs/presentations/                ← Slide decks (gitignored *.pptx)
docs/images/                       ← README screenshots
data/processed/                    ← Generated CSV/JSON artifacts
exports/                           ← Generated Excel workbooks
```

## Skill Index

| Skill | When to Use |
|-------|-------------|
| `nasdaq-correlation-ops` | Full refresh cycles, universe resolution, price providers, regenerating artifacts and workbooks |
| `troubleshooting` | Diagnose Python/dependency/provider/artifact/config failures and log fixes |
| `dashboard-ui` | Change tabs, Plotly figures, theme/CSS, axis spacing, the Heatmap price-action panel |
| `pairs-cointegration-ops` | Pairs trading cointegration workflow, Engle-Granger analysis, thresholds |
| `correlation-delta-tracking` | Prior-run vs current correlation snapshots and delta views |

## Guardrails

1. **Never change the universe or fallback order silently.** All changes must be logged in `codex.md`.
2. **Never accept a universe smaller than 50 names** for the NASDAQ-100 run. ETF-holdings runs (`run_etf_correlation.py`) take the top N holdings by fund weight (`etf_runs.default_top_n`, 50; `--top-n N|all` overrides), use every holding when the fund has fewer, and write to isolated paths.
3. **Never report success** unless universe CSV, correlation CSV, metadata JSON, and Excel workbook were produced.
4. **Keep the heatmap locked to `[-1, 1]` domain.** Never rescale or clip.
5. **Preserve the configured heatmap scale** (`heatmap_min/mid/max_color`, currently red → neutral → blue) unless the user explicitly asks for a change.
6. **Keep the heatmap visually dominant** — full width, pair tables below, top y-axis labels not clipped.
7. **Keep time-series axes readable** — use generous left and bottom margins plus axis-title standoffs so `Date`, `Correlation`, and `Z-score` titles stay clear of tick labels and zero lines.
8. **Keep the Heatmap historical-price panel alive** — place it above the heatmap, default it to `QQQM`, preserve quick lookback controls for `1y`, `6m`, `3m`, and `1w`, prefer yfinance OHLC candlesticks, and fall back to refreshed local adjusted-close data when OHLC is unavailable.
9. **Label rolling-average correlation charts clearly** as top-50 universe averages rather than single-pair diagnostics.
10. **Keep captions bright** on the dark theme.
11. **Record new failure modes** and durable fixes in `codex.md`.
12. **Keep the cointegration tab grounded in generated artifacts**, not workbook parsing or direct fetches.
13. **Show threshold definitions** in plain English on the cointegration tab.
14. **Commit as ArcadiaL00ts with the noreply email**; never use a personal name or email in this repo.

## Multi-Agent Dispatch Rules

When a task involves multiple independent sub-tasks, dispatch them as parallel sub-agents:

| Scenario | Parallel Agents |
|----------|----------------|
| Full refresh | Agent 1: resolve universe + fetch prices. Agent 2: check existing artifacts + verify config. |
| Post-fetch analytics | Agent 1: correlation matrix + pairs ranking. Agent 2: cointegration scan. |
| Export | Agent 1: Excel workbook. Agent 2: CSV/JSON artifacts. Agent 3: update codex.md. |
| Troubleshooting | Agent 1: check Python + dependencies. Agent 2: validate data files. Agent 3: verify config integrity. |

**Rule:** Only parallelize when tasks are truly independent.

## Commands Reference

After `pip install -e .` the `corrdash-*` console scripts work on any OS from any directory. Without an install, use the `scripts/*.py` shims; on Windows `python` may be the Microsoft Store stub, so use `py -3` (the wrappers prefer it).

| Command | Purpose |
|---------|---------|
| `corrdash-update --history-period 2y` / `corrdash-etf --etf TAN` / `corrdash-pairs` / `corrdash-universe` / `corrdash-app [--config ...] [--port N]` | Installed console scripts (same as the scripts below) |
| `commands/update-dashboard.ps1` / `.sh` | Refresh all data + analytics + exports (prompts for history horizon) |
| `commands/open-dashboard.ps1` | Launch the Streamlit dashboard |
| `py -3 scripts/update_dashboard.py` | Direct pipeline execution (interactive horizon prompt) |
| `py -3 scripts/update_dashboard.py --history-period 2y` | Pipeline with explicit history override |
| `py -3 scripts/run_pairs_cointegration.py` | Pairs cointegration only, on existing processed prices |
| `py -3 scripts/refresh_universe.py` | Preview resolved universe (read-only) |
| `py -3 scripts/run_etf_correlation.py --etf TAN` | Run on an ETF's holdings (needs `data/manual_universe/TAN_holdings.csv`) |
| `py -3 scripts/run_dashboard.py --config data/etf/TAN/config.json` | View an ETF run in the dashboard |
| `py -3 -m unittest discover tests` | Run the test suite |
| `streamlit run src/nasdaq_correlation_dashboard/dashboard.py` | Direct Streamlit launch |

## Expected Outputs

| Path | Description |
|------|-------------|
| `data/processed/latest_universe.csv` | Resolved top-50 universe with rank |
| `data/processed/latest_prices.csv` | Raw daily adjusted close prices |
| `data/processed/latest_returns.csv` | Computed log returns |
| `data/processed/latest_correlation.csv` | N×N Pearson correlation matrix |
| `data/processed/latest_metadata.json` | Full provenance metadata |
| `data/processed/previous_{universe,correlation,metadata}.*` | Prior-run snapshots for the delta view |
| `data/processed/latest_pairs_cointegration_all.csv` | All tested pair results |
| `data/processed/latest_pairs_cointegration_qualified.csv` | Pairs passing thresholds |
| `data/processed/latest_pairs_cointegration_spreads.csv` | Spread z-scores for top pairs |
| `data/processed/latest_pairs_cointegration_metadata.json` | Pairs analysis metadata |
| `exports/nasdaq_top50_correlation_dashboard.xlsx` | Main Excel workbook |
| `exports/pairs_cointegration_analysis.xlsx` | Pairs cointegration workbook |
