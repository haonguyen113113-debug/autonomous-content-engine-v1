"""Workstream 2: unified candidate interface, referral-only YouTube,
keyless Internet Archive adapters, exact-vs-generic match grading.

All provider I/O is fixture/mocked — no external downloads in tests.
"""

import pytest

import apps.asset_library.discovery as discovery
from apps.asset_library.auto_acquire import auto_acquire
from apps.asset_library.discovery import DiscoveryError


VALID_YT_ID = "dQw4w9WgXcQ"

UNIFIED_KEYS = {"provider", "source_url", "preview_url", "media_type",
                "license", "creator", "rights_scope", "match_grade",
                "verification_status"}


def _cc_image(candidate_id="7", title="Vietnam Malaysia third place", width=2000):
    return discovery.ExternalAssetCandidate(
        candidate_id=candidate_id, provider="Wikimedia Commons", title=title,
        source_url=f"https://commons.wikimedia.org/wiki/File:{candidate_id}",
        thumbnail_url="https://thumb.wikimedia.org/x.jpg",
        media_type="IMAGE", mime_type="image/jpeg",
        width=width, height=1200, size_bytes=500000,
        license_name="CC BY 4.0", license_url=None,
        creator="Commons User", credit=None,
    )


def _archive_docs():
    return {"response": {"docs": [
        {"identifier": "vietnam-match-2024", "title": "Vietnam match footage",
         "creator": "Archivist", "licenseurl": "https://creativecommons.org/licenses/by/4.0/",
         "mediatype": "movies", "width": "1280", "height": "720"},
        {"identifier": "stadium-photo-1", "title": "Old stadium photo",
         "creator": "Archivist",
         "mediatype": "image", "width": "2000", "height": "1500"},
        {"identifier": "bad id!!", "title": "Rejected", "mediatype": "image"},
    ]}}


def test_unified_interface_shape_all_providers(monkeypatch):
    monkeypatch.setattr(
        discovery, "_archive_get_json", lambda url: _archive_docs())
    archive_img = discovery._search_archive_images("vietnam", limit=5)
    archive_vid = discovery._search_archive_videos("vietnam", limit=5)
    assert len(archive_img) == 1 and len(archive_vid) == 1
    candidates = [
        _cc_image(),
        discovery.youtube_referral_candidate(VALID_YT_ID, "Vietnam highlights",
                                             creator="Channel"),
        archive_img[0],
        archive_vid[0],
    ]
    for candidate in candidates:
        unified = candidate.to_unified_dict()
        assert UNIFIED_KEYS <= set(unified)
        assert unified["media_type"] in {"image", "video"}
        assert unified["preview_url"]
        assert unified["source_url"].startswith("https://")
        assert unified["license"]
        # rights_scope is the workstream-1 scope dict, never a self-made shape.
        scope = unified["rights_scope"]
        assert scope.get("granted_by") in {"deny-default", "backfill-allow"}
        assert scope.get("schema_version") == 1
        assert unified["match_grade"] in {"exact", "generic"}
        assert unified["verification_status"] == "unverified"
    assert candidates[0].media_kind == "image"
    assert candidates[1].media_kind == "video"
    # Legacy mirrors: preview/license follow thumbnail/license_name.
    assert candidates[0].preview_url == candidates[0].thumbnail_url
    assert candidates[0].license == "CC BY 4.0"


