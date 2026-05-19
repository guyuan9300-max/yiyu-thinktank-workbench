"""品牌印象速读 / Brand Audit Report（P6）。

定位：把 themes + gap + brand_proposition + 代表性原话喂给 LLM，
让它扮演资深公关分析师，输出客户能直接拿去开会的简报。

输出层次（避免再次回到"原始素材堆"陷阱）：
  - headline：一句话定位（"公众语境中，X 是 Y 而非 Z"）
  - narrative_md：3 段品牌印象（核心 / 二级 / 缺失）
  - tensions：2-3 条「你说 X，公众看到 Y」张力
  - recommendations：3-5 条可执行建议（动词+具体对象）
  - content_angles：下次发声该强化/弱化/新增哪些

护栏：
  - response_schema 强约束，关键字段非空
  - prompt 明确要求引用具体主题 label，禁止套话
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db import Database, from_json, to_json
from app.services.intelligence_theme_cluster import list_themes
from app.services.intelligence_positioning_gap import (
    compute_gap,
    _parse_propositions,
    infer_brand_proposition_from_data_center,
)

logger = logging.getLogger(__name__)


AUDIT_TTL_HOURS = 24
MAX_EVIDENCE_QUOTES = 12       # 喂给 LLM 的代表性原话上限
MIN_THEMES_FOR_AUDIT = 2       # 至少 2 个主题才生成简报


# ──────────────────────────────────────────────────────────────────────────
# LLM Prompt — 公关分析师角色
# ──────────────────────────────────────────────────────────────────────────

AUDIT_SYSTEM_INSTRUCTION = (
    "你是资深品牌 / 公关分析师，给客户写一份品牌印象速读。"
    "客户会拿这份简报开品牌会，所以你必须做到以下三件事，否则就是失败的简报：\n"
    "\n"
    "1. 【避免套话】"
    "禁止使用『反响良好』『口碑较好』『有一定知名度』『需要进一步加强宣传』之类的空泛表述。"
    "每个判断都必须引用具体主题 label（来自 themes 数组）或具体数字（多少条 / 占比多少）。\n"
    "\n"
    "2. 【写出张力】"
    "tensions 必须以『你说 X，但公众看到 Y』的格式写，至少给出 2 条；"
    "每条必须分别引用一个 self_proposition（来自 brand_proposition）和一个 public_theme（来自 themes）。"
    "如果两者真的高度对齐没有张力，也要写出『最大的空白是什么』（公众没说的部分）。\n"
    "\n"
    "3. 【建议必须可执行】"
    "recommendations 每条必须含『动作动词 + 具体对象』，比如：\n"
    "  - 好：『发一次资金透明度年报，用结构化数据填补「透明」语义空白』\n"
    "  - 差：『提升透明度』『加强专业品牌』『多做内容』\n"
    "\n"
    "content_angles 给两组词：\n"
    "  - amplify：下次发声应强化的主题（来自现有 positive 主题或缺失的自我定位）\n"
    "  - new：完全没人讨论但你想被定义的方向\n"
    "**禁止**生成 reduce 类建议——"
    "「让客户少说什么」是一个高风险判断，需要上下文才能决定，"
    "AI 在缺乏完整组织上下文时容易踩雷，统一不出。\n"
    "\n"
    "只返回 JSON，严禁 Markdown 围栏，严禁解释。"
)


AUDIT_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["headline", "narrative_md", "tensions", "recommendations", "content_angles"],
    "properties": {
        "headline": {
            "type": "string",
            "minLength": 10,
            "maxLength": 120,
        },
        "narrative_md": {
            "type": "string",
            "minLength": 80,
            "maxLength": 1200,
        },
        "tensions": {
            "type": "array",
            "minItems": 1,
            "maxItems": 4,
            "items": {
                "type": "object",
                "required": ["statement", "self_anchor", "public_anchor"],
                "properties": {
                    "statement": {"type": "string", "maxLength": 200},
                    "self_anchor": {"type": "string"},
                    "public_anchor": {"type": "string"},
                },
            },
        },
        "recommendations": {
            "type": "array",
            "minItems": 2,
            "maxItems": 5,
            "items": {
                "type": "object",
                "required": ["action", "rationale"],
                "properties": {
                    "action": {"type": "string", "maxLength": 100},
                    "rationale": {"type": "string", "maxLength": 200},
                    "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                },
            },
        },
        "content_angles": {
            "type": "object",
            "required": ["amplify", "new"],
            "properties": {
                "amplify": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                "new": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
            },
        },
    },
}


def _build_audit_prompt(
    target_name: str,
    propositions: list[str],
    themes: list[dict[str, Any]],
    gap_alignments: list[dict[str, Any]],
    gap_unexpected: list[dict[str, Any]],
    evidence_quotes: list[dict[str, Any]],
) -> str:
    """组装喂给 LLM 的简报输入。"""
    lines: list[str] = []
    lines.append(f"target_name: {target_name}")
    lines.append("")

    lines.append("self_propositions（客户自己说的品牌定位）:")
    if propositions:
        for p in propositions:
            lines.append(f"  - {p}")
    else:
        lines.append("  （客户尚未填写自我定位，所有张力和建议要明确指出『缺乏自我定位』）")
    lines.append("")

    lines.append("public_themes（已聚出的公众印象主题）:")
    for t in themes:
        lines.append(
            f"  - 「{t['themeLabel']}」({t['sentimentTone']}/{t['itemCount']}条) — {t['themeSummary']}"
        )
    lines.append("")

    if gap_alignments:
        lines.append("alignment_status（自我定位 vs 公众主题对齐情况）:")
        for a in gap_alignments:
            sup = ", ".join(x["label"] for x in a.get("supportingThemes", []))
            con = ", ".join(x["label"] for x in a.get("conflictingThemes", []))
            extras = []
            if sup:
                extras.append(f"支持:{sup}")
            if con:
                extras.append(f"冲突:{con}")
            extras_str = f"（{'; '.join(extras)}）" if extras else ""
            lines.append(f"  - 「{a['proposition']}」: {a['status']}{extras_str}")
        lines.append("")

    if gap_unexpected:
        lines.append("unexpected_themes（公众多出来讨论的主题，自我定位里没有）:")
        for u in gap_unexpected:
            lines.append(f"  - {u['label']}")
        lines.append("")

    if evidence_quotes:
        lines.append("evidence_quotes（代表性原话样本）:")
        for q in evidence_quotes[:MAX_EVIDENCE_QUOTES]:
            lines.append(
                f"  - [{q['sentimentTone']}/{q['themeLabel']}] {q['quote'][:180]}"
            )
        lines.append("")

    lines.append(
        "请基于以上素材，输出一份可直接交付客户的品牌印象速读 JSON。"
        "再次提醒：避免套话，每个判断必须引用主题 label 或具体数字。"
    )
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────
# 取证据（每个主题挑代表性原话）
# ──────────────────────────────────────────────────────────────────────────


def _fetch_evidence_quotes(
    db: Database,
    themes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """从每个主题里挑 2-3 条代表性原话喂给 LLM。

    优先级：representative_item_id（如果有原话）→ 主题下前 2 条 items 的 title+summary 拼接
    """
    quotes: list[dict[str, Any]] = []
    for t in themes:
        # 先用 theme 自带的 representative_quote
        if t.get("representativeQuote"):
            quotes.append({
                "themeLabel": t["themeLabel"],
                "sentimentTone": t["sentimentTone"],
                "quote": t["representativeQuote"],
            })
        # 再补 1 条主题下其他 item 的 title
        item_ids = list(t.get("itemIds") or [])[:3]
        if len(item_ids) > 1:
            placeholders = ",".join("?" * len(item_ids))
            rows = db.fetchall(
                f"SELECT id, title FROM intelligence_items WHERE id IN ({placeholders}) LIMIT 3",
                tuple(item_ids),
            )
            for r in rows:
                if r["id"] == t.get("representativeItemId"):
                    continue
                title = str(r["title"] or "").strip()
                if title and not any(q["quote"].startswith(title[:30]) for q in quotes):
                    quotes.append({
                        "themeLabel": t["themeLabel"],
                        "sentimentTone": t["sentimentTone"],
                        "quote": title,
                    })
                    break
    return quotes[:MAX_EVIDENCE_QUOTES]


# ──────────────────────────────────────────────────────────────────────────
# 落库 / 读取
# ──────────────────────────────────────────────────────────────────────────


def _persist_audit(
    db: Database,
    *,
    scope_type: str,
    scope_id: str,
    headline: str,
    narrative_md: str,
    tensions: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
    content_angles: dict[str, list[str]],
    evidence_theme_ids: list[str],
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=AUDIT_TTL_HOURS)
    now_iso = now.isoformat()
    expires_iso = expires.isoformat()
    audit_id = f"audit_{uuid.uuid4().hex[:12]}"

    # 单 scope 单条 — UPSERT
    db.execute(
        "DELETE FROM intelligence_brand_audits WHERE scope_type = ? AND scope_id = ?",
        (scope_type, scope_id),
    )
    db.execute(
        """
        INSERT INTO intelligence_brand_audits (
            id, scope_type, scope_id,
            headline, narrative_md, tensions_json, recommendations_json,
            content_angles_json, evidence_theme_ids_json,
            computed_at, expires_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            audit_id, scope_type, scope_id,
            headline, narrative_md, to_json(tensions), to_json(recommendations),
            to_json(content_angles), to_json(evidence_theme_ids),
            now_iso, expires_iso, now_iso, now_iso,
        ),
    )
    return {
        "id": audit_id,
        "scopeType": scope_type,
        "scopeId": scope_id,
        "headline": headline,
        "narrativeMd": narrative_md,
        "tensions": tensions,
        "recommendations": recommendations,
        "contentAngles": content_angles,
        "evidenceThemeIds": evidence_theme_ids,
        "computedAt": now_iso,
        "expiresAt": expires_iso,
    }


