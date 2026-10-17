"""Tiered discovery: free-first with keyed escalation (Visibly Google-first pattern)."""

import pytest

import apps.asset_library.discovery as discovery
from apps.asset_library.discovery import DiscoveryError


@pytest.fixture(autouse=True)
def _stub_keyless_adapters(monkeypatch):
    """Pin new keyless adapters offline: tests inject fixtures per-case."""
    monkeypatch.setattr(discovery, "_search_archive_images", lambda *a, **k: [])
    monkeypatch.setattr(discovery, "_search_archive_videos", lambda *a, **k: [])
    monkeypatch.setattr(discovery, "search_youtube_referrals", lambda *a, **k: [])


def _fake(provider, index, *, title="Derby stadium night", license_name="CC BY 4.0",
          width=2000, height=1200, size_bytes=500000):
    return discovery.ExternalAssetCandidate(
        candidate_id=f"{provider}:{index}",
        provider=provider,
        title=f"{title} {index}",
        source_url=f"https://example.invalid/{provider}/{index}",
        thumbnail_url="https://example.invalid/thumb.jpg",
        media_type="IMAGE", mime_type="image/jpeg",
        width=width, height=height, size_bytes=size_bytes,
        license_name=license_name, license_url=None,
        creator=None, credit=None,
    )


def _keys():
    return {"PEXELS_API_KEY": "px-test", "PIXABAY_API_KEY": "pb-test"}


def _isolate(monkeypatch):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    monkeypatch.delenv("PIXABAY_API_KEY", raising=False)


def test_free_suffices_keyed_never_queried(monkeypatch):
    _isolate(monkeypatch)
    monkeypatch.setattr(discovery, "_search_openverse_page",
                        lambda *a, **k: [_fake("Openverse · flickr", i) for i in range(8)])
    monkeypatch.setattr(discovery, "search_commons_images", lambda *a, **k: [])

    def boom(*a, **k):
        raise AssertionError("keyed tier must not run when free suffices")

    monkeypatch.setattr(discovery, "_search_pexels_images", boom)
    monkeypatch.setattr(discovery, "_search_pexels_videos", boom)
    monkeypatch.setattr(discovery, "_search_pixabay_images", boom)
    monkeypatch.setattr(discovery, "_search_pixabay_videos", boom)
    ranked, statuses, report = discovery.search_candidates_tiered(
        "derby stadium", api_keys=_keys())
    assert report["tiers_queried"] == ["free"]
    assert report["escalated"] is False
    assert report["keyed_available"] is True
    assert report["free_count"] == 8 and report["keyed_count"] == 0
    assert len(ranked) == 8
    assert {c.source_tier for c in ranked} == {"keyless"}


def test_shortfall_escalates_and_merges(monkeypatch):
    _isolate(monkeypatch)
    monkeypatch.setattr(discovery, "_search_openverse_page",
                        lambda *a, **k: [_fake("Openverse · flickr", i) for i in range(2)])
    monkeypatch.setattr(discovery, "search_commons_images", lambda *a, **k: [])
    monkeypatch.setattr(discovery, "_search_pexels_images",
                        lambda *a, **k: [_fake("Pexels", i + 100) for i in range(4)])
    monkeypatch.setattr(discovery, "_search_pexels_videos", lambda *a, **k: [])
    monkeypatch.setattr(discovery, "_search_pixabay_images", lambda *a, **k: [])
    monkeypatch.setattr(discovery, "_search_pixabay_videos", lambda *a, **k: [])
    ranked, statuses, report = discovery.search_candidates_tiered(
        "derby stadium", api_keys=_keys(), min_free=6)
    assert report["tiers_queried"] == ["free", "keyed"]
    assert report["escalated"] is True
    assert "min_free 6" in report["escalation_reason"]
    assert report["free_count"] == 2
    assert {c.source_tier for c in ranked} == {"keyless", "keyed"}


def test_no_keys_never_escalates(monkeypatch):
    _isolate(monkeypatch)
    monkeypatch.setattr(discovery, "_search_openverse_page",
                        lambda *a, **k: [_fake("Openverse · flickr", i) for i in range(2)])
    monkeypatch.setattr(discovery, "search_commons_images", lambda *a, **k: [])
    ranked, statuses, report = discovery.search_candidates_tiered("derby stadium")
    assert report["tiers_queried"] == ["free"]
    assert report["escalated"] is False
    assert report["keyed_available"] is False
    assert "needs_key" in (report["escalation_reason"] or "")
    assert len(ranked) == 2


