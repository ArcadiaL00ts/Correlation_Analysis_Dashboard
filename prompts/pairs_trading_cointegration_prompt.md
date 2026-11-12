# Pairs Trading Cointegration Skill Prompt

Use this prompt when you want Codex to create or update a reusable skill and analysis workflow for market-neutral pairs trading based on cointegration tests.

## Mission

Build a repo-native skill and supporting code that:

- reads locally available pairs or price data from this workspace first
- identifies cointegrated equity pairs for a market-neutral strategy
- confirms pair eligibility with both Engle-Granger cointegration and an explicit ADF test on the residual spread
- computes hedge ratios, spreads, z-scores, and pair-level diagnostics
- exports a ranked Excel workbook of all tested pairs and the subset that passes the cointegration filters

## Repo Context

- Treat `data/processed/latest_prices.csv` as the default primary input unless the user points to another local dataset.
- The current default price file is a wide daily-price table with `Date` as the first column and ticker columns after it.
- Use `data/processed/latest_universe.csv` and `data/processed/latest_metadata.json` when helpful for universe context and provenance.
- Write final Excel outputs to `exports/`.
- Keep workflow notes and durable troubleshooting guidance in `codex.md` if the process or environment changes materially.

## Core Objective

Create a skill, scripts, and any supporting references needed to scan the local universe for statistically cointegrated pairs suitable for a market-neutral pairs-trading workflow.

The implementation must:

- test every valid pair combination in the selected universe unless the user sets a narrower list
- align both price series on common dates and reject pairs with insufficient overlap
- use price levels, not returns, for cointegration testing
- estimate the hedge ratio with OLS so spread can be defined as `spread = y - beta * x`
- calculate spread z-scores for each qualifying pair
- rank qualifying pairs in a defensible way for research triage

## Statistical Rules

- Use Engle-Granger cointegration testing via `statsmodels` as the primary test.
- Also run an explicit ADF test on the residual spread.
- Mark a pair as qualified only if:
  - Engle-Granger cointegration `p_value < 0.05`
  - ADF test statistic on the spread is `< -2.86`
- Record the full test output even for rejected pairs.
- Because Engle-Granger is direction-sensitive, test both `y ~ x` and `x ~ y` when practical, then keep the orientation with the stronger cointegration evidence.
- Require a configurable minimum overlap window, with `252` trading days as the default floor.
- Use adjusted close prices when the source provides them.

## Spread And Signal Rules

- Compute hedge ratio with OLS on aligned price levels.
- Define residual spread as `spread = y - beta * x`.
- Compute at least:
  - full-sample spread mean
  - full-sample spread standard deviation
  - latest spread value
  - latest z-score
- Prefer also computing:
  - rolling z-score with a configurable lookback
  - spread half-life estimate for mean reversion
  - zero-crossing count or another simple mean-reversion stability metric
- Fail fast when spread standard deviation is zero or the spread series is too short for robust testing.

## Ranking Contract

Rank qualified pairs primarily by statistical quality and tradability, not by raw correlation alone.

Default ranking priority:

1. lower Engle-Granger `p_value`
2. more negative ADF statistic
3. shorter positive half-life, when available
4. larger absolute latest z-score, when the user wants current opportunity ranking

Include a transparent ranking score or ranking columns in the export so the ordering can be audited.

## Output Contract

Produce an Excel workbook such as `exports/pairs_cointegration_analysis.xlsx` with clearly separated sheets, for example:

- `input_summary`
- `all_pairs_tested`
- `qualified_pairs`
- `pair_spreads`
- `parameters`
- `provenance`

At minimum, export these columns for each tested pair:

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
- `critical_value_1pct`
- `critical_value_5pct`
- `critical_value_10pct`
- `qualified_flag`
- `spread_mean`
- `spread_std`
- `latest_spread`
- `latest_zscore`
- `half_life`
- `rank`
- `ranking_score`
- `notes`

If practical, include a sheet with the historical spread and z-score time series for the top-ranked pairs.

## Package Guidance

Choose the smallest package set that materially improves reliability for this task.

Preferred packages:

- `statsmodels`: required for Engle-Granger cointegration, OLS, and ADF testing
- `XlsxWriter` or `openpyxl`: for structured Excel export
- `pandas`, `numpy`, `scipy`: use the existing stack for wrangling and numerical work

Optional packages only if justified by the implementation:

- `arch`: for additional unit-root or residual diagnostics beyond the baseline requirement
- `joblib`: for parallel pair testing if runtime becomes material

Do not add large backtesting frameworks unless they are clearly needed for the current deliverable.

## Skill Creation Requirements

- Create a dedicated skill for this workflow, for example `pairs-cointegration-ops`.
- Follow the local skill-creation conventions in this repo.
- Keep `SKILL.md` concise and push detailed formulas, assumptions, or schema notes into `references/` only if needed.
- Add scripts when deterministic reuse is valuable, especially for:
  - pair enumeration
  - cointegration and ADF testing
  - spread and z-score generation
  - Excel export
- Validate the created skill after implementation.

## Guardrails

- Do not use returns for cointegration tests.
- Do not mark a pair as qualified unless both the `p_value` and ADF-stat thresholds pass.
- Do not hide failed pairs; export rejected-pair diagnostics too.
- Do not rank pairs solely by Pearson correlation.
- Do not assume the local input schema; inspect it first and document any inferred mapping.
- Do not silently install extra packages without recording what was added and why.

## Expected Workflow

1. Inspect the repo and current data files before coding.
2. Read `codex.md`.
3. Inspect the local price data schema and determine the analysis universe.
4. Identify the minimal missing packages and install only the justified ones.
5. Create the skill scaffold and supporting scripts.
6. Run pairwise cointegration testing across the selected universe.
7. Compute spreads and z-scores for qualified pairs.
8. Export the ranked Excel workbook.
9. Validate the skill and sanity-check the output workbook.
10. Summarize what changed, which packages were installed, what was tested, and any remaining assumptions.

## Final Response Requirements

In the final response:

- state the exact input file used
- state the exact output workbook path
- list installed packages and versions
- summarize how many pairs were tested and how many qualified
- name the top-ranked cointegrated pairs
- call out any caveats about sample size, missing data, or test sensitivity
