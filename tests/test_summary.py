"""Pre-production summary: one gate, fix checkboxes, bulk approval."""

import json

import pytest

import apps.preproduction.summary as summary
from apps.preproduction.summary import build_summary, review_summary

RUN_ID = "a" * 12


def _beat(narration, beat_id="beat-1", mode="hook_card", duration=8):
    return {"id": beat_id, "narration": narration, "visual": "Mo ta",
            "evidence_refs": [], "visual_mode": mode,
            "graphic_data": {"hook_text": "Cau mo dau"}, "duration_seconds": duration,
            "timeline_events": []}


def _run(beats, checks=None):
    return {
        "run_id": RUN_ID, "status": "WAITING_FOR_OWNER_REVIEW",
        "llm_cost_usd": 0.0,
        "draft": {
            "topic": "Tran derby toi nay", "story_form": "one-moment-one-read",
            "content_type": "short", "duration_target_seconds": 40,
            "status": "NEEDS_OWNER_REVIEW", "segments": beats,
            "evidence": ["Nguon bao the thao 2026-10-14"], "generation_mode": "local_ollama",
            "fallback_beats": [],
        },
        "asset_checks": checks or [],
    }


def _write_run(tmp_path, run):
    path = tmp_path / "runtime/runs" / f"{RUN_ID}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run, ensure_ascii=False), encoding="utf-8")
    return run


def _check():
    return {
        "requirement_id": "variable-media-1",
        "requirement": {
            "requirement_id": "variable-media-1", "resource_type": "image",
            "purpose": "player_context", "context": "tien dao",
            "rights_state": "verified", "lifecycle_state": "active",
            "discovery_query": "tien dao an mung", "content_objective": "derby",
        },
        "required_count": 1, "eligible_count": 0, "shortfall": 1,
        "discovery_query": "tien dao an mung",
        "web_candidates": [{
            "candidate_id": "openverse:1", "provider": "Openverse · flickr",
            "title": "Tien dao an mung", "license_name": "CC BY 4.0",
            "source_tier": "keyless",
        }],
        "candidate_status": "SUGGESTIONS_ONLY",
        "provider_statuses": [],
    }


def test_build_sections_and_blocks_on_markers(tmp_path):
    _write_run(tmp_path, _run([
        _beat("Tran derby toi nay co gi dac biet"),
        _beat("[CẦN NGUỒN] Them quan sat cu the", beat_id="beat-2"),
    ], [_check()]))
    out = build_summary(tmp_path, RUN_ID)
    assert out["version"] == "1.0" and out["approved"] is False
    assert set(out["sections"]) == {"script", "narrative", "asset", "template", "voice"}
    assert out["sections"]["script"]["status"] == "blocked"
    assert out["sections"]["script"]["unresolved_beats"] == ["beat-2"]
    assert out["overall_status"] == "blocked"
    assert out["sections"]["template"]["decisions"]
    assert (_write_run(tmp_path, _run([])) or True)
    with pytest.raises(ValueError, match="no script beats"):
        build_summary(tmp_path, RUN_ID)
    assert (tmp_path / "runtime/summaries" / f"{RUN_ID}.json").is_file()


def test_autosave_off_by_default_records_nothing(tmp_path):
    _write_run(tmp_path, _run([_beat("Tran derby toi nay co gi dac biet")], [_check()]))
    out = build_summary(tmp_path, RUN_ID)
    assert out["sections"]["asset"]["autosave_enabled"] is False
    assert out["sections"]["asset"]["needs"][0].get("autosaved", []) == []


def test_autosave_saves_top_candidate_when_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("ASSET_AUTOSAVE", "true")
    saved = {}

    def fake_save(root, candidate_id, requirement, rights_reviewed, api_keys=None):
        saved["candidate_id"] = candidate_id
        saved["rights"] = rights_reviewed
        assert requirement.resource_type == "image"
        return {"status": "SAVED", "asset_id": "asset-1"}

    monkeypatch.setattr(summary, "save_commons_candidate", fake_save)
    _write_run(tmp_path, _run([_beat("Tran derby toi nay co gi dac biet")], [_check()]))
    out = build_summary(tmp_path, RUN_ID)
    need = out["sections"]["asset"]["needs"][0]
    assert saved == {"candidate_id": "openverse:1", "rights": True}
    assert need["autosaved"][0]["result"] == {"status": "SAVED", "asset_id": "asset-1"}


