#!/usr/bin/env python3
"""[B] 2026-05-27 V2.3 Step 2 · v2_documents 本机 dedup 收口

背景:
  扫描发现 26 组 (client_id, content_hash) 重复, 33 行多余.
  · 同一份 PDF SHA-256 完全一样, 但被 INSERT 多次
  · 真因: v2_documents 没 UNIQUE(client_id, content_hash) 约束
  · 真因 2: knowledge_v2.py:2230 是 UPDATE-OR-INSERT 用 v2_document_id 不是 content_hash

策略:
  Phase 1 · 清理已有重复 — 每组保留 imported_at 最早的, 删多余
            v2_chunks/v2_sections 会 CASCADE 跟着删
  Phase 2 · CREATE UNIQUE INDEX(client_id, content_hash) WHERE content_hash != ''
            防止未来再被 INSERT 重复

使用:
  python3 scripts/migrate_v23_dedup_v2_documents.py --db <path> [--apply]
"""
import argparse
import sqlite3
import sys
from pathlib import Path


def find_dup_groups(conn: sqlite3.Connection) -> list[dict]:
    """找出所有 (client_id, content_hash) 有重复的组. 返每组 keep/drop ids."""
    rows = conn.execute(
        """
        SELECT client_id, content_hash, COUNT(*) AS n
        FROM v2_documents
        WHERE content_hash != ''
        GROUP BY client_id, content_hash
        HAVING n > 1
        ORDER BY n DESC, client_id, content_hash
        """
    ).fetchall()
    groups = []
    for client_id, content_hash, _n in rows:
        ids = conn.execute(
            """
            SELECT id, imported_at, file_name
            FROM v2_documents
            WHERE client_id = ? AND content_hash = ?
            ORDER BY imported_at ASC, id ASC
            """,
            (client_id, content_hash),
        ).fetchall()
        keep = ids[0]
        drops = ids[1:]
        groups.append({
            "client_id": client_id,
            "content_hash": content_hash,
            "keep_id": keep[0],
            "keep_imported": keep[1],
            "drop_ids": [r[0] for r in drops],
            "file_name": keep[2],
            "n": len(ids),
        })
    return groups


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not args.db.exists():
        print(f"❌ db 不存在: {args.db}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(args.db)
    # 关键: 启 FK 让 v2_chunks/v2_sections CASCADE 跟着删
    conn.execute("PRAGMA foreign_keys = ON")

    print(f"目标 db: {args.db}")
    print(f"模式: {'APPLY' if args.apply else 'DRY-RUN'}")
    print("=" * 72)

    # ── Phase 1 · 清理重复 ──────────────────────────────
    groups = find_dup_groups(conn)
    print(f"\n[Phase 1] 找到 {len(groups)} 组重复, 共 {sum(len(g['drop_ids']) for g in groups)} 行多余\n")

    total_dropped = 0
    chunks_dropped = 0
    sections_dropped = 0
    for g in groups:
        print(f"  · {g['file_name']:30s} · client={g['client_id']} · hash={g['content_hash'][:12]}... · 共 {g['n']} 行")
        print(f"      保留 {g['keep_id']} (imported_at={g['keep_imported']})")
        for drop_id in g["drop_ids"]:
            # 统计 cascade 会清的关联
            chunk_n = conn.execute(
                "SELECT COUNT(*) FROM v2_chunks WHERE v2_document_id = ?", (drop_id,)
            ).fetchone()[0]
            section_n = conn.execute(
                "SELECT COUNT(*) FROM v2_sections WHERE v2_document_id = ?", (drop_id,)
            ).fetchone()[0]
            print(f"      ⊗ 删 {drop_id} (chunks={chunk_n}, sections={section_n})")
            if args.apply:
                # 不依赖 FK CASCADE — 主动删 chunks/sections, 再删 v2_doc
                # 因为 v2_chunks/v2_sections 的 FK 是 ON DELETE CASCADE 但靠 PRAGMA, 显式更稳
                conn.execute("DELETE FROM v2_chunks WHERE v2_document_id = ?", (drop_id,))
                conn.execute("DELETE FROM v2_sections WHERE v2_document_id = ?", (drop_id,))
                conn.execute("DELETE FROM v2_documents WHERE id = ?", (drop_id,))
            chunks_dropped += chunk_n
            sections_dropped += section_n
            total_dropped += 1

    print(f"\n  小计: 删 v2_documents {total_dropped} 行 · v2_chunks {chunks_dropped} 行 · v2_sections {sections_dropped} 行")

    # ── Phase 2 · 加 UNIQUE INDEX ─────────────────────────
    print(f"\n[Phase 2] 加 UNIQUE INDEX(client_id, content_hash) WHERE content_hash != ''")
    index_exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name='uniq_v2_documents_client_hash'"
    ).fetchone()
    if index_exists:
        print("  ⊘ 索引已存在 (idempotent, 不重建)")
    else:
        if args.apply:
            conn.execute(
                """
                CREATE UNIQUE INDEX uniq_v2_documents_client_hash
                ON v2_documents(client_id, content_hash)
                WHERE content_hash != ''
                """
            )
            print("  ✓ 索引已创建")
        else:
            print("  ⊘ DRY-RUN 模式, 没真创建")

    print()
    print("=" * 72)
    if args.apply:
        conn.commit()
        print("✅ 真改完毕. 已 commit.")
        # 验证
        post_dup = conn.execute(
            """
            SELECT COUNT(*) FROM (
              SELECT 1 FROM v2_documents
              WHERE content_hash != ''
              GROUP BY client_id, content_hash
              HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]
        print(f"   验证: 剩余重复组数 = {post_dup} (应该 0)")
    else:
        print("⊘ DRY-RUN. 加 --apply 真执行.")
        print()
        print("先备份:")
        print("  cp ~/Library/Application\\ Support/YiyuThinkTankWorkbench2_V21Lab/app.db /tmp/app.db.bak-v23-step2")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
