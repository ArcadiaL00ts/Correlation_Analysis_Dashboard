from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

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
from nasdaq_correlation_dashboard.net import configure_tls
from nasdaq_correlation_dashboard.settings import load_config
from nasdaq_correlation_dashboard.theme import inject_styles, plotly_theme, resolve_theme_tokens

HEATMAP_MARKET_DEFAULT_TICKER = "QQQM"
HEATMAP_MARKET_LOOKBACKS = {
    "1y": "1y",
    "6m": "6mo",
    "3m": "3mo",
    "1w": "5d",
}



def main() -> None:
    configure_tls()
    root = Path(__file__).resolve().parents[2]
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

    st.markdown("<div class='hero-shell'>", unsafe_allow_html=True)
    # Escape "$" so a ticker-style title ("$TAN ...") is not parsed as LaTeX by Streamlit markdown.
    st.title(config.visuals["page_title"].replace("$", r"\$"))
    st.markdown(
        (
            "<div class='hero-subtitle'>"
            + (
                f"{universe_label} weighted by the fund's own holdings export, "
                "with locally computed correlations."
                if is_etf_run
                else "Official Nasdaq membership authority with transparent top-50 ranking fallbacks "
                "and locally computed correlations."
            )
            + "</div>"
        ),
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    _render_rerun_panel(config, config_path, root, is_etf_run)

    if missing:
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

    universe_count = len(universe)
    average_corr = average_pairwise_correlation(correlation)
    ranking_type = metadata["universe"]["ranking"]["source_type"] or "unresolved"
    fallback_flag = "Yes" if metadata["universe"]["ranking"]["fallback_used"] else "No"
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
    metric_a.metric("Universe Size", universe_count)
    metric_b.metric("Window", f"{metadata['start_date']} → {metadata['end_date']}")
    metric_c.metric("Average Pair Corr", f"{average_corr:.3f}")
    metric_d.metric("Cointegrated Pairs", qualified_count if qualified_count else "n/a")

    status_left, status_right = st.columns([1.2, 1])
    with status_left:
        st.markdown(
            _status_card(
                "Universe Provenance",
                [
                    f"Official trade date: {metadata['universe']['official_source']['trade_date']}",
                    f"Ranking source: {ranking_type}",
                    f"Resolved tickers: {len(metadata['universe']['final_tickers'])}",
                ],
            ),
            unsafe_allow_html=True,
        )
    with status_right:
        st.markdown(
            _status_card(
                "Refresh Status",
                [
                    f"Rows validated: {metadata['validation']['observed_rows']}",
                    f"Missing ratio: {metadata['validation']['observed_missing_ratio']:.2%}",
                    f"Workbook: {paths['excel_workbook'].name}",
                ],
            ),
            unsafe_allow_html=True,
        )

    st.markdown("<div class='section-gap section-gap-tabs'></div>", unsafe_allow_html=True)

    heatmap_tab, rolling_tab, cointegration_tab, universe_tab, run_tab = st.tabs(
        ["Heatmap", "Rolling Research", "Cointegration", "Universe", "Run Status"]
    )

    with heatmap_tab:
        st.subheader("Historical Price and Correlation Heatmap")
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
        st.caption(
            "Candlestick view when OHLC data is available from yfinance; local adjusted-close line fallback otherwise."
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
            use_container_width=True,
            config={"displayModeBar": False},
            theme=None,
        )

        st.markdown("<div class='section-gap section-gap-block'></div>", unsafe_allow_html=True)
        st.plotly_chart(
            _build_heatmap(correlation, config.visuals),
            use_container_width=True,
            config={"displayModeBar": False},
            theme=None,
        )

        st.markdown("<div class='section-gap section-gap-block'></div>", unsafe_allow_html=True)
        strongest_col, weakest_col = st.columns(2)
        with strongest_col:
            st.subheader("Strongest Pairs")
            st.dataframe(
                strongest_pairs,
                use_container_width=True,
                hide_index=True,
                height=420,
            )
        with weakest_col:
            st.subheader("Weakest Pairs")
            st.dataframe(
                weakest_pairs,
                use_container_width=True,
                hide_index=True,
                height=420,
            )

        st.markdown("<div class='section-gap section-gap-block'></div>", unsafe_allow_html=True)
        st.subheader("Rolling Average Correlation")
        window = st.select_slider(
            "Rolling Window",
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
            use_container_width=True,
            config={"displayModeBar": False},
            theme=None,
        )

    with rolling_tab:
        st.subheader("Biggest Correlation Changes From Prior Run")
        if previous_correlation.empty or not previous_metadata:
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

        st.markdown("<div class='section-gap section-gap-block'></div>", unsafe_allow_html=True)
        st.subheader("Pair Diagnostics")
        pair_options = [item["pair"] for item in ranked_pairs(correlation, limit=50, ascending=False)]
        pair_options += [
            item["pair"]
            for item in ranked_pairs(correlation, limit=50, ascending=True)
            if item["pair"] not in pair_options
        ]
        if not pair_options:
            st.info("Pair diagnostics are unavailable because the correlation matrix did not yield any valid pairs.")
        else:
            selected_pair = st.selectbox("Pair", options=pair_options, index=0)
            rolling_window = st.select_slider(
                "Rolling Pair Window",
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
                ),
                use_container_width=True,
                config={"displayModeBar": False},
                theme=None,
            )

            snapshot = returns[[left, right]].tail(15).copy()
            snapshot.index = snapshot.index.strftime("%Y-%m-%d")
            st.dataframe(snapshot, use_container_width=True)

    with cointegration_tab:
        st.subheader("Top 10 Cointegrated Pairs")
        if pairs_qualified.empty or not pairs_metadata:
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
        st.subheader(f"Resolved {universe_title} Universe")
        zero_share = metadata.get("zero_return_share") or {}
        universe_view = universe.copy()
        if zero_share:
            universe_view["zero_return_days"] = universe_view["ticker"].map(zero_share)
        st.dataframe(
            universe_view,
            use_container_width=True,
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
        st.subheader("Source Lineage")
        lineage = {
            "official_source": metadata["universe"]["official_source"],
            "ranking": metadata["universe"]["ranking"],
            "history_substitutions": substitutions,
        }
        st.json(lineage, expanded=False)

    with run_tab:
        st.subheader("Validation And Outputs")
        outputs = pd.DataFrame(
            [
                {
                    "artifact": name,
                    "path": str(path.relative_to(root)),
                    "exists": path.exists(),
                    "size_bytes": path.stat().st_size if path.exists() else None,
                }
                for name, path in {**required, **{k: v for k, v in optional.items() if v is not None}}.items()
            ]
        )
        st.dataframe(outputs, use_container_width=True, hide_index=True)
        st.subheader("Metadata")
        st.json(metadata, expanded=False)


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
            colorbar={
                "title": {"text": "Corr", "font": {"color": theme["text_primary"], "size": 15}},
                "tickfont": {"color": theme["text_primary"], "size": 12},
            },
            text=display_correlation.round(2).values,
            texttemplate="%{text}",
            hovertemplate="X: %{x}<br>Y: %{y}<br>Corr: %{z:.4f}<extra></extra>",
        )
    )
    figure.update_layout(
        height=max(900, len(display_correlation.index) * 18),
        margin={"l": 22, "r": 22, "t": 54, "b": 48},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": theme["mono_font"], "size": 13, "color": theme["text_primary"]},
    )
    figure.update_xaxes(
        side="top",
        tickangle=-32,
        automargin=True,
        tickfont={"color": theme["text_primary"], "size": 12},
    )
    figure.update_yaxes(
        automargin=True,
        tickfont={"color": theme["text_primary"], "size": 12},
    )
    return figure


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
    if lookback_label == "1w":
        x_tickformat = "%d %b"
    elif lookback_label == "3m":
        x_tickformat = "%d %b"

    try:
        market_frame = _fetch_market_ohlc(ticker, history_period, refresh_token)
    except Exception:
        figure = go.Figure()
        figure.add_trace(
            go.Scatter(
                x=local_series.index,
                y=local_series.values,
                mode="lines",
                line={"width": 2.8, "color": theme["accent_cyan"]},
                fill="tozeroy",
                fillcolor=theme["line_fill"],
                hovertemplate="%{x|%Y-%m-%d}<br>Adj Close: %{y:.2f}<extra></extra>",
                name=f"{ticker} adjusted close",
            )
        )
        figure.update_layout(
            **_build_time_series_layout(
                title=f"{ticker} Historical Price",
                y_label="Price (USD)",
                height=360,
                y_gridcolor=theme["y_grid_soft"],
                x_tickformat=x_tickformat,
                visuals=visuals,
            ),
            showlegend=False,
        )
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
                increasing={
                    "line": {"color": theme["success_color"]},
                    "fillcolor": theme["success_fill"],
                },
                decreasing={
                    "line": {"color": theme["danger_color"]},
                    "fillcolor": theme["danger_fill"],
                },
                hovertemplate=(
                    "%{x|%Y-%m-%d}<br>Open: %{open:.2f}<br>High: %{high:.2f}<br>"
                    "Low: %{low:.2f}<br>Close: %{close:.2f}<extra></extra>"
                ),
                name=ticker,
            )
        )
        figure.update_layout(
            **_build_time_series_layout(
                title=f"{ticker} Historical Price",
                y_label="Price (USD)",
                height=360,
                y_gridcolor=theme["y_grid_soft"],
                x_tickformat=x_tickformat,
                visuals=visuals,
            ),
            showlegend=False,
        )
        figure.update_xaxes(rangeslider={"visible": False})
        source_label = "Source: yfinance OHLC"

    figure.add_annotation(
        xref="paper",
        yref="paper",
        x=0.995,
        y=1.08,
        xanchor="right",
        text=source_label,
        showarrow=False,
        font={"color": theme["text_primary"], "size": 12},
        bgcolor=theme["annotation_bg"],
        bordercolor=theme["annotation_border"],
        borderwidth=1,
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
    metric_left.metric("Pairs Compared", len(changes))
    metric_mid.metric("Largest |Delta|", f"{largest_move['abs_change']:.3f}")
    metric_right.metric("Median |Delta|", f"{changes['abs_change'].median():.3f}")

    run_left, run_mid, run_right = st.columns([1.15, 1.15, 1])
    with run_left:
        st.markdown(
            _status_card(
                "Current Run",
                [
                    f"Created: {current_metadata.get('created_at_utc', 'n/a')}",
                    f"Window: {current_metadata.get('start_date', 'n/a')} to {current_metadata.get('end_date', 'n/a')}",
                    f"Tickers: {len(current_tickers)}",
                ],
            ),
            unsafe_allow_html=True,
        )
    with run_mid:
        st.markdown(
            _status_card(
                "Prior Run",
                [
                    f"Created: {previous_metadata.get('created_at_utc', 'n/a')}",
                    f"Window: {previous_metadata.get('start_date', 'n/a')} to {previous_metadata.get('end_date', 'n/a')}",
                    f"Tickers: {len(previous_tickers)}",
                ],
            ),
            unsafe_allow_html=True,
        )
    with run_right:
        st.markdown(
            _status_card(
                "Universe Overlap",
                [
                    f"Common tickers: {len(overlap_tickers)}",
                    f"Added: {_summarize_tickers(added_tickers)}",
                    f"Removed: {_summarize_tickers(removed_tickers)}",
                ],
            ),
            unsafe_allow_html=True,
        )

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
            "Pairs To Surface",
            min_value=1,
            max_value=max_rows,
            value=default_rows,
            step=1,
            key="correlation_change_top_n",
        )

    display_changes = _filter_correlation_changes(changes, focus, top_n)
    st.plotly_chart(
        _build_correlation_change_chart(display_changes, focus, visuals),
        use_container_width=True,
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
    st.dataframe(display_table, use_container_width=True, hide_index=True, height=320)

    detail_pair = st.selectbox(
        "Pair Change Detail",
        options=changes["pair"].tolist(),
        index=0,
        key="correlation_change_detail_pair",
    )
    detail = changes.loc[changes["pair"] == detail_pair].iloc[0]
    detail_left, detail_right = st.columns([1.2, 1])
    with detail_left:
        st.markdown(
            _status_card(
                "Pair Delta Readout",
                [
                    f"Pair: {detail['pair']}",
                    f"Prior correlation: {detail['previous_correlation']:.3f}",
                    f"Current correlation: {detail['current_correlation']:.3f}",
                    f"Net change: {detail['change']:+.3f}",
                    f"Absolute move: {detail['abs_change']:.3f}",
                ],
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
    colors = [theme["danger_color"] if value < 0 else theme["success_color"] for value in chart_data["change"]]
    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=chart_data["change"],
            y=chart_data["pair"],
            orientation="h",
            marker={"color": colors, "line": {"color": theme["bar_border"], "width": 1}},
            customdata=chart_data[["previous_correlation", "current_correlation", "abs_change"]].to_numpy(),
            hovertemplate=(
                "%{y}<br>Delta: %{x:+.3f}<br>Prior: %{customdata[0]:.3f}<br>"
                "Current: %{customdata[1]:.3f}<br>|Delta|: %{customdata[2]:.3f}<extra></extra>"
            ),
        )
    )
    figure.add_vline(x=0, line_width=1, line_color=theme["axis_zero"])
    figure.update_layout(
        title={"text": focus, "x": 0.5, "xanchor": "center"},
        margin={"l": 86, "r": 24, "t": 60, "b": 76},
        height=max(320, len(chart_data) * 36 + 120),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=theme["plot_bg"],
        font={"family": theme["ui_font"], "size": 13, "color": theme["text_primary"]},
        title_font={"color": theme["text_primary"], "size": 22},
        xaxis={
            "title": {
                "text": "Correlation Change",
                "font": {"color": theme["text_primary"], "size": 15},
                "standoff": 20,
            },
            "tickfont": {"color": theme["text_primary"], "size": 12},
            "gridcolor": theme["x_grid"],
            "zerolinecolor": theme["axis_zero"],
            "automargin": True,
            "ticks": "outside",
        },
        yaxis={
            "title": {
                "text": "Pair",
                "font": {"color": theme["text_primary"], "size": 15},
                "standoff": 14,
            },
            "tickfont": {"color": theme["text_primary"], "size": 12},
            "automargin": True,
        },
        hovermode="y unified",
        showlegend=False,
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
        f"Engle-Granger p-value < {thresholds.get('cointegration_p_threshold', 'n/a')}",
        f"ADF statistic < {thresholds.get('adf_stat_threshold', 'n/a')}",
        f"Effective overlap floor: {thresholds.get('minimum_rows_effective', 'n/a')} trading days",
    ]
    if thresholds.get("require_nonstationary_legs"):
        stationary = ", ".join(item["ticker"] for item in pairs_metadata.get("stationary_legs", [])) or "none"
        passed_lines.append(
            f"Both legs trend (price-level ADF p ≥ {thresholds.get('leg_adf_p_threshold', 0.05)}); "
            f"{counts.get('pairs_excluded_stationary_leg', 0)} pairs excluded; range-bound: {stationary}"
        )

    metric_left, metric_mid, metric_right = st.columns(3)
    metric_left.metric("Qualified Pairs", pairs_metadata["counts"]["pairs_qualified"])
    metric_mid.metric(
        "Analysis Window",
        f"{analysis_window.get('start_date', 'n/a')} → {analysis_window.get('end_date', 'n/a')}",
    )
    metric_right.metric(
        "Test Lookback", period_label(str(pairs_metadata.get("history_period", "n/a"))).upper()
    )

    summary_col, definition_col = st.columns([1.5, 1])
    with summary_col:
        st.markdown(
            _status_card(
                "What Passed",
                passed_lines,
            ),
            unsafe_allow_html=True,
        )
    with definition_col:
        st.markdown(
            _definition_card(
                "Threshold Guide",
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
    st.dataframe(
        display_table,
        use_container_width=True,
        hide_index=True,
        height=420,
    )

    if pairs_spreads.empty:
        return

    pair_options = top_pairs["pair"].tolist()
    selected_pair = st.selectbox("Top Pair Detail", options=pair_options, index=0, key="cointegration_pair")
    pair_history = pairs_spreads.loc[pairs_spreads["pair"] == selected_pair].copy()
    pair_row = top_pairs.loc[top_pairs["pair"] == selected_pair].iloc[0]

    detail_left, detail_right = st.columns([1.5, 1])
    with detail_left:
        st.plotly_chart(
            _build_spread_chart(pair_history, selected_pair, pair_row, visuals),
            use_container_width=True,
            config={"displayModeBar": False},
            theme=None,
        )
    with detail_right:
        st.markdown(
            _status_card(
                "Pair Readout",
                [
                    f"Orientation: {pair_row['selected_orientation']}",
                    f"Current z-score: {pair_row['latest_zscore']:.2f}",
                    f"Half-life: {pair_row['half_life']:.2f} days" if pd.notna(pair_row["half_life"]) else "Half-life: n/a",
                    f"Cointegration p-value: {pair_row['coint_p_value']:.4f}",
                    f"ADF statistic: {pair_row['adf_stat']:.3f}",
                ],
            ),
            unsafe_allow_html=True,
        )


def _build_line_chart(series: pd.Series, title: str, y_label: str, visuals: dict) -> go.Figure:
    theme = plotly_theme(visuals)
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=series.index,
            y=series.values,
            mode="lines",
            line={"width": 3, "color": theme["accent_amber"]},
            fill="tozeroy",
            fillcolor=theme["amber_fill"],
            hovertemplate="%{x|%Y-%m-%d}<br>Value: %{y:.3f}<extra></extra>",
        )
    )
    figure.update_layout(
        **_build_time_series_layout(
            title=title,
            y_label=y_label,
            height=420,
            y_range=[-1, 1],
            y_gridcolor=theme["y_grid_strong"],
            visuals=visuals,
        ),
        showlegend=False,
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
            line={"width": 2.8, "color": theme["success_color"]},
            name="Z-score",
            hovertemplate="%{x|%Y-%m-%d}<br>Z-score: %{y:.2f}<extra></extra>",
        )
    )
    figure.add_hline(y=0, line_width=1, line_color=theme["axis_zero"])
    figure.add_hline(y=2, line_dash="dot", line_color=theme["accent_amber"])
    figure.add_hline(y=-2, line_dash="dot", line_color=theme["accent_amber"])
    figure.update_layout(
        **_build_time_series_layout(
            title=f"{pair_name} spread z-score",
            y_label="Z-score",
            height=420,
            y_gridcolor=theme["y_grid_soft"],
            visuals=visuals,
        ),
        showlegend=False,
    )
    annotation = (
        f"p={pair_row['coint_p_value']:.4f} | ADF={pair_row['adf_stat']:.3f} | "
        f"half-life={pair_row['half_life']:.2f}d"
        if pd.notna(pair_row["half_life"])
        else f"p={pair_row['coint_p_value']:.4f} | ADF={pair_row['adf_stat']:.3f}"
    )
    figure.add_annotation(
        xref="paper",
        yref="paper",
        x=0.99,
        y=0.98,
        xanchor="right",
        text=annotation,
        showarrow=False,
        font={"color": theme["text_primary"], "size": 12},
        bgcolor=theme["annotation_bg"],
        bordercolor=theme["annotation_border"],
        borderwidth=1,
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
        "title": {
            "text": y_label,
            "font": {"color": theme["text_primary"], "size": 15},
            "standoff": 22,
        },
        "tickfont": {"color": theme["text_primary"], "size": 12},
        "gridcolor": y_gridcolor,
        "zerolinecolor": theme["axis_zero"],
        "automargin": True,
        "ticks": "outside",
        "ticklabelposition": "outside",
    }
    if y_range is not None:
        yaxis["range"] = y_range

    return {
        "title": {"text": title, "x": 0.5, "xanchor": "center"},
        "margin": {"l": 86, "r": 24, "t": 62, "b": 76},
        "height": height,
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": theme["plot_bg"],
        "title_font": {"color": theme["text_primary"], "size": 22},
        "xaxis": {
            "title": {
                "text": "Date",
                "font": {"color": theme["text_primary"], "size": 15},
                "standoff": 22,
            },
            "tickfont": {"color": theme["text_primary"], "size": 12},
            "gridcolor": theme["x_grid"],
            "automargin": True,
            "ticks": "outside",
            "tickformat": x_tickformat,
        },
        "yaxis": yaxis,
        "font": {"family": theme["ui_font"], "size": 13, "color": theme["text_primary"]},
        "hovermode": "x unified",
    }


