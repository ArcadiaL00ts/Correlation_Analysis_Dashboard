from __future__ import annotations

import argparse
import sys
from pathlib import Path


from ..cli import (
    period_label,
    resolve_history_period,
    scaled_minimum_rows,
    scaled_window,
)
from ..correlation import build_artifacts
from ..atomic_io import copy_file, write_csv, write_json
from ..etf_universe import (
    build_etf_selection,
    parse_holdings,
    read_holdings_file,
    resolve_ambiguous_symbols,
    write_etf_config,
)
from ..excel_export import export_workbook
from ..pairs_cointegration import (
    PairAnalysisConfig,
    analyze_pairs,
    export_pairs_workbook,
    write_pairs_artifacts,
)
from ..net import configure_tls
from ..settings import default_config_path, load_config, project_root
from ..sources import fetch_prices, validate_prices, write_metadata
from ..universe import write_universe

# Forward-fill at most this many consecutive missing days per ticker, so holdings listed on
# exchanges with different holidays (Tel Aviv, Hong Kong, ...) line up with US trading days.
CROSS_EXCHANGE_FFILL_LIMIT = 3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the correlation + cointegration pipeline on an ETF's holdings. "
            "Outputs go to data/etf/<ETF>/ and exports/etf/<ETF>/; NASDAQ-100 artifacts are untouched."
        )
    )
    parser.add_argument("--etf", help="ETF ticker, e.g. TAN. Prompted for when omitted.")
    parser.add_argument(
        "--holdings",
        help="Holdings export (CSV/XLSX). Default: data/manual_universe/<ETF>_holdings.csv",
    )
    parser.add_argument(
        "--ticker-map",
        default="",
        help="Comma list of SOURCE=YAHOO overrides, e.g. 'ENLT=ENLT.TA,3800=3800.HK'.",
    )
    parser.add_argument("--history-period", help="Price history horizon (e.g. 1y, 2y, 5y).")
    parser.add_argument("--pairs-history-period", help="Cointegration window (e.g. 6mo, 1y, 2y).")
    parser.add_argument(
        "--base-config",
        default=str(default_config_path()),
        help="Base config to inherit analytics, history, and visual settings from.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_tls()
    etf = (args.etf or "").strip().upper()
    if not etf and sys.stdin.isatty():
        etf = input("ETF ticker to analyse (e.g. TAN): ").strip().upper()
    if not etf:
        raise SystemExit("Pass --etf <TICKER> (no interactive terminal to prompt).")

    # Ask for the lookbacks first, before touching the holdings file or the network.
    base = load_config(args.base_config)
    history_period = resolve_history_period(
        args.history_period,
        configured=str(base.history["period"]),
        choices=base.history.get("prompt_choices"),
        label="price-history lookback",
    )
    pairs_period = resolve_history_period(
        args.pairs_history_period,
        configured=str(base.pairs_trading.get("history_period", history_period)),
        choices=base.pairs_trading.get("prompt_choices"),
        label="cointegration lookback",
    )
    print(
        f"{etf}: price history {period_label(history_period)}, "
        f"cointegration window {period_label(pairs_period)}."
    )

    holdings_path = Path(
        args.holdings or project_root() / "data" / "manual_universe" / f"{etf}_holdings.csv"
    ).resolve()
    if not holdings_path.exists():
        raise SystemExit(
            f"Holdings file not found: {holdings_path}\n"
            f"Download {etf}'s holdings export from the issuer's site and save it there, "
            "or pass --holdings <path>."
        )

    ticker_map = dict(
        pair.split("=", 1) for pair in args.ticker_map.split(",") if "=" in pair
    )
    holdings, skipped = parse_holdings(read_holdings_file(holdings_path), ticker_map)
    as_of_date = holdings.attrs.get("as_of_date")
    # Holdings whose exchange is ambiguous (e.g. Taiwan .TW vs .TWO) are probed once and cached.
    holdings, symbol_report = resolve_ambiguous_symbols(
        holdings, cache_path=project_root() / "data" / "manual_universe" / "symbol_map.json"
    )
    for item in symbol_report:
        if item["how"] != "cache":
            print(f"{item['source_ticker']}: {item['chosen']} ({item['how']}; candidates {', '.join(item['candidates'])})")
    unmapped = [item for item in skipped if item.get("reason") != "non-equity line"]
    for item in unmapped:
        print(f"Not included: {item['name'] or '?'} ({item.get('identifier') or 'no id'}, weight {item['weight']}): {item['reason']}")

    config_path = write_etf_config(Path(args.base_config), etf, len(holdings))
    config = load_config(config_path)
    config.payload["history"]["period"] = history_period
    config.payload["pairs_trading"]["history_period"] = pairs_period
    # Short lookbacks cannot satisfy the 252-row default; scale row minimums to the chosen window.
    config.payload["validation"]["minimum_rows"] = scaled_minimum_rows(
        history_period, int(config.validation["minimum_rows"])
    )
    config.payload["pairs_trading"]["minimum_rows"] = scaled_minimum_rows(
        pairs_period, int(config.pairs_trading["minimum_rows"])
    )
    config.payload["pairs_trading"]["rolling_z_window"] = scaled_window(
        pairs_period, int(config.pairs_trading["rolling_z_window"])
    )

    result = fetch_prices(config, holdings["ticker"].tolist())
    prices = result.prices  # fetch_prices already retried any blank symbols once
    prices = prices.ffill(limit=CROSS_EXCHANGE_FFILL_LIMIT)

    # Drop holdings Yahoo cannot price (bad symbol mapping, recent IPO) rather than failing the run.
    min_rows = int(config.validation["minimum_rows"])
    max_missing = float(config.validation["maximum_missing_ratio"])
    dropped: list[dict[str, str]] = []
    for ticker in holdings["ticker"]:
        if ticker not in prices.columns:
            dropped.append({"ticker": ticker, "reason": "no price data returned"})
            continue
        series = prices[ticker]
        first_valid = series.first_valid_index()
        if first_valid is None:
            dropped.append({"ticker": ticker, "reason": "no price data returned"})
        elif series.notna().sum() < min_rows:
            dropped.append({"ticker": ticker, "reason": f"only {int(series.notna().sum())} priced rows"})
        elif series.loc[first_valid:].isna().mean() > max_missing:
            # Leading gaps (window opens on a local holiday) are trimmed below, so ignore them here.
            dropped.append(
                {"ticker": ticker, "reason": f"{series.loc[first_valid:].isna().mean():.1%} missing"}
            )
    dropped_set = {item["ticker"] for item in dropped}
    holdings = holdings[~holdings["ticker"].isin(dropped_set)].reset_index(drop=True)
    holdings["rank"] = range(1, len(holdings) + 1)
    if len(holdings) < 3:
        raise SystemExit(f"Only {len(holdings)} priceable holdings; dropped: {dropped}")

    tickers = holdings["ticker"].tolist()
    prices = prices[tickers].dropna(how="all")
    prices = prices.loc[prices.notna().all(axis=1).idxmax():]  # start once every name trades
    config.payload["universe_policy"]["universe_size"] = len(tickers)
    write_json(config.payload, config_path)

    selection = build_etf_selection(etf, holdings, holdings_path, skipped, dropped, as_of_date, symbol_report)
    result.metadata["cross_exchange_ffill_limit"] = CROSS_EXCHANGE_FFILL_LIMIT
    validation = validate_prices(prices, tickers, config)
    artifacts = build_artifacts(prices, result.metadata, selection.metadata, validation, config)

    paths = config.paths
    pair_artifacts = analyze_pairs(
        prices=artifacts.prices,
        tickers=tickers,
        config=PairAnalysisConfig(
            cointegration_p_threshold=float(config.pairs_trading["cointegration_p_threshold"]),
            adf_stat_threshold=float(config.pairs_trading["adf_stat_threshold"]),
            require_nonstationary_legs=bool(config.pairs_trading.get("require_nonstationary_legs", True)),
            leg_adf_p_threshold=float(config.pairs_trading.get("leg_adf_p_threshold", 0.05)),
            min_observations=int(config.pairs_trading["minimum_rows"]),
            rolling_z_window=int(config.pairs_trading["rolling_z_window"]),
            top_spread_export=int(config.pairs_trading["spread_export_limit"]),
            history_period=pairs_period,
        ),
        source_path=paths["raw_prices_csv"],
        universe_path=paths["universe_csv"],
    )

    for current, previous in (
        ("universe_csv", "previous_universe_csv"),
        ("correlation_csv", "previous_correlation_csv"),
        ("metadata_json", "previous_metadata_json"),
    ):
        if paths[current].exists():
            copy_file(paths[current], paths[previous])

    paths["raw_prices_csv"].parent.mkdir(parents=True, exist_ok=True)
    write_universe(selection.universe, paths["universe_csv"])
    write_csv(artifacts.prices, paths["raw_prices_csv"])
    write_csv(artifacts.returns, paths["returns_csv"])
    write_csv(artifacts.correlation, paths["correlation_csv"])
    export_workbook(artifacts, config, paths["excel_workbook"])
    export_pairs_workbook(pair_artifacts, paths["pairs_workbook"])
    write_pairs_artifacts(
        pair_artifacts,
        all_pairs_path=paths["pairs_all_csv"],
        qualified_pairs_path=paths["pairs_qualified_csv"],
        spreads_path=paths["pairs_spreads_csv"],
        metadata_path=paths["pairs_metadata_json"],
    )
    artifacts.metadata["outputs"] = {
        name: {"path": str(path.relative_to(config.root)), "exists": path.exists()}
        for name, path in paths.items()
    }
    write_metadata(artifacts.metadata, paths["metadata_json"])

    print(
        f"{etf}: {len(tickers)} holdings correlated "
        f"({period_label(history_period)}, pairs {period_label(pairs_period)})."
    )
    if dropped:
        print("Dropped (unpriced):", ", ".join(f"{d['ticker']} ({d['reason']})" for d in dropped))
    print(f"Workbook: {paths['excel_workbook']}")
    print(f"View: corrdash-app --config {config_path}   (or: py -3 scripts/run_dashboard.py --config {config_path})")


if __name__ == "__main__":
    main()
