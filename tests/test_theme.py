from __future__ import annotations

import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nasdaq_correlation_dashboard.emblems import EMBLEMS, brand_mark, panel_head  # noqa: E402
from nasdaq_correlation_dashboard.theme import (  # noqa: E402
    VISUAL_DEFAULTS,
    build_css,
    heatmap_color,
    resolve_theme_tokens,
    streamlit_theme_flags,
    streamlit_theme_options,
)


class ThemeTests(unittest.TestCase):
    def test_streamlit_config_matches_theme_defaults(self) -> None:
        # .streamlit/config.toml serves direct `streamlit run`; the launcher passes the same values as flags.
        config = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
        self.assertEqual(config["theme"], streamlit_theme_options())

    def test_font_option_is_a_family_name(self) -> None:
        # A "name:url" font value makes Streamlit drop the whole custom theme.
        self.assertNotIn("http", streamlit_theme_options()["font"])

    def test_flags_pair_keys_with_values(self) -> None:
        flags = streamlit_theme_flags({"accent": "#123456"})
        self.assertEqual(flags[flags.index("--theme.primaryColor") + 1], "#123456")

    def test_overrides_and_blank_values(self) -> None:
        tokens = resolve_theme_tokens({"ink": "#FFFFFF", "accent": " "})
        self.assertEqual(tokens["ink"], "#FFFFFF")
        self.assertEqual(tokens["accent"], VISUAL_DEFAULTS["accent"])

    def test_heatmap_scale_endpoints(self) -> None:
        self.assertEqual(heatmap_color(-1, {}), VISUAL_DEFAULTS["heatmap_min_color"].upper())
        self.assertEqual(heatmap_color(0, {}), VISUAL_DEFAULTS["heatmap_mid_color"].upper())
        self.assertEqual(heatmap_color(5, {}), VISUAL_DEFAULTS["heatmap_max_color"].upper())

    def test_css_respects_reduced_motion(self) -> None:
        self.assertIn("prefers-reduced-motion: reduce", build_css({}))


class EmblemTests(unittest.TestCase):
    def test_every_emblem_renders_decorative_svg(self) -> None:
        for name in EMBLEMS:
            head = panel_head(name, "Title", "Subtitle")
            self.assertIn('aria-hidden="true"', head, name)

    def test_panel_head_escapes_text(self) -> None:
        head = panel_head("matrix", "<b>x</b>", "<i>y</i>")
        self.assertNotIn("<b>x</b>", head)
        self.assertNotIn("<i>y</i>", head)

    def test_brand_mark_handles_small_matrix(self) -> None:
        import pandas as pd

        frame = pd.DataFrame([[1.0, 0.2], [0.2, 1.0]], index=["A", "B"], columns=["A", "B"])
        self.assertEqual(brand_mark(frame, {}).count("<rect"), 4)



class HeatmapLabelTests(unittest.TestCase):
    def test_compact_labels(self) -> None:
        import pandas as pd

        from nasdaq_correlation_dashboard.dashboard import _heatmap_height, _heatmap_labels

        frame = pd.DataFrame([[1.0, -0.134], [0.051, float("nan")]])
        self.assertEqual(_heatmap_labels(frame), [["1", "-.13"], [".05", ""]])
        self.assertEqual(_heatmap_height(50), 50 * 24 + 150)
        big = pd.DataFrame([[0.5] * 81] * 81)
        self.assertEqual({label for row in _heatmap_labels(big) for label in row}, {""})

if __name__ == "__main__":
    unittest.main()
