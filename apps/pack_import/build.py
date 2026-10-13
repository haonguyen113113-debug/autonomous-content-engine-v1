"""Validate and install an owner pack as a draft template version."""

from __future__ import annotations

import sys
from pathlib import Path

from apps.pack_import import PackError, build, validate


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: python -m apps.pack_import.build <drop-folder> [--root .]")
        return 2
    drop = Path(argv[0])
    root = Path(".")
    if "--root" in argv:
        root = Path(argv[argv.index("--root") + 1])
    errors = validate(drop)
    if errors:
        print("pack invalid:")
        for error in errors:
            print("-", error)
        return 1
    try:
        result = build(root, drop)
    except PackError as error:
        print(error)
        return 1
    print(f"installed pack v{result['version']}: {', '.join(result['layouts'])}")
    print("audit: /template-foundation/pack-audit.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
