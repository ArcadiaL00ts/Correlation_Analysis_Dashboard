---
name: dashboard-ui
description: Change the Streamlit GUI or Plotly charts of the NASDAQ-100 correlation dashboard. Use when adding, removing, or restructuring tabs or views, editing the heatmap, rolling-correlation, spread or price-action charts, changing theme colors, fonts or CSS, fixing clipped axes or titles, normalizing section spacing, or making captions and helper text readable on the dark theme.
---

# Dashboard UI

## Where things live

- `src/nasdaq_correlation_dashboard/dashboard.py`: tabs (Heatmap, Rolling, Cointegration, Universe, Run Status) and the Plotly figure builders. It runs under Streamlit as a script, so it keeps absolute `nasdaq_correlation_dashboard.*` imports.
- `src/nasdaq_correlation_dashboard/theme.py`: `VISUAL_DEFAULTS` (design tokens), `resolve_theme_tokens`, `plotly_theme`, `hoverlabel`, `streamlit_theme_options` (the Streamlit base theme, also written to `.streamlit/config.toml` and passed as flags by `corrdash-app`), and `build_css` / `inject_styles`.
- `src/nasdaq_correlation_dashboard/emblems.py`: one hand-built SVG emblem per panel, `panel_head`, and `brand_mark` (a 5x5 tile of the live correlation matrix). Hover keyframes live in `build_css`.
- Wrap every section in `_panel(key, emblem, title, subtitle, tint)` in `dashboard.py`; it renders a keyed container (`st-key-panel_<key>`) that the CSS styles as the panel shell. Info cards use `_status_card` / `_definition_card`.
- `config/dashboard_config.json` → `visuals`: overrides the theme defaults. Config values win.
- Derived data (deltas, rolling averages, pair series) belongs in `correlation.py` or `pairs_cointegration.py`, not inline in the UI.

## Guardrails

1. Read `codex.md` before touching the UI.
2. **Heatmap:** keep it locked to the `[-1, 1]` domain; never rescale or clip. Its color scale comes from `heatmap_min_color` / `heatmap_mid_color` / `heatmap_max_color` in config. Do not change those colors or the domain without explicit user approval.
3. **Heatmap stays dominant:** full width, strongest/weakest pair tables below it, and the top y-axis label not clipped even with 50 tickers.
4. **Price-action panel:** above the heatmap, defaults to `QQQM`, quick lookbacks `1y`, `6m`, `3m`, `1w`. Prefer yfinance OHLC candlesticks and fall back to the refreshed local adjusted-close artifact.
5. **Time-series axes:** use generous left and bottom margins plus axis-title standoffs so `Date`, `Correlation` and `Z-score` titles stay clear of tick labels and zero lines.
6. **Rolling-average charts:** label them as top-50 universe averages, not single-pair diagnostics.
7. **Readability:** keep tab labels, slider and select labels, chart titles, captions and helper text bright on the dark background, and keep vertical spacing consistent between stacked blocks.
8. **Artifact-driven:** views read generated CSV/JSON artifacts, never the Excel workbook or live source fetches. The only exception is the price-action OHLC fetch, or when the user explicitly asks for live data.
9. **Cointegration tab:** read the `latest_pairs_cointegration_*` artifacts and show threshold definitions in plain English.
10. **Design system:** tokens only (no stray hex in components), sentence-case panel titles named after what the panel reveals, one-line subtitles, tooltips on every chart (`hoverlabel`), and emblem animations that play once on hover and settle. Respect `prefers-reduced-motion`. No em dashes in UI copy. Plotly hover formats must not use a `+` sign flag (plotly.js rejects it); pre-format signed values in Python. In `.streamlit/config.toml` the `font` must be a family name, never `name:url` (that makes Streamlit drop the whole theme).
11. Any change to the documented visual identity (colors, fonts, gradient) needs explicit user approval. Update the Visual Identity table in `CLAUDE.md` when it changes.

## Verify

- `py -3 -m compileall src`
- Launch with `commands/open-dashboard.ps1` (or `streamlit run src/nasdaq_correlation_dashboard/dashboard.py`) and click through every tab.
- Log material layout or chart-rule changes in `codex.md`.
