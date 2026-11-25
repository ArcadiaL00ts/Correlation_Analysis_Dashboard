from __future__ import annotations

import html
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from nasdaq_correlation_dashboard.correlation import (
    average_pairwise_correlation,
    correlation_change_table,
    pair_correlation_series,
    ranked_pairs,
    rolling_average_correlation,
)
from nasdaq_correlation_dashboard.cli import period_label
from nasdaq_correlation_dashboard import rerun_job
from nasdaq_correlation_dashboard.emblems import brand_mark, panel_head
from nasdaq_correlation_dashboard.net import configure_tls
from nasdaq_correlation_dashboard.settings import load_config, project_root
from nasdaq_correlation_dashboard.theme import hoverlabel, inject_styles, plotly_theme, resolve_theme_tokens

HEATMAP_MARKET_DEFAULT_TICKER = "QQQM"
HEATMAP_MARKET_LOOKBACKS = {
    "1y": "1y",
    "6m": "6mo",
    "3m": "3mo",
    "1w": "5d",
}


def main() -> None:
    configure_tls()
    root = project_root()
    # DASHBOARD_CONFIG lets the same app render an ETF-holdings run (see scripts/run_etf_correlation.py).
    config_override = os.environ.get("DASHBOARD_CONFIG", "").strip()
    config_path = Path(config_override) if config_override else root / "config" / "dashboard_config.json"
    if not config_path.is_absolute():
        config_path = root / config_path
    config = load_config(config_path)
    paths = config.paths
    universe_label = str(config.universe_policy.get("index_name", "NASDAQ-100"))
    is_etf_run = config.universe_policy.get("selection_mode") == "etf_holdings_weight_rank"
    universe_title = (
        f"{universe_label} ({config.universe_policy.get('universe_size')} names)"
        if is_etf_run
        else f"{universe_label} Top-{config.universe_policy.get('universe_size', 50)}"
    )
    benchmark_ticker = str(
        config.universe_policy.get("benchmark_ticker", HEATMAP_MARKET_DEFAULT_TICKER)
    )

    st.set_page_config(
        page_title=config.visuals["page_title"],
        page_icon=":chart_with_upwards_trend:",
        layout="wide",
    )
    inject_styles(config.visuals)

    required = {
        "universe": paths["universe_csv"],
        "prices": paths["raw_prices_csv"],
        "returns": paths["returns_csv"],
        "correlation": paths["correlation_csv"],
        "metadata": paths["metadata_json"],
        "excel": paths["excel_workbook"],
    }
    optional = {
        "previous_universe": paths.get("previous_universe_csv"),
        "previous_correlation": paths.get("previous_correlation_csv"),
        "previous_metadata": paths.get("previous_metadata_json"),
        "pairs_qualified": paths.get("pairs_qualified_csv"),
        "pairs_spreads": paths.get("pairs_spreads_csv"),
        "pairs_metadata": paths.get("pairs_metadata_json"),
        "pairs_workbook": paths.get("pairs_workbook"),
    }
    missing = [name for name, path in required.items() if not path.exists()]

    subtitle = (
        f"{universe_label} weighted by the fund's own holdings export, with locally computed correlations."
        if is_etf_run
        else "Official Nasdaq membership with transparent top-50 ranking fallbacks and locally computed correlations."
    )
    if missing:
        st.markdown(_hero(config.visuals["page_title"], subtitle, None, {}, config.visuals), unsafe_allow_html=True)
        _render_rerun_panel(config, config_path, root, is_etf_run)
        st.error(
            "Dashboard artifacts are incomplete. Missing: "
            + ", ".join(missing)
            + ". Run `scripts/update_dashboard.py` first."
        )
        return

    universe = pd.read_csv(paths["universe_csv"])
    prices = pd.read_csv(paths["raw_prices_csv"], index_col=0, parse_dates=[0])
    correlation = pd.read_csv(paths["correlation_csv"], index_col=0)
    returns = pd.read_csv(paths["returns_csv"], index_col=0, parse_dates=[0])
    metadata = json.loads(paths["metadata_json"].read_text(encoding="utf-8"))
    previous_universe = _read_optional_csv(optional["previous_universe"])
    previous_correlation = _read_optional_csv(optional["previous_correlation"], index_col=0)
    previous_metadata = _read_optional_json(optional["previous_metadata"])
    pairs_qualified = _read_optional_csv(optional["pairs_qualified"])
    pairs_spreads = _read_optional_csv(optional["pairs_spreads"], parse_dates=["date"])
    pairs_metadata = _read_optional_json(optional["pairs_metadata"])

    st.markdown(
        _hero(config.visuals["page_title"], subtitle, correlation, metadata, config.visuals),
        unsafe_allow_html=True,
    )
    _render_rerun_panel(config, config_path, root, is_etf_run)

    universe_count = len(universe)
    average_corr = average_pairwise_correlation(correlation)
    ranking_type = metadata["universe"]["ranking"]["source_type"] or "unresolved"
    pair_limit = int(config.analytics["pair_table_limit"])
    strongest_pairs = pd.DataFrame(ranked_pairs(correlation, limit=pair_limit, ascending=False))
    weakest_pairs = pd.DataFrame(ranked_pairs(correlation, limit=pair_limit, ascending=True))
    # Only offer rolling windows that fit inside the return history (1w/1m lookbacks are short).
    return_count = len(returns)
    rolling_windows = [w for w in config.rolling_windows if w < return_count] or [
        max(2, return_count // 2)
    ]
    default_window = (
        rolling_windows[1] if len(rolling_windows) > 1 else rolling_windows[0]
    )
    qualified_count = int(pairs_metadata.get("counts", {}).get("pairs_qualified", 0)) if pairs_metadata else 0
    tickers = [benchmark_ticker] + [
        ticker for ticker in universe["ticker"].tolist() if ticker != benchmark_ticker
    ]
    price_refresh_token = (
        metadata.get("created_at_utc") or str(paths["raw_prices_csv"].stat().st_mtime_ns)
    )

    metric_a, metric_b, metric_c, metric_d = st.columns([0.8, 1.7, 1, 1])
    metric_a.metric("Universe size", universe_count)
    metric_b.metric("Window", f"{metadata['start_date']} → {metadata['end_date']}")
    metric_c.metric("Average pair correlation", f"{average_corr:.3f}")
    metric_d.metric("Cointegrated pairs", qualified_count if qualified_count else "n/a")

    status_left, status_right = st.columns([1.2, 1])
    with status_left:
        st.markdown(
            _status_card(
                "Universe provenance",
                [
                    f"{'Holdings as of' if is_etf_run else 'Official trade date'}: "
                    f"{metadata['universe']['official_source']['trade_date']}",
                    f"Ranking source: {ranking_type}",
                    f"Resolved tickers: {len(metadata['universe']['final_tickers'])}",
                ],
                emblem="chain",
                tint="cyan",
            ),
            unsafe_allow_html=True,
        )
    with status_right:
        st.markdown(
            _status_card(
                "Refresh status",
                [
                    f"Rows validated: {metadata['validation']['observed_rows']}",
                    f"Missing ratio: {metadata['validation']['observed_missing_ratio']:.2%}",
                    f"Workbook: {paths['excel_workbook'].name}",
                ],
                emblem="check",
                tint="green",
            ),
            unsafe_allow_html=True,
        )

    heatmap_tab, rolling_tab, cointegration_tab, universe_tab, run_tab = st.tabs(
        ["Heatmap", "Rolling research", "Cointegration", "Universe", "Run status"]
    )

    with heatmap_tab:
        with _panel(
            "price",
            "candles",
            "Price action",
            "Daily candles from yfinance when OHLC is available; local adjusted close otherwise.",
            tint="green",
        ):
            market_control_left, market_control_right = st.columns([1.15, 1])
            with market_control_left:
                market_ticker = st.selectbox(
                    "Ticker",
                    options=tickers,
                    index=0,
                    key="heatmap_market_ticker",
                )
            with market_control_right:
                market_range_label = st.radio(
                    "Lookback",
                    options=list(HEATMAP_MARKET_LOOKBACKS.keys()),
                    index=0,
                    key="heatmap_market_range",
                    horizontal=True,
                )
            st.plotly_chart(
                _build_market_chart(
                    prices=prices,
                    ticker=market_ticker,
                    history_period=HEATMAP_MARKET_LOOKBACKS[market_range_label],
                    lookback_label=market_range_label,
                    refresh_token=price_refresh_token,
                    visuals=config.visuals,
                ),
                width="stretch",
                config={"displayModeBar": False},
                theme=None,
            )

        with _panel(
            "heatmap",
            "matrix",
            "Correlation matrix",
            f"Pearson correlation of daily log returns across the {universe_title} universe, scale fixed at -1 to +1.",
            tint="blue",
            delay=60,
        ):
            # Labels are sized in CSS from the chart's real width and this ticker count, and hidden
            # once cells are too narrow for a readable label (colors and tooltips still carry the value).
            hm_n = max(1, len(correlation.columns))
            st.html(
                f"<style>.st-key-panel_heatmap {{ --hm-n: {hm_n}; }}"
                f"@container (max-width: {200 + hm_n * 15}px) {{ .st-key-panel_heatmap .heatmap-label {{ display: none; }} }}"
                "</style>"
            )
            st.plotly_chart(
                _build_heatmap(correlation, config.visuals),
                width="stretch",
                config={"displayModeBar": False},
                theme=None,
            )

        strongest_col, weakest_col = st.columns(2)
        with strongest_col:
            with _panel("strongest", "strong", "Strongest pairs", "Highest correlations in the matrix", tint="cyan"):
                st.dataframe(strongest_pairs, width="stretch", hide_index=True, height=420)
        with weakest_col:
            with _panel("weakest", "weak", "Weakest pairs", "Lowest correlations in the matrix", tint="rose", delay=60):
                st.dataframe(weakest_pairs, width="stretch", hide_index=True, height=420)

        with _panel(
            "rolling_avg",
            "wave",
            "Universe average correlation",
            f"Average pairwise correlation across all {universe_title} names, not a single pair.",
            tint="cyan",
        ):
            window = st.select_slider(
                "Rolling window (days)",
                options=rolling_windows,
                value=default_window,
                key="avg_corr_window",
            )
            avg_corr = rolling_average_correlation(returns, window)
            st.plotly_chart(
                _build_line_chart(
                    avg_corr,
                    title=f"{universe_title} Universe {window}-Day Average Pairwise Correlation",
                    y_label="Correlation",
                    visuals=config.visuals,
                ),
                width="stretch",
                config={"displayModeBar": False},
                theme=None,
            )

    with rolling_tab:
        if previous_correlation.empty or not previous_metadata:
            with _panel("changes", "delta", "Biggest correlation changes since the prior run", tint="rose"):
                st.info(
                    "Prior-run comparison becomes interactive after the next successful refresh preserves "
                    "a previous correlation snapshot."
                )
        else:
            _render_correlation_changes(
                current_correlation=correlation,
                previous_correlation=previous_correlation,
                current_metadata=metadata,
                previous_metadata=previous_metadata,
                previous_universe=previous_universe,
                visuals=config.visuals,
            )

        with _panel("pair_diag", "twin", "Pair diagnostics", "Rolling correlation for one pair over time", tint="blue"):
            pair_options = [item["pair"] for item in ranked_pairs(correlation, limit=50, ascending=False)]
            pair_options += [
                item["pair"]
                for item in ranked_pairs(correlation, limit=50, ascending=True)
                if item["pair"] not in pair_options
            ]
            if not pair_options:
                st.info("Pair diagnostics are unavailable because the correlation matrix did not yield any valid pairs.")
            else:
                pick_left, pick_right = st.columns([1.15, 1])
                selected_pair = pick_left.selectbox("Pair", options=pair_options, index=0)
                rolling_window = pick_right.select_slider(
                    "Rolling pair window (days)",
                    options=rolling_windows,
                    value=default_window,
                    key="pair_window",
                )
                left, right = selected_pair.split(" vs ")
                pair_series = pair_correlation_series(returns, left, right, rolling_window)
                st.plotly_chart(
                    _build_line_chart(
                        pair_series,
                        title=f"{selected_pair} {rolling_window}-Day Rolling Correlation",
                        y_label="Correlation",
                        visuals=config.visuals,
                        color_key="accent_2",
                    ),
                    width="stretch",
                    config={"displayModeBar": False},
                    theme=None,
                )

                snapshot = returns[[left, right]].tail(15).copy()
                snapshot.index = snapshot.index.strftime("%Y-%m-%d")
                st.caption("Last 15 daily log returns for both legs")
                st.dataframe(snapshot, width="stretch")

    with cointegration_tab:
        if pairs_qualified.empty or not pairs_metadata:
            with _panel("coint", "tether", "Top 10 cointegrated pairs", tint="green"):
                st.info(
                    "Cointegration artifacts are unavailable. Run `scripts/run_pairs_cointegration.py` "
                    "or `scripts/update_dashboard.py` to populate this tab."
                )
        else:
            _render_cointegration_tab(
                pairs_qualified,
                pairs_spreads,
                pairs_metadata,
                config.visuals,
            )

    with universe_tab:
        with _panel(
            "universe",
            "ranks",
            f"Resolved {universe_title} universe",
            "Constituents in rank order, with the share of days each price did not move",
            tint="violet",
        ):
            zero_share = metadata.get("zero_return_share") or {}
            universe_view = universe.copy()
            if zero_share:
                universe_view["zero_return_days"] = universe_view["ticker"].map(zero_share)
            st.dataframe(
                universe_view,
                width="stretch",
                hide_index=True,
                column_config={
                    "zero_return_days": st.column_config.NumberColumn(
                        "Zero-return days", format="percent", help="Share of days with an unchanged price"
                    )
                },
            )
            flag = float(metadata.get("zero_return_flag_threshold", 0.15))
            flagged = sorted(
                ((ticker, share) for ticker, share in zero_share.items() if share > flag),
                key=lambda item: -item[1],
            )
            if flagged:
                st.caption(
                    f"Above {flag:.0%} zero-return days (thin trading or local holidays; their correlations "
                    "with other names read low): "
                    + ", ".join(f"{ticker} {share:.0%}" for ticker, share in flagged)
                )
            substitutions = metadata["universe"].get("history_substitutions") or []
            if substitutions:
                st.caption(
                    "Replaced for short price history (listed after the window start, so keeping them "
                    "would shorten every pair's window): "
                    + "; ".join(
                        f"{item['excluded']} (rank {item['excluded_rank']}, first traded "
                        f"{item['first_price_date']}) → {item['replacement']} (rank {item['replacement_rank']})"
                        for item in substitutions
                    )
                )
        with _panel(
            "lineage",
            "chain",
            "Source lineage",
            "Membership source, ranking source and any fallback that was used",
            tint="blue",
        ):
            lineage = {
                "official_source": metadata["universe"]["official_source"],
                "ranking": metadata["universe"]["ranking"],
                "history_substitutions": substitutions,
            }
            st.json(lineage, expanded=False)

    with run_tab:
        with _panel(
            "outputs",
            "check",
            "Validation and outputs",
            "Every artifact this dashboard reads, and whether it exists",
            tint="green",
        ):
            outputs = pd.DataFrame(
                [
                    {
                        "artifact": name,
                        "path": _display_path(path, config.root),
                        "exists": path.exists(),
                        "size_bytes": path.stat().st_size if path.exists() else None,
                    }
                    for name, path in {**required, **{k: v for k, v in optional.items() if v is not None}}.items()
                ]
            )
            st.dataframe(outputs, width="stretch", hide_index=True)
        with _panel("metadata", "braces", "Metadata", "Full provenance record for the current run", tint="violet"):
            st.json(metadata, expanded=False)

    st.markdown(_footer(metadata, is_etf_run), unsafe_allow_html=True)


@contextmanager
def _panel(
    key: str,
    emblem: str,
    title: str,
    subtitle: str = "",
    tint: str = "cyan",
    delay: int = 0,
) -> Iterator[None]:
    """Shared panel shell: emblem badge, title, one-line subtitle, then the body."""
    with st.container(key=f"panel_{key}"):
        if delay:
            st.html(f"<style>.st-key-panel_{key} {{ --delay: {int(delay)}ms; }}</style>")
        st.markdown(panel_head(emblem, title, subtitle, tint), unsafe_allow_html=True)
        yield


def _hero(title: str, subtitle: str, correlation, metadata: dict, visuals: dict) -> str:
    mark = brand_mark(correlation, visuals) if correlation is not None else ""
    chips = ""
    if metadata:
        ranking = metadata.get("universe", {}).get("ranking", {})
        fallback = bool(ranking.get("fallback_used"))
        chips = (
            '<div class="cd-chips">'
            f'<span class="cd-chip"><span class="cd-chip-dot"></span>Data through <b>{_esc(metadata.get("end_date", "n/a"))}</b></span>'
            f'<span class="cd-chip"><span class="cd-chip-dot" style="--chip:var(--{"warn" if fallback else "pos"})"></span>'
            f'Ranking <b>{_esc(ranking.get("source_type") or "unresolved")}</b>{" (fallback)" if fallback else ""}</span>'
            "</div>"
        )
    return (
        '<div class="cd-hero">'
        f"{mark}"
        '<div class="cd-hero-titles">'
        f'<div class="cd-hero-title" role="heading" aria-level="1">{_esc(title)}</div>'
        f'<p class="cd-hero-sub">{_esc(subtitle)}</p>'
        "</div>"
        f"{chips}"
        "</div>"
    )


def _footer(metadata: dict, is_etf_run: bool) -> str:
    sources = (
        "fund holdings export and Yahoo Finance prices"
        if is_etf_run
        else "Nasdaq index weightings, Invesco QQQM holdings and Yahoo Finance prices"
    )
    return (
        '<div class="cd-footer">'
        f"<span><b>Data</b> {_esc(sources)}; returns and correlations computed locally.</span>"
        f"<span><b>Last refresh</b> {_esc(metadata.get('created_at_utc', 'n/a'))}</span>"
        "<span><b>Method</b> Pearson correlation of daily log returns; Engle-Granger cointegration.</span>"
        "<span>Research only. Not investment advice.</span>"
        "</div>"
    )


def _base_layout(visuals: dict, height: int, title: str | None = None) -> dict:
    theme = plotly_theme(visuals)
    layout = {
        "height": height,
        "paper_bgcolor": theme["clear"],
        "plot_bgcolor": theme["plot_bg"],
        "font": {"family": theme["ui_font"], "size": 12, "color": theme["ink_2"]},
        "hoverlabel": hoverlabel(visuals),
        "showlegend": False,
    }
    if title:
        layout["title"] = {
            "text": title,
            "x": 0,
            "xref": "paper",
            "xanchor": "left",
            "font": {"color": theme["ink"], "size": 14, "family": theme["ui_font"], "weight": 600},
        }
    return layout


def _build_heatmap(correlation: pd.DataFrame, visuals: dict) -> go.Figure:
    theme = plotly_theme(visuals)
    tokens = resolve_theme_tokens(visuals)
    display_correlation = correlation.copy()
    colorscale = [
        [0.0, tokens["heatmap_min_color"]],
        [0.5, tokens["heatmap_mid_color"]],
        [1.0, tokens["heatmap_max_color"]],
    ]
    figure = go.Figure(
        data=go.Heatmap(
            z=display_correlation.values,
            x=list(display_correlation.columns),
            y=list(display_correlation.index),
            zmin=-1,
            zmax=1,
            colorscale=colorscale,
            xgap=1,
            ygap=1,
            colorbar={
                "title": {"text": "Corr", "font": {"color": theme["ink_2"], "size": 12}},
                "tickfont": {"color": theme["ink_2"], "size": 11, "family": theme["mono_font"]},
                "thickness": 12,
                "outlinewidth": 0,
                "tickvals": [-1, -0.5, 0, 0.5, 1],
            },
            text=_heatmap_labels(display_correlation),
            texttemplate="%{text}",
            textfont={"family": theme["mono_font"], "size": 10},
            hovertemplate="<b>%{y} vs %{x}</b><br>Correlation  %{z:.3f}<extra></extra>",
        )
    )
    figure.update_layout(
        **_base_layout(visuals, height=_heatmap_height(len(display_correlation.index))),
        margin={"l": 22, "r": 22, "t": 54, "b": 48},
    )
    figure.update_xaxes(
        side="top",
        tickangle=-32,
        automargin=True,
        showgrid=False,
        tickfont={"color": theme["ink_2"], "size": 11, "family": theme["mono_font"]},
    )
    figure.update_yaxes(
        automargin=True,
        showgrid=False,
        tickfont={"color": theme["ink_2"], "size": 11, "family": theme["mono_font"]},
    )
    return figure


# Above this many tickers the cells are too small for any label; values stay in the tooltip.
HEATMAP_LABEL_LIMIT = 80


def _heatmap_labels(correlation: pd.DataFrame) -> list[list[str]]:
    """Compact cell labels that fit a narrow cell: ".87", "-.13", and "1" on the diagonal."""
    if len(correlation.index) > HEATMAP_LABEL_LIMIT:
        return [["" for _ in row] for row in correlation.values]

    def label(value: float) -> str:
        if pd.isna(value):
            return ""
        text = f"{value:.2f}"
        if text in {"1.00", "-1.00"}:
            return text[:-3]
        return text.replace("0.", ".", 1)

    return [[label(value) for value in row] for row in correlation.values]


def _heatmap_height(count: int) -> int:
    """Rows near-square with the cells: 24px each for a full universe, roomier for small ones."""
    row = 24 if count >= 40 else 32
    return max(520, count * row + 150)


@st.cache_data(show_spinner=False)
def _fetch_market_ohlc(
    ticker: str,
    history_period: str,
    refresh_token: str,
) -> pd.DataFrame:
    del refresh_token

    import yfinance as yf

    frame = yf.download(
        tickers=ticker,
        period=history_period,
        interval="1d",
        auto_adjust=False,
        actions=False,
        progress=False,
        threads=False,
    )
    if frame.empty:
        raise ValueError(f"Unable to load OHLC data for {ticker}.")

    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)

    frame = frame.rename_axis("Date").reset_index()
    required_columns = {"Date", "Open", "High", "Low", "Close"}
    if not required_columns.issubset(frame.columns):
        raise ValueError(f"OHLC columns missing for {ticker}.")

    selected_columns = [column for column in ["Date", "Open", "High", "Low", "Close", "Volume"] if column in frame.columns]
    return frame[selected_columns]


