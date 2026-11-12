"""Shim for ``corrdash-update``; the implementation lives in nasdaq_correlation_dashboard.commands.update."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nasdaq_correlation_dashboard.commands.update import main  # noqa: E402

if __name__ == "__main__":
    main()
