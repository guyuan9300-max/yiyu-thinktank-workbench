"""Trash can service: hold deduped/discarded files with a 2 GB global cap.

Files are physically moved to <data_dir>/.trash/<trashed_id>__<safe_name>
and tracked in the trashed_files table. The cap is enforced on every
trash_file() call via FIFO eviction.
"""

from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

logger = logging.getLogger(__name__)

TRASH_SIZE_LIMIT_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB
TRASH_DIR_NAME = ".trash"

TRASH_REASONS = frozenset({
    "dedup_merge",
    "failed_ingest",
    "user_delete",
})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_trashed_id() -> str:
    return f"trash_{uuid4().hex[:12]}"


def _safe_filename(name: str) -> str:
    cleaned = name.strip().replace("/", "_").replace("\\", "_")
    return cleaned[:200] or "untitled"


def trash_root(data_dir: Path) -> Path:
    root = data_dir / TRASH_DIR_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_status(db, data_dir: Path) -> dict:
    """Return current trash usage stats."""
    row = db.fetchone(
        "SELECT COUNT(1) AS count, COALESCE(SUM(file_size), 0) AS total_bytes, "
        "MIN(trashed_at) AS earliest, MAX(trashed_at) AS latest FROM trashed_files"
    )
    count = int(row["count"] or 0) if row else 0
    total_bytes = int(row["total_bytes"] or 0) if row else 0
    earliest = str(row["earliest"]) if row and row["earliest"] else None
    latest = str(row["latest"]) if row and row["latest"] else None
    return {
        "fileCount": count,
        "totalBytes": total_bytes,
        "limitBytes": TRASH_SIZE_LIMIT_BYTES,
        "usageRatio": (total_bytes / TRASH_SIZE_LIMIT_BYTES) if TRASH_SIZE_LIMIT_BYTES > 0 else 0.0,
        "earliestTrashedAt": earliest,
        "latestTrashedAt": latest,
        "trashDir": str(trash_root(data_dir)),
    }


def trash_file(
    db,
    data_dir: Path,
    *,
    source_path: Path,
    client_id: str = "",
    original_document_id: str = "",
    original_title: str = "",
    reason: str = "dedup_merge",
) -> str | None:
    """Move source_path into the trash dir and record metadata.

    Returns the trashed_file id, or None if source_path is missing.
    """
    if reason not in TRASH_REASONS:
        reason = "dedup_merge"
    if not source_path.exists() or not source_path.is_file():
        logger.warning("[trash] skip non-existent source %s", source_path)
        return None

    file_size = source_path.stat().st_size
    trashed_id = _new_trashed_id()
    safe_name = _safe_filename(source_path.name)
    target = trash_root(data_dir) / f"{trashed_id}__{safe_name}"
    try:
        shutil.move(str(source_path), str(target))
    except OSError as exc:
        logger.error("[trash] move failed %s -> %s: %s", source_path, target, exc)
        return None

    db.execute(
        """
        INSERT INTO trashed_files(
            id, client_id, original_path, trashed_path, file_size,
            original_document_id, original_title, reason, trashed_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            trashed_id,
            client_id or "",
            str(source_path),
            str(target),
            file_size,
            original_document_id or "",
            original_title or source_path.name,
            reason,
            _now_iso(),
        ),
    )

    enforce_size_limit(db, data_dir)
    return trashed_id


def enforce_size_limit(db, data_dir: Path) -> int:
    """Evict oldest entries until total size is under the cap. Returns evicted count."""
    total_bytes = int(
        (db.fetchone("SELECT COALESCE(SUM(file_size), 0) AS s FROM trashed_files") or {"s": 0})["s"]
        or 0
    )
    if total_bytes <= TRASH_SIZE_LIMIT_BYTES:
        return 0

    evicted = 0
    rows = db.fetchall(
        "SELECT id, trashed_path, file_size FROM trashed_files ORDER BY trashed_at ASC"
    )
    for row in rows:
        if total_bytes <= TRASH_SIZE_LIMIT_BYTES:
            break
        target = Path(str(row["trashed_path"]))
        try:
            if target.exists():
                target.unlink()
        except OSError as exc:
            logger.warning("[trash] failed to unlink %s during eviction: %s", target, exc)
        db.execute("DELETE FROM trashed_files WHERE id = ?", (str(row["id"]),))
        total_bytes -= int(row["file_size"] or 0)
        evicted += 1
    return evicted


def clear_all(db, data_dir: Path) -> dict:
    """Empty the trash entirely. Returns {removedCount, freedBytes}."""
    rows = db.fetchall("SELECT id, trashed_path, file_size FROM trashed_files")
    removed = 0
    freed = 0
    for row in rows:
        target = Path(str(row["trashed_path"]))
        try:
            if target.exists():
                target.unlink()
        except OSError as exc:
            logger.warning("[trash] failed to unlink %s during clear: %s", target, exc)
        freed += int(row["file_size"] or 0)
        removed += 1
    db.execute("DELETE FROM trashed_files")

    root = trash_root(data_dir)
    for leftover in root.iterdir():
        if leftover.is_file():
            try:
                leftover.unlink()
            except OSError:
                pass

    return {"removedCount": removed, "freedBytes": freed}
