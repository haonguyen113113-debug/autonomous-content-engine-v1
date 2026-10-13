"""Sports Kit motion atoms (Manim, build-time only).

PIL keeps Vietnamese typography exact (bundled Barlow/BeVietnam TTFs).
Manim animates reviewed values only: slide-in, punch-in, count-up, stagger.
The engine serves/renders video without Manim (see requirements-motion.txt).
"""

from __future__ import annotations

MANIM_MODES = (
    "comparison_duel",
    "stat_leader",
    "player_poster",
    "goal_card",
    "fixture_card",
    "score_card",
)

VI_FONT = "Arial"
DISPLAY_FONT = "Arial"

INK = "#0A0F0D"
CHALK = "#F5F2E8"
MUTED = "#8FA39A"
LIME = "#FFB300"
ORANGE = "#FF6B4A"
KIT_RED = "#B90B1A"