def _gradient_fill(theme: dict, color_key: str) -> dict:
    return {
        "type": "vertical",
        "colorscale": [[0.0, theme["clear"]], [1.0, theme[f"{color_key}_fill"]]],
    }


def _build_market_chart(
    prices: pd.DataFrame,
    ticker: str,
    history_period: str,
    lookback_label: str,
    refresh_token: str,
    visuals: dict,
) -> go.Figure:
    theme = plotly_theme(visuals)
    local_series = prices[ticker].dropna() if ticker in prices.columns else pd.Series(dtype=float)
    x_tickformat = "%b %Y"
    if lookback_label in {"1w", "3m"}:
        x_tickformat = "%d %b"

    layout = _build_time_series_layout(
        title=f"{ticker} Historical Price",
        y_label="Price (USD)",
        height=380,
        y_gridcolor=theme["grid"],
        x_tickformat=x_tickformat,
        visuals=visuals,
    )
    try:
        market_frame = _fetch_market_ohlc(ticker, history_period, refresh_token)
    except Exception:
        figure = go.Figure()
        figure.add_trace(
            go.Scatter(
                x=local_series.index,
                y=local_series.values,
                mode="lines",
                line={"width": 2, "color": theme["accent"]},
                fill="tozeroy",
                fillgradient=_gradient_fill(theme, "accent"),
                hovertemplate="Adj close  %{y:,.2f}<extra></extra>",
                name=f"{ticker} adjusted close",
            )
        )
        figure.update_layout(**layout)
        source_label = "Source: local adjusted-close refresh artifact"
    else:
        figure = go.Figure()
        figure.add_trace(
            go.Candlestick(
                x=market_frame["Date"],
                open=market_frame["Open"],
                high=market_frame["High"],
                low=market_frame["Low"],
                close=market_frame["Close"],
                increasing={"line": {"color": theme["pos"], "width": 1.2}, "fillcolor": theme["pos_fill"]},
                decreasing={"line": {"color": theme["neg"], "width": 1.2}, "fillcolor": theme["neg_fill"]},
                hovertemplate=(
                    "Open  %{open:,.2f}<br>High  %{high:,.2f}<br>"
                    "Low  %{low:,.2f}<br>Close  %{close:,.2f}<extra></extra>"
                ),
                name=ticker,
            )
        )
        figure.update_layout(**layout)
        figure.update_xaxes(rangeslider={"visible": False})
        source_label = "Source: yfinance OHLC"

    figure.add_annotation(
        xref="paper",
        yref="paper",
        x=1,
        y=1.1,
        xanchor="right",
        text=source_label,
        showarrow=False,
        font={"color": theme["ink_2"], "size": 11},
        bgcolor=theme["annotation_bg"],
        bordercolor=theme["annotation_border"],
        borderwidth=1,
        borderpad=4,
    )
    return figure


