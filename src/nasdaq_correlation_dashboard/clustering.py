from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.cluster.hierarchy import dendrogram, linkage
from scipy.spatial.distance import squareform


def hierarchical_order(corr: pd.DataFrame) -> list[str]:
    """Reorder tickers by hierarchical clustering on correlation distance.

    Uses Ward's method on distance = 1 - corr. Returns tickers in the
    order that groups similar stocks together.
    """
    distance = 1 - corr.values
    np.fill_diagonal(distance, 0)
    distance = (distance + distance.T) / 2  # ensure symmetry
    condensed = squareform(distance, checks=False)
    linkage_matrix = linkage(condensed, method="ward")
    dendro = dendrogram(linkage_matrix, no_plot=True)
    order = dendro["leaves"]
    return [corr.columns[i] for i in order]


def sector_order(tickers: list[str], sectors: dict[str, str]) -> list[str]:
    """Sort tickers by sector name, then alphabetically within each sector."""
    return sorted(tickers, key=lambda t: (sectors.get(t, "ZZZ_Other"), t))


def build_dendrogram(
    corr: pd.DataFrame,
    color: str = "#F6F2ED",
    bg_color: str = "rgba(0,0,0,0)",
) -> go.Figure:
    """Build a Plotly figure of the hierarchical clustering dendrogram."""
    distance = 1 - corr.values
    np.fill_diagonal(distance, 0)
    distance = (distance + distance.T) / 2
    condensed = squareform(distance, checks=False)
    linkage_matrix = linkage(condensed, method="ward")
    dendro = dendrogram(linkage_matrix, labels=list(corr.columns), no_plot=True)

    fig = go.Figure()

    icoord = dendro["icoord"]
    dcoord = dendro["dcoord"]
    for xs, ys in zip(icoord, dcoord):
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                line={"color": color, "width": 1.5},
                showlegend=False,
                hoverinfo="skip",
            )
        )

    # Add ticker labels
    tick_positions = list(range(5, 10 * len(dendro["ivl"]), 10))
    fig.update_xaxes(
        tickvals=tick_positions,
        ticktext=dendro["ivl"],
        tickangle=45,
        tickfont={"size": 9, "color": color},
    )

    fig.update_layout(
        margin={"l": 10, "r": 10, "t": 10, "b": 80},
        paper_bgcolor=bg_color,
        plot_bgcolor=bg_color,
        yaxis={
            "title": "Distance (1 - corr)",
            "titlefont": {"color": color, "size": 11},
            "tickfont": {"color": color, "size": 9},
            "gridcolor": "rgba(255,255,255,0.05)",
        },
        height=300,
    )

    return fig
