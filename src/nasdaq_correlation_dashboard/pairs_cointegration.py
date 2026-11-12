from __future__ import annotations

import math
import warnings
import json
from dataclasses import asdict, dataclass, replace
from importlib.metadata import PackageNotFoundError, version
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller, coint


DEFAULT_COINTEGRATION_P_THRESHOLD = 0.05
DEFAULT_ADF_STAT_THRESHOLD = -2.86
DEFAULT_MIN_OBS = 252
DEFAULT_ROLLING_Z_WINDOW = 60
DEFAULT_TOP_SPREAD_EXPORT = 10


@dataclass(frozen=True)
class PairAnalysisConfig:
    cointegration_p_threshold: float = DEFAULT_COINTEGRATION_P_THRESHOLD
    adf_stat_threshold: float = DEFAULT_ADF_STAT_THRESHOLD
    min_observations: int = DEFAULT_MIN_OBS
    rolling_z_window: int = DEFAULT_ROLLING_Z_WINDOW
    top_spread_export: int = DEFAULT_TOP_SPREAD_EXPORT
    history_period: str = "max"


@dataclass
class PairAnalysisArtifacts:
    all_pairs: pd.DataFrame
    qualified_pairs: pd.DataFrame
    spread_history: pd.DataFrame
    input_summary: pd.DataFrame
    parameters: pd.DataFrame
    provenance: pd.DataFrame
    metadata: dict[str, Any]


def load_price_frame(prices_path: str | Path) -> pd.DataFrame:
    prices = pd.read_csv(prices_path, parse_dates=["Date"])
    prices = prices.rename(columns={"Date": "date"}).set_index("date").sort_index()
    prices = prices.apply(pd.to_numeric, errors="coerce")
    prices = prices.replace([np.inf, -np.inf], np.nan)
    return prices


def load_universe_tickers(universe_path: str | Path | None) -> list[str]:
    if universe_path is None:
        return []
    universe = pd.read_csv(universe_path)
    if "ticker" not in universe.columns:
        raise ValueError(f"Universe file {universe_path} is missing a 'ticker' column.")
    return [str(value).strip() for value in universe["ticker"].tolist() if str(value).strip()]


def select_tickers(
    prices: pd.DataFrame,
    requested_tickers: list[str] | None = None,
    universe_tickers: list[str] | None = None,
) -> list[str]:
    requested = [ticker.strip().upper() for ticker in (requested_tickers or []) if ticker.strip()]
    universe = [ticker.strip().upper() for ticker in (universe_tickers or []) if ticker.strip()]
    available = [str(column).strip().upper() for column in prices.columns]

    if requested:
        chosen = [ticker for ticker in requested if ticker in available]
    elif universe:
        chosen = [ticker for ticker in universe if ticker in available]
    else:
        chosen = available

    if len(chosen) < 2:
        raise ValueError("At least two tickers are required for pair testing.")
    return chosen


MIN_COINTEGRATION_OBSERVATIONS = 20