def _render_correlation_changes(
    current_correlation: pd.DataFrame,
    previous_correlation: pd.DataFrame,
    current_metadata: dict,
    previous_metadata: dict,
    previous_universe: pd.DataFrame,
    visuals: dict,
) -> None:
    changes = correlation_change_table(current_correlation, previous_correlation)
    if changes.empty:
        with _panel("changes", "delta", "Biggest correlation changes since the prior run", tint="rose"):
            st.info("No overlapping ticker pairs were available to compare against the prior run.")
        return

    current_tickers = set(current_metadata.get("tickers", list(current_correlation.columns)))
    previous_tickers = set(previous_metadata.get("tickers", list(previous_correlation.columns)))
    if not previous_tickers and not previous_universe.empty and "ticker" in previous_universe.columns:
        previous_tickers = {str(value).strip() for value in previous_universe["ticker"].tolist() if str(value).strip()}
    overlap_tickers = sorted(current_tickers.intersection(previous_tickers))
    added_tickers = sorted(current_tickers - previous_tickers)
    removed_tickers = sorted(previous_tickers - current_tickers)

    largest_move = changes.iloc[0]
    metric_left, metric_mid, metric_right = st.columns(3)
    metric_left.metric("Pairs compared", len(changes))
    metric_mid.metric("Largest |delta|", f"{largest_move['abs_change']:.3f}")
    metric_right.metric("Median |delta|", f"{changes['abs_change'].median():.3f}")

    run_left, run_mid, run_right = st.columns([1.15, 1.15, 1])
    with run_left:
        st.markdown(
            _status_card(
                "Current run",
                [
                    f"Created: {current_metadata.get('created_at_utc', 'n/a')}",
                    f"Window: {current_metadata.get('start_date', 'n/a')} to {current_metadata.get('end_date', 'n/a')}",
                    f"Tickers: {len(current_tickers)}",
                ],
                emblem="clock",
                tint="cyan",
            ),
            unsafe_allow_html=True,
        )
    with run_mid:
        st.markdown(
            _status_card(
                "Prior run",
                [
                    f"Created: {previous_metadata.get('created_at_utc', 'n/a')}",
                    f"Window: {previous_metadata.get('start_date', 'n/a')} to {previous_metadata.get('end_date', 'n/a')}",
                    f"Tickers: {len(previous_tickers)}",
                ],
                emblem="clock",
                tint="blue",
            ),
            unsafe_allow_html=True,
        )
    with run_right:
        st.markdown(
            _status_card(
                "Universe overlap",
                [
                    f"Common tickers: {len(overlap_tickers)}",
                    f"Added: {_summarize_tickers(added_tickers)}",
                    f"Removed: {_summarize_tickers(removed_tickers)}",
                ],
                emblem="venn",
                tint="violet",
            ),
            unsafe_allow_html=True,
        )

    with _panel(
        "changes",
        "delta",
        "Biggest correlation changes since the prior run",
        "Current minus prior correlation for every pair present in both runs",
        tint="rose",
    ):
        focus_left, focus_right = st.columns([1.2, 1])
        with focus_left:
            focus = st.radio(
                "Focus",
                options=[
                    "Largest absolute moves",
                    "Correlation increases",
                    "Correlation decreases",
                ],
                index=0,
                horizontal=True,
                key="correlation_change_focus",
            )
        with focus_right:
            max_rows = min(25, len(changes))
            default_rows = min(10, max_rows)
            top_n = st.slider(
                "Pairs to surface",
                min_value=1,
                max_value=max_rows,
                value=default_rows,
                step=1,
                key="correlation_change_top_n",
            )

        display_changes = _filter_correlation_changes(changes, focus, top_n)
        st.plotly_chart(
            _build_correlation_change_chart(display_changes, focus, visuals),
            width="stretch",
            config={"displayModeBar": False},
            theme=None,
        )

        display_table = display_changes[
            ["pair", "previous_correlation", "current_correlation", "change", "abs_change"]
        ].rename(
            columns={
                "previous_correlation": "prior_corr",
                "current_correlation": "current_corr",
            }
        )
        for column in ["prior_corr", "current_corr", "change", "abs_change"]:
            display_table[column] = display_table[column].round(3)
        st.dataframe(display_table, width="stretch", hide_index=True, height=320)

    with _panel("change_detail", "delta", "Pair change detail", "Prior and current correlation for one pair", tint="amber"):
        detail_pair = st.selectbox(
            "Pair",
            options=changes["pair"].tolist(),
            index=0,
            key="correlation_change_detail_pair",
        )
        detail = changes.loc[changes["pair"] == detail_pair].iloc[0]
        detail_left, detail_right = st.columns([1.2, 1])
        with detail_left:
            st.markdown(
                _status_card(
                    "Pair delta readout",
                    [
                        f"Pair: {detail['pair']}",
                        f"Prior correlation: {detail['previous_correlation']:.3f}",
                        f"Current correlation: {detail['current_correlation']:.3f}",
                        f"Net change: {detail['change']:+.3f}",
                        f"Absolute move: {detail['abs_change']:.3f}",
                    ],
                    emblem="delta",
                    tint="amber",
                ),
                unsafe_allow_html=True,
            )
        with detail_right:
            st.caption(
                "Positive deltas mean the pair became more correlated since the prior refresh; "
                "negative deltas mean the relationship weakened or moved further negative."
            )


