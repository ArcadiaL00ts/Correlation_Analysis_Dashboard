# ETF Holdings Runs

Run the same correlation + cointegration pipeline on any ETF's holdings (e.g. TAN), sized to however
many holdings the fund has. Outputs are isolated: `data/etf/<ETF>/` and `exports/etf/<ETF>/`.
The NASDAQ-100 `latest_*` artifacts and the 50-name guardrail are untouched.

```
py -3 scripts/run_etf_correlation.py --etf TAN [--holdings <file>] [--history-period 2y] [--pairs-history-period 1y]
py -3 scripts/run_dashboard.py --config data/etf/TAN/config.json
```

`commands/run-etf.ps1` asks for the ticker, then (via the script) the price-history and cointegration
lookbacks, before any fetch. Short windows are fine: row minimums scale to the lookback. Once the dashboard
is open, the **Lookback** expander under the title re-runs the pipeline with new windows in place.

## Everything adapts to N holdings

- Universe = every equity holding that Yahoo can price (cash, money-market, currency lines skipped).
  Unpriceable names are dropped and listed in metadata (`ranking.dropped_unpriced`), never silently.
- Correlation matrix is N×N; cointegration tests all C(N,2) pairs; heatmap height scales with N.
- Dashboard titles read "<ETF> ETF holdings (N names)" and the price panel defaults to the ETF itself
  (`universe_policy.benchmark_ticker`) instead of QQQM.
- Mixed exchanges: gaps up to 3 days are forward-filled so foreign holidays line up with US days;
  history starts on the first date every name trades.

## Getting the holdings file (adaptive — check in this order)

1. **File already present:** `data/manual_universe/<ETF>_holdings.csv` (or any path the user gives).
   CSV/XLSX issuer exports are parsed directly; preamble rows and `#` comment lines are skipped.
2. **Issuer download via script:** if it redirects to a generic page or returns HTML, stop. Do not
   spoof headers or otherwise get around the block.
3. **Browser, if the user has Claude in Chrome connected:** call `list_connected_browsers`. Don't assume
   which Chrome install, drive or profile the user has; an installed extension that isn't signed into the
   same claude.ai account shows up as an empty list. If connected: open the issuer's holdings page in a new tab,
   expand the full table (e.g. Invesco "View all" opens a dialog), read it with `read_page` on the table
   region, and close the tab. Reading the table avoids a file download. Clicking "Export data" is a
   download and needs the user's OK.
4. **Otherwise** ask the user to connect the extension or save the export to the path in (1).

Write the CSV with a `Ticker` column holding **Yahoo symbols**, plus `Source Ticker`, `Name`, `Weight`
(percent), `CUSIP`, `Date` (holdings as-of). Rows with a blank issuer ticker (ADRs often) need the US
symbol filled in by name (e.g. Daqo → DQ, T1 Energy → TE).

## Local ticker → Yahoo symbol

The CUSIP/ISIN prefix gives the country: M=Israel `.TA`, G=Cayman/Bermuda (usually `.HK`), E=Spain `.MC`,
D=Germany `.DE`, R=Norway `.OL`, J=Japan `.T`; Y=Asia (ambiguous, check the name: Taiwan `.TW` for
TWSE or `.TWO` for TPEx, Korea `.KS`, Thailand `.BK`, HK `.HK`). Hong Kong codes are zero-padded to 4
digits (`968` → `0968.HK`). Turkey `.IS`. Thai `-R` NVDR lines map to the base `.BK` symbol.
If parsing an issuer file with ISINs, `etf_universe.ISIN_YAHOO_SUFFIX` applies this automatically;
override any symbol with `--ticker-map "LOCAL=YAHOO,..."`.

## Interpretation caveats to report

- Thin or foreign-holiday trading shows up as zero returns (check `(returns == 0).mean()`); these
  names show lower correlations with US names.
- A near-stationary, range-bound price (e.g. BCPG.BK in TAN, 2026) passes Engle-Granger against many
  partners. When one ticker dominates the qualified list, say so instead of presenting those pairs as signal.

## SSL: `CERTIFICATE_VERIFY_FAILED` on this machine

Python's certifi bundle may lack a root that Windows trusts (HTTPS inspection). Without installing
anything, build a session bundle and point requests/yfinance at it:

```
py -3 -c "import ssl,certifi;pem=[open(certifi.where()).read()]+[ssl.DER_cert_to_PEM_cert(c) for s in ('ROOT','CA') for c,e,_ in ssl.enum_certificates(s) if e=='x509_asn'];open('ca_bundle.pem','w').write('\n'.join(pem))"
export SSL_CERT_FILE=$PWD/ca_bundle.pem REQUESTS_CA_BUNDLE=$PWD/ca_bundle.pem CURL_CA_BUNDLE=$PWD/ca_bundle.pem
```

Only applies on Windows; on other machines the default bundle normally works.
