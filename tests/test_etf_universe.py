from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nasdaq_correlation_dashboard.etf_universe import (  # noqa: E402
    parse_holdings,
    read_holdings_file,
    resolve_ambiguous_symbols,
)
from nasdaq_correlation_dashboard.universe import UniverseSourceError  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "holdings"


def _by_source(holdings: pd.DataFrame) -> dict[str, pd.Series]:
    return {row["source_ticker"]: row for _, row in holdings.iterrows()}


class InvescoStyleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = read_holdings_file(FIXTURES / "invesco_style_export.csv")
        self.holdings, self.skipped = parse_holdings(self.frame)
        self.rows = _by_source(self.holdings)

    def test_uses_holding_ticker_not_fund_ticker(self) -> None:
        self.assertNotIn("TAN", self.holdings["ticker"].tolist())
        self.assertEqual(self.holdings.iloc[0]["ticker"], "FSLR")

    def test_cins_prefixes(self) -> None:
        self.assertEqual(self.rows["ENLT"]["ticker"], "ENLT.TA")  # M -> Israel
        self.assertEqual(self.rows["RNW"]["candidates"], ["RNW", "RNW.L", "RNW.HK"])  # G -> probe
        self.assertEqual(self.rows["6244"]["candidates"][:2], ["6244.TW", "6244.TWO"])  # Y -> probe
        self.assertIn("6244.HK", self.rows["6244"]["candidates"])  # HK candidate is zero-padded
        self.assertEqual(self.rows["FSLR"]["candidates"], ["FSLR"])  # numeric CUSIP -> US

    def test_non_equity_and_blank_ticker_are_reported(self) -> None:
        reasons = {item.get("name"): item["reason"] for item in self.skipped}
        self.assertEqual(reasons["US Dollar"], "non-equity line")
        self.assertEqual(reasons["Invesco Government & Agency Portfolio"], "non-equity line")
        daqo = next(item for item in self.skipped if item.get("name") == "Daqo New Energy Corp ADR")
        self.assertEqual(daqo["identifier"], "23703Q203")
        self.assertIn("--ticker-map 23703Q203=", daqo["reason"])
        self.assertEqual(len(self.holdings), 4)

    def test_ticker_map_by_identifier_recovers_blank_ticker(self) -> None:
        holdings, skipped = parse_holdings(self.frame, {"23703Q203": "DQ"})
        self.assertIn("DQ", holdings["ticker"].tolist())
        self.assertFalse(any(item.get("identifier") == "23703Q203" for item in skipped))

    def test_ticker_map_override_and_as_of(self) -> None:
        holdings, _ = parse_holdings(self.frame, {"RNW": "RNW"})
        self.assertEqual(_by_source(holdings)["RNW"]["candidates"], ["RNW"])
        self.assertEqual(self.holdings.attrs["as_of_date"], "2026-11-11")


class ISharesStyleTests(unittest.TestCase):
    def setUp(self) -> None:
        frame = read_holdings_file(FIXTURES / "ishares_style_export.csv")
        self.holdings, self.skipped = parse_holdings(frame)
        self.rows = _by_source(self.holdings)

    def test_preamble_footer_and_as_of(self) -> None:
        self.assertEqual(self.holdings.attrs["as_of_date"], "2026-11-11")
        self.assertEqual(self.holdings.iloc[0]["ticker"], "FSLR")

    def test_exchange_column_decides_suffix(self) -> None:
        self.assertEqual(self.rows["IBE"]["ticker"], "IBE.MC")
        self.assertEqual(self.rows["6244"]["ticker"], "6244.TWO")
        self.assertEqual(self.rows["968"]["ticker"], "0968.HK")
        self.assertEqual(self.rows["ENLT"]["ticker"], "ENLT.TA")
        self.assertEqual(self.rows["FUTR"]["ticker"], "FUTR.L")

    def test_asset_class_beats_name_keywords(self) -> None:
        # "Future plc" is an equity; the cash line and the futures contract are not.
        self.assertIn("FUTR", self.rows)
        skipped = {item["ticker"] for item in self.skipped}
        self.assertEqual(skipped, {"USD", "ESZ6"})


class CommentHeaderTests(unittest.TestCase):
    def test_comment_lines_and_existing_suffixes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "X_holdings.csv"
            path.write_text(
                "# Example fund holdings as of 11/11/2026\n"
                "Ticker,Name,Weight\n"
                "ENLT.TA,Enlight,5.0\n"
                "AAPL,Apple,4.0\n"
                "CASH,Cash Collateral,0.5\n",
                encoding="utf-8",
            )
            holdings, skipped = parse_holdings(read_holdings_file(path))
        self.assertEqual(holdings["ticker"].tolist(), ["ENLT.TA", "AAPL"])
        self.assertEqual(holdings.attrs["as_of_date"], "2026-11-11")
        self.assertEqual(skipped[0]["reason"], "non-equity line")

    def test_missing_columns_raise(self) -> None:
        with self.assertRaises(UniverseSourceError):
            parse_holdings(pd.DataFrame({"Name": ["A"], "Price": [1.0]}))


class SymbolProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        frame = read_holdings_file(FIXTURES / "invesco_style_export.csv")
        self.holdings, _ = parse_holdings(frame)

    def test_probe_picks_listed_candidate_and_caches(self) -> None:
        calls: list[list[str]] = []

        def probe(symbols: list[str]) -> set[str]:
            calls.append(symbols)
            return {"RNW", "6244.TWO"}

        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "symbol_map.json"
            resolved, report = resolve_ambiguous_symbols(self.holdings, cache, probe)
            rows = _by_source(resolved)
            self.assertEqual(rows["RNW"]["ticker"], "RNW")
            self.assertEqual(rows["6244"]["ticker"], "6244.TWO")
            self.assertEqual(len(calls), 1)  # one batched request
            self.assertEqual({item["how"] for item in report}, {"probe"})
            self.assertEqual(json.loads(cache.read_text(encoding="utf-8"))["6244|Y7T08J104"], "6244.TWO")

            def no_network(symbols: list[str]) -> set[str]:
                raise AssertionError("cached symbols must not be probed again")

            again, report = resolve_ambiguous_symbols(self.holdings, cache, no_network)
            self.assertEqual(_by_source(again)["6244"]["ticker"], "6244.TWO")
            self.assertEqual({item["how"] for item in report}, {"cache"})

    def test_probe_failure_keeps_first_guess(self) -> None:
        def broken(symbols: list[str]) -> set[str]:
            raise OSError("offline")

        resolved, report = resolve_ambiguous_symbols(self.holdings, None, broken)
        self.assertEqual(_by_source(resolved)["6244"]["ticker"], "6244.TW")
        self.assertEqual({item["how"] for item in report}, {"unverified first guess"})


if __name__ == "__main__":
    unittest.main()
