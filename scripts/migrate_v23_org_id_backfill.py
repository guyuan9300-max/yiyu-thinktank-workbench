#!/usr/bin/env python3
"""[B] 2026-05-27 V2.3 Step 0 · 历史数据 organization_id 反查迁移

背景:
  V2.3 团队共享需要每条文档/事实带上 organization_id / owner_user_id / department_id.
  但历史 3634 条记录 (documents 1976 + v2_documents 1048 + knowledge_documents 610)
  全是空, 让 data_center_sync 8 步过滤链直接卡死 (line 300/302/304 强校验).

  本脚本一次性反查 + 填充. 当前益语智库只有 1 个 organization, 全设它.
  owner_user_id 默认填 user_guyuan (顾源源, admin, 历史导入大概率是他).

策略:
  · organization_id  ← 'org_yiyu_default' (mirror_organizations 唯一一条)
  · owner_user_id    ← 'user_guyuan' (顾源源, 主导入人)
  · department_id    ← 'department_gq160gdz' (顾源源所属部门)
  · department_ids_json (v2_documents 用 array 字段)
                      ← '["department_gq160gdz"]'
  · 只 UPDATE 空字段, 已有值的保留 (idempotent)

使用:
  python3 scripts/migrate_v23_org_id_backfill.py --db <path> [--apply]
  默认 dry-run 报告会改多少行, --apply 真执行.
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path


DEFAULT_ORG_ID = "org_yiyu_default"
DEFAULT_OWNER_USER_ID = "user_guyuan"
DEFAULT_DEPARTMENT_ID = "department_gq160gdz"
DEFAULT_DEPARTMENT_IDS_JSON = json.dumps([DEFAULT_DEPARTMENT_ID])


def _table_has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(str(r[1]) == column for r in rows)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _check_anchor_data(conn: sqlite3.Connection) -> None:
    """安全门 — 确认默认 org/user/dept 真存在再迁移. 找不到就 abort."""
    org = conn.execute(
        "SELECT id FROM mirror_organizations WHERE id = ?", (DEFAULT_ORG_ID,)
    ).fetchone()
    if not org:
        raise RuntimeError(
            f"❌ mirror_organizations 里找不到 {DEFAULT_ORG_ID}, 迁移 abort. "
            "请先确认 organization 已 sync 自云端."
        )
    user = conn.execute(
        "SELECT id FROM mirror_users WHERE id = ?", (DEFAULT_OWNER_USER_ID,)
    ).fetchone() if _table_exists(conn, "mirror_users") else None
    # mirror_users 不存在也 OK, 老库可能用别的表. owner 用字符串不强校验.
    if user is None and _table_exists(conn, "mirror_users"):
        print(
            f"⚠️  mirror_users 里没找到 {DEFAULT_OWNER_USER_ID}, "
            "但继续 (owner_user_id 是软字段)"
        )


def _backfill_table(
    conn: sqlite3.Connection,
    table: str,
    *,
    apply: bool,
) -> dict:
    """对一张表执行字段填充. 返回统计."""
    if not _table_exists(conn, table):
        return {"table": table, "skipped": "table_missing", "updated": 0}

    has_org = _table_has_column(conn, table, "organization_id")
    has_owner = _table_has_column(conn, table, "owner_user_id")
    has_dept = _table_has_column(conn, table, "department_id")
    has_dept_json = _table_has_column(conn, table, "department_ids_json")

    if not (has_org or has_owner or has_dept or has_dept_json):
        return {"table": table, "skipped": "no_relevant_columns", "updated": 0}

    # 统计需要更新的行数 (按字段独立, 因为有些行 owner_user_id 已有但 org_id 空)
    stats = {"table": table, "total": 0}
    stats["total"] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    if has_org:
        empty_org = conn.execute(
            f"SELECT COUNT(*) FROM {table} "
            f"WHERE organization_id IS NULL OR organization_id = ''"
        ).fetchone()[0]
        stats["empty_org"] = empty_org
        if apply and empty_org > 0:
            conn.execute(
                f"UPDATE {table} SET organization_id = ? "
                f"WHERE organization_id IS NULL OR organization_id = ''",
                (DEFAULT_ORG_ID,),
            )
            stats["updated_org"] = empty_org

    if has_owner:
        empty_owner = conn.execute(
            f"SELECT COUNT(*) FROM {table} "
            f"WHERE owner_user_id IS NULL OR owner_user_id = ''"
        ).fetchone()[0]
        stats["empty_owner"] = empty_owner
        if apply and empty_owner > 0:
            conn.execute(
                f"UPDATE {table} SET owner_user_id = ? "
                f"WHERE owner_user_id IS NULL OR owner_user_id = ''",
                (DEFAULT_OWNER_USER_ID,),
            )
            stats["updated_owner"] = empty_owner

    if has_dept:
        empty_dept = conn.execute(
            f"SELECT COUNT(*) FROM {table} "
            f"WHERE department_id IS NULL OR department_id = ''"
        ).fetchone()[0]
        stats["empty_dept"] = empty_dept
        if apply and empty_dept > 0:
            conn.execute(
                f"UPDATE {table} SET department_id = ? "
                f"WHERE department_id IS NULL OR department_id = ''",
                (DEFAULT_DEPARTMENT_ID,),
            )
            stats["updated_dept"] = empty_dept

    if has_dept_json:
        empty_dept_json = conn.execute(
            f"SELECT COUNT(*) FROM {table} "
            f"WHERE department_ids_json IS NULL OR department_ids_json IN ('', '[]')"
        ).fetchone()[0]
        stats["empty_dept_json"] = empty_dept_json
        if apply and empty_dept_json > 0:
            conn.execute(
                f"UPDATE {table} SET department_ids_json = ? "
                f"WHERE department_ids_json IS NULL OR department_ids_json IN ('', '[]')",
                (DEFAULT_DEPARTMENT_IDS_JSON,),
            )
            stats["updated_dept_json"] = empty_dept_json

    return stats


# 全部参与团队共享 sync 的表 (排除规则 line 300-307 真用到的字段所在表)
TARGET_TABLES = [
    "documents",
    "v2_documents",
    "knowledge_documents",
    # data_center_ingest_events: 也有 org_id/owner 字段, 但内容是真事件不是历史数据,
    # 默认不迁移 (新事件入库时会自动填). 如要补就加进来.
    # "data_center_ingest_events",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--db",
        required=True,
        type=Path,
        help="本地 sqlite db 路径 (~/Library/Application Support/YiyuThinkTankWorkbench2*/app.db)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="真执行 UPDATE (默认 dry-run)",
    )
    args = parser.parse_args()

    if not args.db.exists():
        print(f"❌ db 不存在: {args.db}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(args.db)
    try:
        _check_anchor_data(conn)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    print(f"目标 db: {args.db}")
    print(f"默认值:")
    print(f"  · organization_id    = {DEFAULT_ORG_ID}")
    print(f"  · owner_user_id      = {DEFAULT_OWNER_USER_ID}")
    print(f"  · department_id      = {DEFAULT_DEPARTMENT_ID}")
    print(f"  · department_ids_json= {DEFAULT_DEPARTMENT_IDS_JSON}")
    print(f"模式: {'APPLY (真改 db)' if args.apply else 'DRY-RUN (只统计)'}")
    print()
    print("=" * 72)

    all_stats = []
    for table in TARGET_TABLES:
        stats = _backfill_table(conn, table, apply=args.apply)
        all_stats.append(stats)
        if stats.get("skipped"):
            print(f"⊘ {table:25s} 跳过: {stats['skipped']}")
            continue
        total = stats.get("total", 0)
        print(f"\n表 {table} (总行数 {total}):")
        for k in ("empty_org", "empty_owner", "empty_dept", "empty_dept_json"):
            v = stats.get(k)
            if v is not None and v > 0:
                done = stats.get(k.replace("empty_", "updated_"), 0)
                marker = "✓" if args.apply and done > 0 else " "
                print(f"  {marker} {k:20s} {v:6d} 行需要填充" + (f" → 已更新 {done}" if args.apply else ""))

    print()
    print("=" * 72)
    if args.apply:
        conn.commit()
        print("✅ 真改完毕. 已 commit.")
    else:
        print("⊘ DRY-RUN 没真改. 加 --apply 真执行.")
        print()
        print("建议: 先 cp 备份 db, 然后跑 --apply")
        print("  cp ~/Library/Application\\ Support/YiyuThinkTankWorkbench2_V21Lab/app.db /tmp/app.db.bak-v23-step0")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
