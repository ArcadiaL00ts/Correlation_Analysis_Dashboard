"""Build a small, synthetic artifact set with the real pipeline functions (no network).

Used by the dashboard smoke test: a 5-ticker universe written exactly as the refresh writes it,
into a temporary project root with its own config.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd

from nasdaq_correlation_dashboard.correlation import build_artifacts
from nasdaq_correlation_dashboard.excel_export import export_workbook
from nasdaq_correlation_dashboard.pairs_cointegration import (
    PairAnalysisConfig,
    analyze_pairs,
    export_pairs_workbook,
    write_pairs_artifacts,
)
from nasdaq_correlation_dashboard.settings import default_config_path, load_config
from nasdaq_correlation_dashboard.sources import validate_prices, write_metadata
from nasdaq_correlation_dashboard.universe import write_universe

TICKERS = ["AAA", "BBB", "CCC", "DDD", "EEE"]


def synthetic_prices(rows: int, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.bdate_range(end="2026-11-12", periods=rows)
    common = np.cumsum(rng.normal(0, 0.012, rows))
    data = {}
    for i, ticker in enumerate(TICKERS):
        own = np.cumsum(rng.normal(0, 0.01, rows)) if i % 2 else rng.normal(0, 0.004, rows)
        data[ticker] = np.exp(3 + 0.1 * i + common + own)
    return pd.DataFrame(data, index=index).rename_axis("Date")


def build_fixture(root: Path, rows: int = 300, price_period: str = "1y", pair_period: str = "1y") -> Path:
    """Write config + artifacts under ``root``; return the config path."""
    base = load_config(default_config_path())
    payload = copy.deepcopy(base.payload)
    payload["universe_policy"]["universe_size"] = len(TICKERS)
    payload["universe_policy"]["benchmark_ticker"] = "AAA"
    payload["history"]["period"] = price_period
    payload["validation"]["minimum_rows"] = min(rows, int(payload["validation"]["minimum_rows"]))
    payload["pairs_trading"]["history_period"] = pair_period
    payload["dashboard"] = {"enable_rerun": True}
    config_path = root / "config" / "dashboard_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    config = load_config(config_path)
    paths = config.paths

    prices = synthetic_prices(rows)
    universe = pd.DataFrame(
        {"rank": range(1, len(TICKERS) + 1), "ticker": TICKERS, "company_name": [f"{t} Corp" for t in TICKERS]}
    )
    universe_metadata = {
        "universe_size": len(TICKERS),
        "selection_mode": payload["universe_policy"]["selection_mode"],
        "official_source": {"type": "fixture", "trade_date": "2026-11-11"},
        "ranking": {"source_type": "fixture", "fallback_used": False, "fallback_reason": None},
        "final_tickers": TICKERS,
        "final_universe": universe.to_dict(orient="records"),
    }
    price_metadata = {"provider": "fixture", "period": price_period, "interval": "1d", "tickers_requested": TICKERS}
    validation = validate_prices(prices, TICKERS, config)
    artifacts = build_artifacts(prices, price_metadata, universe_metadata, validation, config)
    pair_artifacts = analyze_pairs(
        prices=artifacts.prices,
        tickers=TICKERS,
        config=PairAnalysisConfig(
            min_observations=min(rows, 100), rolling_z_window=min(20, max(5, rows // 2)), history_period=pair_period
        ),
        source_path=paths["raw_prices_csv"],
        universe_path=paths["universe_csv"],
    )

    write_universe(universe, paths["universe_csv"])
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
    return config_path
