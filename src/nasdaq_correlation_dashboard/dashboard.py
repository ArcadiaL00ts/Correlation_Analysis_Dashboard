from __future__ import annotations

import json
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
from nasdaq_correlation_dashboard.settings import load_config

HEATMAP_MARKET_DEFAULT_TICKER = "QQQM"
HEATMAP_MARKET_LOOKBACKS = {
    "1y": "1y",
    "6m": "6mo",
    "3m": "3mo",
    "1w": "5d",
}
TERMINAL_VISUAL_DEFAULTS = {
    "accent_cyan": "#58C8FF",
    "accent_amber": "#7BA9FF",
    "success_color": "#22C55E",
    "danger_color": "#FB7185",
    "panel_bg_rgba": "rgba(10, 22, 40, 0.78)",
    "hover_glow_rgba": "rgba(88, 200, 255, 0.30)",
    "ascii_opacity": 0.15,
    "ascii_density": 24,
    "hero_font": "Bebas Neue",
    "ui_font": "Sora",
    "mono_font": "JetBrains Mono",
    "text_primary": "#EAF2FF",
    "text_muted": "#A4B8D7",
    "heatmap_min_color": "#7D3A4A",
    "heatmap_mid_color": "#DCE7F6",
    "heatmap_max_color": "#1C8BC4",
    "background_start": "#071222",
    "background_end": "#152B47",
    "panel_border": "rgba(122,157,205,0.34)",
}


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    config = load_config(root / "config" / "dashboard_config.json")
    paths = config.paths

    st.set_page_config(
        page_title=config.visuals["page_title"],
        page_icon=":chart_with_upwards_trend:",
        layout="wide",
    )
    _inject_styles(config.visuals)

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
    st.title(config.visuals["page_title"])
    st.markdown(
        (
            "<div class='hero-subtitle'>"
            "Official Nasdaq membership authority with transparent top-50 ranking fallbacks "
            "and locally computed correlations."
            "</div>"
        ),
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

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
    default_window = (
        config.rolling_windows[1] if len(config.rolling_windows) > 1 else config.rolling_windows[0]
    )
    qualified_count = int(pairs_metadata.get("counts", {}).get("pairs_qualified", 0)) if pairs_metadata else 0
    tickers = [HEATMAP_MARKET_DEFAULT_TICKER] + [
        ticker for ticker in universe["ticker"].tolist() if ticker != HEATMAP_MARKET_DEFAULT_TICKER
    ]
    price_refresh_token = (
        metadata.get("created_at_utc") or str(paths["raw_prices_csv"].stat().st_mtime_ns)
    )

    metric_a, metric_b, metric_c, metric_d = st.columns(4)
    metric_a.metric("Universe Size", universe_count)
    metric_b.metric("Window", f"{metadata['start_date']} to {metadata['end_date']}")
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
            options=config.rolling_windows,
            value=default_window,
            key="avg_corr_window",
        )
        avg_corr = rolling_average_correlation(returns, window)
        st.plotly_chart(
            _build_line_chart(
                avg_corr,
                title=f"NASDAQ-100 Top-50 Universe {window}-Day Average Pairwise Correlation",
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
                options=config.rolling_windows,
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
        st.subheader("Resolved Top-50 Universe")
        st.dataframe(universe, use_container_width=True, hide_index=True)
        st.subheader("Source Lineage")
        lineage = {
            "official_source": metadata["universe"]["official_source"],
            "ranking": metadata["universe"]["ranking"],
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


def _resolve_theme_tokens(visuals: dict) -> dict[str, str]:
    def _text(name: str) -> str:
        value = visuals.get(name)
        if value is None or str(value).strip() == "":
            return str(TERMINAL_VISUAL_DEFAULTS[name])
        return str(value).strip()

    return {
        "background_start": _text("background_start"),
        "background_end": _text("background_end"),
        "panel_border": _text("panel_border"),
        "accent_cyan": _text("accent_cyan"),
        "accent_amber": _text("accent_amber"),
        "success_color": _text("success_color"),
        "danger_color": _text("danger_color"),
        "panel_bg_rgba": _text("panel_bg_rgba"),
        "hover_glow_rgba": _text("hover_glow_rgba"),
        "hero_font": _text("hero_font"),
        "ui_font": _text("ui_font"),
        "mono_font": _text("mono_font"),
        "text_primary": _text("text_primary"),
        "text_muted": _text("text_muted"),
        "heatmap_min_color": _text("heatmap_min_color"),
        "heatmap_mid_color": _text("heatmap_mid_color"),
        "heatmap_max_color": _text("heatmap_max_color"),
    }


def _resolve_visual_float(visuals: dict, key: str, minimum: float, maximum: float) -> float:
    fallback = float(TERMINAL_VISUAL_DEFAULTS[key])
    try:
        candidate = float(visuals.get(key, fallback))
    except (TypeError, ValueError):
        candidate = fallback
    return min(max(candidate, minimum), maximum)


def _plotly_theme(visuals: dict) -> dict[str, str]:
    tokens = _resolve_theme_tokens(visuals)
    return {
        "ui_font": tokens["ui_font"],
        "mono_font": tokens["mono_font"],
        "text_primary": tokens["text_primary"],
        "text_muted": tokens["text_muted"],
        "accent_cyan": tokens["accent_cyan"],
        "accent_amber": tokens["accent_amber"],
        "success_color": tokens["success_color"],
        "danger_color": tokens["danger_color"],
        "plot_bg": "rgba(7,20,35,0.56)",
        "x_grid": "rgba(105,142,183,0.20)",
        "y_grid_soft": "rgba(105,142,183,0.22)",
        "y_grid_strong": "rgba(115,155,198,0.34)",
        "axis_zero": "rgba(193,211,236,0.50)",
        "bar_border": "rgba(193,211,236,0.32)",
        "annotation_bg": "rgba(4,10,20,0.84)",
        "annotation_border": "rgba(105,142,183,0.36)",
        "line_fill": "rgba(53,212,255,0.12)",
        "amber_fill": "rgba(123,169,255,0.20)",
        "success_fill": "rgba(34,197,94,0.32)",
        "danger_fill": "rgba(251,113,133,0.30)",
    }


def _build_heatmap(correlation: pd.DataFrame, visuals: dict) -> go.Figure:
    theme = _plotly_theme(visuals)
    tokens = _resolve_theme_tokens(visuals)
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
    theme = _plotly_theme(visuals)
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
    theme = _plotly_theme(visuals)
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

    metric_left, metric_mid, metric_right = st.columns(3)
    metric_left.metric("Qualified Pairs", pairs_metadata["counts"]["pairs_qualified"])
    metric_mid.metric(
        "Analysis Window",
        f"{analysis_window.get('start_date', 'n/a')} to {analysis_window.get('end_date', 'n/a')}",
    )
    metric_right.metric("Test Lookback", str(pairs_metadata.get("history_period", "n/a")).upper())

    summary_col, definition_col = st.columns([1.5, 1])
    with summary_col:
        st.markdown(
            _status_card(
                "What Passed",
                [
                    f"Engle-Granger p-value < {thresholds.get('cointegration_p_threshold', 'n/a')}",
                    f"ADF statistic < {thresholds.get('adf_stat_threshold', 'n/a')}",
                    f"Effective overlap floor: {thresholds.get('minimum_rows_effective', 'n/a')} trading days",
                ],
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
    theme = _plotly_theme(visuals)
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
    theme = _plotly_theme(visuals)
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
    theme = _plotly_theme(visuals)
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


def _read_optional_csv(
    path: Path | None,
    parse_dates: list[str] | None = None,
    index_col: int | str | None = None,
) -> pd.DataFrame:
    if path is None or not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=parse_dates, index_col=index_col)


def _read_optional_json(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _inject_styles(visuals: dict) -> None:
    tokens = _resolve_theme_tokens(visuals)
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=JetBrains+Mono:wght@400;500;700&family=Sora:wght@400;500;600;700&display=swap');

        :root {{
            --bg-start: {tokens["background_start"]};
            --bg-end: {tokens["background_end"]};
            --panel-bg: {tokens["panel_bg_rgba"]};
            --panel-border: {tokens["panel_border"]};
            --accent-cyan: {tokens["accent_cyan"]};
            --accent-amber: {tokens["accent_amber"]};
            --success: {tokens["success_color"]};
            --danger: {tokens["danger_color"]};
            --text-primary: {tokens["text_primary"]};
            --text-muted: {tokens["text_muted"]};
            --hover-glow: {tokens["hover_glow_rgba"]};
            --hero-font: '{tokens["hero_font"]}', sans-serif;
            --ui-font: '{tokens["ui_font"]}', sans-serif;
            --mono-font: '{tokens["mono_font"]}', monospace;
            --ease-term: 140ms cubic-bezier(0.18, 0.86, 0.22, 1);
            --lift-up: translateY(-3px) scale(1.018);
            --lift-down: translateY(1px) scale(0.985);
            --focus-ring: 0 0 0 2px rgba(53,212,255,0.52);
        }}

        html, body, [data-testid="stAppViewContainer"] {{
            background: linear-gradient(150deg, var(--bg-start) 0%, var(--bg-end) 56%, #030B15 100%);
        }}

        .stApp {{
            color: var(--text-primary);
            font-family: var(--ui-font);
            background:
                repeating-linear-gradient(
                    90deg,
                    rgba(157,176,201,0.08) 0,
                    rgba(157,176,201,0.08) 1px,
                    transparent 1px,
                    transparent 22px
                ),
                repeating-linear-gradient(
                    0deg,
                    rgba(157,176,201,0.06) 0,
                    rgba(157,176,201,0.06) 1px,
                    transparent 1px,
                    transparent 22px
                ),
                radial-gradient(62rem 62rem at 14% 6%, rgba(123, 169, 255, 0.22), transparent 44%),
                radial-gradient(45rem 45rem at 92% 2%, rgba(53, 212, 255, 0.16), transparent 42%);
        }}
        .stApp:hover {{
            background:
                repeating-linear-gradient(
                    90deg,
                    rgba(157,176,201,0.13) 0,
                    rgba(157,176,201,0.13) 1px,
                    transparent 1px,
                    transparent 20px
                ),
                repeating-linear-gradient(
                    0deg,
                    rgba(157,176,201,0.09) 0,
                    rgba(157,176,201,0.09) 1px,
                    transparent 1px,
                    transparent 20px
                ),
                radial-gradient(62rem 62rem at 14% 6%, rgba(123, 169, 255, 0.30), transparent 44%),
                radial-gradient(45rem 45rem at 92% 2%, rgba(53, 212, 255, 0.24), transparent 42%);
        }}

        .main .block-container {{
            padding-top: 1.35rem;
            padding-bottom: 3rem;
        }}

        h1, h2, h3, h4 {{
            color: var(--text-primary) !important;
        }}
        h1 {{
            font-family: var(--hero-font);
            font-size: clamp(2.6rem, 3.2vw, 4rem) !important;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            text-shadow: 0 0 18px rgba(53, 212, 255, 0.10);
            margin-bottom: 0.25rem;
        }}
        h2, h3, h4 {{
            font-family: var(--ui-font);
            letter-spacing: 0.01em;
            font-weight: 600;
        }}

        .hero-shell {{
            padding: 0.2rem 0 0.9rem 0;
            border-bottom: 1px solid rgba(105,142,183,0.28);
            margin-bottom: 0.25rem;
        }}
        .hero-subtitle {{
            color: var(--text-muted);
            font-size: 1rem;
            line-height: 1.55;
            letter-spacing: 0.02em;
            max-width: 78ch;
        }}

        .section-gap {{
            width: 100%;
        }}
        .section-gap-tabs {{
            height: 1rem;
        }}
        .section-gap-block {{
            height: 1.15rem;
        }}

        .status-card,
        .definition-card,
        [data-testid="stMetric"],
        [data-testid="stDataFrame"],
        .stTabs [data-baseweb="tab-list"] {{
            border: 1px solid var(--panel-border) !important;
            border-radius: 16px;
            background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.01)), var(--panel-bg);
            box-shadow: 0 12px 34px rgba(3, 7, 14, 0.42), inset 0 1px 0 rgba(255,255,255,0.05);
            transition: transform var(--ease-term), box-shadow var(--ease-term), border-color var(--ease-term);
        }}
        .status-card:hover,
        .definition-card:hover,
        [data-testid="stMetric"]:hover {{
            transform: var(--lift-up);
            border-color: rgba(53,212,255,0.42) !important;
            box-shadow: 0 16px 38px rgba(2, 8, 18, 0.58), 0 0 0 1px rgba(53,212,255,0.28), 0 0 26px rgba(53,212,255,0.25);
        }}

        .status-card {{
            padding: 1rem 1.1rem;
            min-height: 10rem;
        }}
        .status-card h4,
        .definition-card h4 {{
            margin: 0 0 0.45rem 0;
            font-size: 1.05rem;
            color: var(--accent-cyan) !important;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            font-family: var(--ui-font);
        }}
        .status-card ul,
        .definition-card ul {{
            margin: 0;
            padding-left: 1rem;
            color: var(--text-primary);
            line-height: 1.45;
        }}
        .definition-card {{
            padding: 1rem 1.1rem;
            min-height: 10rem;
        }}

        .stTabs [data-baseweb="tab-list"] {{
            gap: 0.65rem;
            padding: 0.45rem;
        }}
        .stTabs [data-baseweb="tab"] {{
            color: var(--text-muted) !important;
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(105,142,183,0.24);
            border-radius: 999px;
            padding: 0.48rem 1rem;
            font-family: var(--ui-font);
            font-weight: 600;
            transition: color 140ms ease, border-color 140ms ease, background 140ms ease;
        }}
        .stTabs [data-baseweb="tab"]:hover {{
            color: var(--text-primary) !important;
            border-color: var(--accent-cyan);
            transform: var(--lift-up);
            box-shadow: 0 0 0 1px rgba(53,212,255,0.32), 0 10px 24px rgba(0,0,0,0.40), 0 0 18px rgba(53,212,255,0.24);
        }}
        .stTabs [aria-selected="true"] {{
            color: #031221 !important;
            border-color: var(--accent-cyan);
            background: linear-gradient(120deg, rgba(53,212,255,0.95), rgba(53,212,255,0.74));
            box-shadow: 0 10px 20px rgba(53,212,255,0.28), 0 0 18px rgba(53,212,255,0.22);
        }}
        .stTabs [data-baseweb="tab-highlight"] {{
            background: transparent !important;
            height: 0 !important;
        }}

        [data-testid="stMetric"] {{
            padding: 0.92rem 1rem;
            backdrop-filter: blur(10px);
        }}
        [data-testid="stMetricValue"],
        [data-testid="stMetricLabel"] {{
            color: var(--text-primary) !important;
            font-family: var(--mono-font) !important;
        }}

        [data-testid="stWidgetLabel"] p,
        [data-testid="stWidgetLabel"] span,
        .stSelectbox label,
        .stSlider label,
        .stSubheader {{
            color: var(--text-primary) !important;
        }}
        .stCaption,
        [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] p {{
            color: var(--text-muted) !important;
        }}

        [data-testid="stRadio"] label,
        [data-testid="stRadio"] label p,
        [data-testid="stRadio"] label span,
        [data-testid="stRadio"] div[role="radiogroup"] label,
        [data-testid="stRadio"] div[role="radiogroup"] label p,
        [data-testid="stRadio"] div[role="radiogroup"] label span {{
            color: var(--text-primary) !important;
            opacity: 1 !important;
            transition: color var(--ease-term);
        }}
        [data-testid="stRadio"] label:hover span,
        [data-testid="stRadio"] label:hover p {{
            color: var(--accent-cyan) !important;
        }}

        div[data-baseweb="select"] > div,
        div[data-baseweb="base-input"] > div,
        div[data-baseweb="input"] > div {{
            background: rgba(5, 12, 24, 0.88);
            border: 1px solid rgba(105,142,183,0.30);
            border-radius: 12px;
            transition: border-color 140ms ease, box-shadow 140ms ease;
        }}
        div[data-baseweb="select"] > div:hover,
        div[data-baseweb="base-input"] > div:hover,
        div[data-baseweb="input"] > div:hover {{
            transform: var(--lift-up);
            border-color: var(--accent-cyan);
            box-shadow: 0 0 0 1px rgba(53,212,255,0.30), 0 10px 28px rgba(0,0,0,0.58), 0 0 18px rgba(53,212,255,0.20);
        }}
        div[data-baseweb="select"] * {{
            color: var(--text-primary) !important;
        }}
        div[data-baseweb="select"] svg {{
            fill: var(--text-primary) !important;
        }}
        div[data-baseweb="slider"] * {{
            color: var(--text-primary) !important;
        }}

        .stButton > button,
        [data-testid="stDownloadButton"] > button,
        [data-testid="baseButton-secondary"],
        [data-testid="baseButton-primary"],
        button[kind="secondary"],
        button[kind="primary"],
        .stForm button {{
            border-radius: 12px !important;
            border: 1px solid rgba(105,142,183,0.36) !important;
            background: linear-gradient(120deg, rgba(123,169,255,0.24), rgba(53,212,255,0.12)), rgba(7,16,30,0.95) !important;
            color: var(--text-primary) !important;
            font-family: var(--ui-font) !important;
            font-weight: 600 !important;
            letter-spacing: 0.01em;
            transition: box-shadow 140ms ease, border-color 140ms ease, filter 140ms ease;
            cursor: pointer !important;
        }}

        .stButton > button:hover,
        [data-testid="stDownloadButton"] > button:hover,
        [data-testid="baseButton-secondary"]:hover,
        [data-testid="baseButton-primary"]:hover,
        button[kind="secondary"]:hover,
        button[kind="primary"]:hover,
        .stForm button:hover {{
            transform: var(--lift-up);
            border-color: var(--accent-cyan) !important;
            box-shadow: 0 0 0 1px rgba(53,212,255,0.40), 0 12px 26px rgba(0,0,0,0.52), 0 0 24px var(--hover-glow);
            filter: brightness(1.11);
        }}
        .stButton > button:active,
        [data-testid="stDownloadButton"] > button:active,
        [data-testid="baseButton-secondary"]:active,
        [data-testid="baseButton-primary"]:active,
        button[kind="secondary"]:active,
        button[kind="primary"]:active,
        .stForm button:active {{
            transform: var(--lift-down);
            box-shadow: 0 5px 12px rgba(0,0,0,0.48), 0 0 14px rgba(53,212,255,0.26);
        }}
        .stButton > button:focus-visible,
        [data-testid="stDownloadButton"] > button:focus-visible,
        .stForm button:focus-visible,
        div[data-baseweb="select"] > div:focus-within,
        div[data-baseweb="base-input"] > div:focus-within,
        div[data-baseweb="input"] > div:focus-within {{
            box-shadow: var(--focus-ring) !important;
            border-color: var(--accent-cyan) !important;
        }}

        .stDataFrame {{
            overflow: hidden;
        }}
        div[data-testid="stDataFrame"] [role="columnheader"],
        div[data-testid="stDataFrame"] [role="gridcell"] {{
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            color: var(--text-primary) !important;
            font-family: var(--mono-font) !important;
            font-size: 0.88rem !important;
        }}
        div[data-testid="stDataFrame"] [role="columnheader"] {{
            color: var(--accent-cyan) !important;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}

        [data-testid="stSpinner"] {{
            color: var(--text-primary) !important;
            text-shadow: 0 0 10px rgba(53,212,255,0.24);
        }}
        [data-testid="stSpinner"] > div {{
            position: relative;
            width: 66px !important;
            height: 66px !important;
            border-radius: 50% !important;
            border: 2px solid rgba(53,212,255,0.24) !important;
            border-top-color: var(--accent-cyan) !important;
            border-right-color: rgba(53,212,255,0.50) !important;
            animation: sci-spin 0.72s linear infinite !important;
            box-shadow: 0 0 24px rgba(53,212,255,0.22), inset 0 0 16px rgba(53,212,255,0.18);
            background: radial-gradient(circle at center, rgba(53,212,255,0.10), transparent 64%);
        }}
        [data-testid="stSpinner"] > div::before {{
            content: "";
            position: absolute;
            inset: 11px;
            border-radius: 50%;
            border: 2px solid transparent;
            border-left-color: rgba(123,169,255,0.70);
            border-bottom-color: rgba(123,169,255,0.42);
            animation: sci-spin-rev 0.56s linear infinite;
        }}
        @keyframes sci-spin {{
            from {{ transform: rotate(0deg); }}
            to {{ transform: rotate(360deg); }}
        }}
        @keyframes sci-spin-rev {{
            from {{ transform: rotate(360deg); }}
            to {{ transform: rotate(0deg); }}
        }}
        @media (prefers-reduced-motion: reduce) {{
            .status-card:hover,
            .definition-card:hover,
            [data-testid="stMetric"]:hover,
            .stTabs [data-baseweb="tab"]:hover,
            .stForm button:hover,
            div[data-baseweb="select"] > div:hover,
            div[data-baseweb="base-input"] > div:hover,
            div[data-baseweb="input"] > div:hover {{
                transform: none;
            }}
            [data-testid="stSpinner"] > div,
            [data-testid="stSpinner"] > div::before {{
                animation-duration: 2.2s !important;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