def _filter_correlation_changes(changes: pd.DataFrame, focus: str, top_n: int) -> pd.DataFrame:
    if focus == "Correlation increases":
        ordered = changes.sort_values(["change", "abs_change", "pair"], ascending=[False, False, True])
    elif focus == "Correlation decreases":
        ordered = changes.sort_values(["change", "abs_change", "pair"], ascending=[True, False, True])
    else:
        ordered = changes.sort_values(["abs_change", "change", "pair"], ascending=[False, False, True])
    return ordered.head(top_n).copy()


def _build_correlation_change_chart(changes: pd.DataFrame, focus: str, visuals: dict) -> go.Figure:
    theme = plotly_theme(visuals)
    chart_data = changes.sort_values("change", ascending=True)
    colors = [theme["neg"] if value < 0 else theme["pos"] for value in chart_data["change"]]
    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=chart_data["change"],
            y=chart_data["pair"],
            orientation="h",
            marker={"color": colors, "line": {"width": 0}, "cornerradius": 3},
            customdata=list(zip(
                chart_data["previous_correlation"].round(3),
                chart_data["current_correlation"].round(3),
                # Signed strings: plotly.js rejects a "+" sign flag in hover formats.
                chart_data["change"].map(lambda value: f"{value:+.3f}"),
            )),
            hovertemplate=(
                "<b>%{y}</b><br>Change  %{customdata[2]}<br>Prior  %{customdata[0]:.3f}<br>"
                "Current  %{customdata[1]:.3f}<extra></extra>"
            ),
        )
    )
    figure.add_vline(x=0, line_width=1, line_color=theme["zero"])
    figure.update_layout(
        **_base_layout(visuals, height=max(320, len(chart_data) * 34 + 120), title=focus),
        margin={"l": 86, "r": 24, "t": 60, "b": 76},
        bargap=0.32,
        hovermode="closest",
        xaxis={
            "title": {"text": "Correlation change", "font": {"color": theme["ink_2"], "size": 12}, "standoff": 20},
            "tickfont": {"color": theme["ink_2"], "size": 11, "family": theme["mono_font"]},
            "gridcolor": theme["grid"],
            "zeroline": False,
            "automargin": True,
        },
        yaxis={
            "title": {"text": "Pair", "font": {"color": theme["ink_2"], "size": 12}, "standoff": 14},
            "tickfont": {"color": theme["ink"], "size": 11, "family": theme["mono_font"]},
            "automargin": True,
        },
    )
    return figure


