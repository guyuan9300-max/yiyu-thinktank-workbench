#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


SYSTEM_FOLDERS = ("收件箱", "线上转写", "待处理", "归档")
ONLINE_TRANSCRIPT_FOLDER = "线上转写"
PENDING_FOLDER = "待处理"
LEGACY_FOLDERS = {
    "财务与筹款",
    "品牌与传播",
    "项目与业务",
    "组织与战略",
    "其他资料",
    "战略陪伴",
}


@dataclass
class RebucketPlan:
    client_id: str
    client_name: str
    document_id: str
    title: str
    current_label: str
    target_label: str
    old_path: str
    new_path: str | None
    reason: str


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def safe_filename(value: str) -> str:
    cleaned = "".join("_" if ch in '/\\:*?"<>|' else ch for ch in value.strip())
    return cleaned or "未命名"


def db_path_default() -> Path:
    return Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2/app.db"


def backup_database(db_path: Path) -> Path:
    backup_path = db_path.with_name(f"{db_path.stem}.before-folder-rebucket-{datetime.now().strftime('%Y%m%d-%H%M%S')}{db_path.suffix}")
    source = sqlite3.connect(str(db_path))
    try:
        target = sqlite3.connect(str(backup_path))
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()
    return backup_path


def fetchall(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    return list(conn.execute(sql, params))


def ensure_folder(conn: sqlite3.Connection, *, data_dir: Path, client_id: str, label: str) -> str:
    rows = fetchall(
        conn,
        """
        SELECT *
        FROM client_folders
        WHERE client_id = ? AND label = ?
        ORDER BY is_system DESC, file_count DESC, created_at ASC
        """,
        (client_id, label),
    )
    if rows:
        canonical = rows[0]
        folder_id = str(canonical["id"])
        conn.execute(
            """
            UPDATE client_folders
            SET folder_kind = 'system', source_type = 'system', is_system = 1,
                is_hidden = 0, sort_order = ?, created_by_rule = 'system_default',
                path = ?
            WHERE id = ?
            """,
            (
                SYSTEM_FOLDERS.index(label) * 10 if label in SYSTEM_FOLDERS else 100,
                str(data_dir / "client_workspace" / client_id / safe_filename(label)),
                folder_id,
            ),
        )
        for duplicate in rows[1:]:
            conn.execute(
                "UPDATE client_folders SET is_hidden = 1, file_count = 0 WHERE id = ?",
                (str(duplicate["id"]),),
            )
        return folder_id

    folder_id = f"fld_rebucket_{client_id[-6:]}_{abs(hash((client_id, label))) % 10_000_000:07d}"
    timestamp = now_iso()
    folder_path = data_dir / "client_workspace" / client_id / safe_filename(label)
    folder_path.mkdir(parents=True, exist_ok=True)
    conn.execute(
        """
        INSERT INTO client_folders(
            id, client_id, label, path, file_count, last_scanned_at, created_at,
            folder_kind, source_type, is_system, is_hidden, sort_order, created_by_rule, suggested
        )
        VALUES(?, ?, ?, ?, 0, ?, ?, 'system', 'system', 1, 0, ?, 'system_default', 0)
        """,
        (
            folder_id,
            client_id,
            label,
            str(folder_path),
            timestamp,
            timestamp,
            SYSTEM_FOLDERS.index(label) * 10 if label in SYSTEM_FOLDERS else 100,
        ),
    )
    return folder_id


def path_with_collision_guard(target_dir: Path, source_path: Path, document_id: str) -> Path:
    target_path = target_dir / source_path.name
    if not target_path.exists() or target_path.resolve() == source_path.resolve():
        return target_path
    return target_dir / f"{source_path.stem}-{document_id}{source_path.suffix}"


def is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def classify_target(row: sqlite3.Row) -> tuple[str, str]:
    source = str(row["source"] or "")
    origin_type = str(row["origin_type"] or "")
    source_entity_type = str(row["source_entity_type"] or "")
    material_layer = str(row["material_layer"] or "")
    visible_category = str(row["visible_category"] or "")
    folder_kind = str(row["folder_kind"] or "")
    source_type = str(row["folder_source_type"] or "")
    created_by_rule = str(row["created_by_rule"] or "")
    current_label = str(row["current_label"] or visible_category or "")
    if (
        source == "video_transcript"
        or origin_type == "video_transcript"
        or source_entity_type == "video_transcript"
        or material_layer == "external_media_transcript"
        or visible_category == ONLINE_TRANSCRIPT_FOLDER
    ):
        return ONLINE_TRANSCRIPT_FOLDER, "video_transcript"
    if created_by_rule == "manual" and source_type == "user" and current_label and current_label not in SYSTEM_FOLDERS:
        return current_label, "manual_folder_preserved"
    if current_label in SYSTEM_FOLDERS:
        return current_label, "system_folder_preserved"
    if current_label in LEGACY_FOLDERS or folder_kind == "legacy_business" or source_type == "legacy":
        return PENDING_FOLDER, "legacy_folder_collapsed"
    return PENDING_FOLDER, "uncertain_to_pending"


def build_plan(conn: sqlite3.Connection, data_dir: Path, *, move_files: bool) -> list[RebucketPlan]:
    rows = fetchall(
        conn,
        """
        SELECT
            d.id AS document_id,
            d.client_id,
            c.name AS client_name,
            d.title,
            d.path AS document_path,
            d.source,
            d.origin_type,
            d.source_entity_type,
            v.material_layer,
            v.visible_category,
            k.human_folder_category,
            cf.label AS folder_label,
            cf.folder_kind,
            cf.source_type AS folder_source_type,
            cf.created_by_rule
        FROM documents d
        LEFT JOIN clients c ON c.id = d.client_id
        LEFT JOIN v2_documents v ON v.client_id = d.client_id AND v.document_id = d.id
        LEFT JOIN knowledge_documents k ON k.client_id = d.client_id AND k.document_id = d.id
        LEFT JOIN client_folders cf ON cf.id = d.folder_id
        WHERE d.client_id IS NOT NULL
        ORDER BY c.name, d.created_at
        """,
    )
    plans: list[RebucketPlan] = []
    for row in rows:
        current_label = str(row["folder_label"] or row["visible_category"] or row["human_folder_category"] or "")
        wrapped = dict(row)
        wrapped["current_label"] = current_label
        target_label, reason = classify_target(wrapped)  # type: ignore[arg-type]
        old_path = str(row["document_path"] or "")
        new_path: str | None = None
        if move_files and old_path:
            source_path = Path(old_path)
            client_root = data_dir / "client_workspace" / str(row["client_id"])
            if is_under(source_path, client_root):
                target_dir = client_root / safe_filename(target_label)
                target_path = path_with_collision_guard(target_dir, source_path, str(row["document_id"]))
                if target_path.resolve() != source_path.resolve() and (source_path.exists() or target_path.exists()):
                    new_path = str(target_path)
        if current_label != target_label or new_path:
            plans.append(
                RebucketPlan(
                    client_id=str(row["client_id"]),
                    client_name=str(row["client_name"] or row["client_id"]),
                    document_id=str(row["document_id"]),
                    title=str(row["title"] or ""),
                    current_label=current_label or "(未归类)",
                    target_label=target_label,
                    old_path=old_path,
                    new_path=new_path,
                    reason=reason,
                )
            )
    return plans


def update_path_fields(conn: sqlite3.Connection, plan: RebucketPlan) -> str:
    if not plan.new_path:
        return plan.old_path
    source_path = Path(plan.old_path)
    target_path = Path(plan.new_path)
    if not source_path.exists():
        # Idempotency: a previous interrupted rebucket may already have moved a shared physical file.
        if target_path.exists():
            return str(target_path)
        return plan.old_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source_path), str(target_path))
    return str(target_path)


