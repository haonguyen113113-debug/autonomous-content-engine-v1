from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


class TemplateFoundationError(RuntimeError):
    """The requested channel template is absent, malformed, or not released."""


@dataclass(frozen=True)
class TemplatePackage:
    root: Path
    catalog_record: dict[str, Any]
    channel: dict[str, Any]
    manifest: dict[str, Any]
    design_tokens: dict[str, Any]
    timeline: dict[str, Any]
    story_forms: dict[str, Any]
    slots: dict[str, Any]
    licenses: dict[str, Any]


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise TemplateFoundationError(f"Could not read template package file: {path.name}") from error
    if not isinstance(value, dict):
        raise TemplateFoundationError(f"Template package file must contain an object: {path.name}")
    return value


def resolve_template(
    project_root: Path,
    template_id: str,
    version: str | None = None,
    *,
    allow_draft: bool = False,
) -> TemplatePackage:
    """Resolve one immutable package; draft packages require an explicit preview path."""

    root = (project_root / "template_foundation").resolve()
    catalog = _read_json(root / "catalog.json")
    matches = [
        item for item in catalog.get("templates", [])
        if isinstance(item, dict)
        and item.get("template_id") == template_id
        and (version is None or item.get("version") == version)
    ]
    if not allow_draft:
        matches = [item for item in matches if item.get("status") == "released"]
    if not matches:
        raise TemplateFoundationError("No released package matches the requested template and version.")
    record = sorted(matches, key=lambda item: tuple(int(part) for part in str(item.get("version", "0")).split(".")))[-1]
    relative = Path(str(record.get("path", "")))
    package_root = (root / relative).resolve()
    if root not in package_root.parents:
        raise TemplateFoundationError("Template package path escapes its foundation root.")
    channel_record = next(
        (item for item in catalog.get("channels", []) if item.get("channel_id") == record.get("channel_id")),
        None,
    )
    if not channel_record:
        raise TemplateFoundationError("Template channel is missing from the catalog.")
    channel = _read_json(root / str(channel_record.get("path", "")))
    manifest = _read_json(package_root / "manifest.json")
    if manifest.get("template_id") != template_id or manifest.get("version") != record.get("version"):
        raise TemplateFoundationError("Template catalog and package manifest do not match.")
    if manifest.get("channel_id") != channel.get("channel_id"):
        raise TemplateFoundationError("Template package is bound to a different channel.")
    return TemplatePackage(
        root=package_root,
        catalog_record=record,
        channel=channel,
        manifest=manifest,
        design_tokens=_read_json(package_root / "design-tokens.json"),
        timeline=_read_json(package_root / "timeline.json"),
        story_forms=_read_json(package_root / "story-forms.json"),
        slots=_read_json(package_root / "slot-contract.json"),
        licenses=_read_json(package_root / "LICENSES.json"),
    )
