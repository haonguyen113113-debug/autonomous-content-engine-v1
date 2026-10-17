from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
import html
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen
import uuid

from .asset_intelligence import ResourceRequirement
from .ingest import ingest_one
from .registry import connect

try:  # Workstream-1 rights API (consume, never reinvent nor modify).
    from .rights_scope import (
        REQUIRED_HUMAN_REVIEW as _W1_HUMAN_REVIEW,
    )
    from .rights_scope import (
        default_deny_scope as _w1_default_deny_scope,
    )
    from .rights_scope import (
        build_rights_scope as _w1_build_rights_scope,
    )
    from .rights_scope import (
        ensure_rights_scope_schema as _w1_ensure_rights_scope_schema,
    )
    from .rights_scope import (
        is_usable_for as _w1_is_usable_for,
    )
    from .rights_scope import (
        scope_from_legacy as _w1_scope_from_legacy,
    )
    _RIGHTS_W1_AVAILABLE = True
except ImportError:  # Integrator removed/relocated the module: stay importable.
    _RIGHTS_W1_AVAILABLE = False
    _W1_HUMAN_REVIEW = "human_review"
    _w1_default_deny_scope = None  # type: ignore[assignment]
    _w1_build_rights_scope = None  # type: ignore[assignment]
    _w1_ensure_rights_scope_schema = None  # type: ignore[assignment]
    _w1_is_usable_for = None  # type: ignore[assignment]
    _w1_scope_from_legacy = None  # type: ignore[assignment]


COMMONS_API = "https://commons.wikimedia.org/w/api.php"
OPENVERSE_API = "https://api.openverse.org/v1"
PEXELS_API = "https://api.pexels.com"
PIXABAY_API = "https://pixabay.com/api"
PIXABAY_VIDEO_API = "https://pixabay.com/api/videos/"
COMMONS_USER_AGENT = "AutonomousContentEngine/0.1 (local asset discovery)"
MAX_RESULTS = 24
OPENVERSE_PAGE_SIZE = 20
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024
MAX_VIDEO_BYTES = 100 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
ALLOWED_VIDEO_TYPES = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/ogg": ".ogv",
}


class DiscoveryError(RuntimeError):
    """A provider search or candidate acquisition failed."""


