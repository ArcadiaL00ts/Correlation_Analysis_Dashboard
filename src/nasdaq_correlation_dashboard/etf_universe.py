from __future__ import annotations

import copy
import re
import warnings
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd

from .atomic_io import write_json
from .settings import load_config
from .universe import UniverseSelection, UniverseSourceError


# Symbol resolution, in priority order for each holding:
#   1. --ticker-map override        2. a ticker that already has a Yahoo suffix (e.g. ENLT.TA)
#   3. the export's exchange column  4. ISIN country prefix
#   5. CUSIP/CINS first letter       6. otherwise a US listing (bare ticker)
# Some sources map to several candidate exchanges (a Taiwan ISIN can be TWSE ".TW" or TPEx ".TWO";
# a Cayman ISIN can be US-listed or ".HK"). Those are settled by ``resolve_ambiguous_symbols``,
# which probes Yahoo once in a batch and caches the answer in data/manual_universe/symbol_map.json.

ISIN_YAHOO_SUFFIXES: dict[str, list[str]] = {
    "IL": [".TA"],
    "HK": [".HK"],
    "KY": ["", ".HK"],
    "BM": ["", ".HK"],
    "DE": [".DE"],
    "ES": [".MC"],
    "FR": [".PA"],
    "IT": [".MI"],
    "GB": [".L"],
    "CH": [".SW"],
    "NL": [".AS"],
    "BE": [".BR"],
    "AT": [".VI"],
    "PT": [".LS"],
    "IE": [".IR", ""],
    "FI": [".HE"],
    "DK": [".CO"],
    "NO": [".OL"],
    "SE": [".ST"],
    "JP": [".T"],
    "KR": [".KS", ".KQ"],
    "TW": [".TW", ".TWO"],
    "TH": [".BK"],
    "SG": [".SI"],
    "AU": [".AX"],
    "NZ": [".NZ"],
    "CA": [".TO", ".V"],
    "IN": [".NS", ".BO"],
    "BR": [".SA"],
    "MX": [".MX"],
    "ZA": [".JO"],
}
# Single best guess per ISIN country, kept for callers that want one.
ISIN_YAHOO_SUFFIX: dict[str, str] = {country: options[0] for country, options in ISIN_YAHOO_SUFFIXES.items()}

# CUSIP International Numbering System: a letter in the first position gives the issuer's region.
CINS_YAHOO_SUFFIXES: dict[str, list[str]] = {
    "C": [".TO", ".V"],
    "D": [".DE"],
    "E": [".MC"],
    "F": [".PA"],
    "G": ["", ".L", ".HK"],  # UK, Bermuda, Cayman: often US-listed
    "H": [".SW"],
    "J": [".T"],
    "K": [".CO"],
    "M": [".TA"],
    "N": [".AS"],
    "Q": [".AX"],
    "R": [".OL"],
    "S": [".JO"],
    "T": [".MI"],
    "W": [".ST"],
    "Y": [".TW", ".TWO", ".HK", ".KS", ".KQ", ".BK", ".SI"],
}

# Exchange names as issuers print them (iShares "Exchange", others "Market"/"Listing").
EXCHANGE_YAHOO_SUFFIX: list[tuple[str, str]] = [
    ("nasdaq", ""), ("new york", ""), ("nyse", ""), ("cboe", ""), ("bats", ""),
    ("tel aviv", ".TA"), ("hong kong", ".HK"), ("taipei exchange", ".TWO"), ("gretai", ".TWO"),
    ("taiwan", ".TW"), ("kosdaq", ".KQ"), ("korea", ".KS"), ("tokyo", ".T"), ("london", ".L"),
    ("xetra", ".DE"), ("deutsche", ".DE"), ("frankfurt", ".DE"), ("madrid", ".MC"),
    ("euronext paris", ".PA"), ("paris", ".PA"), ("euronext amsterdam", ".AS"), ("amsterdam", ".AS"),
    ("euronext brussels", ".BR"), ("italiana", ".MI"), ("milan", ".MI"), ("six swiss", ".SW"),
    ("swiss", ".SW"), ("copenhagen", ".CO"), ("oslo", ".OL"), ("stockholm", ".ST"), ("helsinki", ".HE"),
    ("tsx venture", ".V"), ("toronto", ".TO"), ("asx", ".AX"), ("australian", ".AX"),
    ("thailand", ".BK"), ("singapore", ".SI"), ("shenzhen", ".SZ"), ("shanghai", ".SS"),
    ("national stock exchange of india", ".NS"), ("bombay", ".BO"), ("sao paulo", ".SA"), ("b3", ".SA"),
    ("johannesburg", ".JO"), ("mexican", ".MX"), ("new zealand", ".NZ"), ("vienna", ".VI"),
]

