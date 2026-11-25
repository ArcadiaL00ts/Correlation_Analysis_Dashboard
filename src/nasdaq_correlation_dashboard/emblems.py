from __future__ import annotations

# Hand-built panel emblems (24x24 SVG). Each plays a short CSS animation when its panel
# is hovered and settles back afterwards; the keyframes live in theme.build_css.

import html

from .theme import TINTS, heatmap_color

_SVG = '<svg class="cd-emblem {cls}" width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">{body}</svg>'
_STROKE = 'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"'


def _candles() -> str:
    candles = [(6, 7, 19, 10, 6, 0.5), (12, 4, 16.5, 6.5, 7, 0.75), (18, 2, 13, 4, 6.5, 1.0)]
    body = ""
    for i, (x, top, bottom, y, h, opacity) in enumerate(candles):
        body += f'<line x1="{x}" y1="{top}" x2="{x}" y2="{bottom}" {_STROKE} stroke-width="1.2" opacity="{opacity}"/>'
        body += (
            f'<rect class="e-body" style="--i:{i}" x="{x - 1.9}" y="{y}" width="3.8" height="{h}" rx="1" '
            f'fill="currentColor" opacity="{opacity}"/>'
        )
    return _SVG.format(cls="e-candles", body=body)


def _matrix() -> str:
    # Symmetric 3x3 tile: the diagonal (self-correlation) is brightest.
    tile, gap = 5.4, 1.6
    origin = (24 - (3 * tile + 2 * gap)) / 2
    opacity = {0: 1.0, 1: 0.55, 2: 0.28}
    body = ""
    for r in range(3):
        for c in range(3):
            d = abs(r - c)
            body += (
                f'<rect style="--d:{d}" x="{origin + c * (tile + gap):.2f}" y="{origin + r * (tile + gap):.2f}" '
                f'width="{tile}" height="{tile}" rx="1.3" fill="currentColor" opacity="{opacity[d]}"/>'
            )
    return _SVG.format(cls="e-matrix", body=body)


def _link(kind: str) -> str:
    dash = ' stroke-dasharray="1.6 2.2"' if kind == "weak" else ""
    body = (
        f'<line class="e-tie" x1="7" y1="12" x2="17" y2="12" {_STROKE} opacity="0.7"{dash}/>'
        '<circle class="e-node l" cx="5.5" cy="12" r="3.2" fill="currentColor"/>'
        f'<circle class="e-node r" cx="18.5" cy="12" r="3.2" fill="currentColor" opacity="{0.55 if kind == "weak" else 0.85}"/>'
    )
    return _SVG.format(cls=f"e-link {kind}", body=body)


def _wave() -> str:
    body = (
        '<line x1="2" y1="19.5" x2="22" y2="19.5" stroke="currentColor" stroke-width="1" opacity="0.3"/>'
        f'<path class="draw" pathLength="1" d="M2 14.5 C5 14.5 6 8 9 8 S13 15.5 16 13.5 S19.5 6.5 21.5 6.5" {_STROKE}/>'
        '<circle class="e-pop" cx="21.5" cy="6.5" r="1.9" fill="currentColor"/>'
    )
    return _SVG.format(cls="e-wave", body=body)


def _twin() -> str:
    body = (
        f'<path class="draw" style="--i:0" pathLength="1" d="M2 13 C5 13 6 6.5 9 6.5 S13 14 16 12 S19.5 6 22 6" {_STROKE}/>'
        f'<path class="draw" style="--i:1" pathLength="1" d="M2 18 C5 18 6 11 9 11.5 S13 18.5 16 16.5 S19.5 11 22 10.5" '
        f'{_STROKE} opacity="0.5"/>'
    )
    return _SVG.format(cls="e-twin", body=body)


def _delta() -> str:
    bars = [("o-left", 12, 4.5, 8.5, 1.0), ("o-right", 4.5, 10.5, 7.5, 0.6), ("o-left", 12, 16.5, 5, 0.8)]
    body = '<line x1="12" y1="2.5" x2="12" y2="21.5" stroke="currentColor" stroke-width="1.2" opacity="0.45"/>'
    for i, (origin, x, y, w, opacity) in enumerate(bars):
        body += (
            f'<rect class="e-bar {origin}" style="--i:{i}" x="{x}" y="{y}" width="{w}" height="3.2" rx="1" '
            f'fill="currentColor" opacity="{opacity}"/>'
        )
    return _SVG.format(cls="e-delta", body=body)


def _tether() -> str:
    # A spread that strays from its mean and is pulled back: mean reversion.
    body = (
        '<line x1="2.5" y1="4.5" x2="21.5" y2="4.5" stroke="currentColor" stroke-width="1" stroke-dasharray="1.5 2" opacity="0.5"/>'
        '<line x1="2.5" y1="19.5" x2="21.5" y2="19.5" stroke="currentColor" stroke-width="1" stroke-dasharray="1.5 2" opacity="0.5"/>'
        '<line x1="2.5" y1="12" x2="21.5" y2="12" stroke="currentColor" stroke-width="1.2" opacity="0.3"/>'
        '<circle class="e-dot" cx="12" cy="12" r="2.8" fill="currentColor"/>'
    )
    return _SVG.format(cls="e-tether", body=body)


def _ranks() -> str:
    body = ""
    for i, (w, opacity) in enumerate([(18, 1.0), (14, 0.75), (10.5, 0.55), (7, 0.35)]):
        body += (
            f'<rect class="e-bar o-left" style="--i:{i}" x="3" y="{3.5 + i * 4.6}" width="{w}" height="3" rx="1" '
            f'fill="currentColor" opacity="{opacity}"/>'
        )
    return _SVG.format(cls="e-ranks", body=body)


