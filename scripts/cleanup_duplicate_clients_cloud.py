#!/usr/bin/env python3
"""[B] 5/25 PM · 清理云端 clients 表里同名重复条目.

背景:
  顾源源 5/25 反馈"同事 sync 后看到 2 个益语智库 + 2 个日慈".
  真因: cloud_backend POST /clients 之前只按 id dedup, 不按 name. 同一 org 同名 client 被 INSERT 多次.
  本脚本已修 cloud_backend 加 name dedup (防未来), 这个脚本清理云端 db 已有重复.

策略:
  · 找所有 org 里 name 重复的 client (COUNT > 1)
  · 保留最老的 (created_at 最小) 当 canonical
  · 其他重复条目: 把它们关联的资源 (tasks/documents/etc) 改成 canonical id, 然后删
  · 全程 dry-run 默认, --apply 真改 db

使用:
  # dry-run (默认, 不改 db):
  python3 scripts/cleanup_duplicate_clients_cloud.py --db <path-to-cloud-db>

  # 真改:
  python3 scripts/cleanup_duplicate_clients_cloud.py --db <path-to-cloud-db> --apply

参数:
  --db    云端 db 路径 (cloud_backend 的 sqlite 文件)
  --apply 真执行 DELETE + UPDATE (默认 dry-run)
"""
import argparse
import sqlite3
import sys
from pathlib import Path


def _has_column(conn, table: str, column: str) -> bool:
    """sqlite pragma 查表里是否真有这个字段 (兼容老 schema)."""
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return any(str(r[1]) == column for r in rows)
    except Exception:
        return False


def find_duplicate_groups(conn) -> list[dict]:
    """找同 org 同名的 client 重复组. 返 [{org_id, name, ids: [...]}]

    顾源源 5/25 PM (Codex 反馈): 线上 clients 表没 frozen_at 字段.
    兼容: 自动检测字段存在与否, 没有就跳过 frozen 过滤.
    """
    has_frozen = _has_column(conn, "clients", "frozen_at")
    extra_where = "AND COALESCE(frozen_at, '') = ''" if has_frozen else ""
    rows = conn.execute(
        f"""SELECT organization_id, name, GROUP_CONCAT(id, '|') AS ids, COUNT(*) AS n
            FROM clients
            WHERE name IS NOT NULL AND TRIM(name) != ''
              {extra_where}
            GROUP BY organization_id, name
            HAVING n > 1
            ORDER BY n DESC, organization_id, name"""
    ).fetchall()
    out = []
    for row in rows:
        org_id, name, ids_csv, n = row
        ids = ids_csv.split("|")
        # 拉每个 id 的 created_at, 排序保留最老的
        details = []
        for cid in ids:
            crow = conn.execute(
                "SELECT id, created_at, updated_at FROM clients WHERE id = ?", (cid,)
            ).fetchone()
            if crow:
                details.append({"id": crow[0], "created_at": crow[1] or "", "updated_at": crow[2] or ""})
        details.sort(key=lambda x: x["created_at"])
        out.append({"org_id": org_id, "name": name, "n": n, "details": details})
    return out


def find_related_tables(conn) -> list[str]:
    """找 db 里有 client_id 字段的表 (重复合并时要 UPDATE 它们).

    只查 schema, 不真扫数据. 返 table_name 列表.
    """
    rows = conn.execute(
        """SELECT m.name FROM sqlite_master m
           WHERE m.type='table' AND m.sql LIKE '%client_id%'
             AND m.name != 'clients'"""
    ).fetchall()
    return [row[0] for row in rows]


