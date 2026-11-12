from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from nasdaq_correlation_dashboard.pairs_cointegration import (
    PairAnalysisConfig,
    analyze_pairs,
    export_pairs_workbook,
    load_price_frame,
    load_universe_tickers,
    select_tickers,
    write_pairs_artifacts,
)
from nasdaq_correlation_dashboard.settings import load_config


DEFAULT_HISTORY_CHOICES = ("6mo", "1y", "2y", "3y", "5y", "10y", "max")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan a local equity universe for cointegrated pairs and export a ranked Excel workbook."
    )
    parser.add_argument(
        "--config",
        default=str(PROJECT_ROOT / "config" / "dashboard_config.json"),
        help="Path to the dashboard configuration JSON file.",
    )
    parser.add_argument(
        "--prices",
        help="Optional override for the input prices CSV. Defaults to the configured processed price file.",
    )
    parser.add_argument(
        "--universe",
        help="Optional override for the universe CSV. Defaults to the configured universe file.",
    )
    parser.add_argument(
        "--output",
        help="Destination workbook path.",
    )
    parser.add_argument(
        "--tickers",
        help="Optional comma-separated ticker subset to analyze.",
    )
    parser.add_argument(
        "--min-obs",
        type=int,
        help="Minimum overlapping observations required to test a pair.",
    )
    parser.add_argument(
        "--rolling-z-window",
        type=int,
        help="Rolling lookback window for the supplementary rolling z-score.",
    )
    parser.add_argument(
        "--top-spreads",
        type=int,
        help="Number of top-ranked pairs to include in the pair_spreads sheet.",
    )
    parser.add_argument(
        "--history-period",
        help="Optional analysis window on the available price history (for example: 6mo, 1y, 2y, max).",
    )
    return parser.parse_args()


def resolve_history_period(args: argparse.Namespace, config) -> str:
    configured = str(config.pairs_trading.get("history_period", config.history["period"]))
    prompt_choices = config.pairs_trading.get("prompt_choices", list(DEFAULT_HISTORY_CHOICES))
    allowed = [str(choice).strip() for choice in prompt_choices if str(choice).strip()]
    if not allowed:
        allowed = list(DEFAULT_HISTORY_CHOICES)

    if args.history_period:
        chosen = args.history_period.strip()
    elif sys.stdin.isatty():
        choice_text = ", ".join(allowed)
        try:
            chosen = (
                input(
                    f"Select cointegration analysis window [{choice_text}] "
                    f"(default: {configured}): "
                ).strip()
                or configured
            )
        except EOFError:
            chosen = configured
    else:
        chosen = configured

    if chosen not in allowed:
        raise SystemExit(
            f"Unsupported history period '{chosen}'. Allowed values: {', '.join(allowed)}."
        )

    config.payload["pairs_trading"]["history_period"] = chosen
    return chosen


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    history_period = resolve_history_period(args, config)

    prices_path = Path(args.prices) if args.prices else config.paths["raw_prices_csv"]
    universe_path = Path(args.universe) if args.universe else config.paths["universe_csv"]
    output_path = Path(args.output) if args.output else config.paths["pairs_workbook"]

    prices = load_price_frame(prices_path)
    universe_tickers = load_universe_tickers(universe_path)
    requested_tickers = [value.strip().upper() for value in (args.tickers or "").split(",") if value.strip()]
    selected_tickers = select_tickers(
        prices,
        requested_tickers=requested_tickers,
        universe_tickers=universe_tickers,
    )

    artifacts = analyze_pairs(
        prices=prices[selected_tickers],
        tickers=selected_tickers,
        config=PairAnalysisConfig(
            min_observations=args.min_obs or int(config.pairs_trading["minimum_rows"]),
            rolling_z_window=args.rolling_z_window or int(config.pairs_trading["rolling_z_window"]),
            top_spread_export=args.top_spreads or int(config.pairs_trading["spread_export_limit"]),
            cointegration_p_threshold=float(config.pairs_trading["cointegration_p_threshold"]),
            adf_stat_threshold=float(config.pairs_trading["adf_stat_threshold"]),
            history_period=history_period,
        ),
        source_path=prices_path,
        universe_path=universe_path,
    )
    export_pairs_workbook(artifacts, output_path)
    write_pairs_artifacts(
        artifacts,
        all_pairs_path=config.paths["pairs_all_csv"],
        qualified_pairs_path=config.paths["pairs_qualified_csv"],
        spreads_path=config.paths["pairs_spreads_csv"],
        metadata_path=config.paths["pairs_metadata_json"],
    )

    qualified_count = int(artifacts.qualified_pairs["qualified_flag"].sum())
    tested_count = len(selected_tickers) * (len(selected_tickers) - 1) // 2
    print(
        "Pairs cointegration analysis completed for "
        f"{len(selected_tickers)} tickers, {tested_count} pairs tested, "
        f"{qualified_count} qualified pairs over the {history_period} window. "
        f"Workbook: {output_path.resolve()}"
    )


if __name__ == "__main__":
    main()