NON_EQUITY_NAME = re.compile(
    r"\b(cash|treasur(y|ies)|money market|government & agency portfolio|futures|swaps?|currency|forward contract|t-bill)\b",
    re.IGNORECASE,
)
NON_EQUITY_TICKER = re.compile(r"USD|CASH|[A-Z]{3}CASH|-+|N/A", re.IGNORECASE)
NON_EQUITY_ASSET_CLASS = re.compile(r"cash|money market|futures?|fx|currency|derivative", re.IGNORECASE)
_TICKER_HEADER = re.compile(r"(^|[,\t\"])\s*(holding ticker|ticker|symbol)\s*([,\t\"]|$)", re.IGNORECASE)
_AS_OF = re.compile(
    r"as of[^0-9A-Za-z]*([A-Za-z]{3,9}\.? \d{1,2},? \d{4}|\d{1,4}[/-]\d{1,2}[/-]\d{1,4})",
    re.IGNORECASE,
)
_ISIN = re.compile(r"[A-Z]{2}[A-Z0-9]{9}\d")


def _select_column(columns: list[str], fragments: list[str]) -> str | None:
    """Exact (case-insensitive) header match first, then substring match, in fragment order."""
    lowered = {column: column.lower().strip() for column in columns}
    for fragment in fragments:
        for column, name in lowered.items():
            if name == fragment:
                return column
    for fragment in fragments:
        for column, name in lowered.items():
            if fragment in name:
                return column
    return None


def _find_header(lines: list[str]) -> int:
    for index, line in enumerate(lines):
        if _TICKER_HEADER.search(line):
            return index
    return 0


def _preamble_as_of(lines: list[str]) -> str | None:
    for line in lines:
        match = _AS_OF.search(line)
        if match:
            parsed = pd.to_datetime(match.group(1).replace(".", ""), errors="coerce")
            if pd.notna(parsed):
                return parsed.date().isoformat()
    return None


def read_holdings_file(path: Path) -> pd.DataFrame:
    """Read an ETF holdings export (CSV or XLSX), skipping preamble rows above the header row.

    Handles issuer exports with a title/as-of preamble (iShares, Global X), ``#`` comment lines,
    and disclaimer footers. An as-of date found in the preamble is kept in ``frame.attrs``.
    """
    if path.suffix.lower() in {".xlsx", ".xls"}:
        raw = pd.read_excel(path, header=None, dtype=str)
        lines = raw.fillna("").astype(str).agg(",".join, axis=1).tolist()
        header_idx = _find_header(lines)
        frame = pd.read_excel(path, header=header_idx, dtype=str)
        preamble = lines[:header_idx]
    else:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        all_lines = text.splitlines()
        comments = [line.lstrip("# ") for line in all_lines if line.lstrip().startswith("#")]
        lines = [line for line in all_lines if not line.lstrip().startswith("#")]
        header_idx = _find_header(lines)
        frame = pd.read_csv(
            StringIO("\n".join(lines[header_idx:])),
            dtype=str,
            on_bad_lines="skip",
            skip_blank_lines=True,
        )
        preamble = comments + lines[:header_idx]
    frame.columns = [str(column).strip() for column in frame.columns]
    as_of = _preamble_as_of(preamble)
    if as_of:
        frame.attrs["as_of_date"] = as_of
    return frame


