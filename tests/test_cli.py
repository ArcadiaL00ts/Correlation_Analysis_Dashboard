from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nasdaq_correlation_dashboard.cli import (  # noqa: E402
    period_label,
    resolve_history_period,
    scaled_minimum_rows,
    scaled_window,
)

CHOICES = ["5d", "1mo", "3mo", "6mo", "1y", "2y"]


class ResolveHistoryPeriodTests(unittest.TestCase):
    def test_aliases(self) -> None:
        for alias, code in {"1w": "5d", "1m": "1mo", "3m": "3mo", "6m": "6mo", "1W": "5d"}.items():
            self.assertEqual(resolve_history_period(alias, "1y", CHOICES, "lookback"), code)

    def test_cli_value_wins_and_config_is_default(self) -> None:
        self.assertEqual(resolve_history_period("2y", "1y", CHOICES, "lookback"), "2y")
        with mock.patch.object(sys.stdin, "isatty", return_value=False):
            self.assertEqual(resolve_history_period(None, "1y", CHOICES, "lookback"), "1y")

    def test_interactive_prompt_and_eof(self) -> None:
        with mock.patch.object(sys.stdin, "isatty", return_value=True):
            with mock.patch("builtins.input", return_value="3m"):
                self.assertEqual(resolve_history_period(None, "1y", CHOICES, "lookback"), "3mo")
            with mock.patch("builtins.input", side_effect=EOFError):
                self.assertEqual(resolve_history_period(None, "1y", CHOICES, "lookback"), "1y")

    def test_invalid_period_exits(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            resolve_history_period("7w", "1y", CHOICES, "price-history lookback")
        self.assertIn("Unsupported price-history lookback '7w'", str(raised.exception))

    def test_labels(self) -> None:
        self.assertEqual([period_label(p) for p in ["5d", "1mo", "3mo", "6mo", "1y"]], ["1w", "1m", "3m", "6m", "1y"])


class ScalingTests(unittest.TestCase):
    def test_scaled_minimum_rows(self) -> None:
        self.assertEqual(scaled_minimum_rows("5d", 252), 4)
        self.assertEqual(scaled_minimum_rows("1mo", 252), 18)
        self.assertEqual(scaled_minimum_rows("2y", 252), 252)  # capped at the configured minimum
        self.assertEqual(scaled_minimum_rows("max", 252), 252)

    def test_scaled_window(self) -> None:
        self.assertEqual(scaled_window("1mo", 60), 10)
        self.assertEqual(scaled_window("5d", 60), 5)  # floor
        self.assertEqual(scaled_window("2y", 60), 60)


if __name__ == "__main__":
    unittest.main()
