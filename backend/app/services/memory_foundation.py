from __future__ import annotations

import logging
from datetime import datetime
import re
from typing import Iterable

logger = logging.getLogger(__name__)
from uuid import uuid4

from app.db import Database, from_json, to_json
from app.models import (
    BackgroundReadiness,
    ClarificationRecord,
    ClientNotebookResponse,
    ClarificationAnswerPayload,
    ClarificationCreatePayload,
    EventLineMemoryResponse,
    EventLineMemorySnapshot,
    EventLineRecord,
    MemoryBackfillResultRecord,
    MemoryFact,
    MemoryStatus,
    OrganizationNotebookSnapshot,
)


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


def _coerce_text(value: object | None) -> str:
    return str(value or "").strip()


POLLUTED_MEMORY_MARKERS = (
    '{"prompt"',
    '"prompt":',
    "你将作为",
    "执行摘要",
    "# 执行摘要",
    "自动整理",
    "目标读者与写作定位",
    "请基于以下材料",
    "请勿直接复制",
    "写作要求",
)

GENERIC_MEMORY_PLACEHOLDERS = (
    "当前重点仍待补充",
    "建议先明确这一阶段的核心事项",
    "当前没有特别突出的阻塞",
    "仍需盯住推进收束",
    "当前还没有稳定识别",
    "暂时还没有稳定识别",
    "还缺下一步最关键动作",
    "当前还看不清",
    "最近关键决策仍待补充",
)


def is_polluted_memory_text(value: object | None) -> bool:
    text = _coerce_text(value)
    if not text:
        return False
    lowered = text.lower()
    if text.startswith("{") and '"prompt"' in lowered:
        return True
    if any(marker.lower() in lowered for marker in POLLUTED_MEMORY_MARKERS):
        return True
    if re.search(r"(^|\n)\s*(title|tags|summary)\s*:", lowered) and (
        '"prompt"' in lowered or "执行摘要" in text or "自动整理" in text
    ):
        return True
    if text.startswith("最近线索：") and (
        "正文" in text or re.search(r"第\s*\d+\s*页", text) or len(text) >= 60
    ):
        return True
    return False


def is_generic_memory_placeholder(value: object | None) -> bool:
    text = _coerce_text(value)
    if not text:
        return False
    return any(marker in text for marker in GENERIC_MEMORY_PLACEHOLDERS)


def sanitize_memory_background_text(
    value: object | None,
    *,
    max_length: int = 160,
    reject_generic: bool = False,
) -> str:
    text = re.sub(r"\s+", " ", _coerce_text(value)).strip()
    if not text:
        return ""
    if is_polluted_memory_text(text):
        return ""
    if reject_generic and is_generic_memory_placeholder(text):
        return ""
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip("，、；：:。 ") + "…"


def _sanitize_text_list(
    values: Iterable[object | None],
    *,
    reject_generic: bool = False,
    limit: int | None = None,
    max_length: int = 80,
) -> list[str]:
    cleaned = _unique(
        sanitize_memory_background_text(value, reject_generic=reject_generic, max_length=max_length)
        for value in values
    )
    if limit is None:
        return cleaned
    return cleaned[:limit]


