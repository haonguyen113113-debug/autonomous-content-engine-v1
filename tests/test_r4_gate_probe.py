"""Unit tests for the encoded-frame contrast probe used by tools/r4_gate.py.

The probe exists because the gate must grade the pixels the MP4 ships. Two
bugs cost real time while building it and are locked in here:

* the plate's own zoom means a zoom-1.0 still no longer covers the same rows;
* a glyph's bloom looks like a bright background unless it is excluded.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("r4_gate", ROOT / "tools" / "r4_gate.py")
r4_gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r4_gate)  # type: ignore[union-attr]


AMBER = (255, 176, 58)


def test_glyph_halo_excludes_the_warm_bloom_but_keeps_the_beam():
    fill_lum = r4_gate._luminance(AMBER)
    # A blend of the amber glyph into the plate — the glow that false-failed.
    assert r4_gate._is_glyph_halo((152, 122, 81), AMBER, fill_lum)
    assert r4_gate._is_glyph_halo((230, 199, 140), AMBER, fill_lum)
    # The cyan beam this bug once hid behind is NOT a halo.
    assert not r4_gate._is_glyph_halo((52, 239, 255), AMBER, fill_lum)
    # Nor is the dark scrim the credit actually sits on.
    assert not r4_gate._is_glyph_halo((5, 8, 15), AMBER, fill_lum)


def test_glyph_halo_for_light_fills_is_a_luminance_rule():
    fill = (242, 246, 255)
    fill_lum = r4_gate._luminance(fill)
    # Near-white plate pixels cannot hurt near-white type by luminance.
    assert r4_gate._is_glyph_halo((242, 246, 254), fill, fill_lum)
    # Dark plate behind the title is background.
    assert not r4_gate._is_glyph_halo((4, 11, 29), fill, fill_lum)


def test_ratio_matches_known_contrast_pairs():
    assert r4_gate._ratio(AMBER, (5, 8, 15)) > 6.0
    assert r4_gate._ratio(AMBER, (52, 239, 255)) < 1.5
    assert round(r4_gate._ratio((0, 0, 0), (255, 255, 255)), 1) == 21.0


def test_percentile_is_clamped_and_robust_to_a_single_sparkle():
    values = [0.001] * 999 + [1.0]
    assert r4_gate._percentile(values, 0.95) == 0.001
    assert r4_gate._percentile([0.5], 0.99) == 0.5
