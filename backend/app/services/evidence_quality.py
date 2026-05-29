from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.models import EvidenceItem, EvidenceQualitySignalRecord
from app.services.freshness_decay import (
    NEUTRAL_WHEN_UNKNOWN,
    compute_time_decay,
)
from app.services.source_semantics import infer_semantic_source_roles_fields


_NOISE_HINTS = (
    "clicktoeditmaster",
    "母版",
    "模板",
    "模板页",
    "目录页",
    "封面",
    "页脚",
    "页码",
    "图标",
    "视觉",
    "背景图",
    "ppt母版",
)
_PPT_METADATA_HINTS = (
    "wps演示",
    "已用的字体",
    "幻灯片标题",
    "主题1",
    "主题 1",
    "arial",
    "thonburi",
    "yuanti",
    "pingfang",
    "produkt",
)
_TEXT_FILE_NOISE_HINTS = (
    "说明.txt",
    "整理说明",
    "重复件已移至废纸篓",
)
_GENERATED_HINTS = ("answer_", "chat_", "历史回答", "生成稿", "草稿")
_BUSINESS_STRATEGY_HINTS = (
    "业务",
    "服务",
    "产品",
    "项目",
    "战略",
    "目标",
    "计划",
    "方向",
)
def _norm(value: str | None) -> str:
    return re.sub(r"\s+", "", str(value or "").lower())