def _parse_list(value: object | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        try:
            parsed = from_json(value, [])
        except Exception:
            parsed = []
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
        text = value.strip()
        return [text] if text else []
    return []


def _unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = str(item).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _ratio(filled: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(max(0.0, min(1.0, filled / total)), 2)


BACKGROUND_TOKEN_STOPWORDS = {
    "今天",
    "本周",
    "下周",
    "客户",
    "项目",
    "组织",
    "团队",
    "我们",
    "继续",
    "推进",
    "合作",
    "沟通",
    "对接",
    "见面",
    "吃饭",
    "讨论",
    "确认",
    "安排",
    "沟通会",
    "这次",
    "本次",
    "当前",
    "下一步",
    "方案",
}


def _extract_reference_tokens(text: str) -> list[str]:
    normalized = _coerce_text(text)
    if not normalized:
        return []
    candidates: list[str] = []
    for chunk in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", normalized):
        token = chunk.strip()
        if len(token) >= 2 and token not in BACKGROUND_TOKEN_STOPWORDS:
            candidates.append(token)
        if re.fullmatch(r"[\u4e00-\u9fff]{4,32}", token):
            for size in range(2, min(len(token), 4) + 1):
                for start in range(0, len(token) - size + 1):
                    piece = token[start : start + size]
                    if piece not in BACKGROUND_TOKEN_STOPWORDS:
                        candidates.append(piece)
    return _unique([item for item in candidates if len(item) >= 2])[:24]


def _token_matches_text(token: str, text: str) -> bool:
    normalized_text = _coerce_text(text)
    if not token or not normalized_text:
        return False
    return token in normalized_text


def _slugify_fact_key_part(value: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", _coerce_text(value))
    return normalized.strip("_")[:48] or "unknown"


def _reference_scope_id(client_id: str, scope_type: str, label: str) -> str:
    return f"{client_id}::{scope_type}::{_slugify_fact_key_part(label)}"


def _extract_person_candidates(*texts: str) -> list[str]:
    candidates: list[str] = []
    patterns = [
        r"由([\u4e00-\u9fff]{2,4})负责",
        r"负责人[：: ]?([\u4e00-\u9fff]{2,4})",
        r"联系人[：: ]?([\u4e00-\u9fff]{2,4})",
        r"对接人[：: ]?([\u4e00-\u9fff]{2,4})",
        r"由([\u4e00-\u9fff]{2,4})牵头",
    ]
    for text in texts:
        normalized = _coerce_text(text)
        if not normalized:
            continue
        for pattern in patterns:
            for match in re.findall(pattern, normalized):
                candidate = _coerce_text(match)
                if 2 <= len(candidate) <= 4:
                    candidates.append(candidate)
    return _unique(candidates)[:8]


def _sync_reference_scope_facts(db: Database, client_id: str, snapshot: OrganizationNotebookSnapshot) -> None:
    notebook_source_id = f"notebook:{client_id}"
    for person in snapshot.keyPeople:
        upsert_memory_fact(
            db,
            scope_type="person",
            scope_id=_reference_scope_id(client_id, "person", person),
            fact_key="background",
            fact_value=f"{person}｜关键人物背景：{snapshot.collaborationRelationship or snapshot.organizationIntro or '客户关键人物'}",
            source_type="organization_notebook",
            source_id=notebook_source_id,
            confidence=0.76,
            freshness=0.92,
            evidence_refs=[notebook_source_id, f"client:{client_id}"],
        )
    for product in _unique([*snapshot.keyProducts, *snapshot.businessModules]):
        upsert_memory_fact(
            db,
            scope_type="product",
            scope_id=_reference_scope_id(client_id, "product", product),
            fact_key="background",
            fact_value=f"{product}｜业务模块背景：{snapshot.collaborationRelationship or snapshot.organizationIntro or '当前业务模块'}",
            source_type="organization_notebook",
            source_id=notebook_source_id,
            confidence=0.72,
            freshness=0.9,
            evidence_refs=[notebook_source_id, f"client:{client_id}"],
        )


def _resolve_client_id_for_memory_scope(db: Database, scope_type: str, scope_id: str) -> str | None:
    normalized_scope_type = _coerce_text(scope_type)
    normalized_scope_id = _coerce_text(scope_id)
    if not normalized_scope_type or not normalized_scope_id:
        return None
    if normalized_scope_type == "client":
        return normalized_scope_id
    if normalized_scope_type == "task":
        row = db.fetchone("SELECT client_id FROM tasks WHERE id = ?", (normalized_scope_id,))
        return _coerce_text(row["client_id"]) if row else None
    if normalized_scope_type == "event_line":
        row = db.fetchone("SELECT primary_client_id FROM event_lines WHERE id = ?", (normalized_scope_id,))
        return _coerce_text(row["primary_client_id"]) if row else None
    if normalized_scope_type in {"person", "product"} and "::" in normalized_scope_id:
        return normalized_scope_id.split("::", 1)[0].strip() or None
    return None


def _build_notebook_reference_entries(snapshot: OrganizationNotebookSnapshot | None) -> list[dict[str, str]]:
    if not snapshot:
        return []
    entries: list[dict[str, str]] = []
    collaboration_context = "；".join(
        part
        for part in (
            snapshot.collaborationRelationship,
            snapshot.organizationIntro,
            snapshot.currentStage,
        )
        if _coerce_text(part)
    )[:240]
    if snapshot.organizationIntro:
        entries.append(
            {
                "entry_type": "organization",
                "label": snapshot.organizationIntro[:32],
                "background": f"组织背景：{snapshot.organizationIntro[:240]}",
            }
        )
    if snapshot.collaborationRelationship:
        entries.append(
            {
                "entry_type": "relationship",
                "label": snapshot.collaborationRelationship[:32],
                "background": f"合作背景：{snapshot.collaborationRelationship[:240]}",
            }
        )
    for person in snapshot.keyPeople:
        entries.append(
            {
                "entry_type": "person",
                "label": person,
                "background": f"{person}｜关键人物背景：{collaboration_context or '客户关键人物'}",
            }
        )
    for product in _unique([*snapshot.keyProducts, *snapshot.businessModules]):
        entries.append(
            {
                "entry_type": "product",
                "label": product,
                "background": f"{product}｜业务模块背景：{collaboration_context or '当前业务模块'}",
            }
        )
    for goal in snapshot.collaborationGoals:
        entries.append(
            {
                "entry_type": "goal",
                "label": goal,
                "background": f"{goal}｜当前合作目标：{collaboration_context or '需要结合合作目标理解'}",
            }
        )
    return entries


def _match_task_reference_entries(
    snapshot: OrganizationNotebookSnapshot | None,
    task_text: str,
) -> list[dict[str, str]]:
    reference_tokens = _extract_reference_tokens(task_text)
    if not snapshot or not reference_tokens:
        return []
    matches: list[dict[str, str]] = []
    for entry in _build_notebook_reference_entries(snapshot):
        label = entry["label"]
        background = entry["background"]
        if any(
            _token_matches_text(token, label) or _token_matches_text(token, background)
            for token in reference_tokens
        ):
            matches.append(entry)
    unique_matches: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for entry in matches:
        key = (entry["entry_type"], entry["label"])
        if key in seen:
            continue
        seen.add(key)
        unique_matches.append(entry)
    return unique_matches[:4]


def _read_memory_facts(db: Database, scope_type: str, scope_id: str, *, limit: int = 12) -> list[MemoryFact]:
    rows = db.fetchall(
        """
        SELECT *
        FROM memory_facts
        WHERE scope_type = ? AND scope_id = ?
        ORDER BY updated_at DESC, created_at DESC
        LIMIT ?
        """,
        (scope_type, scope_id, limit),
    )
    return [_build_memory_fact(row) for row in rows]


def _read_clarifications(db: Database, scope_type: str, scope_id: str, *, status: str | None = None) -> list[ClarificationRecord]:
    if status:
        rows = db.fetchall(
            """
            SELECT *
            FROM clarification_records
            WHERE scope_type = ? AND scope_id = ? AND status = ?
            ORDER BY updated_at DESC, created_at DESC
            """,
            (scope_type, scope_id, status),
        )
    else:
        rows = db.fetchall(
            """
            SELECT *
            FROM clarification_records
            WHERE scope_type = ? AND scope_id = ?
            ORDER BY updated_at DESC, created_at DESC
            """,
            (scope_type, scope_id),
        )
    return [_build_clarification_record(row) for row in rows]


def _build_memory_fact(row) -> MemoryFact:
    return MemoryFact(
        id=str(row["id"]),
        scopeType=str(row["scope_type"]),  # type: ignore[arg-type]
        scopeId=str(row["scope_id"]),
        factKey=str(row["fact_key"]),
        factValue=str(row["fact_value"]),
        sourceType=str(row["source_type"]),
        sourceId=str(row["source_id"]),
        confidence=float(row["confidence"] or 0.0),
        freshness=float(row["freshness"] or 0.0),
        evidenceRefs=_parse_list(row["evidence_refs_json"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _build_clarification_record(row) -> ClarificationRecord:
    return ClarificationRecord(
        id=str(row["id"]),
        scopeType=str(row["scope_type"]),  # type: ignore[arg-type]
        scopeId=str(row["scope_id"]),
        slotKey=str(row["slot_key"]),
        question=str(row["question"]),
        status=str(row["status"]),  # type: ignore[arg-type]
        answerText=str(row["answer_text"]) if row["answer_text"] else None,
        writeScope=_parse_list(row["write_scope_json"]),
        resolvedFactIds=_parse_list(row["resolved_fact_ids_json"]),
        reusable=bool(row["reusable"]),
        createdAt=str(row["created_at"]),
        answeredAt=str(row["answered_at"]) if row["answered_at"] else None,
        updatedAt=str(row["updated_at"]),
    )


def _build_event_line_record(row) -> EventLineRecord:
    return EventLineRecord(
        id=str(row["id"]),
        name=str(row["name"]),
        kind=str(row["kind"]),  # type: ignore[arg-type]
        status=str(row["status"]),  # type: ignore[arg-type]
        stage=str(row["stage"]) if row["stage"] else None,
        summary=str(row["summary"]) if row["summary"] else None,
        intent=str(row["intent"]) if row["intent"] else None,
        currentBlocker=str(row["current_blocker"]) if row["current_blocker"] else None,
        recentDecision=str(row["recent_decision"]) if row["recent_decision"] else None,
        nextStep=str(row["next_step"]) if row["next_step"] else None,
        ownerId=str(row["owner_id"]) if row["owner_id"] else None,
        ownerName=str(row["owner_name"]) if row["owner_name"] else None,
        primaryClientId=str(row["primary_client_id"]) if row["primary_client_id"] else None,
        primaryClientName=str(row["primary_client_name"]) if row["primary_client_name"] else None,
        primaryDepartmentId=str(row["primary_department_id"]) if row["primary_department_id"] else None,
        primaryDepartmentName=str(row["primary_department_name"]) if row["primary_department_name"] else None,
        participantIds=_parse_list(row["participant_ids_json"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _build_organization_notebook_snapshot(row) -> OrganizationNotebookSnapshot:
    return OrganizationNotebookSnapshot(
        id=str(row["id"]),
        clientId=str(row["client_id"]),
        organizationIntro=sanitize_memory_background_text(row["organization_intro"], max_length=240),
        collaborationRelationship=sanitize_memory_background_text(row["collaboration_relationship"], max_length=320),
        currentStage=sanitize_memory_background_text(row["current_stage"], max_length=48),
        businessModules=_sanitize_text_list(_parse_list(row["business_modules_json"]), limit=8, max_length=48),
        keyPeople=_sanitize_text_list(_parse_list(row["key_people_json"]), limit=8, max_length=16),
        keyProducts=_sanitize_text_list(_parse_list(row["key_products_json"]), limit=8, max_length=48),
        currentChallenges=_sanitize_text_list(
            _parse_list(row["current_challenges_json"]),
            reject_generic=True,
            limit=8,
            max_length=96,
        ),
        collaborationGoals=_sanitize_text_list(
            _parse_list(row["collaboration_goals_json"]),
            reject_generic=True,
            limit=8,
            max_length=96,
        ),
        recentFacts=_sanitize_text_list(_parse_list(row["recent_facts_json"]), limit=8, max_length=120),
        informationGaps=_sanitize_text_list(_parse_list(row["information_gaps_json"]), limit=8, max_length=96),
        updatedAt=str(row["updated_at"]),
        confidence=float(row["confidence"] or 0.0),
    )


def _build_event_line_memory_snapshot(row) -> EventLineMemorySnapshot:
    return EventLineMemorySnapshot(
        id=str(row["id"]),
        eventLineId=str(row["event_line_id"]),
        lineName=str(row["line_name"]),
        currentStage=sanitize_memory_background_text(row["current_stage"], max_length=48),
        currentWork=sanitize_memory_background_text(row["current_work"], reject_generic=True, max_length=140),
        currentBlocker=sanitize_memory_background_text(row["current_blocker"], reject_generic=True, max_length=140),
        recentDecision=sanitize_memory_background_text(row["recent_decision"], reject_generic=True, max_length=140),
        nextStep=sanitize_memory_background_text(row["next_step"], reject_generic=True, max_length=140),
        evidenceRefs=_sanitize_text_list(_parse_list(row["evidence_refs_json"]), limit=10, max_length=80),
        clarificationNeeds=_sanitize_text_list(_parse_list(row["clarification_needs_json"]), limit=8, max_length=48),
        analysisSignals=_sanitize_text_list(_parse_list(row["analysis_signals_json"]), limit=4, max_length=140),
        predictionReadiness=float(row["prediction_readiness"] or 0.0),
        updatedAt=str(row["updated_at"]),
        confidence=float(row["confidence"] or 0.0),
    )


# ── Document Knowledge → Memory Pipeline ──────────────────────────────

def backfill_document_knowledge_to_memory(db: Database) -> dict[str, int]:
    """
    把 knowledge_surrogates 中的文档洞察批量写入 memory_facts。

    每个客户的每个文件夹分类（组织与战略/项目与业务/财务与筹款/品牌与传播/战略陪伴）
    产出一条聚合记忆 + 每份高质量文档产出一条独立记忆。

    这样 AI 在理解任务/生成研判时，能读到"CFFC 的战略文档反复提到传播清晰度问题"
    这种从大量文档中提炼出来的认知，而不是只有任务标题。
    """
    import json as _json

    stats = {"clients_processed": 0, "category_summaries": 0, "doc_insights": 0, "total_facts": 0}

    # 获取所有客户
    clients = db.fetchall("SELECT id, name FROM clients")

    for client in clients:
        client_id = str(client["id"])
        client_name = str(client["name"])

        # 获取该客户的所有有摘要的知识代理
        surrogates = db.fetchall(
            """
            SELECT title, folder_category, document_role, overview_summary,
                   core_questions_json, distinct_findings_json, entities_json
            FROM knowledge_surrogates
            WHERE client_id = ? AND overview_summary IS NOT NULL AND LENGTH(overview_summary) > 50
            ORDER BY folder_category, title
            """,
            (client_id,),
        )

        if not surrogates:
            continue

        stats["clients_processed"] += 1

        # ── 按 folder_category 分组聚合 ──
        by_category: dict[str, list] = {}
        for s in surrogates:
            cat = str(s["folder_category"]) or "其他"
            by_category.setdefault(cat, []).append(s)

        for category, docs in by_category.items():
            # 聚合该分类下的核心发现
            all_findings: list[str] = []
            all_entities: list[str] = []
            all_roles: list[str] = []
            summaries: list[str] = []

            for doc in docs:
                summary = str(doc["overview_summary"]).strip()
                if summary:
                    summaries.append(summary[:200])

                findings = _json.loads(doc["distinct_findings_json"]) if doc["distinct_findings_json"] else []
                all_findings.extend(str(f)[:120] for f in findings[:3])

                entities = _json.loads(doc["entities_json"]) if doc["entities_json"] else []
                all_entities.extend(str(e) for e in entities[:3])

                role = str(doc["document_role"]) if doc["document_role"] else ""
                if role and role not in all_roles:
                    all_roles.append(role)

            # 去重
            unique_findings = list(dict.fromkeys(all_findings))[:10]
            unique_entities = list(dict.fromkeys(all_entities))[:8]

            # 写入分类级聚合记忆
            category_value = f"[{client_name}/{category}] 共 {len(docs)} 份文档。"
            if unique_findings:
                category_value += f" 关键发现：{'；'.join(unique_findings[:5])}"
            if unique_entities:
                category_value += f" 涉及：{'、'.join(unique_entities[:5])}"

            upsert_memory_fact(
                db,
                scope_type="client",
                scope_id=client_id,
                fact_key=f"knowledge_category:{category}",
                fact_value=category_value[:800],
                source_type="document_knowledge_backfill",
                source_id=f"{client_id}:{category}",
                confidence=0.75,
                freshness=0.8,
            )
            stats["category_summaries"] += 1
            stats["total_facts"] += 1

        # ── 每份高价值文档写入独立记忆 ──
        _skip_patterns = {"readme", "video_list", "changelog", "license", "node_modules", ".git", "test", "debug", "verify"}
        for s in surrogates:
            summary = str(s["overview_summary"]).strip()
            if len(summary) < 100:
                continue  # 跳过摘要太短的

            title = str(s["title"])
            title_lower = title.lower()
            # 过滤技术文件、测试文件、链接列表等
            if any(p in title_lower for p in _skip_patterns):
                continue

            role = str(s["document_role"]) if s["document_role"] else ""
            category = str(s["folder_category"]) or "其他"

            findings = _json.loads(s["distinct_findings_json"]) if s["distinct_findings_json"] else []
            top_findings = [str(f)[:120] for f in findings[:3]]

            fact_value = f"[{title}] {role}。{summary[:300]}"
            if top_findings:
                fact_value += f" 要点：{'；'.join(top_findings)}"

            upsert_memory_fact(
                db,
                scope_type="client",
                scope_id=client_id,
                fact_key=f"doc_insight:{title[:60]}",
                fact_value=fact_value[:800],
                source_type="document_knowledge_backfill",
                source_id=f"surrogate:{s['title'][:80]}",
                confidence=0.7,
                freshness=0.7,
            )
            stats["doc_insights"] += 1
            stats["total_facts"] += 1

    logger.info("[memory-foundation] document knowledge backfill complete: %s", stats)
    return stats


def upsert_memory_fact(
    db: Database,
    *,
    scope_type: str,
    scope_id: str,
    fact_key: str,
    fact_value: str,
    source_type: str,
    source_id: str,
    confidence: float = 0.6,
    freshness: float = 0.6,
    evidence_refs: list[str] | None = None,
) -> MemoryFact:
    normalized_value = _coerce_text(fact_value)
    if not normalized_value:
        raise ValueError("fact_value cannot be empty")
    timestamp = _now_iso()
    existing = db.fetchone(
        """
        SELECT id, created_at
        FROM memory_facts
        WHERE scope_type = ? AND scope_id = ? AND fact_key = ? AND source_type = ? AND source_id = ?
        """,
        (scope_type, scope_id, fact_key, source_type, source_id),
    )
    fact_id = str(existing["id"]) if existing else _new_id("mfact")
    created_at = str(existing["created_at"]) if existing else timestamp
    db.execute(
        """
        INSERT INTO memory_facts(
            id, scope_type, scope_id, fact_key, fact_value, source_type, source_id,
            confidence, freshness, evidence_refs_json, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(scope_type, scope_id, fact_key, source_type, source_id) DO UPDATE SET
            fact_value = excluded.fact_value,
            confidence = excluded.confidence,
            freshness = excluded.freshness,
            evidence_refs_json = excluded.evidence_refs_json,
            updated_at = excluded.updated_at
        """,
        (
            fact_id,
            scope_type,
            scope_id,
            fact_key,
            normalized_value,
            source_type,
            source_id,
            confidence,
            freshness,
            to_json(_unique(evidence_refs or [])),
            created_at,
            timestamp,
        ),
    )
    row = db.fetchone("SELECT * FROM memory_facts WHERE id = ?", (fact_id,))
    assert row is not None
    return _build_memory_fact(row)


def refresh_organization_notebook_snapshot(db: Database, client_id: str) -> OrganizationNotebookSnapshot | None:
    client_row = db.fetchone("SELECT * FROM clients WHERE id = ?", (client_id,))
    if not client_row:
        return None

    dna_rows = db.fetchall(
        "SELECT * FROM client_dna_documents WHERE client_id = ? ORDER BY updated_at DESC",
        (client_id,),
    )
    dna_by_module = {str(row["module_key"]): row for row in dna_rows}

    organization_row = dna_by_module.get("organization_intro")
    business_row = dna_by_module.get("business_intro")
    team_row = dna_by_module.get("team_intro")
    market_row = dna_by_module.get("market_intro")
    organization_intro = sanitize_memory_background_text(
        organization_row["summary"] if organization_row else "",
        max_length=240,
    )
    if not organization_intro:
        organization_intro = sanitize_memory_background_text(client_row["intro"], max_length=240)
    business_intro = sanitize_memory_background_text(business_row["summary"] if business_row else "", max_length=180)
    team_intro = sanitize_memory_background_text(team_row["summary"] if team_row else "", max_length=180)
    market_intro = sanitize_memory_background_text(market_row["summary"] if market_row else "", max_length=180)

    project_modules = _sanitize_text_list(
        [
        row["name"]
        for row in db.fetchall(
            "SELECT name FROM project_modules WHERE client_id = ? ORDER BY updated_at DESC",
            (client_id,),
        )
    ],
        limit=8,
        max_length=48,
    )
    goals = _sanitize_text_list(
        [
        row["title"]
        for row in db.fetchall(
            "SELECT title FROM goal_records WHERE client_id = ? ORDER BY updated_at DESC",
            (client_id,),
        )
    ],
        reject_generic=True,
        limit=8,
        max_length=96,
    )
    key_people = _unique(
        [
            *[
                _coerce_text(row["owner_name"])
                for row in db.fetchall(
                    "SELECT owner_name FROM goal_records WHERE client_id = ? ORDER BY updated_at DESC",
                    (client_id,),
                )
            ],
            *[
                _coerce_text(row["owner_name"])
                for row in db.fetchall(
                    "SELECT owner_name FROM project_modules WHERE client_id = ? ORDER BY updated_at DESC",
                    (client_id,),
                )
            ],
            *[
                _coerce_text(row["owner_name"])
                for row in db.fetchall(
                    "SELECT owner_name FROM tasks WHERE client_id = ? ORDER BY updated_at DESC LIMIT 8",
                    (client_id,),
                )
            ],
            *_extract_person_candidates(organization_intro, business_intro, team_intro, market_intro),
        ]
    )
    linked_event_lines = list_linked_event_lines(db, client_id)
    current_challenges = _sanitize_text_list(
        [
            *[
                item
                for row in dna_rows
                for item in _parse_list(row["missing_info_json"])
            ],
            *[
                line.currentBlocker
                for line in linked_event_lines
            ],
        ],
        reject_generic=True,
        limit=8,
        max_length=96,
    )
    recent_facts = _sanitize_text_list(
        [item.factValue for item in _read_memory_facts(db, "client", client_id, limit=6)],
        limit=6,
        max_length=140,
    )
    information_gaps = _sanitize_text_list(
        [
            *[
                item
                for row in dna_rows
                for item in _parse_list(row["missing_info_json"])
            ],
            *(item for line in linked_event_lines for item in (_read_event_line_missing_slots(db, line.id))),
        ],
        limit=8,
        max_length=96,
    )
    business_modules = project_modules[:8]
    key_products = _unique(project_modules)[:8]
    collaboration_goals = _unique(goals)[:8]
    relationship_summary_parts = [
        sanitize_memory_background_text(client_row["intro"], max_length=180),
        business_intro,
        team_intro,
        market_intro,
    ]
    collaboration_relationship = "；".join(part for part in relationship_summary_parts if part)[:320]
    filled = sum(
        1
        for item in (
            organization_intro,
            collaboration_relationship,
            _coerce_text(client_row["stage"]),
            business_modules,
            key_people,
            key_products,
            collaboration_goals,
            recent_facts,
        )
        if item
    )
    notebook_score = _ratio(filled, 8)  # 0~1

    # 综合 confidence：notebook 字段完整度 + 文档丰富度 + 记忆密度 + DNA 覆盖度
    doc_count = int(db.scalar("SELECT COUNT(*) FROM knowledge_documents WHERE client_id = ?", (client_id,)) or 0)
    memory_fact_count = int(db.scalar("SELECT COUNT(*) FROM memory_facts WHERE scope_type = 'client' AND scope_id = ?", (client_id,)) or 0)
    dna_count = len(dna_rows)
    surrogate_count = int(db.scalar("SELECT COUNT(*) FROM knowledge_surrogates WHERE client_id = ?", (client_id,)) or 0)
    event_line_count = len(linked_event_lines)

    # 文档丰富度：0~1，10份=0.3，50份=0.7，100份=0.9，200+=1.0
    doc_score = min(1.0, doc_count / 200) if doc_count > 0 else 0
    # 记忆密度：0~1，10条=0.2，50条=0.6，100+=1.0
    memory_score = min(1.0, memory_fact_count / 100) if memory_fact_count > 0 else 0
    # DNA 覆盖：0~1，4个模块全有=1.0
    dna_score = min(1.0, dna_count / 4)
    # 知识代理：0~1（文档被深度处理的比例）
    surrogate_score = min(1.0, surrogate_count / max(doc_count, 1))
    # 事件线活跃度
    eline_score = min(1.0, event_line_count / 3) if event_line_count > 0 else 0

    # 加权综合：notebook 30% + 文档 25% + 记忆 20% + DNA 15% + 事件线 10%
    confidence = round(
        notebook_score * 0.30
        + doc_score * 0.25
        + memory_score * 0.20
        + dna_score * 0.15
        + eline_score * 0.10,
        2
    )
    updated_candidates = [
        _coerce_text(client_row["updated_at"]),
        *[_coerce_text(row["updated_at"]) for row in dna_rows],
        *[_coerce_text(row["updated_at"]) for row in db.fetchall("SELECT updated_at FROM project_modules WHERE client_id = ?", (client_id,))],
        *[_coerce_text(row["updated_at"]) for row in db.fetchall("SELECT updated_at FROM goal_records WHERE client_id = ?", (client_id,))],
        *[_coerce_text(item.updatedAt) for item in _read_memory_facts(db, "client", client_id, limit=1)],
    ]
    updated_at = max([item for item in updated_candidates if item], default=_now_iso())
    notebook_id = f"notebook_{client_id}"
    existing = db.fetchone(
        "SELECT created_at FROM organization_notebook_snapshots WHERE client_id = ?",
        (client_id,),
    )
    created_at = str(existing["created_at"]) if existing else updated_at
    db.execute(
        """
        INSERT INTO organization_notebook_snapshots(
            id, client_id, organization_intro, collaboration_relationship, current_stage, business_modules_json,
            key_people_json, key_products_json, current_challenges_json, collaboration_goals_json, recent_facts_json,
            information_gaps_json, confidence, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(client_id) DO UPDATE SET
            organization_intro = excluded.organization_intro,
            collaboration_relationship = excluded.collaboration_relationship,
            current_stage = excluded.current_stage,
            business_modules_json = excluded.business_modules_json,
            key_people_json = excluded.key_people_json,
            key_products_json = excluded.key_products_json,
            current_challenges_json = excluded.current_challenges_json,
            collaboration_goals_json = excluded.collaboration_goals_json,
            recent_facts_json = excluded.recent_facts_json,
            information_gaps_json = excluded.information_gaps_json,
            confidence = excluded.confidence,
            updated_at = excluded.updated_at
        """,
        (
            notebook_id,
            client_id,
            organization_intro,
            collaboration_relationship,
            _coerce_text(client_row["stage"]),
            to_json(business_modules),
            to_json(key_people),
            to_json(key_products),
            to_json(current_challenges),
            to_json(collaboration_goals),
            to_json(recent_facts),
            to_json(information_gaps),
            confidence,
            created_at,
            updated_at,
        ),
    )
    row = db.fetchone(
        "SELECT * FROM organization_notebook_snapshots WHERE client_id = ?",
        (client_id,),
    )
    assert row is not None
    snapshot = _build_organization_notebook_snapshot(row)
    _sync_reference_scope_facts(db, client_id, snapshot)
    return snapshot


def _read_event_line_missing_slots(db: Database, event_line_id: str) -> list[str]:
    row = db.fetchone(
        "SELECT clarification_needs_json FROM event_line_memory_snapshots WHERE event_line_id = ?",
        (event_line_id,),
    )
    return _parse_list(row["clarification_needs_json"]) if row else []


def list_linked_event_lines(db: Database, client_id: str, *, limit: int = 12) -> list[EventLineRecord]:
    rows = db.fetchall(
        """
        SELECT *
        FROM event_lines
        WHERE primary_client_id = ?
           OR id IN (
                SELECT DISTINCT event_line_id
                FROM tasks
                WHERE client_id = ? AND event_line_id IS NOT NULL AND TRIM(event_line_id) <> ''
           )
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (client_id, client_id, limit),
    )
    return [_build_event_line_record(row) for row in rows]


def refresh_event_line_memory_snapshot(db: Database, event_line_id: str) -> EventLineMemorySnapshot | None:
    row = db.fetchone("SELECT * FROM event_lines WHERE id = ?", (event_line_id,))
    if not row:
        return None

    task_rows = db.fetchall(
        """
        SELECT title, status, updated_at
        FROM tasks
        WHERE event_line_id = ?
        ORDER BY updated_at DESC
        LIMIT 12
        """,
        (event_line_id,),
    )
    attachment_rows = db.fetchall(
        """
        SELECT title, created_at
        FROM task_attachments
        WHERE event_line_id = ?
        ORDER BY created_at DESC
        LIMIT 6
        """,
        (event_line_id,),
    )
    activity_rows = db.fetchall(
        """
        SELECT title, summary, happened_at
        FROM event_line_activities
        WHERE event_line_id = ?
        ORDER BY happened_at DESC, created_at DESC
        LIMIT 8
        """,
        (event_line_id,),
    )
    review_signals: list[str] = []
    review_rows = db.fetchall(
        "SELECT task_snapshot_json, note FROM weekly_review_task_entries ORDER BY updated_at DESC LIMIT 100",
    )
    for review_row in review_rows:
        snapshot = from_json(review_row["task_snapshot_json"], {})
        if isinstance(snapshot, dict) and str(snapshot.get("eventLineId") or "").strip() == event_line_id:
            note = _coerce_text(review_row["note"])
            if note:
                review_signals.append(note)
        if len(review_signals) >= 4:
            break

    event_line = _build_event_line_record(row)
    current_work = sanitize_memory_background_text(event_line.summary, reject_generic=True, max_length=140)
    if not current_work:
        current_work = sanitize_memory_background_text(
            _coerce_text(task_rows[0]["title"]) if task_rows else "",
            reject_generic=True,
            max_length=140,
        )
    current_blocker = sanitize_memory_background_text(event_line.currentBlocker, reject_generic=True, max_length=140)
    recent_decision = sanitize_memory_background_text(event_line.recentDecision, reject_generic=True, max_length=140)
    if not recent_decision:
        decision_fact = next(
            (
                sanitize_memory_background_text(item.factValue, reject_generic=True, max_length=140)
                for item in _read_memory_facts(db, "event_line", event_line_id, limit=6)
                if item.factKey.startswith("meeting_decision")
            ),
            "",
        )
        recent_decision = decision_fact
    next_step = sanitize_memory_background_text(event_line.nextStep, reject_generic=True, max_length=140)
    if not next_step:
        next_step = next(
            (
                sanitize_memory_background_text(task_row["title"], reject_generic=True, max_length=140)
                for task_row in task_rows
                if str(task_row["status"]) in {"inbox", "todo", "doing"}
            ),
            "",
        )
    evidence_refs = _unique(
        [
            *[f"任务：{_coerce_text(item['title'])}" for item in task_rows],
            *[f"附件：{_coerce_text(item['title'])}" for item in attachment_rows],
            *[f"活动：{_coerce_text(item['title'])}" for item in activity_rows],
        ]
    )[:10]
    clarification_needs = _unique(
        [
            "current_stage" if not _coerce_text(event_line.stage) else "",
            "current_work" if not current_work else "",
            "current_blocker" if not current_blocker else "",
            "recent_decision" if not recent_decision else "",
            "next_step" if not next_step else "",
        ]
    )
    filled = sum(
        1
        for item in (
            _coerce_text(event_line.stage),
            current_work,
            current_blocker,
            recent_decision,
            next_step,
        )
        if item
    )
    evidence_score = min(len(evidence_refs), 6) / 6
    prediction_readiness = round((_ratio(filled, 5) * 0.75) + (evidence_score * 0.25), 2)
    confidence = round((_ratio(filled, 5) * 0.7) + (evidence_score * 0.3), 2)
    updated_candidates = [
        _coerce_text(row["updated_at"]),
        *[_coerce_text(item["updated_at"]) for item in task_rows],
        *[_coerce_text(item["created_at"]) for item in attachment_rows],
        *[_coerce_text(item["happened_at"]) for item in activity_rows],
    ]
    updated_at = max([item for item in updated_candidates if item], default=_now_iso())
    snapshot_id = f"eline_memory_{event_line_id}"
    existing = db.fetchone(
        "SELECT created_at FROM event_line_memory_snapshots WHERE event_line_id = ?",
        (event_line_id,),
    )
    created_at = str(existing["created_at"]) if existing else updated_at
    db.execute(
        """
        INSERT INTO event_line_memory_snapshots(
            id, event_line_id, line_name, current_stage, current_work, current_blocker, recent_decision, next_step,
            evidence_refs_json, clarification_needs_json, analysis_signals_json, prediction_readiness, confidence,
            created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(event_line_id) DO UPDATE SET
            line_name = excluded.line_name,
            current_stage = excluded.current_stage,
            current_work = excluded.current_work,
            current_blocker = excluded.current_blocker,
            recent_decision = excluded.recent_decision,
            next_step = excluded.next_step,
            evidence_refs_json = excluded.evidence_refs_json,
            clarification_needs_json = excluded.clarification_needs_json,
            analysis_signals_json = excluded.analysis_signals_json,
            prediction_readiness = excluded.prediction_readiness,
            confidence = excluded.confidence,
            updated_at = excluded.updated_at
        """,
        (
            snapshot_id,
            event_line_id,
            event_line.name,
            _coerce_text(event_line.stage),
            current_work,
            current_blocker,
            recent_decision,
            next_step,
            to_json(evidence_refs),
            to_json(clarification_needs),
            to_json(_unique(review_signals)[:4]),
            prediction_readiness,
            confidence,
            created_at,
            updated_at,
        ),
    )
    snapshot_row = db.fetchone(
        "SELECT * FROM event_line_memory_snapshots WHERE event_line_id = ?",
        (event_line_id,),
    )
    assert snapshot_row is not None
    return _build_event_line_memory_snapshot(snapshot_row)


def get_client_notebook_response(db: Database, client_id: str) -> ClientNotebookResponse:
    snapshot = refresh_organization_notebook_snapshot(db, client_id)
    linked_event_lines = list_linked_event_lines(db, client_id)
    key_facts = _read_memory_facts(db, "client", client_id, limit=8)
    missing_facts = list(snapshot.informationGaps if snapshot else [])
    return ClientNotebookResponse(
        organizationNotebookSnapshot=snapshot,
        keyFacts=key_facts,
        missingFacts=missing_facts,
        linkedEventLines=linked_event_lines,
    )


def get_event_line_memory_response(db: Database, event_line_id: str) -> EventLineMemoryResponse:
    snapshot = refresh_event_line_memory_snapshot(db, event_line_id)
    return EventLineMemoryResponse(
        eventLineMemorySnapshot=snapshot,
        evidenceRefs=snapshot.evidenceRefs if snapshot else [],
        clarificationNeeds=snapshot.clarificationNeeds if snapshot else [],
    )


def get_client_memory_status(db: Database, client_id: str) -> MemoryStatus:
    snapshot = refresh_organization_notebook_snapshot(db, client_id)
    linked_event_lines = list_linked_event_lines(db, client_id)
    covered = 0
    low_evidence = 0
    for line in linked_event_lines:
        memory = refresh_event_line_memory_snapshot(db, line.id)
        if memory and memory.confidence > 0:
            covered += 1
        if memory and memory.predictionReadiness < 0.55:
            low_evidence += 1
    total = len(linked_event_lines)
    return MemoryStatus(
        clientId=client_id,
        notebookCompleteness=_ratio(
            sum(
                1
                for item in (
                    snapshot.organizationIntro if snapshot else "",
                    snapshot.collaborationRelationship if snapshot else "",
                    snapshot.currentStage if snapshot else "",
                    snapshot.businessModules if snapshot else [],
                    snapshot.collaborationGoals if snapshot else [],
                )
                if item
            ),
            5,
        ),
        notebookConfidence=snapshot.confidence if snapshot else 0.0,
        eventLineCoverage=_ratio(covered, total),
        totalEventLines=total,
        coveredEventLines=covered,
        pendingClarifications=len(_read_clarifications(db, "client", client_id, status="pending")) + sum(
            len(_read_clarifications(db, "event_line", line.id, status="pending")) for line in linked_event_lines
        ),
        lowEvidenceJudgments=low_evidence,
        updatedAt=_now_iso(),
    )


def get_task_memory_enrichment(
    db: Database,
    *,
    task_id: str,
    client_id: str | None,
    event_line_id: str | None,
) -> tuple[list[str], BackgroundReadiness, list[MemoryFact]]:
    normalized_client_id = (client_id or "").strip()
    normalized_event_line_id = (event_line_id or "").strip()

    event_line_snapshot = refresh_event_line_memory_snapshot(db, normalized_event_line_id) if normalized_event_line_id else None
    notebook_snapshot = refresh_organization_notebook_snapshot(db, normalized_client_id) if normalized_client_id else None

    task_facts = _read_memory_facts(db, "task", task_id, limit=8)
    event_line_facts = _read_memory_facts(db, "event_line", normalized_event_line_id, limit=4) if normalized_event_line_id else []
    client_facts = _read_memory_facts(db, "client", normalized_client_id, limit=4) if normalized_client_id else []
    task_reference_facts = [fact for fact in task_facts if fact.factKey.startswith("reference_match:")]
    task_text = " ".join(
        [
            *[
                fact.factValue
                for fact in task_facts
                if fact.factKey in {"title", "description"}
            ],
        ]
    ).strip()
    matched_reference_entries = _match_task_reference_entries(notebook_snapshot, task_text) if notebook_snapshot else []
    reference_tokens = _extract_reference_tokens(task_text)
    notebook_reference_pool = _unique(
        [
            notebook_snapshot.organizationIntro if notebook_snapshot else "",
            notebook_snapshot.collaborationRelationship if notebook_snapshot else "",
            *(notebook_snapshot.businessModules if notebook_snapshot else []),
            *(notebook_snapshot.keyPeople if notebook_snapshot else []),
            *(notebook_snapshot.keyProducts if notebook_snapshot else []),
            *(notebook_snapshot.collaborationGoals if notebook_snapshot else []),
            *(notebook_snapshot.currentChallenges if notebook_snapshot else []),
            *(notebook_snapshot.recentFacts if notebook_snapshot else []),
        ]
    )
    notebook_reference_matches = [
        item
        for item in notebook_reference_pool
        if any(_token_matches_text(token, item) for token in reference_tokens)
    ][:4]
    matched_client_facts = [
        fact
        for fact in client_facts
        if any(_token_matches_text(token, fact.factValue) for token in reference_tokens)
    ][:4]
    matched_event_line_facts = [
        fact
        for fact in event_line_facts
        if any(_token_matches_text(token, fact.factValue) for token in reference_tokens)
    ][:3]
    person_facts = _unique(
        [
            fact.id
            for entry in matched_reference_entries
            if entry["entry_type"] == "person" and normalized_client_id
            for fact in _read_memory_facts(
                db,
                "person",
                _reference_scope_id(normalized_client_id, "person", entry["label"]),
                limit=2,
            )
        ]
    )
    product_facts = _unique(
        [
            fact.id
            for entry in matched_reference_entries
            if entry["entry_type"] == "product" and normalized_client_id
            for fact in _read_memory_facts(
                db,
                "product",
                _reference_scope_id(normalized_client_id, "product", entry["label"]),
                limit=2,
            )
        ]
    )
    person_fact_map = {
        fact.id: fact
        for entry in matched_reference_entries
        if entry["entry_type"] == "person" and normalized_client_id
        for fact in _read_memory_facts(
            db,
            "person",
            _reference_scope_id(normalized_client_id, "person", entry["label"]),
            limit=2,
        )
    }
    product_fact_map = {
        fact.id: fact
        for entry in matched_reference_entries
        if entry["entry_type"] == "product" and normalized_client_id
        for fact in _read_memory_facts(
            db,
            "product",
            _reference_scope_id(normalized_client_id, "product", entry["label"]),
            limit=2,
        )
    }
    matched_tokens = _unique(
        [
            token
            for token in reference_tokens
            if any(
                _token_matches_text(token, item)
                for item in [
                    *notebook_reference_matches,
                    *[fact.factValue for fact in matched_client_facts],
                    *[fact.factValue for fact in matched_event_line_facts],
                    *[fact.factValue for fact in person_fact_map.values()],
                    *[fact.factValue for fact in product_fact_map.values()],
                ]
            )
        ]
    )[:4]

    hints: list[str] = []
    if matched_tokens:
        hints.append(f"命中对象：{' / '.join(matched_tokens)}")
    if person_fact_map:
        hints.append(f"人物背景：{next(iter(person_fact_map.values())).factValue}")
    if product_fact_map:
        hints.append(f"业务背景：{next(iter(product_fact_map.values())).factValue}")
    if task_reference_facts:
        hints.append(f"对象背景：{task_reference_facts[0].factValue}")
    if notebook_reference_matches:
        hints.append(f"关联背景：{notebook_reference_matches[0]}")
    if matched_client_facts:
        hints.append(f"历史事实：{matched_client_facts[0].factValue}")
    if event_line_snapshot:
        if event_line_snapshot.currentWork:
            hints.append(f"事件线当前事项：{event_line_snapshot.currentWork}")
        if event_line_snapshot.currentBlocker:
            hints.append(f"当前阻塞：{event_line_snapshot.currentBlocker}")
        if event_line_snapshot.nextStep:
            hints.append(f"下一步：{event_line_snapshot.nextStep}")
    if not hints and notebook_snapshot:
        if notebook_snapshot.currentStage:
            hints.append(f"组织当前阶段：{notebook_snapshot.currentStage}")
        if notebook_snapshot.collaborationGoals:
            hints.append(f"当前合作目标：{notebook_snapshot.collaborationGoals[0]}")
        if notebook_snapshot.currentChallenges:
            hints.append(f"当前组织困境：{notebook_snapshot.currentChallenges[0]}")
    if not hints and task_facts:
        for fact in task_facts:
            if fact.factKey == "description":
                hints.append(f"任务背景：{fact.factValue}")
            elif fact.factKey == "due_date":
                hints.append(f"关键时间：{fact.factValue}")
            elif fact.factKey == "status":
                hints.append(f"当前状态：{fact.factValue}")
            if len(hints) >= 3:
                break

    missing_slots = _unique(
        [
            *(event_line_snapshot.clarificationNeeds if event_line_snapshot else []),
            *(notebook_snapshot.informationGaps if notebook_snapshot else []),
        ]
    )[:5]
    if missing_slots:
        hints.append(f"待澄清：{missing_slots[0]}")

    background_sources = _unique(
        [
            "organization_notebook" if notebook_snapshot else "",
            "notebook_reference_match" if notebook_reference_matches else "",
            "person_facts" if person_fact_map else "",
            "product_facts" if product_fact_map else "",
            "event_line_memory" if event_line_snapshot else "",
            "task_reference_match" if task_reference_facts else "",
            "task_facts" if task_facts else "",
            "client_facts" if client_facts else "",
            "event_line_facts" if event_line_facts else "",
        ]
    )
    linked_facts = _unique(
        [
            *person_facts,
            *product_facts,
            *[fact.id for fact in task_reference_facts],
            *[fact.id for fact in matched_event_line_facts],
            *[fact.id for fact in matched_client_facts],
            *[fact.id for fact in event_line_facts],
            *[fact.id for fact in client_facts],
            *[fact.id for fact in task_facts],
        ]
    )
    linked_fact_map = {
        fact.id: fact
        for fact in [
            *person_fact_map.values(),
            *product_fact_map.values(),
            *task_reference_facts,
            *matched_event_line_facts,
            *matched_client_facts,
            *event_line_facts,
            *client_facts,
            *task_facts,
        ]
    }
    linked_facts_preview = [linked_fact_map[fact_id] for fact_id in linked_facts if fact_id in linked_fact_map][:6]
    if event_line_snapshot:
        score = max(event_line_snapshot.confidence, event_line_snapshot.predictionReadiness)
    elif notebook_snapshot:
        score = notebook_snapshot.confidence
    elif task_facts:
        score = 0.35
    else:
        score = 0.0
    if task_reference_facts or notebook_reference_matches or matched_client_facts or matched_event_line_facts:
        score = min(1.0, score + 0.12)
    if missing_slots:
        score = max(0.0, score - 0.1)
    level: str = "high" if score >= 0.75 else "medium" if score >= 0.45 else "low"
    readiness = BackgroundReadiness(
        score=round(score, 2),
        level=level,  # type: ignore[arg-type]
        missingSlots=missing_slots,
        backgroundSources=background_sources,
    )
    return hints[:4], readiness, linked_facts_preview


def create_clarification_record(db: Database, payload: ClarificationCreatePayload) -> ClarificationRecord:
    timestamp = _now_iso()
    clarification_id = _new_id("clar")
    db.execute(
        """
        INSERT INTO clarification_records(
            id, scope_type, scope_id, slot_key, question, status, answer_text, write_scope_json,
            resolved_fact_ids_json, reusable, created_at, answered_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, 'pending', NULL, ?, '[]', ?, ?, NULL, ?)
        """,
        (
            clarification_id,
            payload.scopeType,
            payload.scopeId,
            payload.slotKey,
            payload.question.strip(),
            to_json(_unique(payload.writeScope)),
            1 if payload.reusable else 0,
            timestamp,
            timestamp,
        ),
    )
    row = db.fetchone("SELECT * FROM clarification_records WHERE id = ?", (clarification_id,))
    assert row is not None
    return _build_clarification_record(row)


def answer_clarification_record(db: Database, clarification_id: str, payload: ClarificationAnswerPayload) -> ClarificationRecord:
    row = db.fetchone("SELECT * FROM clarification_records WHERE id = ?", (clarification_id,))
    if not row:
        raise KeyError("clarification not found")
    answer_text = _coerce_text(payload.answer)
    if not answer_text:
        raise ValueError("answer cannot be empty")

    scope_type = str(row["scope_type"])
    scope_id = str(row["scope_id"])
    slot_key = str(row["slot_key"])
    source_id = clarification_id
    write_scope = _parse_list(row["write_scope_json"]) or [f"{scope_type}:{scope_id}"]
    context_client_id = _resolve_client_id_for_memory_scope(db, scope_type, scope_id)
    if context_client_id:
        notebook_snapshot = refresh_organization_notebook_snapshot(db, context_client_id)
        for entry in _match_task_reference_entries(notebook_snapshot, answer_text):
            if entry["entry_type"] not in {"person", "product"}:
                continue
            write_scope.append(
                f"{entry['entry_type']}:{_reference_scope_id(context_client_id, entry['entry_type'], entry['label'])}"
            )
    write_scope = _unique(write_scope)
    segments = _unique(
        [
            part.strip()
            for raw in answer_text.splitlines()
            for part in [item.strip() for item in raw.replace("；", "。").replace(";", "。").split("。")]
            if part.strip()
        ]
    )[:6]
    if not segments:
        segments = [answer_text]

    fact_ids: list[str] = []
    for target in write_scope:
        target_scope_type, _, target_scope_id = target.partition(":")
        normalized_scope_type = target_scope_type.strip() or scope_type
        normalized_scope_id = target_scope_id.strip() or scope_id
        for index, segment in enumerate(segments, start=1):
            fact = upsert_memory_fact(
                db,
                scope_type=normalized_scope_type,
                scope_id=normalized_scope_id,
                fact_key=slot_key if len(segments) == 1 else f"{slot_key}_{index}",
                fact_value=segment,
                source_type="clarification",
                source_id=f"{source_id}:{normalized_scope_type}:{normalized_scope_id}:{index}",
                confidence=0.82,
                freshness=1.0,
                evidence_refs=[f"clarification:{clarification_id}"],
            )
            fact_ids.append(fact.id)
        if normalized_scope_type == "client":
            refresh_organization_notebook_snapshot(db, normalized_scope_id)
        elif normalized_scope_type == "event_line":
            refresh_event_line_memory_snapshot(db, normalized_scope_id)

    timestamp = _now_iso()
    db.execute(
        """
        UPDATE clarification_records
        SET status = 'answered',
            answer_text = ?,
            resolved_fact_ids_json = ?,
            answered_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (answer_text, to_json(fact_ids), timestamp, timestamp, clarification_id),
    )
    updated_row = db.fetchone("SELECT * FROM clarification_records WHERE id = ?", (clarification_id,))
    assert updated_row is not None
    return _build_clarification_record(updated_row)


def record_client_dna_writeback(
    db: Database,
    *,
    client_id: str,
    module_key: str,
    summary: str,
    file_name: str | None,
    source_kind: str,
    missing_info: list[str] | None = None,
) -> None:
    if summary.strip():
        upsert_memory_fact(
            db,
            scope_type="client",
            scope_id=client_id,
            fact_key=f"dna_module:{module_key}:summary",
            fact_value=summary,
            source_type="client_dna",
            source_id=f"{client_id}:{module_key}",
            confidence=0.88 if source_kind == "manual" else 0.72,
            freshness=0.95,
            evidence_refs=[item for item in [file_name, f"client_dna:{module_key}"] if item],
        )
    for index, item in enumerate(_unique(missing_info or []), start=1):
        upsert_memory_fact(
            db,
            scope_type="client",
            scope_id=client_id,
            fact_key=f"dna_module:{module_key}:missing_{index}",
            fact_value=item,
            source_type="client_dna",
            source_id=f"{client_id}:{module_key}:missing:{index}",
            confidence=0.6,
            freshness=0.9,
            evidence_refs=[f"client_dna:{module_key}"],
        )
    refresh_organization_notebook_snapshot(db, client_id)


def record_imported_document_writeback(
    db: Database,
    *,
    client_id: str,
    document_id: str,
    title: str,
    prepared: dict[str, object],
) -> None:
    summary = _coerce_text(prepared.get("summary"))
    category = _coerce_text(prepared.get("primary_category")) or "其他资料"
    material_layer = _coerce_text(prepared.get("material_layer")) or "evidence"
    confidence = float(prepared.get("classification_confidence") or 0.0)
    needs_review = bool(prepared.get("needs_review"))
    if not summary or needs_review or confidence < 0.55:
        refresh_organization_notebook_snapshot(db, client_id)
        return
    upsert_memory_fact(
        db,
        scope_type="client",
        scope_id=client_id,
        fact_key=f"document_summary:{document_id}",
        fact_value=f"{_coerce_text(title)}｜{category}｜{summary[:180]}",
        source_type="document",
        source_id=document_id,
        confidence=min(max(confidence, 0.55), 0.9),
        freshness=0.82,
        evidence_refs=[f"document:{title}", f"document:{document_id}", f"layer:{material_layer}"],
    )
    refresh_organization_notebook_snapshot(db, client_id)


def record_task_writeback(
    db: Database,
    *,
    task_id: str,
    title: str,
    description: str,
    status: str,
    due_date: str | None,
    client_id: str | None,
    event_line_id: str | None,
) -> None:
    normalized_title = _coerce_text(title)
    normalized_description = _coerce_text(description)
    task_text = " ".join(part for part in (normalized_title, normalized_description) if part).strip()
    upsert_memory_fact(
        db,
        scope_type="task",
        scope_id=task_id,
        fact_key="title",
        fact_value=normalized_title,
        source_type="task",
        source_id=task_id,
        confidence=0.95,
        freshness=1.0,
        evidence_refs=[f"task:{task_id}"],
    )
    if normalized_description:
        upsert_memory_fact(
            db,
            scope_type="task",
            scope_id=task_id,
            fact_key="description",
            fact_value=normalized_description,
            source_type="task",
            source_id=task_id,
            confidence=0.78,
            freshness=1.0,
            evidence_refs=[f"task:{task_id}"],
        )
    upsert_memory_fact(
        db,
        scope_type="task",
        scope_id=task_id,
        fact_key="status",
        fact_value=status,
        source_type="task",
        source_id=task_id,
        confidence=0.98,
        freshness=1.0,
        evidence_refs=[f"task:{task_id}"],
    )
    if due_date:
        upsert_memory_fact(
            db,
            scope_type="task",
            scope_id=task_id,
            fact_key="due_date",
            fact_value=due_date,
            source_type="task",
            source_id=task_id,
            confidence=0.98,
            freshness=1.0,
            evidence_refs=[f"task:{task_id}"],
        )
    if client_id:
        upsert_memory_fact(
            db,
            scope_type="client",
            scope_id=client_id,
            fact_key=f"task_signal:{task_id}",
            fact_value=f"{normalized_title}｜状态：{status}",
            source_type="task",
            source_id=task_id,
            confidence=0.66,
            freshness=0.92,
            evidence_refs=[f"task:{task_id}"],
        )
        notebook_snapshot = refresh_organization_notebook_snapshot(db, client_id)
        for entry in _match_task_reference_entries(notebook_snapshot, task_text):
            label = entry["label"]
            upsert_memory_fact(
                db,
                scope_type="task",
                scope_id=task_id,
                fact_key=f"reference_match:{entry['entry_type']}:{_slugify_fact_key_part(label)}",
                fact_value=entry["background"],
                source_type="organization_notebook",
                source_id=client_id,
                confidence=0.76,
                freshness=0.95,
                evidence_refs=[f"task:{task_id}", f"notebook:{client_id}"],
            )
    if event_line_id:
        upsert_memory_fact(
            db,
            scope_type="event_line",
            scope_id=event_line_id,
            fact_key=f"task_signal:{task_id}",
            fact_value=f"{normalized_title}｜状态：{status}",
            source_type="task",
            source_id=task_id,
            confidence=0.7,
            freshness=0.95,
            evidence_refs=[f"task:{task_id}"],
        )
        refresh_event_line_memory_snapshot(db, event_line_id)


def record_meeting_publish_writeback(
    db: Database,
    *,
    client_id: str,
    meeting_id: str,
    meeting_title: str,
    event_line_ids: list[str] | None = None,
) -> None:
    normalized_event_line_ids = _unique(event_line_ids or [])
    decision_rows = db.fetchall(
        "SELECT summary FROM decisions WHERE meeting_id = ? ORDER BY created_at ASC",
        (meeting_id,),
    )
    risk_rows = db.fetchall(
        "SELECT summary, severity FROM risks WHERE meeting_id = ? ORDER BY created_at ASC",
        (meeting_id,),
    )
    action_rows = db.fetchall(
        "SELECT title, owner_name FROM action_items WHERE meeting_id = ? ORDER BY created_at ASC",
        (meeting_id,),
    )
    for index, row in enumerate(decision_rows, start=1):
        decision_text = _coerce_text(row["summary"])
        upsert_memory_fact(
            db,
            scope_type="client",
            scope_id=client_id,
            fact_key=f"meeting_decision:{index}",
            fact_value=decision_text,
            source_type="meeting",
            source_id=f"{meeting_id}:decision:{index}",
            confidence=0.82,
            freshness=0.96,
            evidence_refs=[f"meeting:{meeting_title}", f"meeting:{meeting_id}"],
        )
        for event_line_id in normalized_event_line_ids:
            upsert_memory_fact(
                db,
                scope_type="event_line",
                scope_id=event_line_id,
                fact_key=f"meeting_decision:{index}",
                fact_value=decision_text,
                source_type="meeting",
                source_id=f"{meeting_id}:decision:{index}",
                confidence=0.78,
                freshness=0.96,
                evidence_refs=[f"meeting:{meeting_title}", f"meeting:{meeting_id}"],
            )
    for index, row in enumerate(risk_rows, start=1):
        risk_text = f"{_coerce_text(row['summary'])}｜等级：{_coerce_text(row['severity']) or 'normal'}"
        upsert_memory_fact(
            db,
            scope_type="client",
            scope_id=client_id,
            fact_key=f"meeting_risk:{index}",
            fact_value=risk_text,
            source_type="meeting",
            source_id=f"{meeting_id}:risk:{index}",
            confidence=0.75,
            freshness=0.96,
            evidence_refs=[f"meeting:{meeting_title}", f"meeting:{meeting_id}"],
        )
        for event_line_id in normalized_event_line_ids:
            upsert_memory_fact(
                db,
                scope_type="event_line",
                scope_id=event_line_id,
                fact_key=f"meeting_risk:{index}",
                fact_value=risk_text,
                source_type="meeting",
                source_id=f"{meeting_id}:risk:{index}",
                confidence=0.72,
                freshness=0.96,
                evidence_refs=[f"meeting:{meeting_title}", f"meeting:{meeting_id}"],
            )
    for index, row in enumerate(action_rows, start=1):
        owner_name = _coerce_text(row["owner_name"])
        value = _coerce_text(row["title"])
        if owner_name:
            value = f"{value}｜负责人：{owner_name}"
        upsert_memory_fact(
            db,
            scope_type="client",
            scope_id=client_id,
            fact_key=f"meeting_action:{index}",
            fact_value=value,
            source_type="meeting",
            source_id=f"{meeting_id}:action:{index}",
            confidence=0.8,
            freshness=0.96,
            evidence_refs=[f"meeting:{meeting_title}", f"meeting:{meeting_id}"],
        )
        for event_line_id in normalized_event_line_ids:
            upsert_memory_fact(
                db,
                scope_type="event_line",
                scope_id=event_line_id,
                fact_key=f"meeting_action:{index}",
                fact_value=value,
                source_type="meeting",
                source_id=f"{meeting_id}:action:{index}",
                confidence=0.76,
                freshness=0.96,
                evidence_refs=[f"meeting:{meeting_title}", f"meeting:{meeting_id}"],
            )
    refresh_organization_notebook_snapshot(db, client_id)
    for event_line_id in normalized_event_line_ids:
        refresh_event_line_memory_snapshot(db, event_line_id)


def record_task_attachment_writeback(
    db: Database,
    *,
    task_id: str,
    client_id: str,
    event_line_id: str | None,
    attachment_title: str,
    attachment_path: str,
) -> None:
    upsert_memory_fact(
        db,
        scope_type="task",
        scope_id=task_id,
        fact_key=f"attachment:{attachment_title}",
        fact_value=attachment_title,
        source_type="task_attachment",
        source_id=f"{task_id}:{attachment_title}",
        confidence=0.92,
        freshness=1.0,
        evidence_refs=[attachment_path],
    )
    if client_id:
        upsert_memory_fact(
            db,
            scope_type="client",
            scope_id=client_id,
            fact_key=f"attachment_signal:{task_id}:{attachment_title}",
            fact_value=f"{attachment_title} 已进入项目资料层",
            source_type="task_attachment",
            source_id=f"{task_id}:{attachment_title}",
            confidence=0.62,
            freshness=1.0,
            evidence_refs=[attachment_path],
        )
        refresh_organization_notebook_snapshot(db, client_id)
    if event_line_id:
        upsert_memory_fact(
            db,
            scope_type="event_line",
            scope_id=event_line_id,
            fact_key=f"attachment_signal:{task_id}:{attachment_title}",
            fact_value=f"{attachment_title} 已作为事件线证据加入",
            source_type="task_attachment",
            source_id=f"{task_id}:{attachment_title}",
            confidence=0.76,
            freshness=1.0,
            evidence_refs=[attachment_path],
        )
        refresh_event_line_memory_snapshot(db, event_line_id)


def record_weekly_review_writeback(db: Database, *, review_id: str) -> None:
    rows = db.fetchall(
        """
        SELECT task_snapshot_json, note
        FROM weekly_review_task_entries
        WHERE review_id = ?
        ORDER BY updated_at DESC
        """,
        (review_id,),
    )
    touched_clients: set[str] = set()
    touched_event_lines: set[str] = set()
    for index, row in enumerate(rows, start=1):
        snapshot = from_json(row["task_snapshot_json"], {})
        if not isinstance(snapshot, dict):
            continue
        note = _coerce_text(row["note"])
        if not note:
            continue
        event_line_id = _coerce_text(snapshot.get("eventLineId"))
        client_id = _coerce_text(snapshot.get("clientId"))
        if event_line_id:
            touched_event_lines.add(event_line_id)
            upsert_memory_fact(
                db,
                scope_type="event_line",
                scope_id=event_line_id,
                fact_key=f"weekly_review_signal:{index}",
                fact_value=note,
                source_type="weekly_review",
                source_id=f"{review_id}:event_line:{index}",
                confidence=0.68,
                freshness=0.88,
                evidence_refs=[f"weekly_review:{review_id}"],
            )
        if client_id:
            touched_clients.add(client_id)
            upsert_memory_fact(
                db,
                scope_type="client",
                scope_id=client_id,
                fact_key=f"weekly_review_signal:{index}",
                fact_value=note,
                source_type="weekly_review",
                source_id=f"{review_id}:client:{index}",
                confidence=0.58,
                freshness=0.88,
                evidence_refs=[f"weekly_review:{review_id}"],
            )
    for client_id in touched_clients:
        refresh_organization_notebook_snapshot(db, client_id)
    for event_line_id in touched_event_lines:
        refresh_event_line_memory_snapshot(db, event_line_id)


def backfill_memory_foundation(
    db: Database,
    *,
    task_ids: list[str] | None = None,
    review_ids: list[str] | None = None,
    client_ids: list[str] | None = None,
    event_line_ids: list[str] | None = None,
) -> MemoryBackfillResultRecord:
    normalized_task_ids = _unique(task_ids or [])
    normalized_review_ids = _unique(review_ids or [])
    normalized_client_ids = _unique(client_ids or [])
    normalized_event_line_ids = _unique(event_line_ids or [])

    if normalized_task_ids:
        task_rows = [
            row
            for task_id in normalized_task_ids
            if (row := db.fetchone("SELECT * FROM tasks WHERE id = ?", (task_id,))) is not None
        ]
    else:
        task_rows = db.fetchall("SELECT * FROM tasks ORDER BY updated_at DESC")

    if normalized_review_ids:
        review_rows = [
            row
            for review_id in normalized_review_ids
            if (row := db.fetchone("SELECT id FROM weekly_reviews WHERE id = ?", (review_id,))) is not None
        ]
    else:
        review_rows = db.fetchall("SELECT id FROM weekly_reviews ORDER BY updated_at DESC")

    touched_task_ids = [str(row["id"]) for row in task_rows]
    if touched_task_ids:
        placeholders = ",".join("?" for _ in touched_task_ids)
        attachment_rows = db.fetchall(
            f"SELECT * FROM task_attachments WHERE task_id IN ({placeholders}) ORDER BY created_at DESC",
            tuple(touched_task_ids),
        )
    else:
        attachment_rows = db.fetchall("SELECT * FROM task_attachments ORDER BY created_at DESC")

    derived_client_ids = _unique(
        [
            *normalized_client_ids,
            *[str(row["client_id"]) for row in task_rows if row["client_id"]],
            *[str(row["client_id"]) for row in attachment_rows if row["client_id"]],
            *[
                str(client_id)
                for review_row in review_rows
                for entry_row in db.fetchall(
                    "SELECT task_snapshot_json FROM weekly_review_task_entries WHERE review_id = ? ORDER BY updated_at DESC",
                    (str(review_row["id"]),),
                )
                if isinstance(snapshot := from_json(entry_row["task_snapshot_json"], {}), dict)
                for client_id in [snapshot.get("clientId")]
                if str(client_id or "").strip()
            ],
        ]
    )
    derived_event_line_ids = _unique(
        [
            *normalized_event_line_ids,
            *[str(row["event_line_id"]) for row in task_rows if row["event_line_id"]],
            *[str(row["event_line_id"]) for row in attachment_rows if row["event_line_id"]],
            *[
                str(event_line_id)
                for review_row in review_rows
                for entry_row in db.fetchall(
                    "SELECT task_snapshot_json FROM weekly_review_task_entries WHERE review_id = ? ORDER BY updated_at DESC",
                    (str(review_row["id"]),),
                )
                if isinstance(snapshot := from_json(entry_row["task_snapshot_json"], {}), dict)
                for event_line_id in [snapshot.get("eventLineId")]
                if str(event_line_id or "").strip()
            ],
        ]
    )

    task_fact_count = 0
    for row in task_rows:
        record_task_writeback(
            db,
            task_id=str(row["id"]),
            title=_coerce_text(row["title"]),
            description=_coerce_text(row["description"]),
            status=_coerce_text(row["status"]) or "todo",
            due_date=_coerce_text(row["due_date"]) or None,
            client_id=_coerce_text(row["client_id"]) or None,
            event_line_id=_coerce_text(row["event_line_id"]) or None,
        )
        task_fact_count += 1

    attachment_fact_count = 0
    for row in attachment_rows:
        record_task_attachment_writeback(
            db,
            task_id=str(row["task_id"]),
            client_id=_coerce_text(row["client_id"]),
            event_line_id=_coerce_text(row["event_line_id"]) or None,
            attachment_title=_coerce_text(row["title"]),
            attachment_path=_coerce_text(row["path"]),
        )
        attachment_fact_count += 1

    review_signal_count = 0
    for row in review_rows:
        review_id = str(row["id"])
        record_weekly_review_writeback(db, review_id=review_id)
        review_signal_count += 1

    notebooks_refreshed = 0
    for client_id in derived_client_ids:
        if refresh_organization_notebook_snapshot(db, client_id):
            notebooks_refreshed += 1

    event_line_snapshots_refreshed = 0
    for event_line_id in derived_event_line_ids:
        if refresh_event_line_memory_snapshot(db, event_line_id):
            event_line_snapshots_refreshed += 1

    return MemoryBackfillResultRecord(
        totalTasks=len(task_rows),
        taskFactsBackfilled=task_fact_count,
        totalAttachments=len(attachment_rows),
        attachmentFactsBackfilled=attachment_fact_count,
        totalReviews=len(review_rows),
        reviewSignalsBackfilled=review_signal_count,
        totalClients=len(derived_client_ids),
        notebooksRefreshed=notebooks_refreshed,
        totalEventLines=len(derived_event_line_ids),
        eventLineSnapshotsRefreshed=event_line_snapshots_refreshed,
        updatedAt=_now_iso(),
    )
