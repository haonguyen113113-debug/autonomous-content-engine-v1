"""Scene Graph executor (renderer side): execute validated graphs only.

Boundary: this module performs ZERO composition choice. It validates the
graph (version/mode/canvas/absolute layers), then draws the absolute
``design`` with the existing Pillow primitives. No slot mapping, no
winner reordering, no asset-driven remapping, no timeline-driven switching.
The frozen ``mode`` is rendered verbatim; misses raise instead of falling
back (fallback decisions belong to the planner + builder).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _validate(graph: dict[str, Any]) -> dict[str, Any]:
    from apps.scene_graph.schema import validate_scene_graph

    return validate_scene_graph(graph)


# Overlay role presets: vị trí/font/màu khóa theo template (deterministic),
# KHÔNG từ LLM. Tọa độ là tỉ lệ canvas (0..1), quy về pixel khi vẽ.
# Các role hỗ trợ: lower_third, caption, hook.
_OVERLAY_ROLE_PRESETS: dict[str, dict[str, Any]] = {
    "lower_third": {
        "font": "bold",
        "size_fraction": 0.05,
        "x_fraction": 0.05,
        "y_fraction": 0.82,
        "fill": (255, 255, 255, 230),
        "stroke_fill": (0, 0, 0, 140),
        "stroke_width": 2,
    },
    "caption": {
        "font": "latin",
        "size_fraction": 0.04,
        "x_fraction": 0.05,
        "y_fraction": 0.48,
        "fill": (255, 255, 255, 255),
    },
    "hook": {
        "font": "bold",
        "size_fraction": 0.075,
        "x_fraction": 0.05,
        "y_fraction": 0.10,
        "fill": (255, 205, 0, 255),
        "stroke_fill": (0, 0, 0, 110),
        "stroke_width": 2,
    },
}


def _role_of(overlay: dict[str, Any]) -> str:
    """Lấy role của overlay: trường ``role`` (free label, do schema cho phép)
    ưu tiên, rồi ``type`` (từ vựng khóa: lower_third/caption), rồi ``kind``
    (legacy)."""
    role = overlay.get("role")
    if not isinstance(role, str) or not role.strip():
        role = overlay.get("type")
    if not isinstance(role, str) or not role.strip():
        role = overlay.get("kind")
    if not isinstance(role, str) or not role.strip():
        raise ValueError("scene graph executor: overlay thiếu role/type/kind")
    return str(role)


def _collect_overlays(checked: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Lấy overlays đã đóng băng vào graph: top-level trước, ``params`` fallback.

    Chỉ đọc giá trị đóng băng; KHÔNG đọc lại timeline/segment để suy ra overlay.
    Schema đã chặn cấu trúc không hợp lệ trước khi executor được gọi.
    """
    overlays = checked.get("overlays")
    if overlays is None and isinstance(checked.get("params"), dict):
        overlays = checked["params"].get("overlays")
    return overlays


def _overlay_font_paths(is_long: bool) -> tuple[str, str]:
    """Đường dẫn font (read-only từ released pack) dùng vẽ overlay."""
    from template_foundation import resolve_template
    from pathlib import Path as _Path

    anchor = _Path(__file__).resolve().parents[2]
    package_id = ("allen-knows-ball.longform-analyst" if is_long
                  else "allen-knows-ball.shortform-analyst")
    package = resolve_template(anchor, package_id, allow_draft=True)
    bold = str(package.root / "resources/fonts/BeVietnamPro-Bold.ttf")
    latin = str(package.root / "resources/fonts/BarlowCondensed-Bold.ttf")
    return bold, latin


