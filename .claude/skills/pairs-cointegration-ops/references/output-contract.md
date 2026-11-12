# Output Contract

Use this reference when changing the ranking logic, qualification rules, or workbook layout.

## Qualification Rules

- Require `Engle-Granger p_value < 0.05`.
- Require `ADF stat < -2.86` on the residual spread.
- Reject pairs with overlap below the configured minimum observation count.
- Test both `y ~ x` and `x ~ y`, then keep the stronger direction.

## Ranking Rules

- Rank qualified pairs by a weighted score built from:
  - lower cointegration `p_value`
  - more negative ADF statistic
  - shorter positive half-life
  - larger absolute latest z-score
- Keep the ranking transparent in exported columns.

## Workbook Sheets

- `input_summary`
- `all_pairs_tested`
- `qualified_pairs`
- `pair_spreads`
- `parameters`
- `provenance`

## Dashboard Artifacts

- `data/processed/latest_pairs_cointegration_all.csv`
- `data/processed/latest_pairs_cointegration_qualified.csv`
- `data/processed/latest_pairs_cointegration_spreads.csv`
- `data/processed/latest_pairs_cointegration_metadata.json`

The dashboard should read these generated artifacts directly instead of parsing the Excel workbook.

## Required Pair Columns

- `ticker_y`
- `ticker_x`
- `sample_start`
- `sample_end`
- `n_obs`
- `hedge_ratio`
- `coint_stat`
- `coint_p_value`
- `adf_stat`
- `adf_p_value`
- `qualified_flag`
- `spread_mean`
- `spread_std`
- `latest_spread`
- `latest_zscore`
- `half_life`
- `rank`
- `ranking_score`
- `notes`
