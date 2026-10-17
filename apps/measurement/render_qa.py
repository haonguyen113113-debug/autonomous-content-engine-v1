"""Render QA: verdicts on ACTUALLY rendered scenes, never on asset presence.

Boundary (workstream 4): the renderer only draws frozen Scene Graphs
(apps.scene_graph builder owns layout; executor owns Pillow primitives).
This module checks the rendered result — pixels + frozen geometry +
rights state — and returns PASS | FAIL | NEEDS_REVIEW with evidence.

Rules:
- PASS only when the check measured the real thing (rendered pixels,
  frozen layer geometry, verified DB rights state).
- FAIL when the render provably violates a gate (clip, safe-area,
  overlap, overfull narration, unverified/missing media).
- NEEDS_REVIEW whenever the check cannot evaluate reliably (no frozen
  layers, no background layer to sample, no narration, no registry,
  no role metadata). Never PASS on "asset exists".

No network, no clock, no randomness. Read-only (never writes runtime or
user data; a missing asset registry yields NEEDS_REVIEW, not a new DB).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

PASS = "PASS"
FAIL = "FAIL"
NEEDS_REVIEW = "NEEDS_REVIEW"

VERDICTS = (PASS, FAIL, NEEDS_REVIEW)


def readiness_verdict(report: dict[str, Any] | None) -> bool:
    """True only when the report's verdict is PASS.

    FAIL and NEEDS_REVIEW are both not-ready: a scene/clip must PASS every
    measured gate before it can be reported as ready.
    """
    return bool(report) and report.get("verdict") == PASS


# Conservative Vietnamese narration rate (words/second). Estimates below
# the beat window PASS; estimates clearly above it FAIL; the band between
# is NEEDS_REVIEW (speech rate varies by voice).
SPEECH_WPS = 2.6
NARRATION_FAIL_MARGIN = 1.15

# Text-box area over canvas area above which a frame reads as clutter.
DENSITY_FAIL = 0.40

# Mirrors apps/studio_templates/audit_cards.bbox_overlap gate.
OVERLAP_FAIL = 0.02

# Mirrors apps/studio_templates/check_starters.py: 7% sides, 9% top,
# 13% bottom; the credit slot (whisper, redundant with run provenance)
# is allowed down to 97% height. 1px tolerance.
_SIDE, _TOP, _BOTTOM, _CREDIT_BOTTOM = 0.07, 0.09, 0.87, 0.97
_TOL_PX = 1.0


def _check(criterion: str, status: str, detail: str) -> dict[str, Any]:
    assert status in VERDICTS, status
    return {"criterion": criterion, "status": status, "detail": detail}


def _validate(graph: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    try:
        from apps.scene_graph.schema import validate_scene_graph

        return validate_scene_graph(graph), None
    except Exception as error:  # invalid graphs never render; report, don't raise
        return None, str(error)[:300]


def visible_text_layers(graph: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Frozen, exported text layers, or None when the graph has no layers.

    Starter graphs carry absolute pixel boxes (measurable). Primitive
    graphs carry no frozen layers — callers must NEEDS_REVIEW geometry.
    """
    if not isinstance(graph, dict) or graph.get("kind") != "starter":
        return None
    design = graph.get("design")
    if not isinstance(design, dict):
        return None
    pages = design.get("pages")
    if not isinstance(pages, list) or len(pages) != 1:
        return None
    children = pages[0].get("children")
    if not isinstance(children, list):
        return None
    return [
        c for c in children
        if isinstance(c, dict) and c.get("type") == "text"
        and c.get("showInExport") is not False
    ]


def _layer_box(layer: dict[str, Any]) -> tuple[float, float, float, float]:
    return (float(layer.get("x", 0)), float(layer.get("y", 0)),
            float(layer.get("width", 0)), float(layer.get("height", 0)))


def _layer_id(layer: dict[str, Any]) -> str:
    slot = (layer.get("custom") or {}).get("slot") if isinstance(layer.get("custom"), dict) else None
    return str(slot or layer.get("id") or "?")


