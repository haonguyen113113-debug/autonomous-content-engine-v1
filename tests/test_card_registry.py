"""Card registry conformance: IDs, purposes, slots and renderer paths agree.

Locks docs/template-build-instruction.md: no card is built twice, none is
missed, none drifts from its renderer path. Planned cards are exempt from
file checks but must still declare purpose, slots and a valid path.
"""

from pathlib import Path

from apps.content_workflow import VISUAL_MODES
from apps.studio_templates.card_registry import BUILT, BY_ID, CARDS, PLANNED

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / "apps" / "studio_templates"

RENDER_MODES = set(VISUAL_MODES) | {"media_b_roll"}


def test_registry_counts():
    assert len(CARDS) == 89
    assert len(BUILT) == 89
    assert len(PLANNED) == 0
    assert len(BY_ID) == 89


def test_registry_entries_well_formed():
    for card in CARDS:
        assert card["aspect"] in ("short", "long"), card["id"]
        assert card["status"] in ("built", "planned"), card["id"]
        assert card["purpose"] and len(card["purpose"]) >= 10, card["id"]
        assert isinstance(card["slots"], list), card["id"]
        kind, target = card["renderer"]
        assert kind in ("starter", "generic", "frame"), card["id"]
        if kind == "generic":
            assert target in RENDER_MODES, (card["id"], target)
        if kind == "starter":
            assert card["aspect"] == "long", card["id"]


def test_built_cards_have_starters():
    missing = []
    for cid in BUILT:
        aspect = BY_ID[cid]["aspect"]
        if not (TPL / f"{cid}.{aspect}.json").is_file():
            missing.append(cid)
    assert missing == []


def test_card_selector_starters_stay_in_registry():
    from apps.card_selector import STARTERS_LONG, STARTERS_SHORT

    built = set(BUILT)
    for mode, sid in {**STARTERS_SHORT, **STARTERS_LONG}.items():
        assert sid in built, (mode, sid)


def test_starter_renderer_paths_cover_registry():
    """Every built card's fallback mode renders without crashing."""
    import tempfile

    from apps.video_renderer import _write_editorial_data_scene
    from template_foundation import resolve_template

    package = resolve_template(ROOT, "allen-knows-ball.shortform-analyst",
                               allow_draft=True)
    kwargs = dict(
        font_path=package.root / "resources/fonts/BeVietnamPro-Bold.ttf",
        display_font_path=package.root / "resources/fonts/BarlowCondensed-Bold.ttf",
        palette=package.design_tokens.get("palette", {}), scene_number=1,
    )
    samples = {
        "hook_card": {"hook_text": "Hang thu sap do toi nay"},
        "duel_columns": {"metrics": [{"label": "X", "home": "1", "away": "0"}],
                         "teams": ["A", "B"], "source": "D", "date": "D"},
        "stat_leader": {"stats": [{"label": "X", "value": "1"}],
                        "source": "D", "date": "D"},
        "player_poster_side": {"player_name": "A", "stats": [{"label": "X", "value": "1"}]},
        "score_card": {"home": "A", "away": "B", "score": "1 - 0"},
        "fixture_card": {"home": "A", "away": "B"},
        "quote_card": {"claim": "Noi dung trich dan"},
        "source_card": {"source": "S", "date": "D", "claim": "C"},
    }
    with tempfile.TemporaryDirectory() as tmp:
        for card in CARDS:
            if card["status"] != "built":
                continue
            kind, target = card["renderer"]
            if kind != "generic":
                continue
            out = Path(tmp) / f"{card['id']}.png"
            _write_editorial_data_scene(
                out, mode=target, data=dict(samples.get(target, {})),
                is_long=(card["aspect"] == "long"), **kwargs)
            assert out.stat().st_size > 5000, card["id"]
