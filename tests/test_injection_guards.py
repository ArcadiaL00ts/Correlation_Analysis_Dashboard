from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from openpyxl import Workbook, load_workbook

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nasdaq_correlation_dashboard.dashboard import _definition_card, _esc, _status_card  # noqa: E402
from nasdaq_correlation_dashboard.excel_export import _write_frame, safe_cell, safe_frame  # noqa: E402

PAYLOAD = '=HYPERLINK("http://x","y")'


class FormulaInjectionTests(unittest.TestCase):
    def test_safe_cell(self) -> None:
        for risky in (PAYLOAD, "+1", "-1+2", "@SUM(A1)", "\tx", "\rx"):
            self.assertEqual(safe_cell(risky), "'" + risky)
        self.assertEqual(safe_cell("AAPL"), "AAPL")
        self.assertEqual(safe_cell(-0.42), -0.42)
        self.assertIsInstance(safe_cell(-0.42), float)

    def test_write_frame_neutralises_strings_and_keeps_numbers(self) -> None:
        frame = pd.DataFrame({"company": [PAYLOAD, "Apple"], "correlation": [-0.5, 0.25]})
        workbook = Workbook()
        _write_frame(workbook.active, frame, "ticker", include_index=False)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.xlsx"
            workbook.save(path)
            sheet = load_workbook(path).active
            self.assertEqual(sheet["A2"].data_type, "s")
            self.assertTrue(str(sheet["A2"].value).startswith("'"))
            self.assertEqual(sheet["B2"].value, -0.5)
            self.assertIsInstance(sheet["B2"].value, float)

    def test_safe_frame(self) -> None:
        frame = pd.DataFrame({"pair": [PAYLOAD, "AAPL / MSFT"], "zscore": [-1.5, 2.0]})
        result = safe_frame(frame)
        self.assertEqual(result["pair"].tolist(), ["'" + PAYLOAD, "AAPL / MSFT"])
        self.assertEqual(result["zscore"].tolist(), [-1.5, 2.0])
        self.assertEqual(frame["pair"].iloc[0], PAYLOAD)  # original untouched


class HtmlEscapeTests(unittest.TestCase):
    def test_cards_escape_values(self) -> None:
        ticker = "<img src=x onerror=1>"
        self.assertEqual(_esc(ticker), "&lt;img src=x onerror=1&gt;")
        card = _status_card("Pair Readout", [f"Pair: {ticker}"])
        self.assertNotIn("<img", card)
        self.assertIn("&lt;img src=x onerror=1&gt;</span>", card)
        definition = _definition_card("Guide", [("ADF", "<script>x</script>")])
        self.assertNotIn("<script>", definition)
        self.assertIn("<strong>ADF:</strong>", definition)


if __name__ == "__main__":
    unittest.main()
