from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nasdaq_correlation_dashboard import rerun_job  # noqa: E402


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return env


def _wait_for(job_dir: Path, states: set[str], timeout: float = 30.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = rerun_job.read_status(job_dir)
        if status.get("state") in states:
            return status
        time.sleep(0.2)
    raise AssertionError(f"job did not reach {states}: {rerun_job.read_status(job_dir)}")


class RerunJobTests(unittest.TestCase):
    def setUp(self) -> None:
        # Jobs are detached on purpose; the Popen handle is dropped while the wrapper runs.
        warnings.simplefilter("ignore", ResourceWarning)
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.job_dir = Path(self._tmp.name)

    def tearDown(self) -> None:
        pid = rerun_job.read_status(self.job_dir).get("pid")
        rerun_job.cancel_job(self.job_dir)
        deadline = time.time() + 10
        while pid and rerun_job.pid_alive(pid) and time.time() < deadline:
            time.sleep(0.1)
        time.sleep(0.2)  # Windows releases file handles just after the process exits
        self._tmp.cleanup()

    def _start(self, code: str, **labels) -> tuple[bool, str]:
        return rerun_job.start_job(
            self.job_dir, [sys.executable, "-c", code], cwd=ROOT, env=_env(), labels=labels
        )

    def test_success_records_status_and_log_and_releases_lock(self) -> None:
        started, _ = self._start("print('pipeline ran')", price_period="1y")
        self.assertTrue(started)
        status = _wait_for(self.job_dir, {"succeeded", "failed"})
        self.assertEqual(status["state"], "succeeded")
        self.assertEqual(status["exit_code"], 0)
        self.assertEqual(status["price_period"], "1y")
        self.assertIn("pipeline ran", rerun_job.log_tail(self.job_dir))
        self.assertFalse(rerun_job.lock_path(self.job_dir).exists())

    def test_failure_is_reported(self) -> None:
        self._start("import sys; print('boom'); sys.exit(3)")
        status = _wait_for(self.job_dir, {"succeeded", "failed"})
        self.assertEqual((status["state"], status["exit_code"]), ("failed", 3))
        self.assertIn("boom", rerun_job.log_tail(self.job_dir))

    def test_second_start_is_refused_while_running(self) -> None:
        started, _ = self._start("import time; time.sleep(30)")
        self.assertTrue(started)
        again, message = self._start("print('second')")
        self.assertFalse(again)
        self.assertIn("already in progress", message)

    def test_cancel_stops_job(self) -> None:
        self._start("import time; time.sleep(30)")
        _wait_for(self.job_dir, {"running"})
        deadline = time.time() + 15
        while not rerun_job.read_status(self.job_dir).get("pid") and time.time() < deadline:
            time.sleep(0.1)
        pid = rerun_job.read_status(self.job_dir)["pid"]
        self.assertTrue(rerun_job.cancel_job(self.job_dir))
        self.assertEqual(rerun_job.read_status(self.job_dir)["state"], "cancelled")
        deadline = time.time() + 10
        while rerun_job.pid_alive(pid) and time.time() < deadline:
            time.sleep(0.1)
        self.assertFalse(rerun_job.pid_alive(pid))
        self.assertFalse(rerun_job.lock_path(self.job_dir).exists())

    def test_stale_lock_from_dead_process_is_cleared(self) -> None:
        rerun_job.lock_path(self.job_dir).write_text("999999", encoding="utf-8")
        rerun_job.status_path(self.job_dir).write_text(
            json.dumps({"state": "running", "pid": 999999, "started_at": "2026-01-01T00:00:00+00:00"}),
            encoding="utf-8",
        )
        status = rerun_job.read_status(self.job_dir)
        self.assertEqual(status["state"], "failed")
        self.assertFalse(rerun_job.lock_path(self.job_dir).exists())
        started, _ = self._start("print('ok')")
        self.assertTrue(started)
        _wait_for(self.job_dir, {"succeeded"})


if __name__ == "__main__":
    unittest.main()