def get_audit(db: Database, *, scope_type: str, scope_id: str) -> dict[str, Any] | None:
    row = db.fetchone(
        "SELECT * FROM intelligence_brand_audits WHERE scope_type = ? AND scope_id = ?",
        (scope_type, scope_id),
    )
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "scopeType": str(row["scope_type"]),
        "scopeId": str(row["scope_id"]),
        "headline": str(row["headline"] or ""),
        "narrativeMd": str(row["narrative_md"] or ""),
        "tensions": from_json(row["tensions_json"], []),
        "recommendations": from_json(row["recommendations_json"], []),
        "contentAngles": from_json(row["content_angles_json"], {}),
        "evidenceThemeIds": from_json(row["evidence_theme_ids_json"], []),
        "computedAt": str(row["computed_at"]),
        "expiresAt": str(row["expires_at"]),
    }


def audit_is_fresh(db: Database, *, scope_type: str, scope_id: str) -> bool:
    row = db.fetchone(
        "SELECT expires_at FROM intelligence_brand_audits WHERE scope_type = ? AND scope_id = ?",
        (scope_type, scope_id),
    )
    if not row:
        return False
    try:
        expires = datetime.fromisoformat(str(row["expires_at"]))
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
    except Exception:  # noqa: BLE001
        return False
    return expires > datetime.now(timezone.utc)