def _summarize_tickers(tickers: list[str], limit: int = 3) -> str:
    if not tickers:
        return "None"
    if len(tickers) <= limit:
        return ", ".join(tickers)
    return f"{', '.join(tickers[:limit])} +{len(tickers) - limit} more"


def _render_cointegration_tab(
    pairs_qualified: pd.DataFrame,
    pairs_spreads: pd.DataFrame,
    pairs_metadata: dict,
    visuals: dict,
) -> None:
    top_limit = min(10, len(pairs_qualified))
    top_pairs = pairs_qualified.head(top_limit).copy()
    thresholds = pairs_metadata.get("thresholds", {})
    definitions = pairs_metadata.get("threshold_definitions", {})
    analysis_window = pairs_metadata.get("analysis_window", {})
    counts = pairs_metadata.get("counts", {})
    passed_lines = [
        f"Engle-Granger p-value: < {thresholds.get('cointegration_p_threshold', 'n/a')}",
        f"ADF statistic: < {thresholds.get('adf_stat_threshold', 'n/a')}",
        f"Effective overlap floor: {thresholds.get('minimum_rows_effective', 'n/a')} trading days",
    ]
    if thresholds.get("require_nonstationary_legs"):
        stationary = ", ".join(item["ticker"] for item in pairs_metadata.get("stationary_legs", [])) or "none"
        passed_lines.append(
            f"Both legs trend: price-level ADF p ≥ {thresholds.get('leg_adf_p_threshold', 0.05)}; "
            f"{counts.get('pairs_excluded_stationary_leg', 0)} pairs excluded; range-bound: {stationary}"
        )

    metric_left, metric_mid, metric_right = st.columns(3)
    metric_left.metric("Qualified pairs", pairs_metadata["counts"]["pairs_qualified"])
    metric_mid.metric(
        "Analysis window",
        f"{analysis_window.get('start_date', 'n/a')} → {analysis_window.get('end_date', 'n/a')}",
    )
    metric_right.metric(
        "Test lookback", period_label(str(pairs_metadata.get("history_period", "n/a"))).upper()
    )

    summary_col, definition_col = st.columns([1.5, 1])
    with summary_col:
        st.markdown(_status_card("What passed", passed_lines, emblem="check", tint="green"), unsafe_allow_html=True)
    with definition_col:
        st.markdown(
            _definition_card(
                "Threshold guide",
                [
                    ("Engle-Granger p-value", definitions.get("cointegration_p_threshold", "")),
                    ("ADF statistic", definitions.get("adf_stat_threshold", "")),
                    ("Effective overlap", definitions.get("minimum_rows_effective", "")),
                    ("Target overlap", definitions.get("minimum_rows_target", "")),
                    ("Rolling z-score", definitions.get("rolling_z_window", "")),
                    ("Trending legs", definitions.get("require_nonstationary_legs", "")),
                ],
            ),
            unsafe_allow_html=True,
        )

    display_columns = [
        "rank",
        "pair",
        "selected_orientation",
        "coint_p_value",
        "adf_stat",
        "half_life",
        "latest_zscore",
        "n_obs",
    ]
    rename_map = {
        "selected_orientation": "orientation",
        "coint_p_value": "coint_p",
        "adf_stat": "adf_stat",
        "half_life": "half_life_days",
        "latest_zscore": "latest_z",
    }
    display_table = top_pairs[display_columns].rename(columns=rename_map).copy()
    for column, decimals in {
        "coint_p": 4,
        "adf_stat": 3,
        "half_life_days": 2,
        "latest_z": 2,
    }.items():
        if column in display_table.columns:
            display_table[column] = display_table[column].round(decimals)
    with _panel(
        "coint",
        "tether",
        f"Top {top_limit} cointegrated pairs",
        "Pairs whose price spread tends to revert to its mean, ranked by test strength",
        tint="green",
    ):
        st.dataframe(display_table, width="stretch", hide_index=True, height=420)

    if pairs_spreads.empty:
        return

    with _panel(
        "spread",
        "tether",
        "Spread detail",
        "Rolling z-score of the hedged spread; dotted lines mark plus and minus 2",
        tint="cyan",
    ):
        pair_options = top_pairs["pair"].tolist()
        selected_pair = st.selectbox("Pair", options=pair_options, index=0, key="cointegration_pair")
        pair_history = pairs_spreads.loc[pairs_spreads["pair"] == selected_pair].copy()
        pair_row = top_pairs.loc[top_pairs["pair"] == selected_pair].iloc[0]

        detail_left, detail_right = st.columns([1.5, 1])
        with detail_left:
            st.plotly_chart(
                _build_spread_chart(pair_history, selected_pair, pair_row, visuals),
                width="stretch",
                config={"displayModeBar": False},
                theme=None,
            )
        with detail_right:
            st.markdown(
                _status_card(
                    "Pair readout",
                    [
                        f"Orientation: {pair_row['selected_orientation']}",
                        f"Current z-score: {pair_row['latest_zscore']:+.2f}",
                        f"Half-life: {pair_row['half_life']:.2f} days" if pd.notna(pair_row["half_life"]) else "Half-life: n/a",
                        f"Cointegration p-value: {pair_row['coint_p_value']:.4f}",
                        f"ADF statistic: {pair_row['adf_stat']:.3f}",
                    ],
                    emblem="tether",
                    tint="cyan",
                ),
                unsafe_allow_html=True,
            )