def analyze_pairs(
    prices: pd.DataFrame,
    tickers: list[str],
    config: PairAnalysisConfig,
    source_path: str | Path,
    universe_path: str | Path | None = None,
) -> PairAnalysisArtifacts:
    analysis_prices = select_analysis_window(prices, config.history_period)
    effective_config = replace(
        config,
        # Shrink to short windows, but never below the floor where Engle-Granger/ADF is meaningful.
        min_observations=max(
            MIN_COINTEGRATION_OBSERVATIONS, min(config.min_observations, len(analysis_prices))
        ),
    )
    pair_rows: list[dict[str, Any]] = []
    spread_exports: list[pd.DataFrame] = []
    pair_count = math.comb(len(tickers), 2)

    for ticker_a, ticker_b in combinations(tickers, 2):
        pair_frame = analysis_prices[[ticker_a, ticker_b]].dropna()
        result, spread_frame = _analyze_pair_orientations(
            pair_frame=pair_frame,
            ticker_a=ticker_a,
            ticker_b=ticker_b,
            config=effective_config,
        )
        pair_rows.append(result)
        if not spread_frame.empty:
            spread_exports.append(spread_frame)

    all_pairs = pd.DataFrame(pair_rows)
    all_pairs = all_pairs.sort_values(
        by=["qualified_flag", "coint_p_value", "adf_stat", "pair"],
        ascending=[False, True, True, True],
    ).reset_index(drop=True)

    ranked_all_pairs = _apply_pair_ranking(all_pairs)
    qualified_pairs = ranked_all_pairs.loc[ranked_all_pairs["qualified_flag"]].reset_index(drop=True)
    top_pair_ids = set(qualified_pairs.head(config.top_spread_export)["pair"].tolist())

    spread_history = pd.DataFrame()
    if top_pair_ids and spread_exports:
        spread_history = pd.concat(
            [frame for frame in spread_exports if frame["pair"].iloc[0] in top_pair_ids],
            ignore_index=True,
        )
        spread_history = spread_history.merge(
            qualified_pairs[["pair", "rank", "ranking_score"]],
            on="pair",
            how="left",
        )
        spread_history = spread_history.sort_values(
            by=["rank", "pair", "date"], ascending=[True, True, True]
        )

    input_summary = pd.DataFrame(
        [
            {"metric": "input_price_file", "value": str(Path(source_path).resolve())},
            {
                "metric": "input_universe_file",
                "value": str(Path(universe_path).resolve()) if universe_path else "",
            },
            {"metric": "n_tickers", "value": len(tickers)},
            {"metric": "n_pairs_tested", "value": pair_count},
            {"metric": "n_pairs_qualified", "value": int(qualified_pairs["qualified_flag"].sum())},
            {"metric": "history_period", "value": config.history_period},
            {"metric": "date_start", "value": str(analysis_prices.index.min().date())},
            {"metric": "date_end", "value": str(analysis_prices.index.max().date())},
            {"metric": "n_price_rows", "value": len(analysis_prices)},
            {"metric": "effective_min_overlap", "value": effective_config.min_observations},
        ]
    )

    parameters = pd.DataFrame(
        [
            {"parameter": "cointegration_p_threshold", "value": config.cointegration_p_threshold},
            {"parameter": "adf_stat_threshold", "value": config.adf_stat_threshold},
            {"parameter": "min_observations_target", "value": config.min_observations},
            {"parameter": "min_observations_effective", "value": effective_config.min_observations},
            {"parameter": "rolling_z_window", "value": config.rolling_z_window},
            {"parameter": "top_spread_export", "value": config.top_spread_export},
            {"parameter": "history_period", "value": config.history_period},
            {"parameter": "test_method", "value": "Engle-Granger plus residual ADF"},
            {"parameter": "hedge_ratio_method", "value": "OLS with intercept"},
        ]
    )

    provenance = pd.DataFrame(
        [
            {"field": "package.pandas", "value": _safe_version("pandas")},
            {"field": "package.numpy", "value": _safe_version("numpy")},
            {"field": "package.statsmodels", "value": _safe_version("statsmodels")},
            {"field": "package.scipy", "value": _safe_version("scipy")},
            {"field": "package.openpyxl", "value": _safe_version("openpyxl")},
            {"field": "source_path", "value": str(Path(source_path).resolve())},
            {"field": "selected_tickers", "value": ", ".join(tickers)},
            {"field": "analysis_orientation_policy", "value": "best of both directions"},
            {"field": "history_period", "value": config.history_period},
        ]
    )

    thresholds = {
        "cointegration_p_threshold": config.cointegration_p_threshold,
        "adf_stat_threshold": config.adf_stat_threshold,
        "minimum_rows_target": config.min_observations,
        "minimum_rows_effective": effective_config.min_observations,
        "rolling_z_window": config.rolling_z_window,
    }
    threshold_definitions = {
        "cointegration_p_threshold": "Lower p-values mean stronger evidence that the pair shares a stable long-run relationship rather than moving together by chance.",
        "adf_stat_threshold": "A more negative ADF statistic means the residual spread is more likely to be mean reverting instead of drifting like a random walk.",
        "minimum_rows_effective": "Minimum overlapping daily observations required before the pair is tested after adjusting for the selected trailing window.",
        "minimum_rows_target": "Target overlap floor for robust estimation before any window-length adjustment is applied.",
        "rolling_z_window": "Lookback window used to standardize the latest spread relative to its recent behavior.",
    }
    metadata = {
        "created_at_utc": pd.Timestamp.utcnow().isoformat(),
        "source_path": str(Path(source_path).resolve()),
        "universe_path": str(Path(universe_path).resolve()) if universe_path else None,
        "history_period": config.history_period,
        "analysis_window": {
            "start_date": str(analysis_prices.index.min().date()),
            "end_date": str(analysis_prices.index.max().date()),
            "rows": int(len(analysis_prices)),
        },
        "counts": {
            "tickers": len(tickers),
            "pairs_tested": pair_count,
            "pairs_qualified": int(qualified_pairs["qualified_flag"].sum()),
        },
        "thresholds": thresholds,
        "threshold_definitions": threshold_definitions,
        "top_pairs": qualified_pairs.head(config.top_spread_export).to_dict(orient="records"),
        "packages": {
            "pandas": _safe_version("pandas"),
            "numpy": _safe_version("numpy"),
            "statsmodels": _safe_version("statsmodels"),
            "scipy": _safe_version("scipy"),
            "openpyxl": _safe_version("openpyxl"),
        },
        "config": asdict(config),
        "effective_config": asdict(effective_config),
    }

    return PairAnalysisArtifacts(
        all_pairs=ranked_all_pairs,
        qualified_pairs=qualified_pairs,
        spread_history=spread_history,
        input_summary=input_summary,
        parameters=parameters,
        provenance=provenance,
        metadata=metadata,
    )


