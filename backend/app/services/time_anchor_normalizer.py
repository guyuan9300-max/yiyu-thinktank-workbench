"""[A] V2.4 P0-3 · TimeAnchorNormalizer · 中文/ISO/口语日期互查

服务: docs/V2.4_MASTER_PLAN.md § 阶段 3

顾源源 5/23 核心场景:
> 系统内部记录的是 ISO 时间 (2026-05-03T00:00:00+00:00),
> 但用户会问 "5 月 3 日" "5 月 6 日" "5 月 18 日".
> 两种表达无法直接匹配, 时间线问题答不出来.
> 时间线是客户故事网的骨架, 时间层不稳, 故事网不成立.

每个时间事实 3 套字段:
  · time_anchor_iso     标准时间, 排序用
  · time_anchor_text    原文时间, 例如 "5 月 6 日"
  · time_aliases        可匹配数组, 例如 ["2026-05-06","5月6日","5/6","5月初"]

支持查询:
  · 中文日期查询  "5 月 6 日发生了什么?"
  · ISO 日期查询  "2026-05-06"
  · 相对时间    "上周" "上次会议" "5 月中旬"
  · 同一天多事件排序
  · 发生 vs 导入时间分开
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class _DbLike(Protocol):
    def execute(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchone(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchall(self, sql: str, params: tuple = ...) -> Any: ...


# ─── 中文日期 ↔ ISO 互转 ────────────────────────────


CN_DATE_PATTERNS = [
    # "5月6日" / "5 月 6 日"
    (re.compile(r"(\d{1,2})\s*月\s*(\d{1,2})\s*日"), "M_D"),
    # "2026年5月6日" / "2026 年 5 月 6 日"
    (re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"), "Y_M_D"),
    # "5/6" / "5/6/2026"
    (re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\b"), "SLASH"),
    # ISO "2026-05-06"
    (re.compile(r"(\d{4}-\d{2}-\d{2})"), "ISO"),
]


DEFAULT_YEAR = 2026  # 当前年份


def parse_to_iso_date(text: str, default_year: int = DEFAULT_YEAR) -> str | None:
    """把任意中文/ISO/slash 表达 → ISO date 'YYYY-MM-DD'.

    返回 None 表示解析失败.
    """
    if not text:
        return None
    text = text.strip()

    for pattern, kind in CN_DATE_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        try:
            if kind == "ISO":
                return m.group(1)
            elif kind == "Y_M_D":
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                return f"{y:04d}-{mo:02d}-{d:02d}"
            elif kind == "M_D":
                mo, d = int(m.group(1)), int(m.group(2))
                return f"{default_year:04d}-{mo:02d}-{d:02d}"
            elif kind == "SLASH":
                mo, d = int(m.group(1)), int(m.group(2))
                y = int(m.group(3)) if m.group(3) else default_year
                if 1 <= mo <= 12 and 1 <= d <= 31:
                    return f"{y:04d}-{mo:02d}-{d:02d}"
        except (ValueError, AttributeError):
            continue
    return None


def iso_to_cn_aliases(iso_date: str, year: int = DEFAULT_YEAR) -> list[str]:
    """ISO 日期 → 全部中文/常用表达 aliases.

    输入: "2026-05-06" 或 "2026-05-06T00:00:00+00:00"
    输出: ["2026-05-06", "5月6日", "5 月 6 日", "5/6", "2026年5月6日", "2026/5/6"]
    """
    if not iso_date:
        return []
    # 截到 YYYY-MM-DD
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", iso_date)
    if not m:
        return []
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return [
        f"{y:04d}-{mo:02d}-{d:02d}",                # ISO
        f"{mo}月{d}日",                              # 5月6日
        f"{mo} 月 {d} 日",                           # 5 月 6 日
        f"{mo}/{d}",                                 # 5/6
        f"{y:04d}/{mo}/{d}",                         # 2026/5/6
        f"{y:04d}年{mo}月{d}日",                      # 2026年5月6日
        f"{y:04d}-{mo}-{d}",                         # 2026-5-6 (非 0 padded)
    ]


# ─── 相对时间解析 ─────────────────────────────────────


def resolve_relative_time(
    text: str, *, now: date | None = None
) -> tuple[date, date] | None:
    """解析相对时间为日期区间 (start, end).

    支持: "上周" / "本周" / "下周" / "上个月" / "本月" / "下个月"
          "X 月初" / "X 月中旬" / "X 月底"
          "近 N 天" / "上 N 天" / "最近 N 天"

    返回 None 表示解析失败.
    """
    if not text:
        return None
    text = text.strip()
    n = now or datetime.now(timezone.utc).date()

    # 周区间
    if "本周" in text or "这周" in text:
        start = n - timedelta(days=n.weekday())
        return (start, start + timedelta(days=6))
    if "上周" in text or "上个星期" in text:
        end = n - timedelta(days=n.weekday() + 1)
        return (end - timedelta(days=6), end)
    if "下周" in text or "下个星期" in text:
        start = n + timedelta(days=7 - n.weekday())
        return (start, start + timedelta(days=6))

    # 月初/中/底
    m = re.search(r"(\d{1,2})\s*月\s*(初|中旬|底|末)", text)
    if m:
        mo = int(m.group(1))
        kind = m.group(2)
        y = n.year
        if kind == "初":
            return (date(y, mo, 1), date(y, mo, 10))
        elif kind == "中旬":
            return (date(y, mo, 11), date(y, mo, 20))
        elif kind in ("底", "末"):
            # 该月最后一天
            if mo == 12:
                next_first = date(y + 1, 1, 1)
            else:
                next_first = date(y, mo + 1, 1)
            last = next_first - timedelta(days=1)
            return (date(y, mo, 21), last)

    # 近 N 天
    m = re.search(r"(?:近|最近|上)\s*(\d+)\s*天", text)
    if m:
        days = int(m.group(1))
        return (n - timedelta(days=days), n)

    return None


# ─── 数据库 schema 增量 ──────────────────────────────


def ensure_time_alias_schema(db: _DbLike) -> None:
    """V2.4 加 atomic_facts.time_anchor_text + time_aliases_json + idx.

    幂等 (ALTER TABLE if not exists 模式).
    """
    for sql in [
        "ALTER TABLE atomic_facts ADD COLUMN time_anchor_text TEXT",
        "ALTER TABLE atomic_facts ADD COLUMN time_aliases_json TEXT DEFAULT '[]'",
    ]:
        try:
            db.execute(sql)
        except Exception:
            pass  # 列已存在
    try:
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_atomic_facts_time_aliases "
            "ON atomic_facts (time_anchor_text)"
        )
    except Exception:
        pass


def backfill_time_aliases(db: _DbLike, client_id: str | None = None) -> int:
    """已写入的 atomic_facts.time_anchor 反向生成 aliases 写入 time_aliases_json.

    Returns:
        更新条数
    """
    ensure_time_alias_schema(db)
    where = "time_anchor IS NOT NULL AND time_anchor != ''"
    params: tuple = ()
    if client_id:
        where += " AND client_id = ?"
        params = (client_id,)
    rows = db.fetchall(
        f"SELECT id, time_anchor FROM atomic_facts WHERE {where}", params,
    )
    import json
    updated = 0
    for r in rows:
        row = dict(r)
        aliases = iso_to_cn_aliases(row["time_anchor"])
        if not aliases:
            continue
        cn_text = aliases[1] if len(aliases) > 1 else aliases[0]
        try:
            db.execute(
                "UPDATE atomic_facts SET time_anchor_text = ?, "
                "time_aliases_json = ? WHERE id = ?",
                (cn_text, json.dumps(aliases, ensure_ascii=False), row["id"]),
            )
            updated += 1
        except Exception as exc:
            logger.warning("backfill time_aliases 失败 id=%s: %s", row["id"], exc)
    return updated


# ─── 查询入口 ────────────────────────────────────────


def find_facts_by_date_query(
    db: _DbLike, client_id: str, query: str,
) -> list[dict]:
    """用户问 "5 月 6 日发生了什么" → 解析 → 查 atomic_facts.

    流程:
      1. 试相对时间 → 日期区间
      2. 试中文/ISO 日期 → 单日
      3. 用 time_anchor (ISO) 范围查 atomic_facts
      4. 同时按 time_aliases_json 内容查 (兜底)
    """
    ensure_time_alias_schema(db)

    # 1 相对时间
    range_result = resolve_relative_time(query)
    if range_result:
        start, end = range_result
        rows = db.fetchall(
            """SELECT * FROM atomic_facts
               WHERE client_id = ? AND status = 'active'
                 AND time_anchor >= ? AND time_anchor < ?
               ORDER BY time_anchor""",
            (client_id, start.isoformat(), (end + timedelta(days=1)).isoformat()),
        )
        return [dict(r) for r in rows]

    # 2 单日
    iso_date = parse_to_iso_date(query)
    if iso_date:
        rows = db.fetchall(
            """SELECT * FROM atomic_facts
               WHERE client_id = ? AND status = 'active'
                 AND (time_anchor LIKE ? OR time_anchor_text = ?
                      OR time_aliases_json LIKE ?)
               ORDER BY time_anchor""",
            (client_id, f"{iso_date}%",
             # 中文表达兜底
             query.strip(), f"%{iso_date}%"),
        )
        return [dict(r) for r in rows]

    # 3 完全没匹配
    return []
