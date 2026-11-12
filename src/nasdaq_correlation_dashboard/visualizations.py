from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .universe import sector_colors


def build_heatmap(
    corr: pd.DataFrame,
    visuals: dict[str, str],
    ticker_order: list[str] | None = None,
    show_text: bool | None = None,
) -> go.Figure:
    """Build an interactive Plotly correlation heatmap.

    Args:
        corr: Correlation matrix DataFrame.
        visuals: Visual config dict with heatmap color keys.
        ticker_order: Optional reordering of tickers.
        show_text: Whether to show text annotations. If None, auto-decides
                   based on matrix size (shown when <= 15 tickers).
    """
    if ticker_order is not None:
        valid = [t for t in ticker_order if t in corr.columns]
        corr = corr.loc[valid, valid]

    n = len(corr)
    if show_text is None:
        show_text = n <= 15

    colorscale = [
        [0.0, visuals["heatmap_min_color"]],
        [0.5, visuals["heatmap_mid_color"]],
        [1.0, visuals["heatmap_max_color"]],
    ]

    text = corr.round(3).values if show_text else None
    texttemplate = "%{text}" if show_text else None

    figure = go.Figure(
        data=go.Heatmap(
            z=corr.values,
            x=list(corr.columns),
            y=list(corr.index),
            zmin=-1,
            zmax=1,
            colorscale=colorscale,
            colorbar={"title": "Corr", "titlefont": {"color": "#F6F2ED"}},
            text=text,
            texttemplate=texttemplate,
            textfont={"size": 8} if show_text else None,
            hovertemplate="X: %{x}<br>Y: %{y}<br>Corr: %{z:.4f}<extra></extra>",
        )
    )

    tick_font_size = max(6, min(12, 180 // n))
    figure.update_layout(
        margin={"l": 10, "r": 10, "t": 30, "b": 10},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={
            "family": "Georgia, Times New Roman, serif",
            "size": tick_font_size,
            "color": "#F6F2ED",
        },
        height=max(500, n * 14),
    )
    figure.update_xaxes(side="top", tickangle=45)
    return figure


def build_scree_plot(
    eigenvalue_data: dict[str, Any],
    bar_color: str = "#1BAA6E",
    line_color: str = "#E6D5C7",
    mp_color: str = "#4D0000",
) -> go.Figure:
    """Build eigenvalue scree plot with Marchenko-Pastur threshold line."""
    eigenvalues = eigenvalue_data["eigenvalues"]
    n = len(eigenvalues)
    mp_upper = eigenvalue_data.get("mp_upper_bound", 0)

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=list(range(1, n + 1)),
            y=eigenvalues,
            marker_color=bar_color,
            opacity=0.8,
            name="Eigenvalues",
            hovertemplate="Component %{x}<br>Eigenvalue: %{y:.4f}<extra></extra>",
        )
    )

    if mp_upper > 0:
        fig.add_hline(
            y=mp_upper,
            line_dash="dash",
            line_color=mp_color,
            annotation_text=f"MP upper: {mp_upper:.2f}",
            annotation_font_color=mp_color,
        )

    # Cumulative variance on secondary axis
    cum_var = eigenvalue_data.get("cumulative_variance", [])
    if cum_var:
        fig.add_trace(
            go.Scatter(
                x=list(range(1, len(cum_var) + 1)),
                y=[v * max(eigenvalues) for v in cum_var],
                mode="lines+markers",
                line={"color": line_color, "width": 2},
                marker={"size": 5},
                name="Cumulative Var (scaled)",
                hovertemplate="Component %{x}<br>Cumulative: %{customdata:.1%}<extra></extra>",
                customdata=cum_var,
            )
        )

    fig.update_layout(
        xaxis_title="Component",
        yaxis_title="Eigenvalue",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Georgia, Times New Roman, serif", "color": "#F6F2ED"},
        legend={"font": {"color": "#F6F2ED"}},
        margin={"l": 50, "r": 20, "t": 30, "b": 50},
        height=400,
        yaxis={"gridcolor": "rgba(255,255,255,0.05)"},
        xaxis={"gridcolor": "rgba(255,255,255,0.05)"},
    )
    return fig