def select_analysis_window(prices: pd.DataFrame, history_period: str) -> pd.DataFrame:
    normalized = history_period.strip().lower()
    if normalized == "max":
        return prices.copy()
    offset_map = {
        "5d": pd.DateOffset(days=7),
        "1mo": pd.DateOffset(months=1),
        "3mo": pd.DateOffset(months=3),
        "6mo": pd.DateOffset(months=6),
        "1y": pd.DateOffset(years=1),
        "2y": pd.DateOffset(years=2),
        "3y": pd.DateOffset(years=3),
        "5y": pd.DateOffset(years=5),
        "10y": pd.DateOffset(years=10),
    }
    if normalized not in offset_map:
        raise ValueError(f"Unsupported history period: {history_period}")

    end_date = prices.index.max()
    start_cutoff = end_date - offset_map[normalized]
    window = prices.loc[prices.index >= start_cutoff].copy()
    if window.empty:
        raise ValueError(f"No price rows remain after applying history period {history_period}.")
    return window


def export_pairs_workbook(
    artifacts: PairAnalysisArtifacts,
    output_path: str | Path,
) -> None:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(destination, engine="openpyxl") as writer:
        artifacts.input_summary.to_excel(writer, sheet_name="input_summary", index=False)
        artifacts.all_pairs.to_excel(writer, sheet_name="all_pairs_tested", index=False)
        artifacts.qualified_pairs.to_excel(writer, sheet_name="qualified_pairs", index=False)
        artifacts.spread_history.to_excel(writer, sheet_name="pair_spreads", index=False)
        artifacts.parameters.to_excel(writer, sheet_name="parameters", index=False)
        artifacts.provenance.to_excel(writer, sheet_name="provenance", index=False)

        workbook = writer.book
        for worksheet in workbook.worksheets:
            worksheet.freeze_panes = "A2"
            for column_cells in worksheet.columns:
                values = [str(cell.value) for cell in column_cells if cell.value is not None]
                width = min(max((len(value) for value in values), default=0) + 2, 48)
                worksheet.column_dimensions[column_cells[0].column_letter].width = width