def _build_line_chart(
    series: pd.Series,
    title: str,
    y_label: str,
    visuals: dict,
    color_key: str = "accent",
) -> go.Figure:
    theme = plotly_theme(visuals)
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=series.index,
            y=series.values,
            mode="lines",
            line={"width": 2, "color": theme[color_key]},
            fill="tozeroy",
            fillgradient=_gradient_fill(theme, color_key),
            hovertemplate="Correlation  %{y:.3f}<extra></extra>",
        )
    )
    figure.update_layout(
        **_build_time_series_layout(
            title=title,
            y_label=y_label,
            height=420,
            y_range=[-1, 1],
            y_gridcolor=theme["grid_strong"],
            visuals=visuals,
        ),
    )
    return figure


def _build_spread_chart(
    pair_history: pd.DataFrame,
    pair_name: str,
    pair_row: pd.Series,
    visuals: dict,
) -> go.Figure:
    theme = plotly_theme(visuals)
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=pair_history["date"],
            y=pair_history["zscore"],
            mode="lines",
            line={"width": 2, "color": theme["accent"]},
            name="Z-score",
            hovertemplate="Z-score  %{y:.2f}<extra></extra>",
        )
    )
    figure.add_hline(y=0, line_width=1, line_color=theme["zero"])
    figure.add_hline(y=2, line_dash="dot", line_width=1.2, line_color=theme["warn"])
    figure.add_hline(y=-2, line_dash="dot", line_width=1.2, line_color=theme["warn"])
    figure.update_layout(
        **_build_time_series_layout(
            title=f"{pair_name} spread z-score",
            y_label="Z-score",
            height=420,
            y_gridcolor=theme["grid"],
            visuals=visuals,
        ),
    )
    annotation = (
        f"p {pair_row['coint_p_value']:.4f} · ADF {pair_row['adf_stat']:.3f} · "
        f"half-life {pair_row['half_life']:.2f}d"
        if pd.notna(pair_row["half_life"])
        else f"p {pair_row['coint_p_value']:.4f} · ADF {pair_row['adf_stat']:.3f}"
    )
    figure.add_annotation(
        xref="paper",
        yref="paper",
        x=1,
        y=1,
        xanchor="right",
        yanchor="bottom",
        text=annotation,
        showarrow=False,
        font={"color": theme["ink_2"], "size": 11, "family": theme["mono_font"]},
        bgcolor=theme["annotation_bg"],
        bordercolor=theme["annotation_border"],
        borderwidth=1,
        borderpad=4,
    )
    return figure


