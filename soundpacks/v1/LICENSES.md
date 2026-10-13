# Soundpack v1 licenses

Every track ships in `tracks/` with a `<slot>.json` sidecar (title, creator,
license + URL, source + landing URLs, duration, sha256, retrieval date).
The engine only plays files listed here; unlisted files in `tracks/` are
ignored.

## Beds (provisional researched files)

| file | title / creator | license | commercial use | credit |
|---|---|---|---|---|
| tracks/tension-pad.mp3 | Tension Drones / Vospi (Freesound 368146) | CC0 | yes | no |
| tracks/neutral-pad.mp3 | Ambient Space Texture / Andrewkn (Freesound 474864) | CC0 | yes | no |
| tracks/uplift-pad.ogg | Soft Corporate / MusicLFiles via Wikimedia Commons | BY 4.0 | yes | credit in description |
| tracks/dramatic-pad.mp3 | Epic_Heroic_Orchestral_Dramatic / SoundFlakes (Freesound 423499) | BY 4.0 | yes | credit in description |

Provisional: owner confirms or replaces via YouTube Audio Library picks
(TA-L01 in the owner catalog — prefer 'Attribution not required', record the
exact track + Studio license status through the drop importer).

## Stingers (owner catalog AKB IDs — import via `soundpacks/drop/`)

Pixabay blocks bots, so files arrive through the owner drop + provenance
register, never downloads. Expected locked filenames:

| slot file | catalog ID | candidate | status |
|---|---|---|---|
| tracks/hook-hit.mp3 | AKB-C05 | Cinematic Impact Hit, Universfield | pending owner drop |
| tracks/transition-whoosh.mp3 | AKB-C02 | Whoosh Effect, DRAGON-STUDIO | pending owner drop |
| tracks/build-riser.mp3 | AKB-C07 | Cinematic Riser 03, DRAGON-STUDIO | pending owner drop |
| tracks/end-jingle.mp3 | — | jingle1, soneproject (CC0, researched) | shipped provisional |

Reserve (shipped on import, unwired until placement is locked): `reveal-boom`
(AKB-C06), `stat-tick` (AKB-C04), `gentle-transition` (AKB-C02B),
`crowd-bed` (MR-S04), `whistle` (MR-S07), `shutter` (BP-S07).

## HOLD policy (from the owner catalog — enforced by the importer)

- `MB-01 Price of Freedom`, `MB-02 Motivation Hip Hop`: pages marked
  **Content ID Registered** → rejected (`content_id_risk` rows never import).
- Freesound uploads outside this pack: each needs its own license check;
  avoid CC BY-NC for monetized use (importer allowlists CC0/BY/BY-SA/Pixabay only).
- Pixabay Content License: free use + modification, no attribution, no
  standalone redistribution; full license text (not the summary) is binding.
- YouTube Audio Library tracks: copyright-safe inside YouTube/YPP, some need
  attribution (copy it from Studio); re-check per platform (TikTok/Instagram
  separate).
- Crowd/whistle SFX are illustrative sound design — never imply real match audio.