def write_pairs_artifacts(
    artifacts: PairAnalysisArtifacts,
    all_pairs_path: str | Path,
    qualified_pairs_path: str | Path,
    spreads_path: str | Path,
    metadata_path: str | Path,
) -> None:
    for frame, destination in [
        (artifacts.all_pairs, all_pairs_path),
        (artifacts.qualified_pairs, qualified_pairs_path),
        (artifacts.spread_history, spreads_path),
    ]:
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(target, index=False)

    metadata_target = Path(metadata_path)
    metadata_target.parent.mkdir(parents=True, exist_ok=True)
    with metadata_target.open("w", encoding="utf-8") as handle:
        json.dump(artifacts.metadata, handle, indent=2)


def _analyze_pair_orientations(
    pair_frame: pd.DataFrame,
    ticker_a: str,
    ticker_b: str,
    config: PairAnalysisConfig,
) -> tuple[dict[str, Any], pd.DataFrame]:
    if len(pair_frame) < config.min_observations:
        row = _base_result_row(ticker_a, ticker_b, len(pair_frame))
        row["notes"] = (
            f"Rejected before testing: overlap {len(pair_frame)} below minimum "
            f"{config.min_observations}."
        )
        return row, pd.DataFrame()

    forward = _evaluate_orientation(pair_frame, y_ticker=ticker_a, x_ticker=ticker_b, config=config)
    reverse = _evaluate_orientation(pair_frame, y_ticker=ticker_b, x_ticker=ticker_a, config=config)

    chosen = min(
        [forward, reverse],
        key=lambda item: (
            item["coint_p_value"] if pd.notna(item["coint_p_value"]) else np.inf,
            item["adf_stat"] if pd.notna(item["adf_stat"]) else np.inf,
            item["half_life"] if pd.notna(item["half_life"]) else np.inf,
        ),
    )
    other = reverse if chosen is forward else forward

    notes = [str(value).strip() for value in (chosen.get("notes"), other.get("notes")) if str(value).strip()]
    chosen["orientation_tested"] = "both"
    chosen["pair"] = f"{min(ticker_a, ticker_b)}|{max(ticker_a, ticker_b)}"
    chosen["selected_orientation"] = f"{chosen['ticker_y']}~{chosen['ticker_x']}"
    chosen["alternate_orientation"] = f"{other['ticker_y']}~{other['ticker_x']}"
    chosen["notes"] = " | ".join(dict.fromkeys(notes))
    return chosen, chosen.pop("_spread_frame")


