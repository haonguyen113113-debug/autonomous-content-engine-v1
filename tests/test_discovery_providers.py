import json
from pathlib import Path

import pytest

import apps.asset_library.discovery as discovery
from apps.asset_library.asset_intelligence import ResourceRequirement


def _ov_item(**overrides):
    item = {
        "id": "12345678-1234-1234-1234-1234567890ab",
        "url": "https://example.invalid/photo.jpg",
        "thumbnail": "https://api.openverse.org/imageproxy/",
        "license": "by",
        "license_version": "4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "width": 2000,
        "height": 1200,
        "filesize": 500000,
        "title": "Derby night lights",
        "source": "flickr",
        "foreign_landing_url": "https://example.invalid/landing/1",
        "creator": "Jane",
        "attribution": "Jane CC BY",
    }
    item.update(overrides)
    return item


def _commons_page(*, pageid="11", mime="image/jpeg", width=1600, height=900,
                  title="File:Derby.jpg", size=400000, mediatype="BITMAP",
                  timestamp=None):
    info = {
        "mime": mime,
        "mediatype": mediatype,
        "width": width,
        "height": height,
        "size": size,
        "url": "https://upload.wikimedia.org/x",
        "descriptionurl": f"https://commons.wikimedia.org/wiki/{title}",
        "thumburl": "https://thumb.wikimedia.org/x.jpg",
        "extmetadata": {
            "LicenseShortName": {"value": "CC BY-SA 4.0"},
            "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0/"},
            "Artist": {"value": "Commons User"},
        },
    }
    if timestamp is not None:
        info["timestamp"] = timestamp
    return {"pageid": pageid, "title": title, "imageinfo": [info]}


def test_openverse_gates_license_size_and_id(monkeypatch):
    payload = {"results": [
        _ov_item(),
        _ov_item(id="nope", license="by-nc"),
        _ov_item(id="12345678-1234-1234-1234-1234567890ac", width=400, height=300),
        _ov_item(id="12345678-1234-1234-1234-1234567890ad", license="by",
                 foreign_landing_url="http://insecure.invalid/x"),
    ]}
    monkeypatch.setattr(discovery, "_openverse_request_json", lambda url: payload)
    results = discovery._search_openverse_page("derby")
    assert len(results) == 1
    assert results[0].candidate_id == "openverse:12345678-1234-1234-1234-1234567890ab"
    assert results[0].media_type == "IMAGE"


def test_commons_video_search_filters_type_and_size(monkeypatch):
    pages = [
        _commons_page(pageid="21", mime="video/mp4", width=1280, height=720,
                      title="File:Derby.webm", mediatype="VIDEO"),
        _commons_page(pageid="22", mime="image/jpeg"),
        _commons_page(pageid="23", mime="video/mp4", width=320, height=240,
                      title="File:Tiny.mp4", mediatype="VIDEO"),
        _commons_page(pageid="24", mime="application/pdf", title="File:Doc.pdf"),
    ]
    monkeypatch.setattr(
        discovery, "_request_json",
        lambda url: {"query": {"pages": pages}} if "generator" in url else {"query": {"pages": []}},
    )
    results = discovery._search_commons_videos("derby", 8)
    assert [c.candidate_id for c in results] == ["21"]
    assert results[0].media_type == "VIDEO"


def test_image_search_merges_ranks_and_dedupes(monkeypatch):
    ov = [
        _ov_item(title="Derby night lights",
                 foreign_landing_url="https://example.invalid/landing/1"),
        _ov_item(id="12345678-1234-1234-1234-1234567890ac", title="Unrelated sunset",
                 foreign_landing_url="https://example.invalid/landing/2"),
    ]
    commons = [
        _commons_page(pageid="31", title="File:Derby night.jpg"),
        _commons_page(pageid="32", title="File:Other.jpg"),
    ]
    # Same landing page as the Openverse hit: must be deduped.
    commons[0]["imageinfo"][0]["descriptionurl"] = "https://example.invalid/landing/1"
    monkeypatch.setattr(discovery, "_search_openverse_page", lambda *a, **k: [
        discovery._candidate_from_openverse(item) for item in ov
    ])
    monkeypatch.setattr(
        discovery, "search_commons_images",
        lambda query, limit=8: [
            c for page in commons
            for c in [discovery._candidate_from_page(page)] if c is not None
        ],
    )
    candidates, statuses = discovery.search_candidates("derby night", limit=10)
    urls = [c.source_url.casefold() for c in candidates]
    assert len(urls) == len(set(urls))
    # Query-matching title ranks first.
    assert "Derby" in candidates[0].title
    # Providers interleave instead of one source dominating every row.
    roots = [c.provider.split(" · ")[0] for c in candidates]
    assert roots[0] != roots[1]
    states = {s["key"]: s["state"] for s in statuses}
    assert states["openverse_image"] == "ready"
    assert states["pexels_image"] == "needs_key"


