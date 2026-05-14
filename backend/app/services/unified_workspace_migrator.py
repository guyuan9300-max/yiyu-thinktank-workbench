"""One-shot migration: collapse all per-client subfolders into a single
「资料库」 directory, merge same-family duplicates (keep newest), and move
the losers into the global trash. Supports dry-run mode that produces a
preview report without touching disk or DB.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.services.knowledge_v2 import (
    LEGACY_FIXED_CATEGORIES,
    LEGACY_SYSTEM_FOLDER_CATEGORIES,
    UNIFIED_FOLDER_LABEL,
    client_workspace_root,
    derive_document_family_id,
)
from app.services import trash_can

logger = logging.getLogger(__name__)

# Folder names that should NOT be touched (system meta dirs and the new
# unified target itself).
PROTECTED_FOLDER_NAMES = frozenset({"_imports", "_v2_meta", UNIFIED_FOLDER_LABEL, ".trash"})

# All legacy folder labels that should be merged into 「资料库」.
LEGACY_FOLDER_LABELS_TO_MERGE: tuple[str, ...] = tuple(
    {*LEGACY_FIXED_CATEGORIES, *LEGACY_SYSTEM_FOLDER_CATEGORIES, "其他资料", "战略陪伴"}
)


@dataclass
class ClientMigrationReport:
    client_id: str
    client_name: str = ""
    files_moved: int = 0
    files_trashed_as_dedup: int = 0
    families_merged: int = 0
    db_paths_updated: int = 0
    folder_rows_removed: int = 0
    errors: list[str] = field(default_factory=list)
    sample_moves: list[tuple[str, str]] = field(default_factory=list)  # (source, target)
    sample_dedups: list[tuple[str, str]] = field(default_factory=list)  # (kept_id, trashed_path)


@dataclass
class MigrationReport:
    dry_run: bool
    per_client: list[ClientMigrationReport] = field(default_factory=list)
    total_files_moved: int = 0
    total_files_trashed_as_dedup: int = 0
    total_families_merged: int = 0
    total_db_paths_updated: int = 0
    total_folder_rows_removed: int = 0

    def add(self, report: ClientMigrationReport) -> None:
        self.per_client.append(report)
        self.total_files_moved += report.files_moved
        self.total_files_trashed_as_dedup += report.files_trashed_as_dedup
        self.total_families_merged += report.families_merged
        self.total_db_paths_updated += report.db_paths_updated
        self.total_folder_rows_removed += report.folder_rows_removed


def _resolve_unified_dir(data_dir: Path, client_id: str, dry_run: bool) -> Path:
    target = client_workspace_root(data_dir, client_id) / UNIFIED_FOLDER_LABEL
    if not dry_run:
        target.mkdir(parents=True, exist_ok=True)
    return target


def _safe_unique_target(target_dir: Path, name: str, used_names: set[str]) -> Path:
    stem = Path(name).stem or "untitled"
    suffix = Path(name).suffix
    candidate = name
    counter = 1
    while candidate in used_names or (target_dir / candidate).exists():
        candidate = f"{stem}__{counter}{suffix}"
        counter += 1
    used_names.add(candidate)
    return target_dir / candidate


def _legacy_subdirs_for_client(workspace_root: Path) -> list[Path]:
    if not workspace_root.exists():
        return []
    result: list[Path] = []
    for child in workspace_root.iterdir():
        if not child.is_dir():
            continue
        if child.name in PROTECTED_FOLDER_NAMES:
            continue
        # Treat any non-protected, non-meta directory as legacy to merge.
        result.append(child)
    return result


def _all_files_in(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    return [p for p in folder.iterdir() if p.is_file()]


def _migrate_one_client(
    db: Any,
    data_dir: Path,
    client_id: str,
    client_name: str,
    dry_run: bool,
) -> ClientMigrationReport:
    report = ClientMigrationReport(client_id=client_id, client_name=client_name)
    workspace_root = client_workspace_root(data_dir, client_id)
    unified_dir = _resolve_unified_dir(data_dir, client_id, dry_run)
    legacy_dirs = _legacy_subdirs_for_client(workspace_root)

    # Track names already present in unified dir to avoid filename collisions.
    used_names: set[str] = set()
    if unified_dir.exists():
        for existing in unified_dir.iterdir():
            if existing.is_file():
                used_names.add(existing.name)

    # === Step 1: Move physical files from legacy folders into 资料库/ ===
    file_moves: list[tuple[Path, Path]] = []  # (src, dst)
    for legacy_dir in legacy_dirs:
        for src_file in _all_files_in(legacy_dir):
            dst = _safe_unique_target(unified_dir, src_file.name, used_names)
            file_moves.append((src_file, dst))

    for src, dst in file_moves:
        if dry_run:
            report.files_moved += 1
            if len(report.sample_moves) < 5:
                report.sample_moves.append((str(src), str(dst)))
            continue
        try:
            shutil.move(str(src), str(dst))
            report.files_moved += 1
            if len(report.sample_moves) < 5:
                report.sample_moves.append((str(src), str(dst)))
        except OSError as exc:
            report.errors.append(f"move failed {src} -> {dst}: {exc}")

    # === Step 2: UPDATE DB path columns to point into 资料库/ ===
    # For documents whose path lives under any legacy folder of this client,
    # rewrite the prefix.
    legacy_dir_strings = [str(d) + "/" for d in legacy_dirs]
    if legacy_dir_strings:
        like_clauses = " OR ".join(["d.path LIKE ?" for _ in legacy_dir_strings])
        like_params = [f"{prefix}%" for prefix in legacy_dir_strings]
        rows_to_fix = db.fetchall(
            f"SELECT id, path FROM documents d WHERE client_id = ? AND ({like_clauses})",
            (client_id, *like_params),
        )
        for row in rows_to_fix:
            old_path = str(row["path"])
            file_name = Path(old_path).name
            new_path = str(unified_dir / file_name)
            if dry_run:
                report.db_paths_updated += 1
                continue
            db.execute("UPDATE documents SET path = ? WHERE id = ?", (new_path, str(row["id"])))
            report.db_paths_updated += 1

        # Same for v2_documents.managed_path
        v2_rows = db.fetchall(
            f"SELECT id, managed_path FROM v2_documents WHERE client_id = ? AND ({like_clauses.replace('d.path', 'managed_path')})",
            (client_id, *like_params),
        )
        for row in v2_rows:
            old_path = str(row["managed_path"])
            file_name = Path(old_path).name
            new_path = str(unified_dir / file_name)
            if not dry_run:
                db.execute("UPDATE v2_documents SET managed_path = ? WHERE id = ?", (new_path, str(row["id"])))

        # Same for knowledge_documents.current_human_path / normalized_path
        kd_rows = db.fetchall(
            f"SELECT id, current_human_path FROM knowledge_documents WHERE client_id = ? AND ({like_clauses.replace('d.path', 'current_human_path')})",
            (client_id, *like_params),
        )
        for row in kd_rows:
            old_path = str(row["current_human_path"])
            file_name = Path(old_path).name
            new_path = str(unified_dir / file_name)
            if not dry_run:
                db.execute(
                    "UPDATE knowledge_documents SET current_human_path = ?, normalized_path = ? WHERE id = ?",
                    (new_path, new_path, str(row["id"])),
                )

    # === Step 3: family-level dedup (keep newest per family) ===
    family_rows = db.fetchall(
        """
        SELECT id, title, path, created_at, document_family_id
        FROM documents
        WHERE client_id = ? AND canonical_kind = 'raw_file' AND document_family_id != ''
        ORDER BY document_family_id, created_at DESC
        """,
        (client_id,),
    )
    by_family: dict[str, list[dict[str, Any]]] = {}
    for row in family_rows:
        family_id = str(row["document_family_id"] or "")
        if not family_id or ":" not in family_id:
            continue
        stem = family_id.split(":", 1)[1].strip()
        if not stem or stem == "unknown" or len(stem) < 3:
            continue
        by_family.setdefault(family_id, []).append({
            "id": str(row["id"]),
            "title": str(row["title"] or ""),
            "path": str(row["path"] or ""),
            "created_at": str(row["created_at"] or ""),
        })

    for family_id, members in by_family.items():
        if len(members) <= 1:
            continue
        # Members already ORDER BY created_at DESC, so members[0] is the newest.
        report.families_merged += 1
        keeper = members[0]
        losers = members[1:]
        for loser in losers:
            loser_path = Path(loser["path"]) if loser["path"] else None
            if dry_run:
                report.files_trashed_as_dedup += 1
                if len(report.sample_dedups) < 5:
                    report.sample_dedups.append((keeper["id"], loser["path"]))
                continue
            if loser_path and loser_path.exists() and loser_path.is_file():
                trash_can.trash_file(
                    db,
                    data_dir,
                    source_path=loser_path,
                    client_id=client_id,
                    original_document_id=loser["id"],
                    original_title=loser["title"],
                    reason="dedup_merge",
                )
            # Remove DB rows for the loser (cascade through related tables).
            db.execute("DELETE FROM knowledge_master_index WHERE surrogate_id IN (SELECT id FROM knowledge_surrogates WHERE knowledge_document_id IN (SELECT id FROM knowledge_documents WHERE document_id = ?))", (loser["id"],))
            db.execute("DELETE FROM knowledge_surrogates WHERE knowledge_document_id IN (SELECT id FROM knowledge_documents WHERE document_id = ?)", (loser["id"],))
            db.execute("DELETE FROM v2_chunks WHERE v2_document_id IN (SELECT id FROM v2_documents WHERE document_id = ?)", (loser["id"],))
            db.execute("DELETE FROM v2_sections WHERE v2_document_id IN (SELECT id FROM v2_documents WHERE document_id = ?)", (loser["id"],))
            db.execute("DELETE FROM v2_documents WHERE document_id = ?", (loser["id"],))
            db.execute("DELETE FROM knowledge_documents WHERE document_id = ?", (loser["id"],))
            db.execute("DELETE FROM documents WHERE id = ?", (loser["id"],))
            report.files_trashed_as_dedup += 1
            if len(report.sample_dedups) < 5:
                report.sample_dedups.append((keeper["id"], loser["path"]))

    # === Step 4: remove empty legacy directories ===
    if not dry_run:
        for legacy_dir in legacy_dirs:
            try:
                if legacy_dir.exists() and not any(legacy_dir.iterdir()):
                    legacy_dir.rmdir()
            except OSError as exc:
                report.errors.append(f"rmdir {legacy_dir}: {exc}")

    # === Step 5: drop non-资料库 client_folders rows ===
    folder_rows = db.fetchall(
        "SELECT id, label FROM client_folders WHERE client_id = ? AND label != ?",
        (client_id, UNIFIED_FOLDER_LABEL),
    )
    for row in folder_rows:
        report.folder_rows_removed += 1
        if dry_run:
            continue
        db.execute("UPDATE documents SET folder_id = NULL WHERE folder_id = ?", (str(row["id"]),))
        db.execute("DELETE FROM client_folders WHERE id = ?", (str(row["id"]),))

    return report


def migrate_all_clients(db: Any, data_dir: Path, *, dry_run: bool = True) -> MigrationReport:
    report = MigrationReport(dry_run=dry_run)
    rows = db.fetchall("SELECT id, name FROM clients ORDER BY name")
    for row in rows:
        client_id = str(row["id"])
        client_name = str(row["name"] or client_id)
        try:
            client_report = _migrate_one_client(db, data_dir, client_id, client_name, dry_run)
        except Exception as exc:
            logger.exception("[unified-migrator] failed on client %s", client_id)
            client_report = ClientMigrationReport(
                client_id=client_id,
                client_name=client_name,
                errors=[f"migration crashed: {exc}"],
            )
        report.add(client_report)
    return report


def format_report(report: MigrationReport) -> str:
    mode = "DRY-RUN" if report.dry_run else "EXECUTED"
    lines: list[str] = [
        f"=== 统一文件夹迁移报告 ({mode}) ===",
        f"客户数: {len(report.per_client)}",
        f"总迁移文件数: {report.total_files_moved}",
        f"去重合并 families: {report.total_families_merged}",
        f"进垃圾桶文件数: {report.total_files_trashed_as_dedup}",
        f"DB path 更新数: {report.total_db_paths_updated}",
        f"删除 client_folders 行: {report.total_folder_rows_removed}",
        "",
        "=== 每客户明细 ===",
    ]
    for cr in report.per_client:
        lines.append(
            f"- {cr.client_name} ({cr.client_id}): 搬 {cr.files_moved} | "
            f"去重 {cr.files_trashed_as_dedup}（{cr.families_merged} 个 family）| "
            f"path 更新 {cr.db_paths_updated} | 删 folder 行 {cr.folder_rows_removed}"
            + (f" | 错误 {len(cr.errors)} 条" if cr.errors else "")
        )
        for src, dst in cr.sample_moves[:3]:
            lines.append(f"    搬: …/{Path(src).parent.name}/{Path(src).name} → …/{UNIFIED_FOLDER_LABEL}/{Path(dst).name}")
        for kept_id, loser_path in cr.sample_dedups[:3]:
            lines.append(f"    去重: 保留 {kept_id}，扔: {Path(loser_path).name}")
        for err in cr.errors[:3]:
            lines.append(f"    ⚠ {err}")
    return "\n".join(lines)
