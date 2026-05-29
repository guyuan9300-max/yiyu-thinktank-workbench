"""定位差异图（P5-B）。

让客户看见自己想被认为是 A，公众实际认为他是 A'。
派生视图：输入 = clients.brand_proposition + 已聚出的 themes；输出 = gap items。

不落表，按需算（< 5s 一次 LLM）。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.db import Database
from app.services.intelligence_theme_cluster import list_themes

logger = logging.getLogger(__name__)


GAP_SYSTEM_INSTRUCTION = (
    "你是品牌策略顾问。客户给出了他『希望外界认为他是怎样的』（self_propositions 列表），"
    "也已经从舆情聚出了大众对他形成的『印象主题』（public_themes 列表）。"
    "请逐个判断每个 self_proposition 在公众印象中的对齐状态："
    "  - affirmed：有公众主题正向支持这条自我定位（举出 supporting_theme_indices）；"
    "  - gap：自我定位强调，但公众主题没有支持，甚至反着说（举出 conflicting_theme_indices）；"
    "  - silent：公众完全没提到这条定位。"
    "另外标记出 unexpected_themes：那些不在 self_propositions 里、但公众强烈讨论的印象（写它们在 public_themes 中的 index）。"
    "每个判断给一句 reason 解释。只返回 JSON，不要 Markdown。"
)

GAP_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["alignments", "unexpected_theme_indices"],
    "properties": {
        "alignments": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["proposition", "status", "reason"],
                "properties": {
                    "proposition": {"type": "string"},
                    "status": {"type": "string", "enum": ["affirmed", "gap", "silent"]},
                    "supporting_theme_indices": {"type": "array", "items": {"type": "integer"}},
                    "conflicting_theme_indices": {"type": "array", "items": {"type": "integer"}},
                    "reason": {"type": "string"},
                },
            },
        },
        "unexpected_theme_indices": {"type": "array", "items": {"type": "integer"}},
    },
}


def infer_brand_proposition_from_data_center(
    db: Database,
    *,
    client_id: str,
) -> tuple[list[str], str]:
    """从数据中心自动推断品牌核心定位关键词。

    优先级（高到低）：
      1. clients.brand_proposition 用户已填  → 直接用
      2. client_strategic_profiles 战略画像有值 → 从中抽
      3. client_glossary 业务术语 + clients.domain → 拼凑兜底

    Returns: (propositions_list, source_label)
      source_label: 'user_filled' / 'strategic_profile' / 'inferred_from_glossary' / 'empty'
    """
    # Priority 1: 用户已填
    row = db.fetchone("SELECT brand_proposition FROM clients WHERE id = ?", (client_id,))
    if row and (row["brand_proposition"] or "").strip():
        return _parse_propositions(str(row["brand_proposition"])), "user_filled"

    # Priority 2: 战略画像
    sp = db.fetchone(
        "SELECT current_needs, strategic_value_to_yiyu, influence FROM client_strategic_profiles WHERE client_id = ?",
        (client_id,),
    )
    if sp:
        candidates: list[str] = []
        for field_name in ("strategic_value_to_yiyu", "current_needs", "influence"):
            text = str(sp[field_name] or "").strip()
            if text and len(text) >= 6:
                # 切句子取前几个名词短语（粗略：按顿号/逗号切）
                parts = re.split(r"[，,、；;\s]+", text)
                for p in parts:
                    p = p.strip()
                    if 2 <= len(p) <= 12:
                        candidates.append(p)
        if candidates:
            return candidates[:5], "strategic_profile"

    # Priority 3: 业务术语 + domain 兜底
    candidates: list[str] = []
    client_row = db.fetchone("SELECT domain FROM clients WHERE id = ?", (client_id,))
    if client_row and (client_row["domain"] or "").strip():
        candidates.append(str(client_row["domain"]).strip())

    # 取 client_glossary 里"业务术语"中 method-like 的（长度 4-10 字，含"学/法/课/营/计划"等方法论 marker）
    try:
        glo_rows = db.fetchall(
            """
            SELECT term FROM client_glossary
            WHERE client_id = ? AND category = '业务术语'
            ORDER BY length(term) ASC
            LIMIT 30
            """,
            (client_id,),
        )
        method_markers = ("学", "法", "课程", "计划", "学院", "营", "网络", "体系", "学说", "理念")
        for r in glo_rows:
            term = str(r["term"] or "").strip()
            if not (4 <= len(term) <= 12):
                continue
            if any(m in term for m in method_markers):
                if term not in candidates:
                    candidates.append(term)
            if len(candidates) >= 5:
                break
    except Exception:  # noqa: BLE001
        pass

    if candidates:
        return candidates[:5], "inferred_from_glossary"
    return [], "empty"


def _parse_propositions(raw: str) -> list[str]:
    """把 clients.brand_proposition 拆成关键词数组。

    支持中英逗号、顿号、分号、换行混用。每个长度 1-20 字，去重。
    """
    if not raw:
        return []
    parts = re.split(r"[，,、；;\n\r]+", raw)
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        token = p.strip()
        if not token or len(token) > 20:
            continue
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
        if len(out) >= 8:
            break
    return out


def _build_gap_prompt(
    target_name: str,
    propositions: list[str],
    themes: list[dict[str, Any]],
) -> str:
    lines = [f"target_name: {target_name}", "", "self_propositions:"]
    for i, p in enumerate(propositions):
        lines.append(f"  [{i}] {p}")
    lines.append("")
    lines.append("public_themes（索引从 0 开始）:")
    for i, t in enumerate(themes):
        lines.append(
            f"  [{i}] ({t['sentimentTone']}/{t['itemCount']}条) {t['themeLabel']} — {t['themeSummary']}"
        )
    lines.append("")
    lines.append("请输出 JSON。每个 self_proposition 都要在 alignments 里出现一次。")
    return "\n".join(lines)


def _call_llm(
    ai_service: object,
    target_name: str,
    propositions: list[str],
    themes: list[dict[str, Any]],
    timeout_seconds: float,
) -> dict[str, Any] | None:
    try:
        raw = ai_service._qwen_generate(  # type: ignore[attr-defined]  # noqa: SLF001
            _build_gap_prompt(target_name, propositions, themes),
            GAP_SYSTEM_INSTRUCTION,
            GAP_RESPONSE_SCHEMA,
            timeout_seconds=timeout_seconds,
            max_tokens=2000,
            temperature=0.15,
            task_kind="default",  # default profile：本地 32B 模型走完整 timeout，不被 fast_structured 限速
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[positioning-gap] LLM failed: %s", exc)
        return None
    if not isinstance(raw, dict):
        try:
            raw = json.loads(str(raw))
        except Exception:  # noqa: BLE001
            return None
    return raw if isinstance(raw, dict) else None


def compute_gap(
    db: Database,
    ai_service: object | None,
    *,
    client_id: str | None,
    project_module_id: str | None,
    target_name: str,
    brand_proposition: str | None = None,
    timeout_seconds: float = 120.0,
) -> dict[str, Any]:
    """算定位差异。返回 {ok, propositions, alignments, themes, unexpectedThemes, reason?}。"""
    scope_type = "project_module" if project_module_id else "client"
    scope_id = project_module_id or client_id or ""

    # brand_proposition 解析 — 优先级链：
    #   1. 调用方明确传入（覆盖一切）
    #   2. 从数据中心自动推断（用户填 / strategic_profile / glossary 兜底）
    proposition_source = "explicit"
    if brand_proposition is not None and brand_proposition.strip():
        propositions = _parse_propositions(brand_proposition)
    else:
        # project_module 走它所属的 client
        effective_client_id = client_id
        if not effective_client_id and project_module_id:
            pm_row = db.fetchone(
                "SELECT client_id FROM project_modules WHERE id = ?",
                (project_module_id,),
            )
            effective_client_id = str(pm_row["client_id"]) if pm_row else ""
        if effective_client_id:
            propositions, proposition_source = infer_brand_proposition_from_data_center(
                db, client_id=effective_client_id,
            )
        else:
            propositions = []

    themes = list_themes(db, scope_type=scope_type, scope_id=scope_id)

    if not propositions:
        return {
            "ok": False,
            "reason": "no_brand_proposition",
            "propositions": [],
            "propositionSource": proposition_source,
            "themes": themes,
            "alignments": [],
            "unexpectedThemes": [],
        }
    if not themes:
        return {
            "ok": False,
            "reason": "no_themes_yet",
            "propositions": propositions,
            "themes": [],
            "alignments": [],
            "unexpectedThemes": [],
        }
    if ai_service is None:
        return {
            "ok": False,
            "reason": "ai_service_unavailable",
            "propositions": propositions,
            "themes": themes,
            "alignments": [],
            "unexpectedThemes": [],
        }
    try:
        health = ai_service.get_health()  # type: ignore[attr-defined]
        if not getattr(health, "ready", False):
            return {
                "ok": False,
                "reason": f"ai_not_ready: {getattr(health, 'detail', '')}",
                "propositions": propositions,
                "themes": themes,
                "alignments": [],
                "unexpectedThemes": [],
            }
    except Exception:  # noqa: BLE001
        return {
            "ok": False,
            "reason": "ai_health_failed",
            "propositions": propositions,
            "themes": themes,
            "alignments": [],
            "unexpectedThemes": [],
        }

    raw = _call_llm(ai_service, target_name, propositions, themes, timeout_seconds)
    if not raw:
        return {
            "ok": False,
            "reason": "llm_failed",
            "propositions": propositions,
            "themes": themes,
            "alignments": [],
            "unexpectedThemes": [],
        }

    alignments_raw = raw.get("alignments") or []
    unexpected_indices = raw.get("unexpected_theme_indices") or []

    # 把索引解回 theme id
    def _idx_to_themes(indices: Any) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if not isinstance(indices, list):
            return out
        for idx in indices:
            try:
                i = int(idx)
            except (TypeError, ValueError):
                continue
            if 0 <= i < len(themes):
                out.append({"id": themes[i]["id"], "label": themes[i]["themeLabel"]})
        return out

    alignments: list[dict[str, Any]] = []
    if isinstance(alignments_raw, list):
        for a in alignments_raw:
            if not isinstance(a, dict):
                continue
            status = str(a.get("status") or "silent").lower()
            if status not in ("affirmed", "gap", "silent"):
                status = "silent"
            alignments.append({
                "proposition": str(a.get("proposition") or "").strip(),
                "status": status,
                "reason": str(a.get("reason") or "").strip()[:300],
                "supportingThemes": _idx_to_themes(a.get("supporting_theme_indices")),
                "conflictingThemes": _idx_to_themes(a.get("conflicting_theme_indices")),
            })

    # 补齐 propositions（防 LLM 漏判某些自我定位）
    seen_props = {a["proposition"] for a in alignments}
    for p in propositions:
        if p not in seen_props:
            alignments.append({
                "proposition": p,
                "status": "silent",
                "reason": "（未在 LLM 返回中出现，按 silent 兜底）",
                "supportingThemes": [],
                "conflictingThemes": [],
            })

    unexpected_themes = _idx_to_themes(unexpected_indices)

    return {
        "ok": True,
        "propositions": propositions,
        "propositionSource": proposition_source,
        "themes": themes,
        "alignments": alignments,
        "unexpectedThemes": unexpected_themes,
    }
