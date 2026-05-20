"""项目画像构建器 — 从现有数据回填 3 张新表 (glossary_relations / risk_signals / commitments).

设计原则:
  · 一次性 LLM 调用 (输入: 现有字典 + atomic_facts + tasks + event_lines, 输出: 3 类结构化数据)
  · 不重新抽 atomic_facts (那是 ingest 的工作), 只在已有事实上推关联
  · tasks.glossary_term_ids 用 regex 匹配 (不调 LLM, 字典 canonical/alias 出现在 task title 就挂)
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from app.db import Database
from app.services.ai import AiInvocationError, AiService


# ============================================================
# 1. tasks.glossary_term_ids 回填 (regex 匹配, 不调 LLM)
# ============================================================


def backfill_task_glossary_links(db: Database, client_id: str) -> dict[str, int]:
    """扫现有 tasks, 把 title/description 含字典 canonical/alias 的 task 自动挂载 term."""
    glossary_rows = db.fetchall(
        "SELECT id, term, aliases_json, category FROM client_glossary WHERE client_id = ?",
        (client_id,),
    )
    # 构造 (匹配 phrase, term_id, category) 列表; 按 phrase 长度倒序避免短覆盖长
    phrases: list[tuple[str, str, str]] = []
    for r in glossary_rows:
        term_id = str(r["id"])
        canonical = str(r["term"] or "").strip()
        category = str(r["category"] or "")
        try:
            aliases = json.loads(r["aliases_json"] or "[]")
        except Exception:
            aliases = []
        phrases.append((canonical, term_id, category))
        for a in aliases:
            if isinstance(a, str) and a.strip():
                phrases.append((a.strip(), term_id, category))
    phrases.sort(key=lambda x: -len(x[0]))

    task_rows = db.fetchall(
        "SELECT id, title, COALESCE(description, '') AS description FROM tasks WHERE client_id = ?",
        (client_id,),
    )
    task_count = 0
    total_links = 0
    for r in task_rows:
        task_id = str(r["id"])
        text = (r["title"] or "") + " " + (r["description"] or "")
        matched_term_ids: list[str] = []
        for phrase, term_id, cat in phrases:
            # 时间类 (关键节点/数字) 用精确匹配; 其它用 substring
            if cat == "关键节点/数字":
                if phrase in text:
                    if term_id not in matched_term_ids:
                        matched_term_ids.append(term_id)
            else:
                if phrase in text:
                    if term_id not in matched_term_ids:
                        matched_term_ids.append(term_id)
        if matched_term_ids:
            db.execute(
                "UPDATE tasks SET glossary_term_ids = ? WHERE id = ?",
                (json.dumps(matched_term_ids, ensure_ascii=False), task_id),
            )
            task_count += 1
            total_links += len(matched_term_ids)
    return {"task_with_links": task_count, "total_links": total_links}


# ============================================================
# 2. LLM 一次性抽: 关联 / 风险 / 承诺
# ============================================================


PORTRAIT_OUTPUT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "relations": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "subject_term": {"type": "STRING"},
                    "predicate": {"type": "STRING"},
                    "object_term": {"type": "STRING"},
                    "confidence": {"type": "STRING", "enum": ["high", "medium", "low"]},
                    "evidence": {"type": "STRING"},
                },
            },
        },
        "risk_signals": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "signal_kind": {"type": "STRING", "enum": ["business_env", "relationship", "delivery", "other"]},
                    "title": {"type": "STRING"},
                    "description": {"type": "STRING"},
                    "severity": {"type": "STRING", "enum": ["low", "medium", "high", "critical"]},
                    "related_terms": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
            },
        },
        "commitments": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "committer": {"type": "STRING"},
                    "recipient": {"type": "STRING"},
                    "commitment_type": {"type": "STRING", "enum": ["delivery", "payment", "configuration", "meeting", "other"]},
                    "content": {"type": "STRING"},
                    "deadline": {"type": "STRING"},
                    "status": {"type": "STRING", "enum": ["pending", "fulfilled", "overdue", "cancelled"]},
                    "related_terms": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "source_type": {"type": "STRING"},
                },
            },
        },
    },
    "required": ["relations", "risk_signals", "commitments"],
}


SYSTEM_PROMPT = """你是企业知识图谱工程师, 任务: 给某客户的『项目画像』补三类结构化数据。

== 1. relations (字典 term 之间的关联关系) ==

字典里已有 N 个 term (项目/人物/机构/业务术语/规则). 但 term 之间的"边"还没建。
你的工作: 推断**哪些 term 之间有业务关系**, 例如:
  · 笑雨老师 → 负责 → 教师赋能项目
  · 心盛计划 → 包含 → 朋辈关怀员培训
  · 张真老师 → 对接 → 战略陪伴 (与益语的对接人)
  · 2026-05-16 → 是关键节点 → 心盛计划 (deadline 关联)

predicate 用中文动词 (负责/包含/对接/属于/服务/承诺/影响/涉及/...)。
只推**facts 里有据的关联**, 不推主观猜测。

