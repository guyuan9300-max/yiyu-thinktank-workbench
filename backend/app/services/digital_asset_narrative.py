from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any
from uuid import uuid4

from app.db import Database, from_json, to_json
from app.models import DigitalAssetClientDetailRecord, DigitalAssetNarrativeRecord
from app.services.digital_asset_center import build_client_digital_assets


NOISE_PATTERN = re.compile(
    r"(报销|发票|收据|测试|冒烟|烟测|test_|offline_upload|待补充客户简介|安装态|\.jpeg)",
    re.IGNORECASE,
)
PROMPT_LIKE_PATTERN = re.compile(
    r"(你将作为|请严格按|目标读者|YAML front matter|filecite|本次候选稿因 AI 结构化超时|降级为资料拼接稿)",
    re.IGNORECASE,
)
PRIORITY_SIGNAL_KEYWORDS = (
    "战略",
    "使命",
    "愿景",
    "定位",
    "阶段",
    "判断",
    "复盘",
    "会议纪要",
    "事件线",
    "项目设计",
    "负责人",
    "风险",
    "目标",
    "合作",
    "传播",
    "成效",
    "反馈",
    "对象",
    "流程",
    "数据",
    "看板",
    "第二曲线",
)
SEVERE_CONTENT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("包含未经证实的百分比", re.compile(r"\d{1,3}\s*%")),
    ("包含准确率/正确率承诺", re.compile(r"(准确率|正确率)")),
    ("包含降本或商业增长话术", re.compile(r"(降本|获客|商业化|盈利|变现|商业增长)")),
    ("包含绝对化判断", re.compile(r"(一定会|绝对|必然|肯定会)")),
    ("把规划写成已完成", re.compile(r"(已经完全|已经全面|成熟闭环|成熟的数据闭环|已形成成熟)")),
    ("使用被要求避免的固定表达", re.compile(r"长期来看")),
    ("把资料数量简单相加为有效资料数", re.compile(r"有效资料\s*\d+")),
)
STYLE_WARNING_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("仍有偏系统化术语：底座", re.compile(r"底座")),
    ("仍有偏系统化术语：补齐", re.compile(r"补齐")),
    ("仍有偏系统化术语：验证表", re.compile(r"验证表")),
    ("仍有评分化表达：资产完成度", re.compile(r"资产完成度")),
)


class DigitalAssetNarrativeQualityError(RuntimeError):
    pass


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _trim(value: object, limit: int = 600) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def _hash_payload(payload: object) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _safe_count(db: Database, query: str, params: tuple[object, ...]) -> int:
    try:
        return int(db.scalar(query, params))
    except Exception:
        return 0


def _safe_rows(db: Database, query: str, params: tuple[object, ...]) -> list[dict[str, Any]]:
    try:
        return [dict(row) for row in db.fetchall(query, params)]
    except Exception:
        return []


CLIENT_TASK_WHERE = """
FROM tasks t
LEFT JOIN event_lines e ON t.event_line_id = e.id
WHERE (e.primary_client_id = ? OR (t.source_type = 'client' AND t.source_id = ?))
  AND COALESCE(t.scope_mode, 'COLLAB_SHARED') != 'PERSONAL_ONLY'
"""


def _normalize_title_key(title: str) -> str:
    value = title.lower()
    value = re.sub(r"\([^)]*\)", "", value)
    value = re.sub(r"_dup\d*|__dup\d*", "", value)
    value = re.sub(r"[_-]?\d{8,14}", "", value)
    value = re.sub(r"整理版\d*", "整理版", value)
    value = re.sub(r"\s+", "", value)
    return value


def _content_is_prompt_like(*parts: object) -> bool:
    return bool(PROMPT_LIKE_PATTERN.search(" ".join(str(part or "") for part in parts)))


def _content_is_noise(*parts: object) -> bool:
    return bool(NOISE_PATTERN.search(" ".join(str(part or "") for part in parts)))