def _chain() -> str:
    # Membership source, ranking proxy, fallback: a signal passes down the chain.
    body = '<line x1="4" y1="12" x2="20" y2="12" stroke="currentColor" stroke-width="1.3" opacity="0.4"/>'
    for i, (x, opacity) in enumerate([(4, 1.0), (12, 0.7), (20, 0.4)]):
        body += f'<circle class="e-node" style="--i:{i}" cx="{x}" cy="12" r="2.6" fill="currentColor" opacity="{opacity}"/>'
    return _SVG.format(cls="e-chain", body=body)


def _check() -> str:
    body = (
        f'<rect x="3" y="3" width="18" height="18" rx="5" {_STROKE} opacity="0.45"/>'
        f'<path class="draw" pathLength="1" d="M7.5 12.5 L10.5 15.5 L16.5 8.5" {_STROKE} stroke-width="1.9"/>'
    )
    return _SVG.format(cls="e-check", body=body)


def _braces() -> str:
    body = (
        f'<path class="e-brace l" d="M8 3.5 C6 3.5 5.5 4.5 5.5 6.5 V9.5 C5.5 11 4.8 12 3.5 12 C4.8 12 5.5 13 5.5 14.5 '
        f'V17.5 C5.5 19.5 6 20.5 8 20.5" {_STROKE}/>'
        f'<path class="e-brace r" d="M16 3.5 C18 3.5 18.5 4.5 18.5 6.5 V9.5 C18.5 11 19.2 12 20.5 12 C19.2 12 18.5 13 18.5 14.5 '
        f'V17.5 C18.5 19.5 18 20.5 16 20.5" {_STROKE}/>'
    )
    for i, x in enumerate([9.5, 12, 14.5]):
        body += f'<circle class="e-node" style="--i:{i}" cx="{x}" cy="12" r="1.15" fill="currentColor"/>'
    return _SVG.format(cls="e-braces", body=body)


def _clock() -> str:
    body = (
        f'<circle cx="12" cy="12" r="9" {_STROKE} opacity="0.5"/>'
        f'<line x1="12" y1="12" x2="15.5" y2="12" {_STROKE} stroke-width="1.8"/>'
        f'<line class="e-hand o-pivot" x1="12" y1="5.5" x2="12" y2="12" {_STROKE} stroke-width="1.8"/>'
        '<circle cx="12" cy="12" r="1.3" fill="currentColor"/>'
    )
    return _SVG.format(cls="e-clock", body=body)


def _venn() -> str:
    body = (
        '<circle class="e-ring l" cx="8.5" cy="12" r="6" fill="currentColor" fill-opacity="0.18" '
        f'{_STROKE} stroke-width="1.4"/>'
        '<circle class="e-ring r" cx="15.5" cy="12" r="6" fill="currentColor" fill-opacity="0.18" '
        f'{_STROKE} stroke-width="1.4" opacity="0.7"/>'
    )
    return _SVG.format(cls="e-venn", body=body)


def _gauge() -> str:
    body = (
        f'<path d="M3.5 17 A8.5 8.5 0 0 1 20.5 17" {_STROKE} opacity="0.45"/>'
        f'<path d="M15.5 9.5 A8.5 8.5 0 0 1 20.5 17" {_STROKE} stroke-width="2"/>'
        f'<line class="e-needle o-pivot" x1="12" y1="9" x2="12" y2="17" {_STROKE} stroke-width="1.8"/>'
        '<circle cx="12" cy="17" r="1.6" fill="currentColor"/>'
    )
    return _SVG.format(cls="e-gauge", body=body)


EMBLEMS = {
    "candles": _candles,
    "matrix": _matrix,
    "strong": lambda: _link("strong"),
    "weak": lambda: _link("weak"),
    "wave": _wave,
    "twin": _twin,
    "delta": _delta,
    "tether": _tether,
    "ranks": _ranks,
    "chain": _chain,
    "check": _check,
    "braces": _braces,
    "clock": _clock,
    "venn": _venn,
    "gauge": _gauge,
}


def emblem_badge(emblem: str, tint: str = "cyan") -> str:
    color = TINTS.get(tint, tint)
    return f'<span class="cd-badge" style="--tint:{html.escape(color)}">{EMBLEMS[emblem]()}</span>'


def panel_head(emblem: str, title: str, subtitle: str = "", tint: str = "cyan") -> str:
    sub = f'<div class="cd-panel-sub">{html.escape(subtitle)}</div>' if subtitle else ""
    return (
        '<div class="cd-panel-head">'
        f"{emblem_badge(emblem, tint)}"
        '<div class="cd-panel-titles">'
        f'<div class="cd-panel-title" role="heading" aria-level="2">{html.escape(title)}</div>{sub}'
        "</div></div>"
    )


def brand_mark(correlation, visuals: dict, size: int = 5) -> str:
    """A 5x5 tile cut from the live correlation matrix, colored on the heatmap scale."""
    import pandas as pd

    frame = correlation if isinstance(correlation, pd.DataFrame) else pd.DataFrame()
    n = min(size, len(frame.index), len(frame.columns))
    cell, gap = 8.0, 1.0
    total = n * cell + (n - 1) * gap if n else 1
    rects = ""
    for r in range(n):
        for c in range(n):
            value = frame.iat[r, c]
            fill = heatmap_color(float(value) if pd.notna(value) else 0.0, visuals)
            rects += (
                f'<rect style="--d:{abs(r - c)}" x="{c * (cell + gap)}" y="{r * (cell + gap)}" '
                f'width="{cell}" height="{cell}" rx="2" fill="{fill}"/>'
            )
    return (
        f'<svg class="cd-mark" viewBox="0 0 {total} {total}" role="img" '
        f'aria-label="Brand mark: correlations among the top {n} names">{rects}</svg>'
    )
