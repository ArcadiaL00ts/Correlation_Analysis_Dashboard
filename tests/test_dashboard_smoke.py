from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

from fixture_artifacts import build_fixture  # noqa: E402

APP = SRC / "nasdaq_correlation_dashboard" / "dashboard.py"


def _offline_yfinance() -> types.ModuleType:
    module = types.ModuleType("yfinance")

    def unavailable(*args, **kwargs):
        raise ConnectionError("offline test: yfinance disabled")

    module.download = unavailable
    module.Ticker = unavailable
    return module


class _OfflineYFinance:
    """Swap only the ``yfinance`` entry in sys.modules (patch.dict would also unload plotly
    submodules imported during the run, leaving two incompatible copies of its classes)."""

    def __enter__(self):
        self._saved = sys.modules.get("yfinance")
        sys.modules["yfinance"] = _offline_yfinance()

    def __exit__(self, *exc):
        if self._saved is None:
            sys.modules.pop("yfinance", None)
        else:
            sys.modules["yfinance"] = self._saved


class DashboardSmokeTests(unittest.TestCase):
    """Render the real Streamlit app headlessly against fixture artifacts."""

    def _run(self, **fixture_kwargs):
        from streamlit.testing.v1 import AppTest

        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        config_path = build_fixture(Path(tmp.name), **fixture_kwargs)
        env = {"DASHBOARD_CONFIG": str(config_path), "DASHBOARD_SKIP_TLS_PROBE": "1"}
        with mock.patch.dict(os.environ, env), _OfflineYFinance():
            app = AppTest.from_file(str(APP), default_timeout=120).run()
        return app

    def test_full_window_renders_all_tabs(self) -> None:
        app = self._run(rows=300)
        self.assertEqual([e.value for e in app.exception], [])
        self.assertEqual(len(app.tabs), 5)
        self.assertTrue(any("Lookback" in expander.label for expander in app.expander))

    def test_one_week_window_with_no_qualified_pairs(self) -> None:
        # 5 prices -> 4 returns; below the 20-observation cointegration floor, so spreads are empty.
        app = self._run(rows=5, price_period="5d", pair_period="1mo")
        self.assertEqual([e.value for e in app.exception], [])
        self.assertEqual(len(app.tabs), 5)

    def test_rerun_panel_can_be_disabled(self) -> None:
        from streamlit.testing.v1 import AppTest

        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        config_path = build_fixture(Path(tmp.name), rows=60)
        payload = config_path.read_text(encoding="utf-8").replace('"enable_rerun": true', '"enable_rerun": false')
        config_path.write_text(payload, encoding="utf-8")
        env = {"DASHBOARD_CONFIG": str(config_path), "DASHBOARD_SKIP_TLS_PROBE": "1"}
        with mock.patch.dict(os.environ, env), _OfflineYFinance():
            app = AppTest.from_file(str(APP), default_timeout=120).run()
        self.assertEqual([e.value for e in app.exception], [])
        self.assertFalse(any("Lookback" in expander.label for expander in app.expander))


if __name__ == "__main__":
    unittest.main()
