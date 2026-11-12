from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from .settings import DashboardConfig, load_config
from .atomic_io import write_csv


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0 Safari/537.36"
)


class UniverseSourceError(RuntimeError):
    """Raised when the ticker universe cannot be resolved safely."""


@dataclass
class UniverseSelection:
    universe: pd.DataFrame
    metadata: dict[str, Any]
    # Next-ranked names (rank target_size+1, +2, ...) used to replace members that lack history.
    reserve: pd.DataFrame | None = None

    @property
    def tickers(self) -> list[str]:
        return self.universe["ticker"].tolist()

    @property
    def reserve_tickers(self) -> list[str]:
        return [] if self.reserve is None else self.reserve["ticker"].tolist()


def resolve_universe(config: DashboardConfig) -> UniverseSelection:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    official_members, official_metadata = _fetch_official_members(config, session)

    ranking_attempts: list[dict[str, Any]] = []
    selected_order: list[str] = []
    ranking_metadata: dict[str, Any] = {
        "source_type": None,
        "source_url": None,
        "fallback_used": False,
        "fallback_reason": None,
        "supplemental_sources": [],
        "attempts": ranking_attempts,
    }

    for source in config.universe_policy["ranking_sources"]:
        source_type = source["type"]
        try:
            if source_type == "qqqm_holdings_download":
                ranked = _fetch_qqqm_rankings(source, session)
            elif source_type == "yfinance_market_cap":
                ranked = _fetch_market_cap_rankings(official_members["ticker"].tolist())
            else:
                raise UniverseSourceError(f"Unsupported ranking source: {source_type}")

            ranked_order = _ranked_intersection(
                official_members["ticker"].tolist(),
                ranked["ticker"].tolist(),
            )
            ranking_attempts.append(
                {
                    "type": source_type,
                    "status": "success",
                    "resolved_constituents": len(ranked_order),
                }
            )
            if not selected_order and ranked_order:
                selected_order.extend(ranked_order)
                ranking_metadata["source_type"] = source_type
                ranking_metadata["source_url"] = source.get("download_url") or source.get(
                    "holdings_page_url"
                )
                ranking_metadata["fallback_used"] = source_type != "nasdaq_weighting_data"
                if source_type != "qqqm_holdings_download":
                    ranking_metadata[
                        "fallback_reason"
                    ] = "QQQM public holdings export was unavailable; live market-cap ranking was used."
                else:
                    ranking_metadata[
                        "fallback_reason"
                    ] = "Nasdaq public weight ranking was unavailable; QQQM holdings were used as the ranking proxy."
            else:
                ranking_metadata["supplemental_sources"].append(source_type)
                selected_order.extend(
                    ticker for ticker in ranked_order if ticker not in selected_order
                )
            if len(selected_order) >= int(config.validation["minimum_ranked_constituents"]):
                break
        except Exception as exc:  # pragma: no cover - defensive network handling
            ranking_attempts.append(
                {"type": source_type, "status": "failed", "error": str(exc)}
            )

    target_size = int(config.universe_policy["universe_size"])
    if len(selected_order) < target_size:
        raise UniverseSourceError(
            "Unable to rank enough official Nasdaq constituents to produce the top 50."
        )

    ranking_lookup = {ticker: rank + 1 for rank, ticker in enumerate(selected_order)}
    def _ranked_rows(tickers: list[str]) -> pd.DataFrame:
        rows = official_members[official_members["ticker"].isin(tickers)].copy()
        rows["rank"] = rows["ticker"].map(ranking_lookup)
        rows = rows.sort_values("rank").reset_index(drop=True)
        return rows[["rank", "ticker", "company_name"]]

    selected = _ranked_rows(selected_order[:target_size])
    reserve_size = int(config.universe_policy.get("reserve_size", 10))
    reserve = _ranked_rows(selected_order[target_size : target_size + reserve_size])

    metadata = {
        "resolved_at_utc": datetime.now(UTC).isoformat(),
        "universe_size": int(target_size),
        "selection_mode": config.universe_policy["selection_mode"],
        "official_source": official_metadata,
        "ranking": ranking_metadata,
        "final_tickers": selected["ticker"].tolist(),
        "final_universe": selected.to_dict(orient="records"),
    }
    return UniverseSelection(universe=selected, metadata=metadata, reserve=reserve)


