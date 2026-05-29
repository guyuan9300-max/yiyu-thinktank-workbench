#!/usr/bin/env python3
"""[B] 2026-05-27 V2.3 Step 2.5 · 历史 v2_documents 反查回写 source_registry

背景:
  Step 0/1 修后, 新导入的 raw_file 和 upsert canonical 都接通了 source_registry.
  但历史 1020 条 v2_documents (file_import + task + meeting + judgment + 等) 没登记.
  Step 3 sync executor 按 source_registry 扫时会漏 99.8% 数据.

策略:
  对每条 v2_documents (organization_id 非空 + 没 source_registry 对应) 回写:
    - source_id = src_<uuid>
    - source_type = origin_type 映射 (按 V2.3 蓝图)
    - source_channel = "canonical_<canonical_kind>" / "local_workspace"
    - client_id / org_id / user_id 跟 v2_documents 一致
    - content_hash = _compute_content_hash(content_hash)
      ↑ 注意 source_registry.content_hash 内部 hash 一次 v2_documents.content_hash 字符串
        而不是文件 SHA-256. 这样 backfill 跟 register_source 调用产生的 hash 一致.
    - raw_reference = v2_document_id

UNIQUE 约束:
  source_registry.source_id PK
  没 (org_id, content_hash) UNIQUE → 重复 OK
  但如果实际同 content_hash 多条 source 会有冗余, 接受 (因为 raw_reference 唯一)

使用:
  python3 scripts/migrate_v23_backfill_source_registry.py --db <path> [--apply]
"""
import argparse
import hashlib
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


# origin_type → source_type 映射 (跟 V2.3 蓝图 + Step 1.5 一致)
SOURCE_TYPE_MAP = {
    "file_import": "file_import",
    "task": "task_review",
    "meeting": "task_review",
    "weekly_review": "task_review",
    "weekly_review_entry": "task_review",
    "judgment_version": "ai_inference",
    "internet_source": "internet_crawl",
    "internet_fact_card": "internet_crawl",
    "internet_enrichment": "internet_crawl",
    "wechat_sogou_search": "internet_crawl",
    "event_line": "task_review",
    "event_line_manual_update": "task_review",
    "calendar_rollup": "task_review",
    "project_module": "task_review",
    "video_transcript": "file_import",
}


def _compute_content_hash(content: str) -> str:
    """Mirror source_registry_store._compute_content_hash so backfill matches future register_source calls."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--batch-size", type=int, default=200)
    args = parser.parse_args()

    if not args.db.exists():
        print(f"❌ db 不存在: {args.db}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    print(f"目标 db: {args.db}")
    print(f"模式: {'APPLY' if args.apply else 'DRY-RUN'}")
    print("=" * 72)

    # 找待 backfill 的 v2_documents (有 org_id 但 raw_reference 不在 source_registry 里)
    rows = conn.execute(
        """
        SELECT vd.id AS v2_document_id, vd.client_id, vd.organization_id, vd.owner_user_id,
               vd.department_id, vd.visibility_scope, vd.content_hash, vd.origin_type,
               vd.canonical_kind, vd.imported_at
        FROM v2_documents vd
        LEFT JOIN source_registry sr
          ON sr.raw_reference = vd.id
        WHERE sr.source_id IS NULL
          AND vd.organization_id != ''
          AND vd.content_hash != ''
        ORDER BY vd.imported_at
        """
    ).fetchall()

    print(f"\n找到 {len(rows)} 条待 backfill 的 v2_documents (有 org_id 且无 source_registry 关联)")

    # origin_type 分布预览
    origin_dist: dict[str, int] = {}
    for r in rows:
        origin_dist[r["origin_type"]] = origin_dist.get(r["origin_type"], 0) + 1
    print(f"\nbackfill 真分布 (按 origin_type → source_type):")
    for ot, n in sorted(origin_dist.items(), key=lambda x: -x[1]):
        st = SOURCE_TYPE_MAP.get(ot, "ai_inference")
        print(f"  {ot:25s} → {st:18s} ({n} 条)")

    if not args.apply:
        print()
        print("=" * 72)
        print("⊘ DRY-RUN. 加 --apply 真执行.")
        print()
        print("先备份:")
        print("  cp ~/Library/Application\\ Support/YiyuThinkTankWorkbench2_V21Lab/app.db /tmp/app.db.bak-v23-step25")
        conn.close()
        return 0

    # 真 INSERT
    inserted = 0
    skipped_conflict = 0
    errors = 0
    for i, row in enumerate(rows):
        try:
            origin_type = row["origin_type"]
            source_type = SOURCE_TYPE_MAP.get(origin_type, "ai_inference")
            source_channel = f"canonical_{row['canonical_kind']}" if origin_type != "file_import" else "local_workspace"
            content_hash = _compute_content_hash(row["content_hash"])
            source_id = f"src_{uuid.uuid4().hex[:24]}"
            visibility = row["visibility_scope"] or "project_public"
            # source_registry.visibility_scope: 'org' 之类, 不是 v2 的 project_public
            # 简化: project_public → org (代表组织内可见)
            if visibility == "project_public":
                sr_visibility = "org"
            else:
                sr_visibility = visibility

            now = _now_iso()
            conn.execute(
                """
                INSERT INTO source_registry(
                    source_id, source_type, source_channel, source_owner,
                    client_id, user_id, org_id,
                    capture_time, source_time, visibility_scope, content_hash,
                    version_id, source_role, initial_confidence, raw_reference,
                    status, created_at, updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    source_type,
                    source_channel,
                    row["owner_user_id"] or None,
                    row["client_id"],
                    row["owner_user_id"] or None,
                    row["organization_id"],
                    now,
                    row["imported_at"] or now,
                    sr_visibility,
                    content_hash,
                    "v1",
                    "generated" if origin_type != "file_import" else "file",
                    0.85,  # 历史数据置信度中等
                    row["v2_document_id"],  # 反向关联 v2_documents
                    "active",
                    now,
                    now,
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError as exc:
            skipped_conflict += 1
            if skipped_conflict <= 3:
                print(f"  ⊘ IntegrityError (skip): {exc}")
        except Exception as exc:
            errors += 1
            print(f"  ⚠ error on row {row['v2_document_id']}: {exc}")

        if (i + 1) % args.batch_size == 0:
            conn.commit()
            print(f"  · 已处理 {i + 1}/{len(rows)} (inserted={inserted}, skipped={skipped_conflict}, errors={errors})")

    conn.commit()
    print()
    print("=" * 72)
    print(f"✅ 完成:")
    print(f"   · inserted: {inserted}")
    print(f"   · skipped (IntegrityError): {skipped_conflict}")
    print(f"   · errors: {errors}")
    print(f"   · 总待处理: {len(rows)}")

    # 验证
    post_total = conn.execute("SELECT COUNT(*) FROM source_registry").fetchone()[0]
    post_file_import = conn.execute(
        "SELECT COUNT(*) FROM source_registry WHERE source_type = 'file_import'"
    ).fetchone()[0]
    post_orphan = conn.execute(
        """
        SELECT COUNT(*) FROM v2_documents vd
        LEFT JOIN source_registry sr ON sr.raw_reference = vd.id
        WHERE sr.source_id IS NULL AND vd.organization_id != ''
        """
    ).fetchone()[0]
    print(f"\n验证:")
    print(f"   · source_registry 总数: {post_total}")
    print(f"   · source_type=file_import: {post_file_import}")
    print(f"   · v2_documents 仍无 source_registry: {post_orphan}")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
