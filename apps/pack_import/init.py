"""Scaffold an owner pack drop folder."""

from __future__ import annotations

import sys
from pathlib import Path

from apps.pack_import import init_scaffold


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: python -m apps.pack_import.init <drop-folder>")
        return 2
    drop = init_scaffold(Path(argv[0]))
    print(f"scaffold ready: {drop} (edit pack.json, export backgrounds, then build)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