def apply_history_coverage(
    selection: UniverseSelection,
    prices: pd.DataFrame,
    max_leading_gap_ratio: float,
) -> tuple[UniverseSelection, pd.DataFrame]:
    """Swap out members that started trading after the window began, promoting reserve names.

    A member whose blank leading rows exceed ``max_leading_gap_ratio`` of the window (a recent IPO
    or listing) would otherwise force the whole analysis down to its short history, because returns
    are aligned on common dates. Such names are excluded and the next-ranked reserve names with full
    coverage take their place, so the run keeps its size and its full window. Every swap is recorded
    in ``metadata["history_substitutions"]``. Raises if the reserve runs out.
    """

    def leading_gap(ticker: str) -> float:
        if ticker not in prices.columns or len(prices) == 0:
            return 1.0
        series = prices[ticker]
        first = series.first_valid_index()
        if first is None:
            return 1.0
        return float((prices.index < first).sum()) / len(prices)

    def first_date(ticker: str) -> str | None:
        if ticker not in prices.columns:
            return None
        first = prices[ticker].first_valid_index()
        return None if first is None else str(pd.Timestamp(first).date())

    short = [t for t in selection.tickers if leading_gap(t) > max_leading_gap_ratio]
    if not short:
        return selection, prices[selection.tickers]

    reserve = selection.reserve if selection.reserve is not None else pd.DataFrame(
        columns=["rank", "ticker", "company_name"]
    )
    universe = selection.universe
    kept = universe[~universe["ticker"].isin(short)]
    promoted_rows: list[pd.Series] = []
    skipped_reserve: list[dict[str, Any]] = []
    reserve_iter = iter(reserve.itertuples(index=False))
    substitutions: list[dict[str, Any]] = []
    for ticker in short:
        row = universe.loc[universe["ticker"] == ticker].iloc[0]
        replacement = None
        for candidate in reserve_iter:
            if leading_gap(candidate.ticker) <= max_leading_gap_ratio:
                replacement = candidate
                break
            skipped_reserve.append({"ticker": candidate.ticker, "first_price_date": first_date(candidate.ticker)})
        if replacement is None:
            raise UniverseSourceError(
                f"{ticker} lacks price history for the chosen window and no reserve name with full "
                "history is left to replace it. Choose a shorter lookback or raise universe_policy.reserve_size."
            )
        promoted_rows.append(pd.Series(replacement._asdict()))
        substitutions.append(
            {
                "excluded": ticker,
                "excluded_rank": int(row["rank"]),
                "first_price_date": first_date(ticker),
                "window_start": str(pd.Timestamp(prices.index.min()).date()),
                "replacement": replacement.ticker,
                "replacement_rank": int(replacement.rank),
            }
        )

    new_universe = pd.concat([kept, pd.DataFrame(promoted_rows)], ignore_index=True)
    new_universe["rank"] = new_universe["rank"].astype(int)
    new_universe = new_universe.sort_values("rank").reset_index(drop=True)[["rank", "ticker", "company_name"]]
    used = set(new_universe["ticker"]) | {item["ticker"] for item in skipped_reserve}
    new_reserve = reserve[~reserve["ticker"].isin(used)].reset_index(drop=True)

    metadata = dict(selection.metadata)
    metadata["history_substitutions"] = substitutions
    if skipped_reserve:
        metadata["history_substitutions_skipped_reserve"] = skipped_reserve
    metadata["final_tickers"] = new_universe["ticker"].tolist()
    metadata["final_universe"] = new_universe.to_dict(orient="records")
    updated = UniverseSelection(universe=new_universe, metadata=metadata, reserve=new_reserve)
    return updated, prices[updated.tickers]


def write_universe(universe: pd.DataFrame, destination) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_csv(universe, destination, index=False)


def refresh_universe(config_path: str | Path, top_n: int = 50) -> dict[str, Any]:
    """Preview the currently resolved universe without writing any artifacts.

    Returns the top ``top_n`` resolved tickers plus the provenance fields that
    ``scripts/refresh_universe.py`` prints.
    """

    selection = resolve_universe(load_config(config_path))
    return {
        "proposed_tickers": selection.universe.head(top_n)["ticker"].tolist(),
        "snapshot_date": selection.metadata["official_source"]["trade_date"],
        "ranking_source": selection.metadata["ranking"]["source_type"],
        "fallback_used": selection.metadata["ranking"]["fallback_used"],
    }


