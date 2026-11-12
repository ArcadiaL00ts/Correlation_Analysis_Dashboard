from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from nasdaq_correlation_dashboard.correlation import build_artifacts
from nasdaq_correlation_dashboard.excel_export import export_workbook
from nasdaq_correlation_dashboard.pairs_cointegration import (
    PairAnalysisConfig,
    analyze_pairs,
    export_pairs_workbook,
    write_pairs_artifacts,
)
from nasdaq_correlation_dashboard.settings import load_config
from nasdaq_correlation_dashboard.sources import (
    fetch_prices,
    validate_prices,
    write_metadata,
)
from nasdaq_correlation_dashboard.universe import resolve_universe, write_universe


DEFAULT_HISTORY_CHOICES = ("6mo", "1y", "2y", "3y", "5y", "10y", "max")


def snapshot_previous_run(paths: dict[str, Path]) -> None:
    snapshot_pairs = (
        ("universe_csv", "previous_universe_csv"),
        ("correlation_csv", "previous_correlation_csv"),
        ("metadata_json", "previous_metadata_json"),
    )
    for current_key, previous_key in snapshot_pairs:
        current_path = paths.get(current_key)
        previous_path = paths.get(previous_key)
        if current_path is None or previous_path is None or not current_path.exists():
            continue
        previous_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(current_path, previous_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh universe, price history, correlation outputs, and Excel workbook."
    )
    parser.add_argument(
        "--config",
        default=str(PROJECT_ROOT / "config" / "dashboard_config.json"),
        help="Path to the dashboard configuration JSON file.",
    )
    parser.add_argument(
        "--history-period",
        help="Optional yfinance history horizon override for this refresh (for example: 1y, 2y, 5y, max).",
    )
    parser.add_argument(
        "--pairs-history-period",
        help="Optional cointegration analysis window override (for example: 6mo, 1y, 2y, max).",
    )
    return parser.parse_args()


def resolve_history_period(args: argparse.Namespace, config) -> str:
    configured = str(config.history["period"])
    prompt_choices = config.history.get("prompt_choices", list(DEFAULT_HISTORY_CHOICES))
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
                    f"Select price-history horizon for this refresh [{choice_text}] "
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
            f"Unsupported history horizon '{chosen}'. Allowed values: {', '.join(allowed)}."
        )

    config.payload["history"]["period"] = chosen
    return chosen


def resolve_pairs_history_period(args: argparse.Namespace, config) -> str:
    configured = str(config.pairs_trading.get("history_period", config.history["period"]))
    prompt_choices = config.pairs_trading.get("prompt_choices", list(DEFAULT_HISTORY_CHOICES))
    allowed = [str(choice).strip() for choice in prompt_choices if str(choice).strip()]
    if not allowed:
        allowed = list(DEFAULT_HISTORY_CHOICES)

    if args.pairs_history_period:
        chosen = args.pairs_history_period.strip()
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
            f"Unsupported cointegration analysis window '{chosen}'. Allowed values: {', '.join(allowed)}."
        )

    config.payload["pairs_trading"]["history_period"] = chosen
    return chosen


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    paths = config.paths
    history_period = resolve_history_period(args, config)
    pairs_history_period = resolve_pairs_history_period(args, config)

    selection = resolve_universe(config)
    result = fetch_prices(config, selection.tickers)
    validation = validate_prices(result.prices, selection.tickers, config)
    artifacts = build_artifacts(
        result.prices,
        result.metadata,
        selection.metadata,
        validation,
        config,
    )

    pair_config = PairAnalysisConfig(
        cointegration_p_threshold=float(config.pairs_trading["cointegration_p_threshold"]),
        adf_stat_threshold=float(config.pairs_trading["adf_stat_threshold"]),
        min_observations=int(config.pairs_trading["minimum_rows"]),
        rolling_z_window=int(config.pairs_trading["rolling_z_window"]),
        top_spread_export=int(config.pairs_trading["spread_export_limit"]),
        history_period=pairs_history_period,
    )
    pair_artifacts = analyze_pairs(
        prices=artifacts.prices,
        tickers=selection.tickers,
        config=pair_config,
        source_path=paths["raw_prices_csv"],
        universe_path=paths["universe_csv"],
    )
    snapshot_previous_run(paths)

    write_universe(selection.universe, paths["universe_csv"])
    paths["raw_prices_csv"].parent.mkdir(parents=True, exist_ok=True)
    artifacts.prices.to_csv(paths["raw_prices_csv"])
    artifacts.returns.to_csv(paths["returns_csv"])
    artifacts.correlation.to_csv(paths["correlation_csv"])
    export_workbook(artifacts, config, paths["excel_workbook"])

    export_pairs_workbook(pair_artifacts, paths["pairs_workbook"])
    write_pairs_artifacts(
        pair_artifacts,
        all_pairs_path=paths["pairs_all_csv"],
        qualified_pairs_path=paths["pairs_qualified_csv"],
        spreads_path=paths["pairs_spreads_csv"],
        metadata_path=paths["pairs_metadata_json"],
    )
    write_metadata(artifacts.metadata, paths["metadata_json"])
    artifacts.metadata["outputs"] = {
        name: {
            "path": str(path.relative_to(config.root)),
            "exists": path.exists(),
        }
        for name, path in paths.items()
    }
    write_metadata(artifacts.metadata, paths["metadata_json"])

    print(
        "Updated dashboard artifacts for "
        f"{len(selection.tickers)} tickers at {paths['excel_workbook'].resolve()} "
        f"using a {history_period} history horizon; "
        f"cointegration window: {pairs_history_period}"
    )


if __name__ == "__main__":
    main()