def test_youtube_referral_defaults():
    candidate = discovery.youtube_referral_candidate(
        VALID_YT_ID, "Vietnam Malaysia full match", creator="VFF Channel",
        duration_seconds=5400)
    assert candidate.provider == "YouTube (referral only)"
    assert candidate.source_url == f"https://www.youtube.com/watch?v={VALID_YT_ID}"
    assert candidate.preview_url == f"https://i.ytimg.com/vi/{VALID_YT_ID}/hqdefault.jpg"
    assert candidate.media_type == "VIDEO"
    assert candidate.rights_scope.get("granted_by") == "deny-default"
    assert discovery.rights_blocked(candidate.rights_scope) is not None
    assert discovery.rights_blocked(_cc_image().rights_scope) is None
    assert candidate.duration_seconds == 5400
    assert discovery.is_referral_only(candidate) is True
    assert discovery.is_referral_only(_cc_image()) is False
    # Workstream-1 decision: YouTube referral denied + human review even with
    # a full purpose; CC candidates are not pre-cleared either (unverified).
    yt_decision = discovery.candidate_rights_decision(
        candidate, {"platform": "youtube", "territory": "VN",
                    "commercial": True, "monetization": True, "edit": True,
                    "credit_planned": True, "use_count": 0})
    assert yt_decision["allowed"] is False
    assert yt_decision["required_action"] == "human_review"
    assert "unknown-source-or-license" in yt_decision["reasons"]
    cc_decision = discovery.candidate_rights_decision(
        _cc_image(), {"platform": "youtube", "territory": "VN",
                      "commercial": True, "monetization": True, "edit": True,
                      "credit_planned": True, "use_count": 0})
    assert cc_decision["allowed"] is False
    assert "rights-not-verified" in cc_decision["reasons"]
    # Invalid video IDs never become candidates.
    assert discovery.youtube_referral_candidate("too-short", "x") is None
    assert discovery.youtube_referral_candidate("not a url at all !!!!", "x") is None


def test_youtube_save_and_download_blocked(monkeypatch, tmp_path):
    from apps.asset_library.asset_intelligence import ResourceRequirement
    requirement = ResourceRequirement(
        requirement_id="clip:yt", resource_type="video",
        purpose="match_analysis_evidence", context="derby")
    with pytest.raises(DiscoveryError, match="referral-only"):
        discovery.save_commons_candidate(
            tmp_path, f"youtube:{VALID_YT_ID}", requirement, rights_reviewed=True)
    candidate = discovery.youtube_referral_candidate(VALID_YT_ID, "Highlights")
    assert candidate is not None
    with pytest.raises(DiscoveryError, match="referral-only"):
        discovery._download_candidate(candidate)
    with pytest.raises(DiscoveryError, match="referral-only"):
        discovery._candidate_by_id(f"youtube:{VALID_YT_ID}")


def test_youtube_search_default_empty_no_hook():
    discovery.set_youtube_search_fn(None)
    assert discovery.search_youtube_referrals("vietnam malaysia") == []
    assert discovery.search_youtube_referrals("   ") == []


def test_youtube_search_hook_filters_and_tolerates_failure():
    discovery.set_youtube_search_fn(None)
    try:
        def hook(query, limit):
            assert query == "vietnam malaysia"
            return [
                {"video_id": VALID_YT_ID, "title": "Vietnam Malaysia full match",
                 "creator": "VFF", "duration_seconds": 5400},
                {"video_id": "bad-id", "title": "Rejected"},
                "not-a-dict",
            ]
        results = discovery.search_youtube_referrals(
            "vietnam malaysia", limit=5, search_fn=hook)
        assert [c.candidate_id for c in results] == [f"youtube:{VALID_YT_ID}"]
        assert results[0].rights_scope.get("granted_by") == "deny-default"

        def boom(query, limit):
            raise RuntimeError("hook down")
        assert discovery.search_youtube_referrals("x", search_fn=boom) == []

        discovery.set_youtube_search_fn(hook)
        via_global = discovery.search_youtube_referrals("vietnam malaysia")
        assert [c.candidate_id for c in via_global] == [f"youtube:{VALID_YT_ID}"]
    finally:
        discovery.set_youtube_search_fn(None)


