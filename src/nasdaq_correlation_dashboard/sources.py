from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .settings import DashboardConfig


class DataSourceError(RuntimeError):
    """Raised when a market-data provider cannot deliver a valid dataset."""


@dataclass
class PriceLoadResult:
    prices: pd.DataFrame
    metadata: dict[str, Any]


def _normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    cleaned = frame.copy()
    cleaned.index = pd.to_datetime(cleaned.index, utc=False)
    cleaned = cleaned.sort_index()
    cleaned = cleaned[~cleaned.index.duplicated(keep="last")]
    cleaned.columns = [str(column).upper() for column in cleaned.columns]
    return cleaned


def fetch_prices(config: DashboardConfig, tickers: list[str]) -> PriceLoadResult:
    provider = config.price_source["provider"]
    if provider == "yfinance":
        try:
            return _fetch_from_yfinance(config, tickers)
        except Exception as exc:
            fallback = config.price_source.get("fallback_provider")
            if fallback != "csv_directory":
                raise
            result = _fetch_from_csv_directory(config, tickers)
            result.metadata["provider_error"] = str(exc)
            result.metadata["provider_warning"] = "Primary provider failed; csv fallback used."
            return result
    if provider == "csv_directory":
        return _fetch_from_csv_directory(config, tickers)
    raise DataSourceError(f"Unsupported provider: {provider}")


def _fetch_from_yfinance(config: DashboardConfig, tickers: list[str]) -> PriceLoadResult:
    import yfinance as yf

    history = config.history
    raw = yf.download(
        tickers=tickers,
        period=history["period"],
        interval=history["interval"],
        auto_adjust=False,
        actions=False,
        progress=False,
        threads=True,
    )
    if raw.empty:
        raise DataSourceError("yfinance returned an empty dataset.")

    price_field = config.price_source["price_field"]
    if isinstance(raw.columns, pd.MultiIndex):
        if price_field not in raw.columns.get_level_values(0):
            raise DataSourceError(f"Expected field '{price_field}' in yfinance dataset.")
        prices = raw[price_field]
    else:
        prices = raw.rename(columns={price_field: tickers[0]})[[tickers[0]]]

    prices = _normalize_frame(prices)
    return PriceLoadResult(
        prices=prices,
        metadata={
            "provider": "yfinance",
            "price_field": price_field,
            "period": history["period"],
            "interval": history["interval"],
            "tickers_requested": tickers,
        },
    )


def _fetch_from_csv_directory(config: DashboardConfig, tickers: list[str]) -> PriceLoadResult:
    csv_dir = (config.root / config.price_source["csv_directory"]).resolve()
    if not csv_dir.exists():
        raise DataSourceError(f"Fallback directory does not exist: {csv_dir}")

    frames: list[pd.Series] = []
    price_field = config.price_source["price_field"]
    for ticker in tickers:
        candidate = csv_dir / f"{ticker}.csv"
        if not candidate.exists():
            raise DataSourceError(f"Missing fallback csv for {ticker}: {candidate}")
        series = pd.read_csv(candidate, parse_dates=["Date"])
        if price_field not in series.columns and "Close" not in series.columns:
            raise DataSourceError(
                f"{candidate} must contain '{price_field}' or 'Close' columns."
            )
        selected = price_field if price_field in series.columns else "Close"
        frames.append(series.set_index("Date")[selected].rename(ticker))

    prices = pd.concat(frames, axis=1)
    prices = _normalize_frame(prices)
    return PriceLoadResult(
        prices=prices,
        metadata={
            "provider": "csv_directory",
            "price_field": price_field,
            "directory": str(csv_dir),
            "tickers_requested": tickers,
        },
    )


def validate_prices(prices: pd.DataFrame, tickers: list[str], config: DashboardConfig) -> dict[str, Any]:
    minimum_rows = int(config.validation["minimum_rows"])
    if len(prices) < minimum_rows:
        raise DataSourceError(
            f"Expected at least {minimum_rows} rows, received {len(prices)} rows."
        )

    missing_ratio = float(prices.isna().mean().max())
    allowed_ratio = float(config.validation["maximum_missing_ratio"])
    if missing_ratio > allowed_ratio:
        raise DataSourceError(
            f"Maximum missing ratio {missing_ratio:.2%} exceeds allowed {allowed_ratio:.2%}."
        )

    missing_tickers = set(tickers) - set(prices.columns)
    if missing_tickers:
        raise DataSourceError(f"Missing tickers from price frame: {sorted(missing_tickers)}")

    return {
        "minimum_rows": minimum_rows,
        "observed_rows": int(len(prices)),
        "maximum_missing_ratio": allowed_ratio,
        "observed_missing_ratio": missing_ratio,
    }


def write_metadata(metadata: dict[str, Any], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)
