from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import html
import ipaddress
import json
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
COMMONS_USER_AGENT = "AutonomousContentEngine/0.1 (local asset discovery)"
MAX_RESULTS = 24
OPENVERSE_PAGE_SIZE = 20
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
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
        media_type=str(image_info.get("mediatype", "BITMAP")),
        mime_type=mime_type,
        width=image_info.get("width"),
        height=image_info.get("height"),
        size_bytes=image_info.get("size"),
        license_name=_clean_metadata(metadata.get("LicenseShortName")),
        license_url=_clean_metadata(metadata.get("LicenseUrl")),
        creator=_clean_metadata(metadata.get("Artist")),
        credit=_clean_metadata(metadata.get("Credit")),
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

    params = urlencode(
        {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "generator": "search",
            "gsrnamespace": 6,
            "gsrsearch": normalized_query,
            "gsrlimit": limit,
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|size|mime|mediatype",
            "iiurlwidth": 480,
        }
    )
    response = _request_json(f"{COMMONS_API}?{params}")
    pages = response.get("query", {}).get("pages", [])
    if not isinstance(pages, list):
        return []

    candidates: list[ExternalAssetCandidate] = []
    for page in pages:
        if not isinstance(page, dict):
            continue
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


def _candidate_by_id(candidate_id: str) -> ExternalAssetCandidate:
    if candidate_id.startswith("openverse:"):
        candidate_uuid = candidate_id.removeprefix("openverse:")
        if not re.fullmatch(r"[0-9a-fA-F-]{36}", candidate_uuid):
            raise ValueError("Invalid Openverse candidate ID.")
        detail = _openverse_request_json(f"{OPENVERSE_API}/images/{candidate_uuid}/")
        candidate = _candidate_from_openverse(detail)
        if candidate is None:
            raise DiscoveryError("The selected Openverse image is no longer eligible.")
        return candidate
    if not candidate_id.isdigit():
        raise ValueError("Invalid external image candidate ID.")

    params = urlencode(
        {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "pageids": candidate_id,
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|size|mime|mediatype",
            "iiurlwidth": 480,
        }
    )
    response = _request_json(f"{COMMONS_API}?{params}")
    pages = response.get("query", {}).get("pages", [])
    if not pages or not isinstance(pages[0], dict):
        raise DiscoveryError("The selected Commons candidate no longer exists.")
    candidate = _candidate_from_page(pages[0])
    if candidate is None:
        raise DiscoveryError("The selected candidate is not a supported image type.")
    if not candidate.source_url.startswith("https://commons.wikimedia.org/"):
        raise DiscoveryError("The selected candidate has an invalid source URL.")
    if urlparse(candidate.thumbnail_url).hostname not in {
        "thumb.wikimedia.org",
        "upload.wikimedia.org",
    }:
        raise DiscoveryError("The selected candidate has an invalid media URL.")
    return candidate


def _download_candidate(candidate: ExternalAssetCandidate) -> tuple[bytes, str]:
    if candidate.candidate_id.startswith("openverse:"):
        return _download_openverse_candidate(candidate.candidate_id.removeprefix("openverse:"))
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
) -> dict[str, Any]:
    """Download and ingest a user-selected Commons image candidate."""

    if requirement.resource_type != "image":
        raise ValueError("External image providers only support image requests.")

    candidate = _candidate_by_id(candidate_id)
    data, mime_type = _download_candidate(candidate)
    extension = ALLOWED_IMAGE_TYPES[mime_type]
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(candidate.title).stem)
    safe_stem = safe_stem.strip(".-_")[:80] or "commons-image"
    inbox = project_root / "runtime/assets/inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    local_path = inbox / f"{safe_stem}-{uuid.uuid4().hex[:8]}{extension}"
    sidecar_path = local_path.with_suffix(local_path.suffix + ".json")

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    sidecar = {
        "source_type": "openverse" if candidate_id.startswith("openverse:") else "wikimedia_commons",
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
