from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from .settings import DashboardConfig


@dataclass
class CorrelationArtifacts:
    prices: pd.DataFrame
    returns: pd.DataFrame
    correlation: pd.DataFrame
    metadata: dict[str, Any]


def build_artifacts(
    prices: pd.DataFrame,
    price_source_metadata: dict[str, Any],
    universe_metadata: dict[str, Any],
    validation_metadata: dict[str, Any],
    config: DashboardConfig,
) -> CorrelationArtifacts:
    history = config.history
    method = history["return_method"].lower()
    if method == "log":
        returns = np.log(prices / prices.shift(1))
    elif method == "simple":
        returns = prices.pct_change()
    else:
        raise ValueError(f"Unsupported return_method: {method}")

    returns = returns.dropna(how="all")
    returns = returns.dropna(axis=0, how="any")
    correlation = returns.corr(method=history["correlation_method"]).round(6)

    metadata = {
        "project_name": config.payload["project_name"],
        "created_at_utc": datetime.now(UTC).isoformat(),
        "tickers": list(prices.columns),
        "start_date": str(prices.index.min().date()),
        "end_date": str(prices.index.max().date()),
        "return_method": history["return_method"],
        "correlation_method": history["correlation_method"],
        "rows": int(len(prices)),
        "return_rows": int(len(returns)),
        "analytics": config.analytics,
        "validation": validation_metadata,
        "universe": universe_metadata,
        "prices": price_source_metadata,
    }
    return CorrelationArtifacts(
        prices=prices,
        returns=returns,
        correlation=correlation,
        metadata=metadata,
    )


def ranked_pairs(
    correlation: pd.DataFrame,
    limit: int,
    ascending: bool = False,
) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for left in correlation.columns:
        for right in correlation.columns:
            if left == right:
                continue
            key = tuple(sorted((left, right)))
            if key in seen:
                continue
            seen.add(key)
            value = float(correlation.loc[left, right])
            pairs.append({"pair": f"{key[0]} vs {key[1]}", "correlation": value})
    ordered = sorted(pairs, key=lambda item: item["correlation"], reverse=not ascending)
    return ordered[:limit]


def correlation_change_table(
    current: pd.DataFrame,
    previous: pd.DataFrame,
) -> pd.DataFrame:
    common_tickers = sorted(set(current.columns).intersection(previous.columns))
    columns = [
        "pair",
        "left",
        "right",
        "current_correlation",
        "previous_correlation",
        "change",
        "abs_change",
    ]
    if len(common_tickers) < 2:
        return pd.DataFrame(columns=columns)

    current_common = current.loc[common_tickers, common_tickers]
    previous_common = previous.loc[common_tickers, common_tickers]

    rows: list[dict[str, Any]] = []
    for index, left in enumerate(common_tickers):
        for right in common_tickers[index + 1 :]:
            current_value = float(current_common.loc[left, right])
            previous_value = float(previous_common.loc[left, right])
            change = current_value - previous_value
            rows.append(
                {
                    "pair": f"{left} vs {right}",
                    "left": left,
                    "right": right,
                    "current_correlation": current_value,
                    "previous_correlation": previous_value,
                    "change": change,
                    "abs_change": abs(change),
                }
            )

    if not rows:
        return pd.DataFrame(columns=columns)

    return pd.DataFrame(rows, columns=columns).sort_values(
        ["abs_change", "change", "pair"],
        ascending=[False, False, True],
    ).reset_index(drop=True)


def average_pairwise_correlation(correlation: pd.DataFrame) -> float:
    if correlation.empty:
        return float("nan")
    mask = ~np.eye(len(correlation), dtype=bool)
    values = correlation.to_numpy()[mask]
    return float(values.mean()) if len(values) else float("nan")


def rolling_average_correlation(returns: pd.DataFrame, window: int) -> pd.Series:
    values: list[float] = []
    dates: list[pd.Timestamp] = []
    for index in range(window - 1, len(returns)):
        sample = returns.iloc[index - window + 1 : index + 1]
        correlation = sample.corr()
        values.append(average_pairwise_correlation(correlation))
        dates.append(returns.index[index])
    return pd.Series(values, index=dates, name=f"avg_corr_{window}")


def pair_correlation_series(
    returns: pd.DataFrame,
    left: str,
    right: str,
    window: int,
) -> pd.Series:
    return returns[left].rolling(window).corr(returns[right]).dropna()
