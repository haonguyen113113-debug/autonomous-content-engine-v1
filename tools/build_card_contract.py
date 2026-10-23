"""Build the unified per-card contract for a released Template Foundation pack.

The contract is the single executable description of what each built card
accepts from the planner:

* ``data_slots`` — every authored text slot, its box/typography, which planner
  value feeds it, whether it is required for a mode, and its fit/limits.
* ``media_slots`` — the authored variable-media regions (empty means the card
  receives no variable Asset Library media).
* ``execution`` — whether the Scene Graph starter path can execute the card
  today, or the card is explicitly legacy/non-ready.

``apps/studio_templates/card_media.py`` is the runtime loader/validator. This
script derives the artifact from the registry + starter JSONs and checks that
the on-disk contract still matches the authored design.

Usage (from the repository root):

    python tools/build_card_contract.py --check
    python tools/build_card_contract.py --write
    python tools/build_card_contract.py --check --version 12.0.0

12.0.0 generation uses its frozen starter-mode surface and includes the
released C-11 hook card. 12.1.0 adds exactly one further execution promotion:
C-09/source_card (claim + source + date credit); BP-20/MR-12/U-08 remain
legacy/non-ready, and long-form is unchanged.

No network, no clock, no randomness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "studio_templates"))

from apps.file_digest import digest_bytes, file_digest  # noqa: E402
from card_registry import CARDS, cards_for_version  # noqa: E402
from apps.card_selector import STARTERS_LONG, STARTERS_SHORT  # noqa: E402
from apps.scene_graph.builder import (  # noqa: E402
    STARTER_MODES,
    STARTER_MODES_12_0_0,
    STARTER_MODES_12_1_0,
    STARTER_MODES_12_2_0,
)
from apps.studio_templates.render_starters import font_for  # noqa: E402

TEMPLATE_VERSION = "12.2.0"

# Frozen per-pack starter-mode surfaces. Each released contract must be
# reproducible byte-for-byte, so the tool never uses the live STARTER_MODES
# set for an older version.
STARTER_MODES_BY_VERSION: dict[str, frozenset[str]] = {
    "12.0.0": STARTER_MODES_12_0_0,
    "12.1.0": STARTER_MODES_12_1_0,
    "12.2.0": STARTER_MODES_12_2_0,
}
PACK = (
    ROOT / "template_foundation" / "templates" / "allen-knows-ball"
    / TEMPLATE_VERSION
)
CONTRACT_FILE = PACK / "card-contract.json"
STARTER_DIR = ROOT / "apps" / "studio_templates"

CONTRACT_ID = "card-contract"
SCHEMA_VERSION = "2.0"
CANVAS = {"width": 1080, "height": 1920}
CANVASES = {
    "short": {"width": 1080, "height": 1920},
    "long": {"width": 1920, "height": 1080},
}
GRAPHIC_TEMPLATES = PACK / "graphic-templates.json"

# Modes that may execute only on named cards. This is deliberately an
# allowlist, not a global promotion: source_card exists in STARTER_MODES for
# 12.1.0, but only C-09 is contract-ready. Any unlisted source card stays
# legacy/non-ready even though its starter has similar slots.
CONTRACT_MODE_CARD_ALLOWLIST: dict[str, set[str]] = {
    "source_card": {"C-09"},
}


def _at_least(version: str, floor: str) -> bool:
    """True when pack ``version`` is ``floor`` or newer.

    Contract behaviour must never be pinned to one exact pack string: a
    later pack inherits every earlier authoring rule unless it explicitly
    changes it. (Exact equality here silently reverted C-09's attribution
    mapping -- source name replacing the claim -- as soon as 12.2.0 shipped.)
    """
    def parts(value: str) -> tuple[int, ...]:
        out: list[int] = []
        for chunk in str(value).strip().split("."):
            try:
                out.append(int(chunk))
            except ValueError:
                out.append(0)
        return tuple(out)

    return parts(version) >= parts(floor)


def _pack(template_version: str | None = None) -> Path:
    version = str(template_version or TEMPLATE_VERSION).strip()
    return (
        ROOT / "template_foundation" / "templates" / "allen-knows-ball"
        / version
    )


def _graphic_templates(template_version: str | None = None) -> Path:
    return _pack(template_version) / "graphic-templates.json"


def _layout_required(template_version: str | None = None) -> dict[str, list[str]]:
    data = json.loads(
        _graphic_templates(template_version).read_text(encoding="utf-8")
    )
    result: dict[str, list[str]] = {}
    for layout in data.get("layouts") or []:
        if not isinstance(layout, dict) or not layout.get("id"):
            continue
        keys: list[str] = []
        for raw in layout.get("required_data") or []:
            key = str(raw)
            if key.startswith("graphic_data."):
                key = key[len("graphic_data."):]
            if key and key not in keys:
                keys.append(key)
        result[str(layout["id"])] = keys
    return result


LAYOUT_REQUIRED = _layout_required()

PLAYER_MODES = (
    "player_card", "player_poster", "player_poster_side",
    "player_poster_top", "potm_card",
)
PORTRAIT_PREFIXES = ("spot", "potm", "profile")

# Modes the selector can pick a specific card for through _story_starter().
STORY_MODES: dict[str, tuple[str, ...]] = {
    "hook_card": ("MR-01", "BP-01"),
    "score_card": ("MR-03",),
    **{mode: ("MR-08",) for mode in PLAYER_MODES},
    "duel_columns": ("BP-07", "BP-10"),
    "stat_leader": ("BP-15", "MR-09", "MR-07"),
    "chart_timeline": ("BP-04", "BP-05", "BP-11", "BP-17", "MR-05"),
    "source_card": ("BP-20", "MR-12"),
}

# Long tactical cards are selected by _tactical_starter(); the Scene Graph
# builder deliberately does not compose long-form starters yet.
LONG_TACTICAL_MODES = {"tactical_explainer"}

# Media slots are copied verbatim from the frozen C6 media contract. They are
# the only authored variable-media regions in pack 12.0.0.
PORTRAIT_SLOT: dict[str, Any] = {
    "slot_id": "player_portrait",
    "role": "player_portrait",
    "asset_type": "image",
    "subject_rule": "depicts_named_player_only",
    "required": False,
    "box_norm": [0.0, 0.147, 0.393, 0.646],
    "fit": "cover",
    "focal_point": [0.5, 0.3],
    "mask": {"shape": "rounded_rect", "corner_radii_px": [0, 52, 52, 0]},
    "z_after_layer_id": "bed-60",
    "min_source_px": [400, 400],
    "rights": {
        "requires_verified": True,
        "requires_active": True,
        "requires_persisted_human_grant": True,
        "purpose_specific": True,
        "human_review_required": True,
    },
    "qa": {"min_painted_fraction": 0.01, "max_outside_leak_pixels": 64},
    "fallback": {
        "behavior": "keep_pack_artwork",
        "reason": (
            "no eligible human-approved player portrait; the authored pack "
            "silhouette remains"
        ),
    },
}
PORTRAIT_CARDS = {"C-04", "MR-08", "BP-03"}

ROLE_LIMITS = {
    "hook_text": (90, 10),
    "player_name": (40, 5),
    "kicker": (34, 5),
    "support": (90, 12),
    "claim": (90, 10),
    "stat_value": (16, 2),
    "stat_label": (42, 5),
    "stat_meta": (60, 6),
    "team": (28, 4),
    "crest": (4, 1),
    "label": (42, 6),
    "metric": (16, 2),
    "credit": (90, 10),
    "context": (70, 8),
    "amount": (18, 2),
    "line": (80, 10),
    "note": (60, 8),
    "title": (42, 5),
    "date": (24, 3),
    "comp": (40, 5),
    "src_title": (40, 5),
    "src_body": (140, 18),
    "default": (60, 8),
}


def _contract_hash(document: dict[str, Any]) -> str:
    payload = dict(document)
    payload.pop("contract_hash", None)
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    """Canonical digest: text artifacts are newline-normalised."""
    return file_digest(path)


def _starter_path(card: dict[str, Any]) -> Path:
    return STARTER_DIR / f"{card['id']}.{card['aspect']}.json"


def _box(child: dict[str, Any]) -> list[int | float]:
    values = [
        child.get("x", 0), child.get("y", 0),
        child.get("width", 0), child.get("height", 0),
    ]
    return [
        int(round(value)) if isinstance(value, (int, float)) else 0
        for value in values
    ]


def _font(child: dict[str, Any]) -> dict[str, Any]:
    return {
        "family": str(child.get("fontFamily", "Be Vietnam Pro")),
        "size_px": int(child.get("fontSize", 40)),
        "weight": str(child.get("fontWeight", "normal")),
        "align": str(child.get("align", "left")),
    }


def _role_for_slot(slot_id: str) -> str:
    if slot_id == "claim":
        return "hook_text"
    if slot_id == "kicker":
        return "kicker"
    if slot_id == "support":
        return "support"
    if slot_id == "credit":
        return "credit"
    if slot_id in ("context",):
        return "context"
    if slot_id in ("amount",):
        return "amount"
    if slot_id in ("line",):
        return "line"
    if slot_id in ("note",):
        return "note"
    if slot_id in ("title",):
        return "title"
    if slot_id in ("date", "when"):
        return "date"
    if slot_id in ("comp",):
        return "comp"
    if slot_id.startswith("src-"):
        return slot_id.replace("-", "_")
    if slot_id.startswith("crest-"):
        return "crest"
    if slot_id.startswith(("team-", "home", "away")):
        return "team"
    if slot_id.startswith(("spot-", "potm-", "profile-")):
        suffix = slot_id.split("-", 1)[1]
        return {
            "name": "player_name",
            "tag": "stat_label",
            "meta": "stat_meta",
            "stat": "stat_value",
        }.get(suffix, "stat_label")
    if re.fullmatch(r"m-\d+-(home|away)", slot_id):
        return "metric"
    if re.fullmatch(r"label-\d+", slot_id):
        return "label"
    if re.fullmatch(r"l-\d+", slot_id):
        return "label"
    if re.fullmatch(r"v-\d+", slot_id):
        return "stat_value"
    return "default"


def _limits(slot_id: str, box: list[int | float], font: dict[str, Any]) -> tuple[int, int, int]:
    role = _role_for_slot(slot_id)
    role_chars, role_words = ROLE_LIMITS.get(role, ROLE_LIMITS["default"])
    size = max(11, int(font["size_px"]))
    width, height = int(box[2]), int(box[3])
    lines = max(1, min(6, int(height // max(1, size * 1.25))))
    # The authored size shrinks by at most half when the value is long; measure
    # capacity at that floor so max_chars describes what can still fit.
    fit_size = max(20, size // 2)
    try:
        face = font_for(font["family"], font["weight"], fit_size)
        sample = "Nguyễn Văn A 0123456789"
        avg = max(1.0, float(face.getlength(sample)) / len(sample))
        fit_chars = max(1, int((width - 4) / avg)) * lines
    except Exception:
        fit_chars = role_chars * lines
    max_chars = max(4, min(int(role_chars), int(fit_chars)))
    max_words = max(1, min(int(role_words), max_chars))
    return max_chars, max_words, lines


def _spec(
    mode: str,
    slot_id: str,
    card_slots: set[str],
    *,
    card_id: str = "",
    template_version: str = "",
) -> dict[str, Any] | None:
    """Return the planner mapping for one authored slot under one mode.

    None means this mode does not describe the slot: the card is not
    contract-executable for that mode and the mode must be declared legacy.
    The 12.1.0 source mapping is scoped to C-09; other source cards keep the
    historical mapping and remain non-ready.
    """
    if mode == "tactical_explainer" and _at_least(template_version, "12.2.0"):
        # 12.2.0/C-12. The reading is the required reviewed line; the heading
        # and provenance are authored/optional. No tactical vector or player
        # list is authored here, so the card never invents a diagram.
        if slot_id == "title":
            return {"sources": [], "required": False, "fallback": "authored_text"}
        if slot_id == "line":
            return {"sources": ["note"], "required": True, "fallback": "hide"}
        if slot_id == "credit":
            return {"sources": ["credit"], "required": False, "fallback": "hide"}
        return None

    if mode == "conclusion" and _at_least(template_version, "12.2.0"):
        # 12.2.0/C-13. Bounded takeaway copy only: the card does not summarize
        # narration, and it never carries a claim without its provenance.
        if slot_id == "title":
            return {"sources": [], "required": False, "fallback": "authored_text"}
        if slot_id == "claim":
            return {"sources": ["claim"], "required": True, "fallback": "hide"}
        if slot_id == "credit":
            return {"sources": ["credit"], "required": False, "fallback": "hide"}
        return None

    if mode == "hook_card":
        if slot_id == "claim":
            return {"sources": ["hook_text"], "required": True, "fallback": "hide"}
        if slot_id in ("kicker", "support", "numeral", "sub"):
            return {"sources": [], "required": False, "fallback": "hide"}
        if slot_id == "credit":
            return {"sources": ["credit"], "required": False, "fallback": "hide"}
        return None

    if mode in ("score_card", "goal_card"):
        mapping = {
            "context": (["context"], False),
            "home": (["winner:name"], True),
            "away": (["loser:name"], True),
            "score": (["winner:score"], True),
            "score-away": (["loser:score"], False),
            "crest-winner": (["winner:crest"], False),
            "crest-loser": (["loser:crest"], False),
            "credit": (["credit"], False),
        }
        if slot_id in mapping:
            sources, required = mapping[slot_id]
            return {"sources": sources, "required": required, "fallback": "hide"}
        return None

    if mode == "duel_columns":
        if slot_id == "title":
            return {"sources": [], "required": False, "fallback": "authored_text"}
        if slot_id == "team-home":
            return {"sources": ["home"], "required": False, "fallback": "hide"}
        if slot_id == "team-away":
            return {"sources": ["away"], "required": False, "fallback": "hide"}
        if slot_id == "crest-home":
            return {"sources": ["crest:home"], "required": False, "fallback": "hide"}
        if slot_id == "crest-away":
            return {"sources": ["crest:away"], "required": False, "fallback": "hide"}
        match = re.fullmatch(r"label-(\d+)", slot_id)
        if match:
            index = int(match.group(1))
            return {
                "sources": [f"metrics[{index}].label"],
                "required": index == 0,
                "fallback": "hide",
            }
        match = re.fullmatch(r"m-(\d+)-(home|away)", slot_id)
        if match:
            index, side = int(match.group(1)), match.group(2)
            return {
                "sources": [f"metrics[{index}].{side}"],
                "required": index == 0,
                "fallback": "hide",
            }
        if slot_id == "credit":
            return {"sources": ["credit"], "required": False, "fallback": "hide"}
        return None

    if mode == "stat_leader":
        if slot_id == "title":
            return {"sources": [], "required": False, "fallback": "authored_text"}
        if slot_id == "kicker":
            return {
                "sources": ["stats[0].label"],
                "required": False,
                "fallback": "authored_text" if "amount" in card_slots else "hide",
                "transform": "upper",
            }
        if slot_id == "claim":
            return {"sources": ["stats[0].value"], "required": True, "fallback": "hide"}
        if slot_id == "support":
            return {
                "sources": ["stats[1].summary"],
                "required": False,
                "fallback": "hide",
                "transform": "upper",
            }
        if slot_id == "amount":
            return {"sources": ["stats[0].value"], "required": True, "fallback": "hide"}
        if slot_id == "line":
            return {
                "sources": ["context", "stats[1].summary"],
                "required": False,
                "fallback": "hide",
            }
        if slot_id == "note":
            return {
                "sources": ["stats[2].summary", "stats[1].label"],
                "required": False,
                "fallback": "hide",
            }
        match = re.fullmatch(r"l-(\d+)", slot_id)
        if match:
            index = int(match.group(1))
            return {
                "sources": [f"stats[{index}].label", f"metrics[{index}].label"],
                "required": index == 0,
                "fallback": "hide",
            }
        match = re.fullmatch(r"v-(\d+)", slot_id)
        if match:
            index = int(match.group(1))
            return {
                "sources": [f"stats[{index}].value", f"metrics[{index}].home"],
                "required": index == 0,
                "fallback": "hide",
            }
        if slot_id == "credit":
            return {"sources": ["credit"], "required": False, "fallback": "hide"}
        return None

    if mode in PLAYER_MODES:
        prefix = next(
            (value for value in PORTRAIT_PREFIXES
             if f"{value}-name" in card_slots),
            None,
        )
        if prefix is None:
            return None
        side = mode in ("player_poster_side", "player_poster_top")
        if slot_id == f"{prefix}-name":
            return {"sources": ["player_name"], "required": True, "fallback": "hide"}
        if slot_id == f"{prefix}-tag":
            return {
                "sources": ["stats[0].label"],
                "required": side,
                "fallback": "hide",
                "transform": "upper",
            }
        if slot_id == f"{prefix}-meta":
            return {
                "sources": ["stats[1].summary"],
                "required": False,
                "fallback": "hide",
                "transform": "upper",
            }
        if slot_id == f"{prefix}-stat":
            return {
                "sources": ["stats[0].value"],
                "required": side,
                "fallback": "hide",
            }
        if slot_id == "credit":
            return {"sources": ["credit"], "required": False, "fallback": "hide"}
        return None

    if mode == "quote_card":
        if slot_id == "src-body":
            return {"sources": ["claim"], "required": True, "fallback": "hide"}
        if slot_id == "src-title":
            return {"sources": [], "required": False, "fallback": "authored_text"}
        if slot_id == "credit":
            return {"sources": ["credit"], "required": False, "fallback": "hide"}
        return None

    if mode == "source_card":
        if _at_least(template_version, "12.1.0") and card_id == "C-09":
            # C-09 is attribution-only: the body carries the reviewed claim,
            # and the credit line always carries both source and date. The
            # authored heading NGUỒN stays authored text. No source name is
            # allowed to masquerade as the claim, and credit cannot be hidden.
            if slot_id == "src-title":
                return {
                    "sources": [],
                    "required": False,
                    "fallback": "authored_text",
                }
            if slot_id == "src-body":
                return {
                    "sources": ["claim"],
                    "required": True,
                    "fallback": "hide",
                }
            if slot_id == "credit":
                return {
                    "sources": ["source", "date"],
                    "required": True,
                    "fallback": "hide",
                    "join": " • ",
                }
            return None
        if slot_id == "src-title":
            return {"sources": [], "required": False, "fallback": "authored_text"}
        if slot_id == "src-body":
            return {
                "sources": ["claim", "source"],
                "required": True,
                "fallback": "hide",
            }
        if slot_id == "credit":
            return {"sources": ["credit"], "required": False, "fallback": "hide"}
        return None

    if mode == "fixture_card":
        if slot_id == "comp":
            return {
                "sources": ["competition", "context"],
                "required": False,
                "fallback": "hide",
            }
        if slot_id == "home":
            return {"sources": ["home"], "required": True, "fallback": "hide"}
        if slot_id == "away":
            return {"sources": ["away"], "required": True, "fallback": "hide"}
        if slot_id in ("date", "when"):
            return {"sources": ["date"], "required": False, "fallback": "hide"}
        if slot_id == "crest-home":
            return {"sources": ["crest:home"], "required": False, "fallback": "hide"}
        if slot_id == "crest-away":
            return {"sources": ["crest:away"], "required": False, "fallback": "hide"}
        if slot_id == "credit":
            return {"sources": ["credit"], "required": False, "fallback": "hide"}
        return None

    return None


# Cards authored for pack 12.2.0 and later. Kept out of STARTERS_SHORT (which
# the frozen 12.0.0/12.1.0 contracts have already hashed) so older packs keep
# reproducing exactly.
SINCE_12_2_0_MODES: dict[str, str] = {
    "C-12": "tactical_explainer",
    "C-13": "conclusion",
}


def _modes_for(card: dict[str, Any]) -> set[str]:
    modes: set[str] = set()
    if card.get("since"):
        since_mode = SINCE_12_2_0_MODES.get(str(card["id"]))
        if since_mode:
            modes.add(since_mode)
    renderer = card.get("renderer") or ("generic", None)
    if renderer[0] == "generic" and renderer[1]:
        modes.add(str(renderer[1]))
    if renderer[0] == "frame":
        modes.add("frame")
    if card["aspect"] == "long" and renderer[0] == "starter":
        modes |= LONG_TACTICAL_MODES
    for mode, card_id in STARTERS_SHORT.items():
        if card_id == card["id"]:
            modes.add(mode)
    if card["aspect"] == "long":
        for mode, card_id in STARTERS_LONG.items():
            if card_id == card["id"]:
                modes.add(mode)
    for mode, ids in STORY_MODES.items():
        if card["id"] in ids:
            modes.add(mode)
    if card["id"] in PORTRAIT_CARDS:
        modes |= set(PLAYER_MODES)
    return modes


def _provides(specs: list[dict[str, Any]]) -> set[str]:
    """Planner data keys these slot mappings can supply.

    ``credit`` is the authored source+date line; winner-first score slots cover
    home/away/score. This is intentionally conservative: a layout requiring a
    key no slot can supply makes the mode non-executable.
    """
    provided: set[str] = set()
    for spec in specs:
        for source in spec.get("sources") or []:
            root = str(source)
            if root.startswith("stats["):
                provided.add("stats")
            elif root.startswith("metrics["):
                provided.add("metrics")
            elif root.startswith(("winner:", "loser:")):
                provided |= {"home", "away", "score"}
            elif root == "credit":
                provided |= {"source", "date"}
            else:
                provided.add(root.split("[", 1)[0])
    return provided


def _execution(
    card: dict[str, Any],
    modes: set[str],
    slot_ids: set[str],
    *,
    template_version: str,
    layout_required: dict[str, list[str]],
    starter_modes: frozenset[str],
) -> dict[str, Any]:
    renderer = card.get("renderer") or ("generic", None)
    if card["aspect"] == "long":
        return {
            "route": "legacy_long",
            "status": "legacy_non_ready",
            "modes": [],
            "legacy_modes": sorted(modes),
            "reason": (
                "long-form starter execution is deferred; the Scene Graph "
                "builder composes short starters only"
            ),
        }
    if renderer[0] == "frame":
        return {
            "route": "frame_legacy",
            "status": "legacy_non_ready",
            "modes": [],
            "legacy_modes": sorted(modes),
            "reason": (
                "frame route: the renderer composes heading/source text; the "
                "authored starter text slots are not executed"
            ),
        }
    executable: list[str] = []
    declared: list[str] = []
    allowlist_blocked: list[str] = []
    for mode in sorted(modes):
        if mode not in starter_modes:
            continue
        allowlist = CONTRACT_MODE_CARD_ALLOWLIST.get(mode)
        if allowlist is not None and card["id"] not in allowlist:
            allowlist_blocked.append(mode)
            continue
        specs = [
            _spec(
                mode, slot_id, slot_ids,
                card_id=str(card["id"]),
                template_version=template_version,
            )
            for slot_id in slot_ids
        ]
        if any(spec is None for spec in specs):
            continue
        if not any(spec and spec.get("required") for spec in specs):
            continue
        required_keys = layout_required.get(mode) or []
        missing_keys = set(required_keys) - _provides(
            [spec for spec in specs if spec is not None]
        )
        if missing_keys:
            continue
        executable.append(mode)
    for mode in sorted(modes):
        if mode not in executable:
            declared.append(mode)
    if not executable:
        if allowlist_blocked:
            allowed = sorted({
                card_id
                for mode in allowlist_blocked
                for card_id in CONTRACT_MODE_CARD_ALLOWLIST.get(mode, set())
            })
            reason = (
                f"{', '.join(allowlist_blocked)} is contract-executable only "
                f"for {', '.join(allowed)} in {template_version}; this card is "
                "explicitly legacy/non-ready"
            )
        else:
            reason = (
                "no supported scene-graph starter mode maps this card's "
                "authored text slots; rendered by the legacy generic path"
            )
        return {
            "route": "legacy_generic",
            "status": "legacy_non_ready",
            "modes": [],
            "legacy_modes": sorted(modes),
            "reason": reason,
        }
    status = "contract" if not declared else "partial"
    return {
        "route": "starter_design",
        "status": status,
        "modes": executable,
        "legacy_modes": declared,
        "reason": None if status == "contract" else (
            "some modes are not executable by the contract starter path; "
            "they remain explicitly legacy/non-ready"
        ),
    }


def _data_slot(
    child: dict[str, Any],
    mode_specs: list[tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    slot_id = str((child.get("custom") or {}).get("slot"))
    box = _box(child)
    font = _font(child)
    max_chars, max_words, max_lines = _limits(slot_id, box, font)
    active_modes = sorted({mode for mode, _ in mode_specs})
    required_modes = sorted({
        mode for mode, spec in mode_specs if spec.get("required")
    })
    sources: list[str] = []
    transforms: set[str] = set()
    fallbacks: set[str] = set()
    joins: set[str] = set()
    for _, spec in mode_specs:
        for source in spec.get("sources") or []:
            if source not in sources:
                sources.append(source)
        if spec.get("transform"):
            transforms.add(str(spec["transform"]))
        if spec.get("join"):
            joins.add(str(spec["join"]))
        fallbacks.add(str(spec.get("fallback") or "hide"))
    fallback = "authored_text" if "authored_text" in fallbacks else "hide"
    if len(transforms) > 1:
        raise SystemExit(f"conflicting transforms for {child.get('id')}: {transforms}")
    if len(joins) > 1:
        raise SystemExit(f"conflicting joins for {child.get('id')}: {joins}")
    if len(sources) == 0:
        fallback = "authored_text" if "authored_text" in fallbacks else "hide"
    record = {
        "slot_id": slot_id,
        "layer_id": str(child.get("id")),
        "type": "text",
        "role": _role_for_slot(slot_id),
        "active_modes": active_modes,
        "required_for_modes": required_modes,
        "sources": sources,
        "transform": next(iter(transforms), None),
        "fallback": fallback,
        "required": bool(required_modes),
        "box_px": box,
        "font": font,
        "fit": {
            "mode": "shrink",
            "min_size_px": max(20, int(font["size_px"]) // 2),
        },
        "max_lines": max_lines,
        "max_words": max_words,
        "max_chars": max_chars,
        "validation": {
            "non_empty": bool(required_modes),
            "max_chars": max_chars,
            "max_words": max_words,
            "max_lines": max_lines,
            "pattern": r"^\d{1,2}$" if slot_id in ("score", "score-away") else None,
        },
    }
    if joins:
        record["join"] = next(iter(joins))
    return record


def _static_layer(child: dict[str, Any]) -> dict[str, Any]:
    box = _box(child)
    font = _font(child)
    return {
        "layer_id": str(child.get("id")),
        "text": str(child.get("text", "")),
        "box_px": box,
        "font": font,
        "fit": {
            "mode": "shrink",
            "min_size_px": max(20, int(font["size_px"]) // 2),
        },
    }


def build(template_version: str | None = None) -> dict[str, Any]:
    version = str(template_version or TEMPLATE_VERSION).strip()
    if version not in STARTER_MODES_BY_VERSION:
        raise SystemExit(f"unsupported template version for contract: {version}")
    graphic_templates = _graphic_templates(version)
    layout_required = _layout_required(version)
    starter_modes = STARTER_MODES_BY_VERSION.get(version, STARTER_MODES)
    pack_cards = cards_for_version(version)
    by_id = {str(card["id"]): card for card in pack_cards}
    if len(by_id) != len(pack_cards):
        raise SystemExit("registry has duplicate card ids")
    cards_out: list[dict[str, Any]] = []
    for card in sorted(pack_cards, key=lambda item: str(item["id"])):
        card_id = str(card["id"])
        aspect = str(card["aspect"])
        path = _starter_path(card)
        if not path.is_file():
            raise SystemExit(f"starter missing for {card_id}: {path}")
        raw_bytes = path.read_bytes()
        raw = json.loads(raw_bytes.decode("utf-8"))
        children = raw["pages"][0]["children"]
        texts = [
            child for child in children
            if isinstance(child, dict) and child.get("type") == "text"
            and child.get("showInExport") is not False
        ]
        editor_notes = [
            {
                "layer_id": str(child.get("id")),
                "text": str(child.get("text", "")),
            }
            for child in children
            if isinstance(child, dict) and child.get("type") == "text"
            and child.get("showInExport") is False
        ]
        slotted = [
            child for child in texts
            if (child.get("custom") or {}).get("slot")
        ]
        if len({str((c.get("custom") or {}).get("slot")) for c in slotted}) != len(slotted):
            raise SystemExit(f"duplicate authored slot on {card_id}")
        modes = _modes_for(card)
        slot_ids = {str((c.get("custom") or {}).get("slot")) for c in slotted}
        execution = _execution(
            card, modes, slot_ids,
            template_version=version,
            layout_required=layout_required,
            starter_modes=starter_modes,
        )
        data_slots: list[dict[str, Any]] = []
        for child in slotted:
            slot_id = str((child.get("custom") or {}).get("slot"))
            specs: list[tuple[str, dict[str, Any]]] = []
            for mode in sorted(modes):
                spec = _spec(
                    mode, slot_id, slot_ids,
                    card_id=card_id,
                    template_version=version,
                )
                if spec is not None:
                    specs.append((mode, spec))
            data_slots.append(_data_slot(child, specs))
        static_layers = [
            _static_layer(child) for child in texts
            if not (child.get("custom") or {}).get("slot")
        ]
        first_image = next(
            (child for child in children
             if isinstance(child, dict) and child.get("type") == "image"),
            None,
        )
        packs = [child for child in children
                 if isinstance(child, dict) and child.get("type") == "image"]
        media_slots = []
        if card_id in PORTRAIT_CARDS:
            media_slots = [json.loads(json.dumps(PORTRAIT_SLOT))]
            if not any(child.get("id") == "bed-60" for child in packs):
                raise SystemExit(f"{card_id}: portrait anchor bed-60 missing")
        renderer = card.get("renderer") or ("generic", None)
        canvas = CANVASES[aspect]
        if (raw.get("width"), raw.get("height")) != (
            canvas["width"], canvas["height"]
        ):
            raise SystemExit(
                f"{card_id}: starter canvas {(raw.get('width'), raw.get('height'))} "
                f"!= contract canvas {(canvas['width'], canvas['height'])}"
            )
        cards_out.append({
            "card_id": card_id,
            "starter_id": card_id,
            "aspect": aspect,
            "family": card.get("family"),
            "canvas": canvas,
            "starter_file": path.name,
            "starter_sha256": digest_bytes(raw_bytes, normalise=True),
            "template_version": version,
            "modes": sorted(modes),
            "renderer_route": {
                "kind": str(renderer[0]),
                "mode": renderer[1],
            },
            "execution": execution,
            "pack_layer_id": first_image.get("id") if first_image else None,
            "data_slots": data_slots,
            "static_text_layers": static_layers,
            "editor_notes": editor_notes,
            "media_slots": media_slots,
        })
    version_path = (
        f"template_foundation/templates/allen-knows-ball/{version}/"
    )
    document = {
        "schema_version": SCHEMA_VERSION,
        "contract_id": CONTRACT_ID,
        "template_version": version,
        "canvas": CANVAS,
        "canvases": CANVASES,
        "layout_grammar": {
            "path": f"{version_path}graphic-templates.json",
            "sha256": _sha256_file(graphic_templates),
        },
        "source_of_truth": {
            "card_index": "apps/studio_templates/card_registry.py",
            "starter_design": "apps/studio_templates/<card_id>.<aspect>.json",
            "layout_grammar": f"{version_path}graphic-templates.json",
            "executable_contract": f"{version_path}card-contract.json",
            "rule": (
                "This is the single executable per-card contract. The starter "
                "JSON owns the authored pixels/geometry; the registry owns the "
                "built card index and renderer route; graphic-templates owns "
                "the mode grammar. The planner freezes this contract into the "
                "Scene Graph; the renderer only executes the frozen text/media."
            ),
        },
        "cards": cards_out,
    }
    document["contract_hash"] = _contract_hash(document)
    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--version", default=TEMPLATE_VERSION)
    args = parser.parse_args()
    document = build(args.version)
    contract_file = _pack(args.version) / "card-contract.json"
    text = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    if args.write:
        contract_file.write_text(text, encoding="utf-8")
        print(f"wrote {contract_file} ({len(document['cards'])} cards)")
        print(f"contract_hash={document['contract_hash']}")
        return 0
    if not contract_file.is_file():
        print(f"missing {contract_file}", file=sys.stderr)
        return 1
    current = json.loads(contract_file.read_text(encoding="utf-8"))
    if current == document:
        print(f"OK {contract_file} ({len(document['cards'])} cards)")
        return 0
    print("DRIFT: on-disk contract differs from generated contract", file=sys.stderr)
    current_cards = {c.get("card_id"): c for c in current.get("cards", [])}
    generated_cards = {c.get("card_id"): c for c in document.get("cards", [])}
    for card_id in sorted(set(current_cards) | set(generated_cards)):
        if current_cards.get(card_id) != generated_cards.get(card_id):
            print(f"  card differs: {card_id}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
