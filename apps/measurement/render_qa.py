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

import re
from pathlib import Path
from typing import Any

PASS = "PASS"
FAIL = "FAIL"
NEEDS_REVIEW = "NEEDS_REVIEW"

VERDICTS = (PASS, FAIL, NEEDS_REVIEW)

# C-09 attribution is graph-level executable in 12.1.0. The owner's static
# visual review is no longer a hard-coded flag: it lives in a scoped review
# record under docs/coordinator/review_records/ and is consulted only when
# card, mode AND pack version all match. The record approves the visual
# inspection of the C-09 static PNG only; it does not verify the claim,
# source/date, asset rights, motion, other cards/modes, other pack versions,
# or production readiness by itself.
from apps.measurement.review_records import source_card_visual_approved


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
            # Only bound media_bindings paint; fallback entries leave the
            # authored pack artwork and need no licence. Unused role refs
            # (cleared-but-not-painted) are reported by the empty-ref path.
            return [
                ref for ref in graph_asset_refs(graph)
                if str(ref.get("where", "")).startswith("media_bindings[")
            ], None
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
        fallbacks = [
            str(binding.get("slot_id"))
            for binding in (graph.get("media_bindings") or [])
            if isinstance(binding, dict) and binding.get("status") == "fallback"
        ]
        if fallbacks:
            note += (
                " Media slot fallback(s) " + ", ".join(sorted(fallbacks))
                + " keep the authored pack artwork; no library image is painted."
            )
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


def _overlay_rendered_check(graph: dict[str, Any]) -> dict[str, Any]:
    """Overlay rendered check on the RAW graph (lenient, never raises).

    Free-standing text overlays have no template-slot binding and are not
    rendered. A graph that declares one therefore fails this production gate.
    """
    if not isinstance(graph, dict):
        return _check("Overlay rendered", NEEDS_REVIEW,
                      "Graph is not an object — overlay cannot be checked.")
    overlays = graph.get("overlays")
    if overlays is None:
        return _check("Overlay rendered", PASS,
                      "No overlay declared in the graph — nothing to render.")
    if not isinstance(overlays, list):
        return _check("Overlay rendered", FAIL,
                      "Graph declares overlays but the value is not a list.")
    if not overlays:
        return _check("Overlay rendered", PASS,
                      "Overlay list is empty — nothing to render.")
    timing = graph.get("timing")
    t_start = t_end = None
    if isinstance(timing, dict):
        try:
            t_start = float(timing.get("start"))
            t_end = float(timing.get("end"))
        except (TypeError, ValueError):
            t_start = t_end = None
    duration = (t_end - t_start) if (t_start is not None and t_end is not None) else None
    problems: list[str] = []
    for index, item in enumerate(overlays):
        prefix = f"overlays[{index}]"
        if not isinstance(item, dict):
            problems.append(f"{prefix} is not an object")
            continue
        otype = item.get("type")
        if otype not in ("lower_third", "caption"):
            problems.append(f"{prefix} type={otype!r} is not lower_third/caption")
            continue
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            problems.append(f"{prefix} missing non-empty text")
            continue
        try:
            start = float(item.get("start_seconds"))
            end = float(item.get("end_seconds"))
        except (TypeError, ValueError):
            problems.append(f"{prefix} timing is not numeric")
            continue
        if not end > start:
            problems.append(f"{prefix} end_seconds <= start_seconds")
            continue
        if duration is not None and start > duration:
            problems.append(f"{prefix} starts after the beat window "
                            f"({start} > {duration})")
            continue
        if duration is not None and end > duration:
            problems.append(f"{prefix} ends after the beat window "
                            f"({end} > {duration})")
            continue
    if problems:
        return _check("Overlay rendered", FAIL, "; ".join(problems))
    return _check(
        "Overlay rendered", FAIL,
        "Free-standing text overlays are not rendered: no frozen template-slot binding exists. "
        "Move the copy into a supported card slot before rendering.",
    )


def _max_channel_difference(left: Any, right: Any) -> Any:
    """Per-pixel max RGB difference as an L image (0-255)."""
    from PIL import ImageChops

    diff = ImageChops.difference(left.convert("RGB"), right.convert("RGB"))
    red, green, blue = diff.split()
    return ImageChops.lighter(ImageChops.lighter(red, green), blue)


