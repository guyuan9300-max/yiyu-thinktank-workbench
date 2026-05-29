"""[B] init_v21_lab_schema.py · headless V2.1 lab db schema 初始化

管理员甲 5/23 sync 第 3 件:
> "新建 scripts/init_v21_lab_schema.py
>  headless 跑一次, 把 11 张关键表 ensure 进 V2.1 lab db
>  (不依赖 Electron 启动)
>  否则以后每次测试都可能被 Electron 没启动、表没 ensure 卡住."

设计:
  · 直接复用 backend service 现成的 ensure_xxx_schema 函数
  · 不重复写 SQL → A 改 schema 自动同步, B 不维护
  · sqlite3.Connection 直接传 (ensure 函数只调 db.execute, 兼容)
  · WAL 模式 + 5s busy_timeout → 不影响正在跑的 V2.1 backend (port 47831)

用法:
  npm run db:init:lab           # package.json 集成
  python scripts/init_v21_lab_schema.py    # 直跑
  python scripts/init_v21_lab_schema.py --db /custom/path/app.db

11 张关键表 (来自 docs/B_AI_SYNC_TO_A_R2_BLOCKER_FIRST_20260523.md):
  V2.3 phase 0/1 (V2.1 lab db 已有, skip):
    atomic_facts / event_line_activities / risk_signals / commitments
    clarification_records / strategic_thought_insights
  V2.3 phase 1 (需建):
    source_registry
  V2.4 P1 (需建):
    atomic_fact_confidence_history
  V2.5 R2-A (需建):
    approval_queue / agent_run_log / idempotency_keys_v25

Author: AI B · 2026-05-23
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"

if not BACKEND_DIR.exists():
    print(f"FATAL: backend dir not found: {BACKEND_DIR}", file=sys.stderr)
    sys.exit(2)

sys.path.insert(0, str(BACKEND_DIR))

DEFAULT_V21_LAB_DB = (
    Path.home()
    / "Library"
    / "Application Support"
    / "YiyuThinkTankWorkbench2_V21Lab"
    / "app.db"
)

CRITICAL_TABLES: tuple[str, ...] = (
    "atomic_facts",
    "atomic_fact_confidence_history",
    "approval_queue",
    "agent_run_log",
    "idempotency_keys_v25",
    "source_registry",
    "event_line_activities",
    "risk_signals",
    "commitments",
    "clarification_records",
    "strategic_thought_insights",
    # V2.6 R3 表 (A 18:35 R4 联动评估发现 V2.1 lab db 缺):
    "file_identities",
    "contract_structures",
    "historical_reference_links",
    "data_gaps",
    "external_evidence_cards",
)

logger = logging.getLogger("init_v21_lab_schema")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="V2.1 lab db headless schema init")
    p.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_V21_LAB_DB,
        help=f"V2.1 lab db path (default: {DEFAULT_V21_LAB_DB})",
    )
    p.add_argument(
        "--check-only",
        action="store_true",
        help="只看哪些表缺, 不真建",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="详细日志",
    )
    return p.parse_args()


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def list_existing_tables(con: sqlite3.Connection) -> set[str]:
    rows = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r[0] for r in rows}


def report_missing(
    existing: set[str], label: str
) -> tuple[list[str], list[str]]:
    have: list[str] = []
    miss: list[str] = []
    for t in CRITICAL_TABLES:
        if t in existing:
            have.append(t)
        else:
            miss.append(t)
    print(f"\n📊 {label}: {len(have)}/{len(CRITICAL_TABLES)} 表存在")
    for t in have:
        print(f"   ✅ {t}")
    for t in miss:
        print(f"   ❌ {t}")
    return have, miss


def run_ensures(con: sqlite3.Connection) -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []

    try:
        from app.services.agent_governance import ensure_governance_schema
        print("\n🔧 ensure_governance_schema (agent_run_log + approval_queue + idempotency_keys_v25)")
        ensure_governance_schema(con)
        results.append(("agent_governance", True, "ok"))
    except Exception as exc:
        logger.exception("ensure_governance_schema failed")
        results.append(("agent_governance", False, repr(exc)))

    try:
        from app.services.atomic_fact_confidence_history import ensure_schema as ensure_fact_conf_history
        print("🔧 atomic_fact_confidence_history.ensure_schema")
        ensure_fact_conf_history(con)
        results.append(("atomic_fact_confidence_history", True, "ok"))
    except Exception as exc:
        logger.exception("atomic_fact_confidence_history.ensure_schema failed")
        results.append(("atomic_fact_confidence_history", False, repr(exc)))

    try:
        from app.services.source_registry_store import ensure_schema as ensure_source_registry
        print("🔧 source_registry_store.ensure_schema")
        ensure_source_registry(con)
        results.append(("source_registry", True, "ok"))
    except Exception as exc:
        logger.exception("source_registry_store.ensure_schema failed")
        results.append(("source_registry", False, repr(exc)))

    # V2.6 R3 表 (A 18:35 R4 联动评估发现缺):
    try:
        from app.services.file_identity_classifier import ensure_file_identity_schema
        print("🔧 file_identity_classifier.ensure_file_identity_schema (file_identities + contract_structures)")
        ensure_file_identity_schema(con)
        results.append(("file_identity + contract_structure", True, "ok"))
    except Exception as exc:
        logger.exception("ensure_file_identity_schema failed")
        results.append(("file_identity + contract_structure", False, repr(exc)))

    try:
        from app.services.historical_material_resolver import ensure_resolver_schema
        print("🔧 historical_material_resolver.ensure_resolver_schema (historical_reference_links)")
        ensure_resolver_schema(con)
        results.append(("historical_reference_links", True, "ok"))
    except Exception as exc:
        logger.exception("ensure_resolver_schema failed")
        results.append(("historical_reference_links", False, repr(exc)))

    try:
        from app.services.data_gap_compensator import ensure_external_evidence_schema
        print("🔧 data_gap_compensator.ensure_external_evidence_schema (data_gaps + external_evidence_cards)")
        ensure_external_evidence_schema(con)
        results.append(("data_gaps + external_evidence_cards", True, "ok"))
    except Exception as exc:
        logger.exception("ensure_external_evidence_schema failed")
        results.append(("data_gaps + external_evidence_cards", False, repr(exc)))

    con.commit()
    return results


def main() -> int:
    args = parse_args()
    setup_logging(args.verbose)

    db_path: Path = args.db
    if not db_path.exists():
        print(f"❌ V2.1 lab db 不存在: {db_path}")
        print("   先启动 V2.1 Electron 一次 (npm run dev:lab) 让初始 db 文件创建")
        return 2

    print(f"📂 V2.1 lab db: {db_path}")
    size_mb = db_path.stat().st_size / 1024 / 1024
    print(f"   大小: {size_mb:.1f} MB")

    # WAL + busy_timeout, 兼容 V2.1 backend 已 open 的连接
    con = sqlite3.connect(db_path, timeout=10.0)
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA busy_timeout=5000")
        con.execute("PRAGMA foreign_keys=ON")

        existing_before = list_existing_tables(con)
        _, missing_before = report_missing(existing_before, "跑前")

        if args.check_only:
            print("\n--check-only 模式, 不真建. 退出.")
            return 0 if not missing_before else 1

        if not missing_before:
            print("\n✅ 所有 11 张表已存在, skip ensure.")
            return 0

        ensure_results = run_ensures(con)
        print("\n📋 ensure 结果:")
        for name, ok, msg in ensure_results:
            mark = "✅" if ok else "❌"
            print(f"   {mark} {name}: {msg}")

        existing_after = list_existing_tables(con)
        _, missing_after = report_missing(existing_after, "跑后")

        if not missing_after:
            print(f"\n✅ V2.1 lab db schema 初始化完成 — {len(CRITICAL_TABLES)} 张关键表全建.")
            print("   下一步: B 跑 python scripts/run_v25_r2_meeting_minute.py")
            return 0
        else:
            print(f"\n⚠️ 仍缺 {len(missing_after)} 张表: {missing_after}")
            print("   说明: 这几张表的 ensure 函数 V2.1 backend 还没写,")
            print("   需要 A 在 backend 补 ensure 或本脚本加 SQL fallback.")
            return 1
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())
