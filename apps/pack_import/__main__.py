"""Dispatch pack_import CLI: init | build."""

from __future__ import annotations

import sys

from apps.pack_import import build as build_module
from apps.pack_import import init as init_module


if __name__ == "__main__":
    if not sys.argv[1:]:
        print("usage: python -m apps.pack_import [init|build] ...")
        raise SystemExit(2)
    verb, rest = sys.argv[1], sys.argv[2:]
    if verb == "init":
        raise SystemExit(init_module.main(rest))
    if verb == "build":
        raise SystemExit(build_module.main(rest))
    print(f"unknown verb '{verb}'; use init or build")
    raise SystemExit(2)