def test_match_grade_exact_terms():
    grade = discovery.grade_match
    assert grade("Vietnam Malaysia third place playoff", "VFF",
                "vietnam malaysia", ["Vietnam", "Malaysia"]) == "exact"
    assert grade("Vietnam training session", "VFF",
                "vietnam malaysia", ["Vietnam", "Malaysia"]) == "generic"
    assert grade("Unrelated concert", None, "vietnam malaysia",
                ["Vietnam", "Malaysia"]) == "generic"


def test_match_grade_heuristic_ignores_generic_football_vocab():
    grade = discovery.grade_match
    # Two significant shared tokens -> exact.
    assert grade("Vietnam Malaysia third place playoff", None,
                "vietnam malaysia playoff") == "exact"
    # Pure generic football vocabulary never counts -> generic.
    assert grade("Football stadium night match", None, "football stadium") == "generic"
    assert grade("Soccer goal clip", None, "soccer goal video") == "generic"


def test_archive_license_mapping_and_rights(monkeypatch):
    monkeypatch.setattr(
        discovery, "_archive_get_json", lambda url: _archive_docs())
    videos = discovery._search_archive_videos("vietnam", limit=5)
    images = discovery._search_archive_images("stadium", limit=5)
    assert len(videos) == 1 and len(images) == 1
    cc_video = videos[0]
    assert cc_video.license_name == "CC BY 4.0"
    assert cc_video.rights_scope.get("granted_by") == "backfill-allow"
    assert discovery.rights_blocked(cc_video.rights_scope) is None
    assert cc_video.width == 1280 and cc_video.height == 720
    unknown = images[0]
    assert unknown.license_name == "Unknown — verify on item page"
    assert unknown.rights_scope.get("granted_by") == "deny-default"
    assert discovery.rights_blocked(unknown.rights_scope) is not None
    assert unknown.preview_url.startswith("https://archive.org/services/img/")
    assert unknown.source_url.startswith("https://archive.org/details/")


def test_archive_detail_routes_by_mediatype(monkeypatch):
    def fake(url):
        if "identifier%3Avideo-1" in url or "identifier:video-1" in url:
            docs = [{"identifier": "video-1", "title": "Clip",
                     "mediatype": "movies",
                     "licenseurl": "https://creativecommons.org/publicdomain/zero/1.0/"}]
        else:
            docs = [{"identifier": "photo-1", "title": "Photo", "mediatype": "image"}]
        return {"response": {"docs": docs}}
    monkeypatch.setattr(discovery, "_archive_get_json", fake)
    video = discovery._archive_detail("video-1")
    assert video.media_type == "VIDEO" and video.license_name == "CC0"
    photo = discovery._archive_detail("photo-1")
    assert photo.media_type == "IMAGE"
    with pytest.raises(ValueError):
        discovery._archive_detail("bad id!!")


def test_archive_file_url_picks_supported_file(monkeypatch):
    monkeypatch.setattr(discovery, "_archive_get_json", lambda url: {"files": [
        {"name": "clip.ogv", "size": 500},
        {"name": "clip.mp4", "size": 9000},
        {"name": "thumb.gif", "size": 100},
    ]})
    assert discovery._archive_file_url("clip-1", video=True).endswith("/clip.mp4")
    monkeypatch.setattr(discovery, "_archive_get_json", lambda url: {"files": [
        {"name": "clip.mp4", "size": 10 ** 12},
    ]})
    with pytest.raises(DiscoveryError, match="no downloadable file"):
        discovery._archive_file_url("clip-1", video=True)


def test_provider_status_lists_new_adapters_and_tiers():
    statuses = discovery.provider_status()
    by_key = {item["key"]: item for item in statuses}
    assert by_key["archive_image"]["state"] == "ready"
    assert by_key["archive_video"]["state"] == "ready"
    assert by_key["youtube_referral"]["state"] == "ready"
    assert by_key["youtube_referral"]["acquisition"] == "referral_only"
    assert by_key["archive_image"]["acquisition"] == "download"
    assert discovery.tier_of_provider_key("archive_image") == "keyless"
    assert discovery.tier_of_provider_key("youtube_referral") == "keyless"
    assert discovery.tier_of_provider("Internet Archive") == "keyless"
    assert discovery.tier_of_provider("YouTube (referral only)") == "keyless"


