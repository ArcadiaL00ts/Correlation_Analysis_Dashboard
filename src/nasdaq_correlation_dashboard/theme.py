from __future__ import annotations

# Dashboard theme tokens, Plotly palette and injected Streamlit CSS.

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


def resolve_theme_tokens(visuals: dict) -> dict[str, str]:
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


def resolve_visual_float(visuals: dict, key: str, minimum: float, maximum: float) -> float:
    fallback = float(TERMINAL_VISUAL_DEFAULTS[key])
    try:
        candidate = float(visuals.get(key, fallback))
    except (TypeError, ValueError):
        candidate = fallback
    return min(max(candidate, minimum), maximum)


def plotly_theme(visuals: dict) -> dict[str, str]:
    tokens = resolve_theme_tokens(visuals)
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


def inject_styles(visuals: dict) -> None:
    import streamlit as st

    tokens = resolve_theme_tokens(visuals)
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
        .stTabs [data-baseweb="tab-list"],
        .stTabs [role="tablist"] {{
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

        /* data-baseweb selectors: Streamlit <= 1.5x; role selectors: React Aria tabs in newer releases. */
        .stTabs [data-baseweb="tab-list"],
        .stTabs [role="tablist"] {{
            gap: 0.65rem;
            padding: 0.45rem;
        }}
        .stTabs [data-baseweb="tab"],
        .stTabs [role="tab"] {{
            color: var(--text-muted) !important;
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(105,142,183,0.24);
            border-radius: 999px;
            padding: 0.48rem 1rem;
            font-family: var(--ui-font);
            font-weight: 600;
            transition: color 140ms ease, border-color 140ms ease, background 140ms ease;
        }}
        .stTabs [data-baseweb="tab"]:hover,
        .stTabs [role="tab"]:hover {{
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
        .stTabs [data-baseweb="tab-highlight"],
        .stTabs .react-aria-SelectionIndicator {{
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
        /* Let long metric values (date windows) wrap instead of truncating with an ellipsis. */
        [data-testid="stMetricValue"] > div {{
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
            overflow-wrap: anywhere;
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
        [data-testid="stSpinnerIcon"] {{
            position: relative;
            /* Ring only on the icon, so spinner text never sits inside it. */
            width: 32px !important;
            height: 32px !important;
            flex: 0 0 auto;
            border-radius: 50% !important;
            border: 2px solid rgba(53,212,255,0.24) !important;
            border-top-color: var(--accent-cyan) !important;
            border-right-color: rgba(53,212,255,0.50) !important;
            animation: sci-spin 0.72s linear infinite !important;
            box-shadow: 0 0 24px rgba(53,212,255,0.22), inset 0 0 16px rgba(53,212,255,0.18);
            background: radial-gradient(circle at center, rgba(53,212,255,0.10), transparent 64%);
        }}
        [data-testid="stSpinnerIcon"]::before {{
            content: "";
            position: absolute;
            inset: 5px;
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
            .stTabs [role="tab"]:hover,
            .stForm button:hover,
            div[data-baseweb="select"] > div:hover,
            div[data-baseweb="base-input"] > div:hover,
            div[data-baseweb="input"] > div:hover {{
                transform: none;
            }}
            [data-testid="stSpinnerIcon"],
            [data-testid="stSpinnerIcon"]::before {{
                animation-duration: 2.2s !important;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