def _draw_overlay(image: Any, overlay: dict[str, Any], width: int,
                  height: int) -> None:
    """Vẽ một overlay văn bản lên ảnh đã render (mutates ``image``).

    Fail-closed: role không hỗ trợ hoặc thiếu văn bản -> ValueError rõ,
    không tự bịa composition.
    """
    if not isinstance(overlay, dict):
        raise ValueError("scene graph executor: overlay phải là một đối tượng")
    role = _role_of(overlay)
    preset = _OVERLAY_ROLE_PRESETS.get(role)
    if preset is None:
        raise ValueError(
            f"scene graph executor: không hỗ trợ overlay role {role!r}; "
            "các role hỗ trợ: lower_third, caption, hook"
        )
    text = overlay.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("scene graph executor: overlay thiếu văn bản không rỗng")

    from PIL import ImageDraw as _ImageDraw
    from PIL import ImageFont as _ImageFont

    is_long = (width, height) == (1920, 1080)
    bold_path, latin_path = _overlay_font_paths(is_long)
    font_path = bold_path if preset["font"] == "bold" else latin_path
    size = max(12, int(height * preset["size_fraction"]))
    font = _ImageFont.truetype(font_path, size)

    drawer = _ImageDraw.Draw(image)
    x = int(width * preset["x_fraction"])
    y = int(height * preset["y_fraction"])
    kwargs: dict[str, Any] = {
        "xy": (x, y),
        "text": text,
        "font": font,
        "fill": preset["fill"],
    }
    if "stroke_fill" in preset:
        kwargs["stroke_width"] = int(preset.get("stroke_width", 2))
        kwargs["stroke_fill"] = preset["stroke_fill"]
    drawer.text(**kwargs)


def _apply_overlays(image: Any, overlays: list[dict[str, Any]], width: int,
                    height: int) -> None:
    """Vẽ toàn bộ overlays lên ảnh đã render (theo thứ tự trong danh sách)."""
    for index, overlay in enumerate(overlays):
        if not isinstance(overlay, dict):
            raise ValueError(
                f"scene graph executor: overlays[{index}] phải là một đối tượng"
            )
        _draw_overlay(image, overlay, width, height)