def build_biplot(
    loadings: pd.DataFrame,
    sectors: dict[str, str],
) -> go.Figure:
    """Build PC1 vs PC2 biplot with tickers colored by sector."""
    if "PC1" not in loadings.columns or "PC2" not in loadings.columns:
        return go.Figure()

    colors = sector_colors()
    fig = go.Figure()

    sector_groups: dict[str, list[str]] = {}
    for ticker in loadings.index:
        sector = sectors.get(ticker, "Other")
        sector_groups.setdefault(sector, []).append(ticker)

    for sector, tickers in sorted(sector_groups.items()):
        subset = loadings.loc[tickers]
        fig.add_trace(
            go.Scatter(
                x=subset["PC1"],
                y=subset["PC2"],
                mode="markers+text",
                text=tickers,
                textposition="top center",
                textfont={"size": 8, "color": "#F6F2ED"},
                marker={
                    "color": colors.get(sector, "#c7c7c7"),
                    "size": 8,
                    "line": {"width": 0.5, "color": "#F6F2ED"},
                },
                name=sector,
                hovertemplate="%{text}<br>PC1: %{x:.4f}<br>PC2: %{y:.4f}<extra></extra>",
            )
        )

    fig.update_layout(
        xaxis_title="PC1 Loading",
        yaxis_title="PC2 Loading",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Georgia, Times New Roman, serif", "color": "#F6F2ED"},
        legend={"font": {"color": "#F6F2ED", "size": 10}},
        margin={"l": 50, "r": 20, "t": 30, "b": 50},
        height=500,
        xaxis={"gridcolor": "rgba(255,255,255,0.05)", "zeroline": True, "zerolinecolor": "rgba(255,255,255,0.15)"},
        yaxis={"gridcolor": "rgba(255,255,255,0.05)", "zeroline": True, "zerolinecolor": "rgba(255,255,255,0.15)"},
    )
    return fig


def build_rolling_chart(
    rolling_series: dict[str, pd.Series],
    pair_name: str,
    windows: list[int],
    returns: pd.DataFrame,
    regime_labels: pd.Series | None = None,
) -> go.Figure:
    """Build rolling correlation line chart for a specific pair.

    Shows rolling correlations at each configured window length,
    with optional regime-colored background bands.
    """
    fig = go.Figure()

    line_colors = ["#1BAA6E", "#E6D5C7", "#ff7f0e", "#9467bd"]
    tickers = pair_name.split(" vs ")

    if len(tickers) == 2 and tickers[0] in returns.columns and tickers[1] in returns.columns:
        clean = returns[[tickers[0], tickers[1]]].dropna()
        for i, w in enumerate(windows):
            rolling = clean[tickers[0]].rolling(w).corr(clean[tickers[1]]).dropna()
            color = line_colors[i % len(line_colors)]
            fig.add_trace(
                go.Scatter(
                    x=rolling.index,
                    y=rolling.values,
                    mode="lines",
                    name=f"{w}d",
                    line={"color": color, "width": 1.5},
                    hovertemplate="%{x}<br>Corr: %{y:.4f}<extra></extra>",
                )
            )

    # Add regime bands if available
    if regime_labels is not None and len(regime_labels) > 0:
        regime_colors = {
            "low_vol": "rgba(27,170,110,0.08)",
            "normal": "rgba(230,213,199,0.06)",
            "high_vol": "rgba(77,0,0,0.12)",
        }
        prev_regime = None
        start_date = None
        for date, regime in regime_labels.items():
            if regime != prev_regime:
                if prev_regime is not None and start_date is not None:
                    fig.add_vrect(
                        x0=start_date, x1=date,
                        fillcolor=regime_colors.get(prev_regime, "rgba(128,128,128,0.05)"),
                        line_width=0,
                        layer="below",
                    )
                start_date = date
                prev_regime = regime
        # Close last regime
        if prev_regime is not None and start_date is not None:
            fig.add_vrect(
                x0=start_date, x1=regime_labels.index[-1],
                fillcolor=regime_colors.get(prev_regime, "rgba(128,128,128,0.05)"),
                line_width=0,
                layer="below",
            )

    fig.update_layout(
        title={"text": pair_name, "font": {"size": 14, "color": "#F6F2ED"}},
        xaxis_title="Date",
        yaxis_title="Correlation",
        yaxis={"range": [-1, 1], "gridcolor": "rgba(255,255,255,0.05)"},
        xaxis={"gridcolor": "rgba(255,255,255,0.05)"},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Georgia, Times New Roman, serif", "color": "#F6F2ED"},
        legend={"font": {"color": "#F6F2ED"}},
        margin={"l": 50, "r": 20, "t": 40, "b": 50},
        height=400,
    )
    return fig