def _changed_pixels(diff_map: Any, box: tuple[int, int, int, int] | None = None,
                    threshold: int = 2) -> int:
    """Count pixels whose max channel difference exceeds ``threshold``."""
    target = diff_map.crop(box) if box is not None else diff_map
    histogram = target.histogram()
    return sum(count for value, count in enumerate(histogram) if value > threshold)


def check_media_placement(
    graph: dict[str, Any],
    painted: Any | None,
    pack_only: Any | None,
) -> dict[str, Any] | None:
    """Verify media paint against the pack-only baseline (rendered pixels).

    - A ``bound`` slot must change at least ``qa.min_painted_fraction`` of
      its authored box and must not change more than
      ``qa.max_outside_leak_pixels`` outside it.
    - A ``fallback`` slot must be pixel-identical to the pack-only render
      inside AND outside its box: the renderer paints no substitute media.

    ``painted`` is the background layer (texts=False) that includes any
    gated media; ``pack_only`` is the same layer rendered with ``media={}``.
    Without the baseline this returns NEEDS_REVIEW instead of guessing.
    """
    if not isinstance(graph, dict) or graph.get("kind") != "starter":
        return None
    bindings = graph.get("media_bindings")
    if not isinstance(bindings, list) or not bindings:
        return None
    name = "Media placement"
    if painted is None:
        return _check(
            name, NEEDS_REVIEW,
            "Scene declares media bindings but no rendered background layer "
            "was supplied — placement cannot be measured.",
        )
    if pack_only is None:
        return _check(
            name, NEEDS_REVIEW,
            "Pack-only baseline missing — paint/leak cannot be distinguished "
            "from authored artwork.",
        )
    try:
        from PIL import Image, ImageChops, ImageDraw

        painted_rgb = painted.convert("RGB")
        pack_rgb = pack_only.convert("RGB")
        if painted_rgb.size != pack_rgb.size:
            return _check(
                name, NEEDS_REVIEW,
                f"Rendered size {painted_rgb.size} differs from pack baseline "
                f"{pack_rgb.size}; placement unverifiable.",
            )
        diff_map = _max_channel_difference(painted_rgb, pack_rgb)
        failures: list[str] = []
        evidence: list[str] = []
        for binding in bindings:
            if not isinstance(binding, dict):
                continue
            slot_id = str(binding.get("slot_id", "?"))
            box = binding.get("box_px")
            if not isinstance(box, list) or len(box) != 4:
                failures.append(f"{slot_id}: invalid frozen box_px")
                continue
            x, y, w, h = (int(value) for value in box)
            if w <= 0 or h <= 0:
                failures.append(f"{slot_id}: empty frozen box_px")
                continue
            area = w * h
            inside = _changed_pixels(diff_map, (x, y, x + w, y + h))
            mask = Image.new("L", painted_rgb.size, 255)
            ImageDraw.Draw(mask).rectangle([x, y, x + w - 1, y + h - 1], fill=0)
            outside = _changed_pixels(ImageChops.multiply(diff_map, mask))
            qa = binding.get("qa") if isinstance(binding.get("qa"), dict) else {}
            status = binding.get("status")
            if status == "bound":
                minimum = float(qa.get("min_painted_fraction", 0.0))
                leak_limit = int(qa.get("max_outside_leak_pixels", 0))
                fraction = inside / area if area else 0.0
                if fraction < minimum:
                    failures.append(
                        f"{slot_id}: painted {fraction:.1%} of its box < "
                        f"{minimum:.1%} (asset may be blank or mis-sized)"
                    )
                else:
                    evidence.append(f"{slot_id} painted {fraction:.1%}")
                if outside > leak_limit:
                    failures.append(
                        f"{slot_id}: {outside} changed pixel(s) outside the "
                        f"frozen box > {leak_limit}"
                    )
                else:
                    evidence.append(f"{slot_id} leak {outside}px")
            elif status == "fallback":
                if inside or outside:
                    failures.append(
                        f"{slot_id}: fallback must paint no media but "
                        f"{inside} inside / {outside} outside pixel(s) changed"
                    )
                else:
                    evidence.append(f"{slot_id} fallback left pack artwork intact")
        if failures:
            return _check(name, FAIL, "; ".join(failures))
        return _check(
            name, PASS,
            "Measured against the pack-only render: " + "; ".join(evidence) + ".",
        )
    except Exception as error:
        return _check(
            name, NEEDS_REVIEW,
            f"Pixel comparison failed ({str(error)[:120]}) — cannot evaluate.",
        )


