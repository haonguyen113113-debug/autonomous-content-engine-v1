# Autonomous Content Engine v1

A portable, local-first autonomous content-to-profit system.

## Project goal

Build a system that continuously discovers opportunities, researches them, generates original content assets, distributes them across platforms, measures outcomes, and improves its future decisions.

The system is designed to remain transferable across machines. The development machine is disposable compute; project source, configuration, workflows, provenance, and persistent state must not depend on a specific computer.

## Current milestone

Rendering integration — local FFmpeg visual previews work in the UI for short and long templates; full-run assembly is wired behind script and voice review.

The first connected slice accepts a generic resource requirement and checks it
against the persisted library. For example:

```json
{
  "requirement_id": "content:topic-123:hero-image",
  "resource_type": "image",
  "purpose": "hero_image",
  "context": "topic-123",
  "rights_state": "verified",
  "lifecycle_state": "active"
}
```

Run it with:

```powershell
python -m apps.asset_library.cli evaluate-requirement --root . --requirement-file requirement.json
```

An `ACQUIRE` result means the inventory check found a gap. Image requests search Openverse across multiple indexed image providers, prioritize
large commercially usable licenses, and run source-diversifying follow-up searches.
Wikimedia Commons remains a fallback. Results show provider, source, creator,
attribution, and license metadata. Search does not download anything; selecting “Save for review” or “Approve rights &
save” is the explicit action that acquires and registers a candidate.

## Local engine UI

Start the UI from the project root:

```powershell
python -m apps.web_ui.server --root .
```

Then open `http://127.0.0.1:8000`. The UI uses Python's standard library and
local browser assets. Select a **short** or **long** content target in Workflows:
short uses the existing 9:16 package, while long uses a parallel 16:9 package
with an 8–20 minute chapter and production timeline. Both packages share the
channel identity but have their own story forms and durations. The local AI model
supports script drafting and asset-need suggestions; video assembly is a separate
renderer responsibility. Every script and asset remains subject to owner review.

The long-form foundation specifies beat timing, absolute overlay in/out points,
transitions, effects, chapters, evidence references, and source cards. The renderer
is now connected for an initial visual composition slice. In Workflows, create a
draft and choose **Render 18-second template preview** to inspect its framing,
Vietnamese typography, palette, and opening/body/ending rhythm. The preview is
silent and is saved under ignored `runtime/renders/<run-id>/` with a JSON quality
report. A full-run render requires owner approval of the script and an audited
local voice preview. The current renderer does not yet place selected football
media, align captions to phrase timing, or execute all declared transitions and
effects; those checks are explicitly marked partial or not assessed in the report.
Install FFmpeg and make `ffmpeg` and `ffprobe` available on `PATH`, or set
`FFMPEG_PATH` to the executable location.
See [the transferable runtime guide](docs/transferable-runtime.md) for installing
Ollama, recreating the optional local TTS runtime, and keeping per-PC data out of Git.

## Core principles

- Portable by design
- Local-first where practical
- Free/open-source tools preferred
- Secrets never committed to Git
- Source evidence and provenance are first-class data
- AI generation is separated from validation and publishing
- Platform adapters remain replaceable
- The system must be able to decline publishing when quality or evidence thresholds are not met

## Initial channel focus

The first operating category is **Soccer**, with a Vietnamese-speaking audience. The first channel foundation is **Allen Knows Ball**. Template Foundation is a separate, versioned layer for the channel's fixed identity and presentation; the Asset Library continues to supply only approved variable media. The initial package is a draft for review, not a production-ready release.