def _parse_year_from_text(text: str) -> int | None:
    match = re.search(r"(20\d{2})", text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except Exception:
        return None


def classify_evidence_quality_fields(
    *,
    title: str = "",
    excerpt: str = "",
    source_type: str = "",
    section_label: str = "",
    retrieval_stage: str = "",
    path: str = "",
    created_at: str | None = None,
    doc_type: str | None = None,
) -> EvidenceQualitySignalRecord:
    merged = _norm(f"{title} {section_label} {excerpt} {path}")
    source_type_norm = _norm(source_type)
    retrieval_stage_norm = _norm(retrieval_stage)

    noise_reasons: list[str] = []
    demotion = 0.0
    score = 0.5
    authority_hint = "unknown"
    source_kind = "unknown"
    semantic_roles, role_reasons = infer_semantic_source_roles_fields(
        title=title,
        excerpt=excerpt,
        source_type=source_type,
        section_label=section_label,
        retrieval_stage=retrieval_stage,
        path=path,
    )

    if source_type_norm in {"generated", "aidraft", "draft", "generated_answer", "ai_draft"}:
        source_kind = "generated_answer"
        noise_reasons.append("generated_draft")
        demotion += 0.4
        authority_hint = "generated"
    elif source_type_norm in {"memory", "memorynote", "memoryfact", "memory_answer"}:
        source_kind = "memory_answer"
        noise_reasons.append("memory_answer")
        demotion += 0.4
        authority_hint = "generated"
    elif source_type_norm in {"official_judgment", "candidate_judgment", "judgment"}:
        source_kind = "judgment"
        authority_hint = "state" if "official" in source_type_norm else "candidate"
    elif source_type_norm in {"topic_candidate", "topic"}:
        source_kind = "topic_candidate"
        authority_hint = "candidate"
    elif "meeting" in source_type_norm or "纪要" in merged:
        if any(token in merged for token in ("决定", "决议")):
            source_kind = "meeting_decision"
        elif any(token in merged for token in ("行动项", "负责人", "due", "截止")):
            source_kind = "meeting_action"
        elif any(token in merged for token in ("风险", "卡点", "挑战")):
            source_kind = "meeting_risk"
        else:
            source_kind = "meeting_note"
        authority_hint = "state"
    elif "task" in source_type_norm:
        source_kind = "task_attachment"
        authority_hint = "state"

    if any(token in merged for token in _NOISE_HINTS):
        if "母版" in merged or "clicktoeditmaster" in merged:
            source_kind = "ppt_master"
            noise_reasons.append("ppt_master")
        elif any(token in merged for token in ("模板", "模板页", "目录页", "封面")):
            source_kind = "template_page"
            noise_reasons.append("template_page")
        else:
            source_kind = "ppt_visual"
            noise_reasons.append("ppt_visual")
        demotion += 0.5
    if any(token in merged for token in _PPT_METADATA_HINTS):
        source_kind = "ppt_master"
        noise_reasons.append("ppt_metadata")
        demotion += 0.8
    if any(token in merged for token in _TEXT_FILE_NOISE_HINTS):
        source_kind = "template_page"
        noise_reasons.append("text_file_noise")
        demotion += 0.8

    excerpt_text = str(excerpt or "").strip()
    if len(excerpt_text) < 30:
        if source_kind == "unknown":
            source_kind = "short_excerpt"
        noise_reasons.append("short_excerpt")
        demotion += 0.2

    if any(token in merged for token in _GENERATED_HINTS):
        noise_reasons.append("generated_path_hint")
        demotion += 0.3

    if retrieval_stage_norm == "raw_chunk":
        score += 0.25
        authority_hint = "raw"
        if source_kind == "unknown":
            source_kind = "raw_document"
    if section_label:
        score += 0.08
    if any(token in merged for token in _BUSINESS_STRATEGY_HINTS):
        score += 0.05

    if source_kind in {"meeting_note", "meeting_decision", "meeting_action", "meeting_risk", "task_attachment"} and authority_hint == "unknown":
        authority_hint = "state"
    if source_kind == "judgment" and authority_hint == "unknown":
        authority_hint = "state"

    # 迭代 1（鲜度衰减）：
    # 优先用 created_at + doc_type 做指数时间衰减；没有 created_at 才降级到
    # 旧的"从 title/excerpt 抓 4 位年份做线性衰减"启发式。这是为了保留对
    # 不带显式 createdAt 的老构造点的可读性，同时让新主路径走精确时间衰减。
    if created_at:
        # 上下文里有真实创建时间，doc_type 作为分类提示（None → default 90 天）。
        freshness = compute_time_decay(created_at, doc_type)
    else:
        year = _parse_year_from_text(str(title or "") + " " + str(excerpt or ""))
        if year:
            current_year = datetime.now().year
            # 线性 fallback 保持向后兼容
            freshness = max(0.0, min(1.0, 1.0 - (current_year - year) * 0.2))
        else:
            # 不再硬编码 0.2（等同"4 年前"的强烈降权）——用中性值
            freshness = NEUTRAL_WHEN_UNKNOWN

    quality_score = max(-2.0, min(3.0, score - demotion + freshness))
    return EvidenceQualitySignalRecord(
        isNoise=demotion >= 0.5,
        noiseReasons=list(dict.fromkeys(noise_reasons)),
        sourceKind=source_kind if source_kind in {
            "raw_document",
            "meeting_note",
            "meeting_decision",
            "meeting_action",
            "meeting_risk",
            "task_attachment",
            "judgment",
            "topic_candidate",
            "generated_answer",
            "memory_answer",
            "ppt_visual",
            "ppt_master",
            "template_page",
            "short_excerpt",
            "unknown",
        } else "unknown",
        qualityScore=round(quality_score, 4),
        demotionScore=round(demotion, 4),
        freshnessScore=round(freshness, 4),
        authorityHint=authority_hint if authority_hint in {"raw", "state", "candidate", "generated", "unknown"} else "unknown",
        semanticRoles=semantic_roles,
        roleReasons=role_reasons,
    )


def classify_evidence_quality(item: EvidenceItem) -> EvidenceQualitySignalRecord:
    return classify_evidence_quality_fields(
        title=item.title,
        excerpt=item.excerpt,
        source_type=item.sourceType,
        section_label=item.sectionLabel or "",
        retrieval_stage=item.retrievalStage or "",
        path=item.path or "",
        created_at=item.createdAt,
        doc_type=item.docType,
    )


def classify_evidence_quality_payload(payload: dict[str, Any]) -> EvidenceQualitySignalRecord:
    return classify_evidence_quality_fields(
        title=str(payload.get("title") or ""),
        excerpt=str(payload.get("excerpt") or ""),
        source_type=str(payload.get("sourceType") or payload.get("source_type") or ""),
        section_label=str(payload.get("sectionLabel") or payload.get("section_label") or ""),
        retrieval_stage=str(payload.get("retrievalStage") or payload.get("sourceStage") or payload.get("source_stage") or ""),
        path=str(payload.get("path") or ""),
        created_at=(payload.get("createdAt") or payload.get("created_at")) or None,
        doc_type=(payload.get("docType") or payload.get("doc_type")) or None,
    )
