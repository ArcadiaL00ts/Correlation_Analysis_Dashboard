# NASDAQ-100 Top-50 Correlation Dashboard Prompt

Use this prompt when you want Codex to refresh, troubleshoot, or extend the dashboard in a disciplined way.

## Mission

Build or update a research-grade correlation dashboard for the top 50 stocks in the NASDAQ-100. The implementation must include:

- A premium Streamlit GUI with a static correlation heatmap, rolling correlation research views, pair diagnostics, provenance panels, and run-status visibility.
- A cointegration research tab that surfaces the top qualified pairs for market-neutral ideas, the thresholds they passed, and short plain-English threshold definitions.
- A dominant full-width heatmap layout with strongest and weakest pair tables placed underneath it in side-by-side panels.
- A generated Excel workbook with universe, prices, returns, correlation matrix, and metadata.
- Generated cointegration csv/json artifacts plus a ranked Excel workbook for pairs trading.
- Guardrails for incomplete universe resolution, stale ranking proxies, missing price history, and missing artifacts.
- A maintained `codex.md` file that records workflow rules and troubleshooting resolutions.
- Skill updates when the workflow or failure handling changes.

## Operating Constraints

- Treat official Nasdaq public NDX data as the authority for index membership.
- Resolve the official member set from the Nasdaq weighting endpoint instead of a pinned static snapshot.
- If public Nasdaq weight ranking is unavailable, use QQQM holdings as the preferred ranking proxy for the top-50 cut.
- If QQQM public holdings are unavailable, use Yahoo Finance market-cap ranking across the official membership list and record the fallback reason.
- Recompute returns and correlations locally instead of trusting precomputed correlation values from any external source.
- Prefer adjusted close daily prices unless the user explicitly requests another field.
- Prompt for the price-history horizon during interactive refresh runs so the analysis window can be chosen at update time.
- Prompt separately for the cointegration analysis window during interactive refresh runs unless the caller provides an explicit override.
- Structure the work as parallel workstreams when practical:
  - source and universe validation
  - price acquisition and guardrails
  - analytics and export generation
  - GUI polish, docs, and skills

## Required Workflow

1. Inspect the existing repo before making assumptions.
2. Read `codex.md` and keep its guardrails in force.
3. Resolve the official NASDAQ-100 membership from the configured Nasdaq endpoint.
4. Rank the universe for a top-50 cut using the configured fallback order and record exact provenance.
5. Fail fast if fewer than 50 ranked constituents can be resolved.
6. Refresh daily price history for the resolved 50 tickers.
7. Fail fast if any ticker is missing, if the row count is too short, or if missingness exceeds the configured threshold.
8. Compute daily returns and a Pearson correlation matrix locally.
9. Support rolling research views for multiple configured windows.
10. Prompt for the history horizon during interactive refresh runs unless the caller provided an explicit override.
11. Prompt for the cointegration analysis window during interactive refresh runs unless the caller provided an explicit override.
12. Export csv artifacts and an Excel workbook.
13. Export cointegration artifacts for the dashboard and the pairs workbook.
14. Ensure the dashboard heatmap honors the full `[-1, 1]` range with the required red-to-green gradient.
15. Ensure top heatmap tick labels remain visible and that tab labels, slider labels, select-box labels, and chart titles remain legible on the dark theme.
16. Keep the cointegration tab grounded in generated artifacts rather than workbook parsing from the UI.
17. If an error occurs, fix it when possible and append a short troubleshooting entry to `codex.md`.
18. In the final response, summarize what changed, what was verified, and what still needs user action.

## Config Contract

- Expose a `universe_policy` with:
  - `universe_size = 50`
  - `selection_mode = latest_weight_rank`
  - official Nasdaq membership source settings
  - QQQM ranking proxy settings
  - Yahoo Finance market-cap fallback settings
- Expose a `price_source` priority list or equivalent fallback contract.
- Expose validation thresholds for minimum rows, maximum missingness, and minimum ranked constituents.
- Expose rolling-window settings for the dashboard research views.
- Expose pairs-trading settings including the cointegration analysis window and qualification thresholds.
- Expose visual theme settings for the Streamlit app.

## Metadata Contract

- Record the resolved top-50 universe as named records, not only ticker symbols.
- Record the official source type, URL, trade date, and observed member count.
- Record the ranking source type, URL, fallback-used flag, fallback reason, and ranking attempts.
- Record provider warnings or provider errors when a fallback path is used.
- Record the run timestamp, analytics window coverage, and output artifact paths.
- Record the cointegration analysis window, qualified-pair count, and threshold configuration in the pair-analysis metadata.

## Guardrails

- Do not silently swap the universe authority away from official Nasdaq membership.
- Do not claim an official weight-ranked top 50 if the public Nasdaq source did not expose that ranking.
- Do not suppress provider failures without recording which fallback path was used.
- Do not report success if the universe csv, correlation csv, metadata json, or Excel workbook were not actually produced.
- Do not report success if the cointegration csv/json artifacts or pairs workbook were not actually produced.
- If Python, Streamlit, or package dependencies are missing, state that clearly and document the setup gap in `codex.md`.
- If a new failure mode appears repeatedly, update the troubleshooting skill instead of burying the fix in one-off notes.

## Advanced Analytics

When configured, the pipeline should also produce:

- **Eigenvalue decomposition** of the correlation matrix with Marchenko-Pastur threshold for random matrix comparison.
- **PCA factor loadings** (top N components) with explained variance ratios and a PC1 vs PC2 biplot colored by sector.
- **Rolling pairwise correlations** for the top correlated and most anti-correlated pairs across multiple windows.
- **Regime detection** via k-means clustering on rolling first-PC volatility (low-vol, normal, high-vol regimes).
- **Correlation stability** measured by Frobenius norm distance between consecutive rolling correlation matrices.
- **Absorption ratio** — rolling fraction of total variance explained by top eigenvalues (systemic risk indicator).

Analytics modules: `analytics.py` for computations, `clustering.py` for hierarchical/sector ordering, `visualizations.py` for Plotly figure builders.

## Required Deliverables

- Updated Python source files
- Updated dynamic universe-resolution logic
- Updated Excel export workflow
- Updated `codex.md`
- Updated skill files
- Updated prompt file
- Stable output artifacts:
  - processed prices
  - processed returns
  - correlation matrix
  - metadata JSON with source lineage
  - Excel workbook
  - cointegration csv/json artifacts
  - pairs cointegration workbook
  - analytics data (PCA loadings, eigenvalues, regime labels)
  - dashboard app view
- Short summary of assumptions and unresolved risks

## Test Expectations

- Verify official Nasdaq membership resolution and guarded fallback ranking behavior.
- Verify the resolved universe contains exactly 50 names with preserved rank order.
- Verify price validation rejects missing tickers, short history, and excessive missingness.
- Verify correlations are recomputed locally and the heatmap remains locked to `[-1, 1]`.
- Verify repeated refreshes overwrite artifacts cleanly and update provenance timestamps.
- Verify the dashboard surfaces fallback warnings and metadata without manual edits.
