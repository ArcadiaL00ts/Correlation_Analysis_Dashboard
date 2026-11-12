from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path




def _listening_pids(port: int) -> list[int]:
    """PIDs listening on ``port`` (best effort; empty if the OS tool is unavailable)."""
    if sys.platform == "win32":
        command = (
            f"Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue | "
            "Select-Object -ExpandProperty OwningProcess -Unique"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True, check=False
        )
    elif shutil.which("lsof"):
        result = subprocess.run(
            ["lsof", "-t", f"-iTCP:{port}", "-sTCP:LISTEN"], capture_output=True, text=True, check=False
        )
    else:
        return []
    return sorted({int(line) for line in result.stdout.split() if line.strip().isdigit()})


def _command_line(pid: int) -> str:
    if sys.platform == "win32":
        command = f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine"
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True, check=False
        )
    else:
        result = subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True, check=False)
    return result.stdout.strip()


def _free_port(port: int) -> None:
    """Stop an earlier copy of this dashboard on ``port``; refuse to touch anything else."""
    for pid in _listening_pids(port):
        if pid == os.getpid():
            continue
        command_line = _command_line(pid)
        if "streamlit" in command_line and "nasdaq_correlation_dashboard" in command_line:
            print(f"Stopping the previous dashboard on port {port} (PID {pid}).")
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)
            else:
                subprocess.run(["kill", str(pid)], capture_output=True, check=False)
        else:
            raise SystemExit(
                f"Port {port} is in use by another program (PID {pid}). Choose a different one with --port."
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch the Streamlit correlation dashboard.")
    parser.add_argument(
        "--config",
        help="Alternate config to display, e.g. data/etf/TAN/config.json from run_etf_correlation.py.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("DASHBOARD_PORT", "8505").strip() or "8505"),
        help="Port to serve on (default 8505, or DASHBOARD_PORT). Only a dashboard already on this port is restarted.",
    )
    args = parser.parse_args()
    streamlit = shutil.which("streamlit")
    app_path = Path(__file__).resolve().parents[1] / "dashboard.py"
    _free_port(args.port)
    port = str(args.port)
    env = os.environ.copy()
    src_root = str(Path(__file__).resolve().parents[2])
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = src_root if not existing else f"{src_root}{os.pathsep}{existing}"
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
