from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import html
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen
import uuid

from .asset_intelligence import ResourceRequirement
from .ingest import ingest_one


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
        return {
            "status": "SAVED",
            "asset_id": result.removeprefix("ingested:"),
            "rights_state": sidecar["rights_state"],
            "candidate": asdict(candidate),
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
        {"key": "openverse_image", "label": "Openverse", "media": "image", "state": "ready"},
        {"key": "commons_image", "label": "Wikimedia Commons", "media": "image", "state": "ready"},
        {"key": "commons_video", "label": "Wikimedia Commons", "media": "video", "state": "ready"},
        {"key": "pexels_image", "label": "Pexels", "media": "image",
         "state": "ready" if pexels_ready else "needs_key"},
        {"key": "pexels_video", "label": "Pexels", "media": "video",
         "state": "ready" if pexels_ready else "needs_key"},
        {"key": "pixabay_image", "label": "Pixabay", "media": "image",
         "state": "ready" if pixabay_ready else "needs_key"},
        {"key": "pixabay_video", "label": "Pixabay", "media": "video",
         "state": "ready" if pixabay_ready else "needs_key"},
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
) -> tuple[list[ExternalAssetCandidate], list[dict[str, str]]]:
    """Search every eligible provider for images or video.

    Returns (candidates, provider_status). Keyed providers without a key are
    reported, not queried. sort=newest puts dated uploads first (Wikimedia
    Commons exposes upload dates; other providers do not). orientation hints
    portrait/landscape to providers that support it. Raises only when every
    queried provider failed.
    """
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

    statuses = provider_status(api_keys)
    ready = {item["key"] for item in statuses if item["state"] == "ready"}
    wanted = resource_type
    collected: list[ExternalAssetCandidate] = []
    failures: list[str] = []
    per_key = dict(api_keys or {})

    def run(key: str, media: str, search: Any) -> None:
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

    if not collected and failures:
        raise DiscoveryError("; ".join(failures))
    ranked = _rank_candidates(collected, normalized_query, limit=limit)
    if sort == "newest":
        # Dated uploads newest-first; undated keep their relevance order.
        dated = [item for item in ranked if item.uploaded_at]
        undated = [item for item in ranked if not item.uploaded_at]
        dated.sort(key=lambda item: str(item.uploaded_at), reverse=True)
        ranked = dated + undated
    return ranked, statuses