# ──────────────────────────────────────────────────────────────────────────
# LLM 调用
# ──────────────────────────────────────────────────────────────────────────


def _invoke_llm(
    ai_service: object,
    prompt: str,
    timeout_seconds: float,
) -> dict[str, Any] | None:
    try:
        raw = ai_service._qwen_generate(  # type: ignore[attr-defined]  # noqa: SLF001
            prompt,
            AUDIT_SYSTEM_INSTRUCTION,
            AUDIT_RESPONSE_SCHEMA,
            timeout_seconds=timeout_seconds,
            max_tokens=4000,
            temperature=0.3,
            task_kind="default",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[brand-audit] LLM call failed: %s", exc)
        return None
    if not isinstance(raw, dict):
        try:
            raw = json.loads(str(raw))
        except Exception:  # noqa: BLE001
            return None
    return raw if isinstance(raw, dict) else None


def _normalize_audit(raw: dict[str, Any]) -> dict[str, Any]:
    """把 LLM 返回的 JSON 整理成内部结构（裁剪长字段、过滤空项）。"""
    headline = str(raw.get("headline") or "").strip()[:120]
    narrative = str(raw.get("narrative_md") or "").strip()[:2000]

    tensions_raw = raw.get("tensions") or []
    tensions: list[dict[str, Any]] = []
    if isinstance(tensions_raw, list):
        for t in tensions_raw:
            if not isinstance(t, dict):
                continue
            statement = str(t.get("statement") or "").strip()
            if not statement:
                continue
            tensions.append({
                "statement": statement[:200],
                "selfAnchor": str(t.get("self_anchor") or "").strip()[:50],
                "publicAnchor": str(t.get("public_anchor") or "").strip()[:50],
            })

    recs_raw = raw.get("recommendations") or []
    recs: list[dict[str, Any]] = []
    if isinstance(recs_raw, list):
        for r in recs_raw:
            if not isinstance(r, dict):
                continue
            action = str(r.get("action") or "").strip()
            if not action:
                continue
            recs.append({
                "action": action[:120],
                "rationale": str(r.get("rationale") or "").strip()[:300],
                "priority": str(r.get("priority") or "medium").strip().lower()
                if str(r.get("priority") or "").lower() in ("high", "medium", "low")
                else "medium",
            })

    angles_raw = raw.get("content_angles") or {}
    angles: dict[str, list[str]] = {"amplify": [], "new": []}
    if isinstance(angles_raw, dict):
        for key in ("amplify", "new"):
            val = angles_raw.get(key) or []
            if isinstance(val, list):
                angles[key] = [str(x).strip() for x in val if str(x).strip()][:5]

    return {
        "headline": headline,
        "narrative_md": narrative,
        "tensions": tensions,
        "recommendations": recs,
        "content_angles": angles,
    }


# ──────────────────────────────────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────────────────────────────────


def recompute_brand_audit(
    db: Database,
    ai_service: object | None,
    *,
    client_id: str | None,
    project_module_id: str | None,
    target_name: str,
    timeout_seconds: float = 150.0,
) -> dict[str, Any]:
    """重算品牌印象速读。"""
    scope_type = "project_module" if project_module_id else "client"
    scope_id = project_module_id or client_id or ""
    if not scope_id:
        return {"ok": False, "reason": "missing_scope", "audit": None}

    if ai_service is None:
        return {"ok": False, "reason": "ai_service_unavailable", "audit": None}
    try:
        health = ai_service.get_health()  # type: ignore[attr-defined]
        if not getattr(health, "ready", False):
            return {
                "ok": False,
                "reason": f"ai_not_ready: {getattr(health, 'detail', '')}",
                "audit": None,
            }
    except Exception:  # noqa: BLE001
        return {"ok": False, "reason": "ai_health_failed", "audit": None}

    themes = list_themes(db, scope_type=scope_type, scope_id=scope_id)
    if len(themes) < MIN_THEMES_FOR_AUDIT:
        # 删掉旧 audit 避免回显过期数据
        db.execute(
            "DELETE FROM intelligence_brand_audits WHERE scope_type = ? AND scope_id = ?",
            (scope_type, scope_id),
        )
        return {
            "ok": False,
            "reason": f"too_few_themes: {len(themes)} < {MIN_THEMES_FOR_AUDIT}",
            "audit": None,
        }

    # 取 brand_proposition — 优先级链：用户填 / strategic_profile / glossary 兜底
    effective_client_id = client_id
    if not effective_client_id and project_module_id:
        pm_row = db.fetchone(
            "SELECT client_id FROM project_modules WHERE id = ?",
            (project_module_id,),
        )
        effective_client_id = str(pm_row["client_id"]) if pm_row else ""
    propositions: list[str] = []
    proposition_source = "empty"
    if effective_client_id:
        propositions, proposition_source = infer_brand_proposition_from_data_center(
            db, client_id=effective_client_id,
        )

    # gap 信息可选——拉到就用，拉不到也能出 audit（让 LLM 自己识别"缺乏自我定位"）
    gap_alignments: list[dict[str, Any]] = []
    gap_unexpected: list[dict[str, Any]] = []
    if propositions:
        try:
            gap = compute_gap(
                db, ai_service,
                client_id=client_id, project_module_id=project_module_id,
                target_name=target_name, brand_proposition=brand_prop,
            )
            if gap.get("ok"):
                gap_alignments = gap.get("alignments") or []
                gap_unexpected = gap.get("unexpectedThemes") or []
        except Exception:  # noqa: BLE001
            pass

    evidence = _fetch_evidence_quotes(db, themes)

    prompt = _build_audit_prompt(
        target_name=target_name,
        propositions=propositions,
        themes=themes,
        gap_alignments=gap_alignments,
        gap_unexpected=gap_unexpected,
        evidence_quotes=evidence,
    )

    raw = _invoke_llm(ai_service, prompt, timeout_seconds)
    if not raw:
        return {"ok": False, "reason": "llm_failed_or_empty", "audit": None}

    norm = _normalize_audit(raw)
    if not norm["headline"] or not norm["narrative_md"]:
        return {"ok": False, "reason": "llm_returned_incomplete", "audit": None}

    audit = _persist_audit(
        db,
        scope_type=scope_type,
        scope_id=scope_id,
        headline=norm["headline"],
        narrative_md=norm["narrative_md"],
        tensions=norm["tensions"],
        recommendations=norm["recommendations"],
        content_angles=norm["content_angles"],
        evidence_theme_ids=[t["id"] for t in themes],
    )
    return {"ok": True, "audit": audit}