def test_tiered_video_search_stamps_grades_and_lists_youtube(monkeypatch):
    monkeypatch.setattr(discovery, "_search_commons_videos", lambda *a, **k: [])
    monkeypatch.setattr(discovery, "_search_archive_videos", lambda *a, **k: [])
    monkeypatch.setattr(
        discovery, "search_youtube_referrals",
        lambda *a, **k: [discovery.youtube_referral_candidate(
            VALID_YT_ID, "Vietnam Malaysia playoff", creator="VFF")])
    ranked, statuses, report = discovery.search_candidates_tiered(
        "vietnam malaysia playoff", resource_type="video",
        exact_terms=["Vietnam", "Malaysia"])
    assert [c.candidate_id for c in ranked] == [f"youtube:{VALID_YT_ID}"]
    assert ranked[0].match_grade == "exact"
    assert ranked[0].source_tier == "keyless"
    assert "youtube_referral" in {item["key"] for item in statuses}


def _seen_by_id(result):
    return {entry["candidate_id"]: entry for entry in result["seen"]}


def test_auto_acquire_skips_youtube_and_prefers_exact(monkeypatch, tmp_path):
    youtube = discovery.youtube_referral_candidate(
        VALID_YT_ID, "Vietnam Malaysia full match", creator="VFF")
    # In the real flow search stamping grades this title exact (both terms
    # match), so it sorts ahead of the acceptable candidate — rights must
    # still block it before any license/title check.
    youtube = discovery.replace(youtube, match_grade="exact")
    generic = _cc_image("10", "Football stadium night")
    exact = _cc_image("11", "Vietnam Malaysia third place playoff")
    exact = discovery.replace(exact, match_grade="exact")
    calls = {}

    def fake_tiered(query, **kwargs):
        calls.update(kwargs)
        return ([youtube, generic, exact], [], {"tiers_queried": ["free"]})

    saved = {}

    def fake_save(root, candidate_id, requirement, **kwargs):
        saved["candidate_id"] = candidate_id
        return {"status": "SAVED", "asset_id": "asset-1",
                "rights_state": "verified", "candidate": {}}

    monkeypatch.setattr(discovery, "search_candidates_tiered", fake_tiered)
    monkeypatch.setattr(discovery, "save_commons_candidate", fake_save)
    result = auto_acquire(
        tmp_path, query="vietnam malaysia", include_terms=["Vietnam", "Malaysia"])
    assert result["status"] == "INGESTED"
    assert saved["candidate_id"] == "11"
    assert calls.get("exact_terms") == ["Vietnam", "Malaysia"]
    seen = _seen_by_id(result)
    assert seen[f"youtube:{VALID_YT_ID}"]["accepted"] is False
    assert "rights blocked" in " ".join(seen[f"youtube:{VALID_YT_ID}"]["reasons"])
    assert seen["11"]["match_grade"] == "exact"


def test_auto_acquire_youtube_only_has_no_qualified_candidate(monkeypatch, tmp_path):
    youtube = discovery.youtube_referral_candidate(
        VALID_YT_ID, "Vietnam Malaysia full match", creator="VFF")
    monkeypatch.setattr(
        discovery, "search_candidates_tiered",
        lambda *a, **k: ([youtube], [], {"tiers_queried": ["free"]}))

    def boom(*a, **k):
        raise AssertionError("referral-only candidates must never be saved")

    monkeypatch.setattr(discovery, "save_commons_candidate", boom)
    result = auto_acquire(tmp_path, query="vietnam malaysia")
    assert result["status"] == "NO_QUALIFIED_CANDIDATE"
    assert result["asset_id"] is None