def test_min_free_zero_is_free_only(monkeypatch):
    _isolate(monkeypatch)
    monkeypatch.setattr(discovery, "_search_openverse_page",
                        lambda *a, **k: [_fake("Wikimedia Commons", 1)])
    monkeypatch.setattr(discovery, "search_commons_images", lambda *a, **k: [])

    def boom(*a, **k):
        raise AssertionError("min_free=0 must not touch the keyed tier")

    monkeypatch.setattr(discovery, "_search_pexels_images", boom)
    monkeypatch.setattr(discovery, "_search_pixabay_images", boom)
    ranked, statuses, report = discovery.search_candidates_tiered(
        "derby", api_keys=_keys(), min_free=0, min_good=0)
    assert report["tiers_queried"] == ["free"]
    assert len(ranked) == 1


def test_validation_errors_match_untiered(monkeypatch):
    _isolate(monkeypatch)
    with pytest.raises(ValueError, match="Search query is required"):
        discovery.search_candidates_tiered("   ")
    with pytest.raises(ValueError, match="250 characters"):
        discovery.search_candidates_tiered("x" * 251)
    with pytest.raises(ValueError, match="image and video"):
        discovery.search_candidates_tiered("derby", resource_type="audio")


def test_all_free_failures_raise(monkeypatch):
    _isolate(monkeypatch)

    def fail(*a, **k):
        raise DiscoveryError("down")

    monkeypatch.setattr(discovery, "_search_openverse_page", fail)
    monkeypatch.setattr(discovery, "search_commons_images", fail)
    with pytest.raises(DiscoveryError):
        discovery.search_candidates_tiered("derby")


def test_plentiful_but_poor_free_still_escalates(monkeypatch):
    _isolate(monkeypatch)
    monkeypatch.setattr(discovery, "_search_openverse_page", lambda *a, **k: [
        _fake("Openverse · flickr", i, title="Unrelated object photo",
              license_name="Unknown license", width=1000, height=1000)
        for i in range(8)])
    monkeypatch.setattr(discovery, "search_commons_images", lambda *a, **k: [])
    monkeypatch.setattr(discovery, "_search_pexels_images",
                        lambda *a, **k: [_fake("Pexels", i + 100) for i in range(4)])
    monkeypatch.setattr(discovery, "_search_pexels_videos", lambda *a, **k: [])
    monkeypatch.setattr(discovery, "_search_pixabay_images", lambda *a, **k: [])
    monkeypatch.setattr(discovery, "_search_pixabay_videos", lambda *a, **k: [])
    ranked, statuses, report = discovery.search_candidates_tiered(
        "derby stadium", api_keys=_keys(), min_free=6)
    assert report["tiers_queried"] == ["free", "keyed"]
    assert report["escalated"] is True
    assert "quality insufficient" in report["escalation_reason"]
    assert report["free_good_count"] == 0


def test_count_shortfall_escalates_despite_good_free(monkeypatch):
    _isolate(monkeypatch)
    monkeypatch.setattr(discovery, "_search_openverse_page",
                        lambda *a, **k: [_fake("Openverse · flickr", i) for i in range(4)])
    monkeypatch.setattr(discovery, "search_commons_images", lambda *a, **k: [])
    monkeypatch.setattr(discovery, "_search_pexels_images",
                        lambda *a, **k: [_fake("Pexels", i + 100) for i in range(4)])
    monkeypatch.setattr(discovery, "_search_pexels_videos", lambda *a, **k: [])
    monkeypatch.setattr(discovery, "_search_pixabay_images", lambda *a, **k: [])
    monkeypatch.setattr(discovery, "_search_pixabay_videos", lambda *a, **k: [])
    ranked, statuses, report = discovery.search_candidates_tiered(
        "derby stadium", api_keys=_keys(), min_free=6, min_good=3)
    assert report["escalated"] is True
    assert "min_free 6" in report["escalation_reason"]


def test_tier_helpers():
    assert discovery.tier_of_provider_key("openverse_image") == "keyless"
    assert discovery.tier_of_provider_key("commons_video") == "keyless"
    assert discovery.tier_of_provider_key("pexels_image") == "keyed"
    assert discovery.tier_of_provider_key("pixabay_video") == "keyed"
    assert discovery.tier_of_provider_key("nope") == "unknown"
    assert discovery.tier_of_provider("Openverse · flickr") == "keyless"
    assert discovery.tier_of_provider("Wikimedia Commons") == "keyless"
    assert discovery.tier_of_provider("Pexels") == "keyed"
    assert discovery.tier_of_provider("Pixabay") == "keyed"
