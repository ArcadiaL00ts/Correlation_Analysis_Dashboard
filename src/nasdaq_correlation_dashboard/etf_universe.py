from __future__ import annotations

import copy
import json
import re
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd

from .settings import load_config
from .universe import UniverseSelection, UniverseSourceError


# ISIN country prefix -> Yahoo Finance exchange suffix for non-US listings.
# Only used when the holdings file gives a bare local ticker; override per-ticker with --ticker-map.
ISIN_YAHOO_SUFFIX: dict[str, str] = {
    "IL": ".TA",
    "HK": ".HK",
    "KY": ".HK",
    "BM": ".HK",
    "CN": ".HK",
    "DE": ".DE",
    "ES": ".MC",
    "FR": ".PA",
    "IT": ".MI",
    "GB": ".L",
    "CH": ".SW",
    "NL": ".AS",
    "DK": ".CO",
    "NO": ".OL",
    "SE": ".ST",
    "JP": ".T",
    "KR": ".KS",
    "TW": ".TW",
    "AU": ".AX",
    "CA": ".TO",
    "IN": ".NS",
    "BR": ".SA",
}

NON_EQUITY_PATTERN = re.compile(r"cash|treasury|money market|future|swap|usd|currency", re.IGNORECASE)


def _select_column(columns: list[str], fragments: list[str]) -> str | None:
    lowered = {column: column.lower().strip() for column in columns}
    for fragment in fragments:
        for column, name in lowered.items():
            if fragment in name:
                return column
    return None


def read_holdings_file(path: Path) -> pd.DataFrame:
    """Read an ETF holdings export (CSV or XLSX), skipping any preamble rows above the header."""
    if path.suffix.lower() in {".xlsx", ".xls"}:
        raw = pd.read_excel(path, header=None, dtype=str)
        lines = raw.fillna("").astype(str).agg(",".join, axis=1).tolist()
        header_idx = next(
            (i for i, line in enumerate(lines) if re.search(r"ticker|symbol", line, re.IGNORECASE)),
            0,
        )
        frame = pd.read_excel(path, header=header_idx, dtype=str)
    else:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        lines = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
        header_idx = next(
            (i for i, line in enumerate(lines) if re.search(r"ticker|symbol", line, re.IGNORECASE)),
            0,
        )
        frame = pd.read_csv(StringIO("\n".join(lines[header_idx:])), dtype=str)
    frame.columns = [str(column).strip() for column in frame.columns]
    return frame


def parse_holdings(
    frame: pd.DataFrame,
    ticker_map: dict[str, str] | None = None,
) -> tuple[pd.DataFrame, list[dict[str, str]]]:
    """Normalize holdings into rank/ticker/company_name/weight with Yahoo-style tickers."""
    columns = list(frame.columns)
    # Prefer the holding's own ticker over the fund ticker column ("Fund Ticker").
    ticker_col = _select_column(
        [c for c in columns if "fund" not in c.lower()], ["holding ticker", "ticker", "symbol"]
    )
    weight_col = _select_column(columns, ["weight", "% of fund", "% of net", "portfolio"])
    name_col = _select_column(columns, ["name", "description", "security"])
    date_col = _select_column(columns, ["as of", "date"])
    isin_col = _select_column(columns, ["isin", "security identifier", "identifier"])
    if ticker_col is None or weight_col is None:
        raise UniverseSourceError(
            f"Holdings file needs ticker and weight columns; found {columns}."
        )

    ticker_map = {k.upper(): v.upper() for k, v in (ticker_map or {}).items()}
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for _, record in frame.iterrows():
        raw_ticker = str(record.get(ticker_col, "") or "").strip().upper()
        name = str(record.get(name_col, "") or "").strip() if name_col else ""
        weight = pd.to_numeric(
            str(record.get(weight_col, "")).replace("%", "").replace(",", ""), errors="coerce"
        )
        if not raw_ticker or raw_ticker == "NAN" or pd.isna(weight):
            continue
        if NON_EQUITY_PATTERN.search(name) or NON_EQUITY_PATTERN.fullmatch(raw_ticker):
            skipped.append({"ticker": raw_ticker, "reason": "non-equity line"})
            continue

        # Bloomberg-style "ENLT IT" -> base ticker; the ISIN decides the exchange.
        base = raw_ticker.split()[0].replace("/", "-")
        if raw_ticker in ticker_map or base in ticker_map:
            yahoo = ticker_map.get(raw_ticker, ticker_map.get(base, base))
        elif "." in base:
            yahoo = base
        else:
            isin = str(record.get(isin_col, "") or "").strip().upper() if isin_col else ""
            country = isin[:2] if re.fullmatch(r"[A-Z]{2}[A-Z0-9]{10}", isin) else "US"
            suffix = ISIN_YAHOO_SUFFIX.get(country, "")
            if suffix == ".HK" and base.isdigit():
                base = base.zfill(4)
            yahoo = f"{base}{suffix}"
        rows.append({"ticker": yahoo, "company_name": name, "weight": float(weight), "source_ticker": raw_ticker})

    holdings = pd.DataFrame(rows)
    if holdings.empty:
        raise UniverseSourceError("Holdings file parsed but yielded no equity rows.")
    holdings = (
        holdings.sort_values("weight", ascending=False)
        .drop_duplicates("ticker")
        .reset_index(drop=True)
    )
    holdings.insert(0, "rank", range(1, len(holdings) + 1))
    if date_col is not None:
        dates = pd.to_datetime(frame[date_col], errors="coerce").dropna()
        if not dates.empty:
            holdings.attrs["as_of_date"] = dates.max().date().isoformat()
    return holdings, skipped