def test_pexels_included_with_key(monkeypatch):
    monkeypatch.setenv("PEXELS_API_KEY", "test-key")

    def fake_pexels(path, key):
        assert key == "test-key"
        if path.startswith("/v1/search"):
            return {"photos": [{
                "id": 99, "width": 2000, "height": 1300,
                "url": "https://www.pexels.com/photo/99/",
                "photographer": "Pex User",
                "alt": "Derby stadium crowd",
                "src": {"original": "https://images.pexels.com/99.jpg",
                        "medium": "https://images.pexels.com/99m.jpg"},
            }]}
        return {"videos": []}

    monkeypatch.setattr(discovery, "_pexels_get_json", fake_pexels)
    monkeypatch.setattr(discovery, "_search_openverse_page", lambda *a, **k: [])
    monkeypatch.setattr(discovery, "search_commons_images", lambda *a, **k: [])
    candidates, statuses = discovery.search_candidates("derby stadium", limit=10)
    assert [c.candidate_id for c in candidates] == ["pexels:99"]
    assert candidates[0].license_name == "Pexels License"
    assert {s["key"]: s["state"] for s in statuses}["pexels_image"] == "ready"


def test_video_search_uses_commons_video_only(monkeypatch):
    monkeypatch.setattr(
        discovery, "_search_commons_videos",
        lambda query, limit: [
            discovery.ExternalAssetCandidate(
                candidate_id="41", provider="Wikimedia Commons", title="Derby clip",
                source_url="https://commons.wikimedia.org/wiki/File:Derby.webm",
                thumbnail_url="", media_type="VIDEO", mime_type="video/mp4",
                width=1280, height=720, size_bytes=9000000,
                license_name="CC BY-SA 4.0", license_url=None,
                creator=None, credit=None, duration_seconds=None,
            )
        ],
    )
    candidates, statuses = discovery.search_candidates("derby", resource_type="video")
    assert len(candidates) == 1
    assert candidates[0].media_type == "VIDEO"
    assert {s["key"]: s["state"] for s in statuses}["openverse_image"] == "ready"


def test_all_providers_failing_raises(monkeypatch):
    def boom(*args, **kwargs):
        raise discovery.DiscoveryError("down")

    monkeypatch.setattr(discovery, "_search_openverse_page", boom)
    monkeypatch.setattr(discovery, "search_commons_images", boom)
    with pytest.raises(discovery.DiscoveryError):
        discovery.search_candidates("derby")


def test_search_validates_inputs():
    with pytest.raises(ValueError):
        discovery.search_candidates("   ")
    with pytest.raises(ValueError):
        discovery.search_candidates("derby", resource_type="audio")
    with pytest.raises(ValueError):
        discovery.search_candidates("derby", limit=99)
    with pytest.raises(ValueError):
        discovery.search_candidates("derby", sort="popular")
    with pytest.raises(ValueError):
        discovery.search_candidates("derby", orientation="panorama")


def test_newest_sort_orders_dated_first(monkeypatch):
    monkeypatch.setattr(discovery, "_search_openverse_page", lambda *a, **k: [])
    pages = [
        _commons_page(pageid="51", title="File:Old.jpg",
                      timestamp="2020-05-01T10:00:00Z"),
        _commons_page(pageid="52", title="File:Fresh.jpg",
                      timestamp="2026-09-20T10:00:00Z"),
        _commons_page(pageid="53", title="File:Undated.jpg"),
    ]
    monkeypatch.setattr(
        discovery, "_request_json",
        lambda url: {"query": {"pages": pages}},
    )
    candidates, _ = discovery.search_candidates("derby", sort="newest")
    assert [(c.candidate_id, c.uploaded_at) for c in candidates] == [
        ("52", "2026-09-20"), ("51", "2020-05-01"), ("53", None),
    ]


