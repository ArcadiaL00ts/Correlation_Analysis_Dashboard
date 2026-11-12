from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class AnalyticsResults:
    """Container for all advanced analytics outputs."""
    eigenvalues: dict[str, Any] = field(default_factory=dict)
    pca_loadings: pd.DataFrame | None = None
    rolling_correlations: dict[str, pd.Series] = field(default_factory=dict)
    regimes: dict[str, Any] = field(default_factory=dict)
    stability: pd.Series | None = None
    absorption_ratio: pd.Series | None = None


def eigenvalue_decomposition(corr: pd.DataFrame) -> dict[str, Any]:
    """Decompose the correlation matrix into eigenvalues.

    Returns eigenvalues, explained variance ratios, cumulative variance,
    and the Marchenko-Pastur upper bound for random matrix comparison.
    """
    eigenvalues = np.linalg.eigvalsh(corr.values)
    eigenvalues = np.sort(eigenvalues)[::-1]  # descending

    total = eigenvalues.sum()
    explained_ratio = eigenvalues / total
    cumulative = np.cumsum(explained_ratio)

    # Marchenko-Pastur upper bound: lambda_+ = (1 + sqrt(N/T))^2
    # For a correlation matrix of N assets over T observations
    n = corr.shape[0]
    # Use a reasonable T estimate (252 trading days * 2 years)
    t_estimate = 504
    q = n / t_estimate
    mp_upper = (1 + np.sqrt(q)) ** 2
    mp_lower = (1 - np.sqrt(q)) ** 2

    return {
        "eigenvalues": eigenvalues.tolist(),
        "explained_variance_ratio": explained_ratio.tolist(),
        "cumulative_variance": cumulative.tolist(),
        "mp_upper_bound": float(mp_upper),
        "mp_lower_bound": float(mp_lower),
        "n_assets": n,
        "n_significant": int(np.sum(eigenvalues > mp_upper)),
    }


def pca_factor_loadings(
    returns: pd.DataFrame, n_components: int = 5
) -> dict[str, Any]:
    """Compute PCA factor loadings on the returns matrix.

    Returns loadings DataFrame (tickers x factors), explained variance
    per component, and cumulative explained variance.
    """
    from sklearn.decomposition import PCA

    clean = returns.dropna()
    n_components = min(n_components, len(clean.columns), len(clean))

    pca = PCA(n_components=n_components)
    pca.fit(clean.values)

    loadings = pd.DataFrame(
        pca.components_.T,
        index=clean.columns,
        columns=[f"PC{i + 1}" for i in range(n_components)],
    )

    return {
        "loadings": loadings,
        "explained_variance": pca.explained_variance_ratio_.tolist(),
        "cumulative_variance": np.cumsum(pca.explained_variance_ratio_).tolist(),
        "n_components": n_components,
    }


def rolling_pairwise(
    returns: pd.DataFrame,
    window: int,
    top_n: int = 20,
    reference_pairs: list[tuple[str, str]] | None = None,
) -> dict[str, pd.Series]:
    """Compute rolling pairwise correlations for the top correlated pairs.

    If reference_pairs is provided, computes rolling correlations for those
    specific pairs. Otherwise, identifies the top_n most correlated and
    bottom 5 most anti-correlated pairs from the full-sample correlation.

    Returns a dict mapping pair names (e.g., "AAPL vs MSFT") to rolling
    correlation Series.
    """
    clean = returns.dropna()

    if reference_pairs is None:
        full_corr = clean.corr()
        pairs_with_values: list[tuple[str, str, float]] = []
        seen: set[tuple[str, str]] = set()

        for col_a in full_corr.columns:
            for col_b in full_corr.columns:
                if col_a == col_b:
                    continue
                key = tuple(sorted((col_a, col_b)))
                if key in seen:
                    continue
                seen.add(key)
                pairs_with_values.append((key[0], key[1], float(full_corr.loc[col_a, col_b])))

        # Top N positive + bottom 5 negative
        sorted_pairs = sorted(pairs_with_values, key=lambda x: x[2], reverse=True)
        selected = sorted_pairs[:top_n]
        negative = [p for p in sorted_pairs if p[2] < 0]
        bottom = negative[-5:] if len(negative) >= 5 else negative
        selected.extend(bottom)

        reference_pairs = [(p[0], p[1]) for p in selected]

    result: dict[str, pd.Series] = {}
    for ticker_a, ticker_b in reference_pairs:
        if ticker_a in clean.columns and ticker_b in clean.columns:
            pair_name = f"{ticker_a} vs {ticker_b}"
            rolling = clean[ticker_a].rolling(window).corr(clean[ticker_b])
            result[pair_name] = rolling.dropna()

    return result