== 2. risk_signals (风险信号) ==

风险 3 类:
  · business_env — 业务环境 (政策变化/竞品/市场)
  · relationship — 关系 (客户冷却/沟通中断/关键人变动)
  · delivery — 交付 (节点逾期风险/资源过载/质量风险)

例: "南沙公益创投出现青少年心理健康服务平台搭建方向" → business_env (severity=medium, related: 心盛计划/教师赋能)

== 3. commitments (承诺) ==

把 facts 里出现的**真实承诺**结构化:
  · committer (谁): 益语 / 客户机构名 / 具体人名
  · recipient (向谁): 同上
  · commitment_type: delivery/payment/configuration/meeting
  · content: 承诺内容
  · deadline: ISO 日期 (有就填)
  · status: pending (未到期) / fulfilled (已完成) / overdue (逾期) / cancelled

例:
  · 益语 → 客户 → delivery → "完成核心项目梳理诊断" → 2026-05-16 → pending
  · 张真 → 益语 → configuration → "提交项目相关资料" → 已 fulfilled

**严格只从 facts 抽**, 不臆测。
"""


def _build_portrait_prompt(
    glossary: list[dict[str, Any]],
    atomic_facts: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    event_lines: list[dict[str, Any]],
    client_name: str,
    *,
    glossary_pack: str = "",
) -> str:
    lines: list[str] = []
    if glossary_pack:
        lines.append(glossary_pack)
        lines.append("\n---\n")
    lines.append(f"# 客户: {client_name}\n")

    lines.append(f"\n## 字典 ({len(glossary)} term):")
    for g in glossary:
        aliases = g.get("aliases", [])
        alias_str = f" [别名: {', '.join(aliases[:3])}]" if aliases else ""
        lines.append(f"  · [{g['category']}] {g['term']}{alias_str}")

    lines.append(f"\n## atomic_facts ({len(atomic_facts)} 条, 高置信度):")
    for f in atomic_facts[:80]:
        lines.append(f"  · {f['subject'][:30]} | {f['attribute']} | {f['value'][:60]}")

    lines.append(f"\n## tasks ({len(tasks)} 条):")
    for t in tasks[:30]:
        ddl = f" ddl={t['deadline']}" if t.get("deadline") else ""
        lines.append(f"  · {t['title'][:50]} | owner={t['owner']}{ddl} | status={t['status']}")

    lines.append(f"\n## event_lines ({len(event_lines)} 条):")
    for el in event_lines:
        lines.append(f"  · {el['name']}: intent={el['intent'][:120]}")

    lines.append("\n请抽 relations / risk_signals / commitments, 标 related_terms 用字典 term canonical name (不是 id).")
    return "\n".join(lines)


def _collect_inputs(db: Database, client_id: str) -> dict[str, Any]:
    client_row = db.fetchone("SELECT name FROM clients WHERE id = ?", (client_id,))
    client_name = str(client_row["name"]) if client_row else client_id

    glossary_rows = db.fetchall(
        "SELECT id, term, aliases_json, category FROM client_glossary WHERE client_id = ?",
        (client_id,),
    )
    glossary = []
    term_name_to_id: dict[str, str] = {}
    for r in glossary_rows:
        try:
            aliases = json.loads(r["aliases_json"] or "[]")
        except Exception:
            aliases = []
        canonical = str(r["term"])
        term_name_to_id[canonical] = str(r["id"])
        for a in aliases:
            if isinstance(a, str):
                term_name_to_id[a] = str(r["id"])
        glossary.append({
            "id": str(r["id"]),
            "term": canonical,
            "aliases": aliases,
            "category": str(r["category"] or ""),
        })

    atomic_rows = db.fetchall(
        """
        SELECT id, subject_text AS subject, attribute, value_text AS value, confidence
        FROM atomic_facts WHERE client_id=? AND status='active' AND confidence>=0.65
        ORDER BY confidence DESC LIMIT 100
        """,
        (client_id,),
    )
    atomic_facts = [dict(r) for r in atomic_rows]

    task_rows = db.fetchall(
        """
        SELECT id, title, owner_name AS owner, substr(deadline_at, 1, 10) AS deadline, progress_status AS status
        FROM tasks WHERE client_id=? ORDER BY updated_at DESC LIMIT 50
        """,
        (client_id,),
    )
    tasks = [dict(r) for r in task_rows]

    el_rows = db.fetchall(
        """
        SELECT name, COALESCE(intent,'') AS intent, COALESCE(next_step,'') AS next_step
        FROM event_lines WHERE primary_client_id=?
        """,
        (client_id,),
    )
    event_lines = [dict(r) for r in el_rows]

    return {
        "client_name": client_name,
        "glossary": glossary,
        "term_name_to_id": term_name_to_id,
        "atomic_facts": atomic_facts,
        "tasks": tasks,
        "event_lines": event_lines,
    }


def build_portrait(db: Database, ai: AiService, client_id: str) -> dict[str, Any]:
    inputs = _collect_inputs(db, client_id)
    health = ai.get_health()
    if not health.ready:
        return {"status": "ai_not_ready", "error": health.detail}

    # P-E.6: 注入字典权威包，让 portrait 的关键数字基于 verified 事实
    glossary_pack = ""
    try:
        from app.services.glossary_attributes_pack import build_verified_attributes_pack
        glossary_pack = build_verified_attributes_pack(db, client_id) or ""
    except Exception:
        glossary_pack = ""

    prompt = _build_portrait_prompt(
        inputs["glossary"], inputs["atomic_facts"],
        inputs["tasks"], inputs["event_lines"],
        inputs["client_name"],
        glossary_pack=glossary_pack,
    )

    try:
        result = ai._qwen_generate(  # noqa: SLF001
            prompt, SYSTEM_PROMPT, PORTRAIT_OUTPUT_SCHEMA,
            timeout_seconds=360.0, max_tokens=8000, temperature=0.2,
        )
    except AiInvocationError as exc:
        return {"status": "llm_failed", "error": f"{type(exc).__name__}: {getattr(exc, 'detail', str(exc))[:300]}"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "exception", "error": f"{type(exc).__name__}: {str(exc)[:300]}"}

    if not isinstance(result, dict):
        return {"status": "bad_output", "error": "LLM returned non-dict"}

    term_name_to_id = inputs["term_name_to_id"]
    relations = result.get("relations") or []
    risks = result.get("risk_signals") or []
    commits = result.get("commitments") or []

    # 写入 3 张表
    now = datetime.now(timezone.utc).isoformat()
    # 清空旧 (该 client) — 回填覆盖
    # 关键: 只删 source_type='ai_inferred' 的, 保护 smart_import_story 等用户来源的数据
    db.execute("DELETE FROM glossary_relations WHERE client_id=? AND source='ai_inferred'", (client_id,))
    db.execute("DELETE FROM risk_signals WHERE client_id=? AND source_type='ai_inferred'", (client_id,))
    db.execute("DELETE FROM commitments WHERE client_id=? AND source_type='ai_inferred'", (client_id,))

    n_rel = 0
    for r in relations:
        if not isinstance(r, dict):
            continue
        subj = term_name_to_id.get(str(r.get("subject_term") or "").strip())
        obj = term_name_to_id.get(str(r.get("object_term") or "").strip())
        predicate = str(r.get("predicate") or "").strip()
        if not subj or not predicate:
            continue
        db.execute(
            """INSERT INTO glossary_relations
               (id, client_id, subject_term_id, predicate, object_term_id,
                source, confidence, status, note, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (str(uuid.uuid4()), client_id, subj, predicate, obj,
             "ai_inferred",
             _conf_to_float(r.get("confidence")),
             "pending", str(r.get("evidence", ""))[:200],
             now, now),
        )
        n_rel += 1

    n_risk = 0
    for s in risks:
        if not isinstance(s, dict):
            continue
        title = str(s.get("title") or "").strip()
        if not title:
            continue
        related_term_ids = []
        for term_name in (s.get("related_terms") or []):
            tid = term_name_to_id.get(str(term_name).strip())
            if tid and tid not in related_term_ids:
                related_term_ids.append(tid)
        db.execute(
            """INSERT INTO risk_signals
               (id, client_id, signal_kind, title, description, severity,
                related_term_ids_json, source_type, source_id, captured_at, status, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (str(uuid.uuid4()), client_id,
             str(s.get("signal_kind", "other") or "other"),
             title, str(s.get("description", ""))[:500],
             str(s.get("severity", "medium")),
             json.dumps(related_term_ids, ensure_ascii=False),
             "ai_inferred", "", now, "active", now, now),
        )
        n_risk += 1

    n_commit = 0
    for c in commits:
        if not isinstance(c, dict):
            continue
        content = str(c.get("content") or "").strip()
        if not content:
            continue
        related_term_ids = []
        for term_name in (c.get("related_terms") or []):
            tid = term_name_to_id.get(str(term_name).strip())
            if tid and tid not in related_term_ids:
                related_term_ids.append(tid)
        db.execute(
            """INSERT INTO commitments
               (id, client_id, committer, recipient, commitment_type, content, deadline,
                status, related_term_ids_json, source_type, source_id, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (str(uuid.uuid4()), client_id,
             str(c.get("committer", ""))[:50], str(c.get("recipient", ""))[:50],
             str(c.get("commitment_type", "delivery")),
             content[:500],
             str(c.get("deadline", "")) or None,
             str(c.get("status", "pending")),
             json.dumps(related_term_ids, ensure_ascii=False),
             "ai_inferred", "", now, now),
        )
        n_commit += 1

    return {
        "status": "ok",
        "relations": n_rel,
        "risk_signals": n_risk,
        "commitments": n_commit,
        "raw_counts": {
            "relations_raw": len(relations),
            "risks_raw": len(risks),
            "commits_raw": len(commits),
        },
    }


def _conf_to_float(value: object) -> float:
    s = str(value or "").lower()
    return {"high": 0.85, "medium": 0.6, "low": 0.35}.get(s, 0.5)