def _definition_card(title: str, entries: list[tuple[str, str]]) -> str:
    items = "".join(
        f"<li><strong>{label}:</strong> {definition}</li>"
        for label, definition in entries
        if definition
    )
    return (
        "<div class='definition-card'>"
        f"<h4>{title}</h4>"
        f"<ul>{items}</ul>"
        "</div>"
    )


def _status_card(title: str, lines: list[str]) -> str:
    items = "".join(f"<li>{line}</li>" for line in lines)
    return (
        "<div class='status-card'>"
        f"<h4>{title}</h4>"
        f"<ul>{items}</ul>"
        "</div>"
    )


def _render_rerun_panel(config, config_path: Path, root: Path, is_etf_run: bool) -> None:
    """Pick new lookbacks and regenerate the artifacts through the pipeline script, then reload."""
    metadata_path = config.paths["metadata_json"]
    pairs_metadata_path = config.paths.get("pairs_metadata_json")
    current = _read_optional_json(metadata_path if metadata_path.exists() else None)
    current_pairs = _read_optional_json(pairs_metadata_path)
    price_choices = [str(c) for c in config.history.get("prompt_choices", [])] or ["1y", "2y"]
    pair_choices = [str(c) for c in config.pairs_trading.get("prompt_choices", [])] or ["1y"]
    price_now = str(current.get("prices", {}).get("period") or config.history["period"])
    pair_now = str(current_pairs.get("history_period") or config.pairs_trading.get("history_period", "1y"))

    with st.expander(
        f"Lookback · price history {period_label(price_now)} · cointegration {period_label(pair_now)}",
        expanded=False,
    ):
        left, mid, right = st.columns([1, 1, 0.8])
        price_period = left.selectbox(
            "Price-history lookback",
            price_choices,
            index=price_choices.index(price_now) if price_now in price_choices else 0,
            format_func=period_label,
            key="rerun_price_period",
        )
        pair_period = mid.selectbox(
            "Cointegration lookback",
            pair_choices,
            index=pair_choices.index(pair_now) if pair_now in pair_choices else 0,
            format_func=period_label,
            key="rerun_pair_period",
        )
        right.markdown("<div style='height:1.75rem'></div>", unsafe_allow_html=True)
        clicked = right.button("Re-run analysis", type="primary", use_container_width=True)
        st.caption(
            "Re-fetches prices and recomputes returns, the correlation matrix, cointegration pairs and "
            "both workbooks for the selected windows. The current run is kept as the prior-run snapshot. "
            "Short windows are noisy: 1w gives only ~4 daily returns per pair, and cointegration needs at "
            "least 20 overlapping days, so it starts at 1m."
        )
        if not clicked:
            return

        if is_etf_run:
            command = [
                sys.executable,
                str(root / "scripts" / "run_etf_correlation.py"),
                "--etf",
                str(config.universe_policy["index_symbol"]),
            ]
            holdings = current.get("universe", {}).get("official_source", {}).get("path")
            if holdings and Path(holdings).exists():
                command += ["--holdings", holdings]
        else:
            command = [
                sys.executable,
                str(root / "scripts" / "update_dashboard.py"),
                "--config",
                str(config_path),
            ]
        command += ["--history-period", price_period, "--pairs-history-period", pair_period]

        env = os.environ.copy()
        src = str(root / "src")
        env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        # The themed spinner renders as a ring (theme.py), so the progress message sits beside it.
        status = st.empty()
        status.info(
            f"Re-running with {period_label(price_period)} of prices and a {period_label(pair_period)} "
            "cointegration window. "
            "This usually takes a minute or two."
        )
        with st.spinner(""):
            completed = subprocess.run(
                command,
                cwd=root,
                env=env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=1800,
                check=False,
            )
        status.empty()
        if completed.returncode != 0:
            st.error("Re-run failed; the previous artifacts are unchanged where the run stopped early.")
            st.code((completed.stderr or completed.stdout)[-3000:], language="text")
            return
        st.cache_data.clear()
        st.rerun()


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


def _read_optional_json(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))




if __name__ == "__main__":
    main()