def build_etf_selection(
    etf: str,
    holdings: pd.DataFrame,
    holdings_path: Path,
    skipped: list[dict[str, str]],
    dropped: list[dict[str, str]],
    as_of_date: str | None = None,
) -> UniverseSelection:
    universe = holdings[["rank", "ticker", "company_name"]].copy()
    metadata = {
        "resolved_at_utc": datetime.now(UTC).isoformat(),
        "universe_size": int(len(universe)),
        "selection_mode": "etf_holdings_weight_rank",
        "official_source": {
            "type": "etf_holdings_file",
            "etf": etf,
            "path": str(holdings_path),
            # Holdings "as of" date when the export carries one, else the file's save date.
            "trade_date": as_of_date or datetime.fromtimestamp(holdings_path.stat().st_mtime).date().isoformat(),
            "note": (
                "ETF holdings run. The NASDAQ-100 50-name minimum does not apply; "
                "the universe is every priced equity holding of the fund."
            ),
        },
        "ranking": {
            "source_type": "etf_holdings_weight",
            "source_url": None,
            "fallback_used": False,
            "fallback_reason": None,
            "supplemental_sources": [],
            "attempts": [],
            "skipped_non_equity": skipped,
            "dropped_unpriced": dropped,
            "weights": dict(zip(holdings["ticker"], holdings["weight"])),
        },
        "final_tickers": universe["ticker"].tolist(),
        "final_universe": universe.to_dict(orient="records"),
    }
    return UniverseSelection(universe=universe.reset_index(drop=True), metadata=metadata)


def write_etf_config(base_config_path: Path, etf: str, universe_size: int) -> Path:
    """Derive a per-ETF config from the base config with isolated output paths."""
    base = load_config(base_config_path)
    payload = copy.deepcopy(base.payload)
    slug = etf.upper()
    payload["project_name"] = f"{slug} Holdings Correlation Dashboard"
    payload["universe_policy"] = {
        "index_symbol": slug,
        "index_name": f"{slug} ETF holdings",
        "universe_size": universe_size,
        "selection_mode": "etf_holdings_weight_rank",
        "benchmark_ticker": slug,
    }
    payload["validation"]["minimum_ranked_constituents"] = universe_size
    data_dir = f"data/etf/{slug}"
    renamed: dict[str, str] = {}
    for key, value in payload["paths"].items():
        name = Path(value).name.replace("nasdaq_top50_", f"{slug.lower()}_")
        folder = f"exports/etf/{slug}" if value.startswith("exports/") else data_dir
        renamed[key] = f"{folder}/{name}"
    payload["paths"] = renamed
    payload["visuals"]["page_title"] = f"${slug} Correlation Analysis"

    destination = base.root / data_dir / "config.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return destination
