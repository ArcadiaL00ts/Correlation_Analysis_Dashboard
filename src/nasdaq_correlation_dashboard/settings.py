from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DashboardConfig:
    root: Path
    payload: dict[str, Any]

    @property
    def paths(self) -> dict[str, Path]:
        configured = self.payload["paths"]
        return {name: self.root / value for name, value in configured.items()}

    @property
    def universe_policy(self) -> dict[str, Any]:
        return dict(self.payload["universe_policy"])

    @property
    def history(self) -> dict[str, Any]:
        return dict(self.payload["history"])

    @property
    def validation(self) -> dict[str, Any]:
        return dict(self.payload["validation"])

    @property
    def analytics(self) -> dict[str, Any]:
        return dict(self.payload["analytics"])

    @property
    def pairs_trading(self) -> dict[str, Any]:
        return dict(self.payload["pairs_trading"])

    @property
    def rolling_windows(self) -> list[int]:
        return [int(value) for value in self.payload["analytics"]["rolling_windows"]]

    @property
    def price_source(self) -> dict[str, Any]:
        return dict(self.payload["price_source"])

    @property
    def visuals(self) -> dict[str, Any]:
        return dict(self.payload["visuals"])


def load_config(config_path: str | Path) -> DashboardConfig:
    config_file = Path(config_path).resolve()
    with config_file.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return DashboardConfig(root=_project_root(config_file), payload=payload)


def _project_root(config_file: Path) -> Path:
    """Nearest ancestor holding pyproject.toml, so configs can live in nested folders."""
    for candidate in config_file.parents:
        if (candidate / "pyproject.toml").exists():
            return candidate
    return config_file.parent.parent


def project_root() -> Path:
    """The checkout holding ``config/dashboard_config.json``.

    The package directory's checkout wins (editable install or running from source); otherwise the
    current working directory, so a regular install works when run from inside a clone.
    """
    package_checkout = Path(__file__).resolve().parents[2]
    if (package_checkout / "config" / "dashboard_config.json").exists():
        return package_checkout
    return Path.cwd()


def default_config_path() -> Path:
    return project_root() / "config" / "dashboard_config.json"
