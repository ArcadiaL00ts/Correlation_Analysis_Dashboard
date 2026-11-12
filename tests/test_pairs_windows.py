from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nasdaq_correlation_dashboard.correlation import build_artifacts  # noqa: E402
from nasdaq_correlation_dashboard.pairs_cointegration import (  # noqa: E402
    MIN_COINTEGRATION_OBSERVATIONS,
    PairAnalysisConfig,
    analyze_pairs,
    leg_level_adf_p_value,
    select_analysis_window,
)
from nasdaq_correlation_dashboard.settings import load_config  # noqa: E402


def _synthetic_prices(rows: int = 300, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.bdate_range("2024-01-01", periods=rows)
    trend = np.cumsum(rng.normal(0, 0.02, rows))  # shared random walk in log space
    return pd.DataFrame(
        {
            # TRA and TRB are cointegrated random walks: valid Engle-Granger pair.
            "TRA": np.exp(4 + trend + rng.normal(0, 0.005, rows)),
            "TRB": np.exp(3 + trend + rng.normal(0, 0.005, rows)),
            # FLAT is range-bound white noise around a constant: stationary price level.
            "FLAT": np.exp(2 + rng.normal(0, 0.01, rows)),
        },
        index=index,
    )


class AnalysisWindowTests(unittest.TestCase):
    def test_short_windows(self) -> None:
        prices = _synthetic_prices()
        self.assertLessEqual(len(select_analysis_window(prices, "5d")), 6)
        self.assertTrue(20 <= len(select_analysis_window(prices, "1mo")) <= 24)
        self.assertTrue(60 <= len(select_analysis_window(prices, "3mo")) <= 67)
        self.assertEqual(len(select_analysis_window(prices, "max")), len(prices))

    def test_unknown_period_raises(self) -> None:
        with self.assertRaises(ValueError):
            select_analysis_window(_synthetic_prices(), "7w")

    def test_below_floor_rejects_every_pair(self) -> None:
        prices = _synthetic_prices()
        artifacts = analyze_pairs(
            prices, ["TRA", "TRB", "FLAT"], PairAnalysisConfig(history_period="5d"), source_path="x.csv"
        )
        self.assertEqual(artifacts.metadata["counts"]["pairs_qualified"], 0)
        self.assertTrue(
            artifacts.all_pairs["notes"].str.contains(f"below minimum {MIN_COINTEGRATION_OBSERVATIONS}").all()
        )


class StationaryLegTests(unittest.TestCase):
    def test_leg_adf(self) -> None:
        prices = _synthetic_prices()
        self.assertLess(leg_level_adf_p_value(prices["FLAT"]), 0.05)
        self.assertGreater(leg_level_adf_p_value(prices["TRA"]), 0.05)
        self.assertTrue(np.isnan(leg_level_adf_p_value(prices["TRA"].head(5))))

    def _analyze(self, require: bool):
        return analyze_pairs(
            _synthetic_prices(),
            ["TRA", "TRB", "FLAT"],
            PairAnalysisConfig(min_observations=100, require_nonstationary_legs=require),
            source_path="x.csv",
        )

    def test_range_bound_leg_is_excluded_from_qualified(self) -> None:
        artifacts = self._analyze(require=True)
        qualified = set(artifacts.qualified_pairs["pair"])
        self.assertIn("TRA|TRB", qualified)
        self.assertFalse(any("FLAT" in pair for pair in qualified))
        flat_rows = artifacts.all_pairs[artifacts.all_pairs["pair"].str.contains("FLAT")]
        self.assertFalse(flat_rows["both_legs_nonstationary"].any())
        self.assertEqual([item["ticker"] for item in artifacts.metadata["stationary_legs"]], ["FLAT"])
        excluded = flat_rows[flat_rows["excluded_stationary_leg"]]
        self.assertTrue(excluded["notes"].str.contains("range-bound leg FLAT").all())
        self.assertEqual(artifacts.metadata["counts"]["pairs_excluded_stationary_leg"], len(excluded))

    def test_flag_off_keeps_legacy_behaviour(self) -> None:
        artifacts = self._analyze(require=False)
        self.assertEqual(artifacts.metadata["counts"]["pairs_excluded_stationary_leg"], 0)
        self.assertIn("leg_y_adf_p", artifacts.all_pairs.columns)


class ZeroReturnShareTests(unittest.TestCase):
    def test_zero_return_share_in_metadata(self) -> None:
        config = load_config(ROOT / "config" / "dashboard_config.json")
        prices = _synthetic_prices(rows=41)
        prices.iloc[1::2, prices.columns.get_loc("FLAT")] = np.nan
        prices = prices.ffill()  # every other day unchanged -> ~50% zero returns
        artifacts = build_artifacts(prices, {}, {}, {}, config)
        share = artifacts.metadata["zero_return_share"]
        self.assertAlmostEqual(share["FLAT"], 0.5, delta=0.03)
        self.assertEqual(share["TRA"], 0.0)


if __name__ == "__main__":
    unittest.main()