def _overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = min(ax + aw, bx + bw) - max(ax, bx)
    iy = min(ay + ah, by + bh) - max(ay, by)
    if ix <= 0 or iy <= 0:
        return 0.0
    denom = min(aw * ah, bw * bh)
    return (ix * iy) / denom if denom > 0 else 0.0


def _contrast(fg: tuple[float, float, float], bg: tuple[float, float, float]) -> float:
    def lum(rgb: tuple[float, float, float]) -> float:
        def ch(v: float) -> float:
            v /= 255.0
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

        r, g, b = (ch(v) for v in rgb)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    la, lb = lum(fg), lum(bg)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


def _hex_rgb(value: str) -> tuple[float, float, float]:
    value = str(value or "#F2F6FF").lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def check_media_rights(
    graph: dict[str, Any],
    root: Path | str | None,
    purpose: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Media rights on the REAL rights state — never on mere file presence.

    Two gates (workstream 1 contract):
    1. Library gate: the record must be rights-verified + active AND the
       file must exist inside runtime/assets/library. Anything else FAILs;
       an unreachable registry NEEDS_REVIEWs.
    2. Scope gate (``is_usable_for``): the asset must be allowed for the
       upload intent (platform/territory/commercial/monetization/edit +
       credit). Denials FAIL with reasons; an unknown intent NEEDS_REVIEWs
       instead of guessing.
    The planner's frozen ``approval_status`` is honored first: a ``pending``
    ref on media the scene paints FAILs (the planner did not clear it —
    the renderer must refuse it, see _scene_graph_media). Monogram
    fallbacks paint no image, so there is nothing to license (PASS).
    """

    def _painted_refs() -> tuple[list[dict[str, Any]], str | None]:
        """Refs this scene actually paints, or (refs, needs_review_reason)."""
        if not isinstance(graph, dict):
            return [], None
        if graph.get("kind") == "starter":
            return [], None  # frozen design pixels only; portraits unused
        params = graph.get("params") if isinstance(graph.get("params"), dict) else {}
        graphic = params.get("graphic_data") if isinstance(params, dict) else {}
        if isinstance(graphic, dict) and graphic.get("media_file"):
            return [], ("graphic_data carries an unfrozen media_file path "
                        "outside the asset contract — confirm provenance.")
        if str(graph.get("mode", "")) == "media_b_roll":
            refs = graph_asset_refs(graph)
            if not refs:
                return [], ("b-roll scene names no frozen asset — the planner "
                            "must freeze one; the renderer never picks media.")
            return refs, None
        return [], None

    name = "Media rights"
    refs, unpainted_note = _painted_refs()
    if unpainted_note is not None:
        return _check(name, NEEDS_REVIEW, unpainted_note)
    if not refs:
        slots: list[str] = []
        for layer in visible_text_layers(graph) or []:
            custom = layer.get("custom") if isinstance(layer.get("custom"), dict) else {}
            slot = custom.get("slot", "") if isinstance(custom, dict) else ""
            if isinstance(slot, str) and slot.startswith("crest-"):
                slots.append(slot)
        provenance = graph.get("provenance") if isinstance(graph.get("provenance"), dict) else {}
        unused = [r for r in graph_asset_refs(graph)]
        note = ""
        if unused:
            labelled = ", ".join(
                str(r["asset_id"]) + " (" + str(r["where"]) + ")" for r in unused)
            note = (" Cleared-but-unused ref(s) not painted by the frozen design: "
                    + labelled + ".")
        if slots and provenance.get("crest") != "monogram-fallback":
            return _check(name, NEEDS_REVIEW,
                          f"Crest slots {sorted(set(slots))} use a non-monogram mechanism "
                          "with no licensed-file evidence — confirm via "
                          "apps.sportskit.crests.resolve_crest before shipping." + note)
        if slots:
            return _check(name, PASS,
                          f"Crest slots {sorted(set(slots))} render monogram initials only "
                          "(provenance crest=monogram-fallback); no third-party crest "
                          "image is used, so no crest license is required." + note)
        return _check(name, PASS, "Scene paints no library media and no crest slots." + note)
    if root is None:
        return _check(name, NEEDS_REVIEW,
                      f"Scene paints {', '.join(r['asset_id'] for r in refs)} but no "
                      "library root was supplied — rights state unverifiable.")
    for ref in refs:
        if ref.get("approval_status") == "pending":
            return _check(name, FAIL,
                          f"Library asset {ref['asset_id']} ({ref['where']}) is frozen "
                          f"as approval_status=pending ({ref.get('rights_scope')}) — "
                          "the planner did not clear it and the renderer must "
                          "refuse it. Route to human rights review.")
        row, error = _registry_row(Path(root), ref["asset_id"])
        if error == "missing":
            return _check(name, NEEDS_REVIEW,
                          f"Scene paints {ref['asset_id']} but no asset registry "
                          "exists — rights state unverifiable.")
        if error == "absent":
            return _check(name, FAIL,
                          f"Library asset {ref['asset_id']} does not exist in the registry.")
        if error:
            return _check(name, NEEDS_REVIEW,
                          f"Asset registry unreadable for {ref['asset_id']}: "
                          f"{error} — rights state unverifiable.")
        assert row is not None
        if row.get("asset_type") != "image" or row.get("rights_state") != "verified" \
                or row.get("lifecycle_state") != "active":
            return _check(name, FAIL,
                          f"Library asset {ref['asset_id']} is {row.get('asset_type')}/"
                          f"{row.get('rights_state')}/{row.get('lifecycle_state')} — "
                          "only verified + active images may render.")
        library_root = (Path(root) / "runtime/assets/library").resolve()
        try:
            image_path = (Path(root) / str(row.get("stored_path") or "")).resolve()
        except Exception:
            return _check(name, FAIL,
                          f"Library asset {ref['asset_id']} has an unresolvable stored_path.")
        if library_root not in image_path.parents or not image_path.is_file():
            return _check(name, FAIL,
                          f"Library asset {ref['asset_id']} file is missing or outside "
                          "runtime/assets/library.")
        if purpose is None:
            return _check(name, NEEDS_REVIEW,
                          f"Library asset {ref['asset_id']} is verified + active with file "
                          "present, but the upload intent (platform/territory) is "
                          "unknown — the per-purpose scope check "
                          "(is_usable_for) cannot run without guessing.")
        try:
            from apps.asset_library.rights_scope import is_usable_for

            scope_out = is_usable_for(row, purpose)
        except Exception as error:
            return _check(name, NEEDS_REVIEW,
                          f"Scope check failed for {ref['asset_id']}: "
                          f"{str(error)[:140]} — cannot evaluate.")
        if not scope_out.get("allowed"):
            return _check(name, FAIL,
                          f"Library asset {ref['asset_id']} denied for this upload: "
                          f"{'; '.join(str(r) for r in scope_out.get('reasons', []))} "
                          f"(action: {scope_out.get('required_action')}).")
        credit = (scope_out.get("scope") or {}).get("credit") or {}
        credit_note = (f" Credit required, burn-in {credit.get('text')!r}."
                       if credit.get("required") else "")
        return _check(name, PASS,
                      f"Library asset {ref['asset_id']} verified + active, file present, "
                      f"scope-allowed ({'; '.join(str(r) for r in scope_out.get('reasons', []))}); "
                      f"attribution {row.get('creator') or '?'} · "
                      f"{row.get('license_type') or '?'}.{credit_note}")
    return _check(name, NEEDS_REVIEW, "No media refs collected — cannot evaluate.")


def qa_scene(
    graph: dict[str, Any],
    image: Any | None = None,
    *,
    bg_image: Any | None = None,
    narration: str | None = None,
    root: Path | str | None = None,
    purpose: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """QA one RENDERED scene STILL (rendered PNG): pixels + frozen geometry.

    This measures the rendered frame — frozen layer geometry, text clipping,
    safe area, overlap, density, contrast sampled on rendered background
    pixels, "text actually paints", narration fit, and media rights — on
    the actual rendered PNG. It does NOT claim the MP4 was QA'd: motion
    execution (punch/slide/fade), timing continuity and clip structure are
    clip-level concerns owned by qa_clip, and real motion still needs owner
    eyeball on the MP4. Stills verify geometry and mapping only.

    - graph: the validated Scene Graph that was executed.
    - image: the rendered Pillow image (RGB/RGBA) of this scene.
    - bg_image: background-only layer (executor render_scene_graph_layers);
      required for real contrast sampling and blank-text detection.
    - narration: beat narration text for the fit check.
    - root: repo root for the media-rights registry probe.
    - purpose: upload intent {platform, territory, ...} for the
      per-purpose scope check; None NEEDS_REVIEWs the scope gate.
    """
    checked, error = _validate(graph)
    if checked is None:
        return {"subject": str((graph or {}).get("segment_id", "?")),
                "verdict": FAIL,
                "checks": [_check("Scene graph contract", FAIL,
                                  f"Invalid scene graph — must not render: {error}")]}
    subject = str(checked.get("segment_id", "?"))
    canvas = checked.get("canvas", {})
    width, height = int(canvas.get("width", 0)), int(canvas.get("height", 0))
    layers = visible_text_layers(checked)
    checks: list[dict[str, Any]] = [_check(
        "Scene graph contract", PASS,
        f"version={checked.get('version')} mode={checked.get('mode')} "
        f"kind={checked.get('kind')} canvas={width}x{height}.")]

    if layers is None:
        checks.append(_check(
            "Text clipping (no-clip)", NEEDS_REVIEW,
            "Primitive graph carries no frozen layers — clipping cannot be "
            "measured; owner must eyeball the rendered frame."))
        checks.append(_check(
            "Safe area", NEEDS_REVIEW,
            "Primitive graph carries no frozen layers — safe-area cannot be "
            "measured; owner must eyeball the rendered frame."))
        checks.append(_check(
            "Text overlap", NEEDS_REVIEW,
            "Primitive graph carries no frozen layers — overlap cannot be "
            "measured; owner must eyeball the rendered frame."))
        checks.append(_check(
            "Visual density", NEEDS_REVIEW,
            "Primitive graph carries no frozen layers — density cannot be "
            "measured; owner must eyeball the rendered frame."))
    else:
        outside = [f"{_layer_id(t)}@{_layer_box(t)}" for t in layers
                   if (_layer_box(t)[0] < -_TOL_PX or _layer_box(t)[1] < -_TOL_PX
                       or _layer_box(t)[0] + _layer_box(t)[2] > width + _TOL_PX
                       or _layer_box(t)[1] + _layer_box(t)[3] > height + _TOL_PX)]
        checks.append(_check(
            "Text clipping (no-clip)",
            FAIL if outside else PASS,
            f"{len(outside)} text box(es) outside {width}x{height}: "
            f"{'; '.join(outside) or 'all boxes inside canvas'}."))
        unsafe: list[str] = []
        for layer in layers:
            x, y, w, h = _layer_box(layer)
            custom = layer.get("custom") if isinstance(layer.get("custom"), dict) else {}
            bottom = _CREDIT_BOTTOM if (isinstance(custom, dict)
                                        and custom.get("slot") == "credit") else _BOTTOM
            if x < width * _SIDE - _TOL_PX or x + w > width * (1 - _SIDE) + _TOL_PX \
                    or y < height * _TOP - _TOL_PX or y + h > height * bottom + _TOL_PX:
                unsafe.append(_layer_id(layer))
        checks.append(_check(
            "Safe area",
            FAIL if unsafe else PASS,
            f"Sides 7%, top 9%, bottom 13% (credit to 97%): "
            f"{'violators ' + ', '.join(sorted(set(unsafe))) if unsafe else 'all text inside'}."))
        clashes: list[str] = []
        for i in range(len(layers)):
            for j in range(i + 1, len(layers)):
                ratio = _overlap(_layer_box(layers[i]), _layer_box(layers[j]))
                if ratio > OVERLAP_FAIL:
                    clashes.append(f"{_layer_id(layers[i])} x {_layer_id(layers[j])}: {ratio:.0%}")
        checks.append(_check(
            "Text overlap",
            FAIL if clashes else PASS,
            f"Gate >2% of smaller box: {'; '.join(clashes) or 'no text-text overlap'}."))
        area = sum(_layer_box(t)[2] * _layer_box(t)[3] for t in layers)
        density = area / float(width * height) if width and height else 0.0
        checks.append(_check(
            "Visual density",
            FAIL if density > DENSITY_FAIL else PASS,
            f"Text boxes cover {density:.1%} of the frame "
            f"({'overcrowded' if density > DENSITY_FAIL else 'within budget'}; gate 40%)."))

    if bg_image is None or layers is None:
        if layers is not None:
            checks.append(_check(
                "Contrast (sampled)", NEEDS_REVIEW,
                "Background layer unavailable — contrast cannot be sampled from "
                "rendered pixels; owner must eyeball or re-run QA with bg_image."))
    else:
        try:
            bg = bg_image.convert("RGB")
            bw, bh = bg.size
            weak: list[str] = []
            for layer in layers:
                x, y, w, h = _layer_box(layer)
                cx = min(bw - 1, max(0, int(x + w / 2)))
                ratios = []
                for frac in (0.15, 0.5, 0.85):
                    py = min(bh - 1, max(0, int(y + h * frac)))
                    bg_px = bg.getpixel((cx, py))
                    fg = _hex_rgb(str(layer.get("fill", "#F2F6FF")))
                    ratios.append(_contrast(fg, tuple(float(v) for v in bg_px)))
                ratio = min(ratios)
                size = int(layer.get("fontSize", 0) or 0)
                floor = 4.5 if size >= 48 and float(layer.get("opacity", 1.0) or 1.0) >= 1.0 else 3.0
                if ratio < floor:
                    weak.append(f"{_layer_id(layer)}: {ratio:.2f} < {floor}")
            checks.append(_check(
                "Contrast (sampled)",
                FAIL if weak else PASS,
                f"Sampled on rendered background pixels (floors 4.5/3.0): "
                f"{'; '.join(weak) or 'all text passes'}."))
        except Exception as error:
            checks.append(_check(
                "Contrast (sampled)", NEEDS_REVIEW,
                f"Background sampling failed ({str(error)[:120]}) — cannot evaluate."))

    if image is not None and bg_image is not None and layers:
        try:
            fg_img = image.convert("RGB")
            bg_flat = bg_image.convert("RGB").resize(fg_img.size)
            from PIL import ImageChops, ImageStat

            blank: list[str] = []
            for layer in layers:
                x, y, w, h = _layer_box(layer)
                box = (int(x / width * fg_img.width), int(y / height * fg_img.height),
                       int((x + w) / width * fg_img.width), int((y + h) / height * fg_img.height))
                box = (max(0, box[0]), max(0, box[1]),
                       min(fg_img.width, box[2]), min(fg_img.height, box[3]))
                if box[2] <= box[0] or box[3] <= box[1]:
                    continue
                diff = ImageChops.difference(fg_img.crop(box), bg_flat.crop(box))
                if sum(ImageStat.Stat(diff).mean) < 1.5:
                    blank.append(_layer_id(layer))
            if blank:
                checks.append(_check(
                    "Text actually paints", FAIL,
                    f"These boxes are pixel-identical to the background "
                    f"(missing glyphs?): {', '.join(sorted(set(blank)))}."))
        except Exception as error:
            checks.append(_check(
                "Text actually paints", NEEDS_REVIEW,
                f"Pixel comparison failed ({str(error)[:120]}) — cannot evaluate."))

    if not (isinstance(narration, str) and narration.strip()):
        checks.append(_check(
            "Narration fit", NEEDS_REVIEW,
            "No narration attached to this beat — fit of voice to the visual "
            "window cannot be evaluated."))
    else:
        words = len(narration.split())
        window = float(checked["timing"]["end"]) - float(checked["timing"]["start"])
        estimate = words / SPEECH_WPS if window > 0 else float("inf")
        if estimate <= window:
            checks.append(_check(
                "Narration fit", PASS,
                f"~{words} words ≈ {estimate:.1f}s at {SPEECH_WPS} wps fits the "
                f"{window:.1f}s window; owner still audits delivery."))
        elif estimate > window * NARRATION_FAIL_MARGIN:
            checks.append(_check(
                "Narration fit", FAIL,
                f"~{words} words ≈ {estimate:.1f}s overflows the {window:.1f}s window "
                f"(>{NARRATION_FAIL_MARGIN}x) — shorten narration or widen the beat."))
        else:
            checks.append(_check(
                "Narration fit", NEEDS_REVIEW,
                f"~{words} words ≈ {estimate:.1f}s is tight against the {window:.1f}s "
                "window — speech rate varies by voice; confirm against the "
                "rendered voice preview."))

    checks.append(check_media_rights(checked, root, purpose))
    if checked.get("kind") == "primitive" and str(checked.get("mode", "")) == "tactical_explainer":
        checks.append(_check(
            "Tactical vectors", NEEDS_REVIEW,
            "Primitive tactical plate: pass/run/press vectors come from an "
            "unfrozen fallback storyboard, not the graph — verify the rendered "
            "diagram against the reviewed tactical data by eye."))

    verdict = FAIL if any(c["status"] == FAIL for c in checks) \
        else (NEEDS_REVIEW if any(c["status"] == NEEDS_REVIEW for c in checks) else PASS)
    return {"subject": subject, "verdict": verdict, "ready": verdict == PASS,
            "checks": checks}


def graph_asset_refs(graph: dict[str, Any]) -> list[dict[str, Any]]:
    """Every library-image reference a scene may paint, with its source.

    Collects the legacy ``params.media_asset_id`` shape plus the v1
    ``roles.hero_image`` / ``roles.player_focus.portrait`` asset refs
    (kind/rights_scope/approval_status frozen by the planner). Monogram
    fallbacks (no image) are excluded — there is nothing to license.
    """
    refs: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _take(asset_id: Any, where: str, ref: dict[str, Any] | None) -> None:
        if not isinstance(asset_id, str) or not asset_id.strip():
            return
        key = asset_id.strip()
        if key in seen:
            return
        seen.add(key)
        ref = ref if isinstance(ref, dict) else {}
        refs.append({
            "asset_id": key,
            "kind": str(ref.get("kind", "library_image")),
            "rights_scope": ref.get("rights_scope"),
            "approval_status": ref.get("approval_status"),
            "license_type": ref.get("license_type"),
            "where": where,
        })

    params = graph.get("params") if isinstance(graph.get("params"), dict) else {}
    roles = graph.get("roles") if isinstance(graph.get("roles"), dict) else {}
    # Roles first: they carry the planner's approval_status/rights_scope.
    # The legacy params.media_asset_id shape has no approval info and only
    # fills gaps (dedupe keeps the first, richest record per asset).
    if isinstance(roles, dict):
        hero = roles.get("hero_image")
        if isinstance(hero, dict) and hero.get("kind") == "library_image":
            _take(hero.get("asset_id"), "roles.hero_image", hero)
        focus = roles.get("player_focus")
        portrait = focus.get("portrait") if isinstance(focus, dict) else None
        if isinstance(portrait, dict) and portrait.get("kind") == "library_image":
            _take(portrait.get("asset_id"), "roles.player_focus.portrait", portrait)
    if isinstance(params, dict):
        _take(params.get("media_asset_id"), "params.media_asset_id", None)
    return refs


def _registry_row(root: Path, asset_id: str) -> tuple[dict[str, Any] | None, str | None]:
    """Read-only library row for an asset. (row, error).

    Never migrates or backfills the user DB (that chain belongs to another
    workstream): a missing ``rights_scope_json`` column simply yields a row
    without it, and scope checks fall back to the in-memory legacy
    derivation. A missing registry file returns (None, 'missing').
    """
    db = Path(root) / "runtime" / "engine.db"
    if not db.is_file():
        return None, "missing"
    try:
        from apps.asset_library.registry import connect

        conn = connect(db)
        try:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(assets)").fetchall()}
            wanted = ["asset_id", "stored_path", "asset_type", "rights_state",
                      "lifecycle_state", "source_url", "creator", "license_type",
                      "metadata_json"]
            for extra in ("rights_scope_json", "source_type", "copyright_exception"):
                if extra in columns:
                    wanted.append(extra)
            row = conn.execute(
                f"SELECT {', '.join(wanted)} FROM assets WHERE asset_id = ?",
                (asset_id,),
            ).fetchone()
        finally:
            conn.close()
    except Exception as error:
        return None, str(error)[:160]
    if row is None:
        return None, "absent"
    return ({key: row[key] for key in row.keys()}, "")


def qa_clip(
    graphs: list[dict[str, Any]],
    images: list[Any] | None = None,
    *,
    bg_images: list[Any] | None = None,
    narrations: dict[str, str] | list[str] | None = None,
    duration_target: float | None = None,
    roles: dict[str, str] | None = None,
    root: Path | str | None = None,
    purpose: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """QA a whole CLIP: per-scene checks plus timing continuity + structure.

    Clip-level QA: timing continuity is read from graph.timing (windows
    from 0, contiguous, no gaps/overlaps, optional duration target), every
    frozen enter/effect/transition is mapped onto an executed renderer
    primitive, and clip structure (hook/opening first, ending last) is
    checked against beat roles. Per-scene stills (qa_scene) feed the
    scene verdicts.

    What is NOT claimed here: actual motion (punch/slide/fade) is not
    measured from pixels — stills only verify the mapping; the owner must
    eyeball the rendered MP4 to confirm real motion. qa_scene covers the
    per-scene still (frozen geometry + pixels), it does not QA the MP4.

    - images / bg_images: rendered Pillow images aligned with graphs
      (may be shorter than graphs or None — missing frames NEEDS_REVIEW
      the pixel checks that need them, never PASS them).
    - narrations: {segment_id: narration} or [narration per beat].
    - roles: {segment_id: role}; without opening/ending role metadata the
      structure check NEEDS_REVIEWs instead of guessing from content.
    - purpose: upload intent for the per-purpose media scope gate.
    """
    graphs = list(graphs or [])
    images = list(images or [])
    bg_images = list(bg_images or [])

    def _narration(index: int, graph: dict[str, Any]) -> str | None:
        if isinstance(narrations, dict):
            value = narrations.get(str(graph.get("segment_id", "")))
            return str(value) if isinstance(value, str) else None
        if isinstance(narrations, (list, tuple)) and index < len(narrations):
            value = narrations[index]
            return str(value) if isinstance(value, str) else None
        return None

    scenes = [qa_scene(graph, images[i] if i < len(images) else None,
                       bg_image=bg_images[i] if i < len(bg_images) else None,
                       narration=_narration(i, graph), root=root, purpose=purpose)
              for i, graph in enumerate(graphs)]
    checks: list[dict[str, Any]] = []

    motion_map: list[str] = []
    unmapped: list[str] = []
    for graph in graphs:
        if not isinstance(graph, dict):
            continue
        sid = str(graph.get("segment_id", "?"))
        motion = graph.get("motion") if isinstance(graph.get("motion"), dict) else {}
        transition = graph.get("transition") if isinstance(graph.get("transition"), dict) else {}
        enter, effect = motion.get("enter"), motion.get("effect", "none")
        trans_in = transition.get("in")
        # Renderer-side execution table (video_renderer Scene Graph path):
        # hook_punch_in -> fast punch zoom; slide_in_right_0_3s -> standard
        # 0.3s slide-in; fade_0_3s -> fade in/out; number_pop -> punch zoom
        # on the frozen numerals (no re-layout); chalk_line_wipe -> 0.3s
        # slide-in; clean_cut -> hard cut (slide suppressed).
        if enter == "hook_punch_in":
            motion_map.append(f"{sid}: hook_punch_in->punch-in")
        elif enter == "slide_in_right_0_3s":
            motion_map.append(f"{sid}: slide_in_right_0_3s->slide-in")
        elif enter == "fade_0_3s":
            motion_map.append(f"{sid}: fade_0_3s->fade-in/out")
        else:
            unmapped.append(f"{sid}: motion.enter={enter!r} has no renderer primitive")
        if effect == "number_pop":
            motion_map.append(f"{sid}: number_pop->punch-in (frozen numerals)")
        elif effect not in (None, "none"):
            unmapped.append(f"{sid}: motion.effect={effect!r} not executed")
        if trans_in not in ("clean_cut", "chalk_line_wipe"):
            unmapped.append(f"{sid}: transition.in={trans_in!r} unknown")
    if unmapped:
        checks.append(_check(
            "Motion execution mapping", NEEDS_REVIEW,
            "Unmapped frozen motion — the renderer cannot execute it without "
            "inventing layout; confirm on the rendered video: "
            + "; ".join(unmapped)))
    else:
        checks.append(_check(
            "Motion execution mapping", PASS,
            "Every frozen enter/effect/transition maps onto an executed "
            "primitive (mapping verified on stills; motion itself needs "
            "video eyeball): " + "; ".join(motion_map) + "."))

    valid = [g for g in graphs if isinstance(g, dict)
             and isinstance(g.get("timing"), dict)]
    try:
        windows = sorted((float(g["timing"]["start"]), float(g["timing"]["end"]),
                          str(g.get("segment_id", "?"))) for g in valid)
    except (TypeError, ValueError):
        windows = []
    if not windows:
        checks.append(_check("Timing continuity", FAIL, "No usable beat timings."))
    else:
        problems: list[str] = []
        if windows[0][0] > 0.05:
            problems.append(f"clip starts at {windows[0][0]:.2f}s, not 0")
        for (s1, e1, sid1), (s2, e2, sid2) in zip(windows, windows[1:]):
            if s2 > e1 + 0.05:
                problems.append(f"gap {e1:.2f}s->{s2:.2f}s ({sid1}->{sid2})")
            elif s2 < e1 - 0.05:
                problems.append(f"overlap {sid1}/{sid2} by {e1 - s2:.2f}s")
            if not e1 > s1:
                problems.append(f"{sid1} has non-positive duration")
        if windows and not windows[-1][1] > windows[-1][0]:
            problems.append(f"{windows[-1][2]} has non-positive duration")
        total = windows[-1][1] if windows else 0.0
        detail = (f"{len(windows)} beat(s), total {total:.2f}s"
                  + (f"; target {duration_target:.0f}s" if duration_target else "")
                  + (f": {'; '.join(problems)}" if problems else
                     "; contiguous from 0, no gaps/overlaps."))
        if duration_target and abs(total - duration_target) > max(1.0, duration_target * 0.01):
            problems.append(f"total {total:.2f}s vs target {duration_target:.0f}s")
        checks.append(_check("Timing continuity", FAIL if problems else PASS, detail))

    if not isinstance(roles, dict) or not roles:
        checks.append(_check(
            "Video structure", NEEDS_REVIEW,
            "No beat-role metadata (opening/body/ending) — order and rhythm "
            "cannot be verified from pixels alone; owner must eyeball the cut."))
    else:
        first, last = windows[0][2] if windows else "?", windows[-1][2] if windows else "?"
        first_role = str(roles.get(first, "")).lower()
        last_role = str(roles.get(last, "")).lower()
        ok_open = any(k in first_role for k in ("hook", "open", "cover"))
        ok_end = any(k in last_role for k in ("end", "takeaway", "clos"))
        if ok_open and ok_end:
            checks.append(_check(
                "Video structure", PASS,
                f"Opens on {first} ({first_role}), closes on {last} ({last_role})."))
        else:
            checks.append(_check(
                "Video structure", FAIL,
                f"Opens on {first} ({first_role or 'unlabelled'}), closes on {last} "
                f"({last_role or 'unlabelled'}) — expected a hook/opening first "
                "and an ending/takeaway last."))

    scene_verdicts = [s["verdict"] for s in scenes]
    bad = FAIL in scene_verdicts or any(c["status"] == FAIL for c in checks)
    unsure = (NEEDS_REVIEW in scene_verdicts
              or any(c["status"] == NEEDS_REVIEW for c in checks))
    verdict = FAIL if bad else (NEEDS_REVIEW if unsure else PASS)
    return {"subject": "clip", "verdict": verdict, "ready": verdict == PASS,
            "scenes": scenes, "clip_checks": checks,
            "checks": checks + [c for s in scenes for c in s["checks"]]}


__all__ = [
    "PASS", "FAIL", "NEEDS_REVIEW", "VERDICTS",
    "SPEECH_WPS", "DENSITY_FAIL", "OVERLAP_FAIL",
    "check_media_rights", "graph_asset_refs", "qa_clip", "qa_scene",
    "readiness_verdict", "visible_text_layers",
]
