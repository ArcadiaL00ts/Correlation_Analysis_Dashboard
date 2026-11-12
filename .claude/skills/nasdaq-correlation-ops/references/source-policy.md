# Source Policy

## Universe Selection

- Prefer the official Nasdaq NDX weighting endpoint and related public NDX materials for membership resolution.
- Record the official trade date used for the membership snapshot in metadata.
- Resolve exactly 50 names for the dashboard universe.
- Treat the public top-50 ranking as a proxy workflow:
  - First choice: QQQM holdings export.
  - Second choice: Yahoo Finance market-cap ranking across the official member set.

## Price History

- Default implementation uses `yfinance` adjusted close daily history because it is practical and already aligned with the current repo.
- Keep the provider adapter isolated so a licensed provider can replace it later without changing dashboard logic.
- Preserve a `csv_directory` fallback for manual or licensed data drops.

## Validation

- Require the configured minimum number of rows.
- Reject outputs with excessive missingness.
- Surface provider failures and ranking fallbacks in metadata instead of swallowing them.