def _build_time_series_layout(
    title: str,
    y_label: str,
    height: int,
    y_gridcolor: str,
    visuals: dict,
    y_range: list[float] | None = None,
    x_tickformat: str = "%b %Y",
) -> dict:
    theme = plotly_theme(visuals)
    yaxis = {
        "title": {"text": y_label, "font": {"color": theme["ink_2"], "size": 12}, "standoff": 22},
        "tickfont": {"color": theme["ink_2"], "size": 11, "family": theme["mono_font"]},
        "gridcolor": y_gridcolor,
        "zerolinecolor": theme["zero"],
        "automargin": True,
        "ticklabelposition": "outside",
    }
    if y_range is not None:
        yaxis["range"] = y_range

    return {
        **_base_layout(visuals, height=height, title=title),
        "margin": {"l": 86, "r": 24, "t": 62, "b": 76},
        "xaxis": {
            "title": {"text": "Date", "font": {"color": theme["ink_2"], "size": 12}, "standoff": 22},
            "tickfont": {"color": theme["ink_2"], "size": 11, "family": theme["mono_font"]},
            "gridcolor": theme["grid"],
            "automargin": True,
            "tickformat": x_tickformat,
            "hoverformat": "%a %d %b %Y",
            # Crosshair: a thin dotted spike that follows the cursor.
            "showspikes": True,
            "spikemode": "across",
            "spikesnap": "cursor",
            "spikethickness": -1,  # negative: no contrasting outline under the spike
            "spikedash": "dot",
            "spikecolor": theme["spike"],
        },
        "yaxis": yaxis,
        "hovermode": "x",  # single-series charts; "x unified" overrides the spike styling
        "spikedistance": -1,
    }


def _esc(value: object) -> str:
    """HTML-escape a data-derived value before it goes into unsafe_allow_html markup."""
    return html.escape(str(value))


def _definition_card(
    title: str,
    entries: list[tuple[str, str]],
    emblem: str = "gauge",
    tint: str = "amber",
) -> str:
    items = "".join(
        f"<li><strong>{_esc(label)}:</strong> {_esc(definition)}</li>"
        for label, definition in entries
        if definition
    )
    return (
        "<div class='cd-card'>"
        f"{panel_head(emblem, title, tint=tint)}"
        f"<ul class='cd-defs'>{items}</ul>"
        "</div>"
    )


def _status_card(title: str, lines: list[str], emblem: str = "check", tint: str = "cyan") -> str:
    """Card with label/value rows; each line is "Label: value" (or a bare value)."""
    rows = ""
    for line in lines:
        label, sep, value = str(line).partition(": ")
        if not sep:
            label, value = "", label
        rows += (
            "<li class='cd-row'>"
            f"<span class='cd-row-label'>{_esc(label)}</span>"
            f"<span class='cd-row-value'>{_esc(value)}</span>"
            "</li>"
        )
    return (
        "<div class='cd-card'>"
        f"{panel_head(emblem, title, tint=tint)}"
        f"<ul class='cd-rows'>{rows}</ul>"
        "</div>"
    )