def check_card_contract(graph: dict[str, Any]) -> dict[str, Any]:
    """Report whether the rendered card actually executed its contract.

    A legacy/fallback/contract-less graph is never a PASS: it may render, but
    it is not covered by the authored card contract and must not be published
    as contract-ready. The check reads the frozen provenance and the current
    contract; it never trusts an asset id or a route name alone.
    """
    provenance = graph.get("provenance") if isinstance(graph.get("provenance"), dict) else {}
    meta = provenance.get("card_contract") if isinstance(provenance, dict) else None
    starter_id = graph.get("starter_id")
    if meta is None:
        if graph.get("kind") == "starter" or starter_id:
            return _check(
                "Card contract", NEEDS_REVIEW,
                "Graph has no card-contract provenance: it used a legacy path "
                "or predates contract v2.0. Rebuild with the planner; do not "
                "treat this render as contract-ready.")
        return _check(
            "Card contract", NEEDS_REVIEW,
            "Primitive graph has no authored card contract: it was rendered "
            "by the legacy generic path, not a contract-executable card. "
            "Inspect it, but do not treat it as contract-ready.")
    if not isinstance(meta, dict):
        return _check(
            "Card contract", FAIL,
            "provenance.card_contract is not an object.")
    status = meta.get("status")
    card_id = str(meta.get("card_id") or starter_id or "?")
    version = str(meta.get("template_version") or provenance.get("template_version") or "")
    reason = str(meta.get("reason") or "").strip()
    if status == "contract":
        from apps.studio_templates.card_media import card_contract

        record = card_contract(starter_id, version)
        if record is None:
            return _check(
                "Card contract", FAIL,
                f"Contract status names {card_id}, but no record exists in "
                f"card-contract {version}.")
        if str(meta.get("sha256")) != record["contract_hash"]:
            return _check(
                "Card contract", FAIL,
                f"{card_id} was frozen against a different contract hash "
                f"({str(meta.get('sha256'))[:12]}… vs "
                f"{record['contract_hash'][:12]}…). Rebuild the graph.")
        if str(meta.get("starter_sha256")) != record["starter_sha256"]:
            return _check(
                "Card contract", FAIL,
                f"{card_id} was frozen against a different authored starter.")
        if graph.get("kind") != "starter":
            return _check(
                "Card contract", FAIL,
                f"{card_id} claims contract execution but rendered a primitive "
                "graph.")
        if graph.get("fallback"):
            return _check(
                "Card contract", FAIL,
                f"{card_id} claims contract execution but carries fallback "
                f"reason: {graph.get('fallback')}.")
        mode = str(graph.get("mode"))
        if mode not in record["execution"]["modes"]:
            return _check(
                "Card contract", FAIL,
                f"{card_id}/{mode} is not contract-executable per the record.")
        bindings = graph.get("data_bindings")
        if not isinstance(bindings, list):
            return _check(
                "Card contract", FAIL,
                f"{card_id} has no frozen data_bindings; text was not "
                "contract-resolved.")
        visible = [b for b in bindings if isinstance(b, dict) and b.get("visible")]
        required_missing = [
            str(b.get("slot_id")) for b in bindings
            if isinstance(b, dict) and b.get("required") and not b.get("visible")
        ]
        if required_missing:
            return _check(
                "Card contract", FAIL,
                f"{card_id} left required data slots empty: "
                f"{', '.join(sorted(required_missing))}.")
        media_slots = record.get("media_slots") or []
        media_bindings = graph.get("media_bindings") if isinstance(
            graph.get("media_bindings"), list) else []
        bound_media = [b for b in media_bindings if isinstance(b, dict)
                       and b.get("status") == "bound"]
        if mode == "source_card":
            by_slot = {
                str(binding.get("slot_id")): binding
                for binding in bindings if isinstance(binding, dict)
            }
            body = by_slot.get("src-body")
            credit = by_slot.get("credit")
            if not body or not body.get("visible") or body.get("sources") != ["claim"]:
                return _check(
                    "Card contract", FAIL,
                    f"{card_id}/source_card must bind only the reviewed claim "
                    "to src-body and keep it visible.")
            credit_slot = next(
                (slot for slot in record["data_slots"]
                 if slot["slot_id"] == "credit"), None)
            credit_join = str((credit_slot or {}).get("join") or "")
            credit_value = str(credit.get("value") or "").strip() if credit else ""
            credit_parts = (
                credit_value.split(credit_join, 1)
                if credit_join and credit_value else [credit_value]
            )
            if (not credit or not credit.get("visible")
                    or credit.get("sources") != ["source", "date"]
                    or not credit_value
                    or len(credit_parts) != 2
                    or not all(part.strip() for part in credit_parts)):
                return _check(
                    "Card contract", FAIL,
                    f"{card_id}/source_card must render a visible credit line "
                    "with both source and date; missing or partial attribution "
                    "is not contract-ready.")
            review_pending = not source_card_visual_approved(
                card_id, mode, version
            )
            if review_pending:
                return _check(
                    "Card contract", NEEDS_REVIEW,
                    f"{card_id}/source_card executed contract {version} "
                    f"sha256={record['contract_hash'][:12]}… with visible "
                    "claim and source+date credit. Rendered frame inspection "
                    "and owner visual approval are still pending, so this is "
                    "not a visual PASS.")
            return _check(
                "Card contract", PASS,
                f"{card_id}/source_card executed contract {version} "
                f"sha256={record['contract_hash'][:12]}… with visible claim "
                "and source+date credit; rendered inspection and owner "
                "approval recorded.")
        return _check(
            "Card contract", PASS,
            f"{card_id}/{mode} executed contract {version} "
            f"sha256={record['contract_hash'][:12]}…; "
            f"{len(visible)} visible data binding(s), "
            f"{len(bound_media)}/{len(media_slots)} media slot(s) bound; "
            "required slots visible.")
    if status == "fallback":
        return _check(
            "Card contract", NEEDS_REVIEW,
            f"{card_id} rendered a declared fallback primitive instead of the "
            f"authored card: {reason or 'no reason recorded'}. Fallback is not "
            "contract-ready; fix the data or choose another card.")
    if status == "legacy_non_ready":
        return _check(
            "Card contract", NEEDS_REVIEW,
            f"{card_id} mode {graph.get('mode')!r} is legacy/non-ready: "
            f"{reason or 'not covered by the executable contract'}. This render "
            "must not pass as contract-ready.")
    if status in ("missing_contract_record", "no_contract"):
        return _check(
            "Card contract", NEEDS_REVIEW,
            f"{card_id} has no executable card contract "
            f"({status}): {reason or 'legacy path'}. Rebuild from the pinned "
            "Template Foundation before publishing.")
    return _check(
        "Card contract", FAIL,
        f"Unknown card-contract status {status!r} on {card_id}.")


