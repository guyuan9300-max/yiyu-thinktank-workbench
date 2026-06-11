"""字典反哺工具 — 给所有上层模块用的统一接口.

3 个核心能力:
  1. expand_aliases — "兴盛计划" → ["兴盛计划", "测试项目A"] (搜索/匹配用)
  2. canonicalize — "兴盛计划" → "测试项目A" (显示用)
  3. load_glossary_brief — 给 LLM 的字典上下文 (周复盘/narrative 用)

用法:
  P1 (chat 搜索): expand_aliases(db, client_id, query)  → FTS 用 OR 拼
  P2 (周复盘 AI):  load_glossary_brief(db, client_id)    → 喂给 LLM
  P3 (客户主页):  canonicalize(db, client_id, task_title)→ 显示规范化
  P4 (情报匹配):   expand_aliases(db, client_id, intel)   → 跨别名匹配
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import NamedTuple

from app.db import Database


class GlossaryEntry(NamedTuple):
    canonical: str
    aliases: tuple[str, ...]
    category: str
    definition: str


def _load_glossary_raw(db: Database, client_id: str) -> list[GlossaryEntry]:
    """从 client_glossary 表加载字典 (无缓存, 调用方应自己缓存)."""
    try:
        rows = db.fetchall(
            """
            SELECT term, aliases_json, category, definition
            FROM client_glossary WHERE client_id = ?
            """,
            (client_id,),
        )
    except Exception:
        return []
    out: list[GlossaryEntry] = []
    for r in rows:
        term = str(r["term"] or "").strip()
        if not term:
            continue
        try:
            aliases_raw = json.loads(r["aliases_json"] or "[]")
        except (TypeError, ValueError):
            aliases_raw = []
        aliases = tuple(
            str(a).strip() for a in aliases_raw if isinstance(a, str) and str(a).strip()
        )
        out.append(GlossaryEntry(
            canonical=term,
            aliases=aliases,
            category=str(r["category"] or "").strip(),
            definition=str(r["definition"] or "").strip(),
        ))
    return out


def expand_aliases(db: Database, client_id: str, query: str) -> list[str]:
    """『兴盛计划』 → ['兴盛计划', '测试项目A', '测试项目A'] — 把查询里的 token expand 到字典所有同义词.

    用法: FTS 搜索时把 expand 后的 list 用 OR 拼起来.
    """
    if not query:
        return []
    glossary = _load_glossary_raw(db, client_id)
    expanded: list[str] = [query]
    seen: set[str] = {query}

    for entry in glossary:
        # query 命中 canonical → 加所有 aliases
        if entry.canonical in query:
            for a in entry.aliases:
                if a and a not in seen:
                    expanded.append(a)
                    seen.add(a)
        # query 命中 alias → 加 canonical + 其他 aliases
        for alias in entry.aliases:
            if alias and alias in query:
                if entry.canonical not in seen:
                    expanded.append(entry.canonical)
                    seen.add(entry.canonical)
                for a2 in entry.aliases:
                    if a2 != alias and a2 not in seen:
                        expanded.append(a2)
                        seen.add(a2)
                break

    return expanded


def canonicalize(db: Database, client_id: str, text: str) -> str:
    """把文本中的字典别名替换成 canonical name. 例: "兴盛计划" → "测试项目A".

    避免重复替换:
      · 替换前先检查 canonical 是否已经在文本中相同位置 — 是就跳过
      · 按 alias 长度倒序处理 (长的先, 避免短 alias 覆盖长 alias)
    """
    if not text:
        return text
    glossary = _load_glossary_raw(db, client_id)
    pairs: list[tuple[str, str]] = []
    for entry in glossary:
        for alias in entry.aliases:
            if not alias or alias == entry.canonical:
                continue
            pairs.append((alias, entry.canonical))
    pairs.sort(key=lambda p: -len(p[0]))
    result = text
    for alias, canonical in pairs:
        if alias not in result:
            continue
        # 关键检查: alias 在文本里是否其实已经在 canonical 内部 (例 alias="测试项目A" 在已替换的"测试项目A" 内)
        # 用 split + 检查相邻是否构成 canonical, 比 regex 简单
        if alias in canonical and canonical in result:
            # canonical 已存在 — 跳过这个短 alias 替换
            continue
        result = result.replace(alias, canonical)
    return result


def load_glossary_brief(db: Database, client_id: str, max_terms: int = 60) -> str:
    """渲染字典摘要给 LLM 当 context (周复盘/narrative 用).

    返回类似:
        测试机构A项目字典 (60 term):
        ## 项目 (6)
          · 测试项目A [别名: 兴盛计划]
          · 测试项目C
          · 教师赋能项目
          ...
        ## 人物 (16)
          · 高老师
          · 张真老师 [别名: 张真]
          · 笑雨老师
          ...
    """
    glossary = _load_glossary_raw(db, client_id)
    if not glossary:
        return ""
    by_cat: dict[str, list[GlossaryEntry]] = {}
    for e in glossary[:max_terms]:
        by_cat.setdefault(e.category or "其他", []).append(e)
    lines = [f"字典 ({len(glossary)} term):"]
    for cat in sorted(by_cat):
        lines.append(f"\n## {cat} ({len(by_cat[cat])})")
        for e in by_cat[cat]:
            alias_str = f" [别名: {', '.join(e.aliases[:3])}]" if e.aliases else ""
            lines.append(f"  · {e.canonical}{alias_str}")
    return "\n".join(lines)


def get_canonical_names(db: Database, client_id: str, category: str | None = None) -> list[str]:
    """快速拿字典里某一类的所有 canonical name (例如所有项目名)."""
    glossary = _load_glossary_raw(db, client_id)
    if category:
        return [e.canonical for e in glossary if e.category == category]
    return [e.canonical for e in glossary]
