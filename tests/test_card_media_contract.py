"""Card-media contract: authored regions, planner binding, renderer paint.

Contract under test (12.0.0):
- ``card-contract.json`` (schema 2.0) is the single executable card record;
  ``card-media-contract.json`` v1.0 is historical and not read at runtime.
- 89/89 built cards have a record; the ONLY variable library-media regions
  are ``C-04``/``MR-08``/``BP-03`` ``player_portrait``.
- The planner binds an asset only when it is a rights-verified, active image
  whose persisted scope was granted by a human; everything else is an
  explicit fallback that leaves the authored pack artwork.
- The frozen ``media_bindings`` + ``media_slot`` design layer are covered by
  ``graph_hash``; the validator rejects post-freeze edits.
- The renderer paints only bound slots, only inside the frozen box, and QA
  proves paint/leak against a pack-only render.

No ffmpeg, no network, no user runtime data (fixtures live under tmp_path).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from apps.asset_library.rights_scope import build_rights_scope

ROOT = Path(__file__).resolve().parent.parent

PORTRAIT_CARDS = ("C-04", "MR-08", "BP-03")


def _scope_json() -> str:
    return json.dumps(
        build_rights_scope(
            platforms=["youtube"],
            territories=["VN"],
            commercial=True,
            monetization=True,
            edit_allowed=True,
            credit_required=True,
            credit_text="Nguon anh / CC BY 4.0",
            license="CC BY 4.0",
            source="wikimedia-commons",
            reviewed_by="human",
        )
    )


def _asset_info(**overrides) -> dict:
    info = {
        "asset_id": "asset-portrait01",
        "asset_type": "image",
        "rights_state": "verified",
        "lifecycle_state": "active",
        "license_type": "CC BY 4.0",
        "purpose_code": "player-portrait",
        "rights_scope_json": _scope_json(),
    }
    info.update(overrides)
    return info


def _build(
    card_id: str = "C-04",
    mode: str = "player_poster_side",
    *,
    media_asset_id: str | None = None,
    asset_info: dict | None = None,
    player: str = "Erling Haaland",
):
    from apps.scene_graph.builder import build_scene_graph

    return build_scene_graph(
        segment_id="beat-1",
        visual_mode=mode,
        starter_id=card_id,
        graphic_data={
            "player_name": player,
            "stats": [
                {"label": "Ban thang", "value": "2"},
                {"label": "Tran", "value": "7"},
            ],
        },
        evidence=["ESPN 14/10/2026"],
        content_type="short",
        start_seconds=0.0,
        end_seconds=5.0,
        index=0,
        media_asset_id=media_asset_id,
        asset_info=asset_info,
    )


def _unfrozen(graph: dict) -> dict:
    provenance = graph.get("provenance")
    if isinstance(provenance, dict):
        provenance.pop("graph_hash", None)
    return graph


def _layer(graph: dict, layer_id: str) -> dict:
    for child in graph["design"]["pages"][0]["children"]:
        if isinstance(child, dict) and child.get("id") == layer_id:
            return child
    raise AssertionError(f"layer {layer_id!r} missing")


# --- contract document ------------------------------------------------------


def test_contract_declares_the_three_portrait_cards():
    from apps.studio_templates.card_media import load_contract, slot_box_px

    contract = load_contract("12.0.0")
    assert contract is not None
    cards = {card["card_id"]: card for card in contract["cards"]}
    assert set(PORTRAIT_CARDS) <= set(cards)
    for card_id in PORTRAIT_CARDS:
        card = cards[card_id]
        assert card["starter_file"] == f"{card_id}.short.json"
        assert (ROOT / "apps/studio_templates" / card["starter_file"]).is_file()
        assert "player_poster_side" in card["modes"]
        slots = {slot["slot_id"]: slot for slot in card["media_slots"]}
        slot = slots["player_portrait"]
        assert slot["role"] == "player_portrait"
        assert slot["asset_type"] == "image"
        assert slot["required"] is False
        assert slot["fit"] == "cover"
        assert slot["z_after_layer_id"] == card["pack_layer_id"] == "bed-60"
        assert slot_box_px(slot, (1080, 1920)) == [0, 282, 424, 1240]
        assert slot["fallback"]["behavior"] == "keep_pack_artwork"


def test_media_slots_filter_by_mode():
    from apps.studio_templates.card_media import media_slots

    assert media_slots("C-04", mode="player_poster_side")
    assert media_slots("MR-08", mode="potm_card")
    assert media_slots("BP-03", mode="player_card")
    assert media_slots("C-04", mode="tactical_explainer") == []


# --- planner binding --------------------------------------------------------


def test_builder_binds_approved_portrait_and_freezes_layer():
    from apps.scene_graph.schema import validate_scene_graph

    graph = _build(media_asset_id="asset-portrait01", asset_info=_asset_info())
    validate_scene_graph(graph)

    binding = graph["media_bindings"][0]
    assert binding["slot_id"] == "player_portrait"
    assert binding["status"] == "bound"
    assert binding["reason"] is None
    assert binding["asset"]["asset_id"] == "asset-portrait01"
    assert binding["asset"]["approval_status"] == "approved"
    assert binding["asset"]["rights_scope"] == "human-granted:youtube"
    assert binding["box_px"] == [0, 282, 424, 1240]

    # The layer is frozen at the authored z-order, right after bed-60.
    children = graph["design"]["pages"][0]["children"]
    ids = [child.get("id") for child in children]
    assert ids.index("media-player_portrait") == ids.index("bed-60") + 1
    layer = _layer(graph, "media-player_portrait")
    assert layer["type"] == "media_slot"
    assert layer["custom"] == {
        "slot_id": "player_portrait",
        "role": "player_portrait",
    }
    assert [layer["x"], layer["y"], layer["width"], layer["height"]] == [0, 282, 424, 1240]

    # Roles mirror exactly the ref that will paint.
    portrait = graph["roles"]["player_focus"]["portrait"]
    assert portrait["asset_id"] == "asset-portrait01"
    assert portrait["approval_status"] == "approved"


def test_builder_is_deterministic_with_media_binding():
    first = _build(media_asset_id="asset-portrait01", asset_info=_asset_info())
    second = _build(media_asset_id="asset-portrait01", asset_info=_asset_info())
    assert first == second
    assert first["provenance"]["graph_hash"] == second["provenance"]["graph_hash"]


def test_builder_falls_back_when_scope_is_not_human_granted():
    from apps.scene_graph.schema import validate_scene_graph

    info = _asset_info()
    info.pop("rights_scope_json")
    graph = _build(media_asset_id="asset-portrait01", asset_info=info)
    validate_scene_graph(graph)

    binding = graph["media_bindings"][0]
    assert binding["status"] == "fallback"
    assert binding["proposed_asset_id"] == "asset-portrait01"
    assert "rights scope" in binding["reason"]
    assert binding["asset"] is None
    # The slot layer still exists: it declares the region, paints nothing.
    assert _layer(graph, "media-player_portrait")["type"] == "media_slot"
    # Roles do not claim a library portrait.
    assert graph["roles"]["player_focus"]["portrait"]["kind"] == "monogram_fallback"


def test_builder_falls_back_for_non_image_or_unverified_assets():
    for info in (
        _asset_info(asset_type="video"),
        _asset_info(rights_state="pending"),
        _asset_info(lifecycle_state="retired"),
    ):
        graph = _build(media_asset_id="asset-portrait01", asset_info=info)
        binding = graph["media_bindings"][0]
        assert binding["status"] == "fallback"
        assert binding["asset"] is None
        assert binding["proposed_asset_id"] == "asset-portrait01"


def test_builder_falls_back_without_asset_record():
    graph = _build(media_asset_id="asset-missing", asset_info=None)
    binding = graph["media_bindings"][0]
    assert binding["status"] == "fallback"
    assert "unavailable" in binding["reason"]


@pytest.mark.parametrize("card_id", PORTRAIT_CARDS)
@pytest.mark.parametrize("mode", [
    "player_card", "player_poster", "player_poster_side",
    "player_poster_top", "potm_card",
])
def test_all_portrait_cards_freeze_a_valid_slot(card_id, mode):
    from apps.scene_graph.schema import validate_scene_graph

    graph = _build(card_id, mode)
    validate_scene_graph(graph)
    assert graph["kind"] == "starter"
    assert graph["media_bindings"][0]["slot_id"] == "player_portrait"
    assert graph["design"]["pages"][0]["children"][1]["id"] == "media-player_portrait"


# --- schema tamper rejection ------------------------------------------------


def test_schema_rejects_geometry_edit_after_freeze():
    graph = _unfrozen(_build(media_asset_id="asset-portrait01", asset_info=_asset_info()))
    graph["media_bindings"][0]["box_px"] = [0, 282, 424, 1200]
    with pytest.raises(ValueError, match="disagrees with frozen layer box"):
        from apps.scene_graph.schema import validate_scene_graph

        validate_scene_graph(graph)


def test_schema_rejects_pending_asset_marked_bound():
    graph = _unfrozen(_build(media_asset_id="asset-portrait01", asset_info=_asset_info()))
    graph["media_bindings"][0]["asset"]["approval_status"] = "pending"
    with pytest.raises(ValueError, match="must be approved"):
        from apps.scene_graph.schema import validate_scene_graph

        validate_scene_graph(graph)


def test_schema_rejects_fallback_carrying_an_asset():
    graph = _unfrozen(_build(media_asset_id="asset-missing", asset_info=None))
    graph["media_bindings"][0]["asset"] = {
        "asset_id": "asset-missing",
        "kind": "library_image",
        "rights_scope": "rights-scope-missing",
        "approval_status": "pending",
    }
    with pytest.raises(ValueError, match="fallback .* must not carry an asset"):
        from apps.scene_graph.schema import validate_scene_graph

        validate_scene_graph(graph)


def test_schema_rejects_slot_layer_without_binding():
    graph = _unfrozen(_build())
    graph["media_bindings"] = []
    with pytest.raises(ValueError, match="without a frozen binding"):
        from apps.scene_graph.schema import validate_scene_graph

        validate_scene_graph(graph)


def test_graph_hash_changes_with_binding_status():
    bound = _build(media_asset_id="asset-portrait01", asset_info=_asset_info())
    fallback = _build(media_asset_id="asset-portrait01")
    assert bound["provenance"]["graph_hash"] != fallback["provenance"]["graph_hash"]


# --- renderer paint + QA placement -----------------------------------------


def _portrait(path: Path) -> Path:
    image = Image.new("RGB", (600, 800), (180, 40, 40))
    draw = ImageDraw.Draw(image)
    draw.rectangle([80, 80, 520, 720], fill=(40, 40, 180))
    image.save(path)
    return path


def _payload(graph: dict, path: Path) -> dict:
    binding = graph["media_bindings"][0]
    return {
        "path": path,
        "fit": binding["fit"],
        "focal_point": binding["focal_point"],
        "mask": binding["mask"],
        "min_source_px": binding["min_source_px"],
    }


def test_render_design_paints_only_inside_the_slot(tmp_path):
    from apps.measurement.render_qa import check_media_placement
    from apps.studio_templates.render_starters import render_design

    graph = _build(media_asset_id="asset-portrait01", asset_info=_asset_info())
    photo = _portrait(tmp_path / "portrait.png")
    pack = render_design(graph["design"], texts=False)
    painted = render_design(
        graph["design"], texts=False,
        media={"player_portrait": _payload(graph, photo)},
    )

    # Outside the frozen box the render is byte-identical to pack-only.
    x, y, w, h = graph["media_bindings"][0]["box_px"]
    right = painted.crop((x + w, 0, painted.width, painted.height))
    right_pack = pack.crop((x + w, 0, pack.width, pack.height))
    assert right.tobytes() == right_pack.tobytes()
    assert painted.crop((0, 0, painted.width, y)).tobytes() == \
        pack.crop((0, 0, pack.width, y)).tobytes()

    report = check_media_placement(graph, painted, pack)
    assert report is not None and report["status"] == "PASS"
    assert "painted" in report["detail"]


def test_fallback_slot_paints_nothing_and_painting_it_fails_qa(tmp_path):
    from apps.measurement.render_qa import check_media_placement
    from apps.studio_templates.render_starters import render_design

    graph = _build(media_asset_id="asset-missing")
    photo = _portrait(tmp_path / "portrait.png")
    pack = render_design(graph["design"], texts=False)

    clean = check_media_placement(graph, pack, pack)
    assert clean is not None and clean["status"] == "PASS"

    wrong = render_design(
        graph["design"], texts=False,
        media={"player_portrait": _payload(graph, photo)},
    )
    report = check_media_placement(graph, wrong, pack)
    assert report is not None and report["status"] == "FAIL"
    assert "fallback must paint no media" in report["detail"]


def _seed_library_row(root: Path, asset_id: str = "asset-portrait01") -> Path:
    from apps.asset_library.registry import connect

    library = root / "runtime/assets/library"
    library.mkdir(parents=True, exist_ok=True)
    photo = _portrait(library / "portrait.png")
    conn = connect(root / "runtime" / "engine.db")
    try:
        conn.execute(
            "INSERT INTO assets (asset_id, original_name, stored_path, asset_type,"
            " size_bytes, sha256, source_type, source_url, creator, license_type,"
            " rights_state, lifecycle_state, metadata_json)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (asset_id, "portrait.png", "runtime/assets/library/portrait.png",
             "image", photo.stat().st_size, "cd" * 32, "wikimedia-commons",
             "https://commons.wikimedia.org/w/index.php?curid=2",
             "A Jean Genie", "CC BY 4.0", "verified", "active", "{}"),
        )
        conn.commit()
    finally:
        conn.close()
    return photo


def test_render_scene_png_paints_bound_slot_from_library(tmp_path):
    from apps.scene_graph.executor import render_scene_graph
    from apps.video_renderer import render_scene_png

    _seed_library_row(tmp_path)
    graph = _build(media_asset_id="asset-portrait01", asset_info=_asset_info())
    out = render_scene_png(graph, tmp_path / "scene.png", root=tmp_path)
    with Image.open(out) as opened:
        painted = opened.convert("RGB")
    pack = render_scene_graph(graph, texts=False, media={}).convert("RGB")

    x, y, w, h = graph["media_bindings"][0]["box_px"]
    center = (x + w // 2, y + h // 2)
    assert painted.getpixel(center) != pack.getpixel(center)


def test_render_scene_png_refuses_bound_slot_without_root(tmp_path):
    from apps.video_renderer import render_scene_png

    graph = _build(media_asset_id="asset-portrait01", asset_info=_asset_info())
    with pytest.raises(ValueError, match="library root"):
        render_scene_png(graph, tmp_path / "scene.png")


def test_render_scene_png_renders_fallback_without_root(tmp_path):
    from apps.video_renderer import render_scene_png

    graph = _build(media_asset_id="asset-missing")
    out = render_scene_png(graph, tmp_path / "scene.png")
    assert out.is_file()
