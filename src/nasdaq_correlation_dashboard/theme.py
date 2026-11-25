from __future__ import annotations

# Dashboard theme: design tokens, Plotly palette, Streamlit base theme and injected CSS.
# Token groups follow the shared dashboard design system (surfaces, lines, ink, signal);
# `config/dashboard_config.json` -> `visuals` overrides any of them at runtime.

VISUAL_DEFAULTS: dict[str, str] = {
    # Surfaces: each step slightly lighter.
    "bg": "#0A0D12",
    "surface": "#0E1218",
    "surface_2": "#141922",
    "surface_3": "#1B212C",
    # Lines: low-contrast borders.
    "line": "rgba(255,255,255,0.07)",
    "line_2": "rgba(255,255,255,0.12)",
    # Text: primary, secondary, muted (never a series color).
    "ink": "#E8ECF2",
    "ink_2": "#9AA3B2",
    "ink_3": "#7A8394",
    # Signal colors with reserved meanings.
    "accent": "#58C8FF",
    "accent_2": "#7BA9FF",
    "pos": "#22C55E",
    "neg": "#FB7185",
    "warn": "#E9B949",
    # Type.
    "ui_font": "Inter",
    "mono_font": "JetBrains Mono",
    # Correlation heatmap scale (red -> neutral -> blue); domain stays locked to [-1, 1].
    "heatmap_min_color": "#7D3A4A",
    "heatmap_mid_color": "#DCE7F6",
    "heatmap_max_color": "#1C8BC4",
}

# Panel emblem tints (identity only; text never uses them).
TINTS: dict[str, str] = {
    "cyan": "#58C8FF",
    "blue": "#7BA9FF",
    "green": "#22C55E",
    "rose": "#FB7185",
    "amber": "#E9B949",
    "violet": "#A78BFA",
}

FONT_CSS_URL = (
    "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700"
    "&family=JetBrains+Mono:wght@400;500;600&display=swap"
)


def resolve_theme_tokens(visuals: dict) -> dict[str, str]:
    """Defaults overlaid with any non-empty `visuals` override."""
    tokens: dict[str, str] = {}
    for name, default in VISUAL_DEFAULTS.items():
        value = visuals.get(name)
        tokens[name] = default if value is None or str(value).strip() == "" else str(value).strip()
    return tokens


def hex_to_rgba(color: str, alpha: float) -> str:
    value = color.lstrip("#")
    red, green, blue = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({red},{green},{blue},{alpha})"