def apply_plan(conn: sqlite3.Connection, data_dir: Path, plans: list[RebucketPlan]) -> None:
    timestamp = now_iso()
    for plan in plans:
        folder_id = ensure_folder(conn, data_dir=data_dir, client_id=plan.client_id, label=plan.target_label)
        final_path = update_path_fields(conn, plan)
        conn.execute(
            """
            UPDATE documents
            SET folder_id = ?,
                path = ?,
                original_source_path = CASE WHEN original_source_path = ? THEN ? ELSE original_source_path END
            WHERE id = ? AND client_id = ?
            """,
            (folder_id, final_path, plan.old_path, final_path, plan.document_id, plan.client_id),
        )
        conn.execute(
            """
            UPDATE v2_documents
            SET visible_category = ?,
                secondary_category = ?,
                managed_path = CASE WHEN managed_path = ? THEN ? ELSE managed_path END,
                markdown_path = CASE WHEN markdown_path = ? THEN ? ELSE markdown_path END,
                original_path = CASE WHEN original_path = ? THEN ? ELSE original_path END,
                updated_at = ?
            WHERE client_id = ? AND document_id = ?
            """,
            (
                plan.target_label,
                plan.target_label,
                plan.old_path,
                final_path,
                plan.old_path,
                final_path,
                plan.old_path,
                final_path,
                timestamp,
                plan.client_id,
                plan.document_id,
            ),
        )
        conn.execute(
            """
            UPDATE knowledge_documents
            SET human_folder_category = ?,
                current_human_path = CASE WHEN current_human_path = ? THEN ? ELSE current_human_path END,
                normalized_path = CASE WHEN normalized_path = ? THEN ? ELSE normalized_path END,
                reclassified_at = ?,
                reclass_reason = ?,
                reclass_confidence = 1.0,
                updated_at = ?
            WHERE client_id = ? AND document_id = ?
            """,
            (
                plan.target_label,
                plan.old_path,
                final_path,
                plan.old_path,
                final_path,
                timestamp,
                f"bulk_folder_rebucket:{plan.reason}",
                timestamp,
                plan.client_id,
                plan.document_id,
            ),
        )
        conn.execute(
            """
            UPDATE knowledge_surrogates
            SET folder_category = ?, updated_at = ?
            WHERE knowledge_document_id IN (
                SELECT id FROM knowledge_documents WHERE client_id = ? AND document_id = ?
            )
            """,
            (plan.target_label, timestamp, plan.client_id, plan.document_id),
        )
        conn.execute(
            """
            UPDATE knowledge_master_index
            SET folder_category = ?,
                source_path = CASE WHEN source_path = ? THEN ? ELSE source_path END,
                updated_at = ?
            WHERE surrogate_id IN (
                SELECT id FROM knowledge_surrogates
                WHERE knowledge_document_id IN (
                    SELECT id FROM knowledge_documents WHERE client_id = ? AND document_id = ?
                )
            )
            """,
            (plan.target_label, plan.old_path, final_path, timestamp, plan.client_id, plan.document_id),
        )
    refresh_folder_rows(conn, data_dir)


