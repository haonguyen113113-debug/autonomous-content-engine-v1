# Soundpack v1 licenses

Every track ships in `tracks/` with a `<slot>.json` sidecar (title, creator,
license + URL, source + landing URLs, duration, sha256, retrieval date).
The engine only plays files listed here; unlisted files in `tracks/` are
ignored.

| file | title / creator | license | commercial use | credit |
|---|---|---|---|---|
| tracks/tension-pad.mp3 | Tension Drones / Vospi (Freesound 368146) | CC0 | yes | no |
| tracks/neutral-pad.mp3 | Ambient Space Texture / Andrewkn (Freesound 474864) | CC0 | yes | no |
| tracks/uplift-pad.ogg | Soft Corporate / MusicLFiles via Wikimedia Commons | BY 4.0 | yes | credit in description |
| tracks/dramatic-pad.mp3 | Epic_Heroic_Orchestral_Dramatic / SoundFlakes (Freesound 423499) | BY 4.0 | yes | credit in description |
| tracks/hook-hit.mp3 | Impact / chriskalos (Freesound 172779) | CC0 | yes | no |
| tracks/transition-whoosh.mp3 | Deep Whoosh #1 / Kinoton (Freesound 351256) | CC0 | yes | no |
| tracks/end-jingle.mp3 | jingle1 / soneproject (Freesound 255100) | CC0 | yes | no |

Notes:

- Freesound previews (`-hq.mp3`) inherit the source sound's license and are
  cleared for reuse under it. For the two BY 4.0 beds, credit the creator in
  the video description when publishing (owner step at publish time).
- Searched via Openverse Audio (`license=cc0,pdm,by`, 2026-10-14); no
  Content ID–claimed commercial recordings. If YouTube ever flags a track,
  swap the file + sidecar and bump the pack version — runs pin versions.
- Never add a track without filling its sidecar + this table.