def _build_selected_materials(db: Database, client_id: str) -> tuple[list[dict[str, object]], int]:
    rows = _safe_rows(
        db,
        """
        SELECT file_name, material_layer, visible_category, secondary_category, parse_status,
               COALESCE(NULLIF(markdown_content,''), NULLIF(preview_text,''), NULLIF(doc_index_text,''), '') AS content,
               updated_at
        FROM v2_documents
        WHERE client_id = ?
        """,
        (client_id,),
    )
    selected: list[dict[str, object]] = []
    seen: set[str] = set()
    duplicate_count = 0
    for row in rows:
        title = str(row.get("file_name") or "")
        content = str(row.get("content") or "")
        if _content_is_noise(title, content) or _content_is_prompt_like(title, content):
            continue
        key = _normalize_title_key(title)
        if key in seen:
            duplicate_count += 1
            continue
        seen.add(key)
        score = 0
        parse_status = str(row.get("parse_status") or "")
        if parse_status == "ready":
            score += 60
        elif parse_status == "partial_ready":
            score += 35
        else:
            score -= 40
        if row.get("secondary_category") == "核心资料":
            score += 35
        if row.get("visible_category") in {"组织与战略", "项目与业务", "品牌与传播", "事件线资料"}:
            score += 20
        hits = [keyword for keyword in PRIORITY_SIGNAL_KEYWORDS if keyword in f"{title} {content}"]
        score += min(len(hits), 4) * 18
        selected.append(
            {
                "score": score,
                "title": title,
                "category": str(row.get("visible_category") or ""),
                "secondary": str(row.get("secondary_category") or ""),
                "parseStatus": parse_status,
                "keywordHits": hits[:5],
                "excerpt": _trim(content, 620),
                "updatedAt": str(row.get("updated_at") or ""),
            }
        )
    selected.sort(key=lambda item: int(item.get("score") or 0), reverse=True)
    return selected[:12], duplicate_count


def _build_quality_warnings(
    *,
    counts: dict[str, int],
    noise_counts: dict[str, int],
    duplicate_count: int,
    dna_documents: list[dict[str, object]],
    digital_asset_summary: dict[str, object],
) -> list[str]:
    warnings: list[str] = []
    total_noise = sum(noise_counts.values())
    if total_noise:
        warnings.append(f"检测到 {total_noise} 条报销、测试、空简介或附件类噪音，生成时需要排除。")
    if duplicate_count:
        warnings.append(f"检测到 {duplicate_count} 条疑似重复资料，已在高优先级材料中去重。")
    prompt_like_dna = [str(item.get("title") or item.get("moduleKey") or "DNA") for item in dna_documents if _content_is_prompt_like(item.get("summary"), item.get("text"))]
    if prompt_like_dna:
        warnings.append(f"{'、'.join(prompt_like_dna[:3])} 含旧提示词或拼接稿，只能作为弱线索。")
    if counts.get("v2Failed", 0):
        warnings.append(f"有 {counts['v2Failed']} 份结构化文档解析失败，不应作为高置信依据。")
    if str(digital_asset_summary.get("assetStage") or "") and int(digital_asset_summary.get("stageProgress") or 0) == 0:
        warnings.append("当前阶段和进度条存在冲突：页面应避免直接把 0% 当成成熟度判断。")
    return warnings