def refresh_folder_rows(conn: sqlite3.Connection, data_dir: Path) -> None:
    timestamp = now_iso()
    # Ensure system folders exist only when needed by future code, then recalculate counts.
    for row in fetchall(conn, "SELECT DISTINCT id FROM clients"):
        client_id = str(row["id"])
        for label in SYSTEM_FOLDERS:
            ensure_folder(conn, data_dir=data_dir, client_id=client_id, label=label)

    folder_rows = fetchall(conn, "SELECT * FROM client_folders")
    for row in folder_rows:
        client_id = str(row["client_id"])
        label = str(row["label"])
        folder_id = str(row["id"])
        knowledge_count = int(
            conn.execute(
                "SELECT COUNT(1) FROM knowledge_documents WHERE client_id = ? AND human_folder_category = ?",
                (client_id, label),
            ).fetchone()[0]
            or 0
        )
        v2_count = int(
            conn.execute(
                "SELECT COUNT(1) FROM v2_documents WHERE client_id = ? AND visible_category = ?",
                (client_id, label),
            ).fetchone()[0]
            or 0
        )
        document_count = int(
            conn.execute(
                "SELECT COUNT(1) FROM documents WHERE client_id = ? AND folder_id = ?",
                (client_id, folder_id),
            ).fetchone()[0]
            or 0
        )
        file_count = max(knowledge_count, v2_count, document_count)
        is_system = int(row["is_system"] or 0) == 1
        created_by_rule = str(row["created_by_rule"] or "")
        source_type = str(row["source_type"] or "")
        is_hidden = 0 if file_count > 0 or (created_by_rule == "manual" and source_type == "user") else 1
        # Keep canonical system rows identifiable, but still hidden when empty.
        if label in SYSTEM_FOLDERS and is_system:
            folder_kind = "system"
            source_type_value = "system"
        else:
            folder_kind = str(row["folder_kind"] or "business")
            source_type_value = source_type or "legacy"
        conn.execute(
            """
            UPDATE client_folders
            SET file_count = ?, last_scanned_at = ?, is_hidden = ?,
                folder_kind = ?, source_type = ?
            WHERE id = ?
            """,
            (file_count, timestamp, is_hidden, folder_kind, source_type_value, folder_id),
        )
    dedupe_folder_rows(conn)


