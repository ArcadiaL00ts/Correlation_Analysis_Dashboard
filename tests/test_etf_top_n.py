from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nasdaq_correlation_dashboard.cli import parse_top_n, resolve_top_n  # noqa: E402
from nasdaq_correlation_dashboard.commands import etf as etf_command  # noqa: E402
from nasdaq_correlation_dashboard.etf_universe import select_top_weighted  # noqa: E402
from nasdaq_correlation_dashboard.sources import PriceLoadResult  # noqa: E402

ANALYZE_PAIRS = etf_command.analyze_pairs


class TopNParsingTests(unittest.TestCase):
    def test_parse(self) -> None:
        self.assertEqual(parse_top_n("50"), 50)
        self.assertEqual(parse_top_n(75), 75)
        for value in ("all", "ALL", "", "0", None):
            self.assertIsNone(parse_top_n(value))
        for bad in ("fifty", "2", "-5"):
            with self.assertRaises(SystemExit):
                parse_top_n(bad)

    def test_resolve_priority(self) -> None:
        self.assertEqual(resolve_top_n("80", 50), 80)
        self.assertIsNone(resolve_top_n("all", 50))
        with mock.patch.object(sys.stdin, "isatty", return_value=False):
            self.assertEqual(resolve_top_n(None, 50), 50)
            self.assertIsNone(resolve_top_n(None, "all"))
        with mock.patch.object(sys.stdin, "isatty", return_value=True):
            with mock.patch("builtins.input", return_value="120"):
                self.assertEqual(resolve_top_n(None, 50, [25, 50, "all"]), 120)
            with mock.patch("builtins.input", return_value=""):
                self.assertEqual(resolve_top_n(None, 50), 50)
            with mock.patch("builtins.input", side_effect=EOFError):
                self.assertEqual(resolve_top_n(None, 50), 50)


class SelectTopWeightedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = pd.DataFrame(
            {
                "rank": [9, 9, 9, 9],
                "ticker": ["B", "A", "D", "C"],
                "company_name": ["b", "a", "d", "c"],
                "weight": [5.0, 9.0, 1.0, 3.0],
            }
        )

    def test_cuts_by_weight_and_reranks(self) -> None:
        keep, excluded = select_top_weighted(self.frame, 2)
        self.assertEqual(keep["ticker"].tolist(), ["A", "B"])
        self.assertEqual(keep["rank"].tolist(), [1, 2])
        self.assertEqual([item["ticker"] for item in excluded], ["C", "D"])

    def test_fewer_holdings_than_requested_keeps_all(self) -> None:
        keep, excluded = select_top_weighted(self.frame, 50)
        self.assertEqual(keep["ticker"].tolist(), ["A", "B", "C", "D"])
        self.assertEqual(excluded, [])
        keep, _ = select_top_weighted(self.frame, None)
        self.assertEqual(len(keep), 4)


def _holdings_csv(path: Path, count: int) -> None:
    weights = np.linspace(8.0, 0.1, count)
    rows = [f"T{i:02d},Company {i:02d},Equity,{w:.3f}" for i, w in enumerate(weights, start=1)]
    path.write_text(
        "Holding Ticker,Name,Class of Shares,Weight\n" + "\n".join(rows) + "\n", encoding="utf-8"
    )


