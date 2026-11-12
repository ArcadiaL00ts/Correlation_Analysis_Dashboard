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

from nasdaq_correlation_dashboard.universe import (  # noqa: E402
    UniverseSelection,
    UniverseSourceError,
    apply_history_coverage,
)


def _rows(tickers: list[str], start_rank: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "rank": range(start_rank, start_rank + len(tickers)),
            "ticker": tickers,
            "company_name": [f"{t} Inc" for t in tickers],
        }
    )


def _prices(late: dict[str, int], tickers: list[str], rows: int = 100) -> pd.DataFrame:
    index = pd.bdate_range("2025-01-01", periods=rows)
    data = {t: np.linspace(10, 20, rows) for t in tickers}
    frame = pd.DataFrame(data, index=index)
    for ticker, first_row in late.items():
        frame.loc[frame.index[:first_row], ticker] = np.nan
    return frame


class HistoryCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.selection = UniverseSelection(
            universe=_rows(["AAA", "NEW", "CCC"], 1),
            metadata={"final_tickers": ["AAA", "NEW", "CCC"]},
            reserve=_rows(["RES1", "RES2"], 4),
        )
        self.all_tickers = ["AAA", "NEW", "CCC", "RES1", "RES2"]

    def test_full_coverage_keeps_selection(self) -> None:
        prices = _prices({}, self.all_tickers)
        selection, trimmed = apply_history_coverage(self.selection, prices, 0.05)
        self.assertEqual(selection.tickers, ["AAA", "NEW", "CCC"])
        self.assertEqual(list(trimmed.columns), ["AAA", "NEW", "CCC"])
        self.assertNotIn("history_substitutions", selection.metadata)

    def test_recent_listing_is_replaced_by_next_rank(self) -> None:
        prices = _prices({"NEW": 60}, self.all_tickers)
        selection, trimmed = apply_history_coverage(self.selection, prices, 0.05)
        self.assertEqual(selection.tickers, ["AAA", "CCC", "RES1"])
        self.assertEqual(selection.universe["rank"].tolist(), [1, 3, 4])
        self.assertEqual(list(trimmed.columns), ["AAA", "CCC", "RES1"])
        swap = selection.metadata["history_substitutions"][0]
        self.assertEqual((swap["excluded"], swap["replacement"], swap["replacement_rank"]), ("NEW", "RES1", 4))
        self.assertEqual(selection.metadata["final_tickers"], ["AAA", "CCC", "RES1"])
        self.assertEqual(selection.reserve_tickers, ["RES2"])

    def test_short_reserve_names_are_skipped(self) -> None:
        prices = _prices({"NEW": 60, "RES1": 50}, self.all_tickers)
        selection, _ = apply_history_coverage(self.selection, prices, 0.05)
        self.assertEqual(selection.tickers, ["AAA", "CCC", "RES2"])
        self.assertEqual(selection.metadata["history_substitutions_skipped_reserve"][0]["ticker"], "RES1")

    def test_small_leading_gap_is_tolerated(self) -> None:
        prices = _prices({"NEW": 3}, self.all_tickers)
        selection, _ = apply_history_coverage(self.selection, prices, 0.05)
        self.assertIn("NEW", selection.tickers)

    def test_exhausted_reserve_raises(self) -> None:
        prices = _prices({"NEW": 60, "RES1": 60, "RES2": 60}, self.all_tickers)
        with self.assertRaises(UniverseSourceError):
            apply_history_coverage(self.selection, prices, 0.05)


if __name__ == "__main__":
    unittest.main()
