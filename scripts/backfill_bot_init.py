#!/usr/bin/env python3
"""M8 (A, 2026-05-25) · 给所有旧 bot 补 reporting_lines + permission_policies.

背景: 顾源源 5/24 创建庆华后, B 在 46-B §3.1 用 SQL 手工兜底了 reporting_lines
+ permission_policies (老代码 create_bot_member 漏建). M8 修了 create 函数, 但旧
bot 不会自动补 — 这个脚本一次性补齐.

idempotent:
  · 已有 reporting_lines 的 bot 跳过 (不覆盖用户已配置)
  · capability 维度 idempotent: 缺哪个补哪个

用法:
  python3 scripts/backfill_bot_init.py             # 扫所有
  python3 scripts/backfill_bot_init.py --bot-id X  # 只补一个
  python3 scripts/backfill_bot_init.py --dry-run   # 干跑不写
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# 让脚本能 import backend.app
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT / "backend"))

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("backfill_bot_init")


def _resolve_db_path() -> Path:
    """V2.1 lab 真 db 路径 (顾源源真用的)."""
    return Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2_V21Lab/app.db"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bot-id", default=None, help="只补这一个 bot_member_id")
    parser.add_argument("--dry-run", action="store_true", help="干跑, 不写 db")
    parser.add_argument("--db", default=None, help="覆盖默认 db 路径")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else _resolve_db_path()
    if not db_path.exists():
        log.error("db not found: %s", db_path)
        return 2
    log.info("db: %s", db_path)

    from app.db import Database  # type: ignore  # noqa: E402

    db = Database(db_path)

    from app.services.bot_members import (  # noqa: E402
        backfill_bot_init, list_bot_members,
    )

    if args.dry_run:
        # 干跑: 列出每个 bot 缺什么, 不写
        bots = list_bot_members(db)
        for b in bots:
            bid = b["id"]
            name = b.get("display_name")
            has_rep = bool(b.get("reporting"))
            existing_caps = {c["capability_key"] for c in (b.get("capabilities") or [])}
            from app.services.bot_members import CAPABILITY_KEYS  # noqa: E402
            missing_caps = [c for c in CAPABILITY_KEYS if c not in existing_caps]
            log.info("[dry] %s (%s): reporting=%s, missing_caps=%s",
                     name, bid, "ok" if has_rep else "MISSING", missing_caps)
        return 0

    result = backfill_bot_init(db, bot_member_id=args.bot_id)
    log.info("done: scanned=%d, reporting_added=%d, permissions_added=%d",
             result["scanned"], result["reporting_added"], result["permissions_added"])
    for b in result["bots"]:
        if b["reporting_added"] or b["capabilities_added"]:
            log.info("  · %s (%s): +rep=%d, +caps=%d",
                     b.get("display_name"), b["bot_member_id"],
                     b["reporting_added"], b["capabilities_added"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