def _plain_text(value: str) -> str:
    return re.sub(r"\*([^*]+)\*", r"\1", str(value))


def _display_lines(text: str) -> list[str]:
    """Lines the authored renderer actually draws: explicit newlines only.

    The renderer does not word-wrap: a long single line overflows
    horizontally rather than reflowing. Measuring a greedy wrap here would
    hide that failure.
    """
    return str(text).split("\n")


def _measure_text(
    text: str,
    *,
    family: str,
    weight: str,
    size: int,
    box_w: float,
    box_h: float,
) -> tuple[list[str], int, list[str]]:
    """Measure text against its frozen box using the renderer's line rules.

    Returns ``(overflow_reasons, line_count, limit_reasons)``. Metrics come
    from the same locked font the renderer uses; multiline step matches
    ``render_starters`` (``fontSize * 1.25``).
    """
    from apps.studio_templates.render_starters import font_for

    font = font_for(str(family), str(weight), int(size))
    lines = _display_lines(_plain_text(text))
    overflow: list[str] = []
    widest = 0.0
    for line in lines:
        bbox = font.getbbox(line)
        widest = max(widest, float(bbox[2] - bbox[0]))
    if widest > box_w + 2.0:
        overflow.append(f"width {widest:.0f}>{box_w:.0f}px")
    step = int(int(size) * 1.25)
    ink_bottom = 0.0
    for index, line in enumerate(lines):
        bbox = font.getbbox(line)
        ink_bottom = max(ink_bottom, index * step + float(bbox[3]))
    # The authored box is a layout rectangle, not a clip: fonts commonly
    # overshoot it by their ascender/descender gap. Allow one quarter of the
    # drawn size, then fail a genuine vertical overflow (e.g. extra lines).
    allowance = float(size) * 0.25
    if ink_bottom > box_h + allowance + 2.0:
        overflow.append(
            f"height {ink_bottom:.0f}>{box_h:.0f}px "
            f"(+{allowance:.0f}px font allowance)")
    return overflow, len(lines), []