def _clean(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    return "" if text.lower() in {"nan", "none", "-", "--"} else text


def _candidates_for(base: str, exchange: str, isin: str, cusip: str) -> tuple[list[str], str]:
    """Yahoo symbol candidates for a bare local ticker, most likely first, plus the evidence used."""

    def with_suffixes(suffixes: list[str]) -> list[str]:
        out: list[str] = []
        for suffix in suffixes:
            local = base
            if suffix == ".HK" and base.isdigit():
                local = base.zfill(4)
            if suffix in {".SS", ".SZ"} and base.isdigit():
                local = base.zfill(6)
            symbol = f"{local}{suffix}"
            if symbol not in out:
                out.append(symbol)
        return out

    if exchange:
        lowered = exchange.lower()
        for fragment, suffix in EXCHANGE_YAHOO_SUFFIX:
            if fragment in lowered:
                return with_suffixes([suffix]), f"exchange '{exchange}'"
    if _ISIN.fullmatch(isin):
        country = isin[:2]
        if country == "US":
            return [base], "US ISIN"
        if country == "CN" and base.isdigit():
            if len(base) == 6:
                return with_suffixes([".SS" if base.startswith("6") else ".SZ"]), "CN ISIN (A-share)"
            return with_suffixes([".HK"]), "CN ISIN (H-share)"
        if country in ISIN_YAHOO_SUFFIXES:
            return with_suffixes(ISIN_YAHOO_SUFFIXES[country]), f"ISIN country {country}"
    if re.fullmatch(r"[A-Z0-9]{9}", cusip) and cusip[0] in CINS_YAHOO_SUFFIXES:
        return with_suffixes(CINS_YAHOO_SUFFIXES[cusip[0]]), f"CINS prefix {cusip[0]}"
    return [base], "default US listing"


def parse_holdings(
    frame: pd.DataFrame,
    ticker_map: dict[str, str] | None = None,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Normalize holdings into rank/ticker/company_name/weight with Yahoo-style tickers.

    Returns ``(holdings, skipped)``. ``holdings.ticker`` is the most likely Yahoo symbol and
    ``holdings.candidates`` lists every plausible one (see ``resolve_ambiguous_symbols``).
    ``skipped`` lists non-equity lines and holdings with no ticker (e.g. ADRs some issuers leave
    blank), with name and identifier so they can be added through ``--ticker-map``.
    """
    columns = list(frame.columns)
    # Prefer the holding's own ticker over the fund's ticker column ("Fund Ticker").
    ticker_col = _select_column(
        [c for c in columns if "fund" not in c.lower() and "source" not in c.lower()],
        ["holding ticker", "ticker", "symbol"],
    )
    weight_col = _select_column(
        columns, ["weight", "weight (%)", "% of fund", "% of net assets", "% of net", "weighting"]
    )
    name_col = _select_column(
        [c for c in columns if "fund" not in c.lower()], ["name", "security name", "description", "security"]
    )
    date_col = _select_column(
        [c for c in columns if not re.search(r"accrual|maturity|settle", c, re.IGNORECASE)],
        ["date", "as of date", "as of"],
    )
    isin_col = _select_column(columns, ["isin"])
    cusip_col = _select_column(columns, ["cusip", "security identifier", "sedol/cusip"])
    exchange_col = _select_column(columns, ["exchange", "market", "listing"])
    asset_col = _select_column(columns, ["asset class", "security type", "class of shares"])
    if ticker_col is None or weight_col is None:
        raise UniverseSourceError(f"Holdings file needs ticker and weight columns; found {columns}.")

    ticker_map = {k.strip().upper(): v.strip().upper() for k, v in (ticker_map or {}).items()}
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for _, record in frame.iterrows():
        raw_ticker = _clean(record.get(ticker_col)).upper()
        name = _clean(record.get(name_col)) if name_col else ""
        weight = pd.to_numeric(
            _clean(record.get(weight_col)).replace("%", "").replace(",", ""), errors="coerce"
        )
        if pd.isna(weight):
            continue  # footer, disclaimer or blank line
        asset_class = _clean(record.get(asset_col)) if asset_col else ""
        isin = (_clean(record.get(isin_col)) if isin_col else "").upper()
        cusip = (_clean(record.get(cusip_col)) if cusip_col else "").upper()
        if not isin and _ISIN.fullmatch(cusip):
            isin, cusip = cusip, ""  # "Security Identifier" columns sometimes hold ISINs
        identifier = isin or cusip
        if asset_class:  # the issuer's own classification beats name keywords ("Future plc")
            is_non_equity = bool(NON_EQUITY_ASSET_CLASS.search(asset_class)) and "equity" not in asset_class.lower()
        else:
            is_non_equity = bool(NON_EQUITY_NAME.search(name))
        is_non_equity = is_non_equity or bool(raw_ticker and NON_EQUITY_TICKER.fullmatch(raw_ticker))
        if is_non_equity:
            skipped.append({"ticker": raw_ticker, "name": name, "reason": "non-equity line"})
            continue

        override = ticker_map.get(raw_ticker) if raw_ticker else None
        if not override and identifier:
            override = ticker_map.get(identifier)
        if not raw_ticker and not override:
            skipped.append(
                {
                    "ticker": "",
                    "name": name,
                    "identifier": identifier,
                    "weight": float(weight),
                    "reason": f"no ticker in the export; add it with --ticker-map {identifier or 'ID'}=<YAHOO>",
                }
            )
            continue

        # Bloomberg-style "ENLT IT" -> base ticker; the exchange/ISIN decides the suffix.
        base = raw_ticker.split()[0].replace("/", "-") if raw_ticker else ""
        if not override and base:
            override = ticker_map.get(base)
        if override:
            candidates, evidence = [override], "--ticker-map"
        elif "." in base and not base.endswith("."):
            candidates, evidence = [base], "suffix in export"
        else:
            exchange = _clean(record.get(exchange_col)) if exchange_col else ""
            candidates, evidence = _candidates_for(base, exchange, isin, cusip)
        rows.append(
            {
                "ticker": candidates[0],
                "company_name": name,
                "weight": float(weight),
                "source_ticker": raw_ticker or identifier,
                "identifier": identifier,
                "candidates": candidates,
                "symbol_evidence": evidence,
            }
        )

    holdings = pd.DataFrame(rows)
    if holdings.empty:
        raise UniverseSourceError("Holdings file parsed but yielded no equity rows.")
    holdings = holdings.sort_values("weight", ascending=False).drop_duplicates("ticker").reset_index(drop=True)
    holdings.insert(0, "rank", range(1, len(holdings) + 1))
    as_of = frame.attrs.get("as_of_date")
    if date_col is not None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)  # mixed date formats parse per element
            dates = pd.to_datetime(frame[date_col], errors="coerce").dropna()
        if not dates.empty:
            as_of = dates.max().date().isoformat()
    if as_of:
        holdings.attrs["as_of_date"] = as_of
    return holdings, skipped


def _probe_with_yfinance(symbols: list[str]) -> set[str]:
    """Symbols that return any close in the last 5 days (one batched request)."""
    import yfinance as yf

    if not symbols:
        return set()
    import logging

    # Most candidates are expected misses; keep yfinance's per-symbol 404 messages out of the output.
    yf_logger = logging.getLogger("yfinance")
    previous_level = yf_logger.level
    yf_logger.setLevel(logging.CRITICAL)
    try:
        raw = yf.download(tickers=symbols, period="5d", auto_adjust=False, progress=False, threads=True)
    finally:
        yf_logger.setLevel(previous_level)
    if raw is None or raw.empty:
        return set()
    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"]
        return {str(column).upper() for column in close.columns if close[column].notna().any()}
    return {symbols[0].upper()} if raw["Close"].notna().any() else set()


def resolve_ambiguous_symbols(
    holdings: pd.DataFrame,
    cache_path: Path | None = None,
    probe: Any = None,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Pick the listed symbol for holdings with several candidate exchanges.

    Cached answers are reused (keyed by source ticker + identifier) so reruns are stable and
    offline. Uncached ones are probed in one batched yfinance request; the first candidate that
    returns prices wins, else the first candidate is kept and reported. Returns the updated
    holdings and a report of every decision.
    """
    import json

    holdings = holdings.copy()
    if "candidates" not in holdings.columns:
        return holdings, []
    cache: dict[str, str] = {}
    if cache_path is not None and cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cache = {}

    def key(row: pd.Series) -> str:
        return f"{row['source_ticker']}|{row.get('identifier', '')}"

    ambiguous = holdings[holdings["candidates"].map(len) > 1]
    to_probe = [row for _, row in ambiguous.iterrows() if key(row) not in cache]
    found: set[str] = set()
    if to_probe:
        symbols = sorted({symbol for row in to_probe for symbol in row["candidates"]})
        try:
            found = {symbol.upper() for symbol in (probe or _probe_with_yfinance)(symbols)}
        except Exception:  # noqa: BLE001 - fall back to first candidates, reported below
            found = set()

    report: list[dict[str, Any]] = []
    for index, row in ambiguous.iterrows():
        k = key(row)
        if k in cache:
            chosen, how = cache[k], "cache"
        else:
            hits = [symbol for symbol in row["candidates"] if symbol.upper() in found]
            chosen, how = (hits[0], "probe") if hits else (row["candidates"][0], "unverified first guess")
            if hits:
                cache[k] = chosen
        holdings.at[index, "ticker"] = chosen
        report.append(
            {
                "source_ticker": row["source_ticker"],
                "candidates": list(row["candidates"]),
                "chosen": chosen,
                "how": how,
            }
        )

    if cache_path is not None and to_probe:
        write_json(dict(sorted(cache.items())), cache_path)
    holdings = holdings.drop_duplicates("ticker").reset_index(drop=True)
    holdings["rank"] = range(1, len(holdings) + 1)
    return holdings, report


def build_etf_selection(
    etf: str,
    holdings: pd.DataFrame,
    holdings_path: Path,
    skipped: list[dict[str, str]],
    dropped: list[dict[str, str]],
    as_of_date: str | None = None,
    symbol_report: list[dict[str, Any]] | None = None,
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
            "skipped_non_equity": [item for item in skipped if item.get("reason") == "non-equity line"],
            "unmapped_holdings": [item for item in skipped if item.get("reason") != "non-equity line"],
            "symbol_resolution": symbol_report or [],
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
    write_json(payload, destination)
    return destination
