# Skills registry — design capabilities that travel with the repo

All skills live vendored under `skills/` and are tracked by git. Moving
machines needs nothing except `git clone` + the check below. No marketplace,
no Node, no re-download.

| Skill | Source | Use in this engine |
|---|---|---|
| polotno-sdk | polotno-project/skills | Studio editor SDK (pre-existing) |
| frontend-design | anthropics/skills | Layout/type/aesthetic direction, plan→review→build→critique |
| canvas-design | anthropics/skills | Philosophy-first static art; 81 OFL fonts for latin display |
| algorithmic-art | anthropics/skills | Seeded generative craft ported to PIL (p5.js itself not used) |
| emil-design-eng | emilkowalski/skills | Detailing craft: animation decisions, review checklist, invisible details |
| theme-factory | anthropics/skills | Coloring method: curated palette + pairing + custom theme generation (presets never touch the locked channel) |
| design-taste | h3nryprod01/design-taste (MIT) | Elite frontend taste synthesis (taste-skill + impeccable + emil): typography, color, motion, anti-slop refs |
| impeccable-lite | ilindaniel/impeccable-lite (Apache-2.0) | No-machinery UI direction: surface modes, craft checklist, generic-reject list, production floor |
| broadcast-depth | custom (this repo) | Faux-3D for CPU PIL: light, glow, grain, haze (no Blender) |

## Migrate to a new machine

```powershell
git clone <repo-url>
cd autonomous-content-engine-v1
python skills/verify.py   # must print ALL SKILLS OK
```

`verify.py` checks every file in `SOURCES.json` (presence + byte size) and
each `SKILL.md` frontmatter name. If anything is missing, re-download from
the `source` URLs in `SOURCES.json` (upstream git blob `sha` recorded per
file for provenance; local bytes differ by our source-header comment).

## Rules for adding a skill

1. Vendor verbatim under `skills/<name>/` (+ `LICENSE.txt`, no exceptions).
2. Prepend the `<!-- Source: ... -->` header like the existing skills.
3. Append its files to `SOURCES.json` (source URL + upstream sha + size).
4. Extend `tests/test_design_skills.py` (install intact) and this table.
5. Never vendor a skill that needs network/GPU/Node at render time unless
   its offline subset is documented in the header (see algorithmic-art).