def _rerun_enabled(config) -> bool:
    return bool(config.payload.get("dashboard", {}).get("enable_rerun", True))


def _render_rerun_panel(config, config_path: Path, root: Path, is_etf_run: bool) -> None:
    """Pick new lookbacks and regenerate the artifacts in a background job (see rerun_job.py)."""
    if not _rerun_enabled(config):
        return
    metadata_path = config.paths["metadata_json"]
    job_dir = metadata_path.parent
    pairs_metadata_path = config.paths.get("pairs_metadata_json")
    current = _read_optional_json(metadata_path if metadata_path.exists() else None)
    current_pairs = _read_optional_json(pairs_metadata_path)
    price_choices = [str(c) for c in config.history.get("prompt_choices", [])] or ["1y", "2y"]
    pair_choices = [str(c) for c in config.pairs_trading.get("prompt_choices", [])] or ["1y"]
    price_now = str(current.get("prices", {}).get("period") or config.history["period"])
    pair_now = str(current_pairs.get("history_period") or config.pairs_trading.get("history_period", "1y"))
    job = rerun_job.read_status(job_dir)
    running = job.get("state") == "running"

    with st.expander(
        f"Lookback · price history {period_label(price_now)} · cointegration {period_label(pair_now)}",
        expanded=running,
    ):
        left, mid, right = st.columns([1, 1, 0.8])
        price_period = left.selectbox(
            "Price-history lookback",
            price_choices,
            index=price_choices.index(price_now) if price_now in price_choices else 0,
            format_func=period_label,
            key="rerun_price_period",
            disabled=running,
        )
        pair_period = mid.selectbox(
            "Cointegration lookback",
            pair_choices,
            index=pair_choices.index(pair_now) if pair_now in pair_choices else 0,
            format_func=period_label,
            key="rerun_pair_period",
            disabled=running,
        )
        right.markdown("<div style='height:1.75rem'></div>", unsafe_allow_html=True)
        clicked = right.button(
            "Re-run analysis", type="primary", width="stretch", disabled=running
        )
        st.caption(
            "Re-fetches prices and recomputes returns, the correlation matrix, cointegration pairs and "
            "both workbooks for the selected windows in the background. The current run is kept as the "
            "prior-run snapshot, and stays in place if the re-run fails. Short windows are noisy: 1w gives "
            "only ~4 daily returns per pair, and cointegration needs at least 20 overlapping days, so it "
            "starts at 1m."
        )

        if clicked:
            started, message = rerun_job.start_job(
                job_dir,
                _rerun_command(config, config_path, root, is_etf_run, current, price_period, pair_period),
                cwd=root,
                env=_rerun_env(root),
                labels={"price_period": price_period, "pair_period": pair_period},
            )
            if not started:
                st.warning(message)
            else:
                st.rerun()

        if running:
            st.fragment(run_every="2s")(_render_rerun_progress)(str(job_dir))
        else:
            _render_rerun_result(job, job_dir)


def _rerun_command(
    config,
    config_path: Path,
    root: Path,
    is_etf_run: bool,
    current: dict,
    price_period: str,
    pair_period: str,
) -> list[str]:
    if is_etf_run:
        command = [
            sys.executable,
            "-m",
            "nasdaq_correlation_dashboard.commands.etf",
            "--etf",
            str(config.universe_policy["index_symbol"]),
        ]
        holdings = current.get("universe", {}).get("official_source", {}).get("path")
        if holdings and Path(holdings).exists():
            command += ["--holdings", holdings]
        # Keep the holdings count the run was made with (the subprocess has no TTY to prompt).
        top_n = config.universe_policy.get("requested_top_n")
        if top_n is not None:
            command += ["--top-n", str(top_n)]
    else:
        command = [sys.executable, "-m", "nasdaq_correlation_dashboard.commands.update", "--config", str(config_path)]
    return command + ["--history-period", price_period, "--pairs-history-period", pair_period]


def _rerun_env(root: Path) -> dict[str, str]:
    env = os.environ.copy()
    src = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONUNBUFFERED"] = "1"  # so the progress panel's log tail updates while the job runs
    return env


def _render_rerun_progress(job_dir_text: str) -> None:
    """Polled every 2s while a job runs; reloads the whole app once it finishes."""
    job_dir = Path(job_dir_text)
    job = rerun_job.read_status(job_dir)
    if job.get("state") != "running":
        st.rerun(scope="app")
        return
    started = pd.Timestamp(job.get("started_at")) if job.get("started_at") else None
    elapsed = (
        f" · {int((pd.Timestamp.now(tz='UTC') - started).total_seconds())}s elapsed" if started is not None else ""
    )
    st.info(
        f"Re-running with {period_label(str(job.get('price_period', '?')))} of prices and a "
        f"{period_label(str(job.get('pair_period', '?')))} cointegration window{elapsed}. "
        "This usually takes a minute or two; you can reload or leave the page."
    )
    tail = rerun_job.log_tail(job_dir, lines=8)
    if tail:
        st.code(tail, language="text")
    if st.button("Cancel re-run", key="rerun_cancel"):
        rerun_job.cancel_job(job_dir)
        st.rerun(scope="app")


def _render_rerun_result(job: dict, job_dir: Path) -> None:
    state = job.get("state")
    if state not in {"succeeded", "failed", "cancelled"}:
        return
    finished = job.get("finished_at", "")
    if state == "succeeded":
        st.success(f"Last re-run finished at {finished}.")
        return
    if state == "cancelled":
        st.warning(f"Last re-run was cancelled at {finished}; the artifacts shown are from the run before it.")
        return
    st.error(
        f"Last re-run failed at {finished}. The artifacts shown are from the last successful run."
        + (f" {job['error']}" if job.get("error") else "")
    )
    tail = rerun_job.log_tail(job_dir, lines=40)
    if tail:
        st.code(tail[-3000:], language="text")


def _read_optional_csv(
    path: Path | None,
    parse_dates: list[str] | None = None,
    index_col: int | str | None = None,
) -> pd.DataFrame:
    if path is None or not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, parse_dates=parse_dates, index_col=index_col)
    except pd.errors.EmptyDataError:
        # e.g. the spreads export when no pair qualifies (common on 1w/1m lookbacks)
        return pd.DataFrame()


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:  # artifacts outside the config's project root
        return str(path)


def _read_optional_json(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))




if __name__ == "__main__":
    main()