def test_script_fix_regenerates_one_beat(monkeypatch, tmp_path):
    _write_run(tmp_path, _run([
        _beat("Tran derby toi nay co gi dac biet"),
        _beat("Doi chu nha choi pressing tam cao", beat_id="beat-2"),
    ]))

    def fake_regen(root, run, beat_id, note):
        assert beat_id == "beat-2" and "pressing" in note
        run["draft"]["segments"][1] = _beat("Doi chu nha ep san doi thu ca tran", beat_id="beat-2")
        summary._write_run(root, run)
        return {"segment": run["draft"]["segments"][1],
                "llm_cost_usd": 0.0, "dropped_media": False}

    monkeypatch.setattr(summary, "regenerate_beat", fake_regen)
    out = review_summary(tmp_path, RUN_ID, False,
                         [{"section": "script", "target": "beat-2",
                           "note": "nhan manh pressing tam cao lan 2"}])
    assert out["approved"] is False
    assert out["fix_requests"][0]["section"] == "script"
    assert "ep san" in out["sections"]["script"]["beats"][1]["narration"]


def test_asset_fix_rediscovers_with_refined_query(monkeypatch, tmp_path):
    _write_run(tmp_path, _run([_beat("Tran derby toi nay co gi dac biet")], [_check()]))

    def fake_search(query, **kwargs):
        assert "phao sang" in query
        from apps.asset_library.discovery import ExternalAssetCandidate
        return [ExternalAssetCandidate(
            candidate_id="pexels:9", provider="Pexels", title="Phao sang",
            source_url="https://example.invalid/9", thumbnail_url="", media_type="IMAGE",
            mime_type="image/jpeg", width=2000, height=1200, size_bytes=1,
            license_name="Pexels", license_url=None, creator=None, credit=None)], [], {}

    monkeypatch.setattr(summary, "search_candidates_tiered", fake_search)
    out = review_summary(tmp_path, RUN_ID, False,
                         [{"section": "asset", "target": "variable-media-1",
                           "note": "phao sang"}])
    need = out["sections"]["asset"]["needs"][0]
    assert need["candidates"][0]["candidate_id"] == "pexels:9"
    assert "phao sang" in need["query"]


def test_template_fix_sets_visual_mode(tmp_path):
    _write_run(tmp_path, _run([
        _beat("Tran derby toi nay co gi dac biet"),
        _beat("Ti so chung cuoc tran dau nay", beat_id="beat-2"),
    ]))
    out = review_summary(tmp_path, RUN_ID, False,
                         [{"section": "template", "target": "beat-2", "note": "score_card"}])
    by_id = {dec["segment_id"]: dec for dec in out["sections"]["template"]["decisions"]}
    assert by_id["beat-2"]["visual_mode"] == "score_card"
    with pytest.raises(ValueError, match="visual mode"):
        review_summary(tmp_path, RUN_ID, False,
                       [{"section": "template", "target": "beat-2", "note": "khong co mode"}])


def test_fix_validation(tmp_path):
    _write_run(tmp_path, _run([_beat("Tran derby toi nay co gi dac biet")]))
    with pytest.raises(ValueError, match="one of"):
        review_summary(tmp_path, RUN_ID, False,
                       [{"section": "amthanh", "target": "x", "note": "y"}])
    with pytest.raises(ValueError, match="no open fixes"):
        review_summary(tmp_path, RUN_ID, True,
                       [{"section": "script", "target": "beat-1", "note": "y"}])
    with pytest.raises(ValueError, match="not found"):
        review_summary(tmp_path, "b" * 12, False, [])


def test_bulk_approve_drives_chain(monkeypatch, tmp_path):
    _write_run(tmp_path, _run([_beat("Tran derby toi nay co gi dac biet")], [_check()]))
    calls = {}

    def fake_voice(root, run_id):
        calls["voice"] = True
        return {"audio_url": "/api/voice-preview/x.wav", "engine": "vieneu",
                "voice": "allen-reference"}

    def fake_fit(root, run):
        calls["fit"] = True

    def fake_render(root, run_id):
        calls["render"] = True
        return {"report": {}}

    monkeypatch.setattr(summary, "synthesize_voice_preview", fake_voice)
    monkeypatch.setattr(summary, "_ensure_voice_fits_script", fake_fit)
    monkeypatch.setattr(summary, "render_full_run", fake_render)
    out = review_summary(tmp_path, RUN_ID, True, [])
    assert out["approved"] is True
    assert calls == {"voice": True, "fit": True, "render": True}
    stored = json.loads((tmp_path / "runtime/runs" / f"{RUN_ID}.json").read_text(encoding="utf-8"))
    assert stored["script_owner_approved"] is True
    assert stored["voice_preview_audited"] is True
    assert stored["voice_audit_method"] == "summary-bulk-auto"
    assert stored["summary_approved"] is True
    assert out["results"]["voice"]["audited"] is True
    assert "next_action" in out["results"]


def test_bulk_approve_refuses_markers(tmp_path):
    _write_run(tmp_path, _run([_beat("[CẦN NGUỒN] Them quan sat")]))
    with pytest.raises(ValueError, match="beat-1"):
        review_summary(tmp_path, RUN_ID, True, [])