def dedupe_folder_rows(conn: sqlite3.Connection) -> None:
    duplicates = fetchall(
        conn,
        """
        SELECT client_id, label, COUNT(1) AS count
        FROM client_folders
        GROUP BY client_id, label
        HAVING COUNT(1) > 1
        """,
    )
    for duplicate in duplicates:
        rows = fetchall(
            conn,
            """
            SELECT *
            FROM client_folders
            WHERE client_id = ? AND label = ?
            ORDER BY is_system DESC, file_count DESC, created_at ASC
            """,
            (str(duplicate["client_id"]), str(duplicate["label"])),
        )
        if not rows:
            continue
        canonical_id = str(rows[0]["id"])
        for row in rows[1:]:
            duplicate_id = str(row["id"])
            conn.execute(
                "UPDATE documents SET folder_id = ? WHERE folder_id = ?",
                (canonical_id, duplicate_id),
            )
            conn.execute(
                "UPDATE client_folders SET is_hidden = 1, file_count = 0 WHERE id = ?",
                (duplicate_id,),
            )


def print_summary(plans: list[RebucketPlan]) -> None:
    by_client: dict[str, dict[str, int]] = {}
    for plan in plans:
        key = f"{plan.client_name} ({plan.client_id})"
        by_client.setdefault(key, {})
        bucket = f"{plan.current_label} -> {plan.target_label}"
        by_client[key][bucket] = by_client[key].get(bucket, 0) + 1
    print(f"planned_changes={len(plans)}")
    for client, buckets in sorted(by_client.items()):
        print(f"\n{client}")
        for bucket, count in sorted(buckets.items(), key=lambda item: (-item[1], item[0])):
            print(f"  {bucket}: {count}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebucket legacy workspace folders into the new dynamic folder model.")
    parser.add_argument("--db", default=str(db_path_default()))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--move-files", action="store_true", help="Move managed files inside client_workspace to the new folder.")
    args = parser.parse_args()

    db_path = Path(args.db).expanduser()
    if not db_path.exists():
        raise SystemExit(f"database not found: {db_path}")
    data_dir = db_path.parent

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        plans = build_plan(conn, data_dir, move_files=args.move_files)
        print_summary(plans)
        if not args.apply:
            print("\ndry-run only. rerun with --apply to update metadata.")
            return 0
        backup_path = backup_database(db_path)
        print(f"\nbackup={backup_path}")
        with conn:
            apply_plan(conn, data_dir, plans)
        print("applied=true")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