def _openverse_request_json(url: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "Referer": "https://openverse.org/",
            "User-Agent": COMMONS_USER_AGENT,
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = response.read(4 * 1024 * 1024)
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise DiscoveryError(f"Openverse request failed: {error}") from error
    try:
        result = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DiscoveryError("Openverse returned invalid JSON.") from error
    if not isinstance(result, dict):
        raise DiscoveryError("Openverse returned an unexpected response.")
    return result


@dataclass(frozen=True)
class ExternalAssetCandidate:
    candidate_id: str
    provider: str
    title: str
    source_url: str
    thumbnail_url: str
    media_type: str
    mime_type: str
    width: int | None
    height: int | None
    size_bytes: int | None
    license_name: str | None
    license_url: str | None
    creator: str | None
    credit: str | None
    duration_seconds: int | None = None
    uploaded_at: str | None = None
    identity: str | None = None
    # Cost tier that served this candidate (Visibly-style data_source
    # transparency). Stamped by search_candidates_tiered; "unknown" when
    # the candidate came through the un-tiered search_candidates path.
    source_tier: str = "unknown"
    # --- Unified discovery interface (workstream 2, additive) ---
    # preview_url mirrors thumbnail_url so every consumer can rely on one
    # preview field regardless of provider. license mirrors license_name.
    # rights_scope is a workstream-1 scope dict (deny-default for
    # YouTube/unknown licenses, scope_from_legacy backfill otherwise) fed
    # straight into is_usable_for by the planner (candidate_rights_decision).
    # match_grade is "exact" (footage of the named match/player) or
    # "generic" (general football footage). verification_status starts
    # "unverified" and only becomes "verified" after human rights review.
    preview_url: str = ""
    license: str | None = None
    rights_scope: dict[str, Any] = field(default_factory=dict)
    match_grade: str = "generic"
    verification_status: str = "unverified"

    def __post_init__(self) -> None:
        if not self.preview_url and self.thumbnail_url:
            object.__setattr__(self, "preview_url", self.thumbnail_url)
        if self.license is None and self.license_name:
            object.__setattr__(self, "license", self.license_name)
        if not self.rights_scope:
            referral = self.candidate_id.startswith(REFERRAL_ONLY_PREFIXES) or (
                "referral only" in (self.provider or "").lower()
            )
            object.__setattr__(
                self,
                "rights_scope",
                _scope_for_candidate(
                    license_name=self.license_name,
                    provider=self.provider,
                    source_url=self.source_url,
                    creator=self.creator,
                    credit=self.credit,
                    referral_only=referral,
                ),
            )
        if self.match_grade not in {"exact", "generic"}:
            object.__setattr__(self, "match_grade", "generic")
        if self.verification_status not in {"unverified", "pending", "verified"}:
            object.__setattr__(self, "verification_status", "unverified")

    @property
    def media_kind(self) -> str:
        """Lowercase media kind (image|video) for the unified interface."""
        return (self.media_type or "").lower()

    def to_unified_dict(self) -> dict[str, Any]:
        """Spec-shaped view: {provider, source_url, preview_url, media_type,
        license, creator, rights_scope, match_grade, verification_status}."""
        return {
            "provider": self.provider,
            "source_url": self.source_url,
            "preview_url": self.preview_url or self.thumbnail_url,
            "media_type": self.media_kind,
            "license": self.license if self.license is not None else self.license_name,
            "creator": self.creator,
            "rights_scope": dict(self.rights_scope) if self.rights_scope else _fallback_deny(
                "rights scope missing — human review required."),
            "match_grade": self.match_grade,
            "verification_status": self.verification_status,
        }


def _license_label(license_code: Any, version: Any) -> str | None:
    if not isinstance(license_code, str) or not license_code:
        return None
    labels = {
        "by": "CC BY",
        "by-sa": "CC BY-SA",
        "cc0": "CC0",
        "pdm": "Public Domain Mark",
    }
    label = labels.get(license_code.lower(), license_code.upper())
    return f"{label} {version}" if version else label


def _candidate_from_openverse(item: dict[str, Any]) -> ExternalAssetCandidate | None:
    image_url = str(item.get("url", ""))
    preview_url = str(item.get("thumbnail", ""))
    media_url = urlparse(image_url)
    preview = urlparse(preview_url)
    license_code = str(item.get("license", "")).lower()
    # Monetized content needs licenses that allow commercial reuse. Keep the
    # license link and attribution visible so the user can make the final call.
    if license_code not in {"by", "by-sa", "cc0", "pdm"}:
        return None
    if media_url.scheme != "https" or preview.scheme != "https":
        return None
    if preview.hostname != "api.openverse.org":
        return None
    width = item.get("width")
    height = item.get("height")
    if not isinstance(width, int) or not isinstance(height, int):
        return None
    if max(width, height) < 1000:
        return None
    candidate_uuid = str(item.get("id", ""))
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", candidate_uuid):
        return None
    landing_url = str(item.get("foreign_landing_url", ""))
    if urlparse(landing_url).scheme != "https":
        return None
    source = str(item.get("source", "Openverse"))
    return ExternalAssetCandidate(
        candidate_id=f"openverse:{candidate_uuid}",
        provider=f"Openverse · {source}",
        title=str(item.get("title") or "Untitled image"),
        source_url=landing_url,
        thumbnail_url=preview_url,
        media_type="IMAGE",
        mime_type="image/unknown",
        width=width,
        height=height,
        size_bytes=item.get("filesize") if isinstance(item.get("filesize"), int) else None,
        license_name=_license_label(license_code, item.get("license_version")),
        license_url=str(item.get("license_url", "")) or None,
        creator=_clean_metadata(item.get("creator")),
        credit=_clean_metadata(item.get("attribution")),
    )


def _search_openverse_page(
    query: str,
    *,
    excluded_sources: tuple[str, ...] = (),
) -> list[ExternalAssetCandidate]:
    params: dict[str, str | int] = {
        "q": query,
        "page_size": OPENVERSE_PAGE_SIZE,
        "license_type": "commercial",
        "size": "large",
    }
    if excluded_sources:
        params["excluded_source"] = ",".join(excluded_sources)
    response = _openverse_request_json(f"{OPENVERSE_API}/images/?{urlencode(params)}")
    results = response.get("results", [])
    if not isinstance(results, list):
        return []
    candidates: list[ExternalAssetCandidate] = []
    for item in results:
        if isinstance(item, dict):
            candidate = _candidate_from_openverse(item)
            if candidate:
                candidates.append(candidate)
    return candidates


def _clean_metadata(value: Any) -> str | None:
    if isinstance(value, dict):
        value = value.get("value")
    if not isinstance(value, str):
        return None
    plain = html.unescape(re.sub(r"<[^>]*>", " ", value))
    plain = " ".join(plain.split())
    return plain or None


def _candidate_from_page(page: dict[str, Any]) -> ExternalAssetCandidate | None:
    image_info = (page.get("imageinfo") or [{}])[0]
    mime_type = str(image_info.get("mime", ""))
    if mime_type not in ALLOWED_IMAGE_TYPES:
        return None

    metadata = image_info.get("extmetadata") or {}
    return ExternalAssetCandidate(
        candidate_id=str(page.get("pageid", "")),
        provider="Wikimedia Commons",
        title=str(page.get("title", "")).removeprefix("File:"),
        source_url=str(image_info.get("descriptionurl", "")),
        thumbnail_url=str(image_info.get("thumburl", "")),
        media_type="IMAGE",
        mime_type=mime_type,
        width=image_info.get("width"),
        height=image_info.get("height"),
        size_bytes=image_info.get("size"),
        license_name=_clean_metadata(metadata.get("LicenseShortName")),
        license_url=_clean_metadata(metadata.get("LicenseUrl")),
        creator=_clean_metadata(metadata.get("Artist")),
        credit=_clean_metadata(metadata.get("Credit")),
        uploaded_at=_commons_uploaded_at(image_info),
    )


def _request_json(url: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": COMMONS_USER_AGENT,
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = response.read(2 * 1024 * 1024)
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise DiscoveryError(f"Wikimedia Commons request failed: {error}") from error

    try:
        result = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DiscoveryError("Wikimedia Commons returned invalid JSON.") from error
    if not isinstance(result, dict):
        raise DiscoveryError("Wikimedia Commons returned an unexpected response.")
    if "error" in result:
        message = result["error"].get("info", "Provider returned an error.")
        raise DiscoveryError(str(message))
    return result


def _commons_file_pages(gsrsearch: str, *, limit: int) -> list[dict[str, Any]]:
    """Shared Commons file search over the File namespace."""
    params = urlencode(
        {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "generator": "search",
            "gsrnamespace": 6,
            "gsrsearch": gsrsearch,
            "gsrlimit": limit,
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|size|mime|mediatype|timestamp",
            "iiurlwidth": 480,
        }
    )
    response = _request_json(f"{COMMONS_API}?{params}")
    pages = response.get("query", {}).get("pages", [])
    if not isinstance(pages, list):
        return []
    return [page for page in pages if isinstance(page, dict)]


def search_commons_images(
    query: str,
    *,
    limit: int = 8,
) -> list[ExternalAssetCandidate]:
    normalized_query = " ".join(query.split())
    if not normalized_query:
        raise ValueError("Search query is required.")
    if len(normalized_query) > 250:
        raise ValueError("Search query must be 250 characters or fewer.")
    if not 1 <= limit <= MAX_RESULTS:
        raise ValueError(f"Result limit must be between 1 and {MAX_RESULTS}.")

    candidates: list[ExternalAssetCandidate] = []
    for page in _commons_file_pages(normalized_query, limit=limit):
        candidate = _candidate_from_page(page)
        if (
            candidate is not None
            and candidate.candidate_id
            and candidate.source_url.startswith("https://commons.wikimedia.org/")
            and urlparse(candidate.thumbnail_url).hostname
            in {"thumb.wikimedia.org", "upload.wikimedia.org"}
        ):
            candidates.append(candidate)
    return candidates


def search_image_candidates(
    query: str,
    *,
    limit: int = 24,
) -> list[ExternalAssetCandidate]:
    """Search Openverse broadly, then exclude its dominant source for variety."""

    normalized_query = " ".join(query.split())
    if not normalized_query:
        raise ValueError("Search query is required.")
    if len(normalized_query) > 250:
        raise ValueError("Search query must be 250 characters or fewer.")
    if not 1 <= limit <= MAX_RESULTS:
        raise ValueError(f"Result limit must be between 1 and {MAX_RESULTS}.")

    try:
        primary = _search_openverse_page(normalized_query)
    except DiscoveryError as error:
        try:
            return search_commons_images(normalized_query, limit=min(limit, 12))
        except DiscoveryError:
            raise error

    by_source: dict[str, int] = {}
    for candidate in primary:
        source = candidate.provider.rsplit(" · ", 1)[-1]
        by_source[source] = by_source.get(source, 0) + 1
    streams = [primary]
    excluded_sources: list[str] = []
    if primary and max(by_source.values()) >= max(3, len(primary) // 2):
        dominant_source = max(by_source, key=by_source.get)
        excluded_sources.append(dominant_source)
        try:
            alternate = _search_openverse_page(
                normalized_query,
                excluded_sources=tuple(excluded_sources),
            )
            streams.append(alternate)
        except DiscoveryError:
            alternate = []

        alternate_counts: dict[str, int] = {}
        for candidate in alternate:
            source = candidate.provider.rsplit(" · ", 1)[-1]
            alternate_counts[source] = alternate_counts.get(source, 0) + 1
        if alternate_counts and max(alternate_counts.values()) >= max(3, len(alternate) // 2):
            alternate_dominant = max(alternate_counts, key=alternate_counts.get)
            if alternate_dominant not in excluded_sources:
                excluded_sources.append(alternate_dominant)
                try:
                    tertiary = _search_openverse_page(
                        normalized_query,
                        excluded_sources=tuple(excluded_sources),
                    )
                    streams.append(tertiary)
                except DiscoveryError:
                    pass

    # Interleave the two provider mixes so one indexed source cannot dominate
    # every row. De-duplicate the same landing page across both result sets.
    mixed: list[ExternalAssetCandidate] = []
    seen_urls: set[str] = set()
    while len(mixed) < limit:
        progressed = False
        for candidates in streams:
            for candidate in candidates:
                key = candidate.source_url.casefold()
                if key not in seen_urls:
                    seen_urls.add(key)
                    mixed.append(candidate)
                    progressed = True
                    break
            if len(mixed) >= limit:
                break
        if not progressed:
            break

    # Keep Commons as a working fallback and a supplemental source when the
    # aggregate index returns too few eligible, sufficiently large images.
    if len(mixed) < limit:
        try:
            for candidate in search_commons_images(
                normalized_query,
                limit=min(12, limit - len(mixed)),
            ):
                key = candidate.source_url.casefold()
                if key not in seen_urls:
                    seen_urls.add(key)
                    mixed.append(candidate)
                    if len(mixed) >= limit:
                        break
        except DiscoveryError:
            if not mixed:
                raise
    return mixed


def _pexels_key(api_keys: dict | None) -> str | None:
    if api_keys and api_keys.get("PEXELS_API_KEY"):
        return str(api_keys["PEXELS_API_KEY"])
    return os.environ.get("PEXELS_API_KEY") or None


def _pixabay_key(api_keys: dict | None) -> str | None:
    if api_keys and api_keys.get("PIXABAY_API_KEY"):
        return str(api_keys["PIXABAY_API_KEY"])
    return os.environ.get("PIXABAY_API_KEY") or None


def _require_pexels_key(api_keys: dict | None) -> str:
    key = _pexels_key(api_keys)
    if not key:
        raise DiscoveryError("Pexels needs a free API key (PEXELS_API_KEY).")
    return key


def _candidate_by_id(
    candidate_id: str,
    api_keys: dict | None = None,
) -> ExternalAssetCandidate:
    if candidate_id.startswith("openverse:"):
        candidate_uuid = candidate_id.removeprefix("openverse:")
        if not re.fullmatch(r"[0-9a-fA-F-]{36}", candidate_uuid):
            raise ValueError("Invalid Openverse candidate ID.")
        detail = _openverse_request_json(f"{OPENVERSE_API}/images/{candidate_uuid}/")
        candidate = _candidate_from_openverse(detail)
        if candidate is None:
            raise DiscoveryError("The selected Openverse image is no longer eligible.")
        return candidate
    if candidate_id.startswith("pexels:"):
        return _pexels_photo_detail(
            candidate_id.removeprefix("pexels:"),
            _require_pexels_key(api_keys),
        )
    if candidate_id.startswith("pexels-video:"):
        return _pexels_video_detail(
            candidate_id.removeprefix("pexels-video:"),
            _require_pexels_key(api_keys),
        )
    if candidate_id.startswith("pixabay:"):
        return _pixabay_photo_detail(
            candidate_id.removeprefix("pixabay:"),
            _require_pixabay_key(api_keys),
        )
    if candidate_id.startswith("pixabay-video:"):
        return _pixabay_video_detail(
            candidate_id.removeprefix("pixabay-video:"),
            _require_pixabay_key(api_keys),
        )
    if candidate_id.startswith("youtube:"):
        raise DiscoveryError(
            "YouTube is referral-only: open the watch page to identify the "
            "rights holder. YouTube videos are never saved as assets and "
            "never granted rights by default."
        )
    if candidate_id.startswith("archive:"):
        return _archive_detail(candidate_id.removeprefix("archive:"))
    if not candidate_id.isdigit():
        raise ValueError("Invalid external candidate ID.")

    params = urlencode(
        {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "pageids": candidate_id,
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|size|mime|mediatype|timestamp",
            "iiurlwidth": 480,
        }
    )
    response = _request_json(f"{COMMONS_API}?{params}")
    pages = response.get("query", {}).get("pages", [])
    if not pages or not isinstance(pages[0], dict):
        raise DiscoveryError("The selected Commons candidate no longer exists.")
    image_info = (pages[0].get("imageinfo") or [{}])[0]
    mime = str(image_info.get("mime", ""))
    if mime in ALLOWED_IMAGE_TYPES:
        candidate = _candidate_from_page(pages[0])
    elif mime in ALLOWED_VIDEO_TYPES:
        candidate = _candidate_from_video_page(pages[0])
    else:
        raise DiscoveryError("The selected candidate is not a supported media type.")
    if candidate is None:
        raise DiscoveryError("The selected candidate is not a supported media type.")
    if not candidate.source_url.startswith("https://commons.wikimedia.org/"):
        raise DiscoveryError("The selected candidate has an invalid source URL.")
    thumb_host = urlparse(candidate.thumbnail_url).hostname if candidate.thumbnail_url else None
    if thumb_host not in {"thumb.wikimedia.org", "upload.wikimedia.org", None}:
        raise DiscoveryError("The selected candidate has an invalid media URL.")
    return candidate


def _download_pinned_image(file_url: str, allowed_hosts: set[str]) -> tuple[bytes, str]:
    """Download an image re-resolved at save time from a pinned file host."""
    _validate_public_https_url(file_url)
    request = Request(file_url, headers={"User-Agent": COMMONS_USER_AGENT})
    opener = build_opener(_PublicHttpsRedirectHandler())
    try:
        with opener.open(request, timeout=30) as response:
            final_url = response.geturl()
            if urlparse(final_url).hostname not in allowed_hosts:
                raise DiscoveryError("Image download left the approved media host.")
            _validate_public_https_url(final_url)
            mime_type = response.headers.get_content_type().lower()
            if mime_type not in ALLOWED_IMAGE_TYPES:
                raise DiscoveryError(f"Unsupported image MIME type: {mime_type}")
            declared_size = response.headers.get("Content-Length")
            if declared_size and int(declared_size) > MAX_DOWNLOAD_BYTES:
                raise DiscoveryError("Image exceeds the 20 MiB download limit.")
            data = response.read(MAX_DOWNLOAD_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
        if isinstance(error, DiscoveryError):
            raise
        raise DiscoveryError(f"Provider image download failed: {error}") from error
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise DiscoveryError("Image exceeds the 20 MiB download limit.")
    return data, mime_type


def _download_candidate(
    candidate: ExternalAssetCandidate,
    api_keys: dict | None = None,
) -> tuple[bytes, str]:
    if is_referral_only(candidate):
        raise DiscoveryError(
            "YouTube is referral-only: open the watch page to identify the "
            "rights holder. YouTube videos are never downloaded as assets."
        )
    if candidate.candidate_id.startswith("archive:"):
        return _download_archive_candidate(candidate)
    if candidate.media_type == "VIDEO":
        return _download_video_candidate(candidate, api_keys)
    if candidate.candidate_id.startswith("openverse:"):
        return _download_openverse_candidate(candidate.candidate_id.removeprefix("openverse:"))
    if candidate.candidate_id.startswith("pixabay:"):
        file_url, _ = _pixabay_file_url(
            candidate.candidate_id.removeprefix("pixabay:"),
            _require_pixabay_key(api_keys),
            video=False,
        )
        return _download_pinned_image(file_url, {"pixabay.com"})
    image_info_url = _candidate_image_url(candidate.candidate_id)
    request = Request(
        image_info_url,
        headers={"User-Agent": COMMONS_USER_AGENT},
    )
    try:
        with urlopen(request, timeout=30) as response:
            final_host = urlparse(response.geturl()).hostname
            if final_host != "upload.wikimedia.org":
                raise DiscoveryError("Image download left the approved media host.")
            mime_type = response.headers.get_content_type().lower()
            if mime_type not in ALLOWED_IMAGE_TYPES:
                raise DiscoveryError(f"Unsupported image MIME type: {mime_type}")
            declared_size = response.headers.get("Content-Length")
            if declared_size and int(declared_size) > MAX_DOWNLOAD_BYTES:
                raise DiscoveryError("Image exceeds the 20 MiB download limit.")
            data = response.read(MAX_DOWNLOAD_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
        raise DiscoveryError(f"Image download failed: {error}") from error

    if len(data) > MAX_DOWNLOAD_BYTES:
        raise DiscoveryError("Image exceeds the 20 MiB download limit.")
    return data, mime_type


def _validate_public_https_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise DiscoveryError("Image URL must use HTTPS.")
    try:
        port = parsed.port or 443
    except ValueError as error:
        raise DiscoveryError("Image URL has an invalid port.") from error
    if port != 443 or parsed.username or parsed.password:
        raise DiscoveryError("Image URL has an invalid authority.")
    try:
        addresses = {
            ipaddress.ip_address(item[4][0])
            for item in socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
        }
    except (OSError, ValueError) as error:
        raise DiscoveryError("Image host could not be resolved.") from error
    if not addresses or any(not address.is_global for address in addresses):
        raise DiscoveryError("Image URL must resolve to a public host.")


class _PublicHttpsRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request: Request, file: Any, code: int, message: str, headers: Any, new_url: str) -> Request | None:
        _validate_public_https_url(new_url)
        return super().redirect_request(request, file, code, message, headers, new_url)


def _download_openverse_candidate(candidate_uuid: str) -> tuple[bytes, str]:
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", candidate_uuid):
        raise ValueError("Invalid Openverse candidate ID.")
    detail = _openverse_request_json(f"{OPENVERSE_API}/images/{candidate_uuid}/")
    candidate = _candidate_from_openverse(detail)
    if candidate is None:
        raise DiscoveryError("The selected Openverse image is no longer eligible.")
    image_url = str(detail.get("url", ""))
    _validate_public_https_url(image_url)
    request = Request(image_url, headers={"User-Agent": COMMONS_USER_AGENT})
    opener = build_opener(_PublicHttpsRedirectHandler())
    try:
        with opener.open(request, timeout=30) as response:
            _validate_public_https_url(response.geturl())
            mime_type = response.headers.get_content_type().lower()
            declared_size = response.headers.get("Content-Length")
            if declared_size and int(declared_size) > MAX_DOWNLOAD_BYTES:
                raise DiscoveryError("Image exceeds the 20 MiB download limit.")
            data = response.read(MAX_DOWNLOAD_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
        if isinstance(error, DiscoveryError):
            raise
        raise DiscoveryError(f"Openverse image download failed: {error}") from error
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise DiscoveryError("Image exceeds the 20 MiB download limit.")
    signatures = {
        "image/jpeg": (b"\xff\xd8\xff", ".jpg"),
        "image/png": (b"\x89PNG\r\n\x1a\n", ".png"),
        "image/gif": (b"GIF87a", ".gif"),
        "image/webp": (b"RIFF", ".webp"),
    }
    if mime_type == "image/webp" and data[8:12] != b"WEBP":
        raise DiscoveryError("Downloaded file is not a valid WebP image.")
    if mime_type not in signatures:
        # Some public image hosts send application/octet-stream; identify a
        # supported raster format from its file signature instead.
        mime_type = next(
            (
                candidate_type
                for candidate_type, (signature, _) in signatures.items()
                if data.startswith(signature)
            ),
            "",
        )
    if not mime_type or not data.startswith(signatures[mime_type][0]):
        raise DiscoveryError("Downloaded file is not a supported raster image.")
    return data, mime_type


def _candidate_image_url(candidate_id: str) -> str:
    params = urlencode(
        {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "pageids": candidate_id,
            "prop": "imageinfo",
            "iiprop": "url|mime",
        }
    )
    response = _request_json(f"{COMMONS_API}?{params}")
    pages = response.get("query", {}).get("pages", [])
    if not pages or not isinstance(pages[0], dict):
        raise DiscoveryError("The selected Commons candidate no longer exists.")
    image_info = (pages[0].get("imageinfo") or [{}])[0]
    image_url = str(image_info.get("url", ""))
    if urlparse(image_url).hostname != "upload.wikimedia.org":
        raise DiscoveryError("The selected candidate has an invalid media URL.")
    return image_url


def save_commons_candidate(
    project_root: Path,
    candidate_id: str,
    requirement: ResourceRequirement,
    *,
    rights_reviewed: bool,
    api_keys: dict | None = None,
) -> dict[str, Any]:
    """Download and ingest a user-selected external candidate (image or video)."""

    if requirement.resource_type not in {"image", "video"}:
        raise ValueError("External providers only support image and video requests.")

    if candidate_id.startswith(REFERRAL_ONLY_PREFIXES):
        raise DiscoveryError(
            "YouTube is referral-only: open the watch page to identify the "
            "rights holder. YouTube videos are never saved as assets and "
            "never granted rights by default."
        )

    candidate = _candidate_by_id(candidate_id, api_keys)
    expected = "VIDEO" if requirement.resource_type == "video" else "IMAGE"
    if candidate.media_type != expected:
        raise ValueError("Candidate type does not match the resource requirement.")
    data, mime_type = _download_candidate(candidate, api_keys)
    extensions = {**ALLOWED_IMAGE_TYPES, **ALLOWED_VIDEO_TYPES}
    extension = extensions[mime_type]
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(candidate.title).stem)
    safe_stem = safe_stem.strip(".-_")[:80] or "external-media"
    inbox = project_root / "runtime/assets/inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    local_path = inbox / f"{safe_stem}-{uuid.uuid4().hex[:8]}{extension}"
    sidecar_path = local_path.with_suffix(local_path.suffix + ".json")

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    source_type = (
        "openverse" if candidate_id.startswith("openverse:")
        else "pexels" if candidate_id.startswith("pexels")
        else "pixabay" if candidate_id.startswith("pixabay")
        else "internet_archive" if candidate_id.startswith("archive:")
        else "wikimedia_commons"
    )
    sidecar = {
        "source_type": source_type,
        "source_url": candidate.source_url,
        "creator": candidate.creator,
        "license_type": candidate.license_name,
        "rights_state": "verified" if rights_reviewed else "unverified",
        "lifecycle_state": "active" if rights_reviewed else "ingested",
        "purpose_code": requirement.purpose,
        "subject_id": requirement.entity_id,
        "metadata": {
            "contexts": [requirement.context] if requirement.context else [],
            "originating_content_objective": requirement.content_objective,
            "candidate_id": candidate.candidate_id,
            "discovery_provider": candidate.provider,
            "license_url": candidate.license_url,
            "license_credit": candidate.credit,
            "rights_reviewed_by_user": rights_reviewed,
            "rights_reviewed_at": now if rights_reviewed else None,
            "downloaded_at": now,
            "uploaded_at": candidate.uploaded_at,
            "mime_type": mime_type,
        },
    }

    try:
        local_path.write_bytes(data)
        sidecar_path.write_text(
            json.dumps(sidecar, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        result = ingest_one(
            inbox,
            project_root / "runtime/assets/library",
            project_root / "runtime/engine.db",
            local_path,
        )
    except Exception:
        local_path.unlink(missing_ok=True)
        sidecar_path.unlink(missing_ok=True)
        raise

    if result.startswith("ingested:"):
        asset_id = result.removeprefix("ingested:")
        scope_persisted = False
        scope_summary: dict[str, Any] | None = None
        if _RIGHTS_W1_AVAILABLE:
            try:
                if rights_reviewed:
                    # Credit comes from the sidecar metadata (license_credit)
                    # or the candidate credit; never inferred beyond that.
                    credit = (
                        sidecar.get("metadata", {}).get("license_credit")
                        or candidate.credit
                    )
                    scope = _w1_build_rights_scope(
                        platforms=["youtube", "tiktok", "facebook", "instagram"],
                        territories=["*"],
                        commercial=True,
                        monetization=True,
                        edit_allowed=True,
                        credit_required=bool(credit),
                        credit_text=credit,
                        license=sidecar.get("license_type"),
                        source=sidecar.get("source_type"),
                        reviewed_by="human",
                        reviewed_at=now,
                        copyright_exception=False,
                        notes="human-reviewed grant persisted at save",
                    )
                else:
                    scope = _w1_default_deny_scope(
                        license=sidecar.get("license_type"),
                        source=sidecar.get("source_type"),
                        notes="not rights-reviewed; deny by default",
                    )
            except ValueError:
                # Review data is insufficient to build a grant: do not infer
                # rights, deny by default so usage stays gated until a human
                # records a valid scope.
                scope = _w1_default_deny_scope(
                    license=sidecar.get("license_type"),
                    source=sidecar.get("source_type"),
                    notes="not rights-reviewed; deny by default",
                )
            try:
                conn = connect(project_root / "runtime/engine.db")
                try:
                    _w1_ensure_rights_scope_schema(conn)
                    conn.execute(
                        "UPDATE assets SET rights_scope_json = ? WHERE asset_id = ?",
                        (json.dumps(scope, ensure_ascii=False), asset_id),
                    )
                    conn.commit()
                finally:
                    conn.close()
                scope_persisted = True
                scope_summary = scope
            except (sqlite3.Error, OSError):
                # Asset was ingested; rights persistence is best-effort and
                # must not roll back a successful save.
                scope_persisted = False
        return {
            "status": "SAVED",
            "asset_id": asset_id,
            "rights_state": sidecar["rights_state"],
            "candidate": asdict(candidate),
            "rights_scope_persisted": scope_persisted,
            "rights_scope": scope_summary,
        }
    if result.startswith("duplicate:"):
        local_path.unlink(missing_ok=True)
        sidecar_path.unlink(missing_ok=True)
        return {
            "status": "ALREADY_IN_LIBRARY",
            "asset_id": result.removeprefix("duplicate:"),
            "rights_state": "existing_record_unchanged",
            "candidate": asdict(candidate),
        }
    raise DiscoveryError(f"Asset ingest did not complete: {result}")


# ---------------------------------------------------------------------------
# Expanded provider scope: keyless video (Wikimedia Commons) plus optional
# keyed providers (Pexels images + video). Keyed providers stay dormant until
# the owner configures a free key; the UI reports them as needing setup
# instead of failing silently.
# ---------------------------------------------------------------------------

def provider_status(api_keys: dict | None = None) -> list[dict[str, str]]:
    """Report every discovery provider and whether it can run right now."""
    pexels_ready = bool(_pexels_key(api_keys))
    pixabay_ready = bool(_pixabay_key(api_keys))
    return [
        {"key": "openverse_image", "label": "Openverse", "media": "image", "state": "ready",
         "acquisition": "download"},
        {"key": "commons_image", "label": "Wikimedia Commons", "media": "image", "state": "ready",
         "acquisition": "download"},
        {"key": "commons_video", "label": "Wikimedia Commons", "media": "video", "state": "ready",
         "acquisition": "download"},
        {"key": "archive_image", "label": "Internet Archive", "media": "image", "state": "ready",
         "acquisition": "download"},
        {"key": "archive_video", "label": "Internet Archive", "media": "video", "state": "ready",
         "acquisition": "download"},
        {"key": "youtube_referral", "label": "YouTube (referral only)", "media": "video",
         "state": "ready", "acquisition": "referral_only"},
        {"key": "pexels_image", "label": "Pexels", "media": "image",
         "state": "ready" if pexels_ready else "needs_key",
         "acquisition": "download"},
        {"key": "pexels_video", "label": "Pexels", "media": "video",
         "state": "ready" if pexels_ready else "needs_key",
         "acquisition": "download"},
        {"key": "pixabay_image", "label": "Pixabay", "media": "image",
         "state": "ready" if pixabay_ready else "needs_key",
         "acquisition": "download"},
        {"key": "pixabay_video", "label": "Pixabay", "media": "video",
         "state": "ready" if pixabay_ready else "needs_key",
         "acquisition": "download"},
    ]


def _pexels_get_json(path: str, key: str) -> dict[str, Any]:
    request = Request(
        f"{PEXELS_API}{path}",
        headers={"Authorization": key, "Accept": "application/json",
                 "User-Agent": COMMONS_USER_AGENT},
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = response.read(4 * 1024 * 1024)
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise DiscoveryError(f"Pexels request failed: {error}") from error
    try:
        result = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DiscoveryError("Pexels returned invalid JSON.") from error
    if not isinstance(result, dict):
        raise DiscoveryError("Pexels returned an unexpected response.")
    if "error" in result:
        raise DiscoveryError(f"Pexels error: {result.get('error')}")
    return result


def _pexels_photo_candidate(item: dict[str, Any]) -> ExternalAssetCandidate | None:
    try:
        photo_id = int(item.get("id", 0))
    except (TypeError, ValueError):
        return None
    if photo_id <= 0:
        return None
    src = item.get("src", {})
    if not isinstance(src, dict) or urlparse(str(src.get("original", ""))).scheme != "https":
        return None
    width = item.get("width")
    height = item.get("height")
    if not isinstance(width, int) or not isinstance(height, int):
        return None
    if max(width, height) < 1000:
        return None
    photographer = _clean_metadata(item.get("photographer"))
    return ExternalAssetCandidate(
        candidate_id=f"pexels:{photo_id}",
        provider="Pexels",
        title=str(item.get("alt") or "Untitled photo"),
        source_url=str(item.get("url", "")) or f"https://www.pexels.com/photo/{photo_id}/",
        thumbnail_url=str(src.get("medium", "")),
        media_type="IMAGE",
        mime_type="image/jpeg",
        width=width,
        height=height,
        size_bytes=None,
        license_name="Pexels License",
        license_url="https://www.pexels.com/license/",
        creator=photographer,
        credit=f"Photo by {photographer} on Pexels" if photographer else "Photo from Pexels",
    )


def _best_pexels_file(files: Any) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    if not isinstance(files, list):
        return None
    for entry in files:
        if not isinstance(entry, dict):
            continue
        if entry.get("file_type") != "video/mp4":
            continue
        try:
            width = int(entry.get("width", 0))
        except (TypeError, ValueError):
            continue
        if urlparse(str(entry.get("link", ""))).scheme != "https":
            continue
        if width <= 1920:
            current = int(best.get("width", 0) or 0) if best else 0
            if best is None or current > 1920 or width > current:
                best = entry
        elif best is None:
            best = entry
    return best


def _pexels_video_candidate(item: dict[str, Any]) -> ExternalAssetCandidate | None:
    try:
        video_id = int(item.get("id", 0))
    except (TypeError, ValueError):
        return None
    if video_id <= 0:
        return None
    chosen = _best_pexels_file(item.get("video_files"))
    if chosen is None:
        return None
    try:
        duration = int(item.get("duration", 0)) or None
    except (TypeError, ValueError):
        duration = None
    user = item.get("user", {})
    creator = _clean_metadata(user.get("name")) if isinstance(user, dict) else None
    return ExternalAssetCandidate(
        candidate_id=f"pexels-video:{video_id}",
        provider="Pexels",
        title=f"Video {video_id}",
        source_url=str(item.get("url", "")) or f"https://www.pexels.com/video/{video_id}/",
        thumbnail_url=str(item.get("image", "")),
        media_type="VIDEO",
        mime_type="video/mp4",
        width=chosen.get("width") if isinstance(chosen.get("width"), int) else None,
        height=chosen.get("height") if isinstance(chosen.get("height"), int) else None,
        size_bytes=None,
        license_name="Pexels License",
        license_url="https://www.pexels.com/license/",
        creator=creator,
        credit=f"Video by {creator} on Pexels" if creator else "Video from Pexels",
        duration_seconds=duration,
    )


def _search_pexels_images(
    query: str, key: str, limit: int, orientation: str | None = None,
) -> list[ExternalAssetCandidate]:
    params = {"query": query, "per_page": min(limit, 20), "size": "large"}
    if orientation in {"landscape", "portrait", "square"}:
        params["orientation"] = orientation
    response = _pexels_get_json(f"/v1/search?{urlencode(params)}", key)
    photos = response.get("photos", [])
    if not isinstance(photos, list):
        return []
    candidates = []
    for item in photos:
        if isinstance(item, dict):
            candidate = _pexels_photo_candidate(item)
            if candidate is not None:
                candidates.append(candidate)
    return candidates


def _search_pexels_videos(
    query: str, key: str, limit: int, orientation: str | None = None,
) -> list[ExternalAssetCandidate]:
    params = {"query": query, "per_page": min(limit, 20), "size": "large"}
    if orientation in {"landscape", "portrait", "square"}:
        params["orientation"] = orientation
    response = _pexels_get_json(f"/v1/videos/search?{urlencode(params)}", key)
    videos = response.get("videos", [])
    if not isinstance(videos, list):
        return []
    candidates = []
    for item in videos:
        if isinstance(item, dict):
            candidate = _pexels_video_candidate(item)
            if candidate is not None:
                candidates.append(candidate)
    return candidates


def _pexels_photo_detail(photo_id: str, key: str) -> ExternalAssetCandidate:
    if not photo_id.isdigit():
        raise ValueError("Invalid Pexels candidate ID.")
    detail = _pexels_get_json(f"/v1/photos/{photo_id}", key)
    candidate = _pexels_photo_candidate(detail)
    if candidate is None:
        raise DiscoveryError("The selected Pexels photo is no longer eligible.")
    return candidate


def _pexels_video_detail(video_id: str, key: str) -> ExternalAssetCandidate:
    if not video_id.isdigit():
        raise ValueError("Invalid Pexels candidate ID.")
    try:
        detail = _pexels_get_json(f"/v1/videos/videos/{video_id}", key)
    except DiscoveryError as error:
        raise DiscoveryError("The selected Pexels video is no longer eligible.") from error
    candidate = _pexels_video_candidate(detail)
    if candidate is None:
        raise DiscoveryError("The selected Pexels video is no longer eligible.")
    return candidate


def _pexels_video_file_url(video_id: str, key: str) -> str:
    detail = _pexels_get_json(f"/v1/videos/videos/{video_id}", key)
    chosen = _best_pexels_file(detail.get("video_files"))
    if chosen is None:
        raise DiscoveryError("The selected Pexels video has no downloadable file.")
    return str(chosen["link"])


def _pixabay_get_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json",
                                    "User-Agent": COMMONS_USER_AGENT})
    try:
        with urlopen(request, timeout=20) as response:
            payload = response.read(4 * 1024 * 1024)
    except HTTPError as error:
        raise DiscoveryError(f"Pixabay request failed with HTTP {error.code}.") from error
    except (URLError, TimeoutError, OSError) as error:
        raise DiscoveryError(f"Pixabay request failed: {error}") from error
    try:
        result = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DiscoveryError("Pixabay returned invalid JSON.") from error
    if not isinstance(result, dict):
        raise DiscoveryError("Pixabay returned an unexpected response.")
    return result


def _require_pixabay_key(api_keys: dict | None) -> str:
    key = _pixabay_key(api_keys)
    if not key:
        raise DiscoveryError("Pixabay needs a free API key (PIXABAY_API_KEY).")
    return key


def _pixabay_photo_candidate(item: dict[str, Any]) -> ExternalAssetCandidate | None:
    try:
        photo_id = int(item.get("id", 0))
    except (TypeError, ValueError):
        return None
    if photo_id <= 0:
        return None
    file_url = str(item.get("largeImageURL", ""))
    if urlparse(file_url).scheme != "https":
        return None
    try:
        width = int(item.get("imageWidth", 0))
        height = int(item.get("imageHeight", 0))
    except (TypeError, ValueError):
        return None
    if max(width, height) < 1000:
        return None
    creator = _clean_metadata(item.get("user"))
    tags = _clean_metadata(item.get("tags")) or f"Pixabay photo {photo_id}"
    return ExternalAssetCandidate(
        candidate_id=f"pixabay:{photo_id}",
        provider="Pixabay",
        title=tags[:120],
        source_url=str(item.get("pageURL", "")) or f"https://pixabay.com/photos/{photo_id}/",
        thumbnail_url=str(item.get("previewURL", "")),
        media_type="IMAGE",
        mime_type="image/jpeg",
        width=width,
        height=height,
        size_bytes=item.get("imageSize") if isinstance(item.get("imageSize"), int) else None,
        license_name="Pixabay Content License",
        license_url="https://pixabay.com/service/license-summary/",
        creator=creator,
        credit=f"Image by {creator} on Pixabay" if creator else "Image from Pixabay",
    )


def _best_pixabay_rendition(entry: dict[str, Any]) -> dict[str, Any] | None:
    videos = entry.get("videos", {})
    if not isinstance(videos, dict):
        return None
    for size in ("medium", "small", "large", "tiny"):
        rendition = videos.get(size, {})
        if not isinstance(rendition, dict):
            continue
        if urlparse(str(rendition.get("url", ""))).scheme != "https":
            continue
        try:
            width = int(rendition.get("width", 0))
            height = int(rendition.get("height", 0))
        except (TypeError, ValueError):
            continue
        if width <= 0 or height <= 0:
            continue
        return {
            "url": str(rendition["url"]),
            "width": width,
            "height": height,
            "thumbnail": str(rendition.get("thumbnail", "")),
        }
    return None


def _pixabay_video_candidate(item: dict[str, Any]) -> ExternalAssetCandidate | None:
    try:
        video_id = int(item.get("id", 0))
    except (TypeError, ValueError):
        return None
    if video_id <= 0:
        return None
    rendition = _best_pixabay_rendition(item)
    if rendition is None:
        return None
    try:
        duration = int(item.get("duration", 0)) or None
    except (TypeError, ValueError):
        duration = None
    creator = _clean_metadata(item.get("user"))
    tags = _clean_metadata(item.get("tags")) or f"Pixabay video {video_id}"
    return ExternalAssetCandidate(
        candidate_id=f"pixabay-video:{video_id}",
        provider="Pixabay",
        title=tags[:120],
        source_url=str(item.get("pageURL", "")) or f"https://pixabay.com/videos/{video_id}/",
        thumbnail_url=rendition["thumbnail"],
        media_type="VIDEO",
        mime_type="video/mp4",
        width=rendition["width"],
        height=rendition["height"],
        size_bytes=None,
        license_name="Pixabay Content License",
        license_url="https://pixabay.com/service/license-summary/",
        creator=creator,
        credit=f"Video by {creator} on Pixabay" if creator else "Video from Pixabay",
        duration_seconds=duration,
    )


def _pixabay_search(query: str, key: str, limit: int, endpoint: str,
                    order: str, orientation: str | None) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "key": key,
        "q": query[:100],
        "per_page": max(3, min(limit, 20)),
        "safesearch": "true",
        "order": "latest" if order == "newest" else "popular",
    }
    if endpoint == PIXABAY_API:
        params.update({"image_type": "photo", "min_width": 1000})
        if orientation in {"horizontal", "vertical"}:
            params["orientation"] = orientation
    response = _pixabay_get_json(f"{endpoint}?{urlencode(params)}")
    hits = response.get("hits", [])
    return [item for item in hits] if isinstance(hits, list) else []


def _search_pixabay_images(query: str, key: str, limit: int,
                           order: str = "relevance",
                           orientation: str | None = None) -> list[ExternalAssetCandidate]:
    pixabay_orientation = {"landscape": "horizontal", "portrait": "vertical"}.get(orientation or "")
    candidates = []
    for item in _pixabay_search(query, key, limit, PIXABAY_API, order, pixabay_orientation):
        if isinstance(item, dict):
            candidate = _pixabay_photo_candidate(item)
            if candidate is not None:
                candidates.append(candidate)
    return candidates


def _search_pixabay_videos(query: str, key: str, limit: int,
                           order: str = "relevance") -> list[ExternalAssetCandidate]:
    candidates = []
    for item in _pixabay_search(query, key, limit, PIXABAY_VIDEO_API, order, None):
        if isinstance(item, dict):
            candidate = _pixabay_video_candidate(item)
            if candidate is not None:
                candidates.append(candidate)
    return candidates


def _pixabay_photo_detail(photo_id: str, key: str) -> ExternalAssetCandidate:
    if not photo_id.isdigit():
        raise ValueError("Invalid Pixabay candidate ID.")
    detail = _pixabay_get_json(f"{PIXABAY_API}/?{urlencode({'key': key, 'id': photo_id})}")
    hits = detail.get("hits", [])
    if not hits or not isinstance(hits[0], dict):
        raise DiscoveryError("The selected Pixabay photo no longer exists.")
    candidate = _pixabay_photo_candidate(hits[0])
    if candidate is None:
        raise DiscoveryError("The selected Pixabay photo is no longer eligible.")
    return candidate


def _pixabay_video_detail(video_id: str, key: str) -> ExternalAssetCandidate:
    if not video_id.isdigit():
        raise ValueError("Invalid Pixabay candidate ID.")
    detail = _pixabay_get_json(f"{PIXABAY_VIDEO_API}?{urlencode({'key': key, 'id': video_id})}")
    hits = detail.get("hits", [])
    if not hits or not isinstance(hits[0], dict):
        raise DiscoveryError("The selected Pixabay video no longer exists.")
    candidate = _pixabay_video_candidate(hits[0])
    if candidate is None:
        raise DiscoveryError("The selected Pixabay video is no longer eligible.")
    return candidate


def _pixabay_file_url(candidate_id: str, key: str, video: bool) -> tuple[str, str | None]:
    """Re-resolve a direct file URL at download time; Pixabay URLs rotate."""
    if video:
        detail = _pixabay_get_json(f"{PIXABAY_VIDEO_API}?{urlencode({'key': key, 'id': candidate_id})}")
        hits = detail.get("hits", [])
        if not hits or not isinstance(hits[0], dict):
            raise DiscoveryError("The selected Pixabay video no longer exists.")
        rendition = _best_pixabay_rendition(hits[0])
        if rendition is None:
            raise DiscoveryError("The selected Pixabay video has no downloadable file.")
        return rendition["url"], {"cdn.pixabay.com"}
    detail = _pixabay_get_json(f"{PIXABAY_API}/?{urlencode({'key': key, 'id': candidate_id})}")
    hits = detail.get("hits", [])
    if not hits or not isinstance(hits[0], dict):
        raise DiscoveryError("The selected Pixabay photo no longer exists.")
    file_url = str(hits[0].get("largeImageURL", ""))
    if urlparse(file_url).scheme != "https":
        raise DiscoveryError("The selected Pixabay photo has no downloadable file.")
    return file_url, {"pixabay.com"}


def _commons_uploaded_at(image_info: dict[str, Any]) -> str | None:
    """Upload timestamp is the only freshness signal Commons exposes."""
    timestamp = image_info.get("timestamp")
    if not isinstance(timestamp, str) or len(timestamp) < 10:
        return None
    return timestamp[:10]


def _candidate_from_video_page(page: dict[str, Any]) -> ExternalAssetCandidate | None:
    image_info = (page.get("imageinfo") or [{}])[0]
    mime_type = str(image_info.get("mime", ""))
    if mime_type not in ALLOWED_VIDEO_TYPES:
        return None
    width = image_info.get("width")
    height = image_info.get("height")
    if not isinstance(width, int) or not isinstance(height, int):
        return None
    if max(width, height) < 640:
        return None
    metadata = image_info.get("extmetadata") or {}
    return ExternalAssetCandidate(
        candidate_id=str(page.get("pageid", "")),
        provider="Wikimedia Commons",
        title=str(page.get("title", "")).removeprefix("File:"),
        source_url=str(image_info.get("descriptionurl", "")),
        thumbnail_url=str(image_info.get("thumburl", "")),
        media_type="VIDEO",
        mime_type=mime_type,
        width=width,
        height=height,
        size_bytes=image_info.get("size") if isinstance(image_info.get("size"), int) else None,
        license_name=_clean_metadata(metadata.get("LicenseShortName")),
        license_url=_clean_metadata(metadata.get("LicenseUrl")),
        creator=_clean_metadata(metadata.get("Artist")),
        credit=_clean_metadata(metadata.get("Credit")),
        uploaded_at=_commons_uploaded_at(image_info),
    )


def _search_commons_videos(query: str, limit: int) -> list[ExternalAssetCandidate]:
    candidates: list[ExternalAssetCandidate] = []
    for page in _commons_file_pages(f"{query} filetype:video", limit=limit):
        candidate = _candidate_from_video_page(page)
        if (
            candidate is not None
            and candidate.candidate_id
            and candidate.source_url.startswith("https://commons.wikimedia.org/")
        ):
            candidates.append(candidate)
    return candidates


def _download_video_candidate(
    candidate: ExternalAssetCandidate,
    api_keys: dict | None = None,
) -> tuple[bytes, str]:
    if is_referral_only(candidate):
        raise DiscoveryError(
            "YouTube is referral-only: open the watch page to identify the "
            "rights holder. YouTube videos are never downloaded as assets."
        )
    if candidate.candidate_id.startswith("pixabay-video:"):
        file_url, allowed_hosts = _pixabay_file_url(
            candidate.candidate_id.removeprefix("pixabay-video:"),
            _require_pixabay_key(api_keys),
            video=True,
        )
        _validate_public_https_url(file_url)
        request = Request(file_url, headers={"User-Agent": COMMONS_USER_AGENT})
        opener = build_opener(_PublicHttpsRedirectHandler())
        error_prefix = "Pixabay video download failed"
    elif candidate.candidate_id.startswith("pexels-video:"):
        file_url = _pexels_video_file_url(
            candidate.candidate_id.removeprefix("pexels-video:"),
            _require_pexels_key(api_keys),
        )
        _validate_public_https_url(file_url)
        request = Request(file_url, headers={"User-Agent": COMMONS_USER_AGENT})
        opener = build_opener(_PublicHttpsRedirectHandler())
        error_prefix = "Pexels video download failed"
        allowed_hosts = None
    else:
        file_url = _candidate_image_url(candidate.candidate_id)
        request = Request(file_url, headers={"User-Agent": COMMONS_USER_AGENT})
        opener = build_opener()
        error_prefix = "Video download failed"
        allowed_hosts = {"upload.wikimedia.org"}
    try:
        with opener.open(request, timeout=60) as response:
            final_url = response.geturl()
            if allowed_hosts is not None and urlparse(final_url).hostname not in allowed_hosts:
                raise DiscoveryError("Video download left the approved media host.")
            _validate_public_https_url(final_url)
            mime_type = response.headers.get_content_type().lower()
            if mime_type not in ALLOWED_VIDEO_TYPES:
                raise DiscoveryError(f"Unsupported video MIME type: {mime_type}")
            declared_size = response.headers.get("Content-Length")
            if declared_size and int(declared_size) > MAX_VIDEO_BYTES:
                raise DiscoveryError("Video exceeds the 100 MiB download limit.")
            data = response.read(MAX_VIDEO_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
        if isinstance(error, DiscoveryError):
            raise
        raise DiscoveryError(f"{error_prefix}: {error}") from error
    if len(data) > MAX_VIDEO_BYTES:
        raise DiscoveryError("Video exceeds the 100 MiB download limit.")
    return data, mime_type


# ---------------------------------------------------------------------------
# Unified interface + referral/keyless adapters (workstream 2).
#
# Rules (no exceptions):
# - YouTube is referral-only: find + link to the watch page so the planner
#   can identify the rights holder. Never download a YouTube video as an
#   asset, never grant rights by default (W1 deny-default scope; save and
#   download raise DiscoveryError for youtube: candidates).
# - No paid API, no mandatory key: Internet Archive (advancedsearch +
#   metadata APIs) and the YouTube referral adapter are keyless. Pexels /
#   Pixabay stay optional keyed escalation (free keys, dormant without one).
# - Rights (workstream 1) are CONSUMED, not reinvented: every candidate
#   carries a workstream-1 scope dict in ``rights_scope`` (deny-default for
#   YouTube/unknown licenses, ``scope_from_legacy`` backfill otherwise) and
#   planners decide per upload intent with ``candidate_rights_decision``
#   (thin wrapper over ``rights_scope.is_usable_for``). See
#   docs/discovery-referral.md point W1-DISCOVERY.
# ---------------------------------------------------------------------------

RIGHTS_ACTION_HUMAN_REVIEW = "human_review"
RIGHTS_ACTION_NONE = "none"


def _source_type_for_provider(provider: str) -> str:
    text = (provider or "").lower()
    if text.startswith("openverse"):
        return "openverse"
    if text.startswith("wikimedia"):
        return "wikimedia_commons"
    if text.startswith("internet archive"):
        return "internet_archive"
    if text.startswith("pexels"):
        return "pexels"
    if text.startswith("pixabay"):
        return "pixabay"
    if text.startswith("youtube"):
        return "youtube"
    return "unknown"


def _fallback_deny(reason: str) -> dict[str, Any]:
    """Local deny shape used only when the workstream-1 module is missing."""
    return {"allowed": False, "required_action": RIGHTS_ACTION_HUMAN_REVIEW,
            "reason": reason, "granted_by": "deny-default"}


def _scope_for_candidate(
    *,
    license_name: str | None,
    provider: str,
    source_url: str,
    creator: str | None = None,
    credit: str | None = None,
    referral_only: bool = False,
    deny_reason: str | None = None,
) -> dict[str, Any]:
    """Build the workstream-1 scope carried by a candidate.

    Referral-only (YouTube) and unknown-license items get a W1 deny-default
    (never grants anything, always routes to human review). Everything else
    gets the deterministic W1 legacy backfill from its license/source, so the
    planner can feed the scope straight into ``is_usable_for``.
    """
    if referral_only:
        reason = deny_reason or YOUTUBE_REFERRAL_REASON
        if _RIGHTS_W1_AVAILABLE:
            return _w1_default_deny_scope(
                license=license_name, source=_source_type_for_provider(provider),
                notes=reason)
        return _fallback_deny(reason)
    if _RIGHTS_W1_AVAILABLE:
        return _w1_scope_from_legacy({
            "license_type": license_name,
            "source_type": _source_type_for_provider(provider),
            "source_url": source_url,
            "creator": creator,
            "metadata": {"license_credit": credit} if credit else {},
        })
    return {"allowed": True, "required_action": RIGHTS_ACTION_HUMAN_REVIEW,
            "reason": "License requires human confirmation before use.",
            "granted_by": "discovery-fallback"}


def rights_blocked(scope: Any) -> str | None:
    """Return the blocking reason when a scope forbids auto-acquisition.

    Consumes workstream-1 semantics: deny-default grants (YouTube, unknown
    licenses) and explicit allowed=False both block. Anything else returns
    None (still subject to human review at save time — never pre-cleared).
    """
    if not isinstance(scope, dict):
        return "missing rights scope"
    if scope.get("granted_by") == "deny-default":
        return str(scope.get("notes") or "deny by default: needs human review")
    if scope.get("allowed") is False:
        return str(scope.get("reason") or "rights not allowed")
    return None


def candidate_rights_decision(
    candidate: ExternalAssetCandidate,
    purpose: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Planner integration point: per-upload-intent decision for a candidate.

    Adapts the candidate to the asset mapping workstream 1 expects and calls
    ``is_usable_for``. Returns W1's {allowed, reasons, required_action,
    scope}. Without the W1 module, returns a conservative local deny.
    """
    scope = dict(candidate.rights_scope) if isinstance(candidate.rights_scope, dict) else {}
    if not _RIGHTS_W1_AVAILABLE or _w1_is_usable_for is None:
        blocked = rights_blocked(scope)
        return {
            "allowed": blocked is None,
            "reasons": ["ok"] if blocked is None else ["rights-module-missing", blocked],
            "required_action": RIGHTS_ACTION_NONE if blocked is None else RIGHTS_ACTION_HUMAN_REVIEW,
            "scope": scope,
        }
    asset = {
        "source_type": _source_type_for_provider(candidate.provider),
        "source_url": candidate.source_url,
        "license_type": candidate.license_name,
        "creator": candidate.creator,
        "rights_state": "verified" if candidate.verification_status == "verified" else "unverified",
        "lifecycle_state": "active",
        "rights_scope": scope,
        "metadata": {
            "license_credit": candidate.credit,
            "candidate_id": candidate.candidate_id,
            "discovery_provider": candidate.provider,
        },
    }
    return _w1_is_usable_for(asset, dict(purpose or {}))


YOUTUBE_REFERRAL_REASON = (
    "YouTube is referral-only: open the watch page to identify the rights "
    "holder. Never ingested as an asset, never granted rights by default."
)


def youtube_rights_scope() -> dict[str, Any]:
    return _scope_for_candidate(
        license_name="Unknown — YouTube Standard License assumed",
        provider="YouTube (referral only)",
        source_url="https://www.youtube.com/",
        referral_only=True,
        deny_reason=YOUTUBE_REFERRAL_REASON,
    )


_GENERIC_FOOTBALL_TOKENS = frozenset({
    "football", "soccer", "stadium", "match", "goal", "ball", "field",
    "pitch", "sport", "sports", "game", "team", "club", "league", "cup",
    "clip", "video", "photo", "image", "highlights", "night", "day",
})


def _significant_tokens(text: str) -> set[str]:
    tokens = set(re.findall(r"[a-z0-9]+", (text or "").lower()))
    return {token for token in tokens if len(token) >= 3 and token not in _GENERIC_FOOTBALL_TOKENS}


def grade_match(
    title: str,
    creator: str | None,
    query: str,
    exact_terms: list[str] | None = None,
) -> str:
    """Grade a candidate as exact vs generic.

    exact = footage of the named match/player: every exact_term appears in
    the title/creator, or (without exact_terms) the title shares 2+
    significant non-generic tokens with the query. Everything else is
    generic football footage. Generic football vocabulary (football,
    stadium, match, ...) never counts toward exact.
    """
    haystack = f"{title or ''} {creator or ''}".casefold()
    if exact_terms:
        wanted = [str(term).casefold().strip() for term in exact_terms if str(term).strip()]
        if wanted and all(term in haystack for term in wanted):
            return "exact"
        return "generic"
    shared = _significant_tokens(query) & _significant_tokens(f"{title or ''} {creator or ''}")
    return "exact" if len(shared) >= 2 else "generic"


def _stamp_grades(
    candidates: list[ExternalAssetCandidate],
    query: str,
    exact_terms: list[str] | None,
) -> list[ExternalAssetCandidate]:
    """Stamp match_grade on search results (search owns grading)."""
    return [
        replace(
            item,
            match_grade=grade_match(item.title, item.creator, query, exact_terms),
        )
        for item in candidates
    ]


YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
YOUTUBE_WATCH_URL = "https://www.youtube.com/watch"
YOUTUBE_THUMB_URL = "https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

_YOUTUBE_SEARCH_FN: Any = None


def set_youtube_search_fn(fn: Any) -> None:
    """Install a keyless YouTube search hook (planner integration point).

    fn(query, limit) returns a list of {"video_id", "title", "creator",
    "duration_seconds"} dicts. None restores the default: the adapter stays
    listed as ready but returns no hits. No network happens inside discovery
    until a hook is installed — tests inject fixtures through here.
    """
    global _YOUTUBE_SEARCH_FN
    _YOUTUBE_SEARCH_FN = fn


def youtube_watch_url(video_id: str) -> str:
    return f"{YOUTUBE_WATCH_URL}?v={video_id}"


def youtube_preview_url(video_id: str) -> str:
    """Keyless preview thumbnail (i.ytimg.com needs no API key)."""
    return YOUTUBE_THUMB_URL.format(video_id=video_id)


def youtube_referral_candidate(
    video_id: str,
    title: str,
    *,
    creator: str | None = None,
    duration_seconds: int | None = None,
) -> ExternalAssetCandidate | None:
    """Build a referral-only YouTube candidate (find + link, never ingest)."""
    if not isinstance(video_id, str) or not YOUTUBE_ID_RE.fullmatch(video_id):
        return None
    clean_title = _clean_metadata(title) or f"YouTube video {video_id}"
    clean_creator = _clean_metadata(creator)
    preview = youtube_preview_url(video_id)
    duration = duration_seconds if isinstance(duration_seconds, int) and duration_seconds > 0 else None
    return ExternalAssetCandidate(
        candidate_id=f"youtube:{video_id}",
        provider="YouTube (referral only)",
        title=clean_title,
        source_url=youtube_watch_url(video_id),
        thumbnail_url=preview,
        preview_url=preview,
        media_type="VIDEO",
        mime_type="video/unknown",
        width=None,
        height=None,
        size_bytes=None,
        license_name="Unknown — YouTube Standard License assumed",
        license_url=None,
        license="Unknown — YouTube Standard License assumed",
        creator=clean_creator,
        credit=(
            f"{clean_creator} via YouTube" if clean_creator
            else "Via YouTube — rights holder on watch page"
        ),
        duration_seconds=duration,
        rights_scope=youtube_rights_scope(),
        match_grade="generic",
        verification_status="unverified",
    )


def _youtube_search_hook(api_keys: dict | None) -> Any:
    if isinstance(api_keys, dict) and callable(api_keys.get("YOUTUBE_SEARCH_FN")):
        return api_keys["YOUTUBE_SEARCH_FN"]
    return _YOUTUBE_SEARCH_FN


def search_youtube_referrals(
    query: str,
    limit: int = 8,
    *,
    api_keys: dict | None = None,
    search_fn: Any = None,
) -> list[ExternalAssetCandidate]:
    """Keyless YouTube referral search. Never touches the network by default.

    Without an installed hook the adapter reports ready (so planners can see
    the referral option) but returns no hits. Hook failures degrade to []
    so discovery never breaks because of an auxiliary source.
    """
    normalized = " ".join(str(query or "").split())
    if not normalized or limit < 1:
        return []
    hook = search_fn if callable(search_fn) else _youtube_search_hook(api_keys)
    if hook is None:
        return []
    try:
        raw = hook(normalized, min(limit, MAX_RESULTS))
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    candidates: list[ExternalAssetCandidate] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        candidate = youtube_referral_candidate(
            str(entry.get("video_id", "")),
            str(entry.get("title", "") or ""),
            creator=entry.get("creator"),
            duration_seconds=entry.get("duration_seconds"),
        )
        if candidate is not None:
            candidates.append(candidate)
        if len(candidates) >= limit:
            break
    return candidates


ARCHIVE_SEARCH_API = "https://archive.org/advancedsearch.php"
ARCHIVE_ITEM_URL = "https://archive.org/details/{identifier}"
ARCHIVE_PREVIEW_URL = "https://archive.org/services/img/{identifier}"
ARCHIVE_METADATA_URL = "https://archive.org/metadata/{identifier}"
ARCHIVE_DOWNLOAD_URL = "https://archive.org/download/{identifier}/{name}"
ARCHIVE_ID_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$")
ARCHIVE_IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp", ".gif")
ARCHIVE_VIDEO_SUFFIXES = (".mp4", ".webm", ".ogv")
_ARCHIVE_FIELDS = ["identifier", "title", "creator", "licenseurl", "rights", "mediatype",
                  "width", "height"]


def _archive_get_json(url: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": COMMONS_USER_AGENT},
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = response.read(2 * 1024 * 1024)
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise DiscoveryError(f"Internet Archive request failed: {error}") from error
    try:
        result = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DiscoveryError("Internet Archive returned invalid JSON.") from error
    if not isinstance(result, dict):
        raise DiscoveryError("Internet Archive returned an unexpected response.")
    return result


def _archive_license(doc: dict[str, Any]) -> tuple[str | None, str | None, bool]:
    """Return (license_name, license_url, known_reusable).

    Unknown licenses are never pre-approved: rights_scope.allowed stays
    False until a human reviews the item page.
    """
    license_url = doc.get("licenseurl")
    if isinstance(license_url, list):
        license_url = license_url[0] if license_url else None
    if isinstance(license_url, str) and license_url.startswith("https://"):
        lowered = license_url.lower()
        if "publicdomain/zero" in lowered:
            return "CC0", license_url, True
        if "publicdomain/mark" in lowered:
            return "Public Domain Mark", license_url, True
        match = re.search(r"creativecommons\.org/licenses/([a-z-]+)/(\d\.\d)", lowered)
        if match:
            return _license_label(match.group(1), match.group(2)), license_url, True
        return f"See license: {license_url}", license_url, False
    rights = _clean_metadata(doc.get("rights"))
    if rights:
        return rights[:160], None, False
    return "Unknown — verify on item page", None, False


def _archive_dim(value: Any) -> int | None:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError, AttributeError):
        return None
    return parsed if parsed > 0 else None


def _archive_candidate_from_doc(
    doc: dict[str, Any],
    *,
    media_type: str,
    mime_type: str,
) -> ExternalAssetCandidate | None:
    if not isinstance(doc, dict):
        return None
    identifier = str(doc.get("identifier", ""))
    if not ARCHIVE_ID_RE.fullmatch(identifier):
        return None
    title = _clean_metadata(doc.get("title")) or identifier
    creator = _clean_metadata(doc.get("creator"))
    license_name, license_url, reusable = _archive_license(doc)
    preview = ARCHIVE_PREVIEW_URL.format(identifier=identifier)
    scope = _scope_for_candidate(
        license_name=license_name,
        provider="Internet Archive",
        source_url=ARCHIVE_ITEM_URL.format(identifier=identifier),
        creator=creator,
        credit=f"{creator} via Internet Archive" if creator else None,
        referral_only=not reusable,
        deny_reason="Internet Archive license unknown — human review of the item page required.",
    )
    return ExternalAssetCandidate(
        candidate_id=f"archive:{identifier}",
        provider="Internet Archive",
        title=title[:160],
        source_url=ARCHIVE_ITEM_URL.format(identifier=identifier),
        thumbnail_url=preview,
        preview_url=preview,
        media_type=media_type,
        mime_type=mime_type,
        width=_archive_dim(doc.get("width")),
        height=_archive_dim(doc.get("height")),
        size_bytes=None,
        license_name=license_name,
        license_url=license_url,
        license=license_name,
        creator=creator,
        credit=f"{creator} via Internet Archive" if creator else "Via Internet Archive",
        duration_seconds=None,
        rights_scope=scope,
        match_grade="generic",
        verification_status="unverified",
    )


def _search_archive(
    query: str,
    limit: int,
    *,
    collection: str,
    media_type: str,
    mime_type: str,
) -> list[ExternalAssetCandidate]:
    normalized = " ".join(str(query or "").split())
    if not normalized:
        raise ValueError("Search query is required.")
    params = urlencode(
        {
            "q": f"({normalized[:100]}) AND mediatype:{collection}",
            "fl[]": _ARCHIVE_FIELDS,
            "rows": max(3, min(limit, 20)),
            "page": 1,
            "output": "json",
        },
        doseq=True,
    )
    response = _archive_get_json(f"{ARCHIVE_SEARCH_API}?{params}")
    docs = response.get("response", {}).get("docs", [])
    if not isinstance(docs, list):
        return []
    candidates: list[ExternalAssetCandidate] = []
    for doc in docs:
        # The query already filters mediatype server-side; re-check client-side
        # so loose API responses can never mix stills into video results.
        if isinstance(doc, dict) and doc.get("mediatype") not in (None, "", collection):
            continue
        candidate = _archive_candidate_from_doc(doc, media_type=media_type, mime_type=mime_type)
        if candidate is not None:
            candidates.append(candidate)
        if len(candidates) >= limit:
            break
    return candidates


def _search_archive_images(query: str, limit: int = 12) -> list[ExternalAssetCandidate]:
    """Keyless Internet Archive image search (no key, no quota)."""
    return _search_archive(query, limit, collection="image",
                           media_type="IMAGE", mime_type="image/unknown")


def _search_archive_videos(query: str, limit: int = 12) -> list[ExternalAssetCandidate]:
    """Keyless Internet Archive video search (no key, no quota)."""
    return _search_archive(query, limit, collection="movies",
                           media_type="VIDEO", mime_type="video/unknown")


def _archive_detail(identifier: str) -> ExternalAssetCandidate:
    if not isinstance(identifier, str) or not ARCHIVE_ID_RE.fullmatch(identifier):
        raise ValueError("Invalid Internet Archive candidate ID.")
    params = urlencode(
        {
            "q": f"identifier:{identifier}",
            "fl[]": _ARCHIVE_FIELDS,
            "rows": 1,
            "page": 1,
            "output": "json",
        },
        doseq=True,
    )
    try:
        response = _archive_get_json(f"{ARCHIVE_SEARCH_API}?{params}")
    except DiscoveryError as error:
        raise DiscoveryError(
            "The selected Internet Archive item is no longer available."
        ) from error
    docs = response.get("response", {}).get("docs", [])
    if not docs or not isinstance(docs[0], dict):
        raise DiscoveryError("The selected Internet Archive item is no longer available.")
    doc = docs[0]
    collection = str(doc.get("mediatype", ""))
    if collection == "movies":
        media_type, mime_type = "VIDEO", "video/unknown"
    elif collection == "image":
        media_type, mime_type = "IMAGE", "image/unknown"
    else:
        raise DiscoveryError("The selected Internet Archive item is not a supported media type.")
    candidate = _archive_candidate_from_doc(doc, media_type=media_type, mime_type=mime_type)
    if candidate is None:
        raise DiscoveryError("The selected Internet Archive item is no longer available.")
    return candidate


def _archive_file_url(identifier: str, *, video: bool) -> str:
    """Re-resolve a direct file URL at download time via the metadata API."""
    try:
        meta = _archive_get_json(ARCHIVE_METADATA_URL.format(identifier=identifier))
    except DiscoveryError as error:
        raise DiscoveryError(
            "The selected Internet Archive item is no longer available."
        ) from error
    files = meta.get("files", [])
    if not isinstance(files, list):
        raise DiscoveryError("The selected Internet Archive item has no downloadable file.")
    suffixes = ARCHIVE_VIDEO_SUFFIXES if video else ARCHIVE_IMAGE_SUFFIXES
    cap = MAX_VIDEO_BYTES if video else MAX_DOWNLOAD_BYTES
    shortlisted: list[str] = []
    for entry in files:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", ""))
        if not name or name.startswith("/") or "/" in name:
            continue
        if not name.lower().endswith(suffixes):
            continue
        try:
            size = int(entry.get("size", 0) or 0)
        except (TypeError, ValueError):
            size = 0
        if size and size > cap:
            continue
        shortlisted.append(name)
    if not shortlisted:
        raise DiscoveryError("The selected Internet Archive item has no downloadable file.")
    # Prefer the most widely playable rendition (mp4 for video, jpeg for
    # stills) instead of whichever file the item lists first.
    preferred = ".mp4" if video else ".jpg"
    chosen = next((name for name in shortlisted if name.lower().endswith(preferred)),
                  shortlisted[0])
    return ARCHIVE_DOWNLOAD_URL.format(identifier=identifier, name=chosen)


def _download_archive_candidate(candidate: ExternalAssetCandidate) -> tuple[bytes, str]:
    video = candidate.media_type == "VIDEO"
    allowed = ALLOWED_VIDEO_TYPES if video else ALLOWED_IMAGE_TYPES
    cap = MAX_VIDEO_BYTES if video else MAX_DOWNLOAD_BYTES
    kind = "video" if video else "image"
    file_url = _archive_file_url(candidate.candidate_id.removeprefix("archive:"), video=video)
    _validate_public_https_url(file_url)
    request = Request(file_url, headers={"User-Agent": COMMONS_USER_AGENT})
    opener = build_opener(_PublicHttpsRedirectHandler())
    try:
        with opener.open(request, timeout=60 if video else 30) as response:
            _validate_public_https_url(response.geturl())
            mime_type = response.headers.get_content_type().lower()
            if mime_type not in allowed:
                raise DiscoveryError(f"Unsupported {kind} MIME type: {mime_type}")
            declared_size = response.headers.get("Content-Length")
            if declared_size and int(declared_size) > cap:
                raise DiscoveryError(
                    f"{'Video' if video else 'Image'} exceeds the download limit."
                )
            data = response.read(cap + 1)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
        if isinstance(error, DiscoveryError):
            raise
        raise DiscoveryError(f"Internet Archive {kind} download failed: {error}") from error
    if len(data) > cap:
        raise DiscoveryError(f"{'Video' if video else 'Image'} exceeds the download limit.")
    return data, mime_type


def _score_candidate(candidate: ExternalAssetCandidate, query_tokens: set[str]) -> float:
    """Relevance first, then reusable license and resolution; no ML dependency."""
    title_tokens = set(
        re.findall(r"[a-z0-9]+", f"{candidate.title} {candidate.provider}".lower())
    )
    overlap = len(query_tokens & title_tokens) / max(1, len(query_tokens))
    license_name = (candidate.license_name or "").upper()
    if "CC0" in license_name or "PUBLIC DOMAIN" in license_name:
        license_score = 3.0
    elif "PIXABAY" in license_name or "PEXELS" in license_name or "BY-SA" in license_name or "CC BY" in license_name:
        license_score = 2.0
    else:
        license_score = 1.0
    megapixels = ((candidate.width or 0) * (candidate.height or 0)) / 1_000_000
    size_score = min(2.0, megapixels / 2.0) if megapixels > 0 else 0.5
    if candidate.duration_seconds:
        size_score += 0.2
    return overlap * 3.0 + license_score + size_score


def _rank_candidates(
    candidates: list[ExternalAssetCandidate],
    query: str,
    *,
    limit: int,
) -> list[ExternalAssetCandidate]:
    """Score within each provider, interleave providers for diversity, dedupe URLs."""
    query_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
    groups: dict[str, list[ExternalAssetCandidate]] = {}
    for candidate in candidates:
        group = candidate.provider.split(" · ")[0]
        groups.setdefault(group, []).append(candidate)
    for group in groups.values():
        group.sort(key=lambda item: _score_candidate(item, query_tokens), reverse=True)
    ranked: list[ExternalAssetCandidate] = []
    seen_urls: set[str] = set()
    while len(ranked) < limit:
        progressed = False
        for group in groups.values():
            while group:
                candidate = group.pop(0)
                key = candidate.source_url.casefold()
                if key not in seen_urls:
                    seen_urls.add(key)
                    ranked.append(candidate)
                    progressed = True
                    break
            if len(ranked) >= limit:
                break
        if not progressed:
            break
    return ranked


def search_candidates(
    query: str,
    *,
    resource_type: str = "image",
    limit: int = 24,
    api_keys: dict | None = None,
    sort: str = "relevance",
    orientation: str | None = None,
    exact_terms: list[str] | None = None,
) -> tuple[list[ExternalAssetCandidate], list[dict[str, str]]]:
    """Search every eligible provider for images or video.

    Returns (candidates, provider_status). Keyed providers without a key are
    reported, not queried. sort=newest puts dated uploads first (Wikimedia
    Commons exposes upload dates; other providers do not). orientation hints
    portrait/landscape to providers that support it. exact_terms (player /
    match names from the planner) grade candidates as exact vs generic.
    Raises only when every queried provider failed.
    """
    normalized_query = _validate_search_args(query, resource_type, limit, sort, orientation)
    statuses = provider_status(api_keys)
    collected, failures = _collect_from_providers(
        statuses, api_keys, normalized_query, resource_type, limit, sort, orientation)
    if not collected and failures:
        raise DiscoveryError("; ".join(failures))
    ranked = _rank_collected(collected, normalized_query, limit, sort)
    return _stamp_grades(ranked, normalized_query, exact_terms), statuses


# Cost tiers, cheapest first. Mirrors the Visibly "Google-first" pattern:
# free sources serve every request; quota-limited keyed sources run only
# when the free tier cannot satisfy the need.
FREE_PROVIDER_KEYS = frozenset({
    "openverse_image", "commons_image", "commons_video",
    "archive_image", "archive_video", "youtube_referral",
})
KEYED_PROVIDER_KEYS = frozenset({"pexels_image", "pexels_video", "pixabay_image", "pixabay_video"})
# Providers that may be listed for discovery but must never be downloaded
# as assets (referral-only: find + link to the source, nothing else).
REFERRAL_ONLY_KEYS = frozenset({"youtube_referral"})
REFERRAL_ONLY_PREFIXES = ("youtube:",)


def tier_of_provider_key(key: str) -> str:
    """Cost tier for a provider status key: keyless, keyed, or unknown."""
    if key in FREE_PROVIDER_KEYS:
        return "keyless"
    if key in KEYED_PROVIDER_KEYS:
        return "keyed"
    return "unknown"


def tier_of_provider(label: str) -> str:
    """Cost tier for a candidate provider label (prefix match)."""
    text = (label or "").lower()
    if text.startswith("openverse") or text.startswith("wikimedia"):
        return "keyless"
    if text.startswith("internet archive") or text.startswith("youtube"):
        return "keyless"
    if text.startswith("pexels") or text.startswith("pixabay"):
        return "keyed"
    return "unknown"


def is_referral_only(candidate: ExternalAssetCandidate) -> bool:
    """True when the candidate must never be downloaded as an asset."""
    provider = (candidate.provider or "").lower()
    if candidate.candidate_id.startswith(REFERRAL_ONLY_PREFIXES):
        return True
    return "referral only" in provider or provider.startswith("youtube")


def _validate_search_args(
    query: str, resource_type: str, limit: int, sort: str, orientation: str | None,
) -> str:
    normalized_query = " ".join(query.split())
    if not normalized_query:
        raise ValueError("Search query is required.")
    if len(normalized_query) > 250:
        raise ValueError("Search query must be 250 characters or fewer.")
    if resource_type not in {"image", "video"}:
        raise ValueError("Discovery supports image and video requests.")
    if sort not in {"relevance", "newest"}:
        raise ValueError("Sort must be relevance or newest.")
    if orientation is not None and orientation not in {"landscape", "portrait", "square"}:
        raise ValueError("Orientation must be landscape, portrait, or square.")
    if not 1 <= limit <= MAX_RESULTS:
        raise ValueError(f"Result limit must be between 1 and {MAX_RESULTS}.")
    return normalized_query


def _collect_from_providers(
    statuses: list[dict[str, str]],
    api_keys: dict | None,
    normalized_query: str,
    resource_type: str,
    limit: int,
    sort: str,
    orientation: str | None,
    provider_keys: frozenset[str] | set[str] | None = None,
) -> tuple[list[ExternalAssetCandidate], list[str]]:
    """Query one tier of providers; None means every eligible provider."""
    ready = {item["key"] for item in statuses if item["state"] == "ready"}
    wanted = resource_type
    collected: list[ExternalAssetCandidate] = []
    failures: list[str] = []
    per_key = dict(api_keys or {})

    def run(key: str, media: str, search: Any) -> None:
        if provider_keys is not None and key not in provider_keys:
            return
        for status in statuses:
            if status["key"] != key:
                continue
            if key not in ready or media != wanted:
                return
            try:
                collected.extend(search())
            except DiscoveryError as error:
                status["state"] = "failed"
                failures.append(f"{key}: {error}")

    pexels_key = _pexels_key(per_key)
    pixabay_key = _pixabay_key(per_key)
    pixabay_orientation = {"landscape": "horizontal", "portrait": "vertical"}.get(orientation or "")
    pixabay_order = sort
    run("openverse_image", "image",
        lambda: _search_openverse_page(normalized_query)[:limit])
    run("commons_image", "image",
        lambda: search_commons_images(normalized_query, limit=min(limit, 12)))
    run("commons_video", "video",
        lambda: _search_commons_videos(normalized_query, limit=min(limit, 12)))
    run("archive_image", "image",
        lambda: _search_archive_images(normalized_query, limit=min(limit, 12)))
    run("archive_video", "video",
        lambda: _search_archive_videos(normalized_query, limit=min(limit, 12)))
    run("youtube_referral", "video",
        lambda: search_youtube_referrals(normalized_query, limit, api_keys=per_key))
    if pexels_key:
        run("pexels_image", "image",
            lambda: _search_pexels_images(normalized_query, pexels_key, limit, orientation))
        run("pexels_video", "video",
            lambda: _search_pexels_videos(normalized_query, pexels_key, limit, orientation))
    if pixabay_key:
        run("pixabay_image", "image",
            lambda: _search_pixabay_images(normalized_query, pixabay_key, limit,
                                           pixabay_order, pixabay_orientation))
        run("pixabay_video", "video",
            lambda: _search_pixabay_videos(normalized_query, pixabay_key, limit, pixabay_order))
    return collected, failures


def _rank_collected(
    collected: list[ExternalAssetCandidate],
    normalized_query: str,
    limit: int,
    sort: str,
) -> list[ExternalAssetCandidate]:
    ranked = _rank_candidates(collected, normalized_query, limit=limit)
    if sort == "newest":
        # Dated uploads newest-first; undated keep their relevance order.
        dated = [item for item in ranked if item.uploaded_at]
        undated = [item for item in ranked if not item.uploaded_at]
        dated.sort(key=lambda item: str(item.uploaded_at), reverse=True)
        ranked = dated + undated
    return ranked


def _stamp_tiers(
    candidates: list[ExternalAssetCandidate],
) -> list[ExternalAssetCandidate]:
    return [replace(item, source_tier=tier_of_provider(item.provider)) for item in candidates]


def search_candidates_tiered(
    query: str,
    *,
    resource_type: str = "image",
    limit: int = 24,
    api_keys: dict | None = None,
    sort: str = "relevance",
    orientation: str | None = None,
    min_free: int = 6,
    min_good: int = 3,
    good_score: float = 4.0,
    exact_terms: list[str] | None = None,
) -> tuple[list[ExternalAssetCandidate], list[dict[str, str]], dict[str, Any]]:
    """Free-first discovery with keyed-tier escalation.

    Phase 1 queries only keyless providers (Openverse, Wikimedia Commons,
    Internet Archive, YouTube referrals: no quota, no key). Phase 2 (Pexels,
    no quota, no key). Phase 2 (Pexels, Pixabay) runs when the free tier
    is insufficient — by *count* (fewer than ``min_free`` usable
    candidates) or by *quality* (fewer than ``min_good`` candidates
    scoring at least ``good_score`` on the same relevance/license/size
    basis as ranking). Count alone never hides better keyed results:
    plentiful-but-poor free matches still escalate. ``min_free=0`` and
    ``min_good=0`` together mean free-only (keyed tier never queried).

    Returns (candidates, provider_status, tier_report) where tier_report
    carries ``tiers_queried``, ``free_count``, ``free_good_count``,
    ``keyed_count``, ``escalated``, ``escalation_reason`` and
    ``keyed_available`` — the transparency counterpart to Visibly's
    ``data_source`` field. Every returned candidate is stamped with
    ``source_tier``. Raises only when every queried provider failed.
    """
    normalized_query = _validate_search_args(query, resource_type, limit, sort, orientation)
    statuses = provider_status(api_keys)
    keyed_available = any(
        item["key"] in KEYED_PROVIDER_KEYS and item["state"] == "ready"
        and item.get("media") == resource_type
        for item in statuses
    )
    effective_min = max(0, min(int(min_free), limit))
    effective_good = max(0, min(int(min_good), limit))

    free_collected, free_failures = _collect_from_providers(
        statuses, api_keys, normalized_query, resource_type, limit, sort,
        orientation, FREE_PROVIDER_KEYS)
    free_ranked = _rank_collected(free_collected, normalized_query, limit, sort)
    query_tokens = set(re.findall(r"[a-z0-9]+", normalized_query.lower()))
    free_good = sum(1 for item in free_ranked
                    if _score_candidate(item, query_tokens) >= good_score)

    short_on_count = len(free_ranked) < effective_min
    short_on_quality = free_good < effective_good
    if (not short_on_count and not short_on_quality) or not keyed_available:
        if not free_ranked and free_failures:
            raise DiscoveryError("; ".join(free_failures))
        reason = None
        if short_on_count or short_on_quality:
            reason = "keyed tier unavailable (needs_key); free tier served what it could"
        report = {
            "tiers_queried": ["free"],
            "free_count": len(free_ranked),
            "free_good_count": free_good,
            "keyed_count": 0,
            "escalated": False,
            "escalation_reason": reason,
            "keyed_available": keyed_available,
        }
        return _stamp_grades(_stamp_tiers(free_ranked), normalized_query, exact_terms), statuses, report

    if short_on_count and short_on_quality:
        why = (f"free tier returned {len(free_ranked)} < min_free {effective_min} "
               f"with only {free_good} good < min_good {effective_good}")
    elif short_on_count:
        why = f"free tier returned {len(free_ranked)} < min_free {effective_min}"
    else:
        why = (f"free tier quality insufficient: only {free_good} good "
               f"< min_good {effective_good} (plentiful but poor matches)")
    keyed_collected, keyed_failures = _collect_from_providers(
        statuses, api_keys, normalized_query, resource_type, limit, sort,
        orientation, KEYED_PROVIDER_KEYS)
    merged = _rank_collected(free_collected + keyed_collected, normalized_query, limit, sort)
    if not merged and free_failures + keyed_failures:
        raise DiscoveryError("; ".join(free_failures + keyed_failures))
    report = {
        "tiers_queried": ["free", "keyed"],
        "free_count": len(free_ranked),
        "free_good_count": free_good,
        "keyed_count": max(0, len(merged) - len(free_ranked)),
        "escalated": True,
        "escalation_reason": why,
        "keyed_available": keyed_available,
    }
    return _stamp_grades(_stamp_tiers(merged), normalized_query, exact_terms), statuses, report
