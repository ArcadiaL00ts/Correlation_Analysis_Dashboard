from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"


def _cleanup_stale_dashboard_processes(app_path: Path) -> None:
    if sys.platform != "win32":
        return
    command = (
        "$self = $PID; "
        "Get-CimInstance Win32_Process | "
        "Where-Object { "
        "$_.Name -eq 'python.exe' -and "
        "$_.ProcessId -ne $self -and "
        "$_.CommandLine -like '*streamlit*' -and "
        "$_.CommandLine -like '*nasdaq_correlation_dashboard*' -and "
        "$_.CommandLine -like '*dashboard.py*' "
        "} | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        check=False,
        capture_output=True,
        text=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch the Streamlit correlation dashboard.")
    parser.add_argument(
        "--config",
        help="Alternate config to display, e.g. data/etf/TAN/config.json from run_etf_correlation.py.",
    )
    args = parser.parse_args()
    streamlit = shutil.which("streamlit")
    app_path = SRC_ROOT / "nasdaq_correlation_dashboard" / "dashboard.py"
    _cleanup_stale_dashboard_processes(app_path)

    port = os.environ.get("DASHBOARD_PORT", "8505").strip() or "8505"
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(SRC_ROOT) if not existing else f"{SRC_ROOT}{os.pathsep}{existing}"
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    if args.config:
        env["DASHBOARD_CONFIG"] = str(Path(args.config).resolve())
    if streamlit is not None:
        command = [
            streamlit,
            "run",
            str(app_path),
            "--browser.gatherUsageStats",
            "false",
            "--server.port",
            port,
            "--server.headless",
            "false",
        ]
    else:
        command = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(app_path),
            "--browser.gatherUsageStats",
            "false",
            "--server.port",
            port,
            "--server.headless",
            "false",
        ]
    print(f"Starting dashboard at http://localhost:{port}")
    subprocess.run(command, check=True, env=env)


if __name__ == "__main__":
    main()
