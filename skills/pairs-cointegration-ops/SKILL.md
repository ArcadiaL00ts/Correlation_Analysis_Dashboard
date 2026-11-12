---
name: pairs-cointegration-ops
description: Create, run, or update the repo's market-neutral pairs-trading cointegration workflow. Use when Codex needs to scan local equity price data for cointegrated pairs, run Engle-Granger and residual ADF tests, compute hedge ratios and spread z-scores, rank qualified pairs, install the minimal quant dependencies, or export the ranked Excel workbook.
---

# Pairs Cointegration Ops

## Overview

Use the local processed price data to find statistically cointegrated equity pairs and export a ranked workbook for market-neutral research. Keep the workflow reproducible through the repo runner script instead of ad hoc notebooks.

## Workflow

1. Read `codex.md` before changing the workflow.
2. Inspect `data/processed/latest_prices.csv` first unless the user explicitly points to another local file.
3. Use `data/processed/latest_universe.csv` when you need the intended ticker universe or display order.
4. Ensure `statsmodels` is installed before running the analysis. Reuse the existing `openpyxl`, `pandas`, `numpy`, and `scipy` packages unless there is a clear gap.
5. Treat the cointegration history window as configurable. Use the `pairs_trading.history_period` setting by default and allow explicit CLI overrides when the user wants a different test horizon.
6. Run `scripts/run_pairs_cointegration.py` for the actual analysis and workbook export.
7. Export rejected pairs as well as qualified pairs; do not hide failed diagnostics.
8. Write machine-readable CSV and JSON artifacts for the dashboard tab in addition to the Excel workbook.
9. Update `codex.md` if the workflow, package baseline, or durable failure handling changes.

## Statistical Rules

- Use Engle-Granger cointegration plus an explicit ADF test on the residual spread.
- Qualify a pair only when both conditions pass:
  - cointegration `p_value < 0.05`
  - ADF test statistic `< -2.86`
- Test both orientations of the pair and keep the stronger direction.
- Use price levels, not returns, for the cointegration tests.
- Compute hedge ratio with OLS and export spread diagnostics including the latest z-score.

## Commands

Use the default processed dataset:

```powershell
py -3 scripts/run_pairs_cointegration.py
```

Override the cointegration test window:

```powershell
py -3 scripts/run_pairs_cointegration.py --history-period 6mo
```

Analyze a subset:

```powershell
py -3 scripts/run_pairs_cointegration.py --tickers AAPL,MSFT,NVDA,AMD
```

Override the input or output paths:

```powershell
py -3 scripts/run_pairs_cointegration.py --prices data/processed/latest_prices.csv --output exports/pairs_cointegration_analysis.xlsx
```

Read [references/output-contract.md](references/output-contract.md) when you need to change qualification thresholds, ranking rules, or workbook sheets.
