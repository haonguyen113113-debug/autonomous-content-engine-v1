"""Render helper: manim CLI wrapper for Kit proofs (build-time only)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


SCENES = ("DuelColumns", "StatLeader", "PosterSide", "GoalPunch",
          "FixtureCard", "ScoreBug", "QuoteReveal", "WelcomeCard")

# v8 atoms kept for history; new default is the v9 Kit set above.
LEGACY_SCENES = ("HookCard", "ComparisonDuel", "StatLeader", "PlayerPoster",
                 "GoalCard", "FixtureCard", "ScoreCard")


def render_scenes(root: Path, scenes: tuple[str, ...] = SCENES,
                  aspect: str = "short", quality: str = "qm") -> dict[str, str]:
    """Render manim scenes to template previews/manim/. Returns scene->mp4."""
    out: dict[str, str] = {}
    scene_file = root / "apps/manim_kit/sportskit.py"
    media_dir = root / "template_foundation/templates/allen-knows-ball/9.0.0/previews/manim"
    media_dir.mkdir(parents=True, exist_ok=True)
    width, height = (1080, 1920) if aspect != "long" else (1920, 1080)
    for scene in scenes:
        cmd = ["manim", f"-{quality}", "--format=mp4",
               "-r", f"{width},{height}",
               "--media_dir", str(media_dir), str(scene_file), scene]
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True,
                              timeout=600)
        if proc.returncode != 0:
            raise RuntimeError(f"manim {scene} failed: {proc.stderr[-2000:]}")
        matches = sorted(media_dir.rglob(f"{scene}*.mp4"),
                         key=lambda p: p.stat().st_mtime)
        if not matches:
            raise RuntimeError(f"manim {scene} produced no mp4 under {media_dir}")
        out[scene] = str(matches[-1])
    return out


if __name__ == "__main__":
    import sys
    repo = Path(__file__).resolve().parent.parent.parent
    only = tuple(sys.argv[1:]) or SCENES
    print(render_scenes(repo, only))