def fit_text_size(slot: dict[str, Any], value: str) -> int:
    """Return the font size the planner/builder will freeze for this slot.

    Mirrors ``builder._shrink_to_fit``: step down by 2px to the contract's
    floor, never word-wrap. Keeping the calculation here lets planner
    readiness and rendered QA use the same measurement.
    """
    from apps.studio_templates.render_starters import font_for

    size = int(slot["font"]["size_px"])
    floor = max(20, size // 2)
    width = float(slot["box_px"][2])
    while size > floor:
        try:
            font = font_for(
                str(slot["font"]["family"]),
                str(slot["font"]["weight"]),
                size,
            )
            box = font.getbbox(str(value))
        except Exception:
            break
        if float(box[2] - box[0]) <= width + 2.0:
            break
        size -= 2
    return size


def measure_text_slot(
    slot: dict[str, Any],
    value: str,
    *,
    size: int | None = None,
) -> dict[str, Any]:
    """Measure one frozen/planned value against its contract slot.

    Returns a deterministic status plus the evidence. ``size`` is the already
    frozen draw size in graph QA; when omitted, the planner fit size is used.
    This measures the value at the size that will actually be drawn, not the
    intended asset/card path.
    """
    draw_size = int(size if size is not None else fit_text_size(slot, value))
    _x, _y, width, height = (float(item) for item in slot["box_px"])
    overflow, line_count, _limits = _measure_text(
        str(value),
        family=str(slot["font"]["family"]),
        weight=str(slot["font"]["weight"]),
        size=draw_size,
        box_w=width,
        box_h=height,
    )
    plain = _plain_text(str(value))
    limit_hits: list[str] = []
    if len(plain) > int(slot["max_chars"]):
        limit_hits.append(f"{len(plain)}>{slot['max_chars']} chars")
    if len(plain.split()) > int(slot["max_words"]):
        limit_hits.append(f"{len(plain.split())}>{slot['max_words']} words")
    if line_count > int(slot["max_lines"]):
        limit_hits.append(f"{line_count}>{slot['max_lines']} lines")
    status = FAIL if overflow else (NEEDS_REVIEW if limit_hits else PASS)
    return {
        "slot_id": str(slot["slot_id"]),
        "status": status,
        "size_px": draw_size,
        "line_count": line_count,
        "overflow": overflow,
        "limit_hits": limit_hits,
    }


def check_text_fit(graph: dict[str, Any]) -> dict[str, Any] | None:
    """Measure frozen text at its frozen font size against its contract box.

    This catches the failure the shrink-to-fit step cannot: a value that
    overflows its authored box, or one that exceeds the semantic
    length/line limits the contract declares. It measures the frozen text
    and geometry, not the intended asset path.
    """
    provenance = graph.get("provenance") if isinstance(graph.get("provenance"), dict) else {}
    meta = provenance.get("card_contract") if isinstance(provenance, dict) else None
    if not isinstance(meta, dict) or meta.get("status") != "contract":
        return None
    from apps.studio_templates.card_media import card_contract

    record = card_contract(graph.get("starter_id"), meta.get("template_version"))
    if record is None or graph.get("kind") != "starter":
        return _check(
            "Text fit (contract)", NEEDS_REVIEW,
            "Cannot load the card contract/starter to measure text fit.")
    design = graph.get("design") if isinstance(graph.get("design"), dict) else {}
    pages = design.get("pages") if isinstance(design.get("pages"), list) else []
    children = pages[0].get("children") if pages and isinstance(pages[0], dict) else []
    by_layer = {
        str(child.get("id")): child for child in children
        if isinstance(child, dict) and child.get("type") == "text"
    }
    bindings = {
        str(binding.get("slot_id")): binding
        for binding in (graph.get("data_bindings") or [])
        if isinstance(binding, dict)
    }
    overflowed: list[str] = []
    over_limit: list[str] = []
    measured = 0
    try:
        for slot in record["data_slots"]:
            binding = bindings.get(str(slot["slot_id"]))
            if not binding or not binding.get("visible"):
                continue
            layer = by_layer.get(str(slot["layer_id"]))
            if layer is None:
                over_limit.append(f"{slot['slot_id']}: missing frozen text layer")
                continue
            size = int(layer.get("fontSize", slot["font"]["size_px"]))
            result = measure_text_slot(slot, str(binding["value"]), size=size)
            measured += 1
            if result["overflow"]:
                overflowed.append(
                    f"{slot['slot_id']} ({'; '.join(result['overflow'])})"
                )
            if result["limit_hits"]:
                over_limit.append(
                    f"{slot['slot_id']} ({', '.join(result['limit_hits'])})"
                )
        for static in record.get("static_text_layers") or []:
            layer = by_layer.get(str(static["layer_id"]))
            if layer is None:
                over_limit.append(f"{static['layer_id']}: missing static text layer")
                continue
            size = int(layer.get("fontSize", static["font"]["size_px"]))
            x, y, w, h = (float(value) for value in static["box_px"])
            _ = (x, y)
            overflow, _line_count, _limits = _measure_text(
                str(static["text"]),
                family=str(static["font"]["family"]),
                weight=str(static["font"]["weight"]),
                size=size,
                box_w=w,
                box_h=h,
            )
            measured += 1
            if overflow:
                overflowed.append(f"{static['layer_id']} ({'; '.join(overflow)})")
    except Exception as error:  # font install/metrics failure is not a PASS
        return _check(
            "Text fit (contract)", NEEDS_REVIEW,
            f"Text metrics could not be measured ({str(error)[:140]}); owner "
            "must inspect the rendered frame.")
    if overflowed:
        return _check(
            "Text fit (contract)", FAIL,
            f"{len(overflowed)} frozen text box(es) overflow at the drawn font "
            f"size: {'; '.join(overflowed[:4])}"
            f"{' …' if len(overflowed) > 4 else ''}.")
    if over_limit:
        return _check(
            "Text fit (contract)", NEEDS_REVIEW,
            f"Text fits its box but exceeds declared contract limits: "
            f"{'; '.join(over_limit[:4])}"
            f"{' …' if len(over_limit) > 4 else ''}. Shrink-to-fit is not "
            "editorial approval; shorten the copy or use another card.")
    return _check(
        "Text fit (contract)", PASS,
        f"Measured {measured} frozen text layer(s) against their authored "
        "boxes at the drawn font size; all fit within limits.")


def qa_scene(
    graph: dict[str, Any],
    image: Any | None = None,
    *,
    bg_image: Any | None = None,
    pack_image: Any | None = None,
    narration: str | None = None,
    root: Path | str | None = None,
    purpose: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """QA one RENDERED scene STILL (rendered PNG): pixels + frozen geometry.

    This measures the rendered frame — frozen layer geometry, text clipping,
    safe area, overlap, density, contrast sampled on rendered background
    pixels, "text actually paints", media placement, narration fit, and
    media rights — on the actual rendered PNG. It does NOT claim the MP4
    was QA'd: motion execution (punch/slide/fade), timing continuity and
    clip structure are clip-level concerns owned by qa_clip, and real
    motion still needs owner eyeball on the MP4. Stills verify geometry and
    mapping only.

    - graph: the validated Scene Graph that was executed.
    - image: the rendered Pillow image (RGB/RGBA) of this scene.
    - bg_image: background-only layer (executor render_scene_graph_layers);
      required for real contrast sampling and blank-text detection.
    - pack_image: the same background layer rendered with ``media={}``;
      required to prove frozen media painted inside its slot and nowhere
      else (and that fallback slots painted nothing).
    - narration: beat narration text for the fit check.
    - root: repo root for the media-rights registry probe.
    - purpose: upload intent {platform, territory, ...} for the
      per-purpose scope check; None NEEDS_REVIEWs the scope gate.
    """
    checked, error = _validate(graph)
    subject = str((graph or {}).get("segment_id", "?"))
    # Overlay check on the raw graph (lenient, never raises): surfaces a bad
    # overlay timing/content as "Overlay rendered" even when the core gate
    # already rejects the graph. Never PASSes on mere presence in input.
    overlay_check = _overlay_rendered_check(graph)
    if checked is None:
        return {"subject": subject, "verdict": FAIL, "ready": False,
                "checks": [_check("Scene graph contract", FAIL,
                                  f"Invalid scene graph — must not render: {error}"),
                           overlay_check]}
    canvas = checked.get("canvas", {})
    width, height = int(canvas.get("width", 0)), int(canvas.get("height", 0))
    layers = visible_text_layers(checked)
    checks: list[dict[str, Any]] = [_check(
        "Scene graph contract", PASS,
        f"version={checked.get('version')} mode={checked.get('mode')} "
        f"kind={checked.get('kind')} canvas={width}x{height}.")]
    checks.append(check_card_contract(checked))

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

    text_fit = check_text_fit(checked)
    if text_fit is not None:
        checks.append(text_fit)

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
    placement = check_media_placement(checked, bg_image, pack_image)
    if placement is not None:
        checks.append(placement)
    if checked.get("kind") == "primitive" and str(checked.get("mode", "")) == "tactical_explainer":
        checks.append(_check(
            "Tactical vectors", NEEDS_REVIEW,
            "Primitive tactical plate: pass/run/press vectors come from an "
            "unfrozen fallback storyboard, not the graph — verify the rendered "
            "diagram against the reviewed tactical data by eye."))
    checks.append(overlay_check)

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
    # Frozen card-media bindings are executable refs: they come first so the
    # dedupe keeps the exact ref the renderer paints.
    bindings = graph.get("media_bindings")
    if isinstance(bindings, list):
        for binding in bindings:
            if not isinstance(binding, dict) or binding.get("status") != "bound":
                continue
            asset = binding.get("asset")
            if isinstance(asset, dict) and asset.get("kind") == "library_image":
                _take(
                    asset.get("asset_id"),
                    f"media_bindings[{binding.get('slot_id')}].asset",
                    asset,
                )
    # Roles next: they carry the planner's approval_status/rights_scope.
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
    pack_images: list[Any] | None = None,
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
    - pack_images: background-only renders with no bound media, aligned
      with graphs; prove media placement and empty fallback slots.
    - narrations: {segment_id: narration} or [narration per beat].
    - roles: {segment_id: role}; without opening/ending role metadata the
      structure check NEEDS_REVIEWs instead of guessing from content.
    - purpose: upload intent for the per-purpose media scope gate.
    """
    graphs = list(graphs or [])
    images = list(images or [])
    bg_images = list(bg_images or [])
    pack_images = list(pack_images or [])

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
                       pack_image=pack_images[i] if i < len(pack_images) else None,
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

    # Clip-level overlay aggregation: every scene's overlay gate must be
    # clean for the clip to PASS the overlay criterion.
    scene_overlay = [next((c["status"] for c in s["checks"]
                           if c["criterion"] == "Overlay rendered"), None)
                     for s in scenes]
    if any(st == FAIL for st in scene_overlay):
        checks.append(_check(
            "Overlay rendered", FAIL,
            "One or more scenes declare free-standing overlays without a "
            "frozen template-slot binding; renderer suppresses them."))
    elif any(st == NEEDS_REVIEW for st in scene_overlay):
        checks.append(_check(
            "Overlay rendered", NEEDS_REVIEW,
            "Overlay(s) declared valid but a still cannot confirm in-frame "
            "paint — verify on the rendered MP4."))
    else:
        checks.append(_check(
            "Overlay rendered", PASS,
            "No overlay declared in any scene — nothing to render."))

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