def build_digital_asset_narrative_context(
    db: Database,
    client_id: str,
    detail: DigitalAssetClientDetailRecord | None = None,
) -> dict[str, object]:
    client_row = db.fetchone("SELECT id, name, stage, intro FROM clients WHERE id = ?", (client_id,))
    if client_row is None:
        raise ValueError("Client not found")
    detail = detail or build_client_digital_assets(db, client_id)
    counts = {
        "documents": _safe_count(db, "SELECT COUNT(1) AS count FROM documents WHERE client_id = ?", (client_id,)),
        "v2Documents": _safe_count(db, "SELECT COUNT(1) AS count FROM v2_documents WHERE client_id = ?", (client_id,)),
        "v2Ready": _safe_count(db, "SELECT COUNT(1) AS count FROM v2_documents WHERE client_id = ? AND parse_status = 'ready'", (client_id,)),
        "v2PartialReady": _safe_count(db, "SELECT COUNT(1) AS count FROM v2_documents WHERE client_id = ? AND parse_status = 'partial_ready'", (client_id,)),
        "v2Failed": _safe_count(db, "SELECT COUNT(1) AS count FROM v2_documents WHERE client_id = ? AND parse_status = 'failed'", (client_id,)),
        "dnaDocuments": _safe_count(db, "SELECT COUNT(1) AS count FROM client_dna_documents WHERE client_id = ?", (client_id,)),
        "eventLines": _safe_count(db, "SELECT COUNT(1) AS count FROM event_lines WHERE primary_client_id = ?", (client_id,)),
        "meetings": _safe_count(db, "SELECT COUNT(1) AS count FROM meetings WHERE client_id = ?", (client_id,)),
        "tasks": _safe_count(db, "SELECT COUNT(1) AS count " + CLIENT_TASK_WHERE, (client_id, client_id)),
        "evidenceCards": _safe_count(db, "SELECT COUNT(1) AS count FROM evidence_cards WHERE client_id = ?", (client_id,)),
        "themeClusters": _safe_count(db, "SELECT COUNT(1) AS count FROM theme_clusters WHERE client_id = ?", (client_id,)),
        "openQuestions": _safe_count(db, "SELECT COUNT(1) AS count FROM open_questions WHERE client_id = ?", (client_id,)),
        "judgmentVersions": _safe_count(db, "SELECT COUNT(1) AS count FROM judgment_versions WHERE client_id = ?", (client_id,)),
        "clientAnalysisRuns": _safe_count(db, "SELECT COUNT(1) AS count FROM client_analysis_runs WHERE client_id = ?", (client_id,)),
    }
    category_breakdown = _safe_rows(
        db,
        """
        SELECT visible_category, secondary_category, parse_status, COUNT(1) AS count
        FROM v2_documents
        WHERE client_id = ?
        GROUP BY visible_category, secondary_category, parse_status
        ORDER BY count DESC
        LIMIT 12
        """,
        (client_id,),
    )
    all_v2 = _safe_rows(db, "SELECT file_name, preview_text, doc_index_text, markdown_content FROM v2_documents WHERE client_id = ?", (client_id,))
    all_documents = _safe_rows(db, "SELECT title, excerpt FROM documents WHERE client_id = ?", (client_id,))
    all_tasks = _safe_rows(db, "SELECT t.title, t.description " + CLIENT_TASK_WHERE, (client_id, client_id))
    noise_counts = {
        "v2DocumentsNoise": sum(1 for row in all_v2 if _content_is_noise(row.get("file_name"), row.get("preview_text"), row.get("doc_index_text"), row.get("markdown_content"))),
        "documentsNoise": sum(1 for row in all_documents if _content_is_noise(row.get("title"), row.get("excerpt"))),
        "tasksNoise": sum(1 for row in all_tasks if _content_is_noise(row.get("title"), row.get("description"))),
    }
    selected_materials, duplicate_count = _build_selected_materials(db, client_id)
    dna_documents = [
        {
            "moduleKey": str(row.get("module_key") or ""),
            "title": str(row.get("title") or ""),
            "summary": _trim(row.get("summary"), 900),
            "text": _trim(row.get("normalized_text"), 3600),
            "updatedAt": str(row.get("updated_at") or ""),
        }
        for row in _safe_rows(
            db,
            """
            SELECT module_key, title, summary, normalized_text, updated_at
            FROM client_dna_documents
            WHERE client_id = ?
            ORDER BY updated_at DESC
            """,
            (client_id,),
        )
    ]
    generation_dna_documents = [item for item in dna_documents if not _content_is_prompt_like(item.get("summary"), item.get("text"))]
    event_lines = [
        {
            "name": str(row.get("name") or ""),
            "status": str(row.get("status") or ""),
            "stage": str(row.get("stage") or ""),
            "summary": _trim(row.get("summary"), 520),
            "intent": _trim(row.get("intent"), 620),
            "currentBlocker": _trim(row.get("current_blocker"), 360),
            "recentDecision": _trim(row.get("recent_decision"), 360),
            "nextStep": _trim(row.get("next_step"), 360),
            "evidenceCount": int(row.get("evidence_count") or 0),
            "updatedAt": str(row.get("updated_at") or ""),
        }
        for row in _safe_rows(
            db,
            """
            SELECT name, status, stage, summary, intent, current_blocker, recent_decision, next_step, evidence_count, updated_at
            FROM event_lines
            WHERE primary_client_id = ?
            ORDER BY updated_at DESC
            LIMIT 6
            """,
            (client_id,),
        )
    ]
    tasks = [
        {
            "title": str(row.get("title") or ""),
            "description": _trim(row.get("description"), 520),
            "status": str(row.get("status") or ""),
            "progressStatus": str(row.get("progress_status") or ""),
            "evidenceCount": int(row.get("evidence_count") or 0),
            "updatedAt": str(row.get("updated_at") or ""),
        }
        for row in _safe_rows(
            db,
            """
            SELECT t.title, t.description, t.status, t.progress_status, t.evidence_count, t.updated_at
            FROM tasks t
            LEFT JOIN event_lines e ON t.event_line_id = e.id
            WHERE (e.primary_client_id = ? OR (t.source_type = 'client' AND t.source_id = ?))
              AND COALESCE(t.scope_mode, 'COLLAB_SHARED') != 'PERSONAL_ONLY'
            ORDER BY t.updated_at DESC
            LIMIT 8
            """,
            (client_id, client_id),
        )
        if not _content_is_noise(row.get("title"), row.get("description"))
    ]
    meetings = [
        {
            "title": str(row.get("title") or ""),
            "stage": str(row.get("stage") or ""),
            "notes": _trim(row.get("notes"), 520),
            "transcriptExcerpt": _trim(row.get("transcript_text"), 520),
            "updatedAt": str(row.get("updated_at") or ""),
        }
        for row in _safe_rows(
            db,
            """
            SELECT title, stage, notes, transcript_text, updated_at
            FROM meetings
            WHERE client_id = ?
            ORDER BY updated_at DESC
            LIMIT 6
            """,
            (client_id,),
        )
        if not _content_is_noise(row.get("title"), row.get("notes"), row.get("transcript_text"))
    ]
    judgment_versions = [
        {
            "topic": str(row.get("topic") or ""),
            "status": str(row.get("status") or ""),
            "summary": _trim(row.get("summary"), 620),
            "riskLevel": str(row.get("risk_level") or ""),
            "confidence": str(row.get("confidence") or ""),
            "qualityTier": str(row.get("quality_tier") or ""),
            "updatedAt": str(row.get("updated_at") or ""),
        }
        for row in _safe_rows(
            db,
            """
            SELECT topic, status, summary, risk_level, confidence, quality_tier, updated_at
            FROM judgment_versions
            WHERE client_id = ?
            ORDER BY updated_at DESC
            LIMIT 6
            """,
            (client_id,),
        )
        if not _content_is_noise(row.get("topic"), row.get("summary"))
    ]
    recent_analyses = [
        {
            "question": _trim(row.get("question"), 260),
            "status": str(row.get("status") or ""),
            "answerMode": str(row.get("answer_mode") or ""),
            "summary": _trim(row.get("long_answer") or row.get("structured_summary_json"), 620),
            "updatedAt": str(row.get("updated_at") or ""),
        }
        for row in _safe_rows(
            db,
            """
            SELECT question, status, answer_mode, long_answer, structured_summary_json, updated_at
            FROM client_analysis_runs
            WHERE client_id = ? AND status IN ('succeeded', 'completed', 'done')
            ORDER BY updated_at DESC
            LIMIT 6
            """,
            (client_id,),
        )
        if not _content_is_noise(row.get("question"), row.get("long_answer"), row.get("structured_summary_json"))
    ]
    notebook = _safe_rows(
        db,
        """
        SELECT organization_intro, collaboration_relationship, current_stage,
               business_modules_json, key_people_json, key_products_json,
               current_challenges_json, collaboration_goals_json, recent_facts_json,
               information_gaps_json, updated_at
        FROM organization_notebook_snapshots
        WHERE client_id = ?
        LIMIT 1
        """,
        (client_id,),
    )
    organization_notebook = notebook[0] if notebook else {}
    digital_asset_summary = {
        "scoreMethodVersion": detail.scoreMethodVersion,
        "assetProfileType": detail.assetProfileType,
        "secondaryProfileTypes": detail.secondaryProfileTypes,
        "maturityScore": detail.maturityScore,
        "depositThickness": detail.depositThickness,
        "scoreBreakdown": detail.scoreBreakdown.model_dump(mode="json") if hasattr(detail.scoreBreakdown, "model_dump") else {},
        "scoreRationale": detail.scoreRationale,
        "materialMaturityRows": [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else {}
            for item in detail.materialMaturityRows[:8]
        ],
        "assetStage": detail.assetStage,
        "assetTrackTitle": detail.assetTrackTitle,
        "assetCompletionScore": detail.assetCompletionScore,
        "understandingScore": detail.understandingScore,
        "stageProgress": detail.stageProgress,
        "unlockedCapabilities": detail.unlockedCapabilities,
        "stageBlockers": detail.stageBlockers,
        "nextBestDeposits": [
            {
                "title": item.title,
                "reason": _trim(item.reason, 340),
            }
            for item in detail.nextBestDeposits[:4]
        ],
    }
    quality_warnings = _build_quality_warnings(
        counts=counts,
        noise_counts=noise_counts,
        duplicate_count=duplicate_count,
        dna_documents=dna_documents,
        digital_asset_summary=digital_asset_summary,
    )
    material_audit = {
        "counts": counts,
        "categoryBreakdownTop": category_breakdown,
        "noiseCounts": noise_counts,
        "duplicatePriorityMaterialsRemoved": duplicate_count,
        "selectedPriorityMaterials": [
            {
                "score": item["score"],
                "title": item["title"],
                "category": item["category"],
                "secondary": item["secondary"],
                "parseStatus": item["parseStatus"],
                "keywordHits": item["keywordHits"],
            }
            for item in selected_materials
        ],
        "qualityWarnings": quality_warnings,
    }
    context = {
        "client": {
            "id": str(client_row["id"]),
            "name": str(client_row["name"] or ""),
            "stage": str(client_row["stage"] or ""),
            "intro": _trim(client_row["intro"], 220),
        },
        "materialAudit": material_audit,
        "priority": {
            "rule": "近期事件线/任务/判断版本 > 核心战略文档 > 项目资料 > 数字资产统计 > 其他资料",
            "eventLines": event_lines,
            "tasks": tasks,
            "meetings": meetings,
            "judgmentVersions": judgment_versions,
            "recentAnalyses": recent_analyses,
            "coreMaterials": selected_materials,
            "dnaDocuments": generation_dna_documents,
            "organizationNotebook": organization_notebook,
            "digitalAssetSummary": digital_asset_summary,
        },
    }
    fingerprint_payload = {
        "client": context["client"],
        "counts": counts,
        "selected": [(item.get("title"), item.get("updatedAt"), item.get("score")) for item in selected_materials],
        "eventLines": [
            (item.get("name"), item.get("updatedAt"), item.get("summary"), item.get("recentDecision"), item.get("nextStep"))
            for item in event_lines
        ],
        "tasks": [(item.get("title"), item.get("updatedAt"), item.get("description")) for item in tasks],
        "judgments": [(item.get("topic"), item.get("updatedAt"), item.get("summary")) for item in judgment_versions],
    }
    context["sourceFingerprint"] = _hash_payload(fingerprint_payload)
    return context


