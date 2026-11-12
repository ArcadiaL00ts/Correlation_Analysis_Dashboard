"""Atomic artifact writes: write to a temp file beside the target, then ``os.replace``.

The dashboard re-reads artifacts on every interaction while a background re-run may be writing
them, so a reader must never see a half-written CSV, JSON or workbook.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pandas as pd


def replace_with_retry(source: Path, target: Path, attempts: int = 20) -> None:
    for attempt in range(attempts):
        try:
            os.replace(source, target)
            return
        except PermissionError:  # Windows: a reader holds the target open for a moment
            if attempt == attempts - 1:
                raise
            time.sleep(0.05 * (attempt + 1))


@contextmanager
def atomic_target(path: str | Path) -> Iterator[Path]:
    """Yield a temp path (same directory and suffix) that replaces ``path`` on success."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.stem}.{os.getpid()}.tmp{target.suffix}")
    try:
        yield tmp
        replace_with_retry(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)


def write_csv(frame: pd.DataFrame, path: str | Path, **kwargs: Any) -> None:
    with atomic_target(path) as tmp:
        frame.to_csv(tmp, **kwargs)


def write_json(payload: Any, path: str | Path) -> None:
    with atomic_target(path) as tmp:
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def copy_file(source: str | Path, path: str | Path) -> None:
    import shutil

    with atomic_target(path) as tmp:
        shutil.copy2(source, tmp)