def _evaluate_orientation(
    pair_frame: pd.DataFrame,
    y_ticker: str,
    x_ticker: str,
    config: PairAnalysisConfig,
) -> dict[str, Any]:
    row = _base_result_row(y_ticker, x_ticker, len(pair_frame))
    row["sample_start"] = str(pair_frame.index.min().date())
    row["sample_end"] = str(pair_frame.index.max().date())

    x = pair_frame[x_ticker].astype(float)
    y = pair_frame[y_ticker].astype(float)

    warning_messages: list[str] = []
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            coint_stat, coint_p_value, critical_values = coint(y, x, trend="c", autolag="aic")
            warning_messages.extend(str(item.message) for item in caught)
    except Exception as exc:
        row["notes"] = f"Cointegration test failed: {exc}"
        row["_spread_frame"] = pd.DataFrame()
        return row

    try:
        model = sm.OLS(y, sm.add_constant(x, has_constant="add")).fit()
        intercept = float(model.params.iloc[0])
        hedge_ratio = float(model.params.iloc[1])
        spread = y - (intercept + hedge_ratio * x)
    except Exception as exc:
        row["notes"] = f"OLS hedge ratio estimation failed: {exc}"
        row["_spread_frame"] = pd.DataFrame()
        return row

    row["intercept"] = intercept
    row["hedge_ratio"] = hedge_ratio
    row["coint_stat"] = float(coint_stat)
    row["coint_p_value"] = float(coint_p_value)
    row["critical_value_1pct"] = float(critical_values[0]) if len(critical_values) > 0 else np.nan
    row["critical_value_5pct"] = float(critical_values[1]) if len(critical_values) > 1 else np.nan
    row["critical_value_10pct"] = float(critical_values[2]) if len(critical_values) > 2 else np.nan

    if spread.std(ddof=0) == 0 or spread.isna().all():
        row["notes"] = "Spread variance is zero after hedge-ratio estimation."
        row["_spread_frame"] = pd.DataFrame()
        return row

    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            adf_result = adfuller(spread, regression="c", autolag="AIC")
            warning_messages.extend(str(item.message) for item in caught)
    except Exception as exc:
        row["notes"] = f"ADF test failed: {exc}"
        row["_spread_frame"] = pd.DataFrame()
        return row

    adf_stat, adf_p_value, _, _, adf_critical_values, _ = adf_result
    spread_mean = float(spread.mean())
    spread_std = float(spread.std(ddof=0))
    latest_spread = float(spread.iloc[-1])
    latest_zscore = (latest_spread - spread_mean) / spread_std
    rolling_zscore = _latest_rolling_zscore(spread, config.rolling_z_window)
    half_life = _estimate_half_life(spread)
    zero_crossings = _count_zero_crossings(spread)
    qualified = (
        float(coint_p_value) < config.cointegration_p_threshold
        and float(adf_stat) < config.adf_stat_threshold
    )

    row.update(
        {
            "adf_stat": float(adf_stat),
            "adf_p_value": float(adf_p_value),
            "spread_mean": spread_mean,
            "spread_std": spread_std,
            "latest_spread": latest_spread,
            "latest_zscore": float(latest_zscore),
            "latest_rolling_zscore": rolling_zscore,
            "half_life": half_life,
            "zero_crossings": zero_crossings,
            "qualified_flag": qualified,
        }
    )

    adf_1 = adf_critical_values.get("1%", np.nan)
    adf_5 = adf_critical_values.get("5%", np.nan)
    adf_10 = adf_critical_values.get("10%", np.nan)
    row["adf_critical_value_1pct"] = float(adf_1) if pd.notna(adf_1) else np.nan
    row["adf_critical_value_5pct"] = float(adf_5) if pd.notna(adf_5) else np.nan
    row["adf_critical_value_10pct"] = float(adf_10) if pd.notna(adf_10) else np.nan

    if warning_messages:
        row["notes"] = " | ".join(dict.fromkeys(warning_messages))

    spread_export = pd.DataFrame(
        {
            "date": spread.index,
            "pair": f"{min(y_ticker, x_ticker)}|{max(y_ticker, x_ticker)}",
            "ticker_y": y_ticker,
            "ticker_x": x_ticker,
            "selected_orientation": f"{y_ticker}~{x_ticker}",
            "spread": spread.values,
            "zscore": ((spread - spread_mean) / spread_std).values,
        }
    )
    row["_spread_frame"] = spread_export
    return row


def _base_result_row(ticker_y: str, ticker_x: str, n_obs: int) -> dict[str, Any]:
    return {
        "pair": "",
        "ticker_y": ticker_y,
        "ticker_x": ticker_x,
        "sample_start": "",
        "sample_end": "",
        "n_obs": int(n_obs),
        "selected_orientation": "",
        "alternate_orientation": "",
        "orientation_tested": "",
        "intercept": np.nan,
        "hedge_ratio": np.nan,
        "coint_stat": np.nan,
        "coint_p_value": np.nan,
        "adf_stat": np.nan,
        "adf_p_value": np.nan,
        "critical_value_1pct": np.nan,
        "critical_value_5pct": np.nan,
        "critical_value_10pct": np.nan,
        "adf_critical_value_1pct": np.nan,
        "adf_critical_value_5pct": np.nan,
        "adf_critical_value_10pct": np.nan,
        "qualified_flag": False,
        "spread_mean": np.nan,
        "spread_std": np.nan,
        "latest_spread": np.nan,
        "latest_zscore": np.nan,
        "latest_rolling_zscore": np.nan,
        "half_life": np.nan,
        "zero_crossings": np.nan,
        "ranking_score": np.nan,
        "rank": np.nan,
        "notes": "",
    }


