from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from nasdaq_correlation_dashboard.correlation import correlation_change_table


class CorrelationChangeTableTests(unittest.TestCase):
    def test_builds_pair_deltas_for_overlapping_tickers(self) -> None:
        current = pd.DataFrame(
            [
                [1.0, 0.80, 0.10],
                [0.80, 1.0, -0.20],
                [0.10, -0.20, 1.0],
            ],
            index=["AAPL", "MSFT", "NVDA"],
            columns=["AAPL", "MSFT", "NVDA"],
        )
        previous = pd.DataFrame(
            [
                [1.0, 0.50, -0.05],
                [0.50, 1.0, -0.10],
                [-0.05, -0.10, 1.0],
            ],
            index=["AAPL", "MSFT", "NVDA"],
            columns=["AAPL", "MSFT", "NVDA"],
        )

        changes = correlation_change_table(current, previous)

        self.assertEqual(["AAPL vs MSFT", "AAPL vs NVDA", "MSFT vs NVDA"], changes["pair"].tolist())
        self.assertAlmostEqual(0.30, changes.iloc[0]["change"])
        self.assertAlmostEqual(0.15, changes.iloc[1]["abs_change"])
        self.assertAlmostEqual(-0.10, changes.iloc[2]["change"])

    def test_ignores_non_overlapping_tickers(self) -> None:
        current = pd.DataFrame(
            [
                [1.0, 0.25, 0.60],
                [0.25, 1.0, 0.10],
                [0.60, 0.10, 1.0],
            ],
            index=["AAPL", "MSFT", "NVDA"],
            columns=["AAPL", "MSFT", "NVDA"],
        )
        previous = pd.DataFrame(
            [
                [1.0, 0.05],
                [0.05, 1.0],
            ],
            index=["AAPL", "MSFT"],
            columns=["AAPL", "MSFT"],
        )

        changes = correlation_change_table(current, previous)

        self.assertEqual(1, len(changes))
        self.assertEqual("AAPL vs MSFT", changes.iloc[0]["pair"])
        self.assertAlmostEqual(0.20, changes.iloc[0]["change"])


if __name__ == "__main__":
    unittest.main()
