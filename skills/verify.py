"""Verify vendored skills are complete (migration check, no network).

Run: python skills/verify.py  (exit 0 + ALL SKILLS OK on success)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    manifest = json.loads((ROOT / "skills/SOURCES.json").read_text(encoding="utf-8"))
    files = manifest.get("files", {})
    failures: list[str] = []
    for rel, meta in sorted(files.items()):
        path = ROOT / "skills" / rel
        if not path.is_file():
            failures.append(f"MISSING {rel}")
            continue
        want = meta.get("vendored_size", meta.get("size"))
        if path.stat().st_size != want:
            failures.append(f"SIZE-MISMATCH {rel} "
                            f"(want {want}, got {path.stat().st_size})")
    for skill_dir in sorted((ROOT / "skills").iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if skill_dir.is_dir() and skill_md.is_file():
            text = skill_md.read_text(encoding="utf-8")
            if "\nname: " not in text or skill_dir.name not in text:
                failures.append(f"BAD-FRONTMATTER {skill_dir.name}/SKILL.md")
    if failures:
        print("SKILL VERIFY FAILED:")
        for failure in failures:
            print(f"  - {failure}")
        print(f"Re-download from the source URLs in skills/SOURCES.json ({len(failures)} issue(s)).")
        return 1
    print(f"ALL SKILLS OK ({len(files)} files, "
          f"{len([d for d in (ROOT / 'skills').iterdir() if d.is_dir()])} skills).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