def _apply_pair_ranking(all_pairs: pd.DataFrame) -> pd.DataFrame:
    qualified = all_pairs.loc[all_pairs["qualified_flag"]].copy()
    if qualified.empty:
        return all_pairs.copy()

    half_life_values = qualified["half_life"].replace([np.inf, -np.inf], np.nan)
    finite_half_life = half_life_values[half_life_values > 0]
    half_life_fallback = float(finite_half_life.max()) + 1.0 if not finite_half_life.empty else 1_000_000.0
    qualified["_half_life_rank_input"] = half_life_values.where(half_life_values > 0, half_life_fallback)
    qualified["_abs_zscore"] = qualified["latest_zscore"].abs()

    qualified["_p_rank"] = qualified["coint_p_value"].rank(method="dense", ascending=True)
    qualified["_adf_rank"] = qualified["adf_stat"].rank(method="dense", ascending=True)
    qualified["_half_life_rank"] = qualified["_half_life_rank_input"].rank(method="dense", ascending=True)
    qualified["_z_rank"] = qualified["_abs_zscore"].rank(method="dense", ascending=False)
    qualified["ranking_score"] = (
        0.4 * qualified["_p_rank"]
        + 0.3 * qualified["_adf_rank"]
        + 0.2 * qualified["_half_life_rank"]
        + 0.1 * qualified["_z_rank"]
    )
    qualified = qualified.sort_values(
        by=["ranking_score", "coint_p_value", "adf_stat", "_half_life_rank_input", "_abs_zscore"],
        ascending=[True, True, True, True, False],
    ).reset_index(drop=True)
    qualified["rank"] = np.arange(1, len(qualified) + 1)

    ranked_map = qualified.set_index("pair")[["rank", "ranking_score"]]
    merged = all_pairs.copy()
    merged = merged.merge(ranked_map, on="pair", how="left", suffixes=("", "_qualified"))
    merged["rank"] = merged["rank_qualified"].combine_first(merged["rank"])
    merged["ranking_score"] = merged["ranking_score_qualified"].combine_first(merged["ranking_score"])
    merged = merged.drop(
        columns=[
            column
            for column in [
                "rank_qualified",
                "ranking_score_qualified",
                "_half_life_rank_input",
                "_abs_zscore",
                "_p_rank",
                "_adf_rank",
                "_half_life_rank",
                "_z_rank",
            ]
            if column in merged.columns
        ]
    )

    return merged.sort_values(
        by=["qualified_flag", "rank", "coint_p_value", "adf_stat", "pair"],
        ascending=[False, True, True, True, True],
        na_position="last",
    ).reset_index(drop=True)


def _latest_rolling_zscore(spread: pd.Series, window: int) -> float:
    if len(spread) < window:
        return float("nan")
    rolling_mean = spread.rolling(window=window).mean()
    rolling_std = spread.rolling(window=window).std(ddof=0)
    latest_std = rolling_std.iloc[-1]
    if latest_std == 0 or pd.isna(latest_std):
        return float("nan")
    return float((spread.iloc[-1] - rolling_mean.iloc[-1]) / latest_std)


def _estimate_half_life(spread: pd.Series) -> float:
    lagged = spread.shift(1)
    delta = spread.diff()
    regression_frame = pd.DataFrame({"lagged": lagged, "delta": delta}).dropna()
    if len(regression_frame) < 20:
        return float("nan")

    model = sm.OLS(
        regression_frame["delta"],
        sm.add_constant(regression_frame["lagged"], has_constant="add"),
    ).fit()
    beta = float(model.params.iloc[1])
    if beta >= 0:
        return float("nan")
    return float(-np.log(2) / beta)


def _count_zero_crossings(spread: pd.Series) -> int:
    signs = np.sign(spread).replace(0, np.nan).ffill()
    crossings = (signs * signs.shift(1) < 0).sum()
    return int(crossings)


def _safe_version(package_name: str) -> str:
    try:
        return version(package_name)
    except PackageNotFoundError:
        return "not-installed"