def test_orientation_forwarded_to_pexels(monkeypatch):
    monkeypatch.setenv("PEXELS_API_KEY", "test-key")
    seen = []

    def fake_pexels(path, key):
        seen.append(path)
        return {"photos": [], "videos": []}

    monkeypatch.setattr(discovery, "_pexels_get_json", fake_pexels)
    monkeypatch.setattr(discovery, "_search_openverse_page", lambda *a, **k: [])
    monkeypatch.setattr(discovery, "search_commons_images", lambda *a, **k: [])
    monkeypatch.setattr(discovery, "_search_commons_videos", lambda *a, **k: [])
    discovery.search_candidates("derby", orientation="portrait")
    assert any(p.startswith("/v1/search?") and "orientation=portrait" in p for p in seen)
    seen.clear()
    discovery.search_candidates("derby", resource_type="video", orientation="portrait")
    assert any(p.startswith("/v1/videos/search") and "orientation=portrait" in p for p in seen)


def test_best_pexels_file_prefers_viewable_mp4():
    files = [
        {"file_type": "video/mp4", "width": 3840, "link": "https://x/big.mp4"},
        {"file_type": "video/mp4", "width": 1280, "link": "https://x/mid.mp4"},
        {"file_type": "video/webm", "width": 640, "link": "https://x/small.webm"},
    ]
    assert discovery._best_pexels_file(files)["link"] == "https://x/mid.mp4"
    assert discovery._best_pexels_file([{"file_type": "video/webm"}]) is None


def _video_requirement():
    return ResourceRequirement(
        requirement_id="clip:derby",
        resource_type="video",
        purpose="match_analysis_evidence",
        context="derby",
        rights_state="verified",
        lifecycle_state="active",
        discovery_query="derby",
        content_objective="Derby analysis",
    )


def test_save_video_candidate_ingests(monkeypatch, tmp_path):
    candidate = discovery.ExternalAssetCandidate(
        candidate_id="55", provider="Wikimedia Commons", title="Derby clip",
        source_url="https://commons.wikimedia.org/wiki/File:Derby.webm",
        thumbnail_url="", media_type="VIDEO", mime_type="video/mp4",
        width=1280, height=720, size_bytes=1000,
        license_name="CC BY-SA 4.0", license_url=None,
        creator="Clipper", credit=None, duration_seconds=12,
    )
    monkeypatch.setattr(discovery, "_candidate_by_id", lambda *a, **k: candidate)
    monkeypatch.setattr(
        discovery, "_download_candidate",
        lambda *a, **k: (b"\x00\x00\x00\x20ftypmp42" + b"\x00" * 64, "video/mp4"),
    )
    result = discovery.save_commons_candidate(
        tmp_path, "55", _video_requirement(), rights_reviewed=True
    )
    assert result["status"] == "SAVED"
    assert result["rights_state"] == "verified"
    from apps.asset_library.registry import connect
    conn = connect(tmp_path / "runtime/engine.db")
    try:
        row = conn.execute(
            "SELECT asset_type, rights_state, lifecycle_state FROM assets WHERE asset_id = ?",
            (result["asset_id"],),
        ).fetchone()
    finally:
        conn.close()
    assert tuple(row) == ("video", "verified", "active")


def test_save_rejects_type_mismatch(monkeypatch, tmp_path):
    candidate = discovery.ExternalAssetCandidate(
        candidate_id="56", provider="Wikimedia Commons", title="Derby clip",
        source_url="https://commons.wikimedia.org/wiki/File:Derby.webm",
        thumbnail_url="", media_type="VIDEO", mime_type="video/mp4",
        width=1280, height=720, size_bytes=1000,
        license_name="CC BY-SA 4.0", license_url=None,
        creator=None, credit=None, duration_seconds=None,
    )
    monkeypatch.setattr(discovery, "_candidate_by_id", lambda *a, **k: candidate)
    requirement = ResourceRequirement(
        requirement_id="img:derby", resource_type="image", purpose="hero_image",
        context="derby", rights_state="verified", lifecycle_state="active",
    )
    with pytest.raises(ValueError, match="does not match"):
        discovery.save_commons_candidate(
            tmp_path, "56", requirement, rights_reviewed=True
        )