def render_scene_graph(
    graph: dict[str, Any],
    *,
    texts: bool = True,
    decor: bool = True,
    transparent: bool = False,
    media: dict[str, dict[str, Any]] | None = None,
) -> Any:
    """Render a validated Scene Graph to a Pillow image.

    Starter graphs carry an absolute ``design`` (pixel boxes, fitted font
    sizes, pre-placed winner dots, hidden flags already applied). It is
    passed through to the existing ``render_design`` primitive unchanged.
    ``media`` maps a frozen ``media_slot`` id to the already-gated asset
    payload (path/fit/focal/mask/min_source_px); the primitive paints it in
    the authored region only. Unknown slots are ignored (they cannot exist
    without a frozen layer). Primitive graphs (photo beds, pitch plates,
    generic data frames) are rendered by the matching existing primitive
    for the frozen mode, without any mode switching.

    Khi graph kèm theo ``overlays`` (đóng băng bởi builder; top-level
    trước, ``params`` fallback), executor vẽ mỗi overlay văn bản theo role
    preset cố định lên ảnh đã render. Overlay không vẽ được -> ValueError
    (fail-closed, không tự bịa composition). Executor KHÔNG đọc lại
    timeline/segment để suy ra overlay.
    """
    checked = _validate(graph)
    canvas = checked["canvas"]
    width, height = int(canvas["width"]), int(canvas["height"])

    if checked.get("kind") == "starter":
        from apps.studio_templates.render_starters import render_design

        design = checked["design"]
        if not isinstance(design, dict):
            raise ValueError("scene graph executor: starter graph lacks design")
        image = render_design(design, texts=texts, decor=decor,
                              transparent=transparent, media=media)
    else:
        # Primitive: dispatch verbatim on the frozen mode. Each branch calls the
        # long-standing Pillow primitive with the frozen params; there is no
        # re-mapping to another mode on any condition.
        mode = str(checked.get("mode"))
        params = checked.get("params") or {}
        graphic = params.get("graphic_data") if isinstance(params, dict) else {}
        graphic = dict(graphic) if isinstance(graphic, dict) else {}
        if mode == "media_b_roll":
            media_asset_id = params.get("media_asset_id") if isinstance(params, dict) else None
            if not media_asset_id:
                raise ValueError("scene graph executor: b-roll graph lacks media_asset_id")
            raise ValueError(
                "scene graph executor: b-roll needs a resolved library image; "
                "resolve via write_scene_png(root=...) with a verified asset"
            )
        from apps.video_renderer import _write_editorial_data_scene as _write_data
        from apps.video_renderer import _write_tactical_scene as _write_pitch
        from template_foundation import resolve_template
        from pathlib import Path as _Path
        import tempfile as _tempfile

        is_long = (width, height) == (1920, 1080)
        # Palette + fonts resolve from the released pack only (read-only).
        anchor = _Path(__file__).resolve().parents[2]
        package_id = ("allen-knows-ball.longform-analyst" if is_long
                      else "allen-knows-ball.shortform-analyst")
        package = resolve_template(anchor, package_id, allow_draft=True)
        palette = package.design_tokens.get("palette", {})
        font = package.root / "resources/fonts/BeVietnamPro-Bold.ttf"
        latin = package.root / "resources/fonts/BarlowCondensed-Bold.ttf"
        if mode == "tactical_explainer":
            # Spec comes from the frozen graph only (top-level first,
            # params mirror for primitive graphs). No beat-index fallback,
            # no legacy storyboard: the planner must freeze it.
            spec = checked.get("tactical_diagram")
            if not isinstance(spec, dict):
                params = checked.get("params")
                spec = params.get("tactical_diagram") if isinstance(params, dict) else None
            if not isinstance(spec, dict):
                raise ValueError(
                    "scene graph executor: tactical_explainer beat lacks frozen "
                    "tactical_diagram spec — planner must freeze it"
                )
            with _tempfile.TemporaryDirectory() as tmp:
                out = _Path(tmp) / "scene.png"
                _write_pitch(out, width=width, height=height, font_path=font,
                             display_font_path=latin, palette=palette, spec=spec,
                             is_long=is_long, scene_number=int(checked.get("index", 0)) + 1,
                             scene_count=int(checked.get("index", 0)) + 1)
                from PIL import Image as _Image

                image = _Image.open(out).copy()
        else:
            with _tempfile.TemporaryDirectory() as tmp:
                out = _Path(tmp) / "scene.png"
                _write_data(out, font_path=font, display_font_path=latin, mode=mode,
                            data=graphic, palette=palette, is_long=is_long,
                            scene_number=int(checked.get("index", 0)) + 1)
                from PIL import Image as _Image

                image = _Image.open(out).copy()

    # Overlays đóng băng trong graph (top-level trước, params fallback).
    # Vẽ lên ảnh đã render theo role preset cố định; KHÔNG đọc lại
    # timeline/segment để suy ra overlay.
    overlays = _collect_overlays(checked)
    if overlays:
        try:
            _apply_overlays(image, overlays, width, height)
        except ValueError:
            raise
        except Exception as error:  # pragma: no cover - fail-closed
            raise ValueError(
                f"scene graph executor: không thể vẽ overlays: {error}"
            ) from error
    return image


def render_scene_graph_layers(
    graph: dict[str, Any],
    *,
    media: dict[str, dict[str, Any]] | None = None,
) -> tuple[Any, Any | None]:
    """Background + text layers for kinetic video entrances.

    Mirrors the legacy bg/text split (plate lands first, type fades in at
    +0.6s) but both layers come from the same frozen absolute design.
    ``media`` paints already-gated assets into their frozen media_slot
    regions on the background layer only (the text layer is transparent).
    Returns (bg_image, text_image_or_None).
    """
    checked = _validate(graph)
    if checked.get("kind") != "starter" or not isinstance(checked.get("design"), dict):
        image = render_scene_graph(checked, media=media)
        return image, None
    from apps.studio_templates.render_starters import render_design

    design = checked["design"]
    bg = render_design(design, texts=False, media=media)
    has_text = any(isinstance(c, dict) and c.get("type") == "text"
                   and c.get("showInExport") is not False
                   for c in design["pages"][0]["children"])
    text = render_design(design, decor=False, transparent=True) if has_text else None
    return bg, text


def write_scene_png(graph: dict[str, Any], path: str | Path) -> Path:
    """Render a starter graph to a PNG file (absolute layers only)."""
    checked = _validate(graph)
    if checked.get("kind") != "starter":
        raise ValueError("scene graph executor: write_scene_png needs a starter graph")
    image = render_scene_graph(checked)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(out)
    return out


__all__ = [
    "render_scene_graph",
    "render_scene_graph_layers",
    "write_scene_png",
]