def _row_to_narrative(row: Any) -> DigitalAssetNarrativeRecord:
    material_audit = from_json(row["material_audit_json"] or "{}", {})
    quality_warnings = from_json(row["quality_warnings_json"] or "[]", [])
    return DigitalAssetNarrativeRecord(
        id=str(row["id"]),
        clientId=str(row["client_id"]),
        sourceFingerprint=str(row["source_fingerprint"] or ""),
        contentMarkdown=str(row["content_markdown"] or ""),
        materialAudit=material_audit if isinstance(material_audit, dict) else {},
        qualityWarnings=[str(item) for item in quality_warnings] if isinstance(quality_warnings, list) else [],
        provider=str(row["provider"] or ""),
        model=str(row["model"] or ""),
        generatedAt=str(row["generated_at"] or row["updated_at"] or ""),
        failureReason=str(row["failure_reason"] or ""),
    )


def get_latest_digital_asset_narrative(db: Database, client_id: str) -> DigitalAssetNarrativeRecord | None:
    row = db.fetchone(
        """
        SELECT *
        FROM digital_asset_narrative_snapshots
        WHERE client_id = ? AND failure_reason = '' AND content_markdown != ''
        ORDER BY generated_at DESC
        LIMIT 1
        """,
        (client_id,),
    )
    return _row_to_narrative(row) if row is not None else None


