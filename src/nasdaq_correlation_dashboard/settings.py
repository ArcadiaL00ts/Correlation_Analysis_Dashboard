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
    return DashboardConfig(root=config_file.parent.parent, payload=payload)