def merge_duplicate(conn, keep_id: str, drop_ids: list[str],
                     related_tables: list[str], apply: bool) -> dict:
    """把 drop_ids 关联的资源迁到 keep_id, 然后删 drop_ids 行.

    [B] 5/25 PM 真用 bug fix: 某些表有 UNIQUE(client_id, X) 约束, 直接 UPDATE 会撞.
    修法: 用 UPDATE OR IGNORE (sqlite 支持) + 然后 DELETE 没合并成功的源行.
    保留 keep_id 那边的版本 (dest 已有, 信息更新), drop 那边重复版本作废.
    """
    stats = {"tables_updated": 0, "rows_moved": 0, "rows_dropped_conflict": 0, "clients_deleted": 0}

    for table in related_tables:
        placeholders = ",".join("?" * len(drop_ids))
        count_sql = f"SELECT COUNT(*) FROM {table} WHERE client_id IN ({placeholders})"
        try:
            cnt = conn.execute(count_sql, drop_ids).fetchone()[0]
        except sqlite3.OperationalError:
            continue
        if cnt == 0:
            continue
        stats["tables_updated"] += 1
        if apply:
            # 步骤 1: UPDATE OR IGNORE — 冲突的行不动 (但 sqlite IGNORE 不会真静默, 我们用 try)
            # 用 OR IGNORE 让 UNIQUE 冲突自动跳过, 而不是抛错
            update_sql = f"UPDATE OR IGNORE {table} SET client_id = ? WHERE client_id IN ({placeholders})"
            conn.execute(update_sql, [keep_id, *drop_ids])
            # 步骤 2: 上面 IGNORE 没成功更新的行 (因为 UNIQUE 冲突), 直接 DELETE
            # — 这些行的 client_id 还是旧 drop_id, 后面 DELETE clients 时会变孤儿
            cleanup_sql = f"DELETE FROM {table} WHERE client_id IN ({placeholders})"
            cur = conn.execute(cleanup_sql, drop_ids)
            dropped = cur.rowcount
            moved = cnt - dropped
            stats["rows_moved"] += moved
            stats["rows_dropped_conflict"] += dropped
        else:
            stats["rows_moved"] += cnt  # dry-run 假定全成功

    # 删 drop_ids 行
    for did in drop_ids:
        if apply:
            conn.execute("DELETE FROM clients WHERE id = ?", (did,))
        stats["clients_deleted"] += 1

    return stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path, help="云端 db 路径")
    parser.add_argument("--apply", action="store_true", help="真执行 DELETE+UPDATE (默认 dry-run)")
    args = parser.parse_args()

    if not args.db.exists():
        print(f"❌ db 不存在: {args.db}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(args.db)

    groups = find_duplicate_groups(conn)
    if not groups:
        print("✓ 没找到重复同名 client, 不需要清理.")
        return 0

    print(f"\n=== 找到 {len(groups)} 组重复同名 client ===\n")

    related_tables = find_related_tables(conn)
    print(f"会同步 update 的表 (含 client_id 字段): {len(related_tables)}")
    for t in related_tables:
        print(f"  · {t}")
    print()

    total_stats = {"tables_updated": 0, "rows_moved": 0, "rows_dropped_conflict": 0, "clients_deleted": 0}

    for g in groups:
        keep = g["details"][0]
        drops = g["details"][1:]
        print(f"--- {g['name']} (org={g['org_id']}) — 共 {g['n']} 条 ---")
        print(f"  保留: {keep['id']} (最早建于 {keep['created_at']})")
        for d in drops:
            print(f"  ⊗ 删除: {d['id']} (建于 {d['created_at']})")

        stats = merge_duplicate(
            conn, keep_id=keep["id"], drop_ids=[d["id"] for d in drops],
            related_tables=related_tables, apply=args.apply,
        )
        print(f"    → 涉及表数: {stats['tables_updated']}, 迁移行: {stats['rows_moved']}, 删 client: {stats['clients_deleted']}")
        for k, v in stats.items():
            total_stats[k] += v
        print()

    if args.apply:
        conn.commit()
        print(f"✅ 真改完毕. 涉及表 {total_stats['tables_updated']}, 迁 {total_stats['rows_moved']} 行, 删 {total_stats['clients_deleted']} client.")
    else:
        print(f"⊘ DRY-RUN 模式, 没真改. 加 --apply 真执行.")
        print(f"   预期: 涉及表 {total_stats['tables_updated']}, 迁 {total_stats['rows_moved']} 行, 删 {total_stats['clients_deleted']} client.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