def _content_quality_violations(content: str) -> list[str]:
    return [label for label, pattern in SEVERE_CONTENT_PATTERNS if pattern.search(content)]


def _content_style_warnings(content: str) -> list[str]:
    return [label for label, pattern in STYLE_WARNING_PATTERNS if pattern.search(content)]


def _ai_health(ai_service: object) -> tuple[str, str]:
    try:
        health = ai_service.get_health()  # type: ignore[attr-defined]
        return str(getattr(health, "provider", "")), str(getattr(health, "model", ""))
    except Exception:
        return "", ""


def _generate_with_ai(ai_service: object, *, prompt: str, system_instruction: str, max_tokens: int, timeout_seconds: float) -> str:
    generator = getattr(ai_service, "_qwen_generate")
    result = generator(
        prompt=prompt,
        system_instruction=system_instruction,
        response_schema=None,
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
        temperature=0.34,
        top_p=0.88,
        enable_thinking=False,
    )
    return str(result or "").strip()


def _save_narrative_snapshot(
    db: Database,
    *,
    client_id: str,
    source_fingerprint: str,
    content_markdown: str,
    material_audit: dict[str, object],
    quality_warnings: list[str],
    raw_output: str,
    provider: str,
    model: str,
    failure_reason: str = "",
) -> DigitalAssetNarrativeRecord:
    now = _now_iso()
    snapshot_id = "dan_" + uuid4().hex[:24]
    db.execute(
        """
        INSERT INTO digital_asset_narrative_snapshots(
            id, client_id, source_fingerprint, content_markdown, material_audit_json,
            quality_warnings_json, raw_output, provider, model, generated_at,
            failure_reason, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot_id,
            client_id,
            source_fingerprint,
            content_markdown,
            to_json(material_audit),
            to_json(quality_warnings),
            raw_output,
            provider,
            model,
            now,
            failure_reason,
            now,
            now,
        ),
    )
    row = db.fetchone("SELECT * FROM digital_asset_narrative_snapshots WHERE id = ?", (snapshot_id,))
    if row is None:
        raise RuntimeError("Digital asset narrative snapshot was not saved")
    return _row_to_narrative(row)


def refresh_digital_asset_narrative(db: Database, ai_service: object, client_id: str) -> DigitalAssetNarrativeRecord:
    detail = build_client_digital_assets(db, client_id)
    context = build_digital_asset_narrative_context(db, client_id, detail=detail)
    source_fingerprint = str(context.get("sourceFingerprint") or "")
    material_audit = context.get("materialAudit") if isinstance(context.get("materialAudit"), dict) else {}
    material_audit = material_audit if isinstance(material_audit, dict) else {}
    quality_warnings = [str(item) for item in material_audit.get("qualityWarnings", [])] if isinstance(material_audit.get("qualityWarnings"), list) else []
    provider, model = _ai_health(ai_service)
    system_instruction = (
        "你是益语智库的客户资料分析顾问。请基于真实数据中心资料生成数字资产中心详情页文案。"
        "用普通人能听懂的话，不要堆术语；少用底座、资产、补齐、验证表、赋能、闭环。"
        "必须区分：资料已经显示、可以初步判断、现在还不能确定。"
        "类型、等级、成熟度和五项评分已经由后端确定性规则算出，你只能解释这些结果，不能重新打分或改写等级。"
        "不能编造数字、百分比、准确率、降本比例、未给出的时间节点。"
        "不要把公益项目写成商业增长案例。不要使用“长期来看”。"
    )
    generation_prompt = (
        "下面是从当前后端数据库和数字资产接口读取的真实资料包。"
        "请输出 Markdown，包含这些小节：\n"
        "## 资料概况\n"
        "## 系统已经能看清什么\n"
        "## 系统现在能帮什么\n"
        "## 现在还不能确定什么\n"
        "## 接下来建议先整理什么\n\n"
        "要求：内容要直白、可展示、可追责；不要解释生成过程；不要把 documents 和 v2Documents 相加成“有效资料总数”。\n\n"
        f"真实资料包：\n{json.dumps(context, ensure_ascii=False, default=str)}"
    )
    raw_output = _generate_with_ai(ai_service, prompt=generation_prompt, system_instruction=system_instruction, max_tokens=3200, timeout_seconds=160.0)
    calibration_prompt = (
        "请校准下面这段数字资产中心文案。只返回修订后的 Markdown 正文，不要解释。\n"
        "校准规则：\n"
        "1. 删除或改写没有证据的数字、百分比、准确率、降本、商业化表达。\n"
        "2. 把“已经完成/一定会”改成“资料显示/可以初步判断/还不能确定”。\n"
        "3. 把“底座、补齐、验证表、闭环”等系统术语改成普通表达。\n"
        "4. 保留资料质量问题和下一步建议。\n\n"
        f"原文：\n{raw_output}"
    )
    calibrated = _generate_with_ai(ai_service, prompt=calibration_prompt, system_instruction=system_instruction, max_tokens=2600, timeout_seconds=120.0)
    final_content = calibrated or raw_output
    severe_violations = _content_quality_violations(final_content)
    style_warnings = _content_style_warnings(final_content)
    all_warnings = [*quality_warnings, *style_warnings]
    if severe_violations:
        failure_reason = "；".join(severe_violations)
        _save_narrative_snapshot(
            db,
            client_id=client_id,
            source_fingerprint=source_fingerprint,
            content_markdown="",
            material_audit=material_audit,
            quality_warnings=all_warnings,
            raw_output=f"{raw_output}\n\n--- calibrated ---\n{final_content}",
            provider=provider,
            model=model,
            failure_reason=failure_reason,
        )
        raise DigitalAssetNarrativeQualityError(failure_reason)
    return _save_narrative_snapshot(
        db,
        client_id=client_id,
        source_fingerprint=source_fingerprint,
        content_markdown=final_content,
        material_audit=material_audit,
        quality_warnings=all_warnings,
        raw_output=f"{raw_output}\n\n--- calibrated ---\n{final_content}",
        provider=provider,
        model=model,
    )