class EtfRunTopNTests(unittest.TestCase):
    """End-to-end ETF run on synthetic holdings with mocked prices (no network)."""

    UNPRICEABLE = {"T03", "T10"}

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "pyproject.toml").write_text("", encoding="utf-8")
        (self.tmp / "config").mkdir()
        base = json.loads((ROOT / "config" / "dashboard_config.json").read_text(encoding="utf-8"))
        base["etf_runs"]["reserve_size"] = 0  # force the backfill loop to run
        self.base_config = self.tmp / "config" / "dashboard_config.json"
        self.base_config.write_text(json.dumps(base), encoding="utf-8")
        self.fetch_calls: list[list[str]] = []

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _fake_fetch(self, config, tickers: list[str]) -> PriceLoadResult:
        self.fetch_calls.append(list(tickers))
        index = pd.bdate_range("2026-01-02", periods=130)
        rng = np.random.default_rng(len(self.fetch_calls))
        common = rng.normal(0, 0.01, len(index)).cumsum()
        data = {}
        for ticker in tickers:
            if ticker in self.UNPRICEABLE:
                data[ticker] = np.nan
            else:
                data[ticker] = 100 * np.exp(common + rng.normal(0, 0.01, len(index)).cumsum())
        prices = pd.DataFrame(data, index=index)
        return PriceLoadResult(prices=prices, metadata={"provider": "test", "tickers_requested": tickers})

    @staticmethod
    def _few_pairs(**kwargs):
        # Cointegration over C(N,2) pairs is slow and covered elsewhere; this test is about sizing.
        return ANALYZE_PAIRS(**{**kwargs, "tickers": kwargs["tickers"][:5]})

    def _run(self, count: int, *extra: str) -> tuple[pd.DataFrame, dict]:
        self.fetch_calls.clear()
        holdings = self.tmp / "ZZT_holdings.csv"
        _holdings_csv(holdings, count)
        argv = [
            "corrdash-etf", "--etf", "ZZT", "--holdings", str(holdings),
            "--base-config", str(self.base_config),
            "--history-period", "6mo", "--pairs-history-period", "3mo", *extra,
        ]
        with mock.patch.object(sys, "argv", argv), \
                mock.patch.object(sys.stdin, "isatty", return_value=False), \
                mock.patch.object(etf_command, "configure_tls"), \
                mock.patch.object(etf_command, "fetch_prices", side_effect=self._fake_fetch), \
                mock.patch.object(
                    etf_command, "resolve_ambiguous_symbols", side_effect=lambda h, **_: (h, [])
                ), \
                mock.patch.object(etf_command, "analyze_pairs", side_effect=self._few_pairs), \
                mock.patch("builtins.print"):
            etf_command.main()
        config = json.loads((self.tmp / "data" / "etf" / "ZZT" / "config.json").read_text(encoding="utf-8"))
        for key in ("universe_csv", "correlation_csv", "metadata_json", "excel_workbook", "pairs_workbook"):
            self.assertTrue((self.tmp / config["paths"][key]).exists(), key)
        correlation = pd.read_csv(self.tmp / config["paths"]["correlation_csv"], index_col=0)
        return correlation, config

    def test_default_top_50_by_weight_backfills_unpriceable(self) -> None:
        correlation, config = self._run(60)
        expected = [f"T{i:02d}" for i in range(1, 53) if f"T{i:02d}" not in self.UNPRICEABLE]
        self.assertEqual(correlation.shape, (50, 50))
        self.assertEqual(list(correlation.index), expected)
        # 50 fetched, 2 unpriceable, so the next two heaviest are fetched to backfill.
        self.assertEqual(self.fetch_calls, [[f"T{i:02d}" for i in range(1, 51)], ["T51", "T52"]])
        self.assertEqual(config["universe_policy"]["universe_size"], 50)
        self.assertEqual(config["universe_policy"]["requested_top_n"], 50)
        metadata = json.loads((self.tmp / config["paths"]["metadata_json"]).read_text(encoding="utf-8"))
        ranking = metadata["universe"]["ranking"]
        self.assertEqual(ranking["requested_top_n"], 50)
        self.assertEqual(ranking["equity_holdings_total"], 60)
        self.assertEqual(len(ranking["excluded_below_weight_cutoff"]), 8)

    def test_small_fund_adapts_below_requested(self) -> None:
        correlation, config = self._run(39)
        self.assertEqual(correlation.shape, (37, 37))  # 39 holdings minus 2 unpriceable
        self.assertEqual(config["universe_policy"]["requested_top_n"], 50)

    def test_user_can_ask_for_more_than_50(self) -> None:
        correlation, _ = self._run(80, "--top-n", "60")
        self.assertEqual(correlation.shape, (60, 60))
        correlation, config = self._run(80, "--top-n", "all")
        self.assertEqual(correlation.shape, (78, 78))
        self.assertEqual(config["universe_policy"]["requested_top_n"], "all")


if __name__ == "__main__":
    unittest.main()
