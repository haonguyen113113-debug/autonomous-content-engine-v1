# Polotno research — advanced techniques for the Kit rebuild (Oct 2026)

Sources: polotno-sdk SKILL.md + capabilities, polotno-design
(design-format, archetypes, transformations, proof-checks, commands,
runtimes/headless), docs pages (store, fonts, text-overflow, text-element
schema), all verified live in our Studio tab unless noted.

## 1. Runtime position (no Node.js on this machine)

- Headless scripts (`validate.js`/`lint.js`/`render.js`, polotno-node) and
  Cloud Render API need Node / paid key → NOT available.
- Our runtime = live browser editor: Studio page + store evaluate +
  file download + Python backend endpoints. Full loop proven:
  loadJSON → waitLoading → toDataURL pixelRatio 1 → 1080×1920 exact →
  pixel-verified (navy/orange zones, winner lime, credit).
- No-Node install of the skill: `skills/polotno-sdk/SKILL.md` saved verbatim.

## 2. Verified API surface (live `typeof` + export proofs)

- `createPolotnoApp({key, showCredit, container, sections})`, full store API.
- `store.setSize(w,h[,magic])`, `toDataURL({pixelRatio:1,pageId,mimeType})`,
  `toJSON/loadJSON`, `waitLoading`, `addFont`.
- `window.polotnoConfig`: `setGoogleFonts` ✓, `addGlobalFont` ✓,
  `setUploadFunc` ✓, `setTextOverflow` ✓ (function, all verified live).
- Google Fonts built in: Barlow Condensed, Be Vietnam Pro, Permanent Marker.
- Public template API works keyless:
  `api.polotno.com/api/get-templates?size=WxH&query=&per_page=&page=`
  (used it: 71 sport hits).

## 3. Sample-template verdict (user suggestion, checked)

- Closest public sample (`sports-football-event` story): event-promo grammar
  (full-bleed stock photo + giant date), Oswald/Quattrocento fonts, Unsplash
  photos with no provenance → fails our grammar (duel/winner-lime/poster/
  ticker), brand fonts, and rights pipeline. Rest of sport hits are generic
  ads. **Verdict: no fitting sample — rebuild from scratch on top of our
  proof-passed duel_columns starter.**

## 4. Advanced techniques selected for the build

1. **Strict boxes**: `setTextOverflow('change-font-size')` — long names/scores
   shrink instead of breaking layout (client default `resize` would).
2. **Brand lock**: `setGoogleFonts(['Barlow Condensed','Be Vietnam Pro',
   'Permanent Marker'])` limits the font dropdown; decoration elements get
   `selectable:false, draggable:false, resizable:false, removable:false`,
   value texts keep `contentEditable:true, styleEditable:false`.
3. **Slots**: `custom:{slot}` on every variable element (= pack boxes keys);
   bulk rows derive from one source template, never from each other.
4. **Native primitives over drawing**: `textTransform:uppercase`,
   `backgroundEnabled` pills, `line` arrows/chevrons, figure shapes —
   no hand SVG needed.
5. **Short↔long = recompose, never magic-resize** (transformation contract);
   12 starters × 2 aspects derived from short sources with recorded deltas.
6. **Placeholders**: none in starters (they render in exports).
7. **Proof loop per starter** (proof-checks.md): content → clipping →
   focus/reading → spacing/roles; compare against source at same scale.
8. **Uploads**: default base64 is fine local (PNG export flattens);
   `setUploadFunc` reserved for later server-side photo rights flow.
9. **Own template library** via existing `/api/studio/starter/<name>` pattern
   (public API proven unfitting, so we serve our starters, same mechanism).

## 5. Blockers (owner actions)

- `POLOTNO_API_KEY` (free trial, no card, polotno.com/cabinet) → `.env`;
  without it exports may watermark. Only item I cannot do myself.
- Internet required for unpkg CDN + Google Fonts on the Studio page.

## 6. Build plan (awaits go-ahead, NOT executed)

12 Kit starters (short+long) with lock flags + slots + overflow mode,
font-list limit + overflow default in Studio init, generalized starter
endpoint + Studio template picker, proof PNG per starter, tests, docs.
