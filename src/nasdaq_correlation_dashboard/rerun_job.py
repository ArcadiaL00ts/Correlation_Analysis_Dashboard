"""Background pipeline re-run for the dashboard: one job at a time, state kept on disk.

The dashboard starts ``python -m nasdaq_correlation_dashboard.rerun_job ... -- <pipeline command>``
as a detached process. Three files in the run's data directory hold the state, so a page reload,
a second browser or a Streamlit script restart all see the same job:

- ``.rerun.lock``: created exclusively before launch; a second start is refused while its PID lives.
- ``rerun_status.json``: ``{state, pid, started_at, finished_at, exit_code, price_period, pair_period}``.
- ``rerun.log``: the pipeline's combined stdout/stderr.

A lock whose process has died is treated as stale and cleared.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LOCK_NAME = ".rerun.lock"
STATUS_NAME = "rerun_status.json"
LOG_NAME = "rerun.log"
# A freshly created lock has no wrapper PID yet; give the wrapper this long to record it.
STARTUP_GRACE_SECONDS = 30


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def lock_path(job_dir: Path) -> Path:
    return Path(job_dir) / LOCK_NAME


def status_path(job_dir: Path) -> Path:
    return Path(job_dir) / STATUS_NAME


def log_path(job_dir: Path) -> Path:
    return Path(job_dir) / LOG_NAME


def pid_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        # A finished child we launched stays a zombie (and answers kill(0)) until reaped.
        reaped, _ = os.waitpid(int(pid), os.WNOHANG)
        if reaped == int(pid):
            return False
    except ChildProcessError:
        pass  # not our child (or already reaped)
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    for attempt in range(20):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:  # Windows: a reader has the file open for a moment
            time.sleep(0.05 * (attempt + 1))
    os.replace(tmp, path)


def _read_json(path: Path) -> dict[str, Any]:
    for _ in range(5):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (json.JSONDecodeError, PermissionError):
            time.sleep(0.05)
    return {}


def _lock_pid(job_dir: Path) -> tuple[int | None, float | None]:
    path = lock_path(job_dir)
    try:
        text = path.read_text(encoding="utf-8").strip()
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        return None, None
    try:
        return int(text), mtime
    except ValueError:
        return None, mtime


def _lock_is_live(job_dir: Path) -> bool:
    pid, mtime = _lock_pid(job_dir)
    if mtime is None:
        return False
    if pid_alive(pid):
        return True
    return pid is None and (time.time() - mtime) < STARTUP_GRACE_SECONDS


def read_status(job_dir: Path) -> dict[str, Any]:
    """Current job status; a running job whose process vanished is marked failed and unlocked."""
    job_dir = Path(job_dir)
    status = _read_json(status_path(job_dir))
    if status.get("state") == "running" and not _lock_is_live(job_dir):
        status.update(
            state="failed",
            finished_at=status.get("finished_at") or _now(),
            exit_code=status.get("exit_code"),
            error="The re-run process ended without reporting a result (killed or crashed).",
        )
        _write_json(status_path(job_dir), status)
        lock_path(job_dir).unlink(missing_ok=True)
    elif status.get("state") != "running" and lock_path(job_dir).exists() and not _lock_is_live(job_dir):
        lock_path(job_dir).unlink(missing_ok=True)
    return status


def start_job(
    job_dir: Path,
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    labels: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    """Launch ``command`` in the background. Returns ``(started, message)``."""
    job_dir = Path(job_dir)
    job_dir.mkdir(parents=True, exist_ok=True)
    read_status(job_dir)  # clears a stale lock
    try:
        fd = os.open(lock_path(job_dir), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False, "A re-run is already in progress for this dashboard."
    os.close(fd)

    status: dict[str, Any] = {
        "state": "running",
        "pid": None,
        "started_at": _now(),
        "finished_at": None,
        "exit_code": None,
        "command": command,
        **(labels or {}),
    }
    _write_json(status_path(job_dir), status)
    wrapper = [
        sys.executable,
        "-m",
        "nasdaq_correlation_dashboard.rerun_job",
        "--job-dir",
        str(job_dir),
        "--",
        *command,
    ]
    popen_kwargs: dict[str, Any] = {
        "cwd": str(cwd),
        "env": env,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if sys.platform == "win32":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    else:
        popen_kwargs["start_new_session"] = True
    try:
        process = subprocess.Popen(wrapper, **popen_kwargs)
    except OSError as exc:
        status.update(state="failed", finished_at=_now(), error=f"Could not start the re-run: {exc}")
        _write_json(status_path(job_dir), status)
        lock_path(job_dir).unlink(missing_ok=True)
        return False, status["error"]
    lock_path(job_dir).write_text(str(process.pid), encoding="utf-8")
    current = _read_json(status_path(job_dir))
    if current.get("state") == "running" and current.get("started_at") == status["started_at"]:
        current["pid"] = process.pid
        _write_json(status_path(job_dir), current)
    return True, "Re-run started."


def cancel_job(job_dir: Path) -> bool:
    """Kill the running job (and the pipeline under it). Returns True if something was stopped."""
    job_dir = Path(job_dir)
    status = _read_json(status_path(job_dir))
    pid = status.get("pid") or _lock_pid(job_dir)[0]
    stopped = False
    if pid and pid_alive(pid):
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)
        else:
            try:
                os.killpg(os.getpgid(int(pid)), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
        stopped = True
    if status.get("state") == "running":
        status.update(state="cancelled", finished_at=_now())
        _write_json(status_path(job_dir), status)
    lock_path(job_dir).unlink(missing_ok=True)
    return stopped


def log_tail(job_dir: Path, lines: int = 20) -> str:
    try:
        text = log_path(job_dir).read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""
    return "\n".join(text.splitlines()[-lines:])


def _run_wrapper(job_dir: Path, command: list[str]) -> int:
    lock_path(job_dir).write_text(str(os.getpid()), encoding="utf-8")
    status = _read_json(status_path(job_dir))
    status.update(pid=os.getpid(), state="running")
    _write_json(status_path(job_dir), status)
    exit_code = 1
    try:
        with log_path(job_dir).open("w", encoding="utf-8", errors="replace") as log:
            exit_code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
    finally:
        status = _read_json(status_path(job_dir))
        if status.get("state") == "running":
            status.update(
                state="succeeded" if exit_code == 0 else "failed",
                exit_code=exit_code,
                finished_at=_now(),
            )
            _write_json(status_path(job_dir), status)
        lock_path(job_dir).unlink(missing_ok=True)
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a dashboard pipeline job and record its status.")
    parser.add_argument("--job-dir", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("missing pipeline command after --")
    return _run_wrapper(Path(args.job_dir), command)


if __name__ == "__main__":
    raise SystemExit(main())