def _fetch_official_members(
    config: DashboardConfig,
    session: requests.Session,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    policy = config.universe_policy
    official = policy["official_source"]
    offset = int(policy.get("official_trade_date_offset_days", 1))
    lookback = int(policy.get("official_trade_date_lookback_days", 7))

    errors: list[str] = []
    for extra_days in range(lookback + 1):
        trade_date = (datetime.now(UTC) - timedelta(days=offset + extra_days)).date()
        response = session.post(
            official["weighting_data_url"],
            data={
                "id": policy["index_symbol"],
                "tradeDate": trade_date.isoformat(),
                "timeOfDay": "SOD",
            },
            timeout=20,
        )
        if response.status_code != 200:
            errors.append(f"{trade_date}: HTTP {response.status_code}")
            continue
        payload = response.json()
        frame = pd.DataFrame(payload.get("aaData", []))
        if frame.empty:
            errors.append(f"{trade_date}: empty membership payload")
            continue
        normalized = frame.rename(
            columns={"Name": "company_name", "Symbol": "ticker"}
        )[["company_name", "ticker"]]
        normalized["ticker"] = normalized["ticker"].str.upper().str.strip()
        normalized["company_name"] = normalized["company_name"].str.strip()
        normalized = normalized.dropna().drop_duplicates("ticker").reset_index(drop=True)
        if len(normalized) < int(config.universe_policy["universe_size"]):
            errors.append(
                f"{trade_date}: expected at least {config.universe_policy['universe_size']} constituents"
            )
            continue
        return normalized, {
            "type": official["type"],
            "source_url": official["weighting_data_url"],
            "overview_url": official["overview_url"],
            "fact_sheet_url": official["fact_sheet_url"],
            "trade_date": trade_date.isoformat(),
            "member_count": int(len(normalized)),
        }

    raise UniverseSourceError(
        "Official Nasdaq membership could not be resolved. "
        + "; ".join(errors[-3:])
    )


def _fetch_qqqm_rankings(
    source: dict[str, Any],
    session: requests.Session,
) -> pd.DataFrame:
    session.get(source["holdings_page_url"], timeout=20)
    response = session.get(
        source["download_url"],
        headers={"Referer": source["holdings_page_url"]},
        timeout=20,
        allow_redirects=True,
    )
    content_type = response.headers.get("Content-Type", "")
    content = response.content
    if response.url.endswith("/etfs.html") or b"<html" in content[:200].lower():
        raise UniverseSourceError("QQQM holdings download redirected to a generic ETF page.")

    frame = _read_download_frame(content, content_type)
    symbol_col = _select_column(frame.columns, ["ticker", "symbol"])
    weight_col = _select_column(frame.columns, ["% of fund", "weight", "portfolio"])
    if symbol_col is None or weight_col is None:
        raise UniverseSourceError("QQQM holdings export did not expose symbol and weight columns.")

    normalized = pd.DataFrame(
        {
            "ticker": frame[symbol_col].astype(str).str.upper().str.strip(),
            "ranking_value": _coerce_numeric(frame[weight_col]),
        }
    )
    normalized = normalized.dropna(subset=["ticker", "ranking_value"])
    normalized = normalized[normalized["ticker"].str.match(r"^[A-Z.\-]+$")]
    normalized = normalized.drop_duplicates("ticker")
    normalized = normalized.sort_values("ranking_value", ascending=False).reset_index(drop=True)
    if normalized.empty:
        raise UniverseSourceError("QQQM holdings export was parsed successfully but yielded no rows.")
    return normalized


def _fetch_market_cap_rankings(tickers: list[str]) -> pd.DataFrame:
    import yfinance as yf

    rows: list[dict[str, Any]] = []
    for ticker in tickers:
        instrument = yf.Ticker(ticker)
        market_cap = None
        try:
            fast_info = getattr(instrument, "fast_info", {}) or {}
            market_cap = fast_info.get("market_cap")
        except Exception:
            market_cap = None
        if not market_cap:
            try:
                info = instrument.info or {}
                market_cap = info.get("marketCap")
            except Exception:
                market_cap = None
        if market_cap:
            rows.append({"ticker": ticker, "ranking_value": float(market_cap)})

    ranked = pd.DataFrame(rows)
    if ranked.empty:
        raise UniverseSourceError("Yahoo Finance market-cap fallback returned no usable values.")
    return ranked.sort_values("ranking_value", ascending=False).reset_index(drop=True)


def _read_download_frame(content: bytes, content_type: str) -> pd.DataFrame:
    lowered = content_type.lower()
    if "sheet" in lowered or content[:2] == b"PK":
        return pd.read_excel(BytesIO(content))
    if "csv" in lowered or "text/plain" in lowered or content[:32].startswith(b"Ticker"):
        return pd.read_csv(StringIO(content.decode("utf-8", errors="ignore")))
    raise UniverseSourceError(f"Unsupported QQQM holdings content type: {content_type}")


def _select_column(columns, expected_fragments: list[str]) -> str | None:
    lowered = {str(column).lower(): str(column) for column in columns}
    for fragment in expected_fragments:
        for lowered_name, original in lowered.items():
            if fragment in lowered_name:
                return original
    return None


def _coerce_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace("%", "", regex=False).str.replace(",", "", regex=False),
        errors="coerce",
    )


def _ranked_intersection(official_tickers: list[str], ranked_tickers: list[str]) -> list[str]:
    official = set(official_tickers)
    return [ticker for ticker in ranked_tickers if ticker in official]
