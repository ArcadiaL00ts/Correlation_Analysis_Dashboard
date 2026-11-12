from __future__ import annotations

import argparse


from ..net import configure_tls
from ..universe import refresh_universe
from ..settings import default_config_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview the currently resolved top-50 universe and its provenance."
    )
    parser.add_argument(
        "--config",
        default=str(default_config_path()),
        help="Path to the dashboard configuration JSON file.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=50,
        help="Number of ranked names to print (default: 50).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_tls()
    result = refresh_universe(args.config, top_n=args.top_n)

    print(f"Resolved tickers ({len(result['proposed_tickers'])}):")
    for index, ticker in enumerate(result["proposed_tickers"], 1):
        print(f"  {index:2d}. {ticker}")

    print("\nProvenance:")
    print(f"  Official trade date: {result['snapshot_date']}")
    print(f"  Ranking source: {result['ranking_source']}")
    print(f"  Fallback used: {result['fallback_used']}")
    print("\nThis command is preview-only and does not modify the config file.")


if __name__ == "__main__":
    main()