def build_absorption_ratio_chart(ar_series: pd.Series) -> go.Figure:
    """Build absorption ratio time series chart."""
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=ar_series.index,
            y=ar_series.values,
            mode="lines",
            line={"color": "#1BAA6E", "width": 2},
            fill="tozeroy",
            fillcolor="rgba(27,170,110,0.1)",
            name="Absorption Ratio",
            hovertemplate="%{x}<br>AR: %{y:.4f}<extra></extra>",
        )
    )

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Absorption Ratio",
        yaxis={"range": [0, 1], "gridcolor": "rgba(255,255,255,0.05)"},
        xaxis={"gridcolor": "rgba(255,255,255,0.05)"},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Georgia, Times New Roman, serif", "color": "#F6F2ED"},
        margin={"l": 50, "r": 20, "t": 30, "b": 50},
        height=350,
    )
    return fig


def build_stability_chart(stability_series: pd.Series) -> go.Figure:
    """Build correlation stability (Frobenius norm change) chart."""
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=stability_series.index,
            y=stability_series.values,
            mode="lines",
            line={"color": "#E6D5C7", "width": 1.5},
            fill="tozeroy",
            fillcolor="rgba(230,213,199,0.08)",
            name="Correlation Change Intensity",
            hovertemplate="%{x}<br>Frobenius Δ: %{y:.4f}<extra></extra>",
        )
    )

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Frobenius Norm Change",
        yaxis={"gridcolor": "rgba(255,255,255,0.05)"},
        xaxis={"gridcolor": "rgba(255,255,255,0.05)"},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Georgia, Times New Roman, serif", "color": "#F6F2ED"},
        margin={"l": 50, "r": 20, "t": 30, "b": 50},
        height=350,
    )
    return fig


def build_regime_timeline(regime_labels: pd.Series) -> go.Figure:
    """Build a regime timeline visualization with colored bands."""
    regime_colors = {
        "low_vol": "#1BAA6E",
        "normal": "#E6D5C7",
        "high_vol": "#4D0000",
    }

    fig = go.Figure()

    # Create colored segments for each regime
    prev_regime = None
    start_date = None
    segments: list[dict] = []

    for date, regime in regime_labels.items():
        if regime != prev_regime:
            if prev_regime is not None and start_date is not None:
                segments.append({"start": start_date, "end": date, "regime": prev_regime})
            start_date = date
            prev_regime = regime

    if prev_regime is not None and start_date is not None:
        segments.append({"start": start_date, "end": regime_labels.index[-1], "regime": prev_regime})

    for seg in segments:
        color = regime_colors.get(seg["regime"], "#7f7f7f")
        fig.add_trace(
            go.Scatter(
                x=[seg["start"], seg["end"], seg["end"], seg["start"], seg["start"]],
                y=[0, 0, 1, 1, 0],
                fill="toself",
                fillcolor=color,
                line={"width": 0},
                mode="lines",
                name=seg["regime"],
                showlegend=False,
                hovertemplate=f'{seg["regime"]}<br>%{{x}}<extra></extra>',
                opacity=0.7,
            )
        )

    # Add legend entries
    for regime_name, color in regime_colors.items():
        fig.add_trace(
            go.Scatter(
                x=[None], y=[None],
                mode="markers",
                marker={"size": 12, "color": color},
                name=regime_name.replace("_", " ").title(),
            )
        )

    fig.update_layout(
        xaxis_title="Date",
        yaxis={"visible": False},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Georgia, Times New Roman, serif", "color": "#F6F2ED"},
        legend={"font": {"color": "#F6F2ED"}},
        margin={"l": 10, "r": 10, "t": 10, "b": 40},
        height=120,
        xaxis={"gridcolor": "rgba(255,255,255,0.05)"},
    )
    return fig
