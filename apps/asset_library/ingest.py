from __future__ import annotations

import mimetypes
import shutil
import uuid
from pathlib import Path
from typing import Iterable

from .registry import (
    AssetRecord,
    connect,
    file_sha256,
    infer_asset_type,
    read_sidecar,
    technical_metadata,
)
from .source_registry import (
    get_current_source_revision,
    get_source_revision,
)


SUPPORTED_SKIP = {".json"}


def iter_files(inbox: Path) -> Iterable[Path]:
    for path in sorted(inbox.rglob("*")):
        if path.is_file() and path.suffix.lower() not in SUPPORTED_SKIP:
            yield path


def ingest_one(
    inbox: Path,
    library_root: Path,
    db_path: Path,
    path: Path,
) -> str:
    digest = file_sha256(path)
    conn = connect(db_path)
    try:
        duplicate = conn.execute(
            "SELECT asset_id FROM assets WHERE sha256 = ?",
            (digest,),
        ).fetchone()
        if duplicate:
            return f"duplicate:{duplicate['asset_id']}"

        sidecar = read_sidecar(path)
        asset_type = infer_asset_type(path)
        mime_type = mimetypes.guess_type(path.name)[0]
        metadata = technical_metadata(
            path,
            asset_type,
            mime_type,
        )
        sidecar_metadata = sidecar.get("metadata", {})
        if not isinstance(sidecar_metadata, dict):
            raise ValueError("Provenance sidecar metadata must be an object")
        metadata.update(sidecar_metadata)
        metadata["ingest_source"] = "local_inbox"
        metadata["provenance_sidecar"] = bool(sidecar)

        source_type = str(sidecar.get("source_type", "unknown"))
        source_url = sidecar.get("source_url")
        creator = sidecar.get("creator")
        license_type = sidecar.get("license_type")
        rights_state = str(
            sidecar.get("rights_state", "unverified")
        )
        lifecycle_state = str(
            sidecar.get("lifecycle_state", "ingested")
        )

        source_id = sidecar.get("source_id")
        source_revision_id = sidecar.get("source_revision_id")
        if source_id:
            if source_revision_id:
                revision = get_source_revision(
                    conn,
                    source_revision_id,
                )
                if revision is None or revision.source_id != source_id:
                    raise ValueError(
                        "sidecar source_revision_id does not match source_id"
                    )
            else:
                revision = get_current_source_revision(
                    conn,
                    source_id,
                )
                if revision is None:
                    raise ValueError(
                        f"unknown source_id: {source_id}"
                    )
                source_revision_id = revision.revision_id

        asset_id = f"asset-{uuid.uuid4().hex[:12]}"
        destination_dir = library_root / asset_type
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / path.name
        if destination.exists():
            destination = (
                destination_dir
                / f"{path.stem}-{digest[:8]}{path.suffix}"
            )
        shutil.copy2(path, destination)

        try:
            record = AssetRecord(
                asset_id=asset_id,
                original_name=path.name,
                stored_path=destination.relative_to(
                    library_root.parent.parent.parent
                ).as_posix(),
                asset_type=asset_type,
                mime_type=mime_type,
                size_bytes=path.stat().st_size,
                sha256=digest,
                source_type=source_type,
                source_url=source_url,
                creator=creator,
                license_type=license_type,
                rights_state=rights_state,
                lifecycle_state=lifecycle_state,
                market_code=sidecar.get("market_code"),
                category_code=sidecar.get("category_code"),
                subject_type=sidecar.get("subject_type"),
                subject_id=sidecar.get("subject_id"),
                competition_code=sidecar.get("competition_code"),
                purpose_code=sidecar.get("purpose_code"),
                metadata=metadata,
                source_id=source_id,
                source_revision_id=source_revision_id,
            )
            from .registry import upsert_asset
            upsert_asset(conn, record)
            conn.commit()
            return f"ingested:{asset_id}"
        except Exception:
            destination.unlink(missing_ok=True)
            raise
    finally:
        conn.close()


def ingest_inbox(project_root: Path) -> list[str]:
    inbox = project_root / "runtime/assets/inbox"
    library_root = project_root / "runtime/assets/library"
    db_path = project_root / "runtime/engine.db"
    results: list[str] = []
    for path in iter_files(inbox):
        try:
            results.append(
                ingest_one(
                    inbox,
                    library_root,
                    db_path,
                    path,
                )
            )
        except Exception as exc:
            results.append(
                f"error:{path.name}:{exc}"
            )
    return results
