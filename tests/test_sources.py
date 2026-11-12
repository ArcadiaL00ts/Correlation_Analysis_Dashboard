from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nasdaq_correlation_dashboard.settings import load_config  # noqa: E402
from nasdaq_correlation_dashboard.sources import DataSourceError, fetch_prices, validate_prices  # noqa: E402

INDEX = pd.bdate_range("2026-01-01", periods=30)


def _raw(tickers: list[str], blank: set[str] = frozenset()) -> pd.DataFrame:
    columns = pd.MultiIndex.from_product([["Adj Close", "Close"], tickers])
    data = np.tile(np.linspace(10, 20, len(INDEX))[:, None], (1, len(columns)))
    frame = pd.DataFrame(data, index=INDEX, columns=columns)
    for ticker in blank:
        frame.loc[:, (slice(None), ticker)] = np.nan
    return frame


class FetchPricesRetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(ROOT / "config" / "dashboard_config.json")
        self.config.payload["price_source"]["fallback_provider"] = None
        self.config.payload["price_source"]["provider"] = "yfinance"

    def _run(self, responses: list[pd.DataFrame]) -> tuple:
        fake = types.SimpleNamespace(download=mock.Mock(side_effect=responses))
        with mock.patch.dict(sys.modules, {"yfinance": fake}):
            result = fetch_prices(self.config, ["AAA", "BBB", "CCC"])
        return result, fake.download

    def test_blank_symbol_is_retried_and_recovered(self) -> None:
        result, download = self._run([_raw(["AAA", "BBB", "CCC"], blank={"BBB"}), _raw(["BBB"])])
        self.assertEqual(download.call_count, 2)
        self.assertEqual(download.call_args_list[1].kwargs["tickers"], ["BBB"])
        self.assertTrue(result.prices["BBB"].notna().all())
        self.assertEqual(result.metadata["retried_tickers"], ["BBB"])
        self.assertEqual(result.metadata["retry_recovered_tickers"], ["BBB"])

    def test_still_blank_after_retry_is_reported(self) -> None:
        result, download = self._run([_raw(["AAA", "BBB", "CCC"], blank={"CCC"}), pd.DataFrame()])
        self.assertEqual(download.call_count, 2)
        self.assertEqual(result.metadata["retry_recovered_tickers"], [])
        self.assertTrue(result.prices["CCC"].isna().all())

    def test_no_retry_when_complete(self) -> None:
        result, download = self._run([_raw(["AAA", "BBB", "CCC"])])
        self.assertEqual(download.call_count, 1)
        self.assertNotIn("retried_tickers", result.metadata)

    def test_empty_download_raises(self) -> None:
        with self.assertRaises(DataSourceError):
            self._run([pd.DataFrame()])


class ValidatePricesTests(unittest.TestCase):
    def test_short_window_passes_with_scaled_minimum(self) -> None:
        config = load_config(ROOT / "config" / "dashboard_config.json")
        config.payload["validation"]["minimum_rows"] = 4
        prices = pd.DataFrame({"AAA": [1.0, 2, 3, 4, 5], "BBB": [2.0, 3, 4, 5, 6]}, index=INDEX[:5])
        report = validate_prices(prices, ["AAA", "BBB"], config)
        self.assertEqual(report["observed_rows"], 5)


if __name__ == "__main__":
    unittest.main()
