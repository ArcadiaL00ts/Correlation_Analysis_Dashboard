# CLAUDE.md — Authoritative Instructions for Claude Code

## Project Identity

**Name:** NASDAQ-100 Top-50 Correlation Dashboard
**Stack:** Python 3.11+ · Streamlit · Plotly · yfinance · requests · openpyxl · scikit-learn · scipy · statsmodels
**Purpose:** Research-grade correlation analysis for the top 50 NASDAQ-100 constituents with explicit universe provenance, guarded fallback logic, cointegration research, and advanced quant analytics (PCA, eigenvalues, regime detection, rolling correlations, absorption ratio).

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
- **Local computation only:** Returns, correlations, PCA, and cointegration tests are computed locally.
- **Metadata tracking:** Every artifact includes provenance metadata (source, timestamps, fallback reasons).
- **Defensive validation:** Fail fast on data quality issues (missing tickers, insufficient rows, excessive NaN ratio, insufficient ranked constituents).

## Code Conventions

- Every Python file starts with `from __future__ import annotations`.
- Use type hints everywhere. Prefer `list[str]` over `List[str]`, `dict[str, Any]` over `Dict[str, Any]`.
- Use `pathlib.Path` for all file operations.
- Use `frozen=True` on config-related dataclasses.
- Import heavy third-party libraries inside functions (e.g., `import yfinance as yf` inside fetch functions).

## Visual Identity

| Element | Value |
|---------|-------|
| Heatmap min color (-1) | `#570B12` (dark red) |
| Heatmap mid color (0) | `#E7D9C8` (warm neutral) |
| Heatmap max color (+1) | `#0D8F61` (green) |
| Background gradient | `#09111C` → `#132739` → `#071019` |
| Panel border | `rgba(255,255,255,0.10)` |
| Heading font | Cormorant Garamond, serif |
| Body font | IBM Plex Sans, sans-serif |
| Text color | `#F7F1E8` (warm off-white) |
| Header fill (Excel) | `#10243E` with white bold text |

These values must never be changed without explicit user approval.

## File Map

```
CLAUDE.md                          ← Authoritative Claude Code instructions (this file)
codex.md                           ← Human-readable operating guide + troubleshooting log
config/dashboard_config.json       ← Single source of truth for all settings

src/nasdaq_correlation_dashboard/
  settings.py                      ← DashboardConfig dataclass
  universe.py                      ← Live universe resolver (Nasdaq endpoint → QQQM → Yahoo Finance)
  universe_fetcher.py              ← Supplemental QQQM holdings fetcher for preview/refresh
  sources.py                       ← Price data fetching (yfinance + CSV fallback)
  correlation.py                   ← Return/correlation computation, ranked_pairs, rolling avg corr
  analytics.py                     ← PCA, eigenvalues, rolling pairwise correlations, regime detection,
                                     correlation stability, absorption ratio
  clustering.py                    ← Hierarchical/sector ordering, dendrogram building
  visualizations.py                ← Plotly figure builders (heatmap, scree, biplot, rolling, regimes)
  pairs_cointegration.py           ← Engle-Granger cointegration analysis, spread z-scores
  dashboard.py                     ← Streamlit multi-tab GUI (Heatmap, Rolling, Cointegration, Universe, Run Status)
  excel_export.py                  ← openpyxl workbook export with conditional formatting

scripts/
  update_dashboard.py              ← Full pipeline orchestrator (universe → prices → correlation → pairs → export)
  run_dashboard.py                 ← Streamlit launcher
  refresh_universe.py              ← Preview resolved universe (read-only)

commands/
  update-dashboard.ps1             ← Windows PowerShell wrapper for update
  open-dashboard.ps1               ← Windows PowerShell wrapper for dashboard launch

skills/
  nasdaq-correlation-ops/          ← General dashboard maintenance and orchestration
  dashboard-build/                 ← GUI layout, tabs, CSS styling
  dashboard-chart-polish/          ← Axis spacing, anti-clipping rules, heatmap price-action panel
  data-refresh/                    ← Price fetching, universe resolution, pipeline issues
  troubleshooting/                 ← Diagnostics: Python, deps, data files, config
  visualization-update/            ← Chart modifications, Plotly figures, color schemes
  nasdaq-correlation-troubleshooting/ ← Focused troubleshooting skill
  pairs-cointegration-ops/         ← Pairs trading cointegration workflow

prompts/                           ← Prompt templates
data/processed/                    ← Generated CSV/JSON artifacts
exports/                           ← Generated Excel workbooks
```

## Skill Index