def heatmap_color(value: float, visuals: dict) -> str:
    """Color for a correlation in [-1, 1] on the configured diverging scale."""
    tokens = resolve_theme_tokens(visuals)
    value = max(-1.0, min(1.0, float(value)))
    start = tokens["heatmap_mid_color"]
    end = tokens["heatmap_max_color"] if value >= 0 else tokens["heatmap_min_color"]
    t = abs(value)
    a = [int(start.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)]
    b = [int(end.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(a, b))


def streamlit_theme_options(visuals: dict | None = None) -> dict[str, str]:
    """Streamlit base theme (widgets, dataframes, sliders) matching the CSS tokens."""
    tokens = resolve_theme_tokens(visuals or {})
    return {
        "base": "dark",
        "primaryColor": tokens["accent"],
        "backgroundColor": tokens["bg"],
        "secondaryBackgroundColor": tokens["surface_2"],
        "textColor": tokens["ink"],
        "borderColor": "#262C37",
        "dataframeBorderColor": "#20262F",
        "dataframeHeaderBackgroundColor": tokens["surface_3"],
        # Family names only: a "name:url" value here makes Streamlit drop the whole custom theme.
        # The fonts themselves load through the @import in build_css.
        "font": f"{tokens['ui_font']}, sans-serif",
        "codeFont": f"{tokens['mono_font']}, monospace",
        "baseRadius": "8px",
    }


def streamlit_theme_flags(visuals: dict | None = None) -> list[str]:
    flags: list[str] = []
    for key, value in streamlit_theme_options(visuals).items():
        flags += [f"--theme.{key}", value]
    return flags


def plotly_theme(visuals: dict) -> dict[str, str]:
    tokens = resolve_theme_tokens(visuals)
    return {
        "ui_font": tokens["ui_font"],
        "mono_font": tokens["mono_font"],
        "ink": tokens["ink"],
        "ink_2": tokens["ink_2"],
        "ink_3": tokens["ink_3"],
        "accent": tokens["accent"],
        "accent_2": tokens["accent_2"],
        "pos": tokens["pos"],
        "neg": tokens["neg"],
        "warn": tokens["warn"],
        "plot_bg": "rgba(0,0,0,0)",
        "grid": "rgba(255,255,255,0.06)",
        "grid_strong": "rgba(255,255,255,0.09)",
        "zero": "rgba(232,236,242,0.32)",
        "spike": "rgba(232,236,242,0.35)",
        "tip_bg": "#12161E",
        "tip_border": tokens["line_2"],
        "annotation_bg": hex_to_rgba(tokens["surface_2"], 0.92),
        "annotation_border": tokens["line_2"],
        "accent_fill": hex_to_rgba(tokens["accent"], 0.26),
        "accent_2_fill": hex_to_rgba(tokens["accent_2"], 0.26),
        "pos_fill": hex_to_rgba(tokens["pos"], 0.34),
        "neg_fill": hex_to_rgba(tokens["neg"], 0.34),
        "clear": "rgba(0,0,0,0)",
    }


def hoverlabel(visuals: dict) -> dict:
    theme = plotly_theme(visuals)
    return {
        "bgcolor": theme["tip_bg"],
        "bordercolor": theme["tip_border"],
        "font": {"family": theme["ui_font"], "size": 12, "color": theme["ink"]},
        "align": "left",
        "namelength": -1,
    }


# Selector for every element whose hover plays its emblem animation.
_HOVER = ':is([class*="st-key-panel_"], .cd-card, .cd-hero):hover'


def build_css(visuals: dict) -> str:
    t = resolve_theme_tokens(visuals)
    h = _HOVER
    return f"""
@import url('{FONT_CSS_URL}');

:root {{
    --bg: {t["bg"]};
    --surface: {t["surface"]};
    --surface-2: {t["surface_2"]};
    --surface-3: {t["surface_3"]};
    --line: {t["line"]};
    --line-2: {t["line_2"]};
    --ink: {t["ink"]};
    --ink-2: {t["ink_2"]};
    --ink-3: {t["ink_3"]};
    --accent: {t["accent"]};
    --accent-2: {t["accent_2"]};
    --pos: {t["pos"]};
    --neg: {t["neg"]};
    --warn: {t["warn"]};
    --font-sans: '{t["ui_font"]}', system-ui, -apple-system, 'Segoe UI', sans-serif;
    --font-mono: '{t["mono_font"]}', ui-monospace, monospace;
    --spring: cubic-bezier(0.34, 1.4, 0.64, 1);
    --ease-out: cubic-bezier(0.22, 1, 0.36, 1);
    --focus-ring: 0 0 0 2px var(--bg), 0 0 0 4px color-mix(in srgb, var(--accent) 70%, transparent);
    color-scheme: dark;
}}

/* ---------- page ---------- */
html, body, .stApp, [data-testid="stAppViewContainer"] {{
    background:
        radial-gradient(1200px 600px at 8% -12%, color-mix(in srgb, var(--accent) 8%, transparent), transparent 60%),
        radial-gradient(900px 500px at 100% 0%, color-mix(in srgb, var(--accent-2) 6%, transparent), transparent 60%),
        var(--bg);
    color: var(--ink);
    font-family: var(--font-sans);
    -webkit-font-smoothing: antialiased;
}}
[data-testid="stHeader"] {{ background: transparent; }}
.main .block-container, [data-testid="stMainBlockContainer"] {{
    max-width: 1560px;
    padding-top: 1.75rem;
    padding-bottom: 2.5rem;
}}
@media (max-width: 640px) {{
    .main .block-container, [data-testid="stMainBlockContainer"] {{ padding-left: 16px; padding-right: 16px; }}
}}
.stApp p, .stApp li, .stApp label {{ font-family: var(--font-sans); }}
.tabular, [data-testid="stMetricValue"] {{ font-variant-numeric: tabular-nums; }}
::-webkit-scrollbar {{ height: 8px; width: 8px; }}
::-webkit-scrollbar-thumb {{ background: #262B35; border-radius: 8px; }}
::-webkit-scrollbar-track {{ background: transparent; }}

/* ---------- motion presets ---------- */
@keyframes cd-fade-up {{
    from {{ opacity: 0; transform: translateY(14px); }}
    to {{ opacity: 1; transform: none; }}
}}
@keyframes cd-spin {{ to {{ transform: rotate(360deg); }} }}

/* ---------- header ---------- */
.cd-hero {{
    display: flex; flex-wrap: wrap; align-items: center; gap: 14px 16px;
    padding: 0 0 18px 0; margin-bottom: 4px;
    border-bottom: 1px solid var(--line);
    animation: cd-fade-up 0.5s var(--ease-out) both;
}}
.cd-hero-titles {{ min-width: 0; flex: 1 1 320px; }}
.stApp .cd-hero-title {{
    margin: 0; color: var(--ink); font-size: 26px; font-weight: 650; line-height: 1.2; letter-spacing: -0.015em;
}}
.stApp p.cd-hero-sub {{ margin: 4px 0 0 0; color: var(--ink-2); font-size: 13px; line-height: 1.5; max-width: 78ch; }}
.cd-chips {{ display: flex; flex-wrap: wrap; gap: 8px; }}
.cd-chip {{
    display: inline-flex; align-items: center; gap: 7px; white-space: nowrap;
    padding: 4px 11px; border-radius: 999px; font-size: 11.5px; font-weight: 500;
    color: var(--ink-2); background: var(--surface-2); border: 1px solid var(--line);
    font-variant-numeric: tabular-nums;
}}
.cd-chip b {{ color: var(--ink); font-weight: 600; }}
.cd-chip-dot {{ width: 6px; height: 6px; border-radius: 50%; background: var(--chip, var(--accent)); }}

/* brand mark: a tile from the live correlation matrix */
.cd-mark {{ flex: none; width: 44px; height: 44px; }}
.cd-mark rect {{ transform-box: fill-box; transform-origin: center; }}
.cd-hero:hover .cd-mark rect {{ animation: cd-mark-ripple 0.75s var(--ease-out) both; animation-delay: calc(var(--d) * 70ms); }}
@keyframes cd-mark-ripple {{
    0% {{ transform: scale(1); }}
    35% {{ transform: scale(0.55); opacity: 0.6; }}
    70% {{ transform: scale(1.1); opacity: 1; }}
    100% {{ transform: scale(1); }}
}}

/* ---------- panel shell ---------- */
[class*="st-key-panel_"] {{
    background: color-mix(in srgb, var(--surface) 88%, transparent);
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 0 20px 20px 20px;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.04), 0 20px 40px -24px rgba(0,0,0,0.7);
    animation: cd-fade-up 0.55s var(--ease-out) both;
    animation-delay: var(--delay, 0ms);
    transition: border-color 0.25s ease, box-shadow 0.25s ease;
}}
[class*="st-key-panel_"]:hover {{
    border-color: var(--line-2);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.05), 0 26px 48px -24px rgba(0,0,0,0.85);
}}
@media (max-width: 640px) {{ [class*="st-key-panel_"] {{ padding: 0 14px 14px 14px; }} }}

/* ---------- adaptive correlation matrix ---------- */
/* Wide screens: the matrix panel grows past the content width (up to 1900px) for bigger cells. */
@media (min-width: 1760px) {{
    .st-key-panel_heatmap {{
        --hm-width: min(calc(100vw - 120px), 1900px);
        width: var(--hm-width) !important;
        max-width: none;
        margin-left: calc((100% - var(--hm-width)) / 2);
    }}
}}
/* Cell labels sized from the chart's real width: plot area ~ chart width minus ~200px of
   ticker labels and colorbar, split across --hm-n columns; a 4-character label ("-.13")
   needs about 2.4 font-sizes of width in the mono face. */
.st-key-panel_heatmap [data-testid="stPlotlyChart"] {{ container-type: inline-size; }}
.st-key-panel_heatmap .heatmap-label text {{
    font-size: clamp(6px, calc((100cqw - 200px) / var(--hm-n, 50) / 2.8), 12px) !important;
}}
.cd-panel-head {{
    display: flex; align-items: center; gap: 12px;
    margin: 0 -20px 4px -20px; padding: 16px 20px 14px 20px;
    border-bottom: 1px solid var(--line);
}}
.cd-panel-titles {{ min-width: 0; flex: 1; }}
.cd-panel-title {{ color: var(--ink); font-size: 15px; font-weight: 600; letter-spacing: -0.01em; line-height: 1.3; }}
.cd-panel-sub {{ color: var(--ink-2); font-size: 12px; line-height: 1.45; margin-top: 2px; }}

/* ---------- emblem badge: a split ring (two legs of a pair) that turns half a lap on hover ---------- */
.cd-badge {{
    position: relative; flex: none; width: 40px; height: 40px;
    display: grid; place-items: center; color: var(--tint);
}}
.cd-badge::before {{
    content: ""; position: absolute; inset: 0; border-radius: 50%;
    background: conic-gradient(from 20deg, var(--tint) 0 24%, transparent 24% 50%,
        color-mix(in srgb, var(--tint) 45%, transparent) 50% 74%, transparent 74%);
    -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 1.4px), #000 calc(100% - 1.1px));
    mask: radial-gradient(farthest-side, transparent calc(100% - 1.4px), #000 calc(100% - 1.1px));
    opacity: 0.7;
    transition: transform 1s var(--ease-out), opacity 0.3s ease;
}}
.cd-badge::after {{
    content: ""; position: absolute; inset: 3px; border-radius: 50%;
    background: radial-gradient(circle, color-mix(in srgb, var(--tint) 12%, transparent), transparent 72%);
    opacity: 0.55; transition: box-shadow 0.35s ease, opacity 0.35s ease;
}}
{h} .cd-badge::before {{ transform: rotate(180deg); opacity: 1; }}
{h} .cd-badge::after {{ opacity: 1; box-shadow: inset 0 0 12px color-mix(in srgb, var(--tint) 28%, transparent); }}
.cd-emblem {{ position: relative; z-index: 1; overflow: visible; }}
.cd-emblem * {{ transform-box: fill-box; transform-origin: center; }}
.cd-emblem .o-left {{ transform-origin: left center; }}
.cd-emblem .o-right {{ transform-origin: right center; }}
.cd-emblem .o-bottom {{ transform-origin: center bottom; }}
.cd-emblem .o-pivot {{ transform-origin: center bottom; }}
.cd-emblem .draw {{ stroke-dasharray: 1; stroke-dashoffset: 0; }}

/* emblem animations: play once on hover, then settle */
{h} .e-candles .e-body {{ animation: e-grow 0.6s var(--spring) both; animation-delay: calc(var(--i) * 110ms); }}
@keyframes e-grow {{ from {{ transform: scaleY(0.2); }} to {{ transform: scaleY(1); }} }}

{h} .e-matrix rect {{ animation: e-ripple 0.7s var(--ease-out) both; animation-delay: calc(var(--d) * 110ms); }}
@keyframes e-ripple {{
    0% {{ transform: scale(1); }}
    40% {{ transform: scale(0.6); opacity: 0.35; }}
    75% {{ transform: scale(1.15); opacity: 1; }}
    100% {{ transform: scale(1); }}
}}

.e-link .e-node, .e-link .e-tie {{ transition: transform 0.5s var(--spring), opacity 0.3s ease; }}
{h} .e-link.strong .e-node.l {{ transform: translateX(2.6px); }}
{h} .e-link.strong .e-node.r {{ transform: translateX(-2.6px); }}
{h} .e-link.strong .e-tie {{ transform: scaleX(0.55); }}
{h} .e-link.weak .e-node.l {{ transform: translateX(-1.8px); }}
{h} .e-link.weak .e-node.r {{ transform: translateX(1.8px); }}
{h} .e-link.weak .e-tie {{ opacity: 0.15; }}

{h} .draw {{ animation: e-draw 0.8s var(--ease-out) both; animation-delay: calc(var(--i, 0) * 150ms); }}
@keyframes e-draw {{ from {{ stroke-dashoffset: 1; }} to {{ stroke-dashoffset: 0; }} }}
{h} .e-pop {{ animation: e-pop 0.45s var(--spring) both; animation-delay: 0.65s; }}
@keyframes e-pop {{ from {{ transform: scale(0); }} to {{ transform: scale(1); }} }}

{h} .e-delta .e-bar {{ animation: e-grow-x 0.55s var(--spring) both; animation-delay: calc(var(--i) * 100ms); }}
@keyframes e-grow-x {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}

{h} .e-tether .e-dot {{ animation: e-revert 1.2s cubic-bezier(0.45, 0, 0.3, 1) both; }}
@keyframes e-revert {{
    0% {{ transform: translateY(0); }}
    18% {{ transform: translateY(-6.5px); }}
    40% {{ transform: translateY(5px); }}
    60% {{ transform: translateY(-2.8px); }}
    80% {{ transform: translateY(1.2px); }}
    100% {{ transform: translateY(0); }}
}}

{h} .e-ranks .e-bar {{ animation: e-grow-x 0.6s var(--ease-out) both; animation-delay: calc(var(--i) * 90ms); }}

{h} .e-chain .e-node {{ animation: e-pulse 0.5s var(--ease-out) both; animation-delay: calc(var(--i) * 160ms); }}
@keyframes e-pulse {{ 0% {{ transform: scale(1); }} 45% {{ transform: scale(1.55); }} 100% {{ transform: scale(1); }} }}

.e-braces .e-brace {{ transition: transform 0.45s var(--spring); }}
{h} .e-braces .e-brace.l {{ transform: translateX(-1.6px); }}
{h} .e-braces .e-brace.r {{ transform: translateX(1.6px); }}
{h} .e-braces .e-node {{ animation: e-pulse 0.45s var(--ease-out) both; animation-delay: calc(var(--i) * 120ms + 0.1s); }}

{h} .e-clock .e-hand {{ animation: e-sweep 0.9s var(--ease-out) both; }}
@keyframes e-sweep {{ from {{ transform: rotate(0deg); }} to {{ transform: rotate(360deg); }} }}

.e-venn .e-ring {{ transition: transform 0.5s var(--spring); }}
{h} .e-venn .e-ring.l {{ transform: translateX(1.8px); }}
{h} .e-venn .e-ring.r {{ transform: translateX(-1.8px); }}

.e-gauge .e-needle {{ transform: rotate(-55deg); transition: transform 0.7s var(--spring); }}
{h} .e-gauge .e-needle {{ transform: rotate(38deg); }}

/* ---------- info cards (status, definitions) ---------- */
.cd-card {{
    background: color-mix(in srgb, var(--surface) 88%, transparent);
    border: 1px solid var(--line); border-radius: 16px;
    padding: 0 18px 14px 18px; margin-bottom: 0.25rem; min-height: 9.5rem;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.04), 0 20px 40px -24px rgba(0,0,0,0.7);
    animation: cd-fade-up 0.55s var(--ease-out) both;
    transition: border-color 0.25s ease, transform 0.35s var(--spring);
}}
.cd-card:hover {{ border-color: var(--line-2); transform: translateY(-2px); }}
.cd-card .cd-panel-head {{ margin: 0 -18px 8px -18px; padding: 14px 18px 12px 18px; }}
[class*="st-key-panel_"] .cd-card {{ background: var(--surface-2); box-shadow: none; animation: none; }}
.stApp ul.cd-rows, .stApp ul.cd-defs {{ margin: 0; padding: 0; list-style: none; }}
.stApp li.cd-row {{ margin: 0;
    display: flex; justify-content: space-between; align-items: baseline; gap: 16px;
    padding: 5px 0; font-size: 12.5px; border-bottom: 1px dashed var(--line);
}}
.stApp li.cd-row:last-child {{ border-bottom: 0; }}
.cd-row-label {{ color: var(--ink-2); flex: none; }}
.cd-row-value {{ color: var(--ink); font-weight: 500; text-align: right; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }}

.stApp .cd-defs li {{ margin: 0; padding: 6px 0; font-size: 12.5px; line-height: 1.5; color: var(--ink-2); border-bottom: 1px dashed var(--line); }}
.stApp .cd-defs li:last-child {{ border-bottom: 0; }}
.cd-defs strong {{ color: var(--ink); font-weight: 600; }}

/* ---------- stat tiles ---------- */
[data-testid="stMetric"] {{
    background: var(--surface); border: 1px solid var(--line); border-radius: 12px;
    padding: 14px 16px;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
    animation: cd-fade-up 0.5s var(--ease-out) both;
    transition: transform 0.35s var(--spring), border-color 0.25s ease, box-shadow 0.25s ease;
}}
[data-testid="stMetric"]:hover {{
    transform: translateY(-2px);
    border-color: color-mix(in srgb, var(--accent) 35%, transparent);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.04), 0 14px 30px -18px color-mix(in srgb, var(--accent) 40%, transparent);
}}
[data-testid="stMetricLabel"] p {{ color: var(--ink-2) !important; font-size: 12px !important; font-weight: 500; }}
[data-testid="stMetricValue"] {{ color: var(--ink) !important; font-family: var(--font-mono) !important; font-size: 24px !important; font-weight: 500; }}
[data-testid="stMetricValue"] > div {{ white-space: normal !important; overflow: visible !important; text-overflow: clip !important; overflow-wrap: anywhere; }}

/* ---------- tabs: segmented control with a sliding pill ---------- */
.stTabs [data-baseweb="tab-list"], .stTabs [role="tablist"] {{
    position: relative; width: fit-content; max-width: 100%; gap: 2px; padding: 4px;
    background: var(--surface-2); border: 1px solid var(--line); border-radius: 12px;
}}
.stTabs [data-baseweb="tab"], .stTabs [role="tab"] {{
    position: relative; z-index: 1; height: auto; padding: 7px 14px; margin: 0;
    border-radius: 8px; background: transparent !important; border: 0;
    color: var(--ink-3) !important; transition: color 0.2s ease;
}}
.stTabs [role="tab"] p {{ font-size: 13px; font-weight: 500; }}
.stTabs [role="tab"]:hover {{ color: var(--ink-2) !important; }}
.stTabs [aria-selected="true"] {{ color: var(--ink) !important; }}
.stTabs [role="tab"]:focus-visible {{ outline: none; box-shadow: var(--focus-ring); }}
.stTabs [data-baseweb="tab-highlight"] {{
    top: 4px; bottom: auto !important; height: calc(100% - 8px) !important; z-index: 0;
    border-radius: 8px; background: var(--surface-3) !important;
    box-shadow: inset 0 0 0 1px rgba(255,255,255,0.08);
    transition: transform 0.38s var(--spring), width 0.38s var(--spring) !important;
}}
.stTabs .react-aria-SelectionIndicator {{
    border-radius: 8px; background: var(--surface-3) !important; height: 100% !important;
    transition: translate 0.38s var(--spring), width 0.38s var(--spring);
}}
.stTabs [data-baseweb="tab-border"] {{ display: none; }}
.stTabs [data-baseweb="tab-panel"], .stTabs [role="tabpanel"] {{ padding-top: 18px; }}

/* ---------- radios: segmented control ---------- */
[data-testid="stRadio"] div[role="radiogroup"] {{
    display: inline-flex; flex-wrap: wrap; gap: 2px; width: fit-content; max-width: 100%;
    padding: 4px; background: var(--surface-2); border: 1px solid var(--line); border-radius: 12px;
}}
[data-testid="stRadio"] label[data-baseweb="radio"] {{
    margin: 0; padding: 6px 13px; border-radius: 8px; cursor: pointer;
    transition: background-color 0.2s ease, box-shadow 0.2s ease, transform 0.15s ease;
}}
[data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child {{ display: none; }}
[data-testid="stRadio"] label[data-baseweb="radio"] p {{ color: var(--ink-3); font-size: 12.5px; font-weight: 500; transition: color 0.2s ease; }}
[data-testid="stRadio"] label[data-baseweb="radio"]:hover p {{ color: var(--ink-2); }}
[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {{
    background: var(--surface-3); box-shadow: inset 0 0 0 1px rgba(255,255,255,0.08);
}}
[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) p {{ color: var(--ink); }}
[data-testid="stRadio"] label[data-baseweb="radio"]:active {{ transform: scale(0.95); }}
[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:focus-visible) {{ box-shadow: var(--focus-ring); }}

/* ---------- widgets ---------- */
[data-testid="stWidgetLabel"] p {{ color: var(--ink-2) !important; font-size: 12px !important; font-weight: 500; }}
.stCaption, [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{
    color: var(--ink-2) !important; font-size: 12px;
}}
div[data-baseweb="select"] > div, div[data-baseweb="base-input"], div[data-baseweb="input"] {{
    background: var(--surface-2) !important; border-color: var(--line-2) !important; border-radius: 8px !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
}}
div[data-baseweb="select"] > div:hover, div[data-baseweb="input"]:hover {{ border-color: rgba(255,255,255,0.22) !important; }}
div[data-baseweb="select"] > div:focus-within, div[data-baseweb="input"]:focus-within {{
    border-color: color-mix(in srgb, var(--accent) 60%, transparent) !important; box-shadow: var(--focus-ring);
}}
div[data-baseweb="popover"] ul {{ background: var(--surface-2); }}

.stButton > button, [data-testid="stDownloadButton"] > button, .stForm button {{
    border-radius: 8px; border: 1px solid var(--line-2); background: var(--surface-2); color: var(--ink);
    font-weight: 500; cursor: pointer;
    transition: background-color 0.2s ease, border-color 0.2s ease, transform 0.3s var(--spring), box-shadow 0.2s ease;
}}
.stButton > button:hover, [data-testid="stDownloadButton"] > button:hover, .stForm button:hover {{
    background: var(--surface-3); border-color: rgba(255,255,255,0.2); color: var(--ink); transform: translateY(-1px);
}}
.stButton > button:active, [data-testid="stDownloadButton"] > button:active, .stForm button:active {{
    transform: scale(0.96); transition-duration: 0.1s;
}}
.stButton > button[kind="primary"] {{
    background: color-mix(in srgb, var(--accent) 16%, var(--surface-2));
    border-color: color-mix(in srgb, var(--accent) 50%, transparent); color: var(--ink);
}}
.stButton > button[kind="primary"]:hover {{
    background: color-mix(in srgb, var(--accent) 24%, var(--surface-2));
    border-color: color-mix(in srgb, var(--accent) 75%, transparent);
    box-shadow: 0 10px 24px -14px color-mix(in srgb, var(--accent) 70%, transparent);
}}
.stButton > button:focus-visible, [data-testid="stDownloadButton"] > button:focus-visible {{ box-shadow: var(--focus-ring); outline: none; }}

[data-testid="stExpander"] details {{
    background: color-mix(in srgb, var(--surface) 88%, transparent);
    border: 1px solid var(--line); border-radius: 12px; transition: border-color 0.25s ease;
}}
[data-testid="stExpander"] details:hover {{ border-color: var(--line-2); }}
[data-testid="stExpander"] summary p {{ color: var(--ink-2); font-size: 13px; font-weight: 500; }}
[data-testid="stExpander"] summary:hover p {{ color: var(--ink); }}

[data-testid="stDataFrame"] {{ border: 1px solid var(--line); border-radius: 12px; overflow: hidden; }}
[data-testid="stAlert"] > div {{ border-radius: 12px; }}
[data-testid="stPlotlyChart"] {{ animation: cd-fade-up 0.6s var(--ease-out) both; animation-delay: 80ms; }}

[data-testid="stSpinnerIcon"] {{
    width: 22px !important; height: 22px !important; border-radius: 50% !important;
    border: 2px solid color-mix(in srgb, var(--accent) 22%, transparent) !important;
    border-top-color: var(--accent) !important; animation: cd-spin 0.8s linear infinite !important;
}}

/* ---------- footer ---------- */
.stApp .cd-footer {{
    margin-top: 28px; padding-top: 16px; border-top: 1px solid var(--line);
    display: flex; flex-wrap: wrap; gap: 6px 18px; color: var(--ink-3); font-size: 11.5px; line-height: 1.5;
}}
.cd-footer b {{ color: var(--ink-2); font-weight: 500; }}

/* ---------- reduced motion: no entrances, no emblem plays, slow spinner ---------- */
@media (prefers-reduced-motion: reduce) {{
    *, *::before, *::after {{ animation-duration: 0.01ms !important; animation-delay: 0ms !important; transition-duration: 0.01ms !important; }}
    [data-testid="stSpinnerIcon"] {{ animation-duration: 2.4s !important; }}
    [data-testid="stMetric"]:hover, .cd-card:hover {{ transform: none; }}
}}
"""


def inject_styles(visuals: dict) -> None:
    import streamlit as st

    st.html(f"<style>{build_css(visuals)}</style>")
