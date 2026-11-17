from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nasdaq_correlation_dashboard.commands import app  # noqa: E402


class AppLauncherAddressTests(unittest.TestCase):
    def _launch(self, argv: list[str], env: dict[str, str] | None = None, which: str | None = "streamlit") -> list[str]:
        environ = {k: v for k, v in os.environ.items() if k != "DASHBOARD_ADDRESS"}
        environ.update(env or {})
        with mock.patch.object(sys, "argv", ["corrdash-app", *argv]), \
                mock.patch.dict(os.environ, environ, clear=True), \
                mock.patch.object(app.shutil, "which", return_value=which), \
                mock.patch.object(app, "_free_port"), \
                mock.patch.object(app.subprocess, "run") as run, \
                mock.patch("builtins.print"):
            app.main()
        return run.call_args.args[0]

    @staticmethod
    def _address(command: list[str]) -> str:
        return command[command.index("--server.address") + 1]

    def test_defaults_to_localhost(self) -> None:
        self.assertEqual(self._address(self._launch([])), "127.0.0.1")
        self.assertEqual(self._address(self._launch([], which=None)), "127.0.0.1")

    def test_lan_flag_binds_all_interfaces(self) -> None:
        command = self._launch(["--lan", "--port", "8599"])
        self.assertEqual(self._address(command), "0.0.0.0")
        self.assertEqual(command[command.index("--server.port") + 1], "8599")

    def test_env_override(self) -> None:
        self.assertEqual(self._address(self._launch([], env={"DASHBOARD_ADDRESS": "192.168.1.5"})), "192.168.1.5")

    def test_python_module_fallback_has_same_arguments(self) -> None:
        binary = self._launch([])
        module = self._launch([], which=None)
        self.assertEqual(module[:3], [sys.executable, "-m", "streamlit"])
        self.assertEqual(binary[1:], module[3:])


if __name__ == "__main__":
    unittest.main()
