# Soundpack drop folder (owner-side intake)

Pixabay blocks bots, so the engine never downloads sounds itself. Workflow
from the owner sound catalog:

1. Audition + download on the asset page; keep the license evidence.
2. Rename the file EXACTLY to the manifest's locked filename for its slot
   (`hook-hit.mp3`, `transition-whoosh.mp3`, `build-riser.mp3`,
   `reveal-boom.mp3`, `stat-tick.mp3`, `gentle-transition.mp3`,
   `crowd-bed.mp3`, `whistle.mp3`, `shutter.mp3`, or a bed filename).
3. Add one row per file to `register.csv` (columns in the header).
   Required: slot, file, title, creator, license, page_url, commercial_ok.
   BY licenses additionally require credit_text. Rows flagged
   content_id_risk (HOLD policy: MB-01, MB-02) are rejected.
4. Run the import (validates decodability, duration caps, 20 MiB,
   allowlisted license, provenance): ask the agent or run
   `python -c "from apps.soundpack.intake import import_pack; import json; print(json.dumps(import_pack('.'), indent=1))"`.

Beds stay provisional researched files until YouTube Audio Library picks
(TA-L01) arrive through this same drop with their Studio license status.