def _pixabay_photo_hit(photo_id=101, width=2000, height=1300):
    return {
        "id": photo_id,
        "pageURL": f"https://pixabay.com/photos/test-{photo_id}/",
        "tags": "derby stadium night",
        "previewURL": "https://cdn.pixabay.com/photo/150.jpg",
        "largeImageURL": "https://pixabay.com/get/abcdef_1280.jpg",
        "imageWidth": width,
        "imageHeight": height,
        "imageSize": 500000,
        "user": "Pix User",
    }


def _pixabay_video_hit(video_id=202):
    return {
        "id": video_id,
        "pageURL": f"https://pixabay.com/videos/test-{video_id}/",
        "tags": "derby stadium night",
        "duration": 15,
        "user": "Pix Videographer",
        "videos": {
            "medium": {"url": "https://cdn.pixabay.com/video/medium.mp4",
                       "width": 1280, "height": 720},
            "small": {"url": "https://cdn.pixabay.com/video/small.mp4",
                      "width": 640, "height": 360},
        },
    }


def test_pixabay_included_with_key_and_latest_order(monkeypatch):
    monkeypatch.setenv("PIXABAY_API_KEY", "px-key")
    seen = []

    def fake_pixabay(url):
        seen.append(url)
        if url.startswith(discovery.PIXABAY_VIDEO_API):
            return {"hits": [_pixabay_video_hit()]}
        return {"hits": [_pixabay_photo_hit()]}

    monkeypatch.setattr(discovery, "_pixabay_get_json", fake_pixabay)
    monkeypatch.setattr(discovery, "_search_openverse_page", lambda *a, **k: [])
    monkeypatch.setattr(discovery, "search_commons_images", lambda *a, **k: [])
    candidates, statuses = discovery.search_candidates(
        "derby stadium", limit=10, sort="newest")
    assert [c.candidate_id for c in candidates] == ["pixabay:101"]
    assert candidates[0].license_name == "Pixabay Content License"
    assert {s["key"]: s["state"] for s in statuses}["pixabay_image"] == "ready"
    assert any("order=latest" in url for url in seen)


def test_pixabay_video_candidate_and_save(monkeypatch, tmp_path):
    monkeypatch.setenv("PIXABAY_API_KEY", "px-key")
    monkeypatch.setattr(
        discovery, "_pixabay_get_json",
        lambda url: {"hits": [_pixabay_video_hit()]},
    )
    monkeypatch.setattr(discovery, "_search_commons_videos", lambda *a, **k: [])
    monkeypatch.setattr(discovery, "_search_openverse_page", lambda *a, **k: [])
    candidates, _ = discovery.search_candidates("derby", resource_type="video")
    assert [c.candidate_id for c in candidates] == ["pixabay-video:202"]
    assert candidates[0].duration_seconds == 15
    monkeypatch.setattr(
        discovery, "_download_candidate",
        lambda *a, **k: (b"\x00\x00\x00\x20ftypmp42" + b"\x00" * 64, "video/mp4"),
    )
    result = discovery.save_commons_candidate(
        tmp_path, "pixabay-video:202", _video_requirement(), rights_reviewed=True,
        api_keys={"PIXABAY_API_KEY": "px-key"},
    )
    assert result["status"] == "SAVED"
    from apps.asset_library.registry import connect
    conn = connect(tmp_path / "runtime/engine.db")
    try:
        row = conn.execute(
            "SELECT asset_type, source_url FROM assets WHERE asset_id = ?",
            (result["asset_id"],),
        ).fetchone()
    finally:
        conn.close()
    assert tuple(row) == ("video", "https://pixabay.com/videos/test-202/")


def test_pixabay_skipped_without_key(monkeypatch):
    monkeypatch.delenv("PIXABAY_API_KEY", raising=False)
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)

    def boom(url):
        raise AssertionError("must not query Pixabay without a key")

    monkeypatch.setattr(discovery, "_pixabay_get_json", boom)
    monkeypatch.setattr(discovery, "_search_openverse_page", lambda *a, **k: [])
    monkeypatch.setattr(discovery, "search_commons_images", lambda *a, **k: [])
    candidates, statuses = discovery.search_candidates("derby")
    assert candidates == []
    states = {s["key"]: s["state"] for s in statuses}
    assert states["pixabay_image"] == "needs_key"
    assert states["pixabay_video"] == "needs_key"