def detect_regimes(
    returns: pd.DataFrame,
    n_regimes: int = 3,
    vol_window: int = 21,
) -> dict[str, Any]:
    """Detect market regimes using k-means on rolling first-PC volatility.

    Clusters periods into n_regimes groups (e.g., low-vol, normal, high-vol)
    based on the rolling realized volatility of the first principal component.

    Returns regime labels, per-regime statistics, and per-regime average
    correlation matrices.
    """
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA

    clean = returns.dropna()
    if len(clean) < vol_window + 10:
        return {"warning": "Insufficient data for regime detection."}

    # Extract first PC scores
    pca = PCA(n_components=1)
    pc1_scores = pca.fit_transform(clean.values).flatten()
    pc1_series = pd.Series(pc1_scores, index=clean.index)

    # Rolling realized volatility of PC1
    rolling_vol = pc1_series.rolling(vol_window).std().dropna()

    if len(rolling_vol) < n_regimes * 2:
        return {"warning": "Insufficient data for regime detection after rolling window."}

    # K-means clustering
    kmeans = KMeans(n_clusters=n_regimes, random_state=42, n_init=10)
    labels = kmeans.fit_predict(rolling_vol.values.reshape(-1, 1))

    # Sort regimes by centroid (low vol = 0, high vol = n-1)
    centroids = kmeans.cluster_centers_.flatten()
    sort_order = np.argsort(centroids)
    label_map = {old: new for new, old in enumerate(sort_order)}
    sorted_labels = np.array([label_map[l] for l in labels])

    regime_names = {0: "low_vol", 1: "normal", 2: "high_vol"}
    if n_regimes == 2:
        regime_names = {0: "low_vol", 1: "high_vol"}

    regime_series = pd.Series(
        [regime_names.get(l, f"regime_{l}") for l in sorted_labels],
        index=rolling_vol.index,
        name="regime",
    )

    # Per-regime statistics
    per_regime: dict[str, dict[str, Any]] = {}
    aligned_returns = clean.loc[rolling_vol.index]

    for regime_id, regime_name in regime_names.items():
        mask = sorted_labels == regime_id
        regime_dates = rolling_vol.index[mask]
        regime_returns = aligned_returns.loc[regime_dates]

        if len(regime_returns) > 1:
            regime_corr = regime_returns.corr().round(6)
            avg_corr = regime_corr.values[np.triu_indices_from(regime_corr.values, k=1)].mean()
            avg_vol = regime_returns.std().mean()
            per_regime[regime_name] = {
                "n_days": int(mask.sum()),
                "avg_correlation": float(avg_corr),
                "avg_volatility": float(avg_vol),
                "correlation_matrix": regime_corr,
                "centroid_vol": float(centroids[sort_order[regime_id]]),
            }

    return {
        "regime_labels": regime_series,
        "per_regime": per_regime,
        "n_regimes": n_regimes,
        "vol_window": vol_window,
    }


def correlation_stability(
    returns: pd.DataFrame, window: int = 63
) -> pd.Series:
    """Measure correlation stability via Frobenius norm of consecutive changes.

    Computes rolling correlation matrices and measures the Frobenius norm
    distance between consecutive matrices. High values indicate rapid
    changes in correlation structure.
    """
    clean = returns.dropna()
    dates = clean.index[window - 1:]

    prev_corr = None
    stability_values: list[float] = []
    stability_dates: list = []

    for i in range(len(dates)):
        window_data = clean.iloc[i:i + window]
        if len(window_data) < window:
            break
        current_corr = window_data.corr().values

        if prev_corr is not None:
            diff = current_corr - prev_corr
            frobenius = np.sqrt(np.sum(diff ** 2))
            stability_values.append(frobenius)
            stability_dates.append(dates[i])

        prev_corr = current_corr

    return pd.Series(stability_values, index=stability_dates, name="correlation_change_intensity")


def absorption_ratio(
    returns: pd.DataFrame,
    n_components: int = 5,
    window: int = 252,
) -> pd.Series:
    """Compute rolling absorption ratio — fraction of variance in top eigenvalues.

    High absorption ratio signals systemic risk and crowded positioning.
    Values near 1.0 indicate a single-factor market; lower values
    indicate more diversified risk.
    """
    clean = returns.dropna()
    if len(clean) < window + 10:
        return pd.Series(dtype=float, name="absorption_ratio")

    ar_values: list[float] = []
    ar_dates: list = []

    for i in range(window, len(clean) + 1):
        window_data = clean.iloc[i - window:i]
        corr = window_data.corr().values

        eigenvalues = np.linalg.eigvalsh(corr)
        eigenvalues = np.sort(eigenvalues)[::-1]

        n_comp = min(n_components, len(eigenvalues))
        total_var = eigenvalues.sum()
        if total_var > 0:
            ar = eigenvalues[:n_comp].sum() / total_var
        else:
            ar = 0.0

        ar_values.append(float(ar))
        ar_dates.append(clean.index[i - 1])

    return pd.Series(ar_values, index=ar_dates, name="absorption_ratio")


def run_full_analytics(
    returns: pd.DataFrame,
    correlation: pd.DataFrame,
    analytics_config: dict[str, Any],
) -> AnalyticsResults:
    """Run the full analytics suite based on config settings."""
    results = AnalyticsResults()

    # Eigenvalue decomposition
    if analytics_config.get("eigenvalue_decomposition", True):
        results.eigenvalues = eigenvalue_decomposition(correlation)

    # PCA factor loadings
    n_components = int(analytics_config.get("pca_components", 5))
    pca_result = pca_factor_loadings(returns, n_components)
    results.pca_loadings = pca_result["loadings"]
    if not results.eigenvalues:
        results.eigenvalues = {}
    results.eigenvalues["pca_explained_variance"] = pca_result["explained_variance"]
    results.eigenvalues["pca_cumulative_variance"] = pca_result["cumulative_variance"]

    # Rolling correlations (use the shortest configured window)
    windows = analytics_config.get("rolling_windows", [21, 63, 126, 252])
    top_n = int(analytics_config.get("top_rolling_pairs", 20))
    if windows:
        results.rolling_correlations = rolling_pairwise(
            returns, window=min(windows), top_n=top_n
        )

    # Regime detection
    if analytics_config.get("regime_detection", True):
        n_regimes = int(analytics_config.get("n_regimes", 3))
        results.regimes = detect_regimes(returns, n_regimes=n_regimes)

    # Correlation stability
    stability_window = int(analytics_config.get("correlation_stability_window", 63))
    results.stability = correlation_stability(returns, window=stability_window)

    # Absorption ratio
    ar_components = int(analytics_config.get("absorption_ratio_components", 5))
    results.absorption_ratio = absorption_ratio(returns, n_components=ar_components)

    return results
