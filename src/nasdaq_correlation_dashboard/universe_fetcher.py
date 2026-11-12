from __future__ import annotations

from pathlib import Path
from typing import Any

from .settings import load_config
from .universe import resolve_universe


def refresh_universe(
    config_path: str | Path,
    top_n: int = 50,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Preview the currently resolved universe without mutating config state.

    Args:
        config_path: Path to `dashboard_config.json`.
        top_n: Number of ranked names to return from the resolved universe.
        dry_run: Kept for backwards compatibility. The function is always non-mutating.

    Returns:
        A summary dict with the resolved tickers and provenance metadata.
    """

    config = load_config(config_path)
    selection = resolve_universe(config)
    preview = selection.universe.head(top_n)

    return {
        "proposed_tickers": preview["ticker"].tolist(),
        "snapshot_date": selection.metadata["official_source"]["trade_date"],
        "ranking_source": selection.metadata["ranking"]["source_type"],
        "fallback_used": selection.metadata["ranking"]["fallback_used"],
        "diff": {
            "added": [],
            "removed": [],
            "unchanged": preview["ticker"].tolist(),
        },
        "applied": False,
        "warning": None,
        "dry_run": dry_run,
    }