| Skill | When to Use |
|-------|-------------|
| `nasdaq-correlation-ops` | General dashboard maintenance, full refresh cycles, coordinating across sub-skills |
| `dashboard-build` | Build or rebuild the Streamlit GUI, modify tab layout, update CSS |
| `dashboard-chart-polish` | Fix clipped Plotly axes, normalize section spacing, brighten helper text, or maintain the Heatmap price-action chart |
| `data-refresh` | Refresh price data, resolve universe, recompute analytics, troubleshoot providers |
| `troubleshooting` | Diagnose Python/dependency/data/config issues, validate artifacts |
| `visualization-update` | Modify charts, add plot types, change color schemes, update Plotly figures |
| `nasdaq-correlation-troubleshooting` | Focused troubleshooting for specific failure modes |
| `pairs-cointegration-ops` | Pairs trading cointegration workflow, Engle-Granger analysis |

## Guardrails

1. **Never change the universe or fallback order silently.** All changes must be logged in `codex.md`.
2. **Never accept a universe smaller than 50 names.**
3. **Never report success** unless universe CSV, correlation CSV, metadata JSON, and Excel workbook were produced.
4. **Keep the heatmap locked to `[-1, 1]` domain.** Never rescale or clip.
5. **Preserve the red-neutral-green heatmap scale** unless the user explicitly asks for a change.
6. **Keep the heatmap visually dominant** — full width, pair tables below, top y-axis labels not clipped.
7. **Keep time-series axes readable** — use generous left and bottom margins plus axis-title standoffs so `Date`, `Correlation`, and `Z-score` titles stay clear of tick labels and zero lines.
8. **Keep the Heatmap historical-price panel alive** — place it above the heatmap, default it to `QQQM`, preserve quick lookback controls for `1y`, `6m`, `3m`, and `1w`, prefer yfinance OHLC candlesticks, and fall back to refreshed local adjusted-close data when OHLC is unavailable.
9. **Label rolling-average correlation charts clearly** as top-50 universe averages rather than single-pair diagnostics.
10. **Keep captions bright** on the dark theme.
11. **Record new failure modes** and durable fixes in `codex.md`.
12. **Keep the cointegration tab grounded in generated artifacts**, not workbook parsing or direct fetches.
13. **Show threshold definitions** in plain English on the cointegration tab.

## Multi-Agent Dispatch Rules

When a task involves multiple independent sub-tasks, dispatch them as parallel sub-agents:

| Scenario | Parallel Agents |
|----------|----------------|
| Full refresh | Agent 1: resolve universe + fetch prices. Agent 2: check existing artifacts + verify config. |
| Post-fetch analytics | Agent 1: correlation matrix + pairs. Agent 2: PCA/eigenvalues. Agent 3: rolling correlations + regimes. |
| Export | Agent 1: Excel workbook. Agent 2: CSV/JSON artifacts. Agent 3: update codex.md. |
| Troubleshooting | Agent 1: check Python + dependencies. Agent 2: validate data files. Agent 3: verify config integrity. |

**Rule:** Only parallelize when tasks are truly independent.

## Commands Reference

| Command | Purpose |
|---------|---------|
| `commands/update-dashboard.ps1` | Refresh all data + analytics + exports (prompts for history horizon) |
| `commands/open-dashboard.ps1` | Launch the Streamlit dashboard |
| `python scripts/update_dashboard.py` | Direct pipeline execution (interactive horizon prompt) |
| `python scripts/update_dashboard.py --history-period 2y` | Pipeline with explicit history override |
| `python scripts/refresh_universe.py` | Preview resolved universe (read-only) |
| `streamlit run src/nasdaq_correlation_dashboard/dashboard.py` | Direct Streamlit launch |

## Expected Outputs

| Path | Description |
|------|-------------|
| `data/processed/latest_universe.csv` | Resolved top-50 universe with rank |
| `data/processed/latest_prices.csv` | Raw daily adjusted close prices |
| `data/processed/latest_returns.csv` | Computed log returns |
| `data/processed/latest_correlation.csv` | N×N Pearson correlation matrix |
| `data/processed/latest_metadata.json` | Full provenance metadata |
| `data/processed/latest_pairs_cointegration_all.csv` | All tested pair results |
| `data/processed/latest_pairs_cointegration_qualified.csv` | Pairs passing thresholds |
| `data/processed/latest_pairs_cointegration_spreads.csv` | Spread z-scores for top pairs |
| `data/processed/latest_pairs_cointegration_metadata.json` | Pairs analysis metadata |
| `exports/nasdaq_top50_correlation_dashboard.xlsx` | Main Excel workbook |
| `exports/pairs_cointegration_analysis.xlsx` | Pairs cointegration workbook |
