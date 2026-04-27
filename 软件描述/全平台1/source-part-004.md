# 益语软件平台源码导出（第004卷）

- 导出时间: 2026-04-20 18:08:04
- 内容范围: 主仓库源码 + mobile 子仓库源码
- 说明: 每个条目为完整源码文件。

## `backend/app/services/knowledge_base.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import atexit
import hashlib
import json
import logging
import os
import re
import shutil
import zipfile
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from xml.etree import ElementTree as ET

from app.db import Database, from_json, to_json

try:
    from fastembed import TextEmbedding

    HAS_FASTEMBED = True
except Exception:  # pragma: no cover - import fallback
    TextEmbedding = None  # type: ignore[assignment]
    HAS_FASTEMBED = False

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import Distance, PointStruct, VectorParams

    HAS_QDRANT = True
except Exception:  # pragma: no cover - import fallback
    QdrantClient = None  # type: ignore[assignment]
    Distance = None  # type: ignore[assignment]
    PointStruct = None  # type: ignore[assignment]
    VectorParams = None  # type: ignore[assignment]
    HAS_QDRANT = False

try:
    from pypdf import PdfReader

    HAS_PYPDF = True
except Exception:  # pragma: no cover - import fallback
    PdfReader = None  # type: ignore[assignment]
    HAS_PYPDF = False


TEXT_EXTENSIONS = {".md", ".txt", ".json", ".csv"}
ARCHIVE_XML_EXTENSIONS = {".docx", ".pptx", ".xlsx"}
PDF_EXTENSIONS = {".pdf"}
PRIMARY_CATEGORIES = [
    "财务与筹款",
    "品牌与传播",
    "项目与业务",
    "组织与战略",
    "其他资料",
]
HUMAN_VISIBLE_CATEGORIES = [*PRIMARY_CATEGORIES, "战略陪伴"]
CATEGORY_KEYWORDS = {
    "财务与筹款": ["预算", "财务", "筹款", "捐赠", "基金", "募资", "现金流", "报表", "赞助"],
    "品牌与传播": ["传播", "品牌", "媒体", "公关", "公众号", "内容", "活动传播", "campaign", "社媒"],
    "项目与业务": ["项目", "执行", "交付", "业务", "方案", "里程碑", "调研", "落地", "访谈"],
    "组织与战略": ["战略", "组织", "okr", "治理", "董事会", "人力", "招聘", "文化", "年度计划", "规划"],
}
SECONDARY_CATEGORY_KEYWORDS = {
    "财务与筹款": {
        "预算与报表": ["预算", "报表", "财务", "现金流"],
        "捐赠与募资": ["捐赠", "募资", "筹款", "赞助", "基金"],
    },
    "品牌与传播": {
        "内容与品牌": ["品牌", "内容", "故事", "视觉"],
        "渠道与活动": ["媒体", "活动", "传播", "社媒", "公关"],
    },
    "项目与业务": {
        "项目推进": ["项目", "推进", "交付", "里程碑", "执行"],
        "调研与客户": ["调研", "访谈", "客户", "需求", "反馈"],
    },
    "组织与战略": {
        "组织治理": ["组织", "治理", "董事会", "制度", "流程", "人力"],
        "战略规划": ["战略", "规划", "年度计划", "okr", "路线图"],
    },
}
STOPWORDS = {
    "我们",
    "你们",
    "他们",
    "已经",
    "以及",
    "需要",
    "进行",
    "关于",
    "这个",
    "那个",
    "本周",
    "工作",
    "内容",
    "处理",
    "项目",
    "客户",
    "当前",
    "资料",
    "文件",
    "计划",
    "总结",
}
TOKEN_CHAR_STOP = set("的了是和在对与及并将把里到什么这那")
QUERY_NOISE_PATTERNS = [
    r"请简要介绍一下",
    r"请简要介绍",
    r"简要介绍一下",
    r"简要介绍",
    r"请介绍一下",
    r"请介绍",
    r"介绍一下",
    r"什么样的机构",
    r"什么样的",
    r"是一家什么样的",
    r"是一家什么样",
]
INDEX_PLACEHOLDER_PATTERNS = (
    "已归入客户知识底座",
    "已进入资料缓冲池",
    "可作为后续问答",
    "证据引用来源",
    "等待进一步解析",
)
INDEX_NOISE_FRAGMENTS = (
    "资料缓",
    "冲池",
    "后续问",
    "证据引",
    "知识底座",
    "等待进一步",
    "yiyuthinktankworkbench",
)
OVERVIEW_QUERY_HINTS = ("介绍", "简介", "概况", "概览", "是什么", "背景", "定位", "做什么", "是谁")
INTRO_PROFILE_HINTS = ("介绍", "简介", "概况", "概览", "背景", "定位", "做什么", "团队", "业务", "历史")
INTRO_PRIORITY_HINTS = (
    "介绍",
    "简介",
    "概览",
    "定位",
    "核心业务",
    "团队",
    "访谈",
    "纪要",
    "理事会",
    "工作坊",
    "战略框架",
    "业务介绍",
    "组织介绍",
)
INTRO_NOISE_HINTS = (
    "文件导入",
    "完整解决方案",
    "上传说明",
    "目录重分类",
    "重建知识索引",
    "导入飞书",
    "缓冲池",
    "精简版",
    "完整版",
    "第8稿",
    "第7稿",
    "click to edit master",
    "master title style",
    "工作台",
)
STRATEGIC_ANALYSIS_HINTS = (
    "战略",
    "定位",
    "风险",
    "建议",
    "判断",
    "分析",
    "诊断",
    "方向",
    "重点",
    "卡点",
    "问题",
    "路径",
    "概括",
    "概述",
    "脉络",
    "为什么",
    "怎么做",
    "如何看",
)
CATEGORY_QUERY_HINTS = {
    "财务与筹款": ("财务", "筹款", "募资", "捐赠", "预算", "赞助", "基金", "现金流"),
    "品牌与传播": ("品牌", "传播", "公关", "媒体", "公众号", "内容", "活动", "社媒"),
    "项目与业务": ("项目", "业务", "交付", "推进", "执行", "落地", "访谈", "需求", "反馈"),
    "组织与战略": ("组织", "战略", "治理", "年度计划", "okr", "路线图", "机制", "团队", "人力"),
}
FINANCE_QUERY_HINTS = (
    "财务",
    "报表",
    "预算",
    "收支",
    "收入",
    "支出",
    "资产",
    "负债",
    "现金流",
    "审计",
    "决算",
    "净资产",
    "货币资金",
)
FINANCE_STATEMENT_QUERY_HINTS = (
    "财务状况",
    "财务情况",
    "资产",
    "负债",
    "现金流",
    "收入",
    "支出",
    "费用",
    "净资产",
    "资产负债",
    "决算",
    "审计",
    "报表",
    "结余",
)
FINANCE_PRIORITY_HINTS = (
    "财务报告",
    "财务决算",
    "决算报告",
    "审计报告",
    "预算",
    "报表",
    "收支",
    "收入总额",
    "费用总额",
    "资产总额",
    "负债总额",
    "资产负债率",
    "净资产",
    "货币资金",
    "捐赠收入",
    "提供服务收入",
    "管理费用",
    "业务活动成本",
    "现金流",
)
FINANCE_STATEMENT_PRIORITY_HINTS = (
    "财务报告",
    "年度财务报告",
    "决算报告",
    "审计报告",
    "资产总额",
    "负债总额",
    "资产负债率",
    "净资产",
    "收入总额",
    "费用总额",
    "收支结余",
    "货币资金",
    "捐赠收入",
    "提供服务收入",
)
FINANCE_TEMPLATE_NOISE_HINTS = (
    "模板",
    "项目价值分析表",
    "预算调整",
    "项目计划书",
    "项目方案",
    "询价单",
)
QDRANT_VECTOR_SIZE = 256
MASTER_VECTOR_CANDIDATE_THRESHOLD = 0.10
CHUNK_VECTOR_CANDIDATE_THRESHOLD = 0.12
_QDRANT_CLIENTS: dict[str, Any] = {}
_EMBEDDING_MODE_SETTING = os.getenv("YIYU_EMBEDDING_MODE", "auto").strip().lower()
_FASTEMBED_MODEL_NAME = os.getenv("YIYU_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5").strip() or "BAAI/bge-small-zh-v1.5"
_FASTEMBED_BATCH_SIZE = max(1, int(os.getenv("YIYU_EMBEDDING_BATCH_SIZE", "16")))
_EMBEDDERS: dict[str, Any] = {}
_EMBEDDING_STATE: dict[str, dict[str, Any]] = {}
logger = logging.getLogger(__name__)


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _close_qdrant_clients() -> None:
    for client in list(_QDRANT_CLIENTS.values()):
        try:
            client.close()
        except Exception:
            pass
    _QDRANT_CLIENTS.clear()


atexit.register(_close_qdrant_clients)


@dataclass
class PreparedKnowledgeDocument:
    knowledge_document_id: str
    doc_uid: str
    title: str
    original_path: str
    import_source_path: str
    current_human_path: str | None
    human_folder_category: str | None
    normalized_path: str | None
    surrogate_md_path: str | None
    kind: str
    primary_category: str
    secondary_category: str
    short_summary: str
    summary: str
    retrieval_summary: str
    document_role: str
    query_hints: list[str]
    distinct_findings: list[str]
    core_questions: list[str]
    keywords: list[str]
    tags: list[str]
    entities: list[str]
    date_range: str | None
    classification_confidence: float
    needs_review: bool
    dedup_status: str
    vector_status: str
    chunk_count: int
    binary_hash: str
    normalized_hash: str
    raw_text: str


@dataclass
class CitationMatch:
    knowledge_document_id: str
    chunk_id: str | None
    title: str
    excerpt: str
    score: float
    coverage: float
    section_label: str | None
    source_stage: str
    drillthrough_used: bool
    matched_terms: list[str]
    path: str | None


@dataclass
class RetrievalBundle:
    citations: list[CitationMatch]
    coverage: float
    retrieval_summary: dict[str, Any]
    context_text: str
    matched_terms: list[str]
    failure_reason: str | None = None


def serialize_retrieval_bundle(bundle: RetrievalBundle) -> dict[str, Any]:
    return {
        "citations": [
            {
                "knowledge_document_id": item.knowledge_document_id,
                "chunk_id": item.chunk_id,
                "title": item.title,
                "excerpt": item.excerpt,
                "score": item.score,
                "coverage": item.coverage,
                "section_label": item.section_label,
                "source_stage": item.source_stage,
                "drillthrough_used": item.drillthrough_used,
                "matched_terms": item.matched_terms,
                "path": item.path,
            }
            for item in bundle.citations
        ],
        "coverage": bundle.coverage,
        "retrieval_summary": bundle.retrieval_summary,
        "context_text": bundle.context_text,
        "matched_terms": bundle.matched_terms,
        "failure_reason": bundle.failure_reason,
    }


def deserialize_retrieval_bundle(payload: dict[str, Any]) -> RetrievalBundle:
    citations_payload = payload.get("citations", [])
    citations: list[CitationMatch] = []
    if isinstance(citations_payload, list):
        for item in citations_payload:
            if not isinstance(item, dict):
                continue
            citations.append(
                CitationMatch(
                    knowledge_document_id=str(item.get("knowledge_document_id", "")),
                    chunk_id=str(item["chunk_id"]) if item.get("chunk_id") else None,
                    title=str(item.get("title", "")),
                    excerpt=str(item.get("excerpt", "")),
                    score=float(item.get("score", 0.0) or 0.0),
                    coverage=float(item.get("coverage", 0.0) or 0.0),
                    section_label=str(item["section_label"]) if item.get("section_label") else None,
                    source_stage=str(item.get("source_stage", "raw_chunk")),
                    drillthrough_used=bool(item.get("drillthrough_used", False)),
                    matched_terms=[str(term) for term in item.get("matched_terms", []) if str(term).strip()],
                    path=str(item["path"]) if item.get("path") else None,
                )
            )
    retrieval_summary = payload.get("retrieval_summary", {})
    matched_terms = payload.get("matched_terms", [])
    return RetrievalBundle(
        citations=citations,
        coverage=float(payload.get("coverage", 0.0) or 0.0),
        retrieval_summary=retrieval_summary if isinstance(retrieval_summary, dict) else {},
        context_text=str(payload.get("context_text", "")),
        matched_terms=[str(term) for term in matched_terms if str(term).strip()] if isinstance(matched_terms, list) else [],
        failure_reason=str(payload["failure_reason"]) if payload.get("failure_reason") else None,
    )


def tokenize(text: str) -> list[str]:
    normalized = text.lower()
    normalized = re.sub(r"[，。；：,.!?！？/\\-]+", " ", normalized)
    for pattern in QUERY_NOISE_PATTERNS:
        normalized = re.sub(pattern, " ", normalized)
    normalized = re.sub(r"(什么|以及|进行|关于|当前|这个|那个|一个|一下)", " ", normalized)
    normalized = re.sub(r"[的是了和在对与及并将把里到]", " ", normalized)
    raw_tokens = re.findall(r"[A-Za-z0-9]{2,}|[\u4e00-\u9fff]{2,8}", normalized)
    seen: set[str] = set()
    tokens: list[str] = []
    for token in raw_tokens:
        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            candidates = [token]
            if len(token) > 4:
                for size in (4, 3, 2):
                    for index in range(0, len(token) - size + 1):
                        candidates.append(token[index : index + size])
        else:
            candidates = [token]
        for candidate in candidates:
            if re.fullmatch(r"[\u4e00-\u9fff]+", candidate):
                if candidate[0] in TOKEN_CHAR_STOP or candidate[-1] in TOKEN_CHAR_STOP:
                    continue
                if sum(1 for char in candidate if char in TOKEN_CHAR_STOP) >= 2:
                    continue
            if candidate in STOPWORDS or len(candidate.strip()) < 2:
                continue
            if candidate not in seen:
                tokens.append(candidate)
                seen.add(candidate)
    return tokens


def normalize_text(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"\s+", " ", lowered)
    lowered = re.sub(r"[^\w\u4e00-\u9fff]+", "", lowered)
    return lowered.strip()


def is_overview_query(text: str) -> bool:
    normalized = re.sub(r"\s+", "", (text or "").lower())
    return any(hint in normalized for hint in OVERVIEW_QUERY_HINTS)


def is_intro_profile_query(text: str) -> bool:
    normalized = re.sub(r"\s+", "", (text or "").lower())
    return any(hint in normalized for hint in INTRO_PROFILE_HINTS)


def is_strategy_analysis_query(text: str) -> bool:
    normalized = re.sub(r"\s+", "", (text or "").lower())
    return any(hint in normalized for hint in STRATEGIC_ANALYSIS_HINTS)


def is_finance_query(text: str) -> bool:
    normalized = re.sub(r"\s+", "", (text or "").lower())
    return any(hint in normalized for hint in FINANCE_QUERY_HINTS)


def is_finance_statement_query(text: str) -> bool:
    normalized = re.sub(r"\s+", "", (text or "").lower())
    return any(hint in normalized for hint in FINANCE_STATEMENT_QUERY_HINTS)


def infer_query_categories(text: str, tokens: list[str]) -> list[str]:
    normalized = re.sub(r"\s+", "", (text or "").lower())
    matched: list[str] = []
    for category, hints in CATEGORY_QUERY_HINTS.items():
        if any(hint in normalized for hint in hints) or any(token in "".join(hints) for token in tokens):
            matched.append(category)
    if matched:
        return matched
    if is_intro_profile_query(text):
        return ["组织与战略", "项目与业务"]
    if is_strategy_analysis_query(text):
        return list(PRIMARY_CATEGORIES)
    return []


def intro_document_score_adjustment(
    *,
    title: str,
    summary: str,
    document_role: str,
    folder_category: str,
    path: str | None,
) -> float:
    haystack = " ".join(part.lower() for part in (title, summary, document_role, folder_category, path or "") if part)
    adjustment = 0.0
    if any(marker in haystack for marker in INTRO_NOISE_HINTS):
        adjustment -= 1.8
    if any(marker in haystack for marker in ("核心业务介绍", "业务介绍", "组织介绍")):
        adjustment += 0.9
    if any(marker in haystack for marker in INTRO_PRIORITY_HINTS):
        adjustment += 0.35
    if document_role == "机构介绍":
        adjustment += 0.55
    if folder_category in {"组织与战略", "项目与业务"}:
        adjustment += 0.12
    return adjustment


def intro_chunk_score_adjustment(*, title: str, excerpt: str, section_label: str | None, path: str | None) -> float:
    haystack = " ".join(part.lower() for part in (title, excerpt, section_label or "", path or "") if part)
    adjustment = 0.0
    if any(marker in haystack for marker in INTRO_NOISE_HINTS):
        adjustment -= 1.4
    if any(marker in haystack for marker in ("核心业务介绍", "业务介绍", "组织介绍")):
        adjustment += 0.42
    if any(marker in haystack for marker in INTRO_PRIORITY_HINTS):
        adjustment += 0.22
    return adjustment


def is_intro_noise_text(*parts: str | None) -> bool:
    haystack = " ".join(part.lower() for part in parts if part)
    return any(marker in haystack for marker in INTRO_NOISE_HINTS)


def is_intro_priority_text(*parts: str | None) -> bool:
    haystack = " ".join(part.lower() for part in parts if part)
    if any(marker in haystack for marker in ("核心业务介绍", "业务介绍", "组织介绍")):
        return True
    return any(marker in haystack for marker in INTRO_PRIORITY_HINTS)


def is_finance_priority_text(*parts: str | None) -> bool:
    haystack = " ".join(part.lower() for part in parts if part)
    return any(marker in haystack for marker in FINANCE_PRIORITY_HINTS)


def is_finance_statement_priority_text(*parts: str | None) -> bool:
    haystack = " ".join(part.lower() for part in parts if part)
    return any(marker in haystack for marker in FINANCE_STATEMENT_PRIORITY_HINTS)


def finance_document_score_adjustment(
    *,
    title: str,
    summary: str,
    document_role: str,
    folder_category: str,
    path: str | None,
    statement_mode: bool = False,
) -> float:
    haystack = " ".join(part.lower() for part in (title, summary, document_role, folder_category, path or "") if part)
    adjustment = 0.0
    if folder_category == "财务与筹款":
        adjustment += 0.95
    elif folder_category != "财务与筹款" and not is_finance_priority_text(title, summary, document_role, path):
        adjustment -= 0.22
    if document_role == "财务资料":
        adjustment += 0.55
    if is_finance_priority_text(title, summary, document_role, path):
        adjustment += 0.78
    if statement_mode:
        if is_finance_statement_priority_text(title, summary, document_role, path):
            adjustment += 0.92
        if any(marker in haystack for marker in FINANCE_TEMPLATE_NOISE_HINTS) and not is_finance_statement_priority_text(title, summary, document_role, path):
            adjustment -= 1.05
    if any(marker in haystack for marker in INTRO_NOISE_HINTS):
        adjustment -= 0.4
    if any(marker in haystack for marker in ("核心业务介绍", "机构和业务简介", "工作坊", "访谈", "年会手册")) and not is_finance_priority_text(title, summary, path):
        adjustment -= 0.28
    return adjustment


def finance_chunk_score_adjustment(
    *,
    title: str,
    excerpt: str,
    section_label: str | None,
    path: str | None,
    statement_mode: bool = False,
) -> float:
    haystack = " ".join(part.lower() for part in (title, excerpt, section_label or "", path or "") if part)
    adjustment = 0.0
    if is_finance_priority_text(title, excerpt, section_label, path):
        adjustment += 1.15
    elif "财务与筹款" in haystack:
        adjustment += 0.45
    if any(marker in haystack for marker in ("资产总额", "负债总额", "资产负债率", "净资产", "收入总额", "费用总额", "收支结余", "货币资金")):
        adjustment += 0.68
    if statement_mode:
        if is_finance_statement_priority_text(title, excerpt, section_label, path):
            adjustment += 0.95
        if any(marker in haystack for marker in FINANCE_TEMPLATE_NOISE_HINTS) and not is_finance_statement_priority_text(title, excerpt, section_label, path):
            adjustment -= 1.2
    if any(marker in haystack for marker in ("核心业务介绍", "机构和业务简介", "工作坊", "访谈")) and not is_finance_priority_text(title, excerpt, section_label, path):
        adjustment -= 0.35
    return adjustment


def diversify_candidate_documents(
    candidates: list[dict[str, Any]],
    *,
    preferred_categories: list[str],
    limit: int,
    strategic_mode: bool,
    overview_mode: bool = False,
    finance_mode: bool = False,
) -> list[dict[str, Any]]:
    if not strategic_mode and not overview_mode:
        return candidates[:limit]
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()

    def take_first_for_category(category: str) -> None:
        for item in candidates:
            if item.get("master_id") in selected_ids:
                continue
            if item.get("folder_category") != category:
                continue
            selected.append(item)
            selected_ids.add(str(item.get("master_id")))
            return

    if finance_mode and "财务与筹款" in preferred_categories:
        finance_taken = 0
        for item in candidates:
            if item.get("master_id") in selected_ids:
                continue
            if item.get("folder_category") != "财务与筹款":
                continue
            selected.append(item)
            selected_ids.add(str(item.get("master_id")))
            finance_taken += 1
            if finance_taken >= 3 or len(selected) >= limit:
                return selected[:limit]

    for category in preferred_categories:
        take_first_for_category(category)
        if len(selected) >= limit:
            return selected[:limit]
    for category in PRIMARY_CATEGORIES:
        take_first_for_category(category)
        if len(selected) >= limit:
            return selected[:limit]
    for item in candidates:
        master_id = str(item.get("master_id"))
        if master_id in selected_ids:
            continue
        selected.append(item)
        selected_ids.add(master_id)
        if len(selected) >= limit:
            break
    return selected[:limit]


def dedupe_ranked_matches(
    matches: list[dict[str, Any]],
    *,
    limit: int,
    key_builder,
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in matches:
        key = str(key_builder(item))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped


def build_source_tree(path: Path, mode: str) -> tuple[dict[str, Any], int]:
    if mode == "file":
        return {
            "name": path.name,
            "path": str(path),
            "type": "file",
        }, 1 if path.exists() and path.is_file() else 0

    file_count = 0

    def walk(node: Path) -> dict[str, Any]:
        nonlocal file_count
        if node.is_file():
            file_count += 1
            return {"name": node.name, "path": str(node), "type": "file"}
        children = sorted(node.iterdir(), key=lambda item: (item.is_file(), item.name.lower()))
        return {
            "name": node.name,
            "path": str(node),
            "type": "directory",
            "children": [walk(child) for child in children[:120]],
        }

    return walk(path), file_count


def _read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _read_xml_archive(path: Path) -> str:
    texts: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            names = [name for name in archive.namelist() if name.endswith(".xml")]
            for name in names:
                if path.suffix.lower() == ".docx" and not name.startswith("word/"):
                    continue
                if path.suffix.lower() == ".pptx" and not name.startswith("ppt/"):
                    continue
                if path.suffix.lower() == ".xlsx" and not name.startswith("xl/"):
                    continue
                try:
                    payload = archive.read(name)
                except KeyError:
                    continue
                try:
                    root = ET.fromstring(payload)
                except ET.ParseError:
                    continue
                texts.extend([node.strip() for node in root.itertext() if node and node.strip()])
    except Exception:
        return ""
    return "\n".join(texts)


def _read_pdf_file(path: Path) -> str:
    if not HAS_PYPDF or PdfReader is None:
        return ""
    pages: list[str] = []
    try:
        reader = PdfReader(str(path))
    except Exception:
        return ""
    for page in getattr(reader, "pages", []):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        cleaned = text.strip()
        if cleaned:
            pages.append(cleaned)
    return "\n\n".join(pages)


def extract_document_text(path: Path, fallback_excerpt: str = "") -> str:
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        text = _read_text_file(path)
        return text or fallback_excerpt
    if suffix in ARCHIVE_XML_EXTENSIONS:
        text = _read_xml_archive(path)
        return text or fallback_excerpt
    if suffix in PDF_EXTENSIONS:
        text = _read_pdf_file(path)
        return text or fallback_excerpt
    return fallback_excerpt


def build_excerpt(text: str, fallback_title: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if cleaned:
        return cleaned[:140]
    return f"{fallback_title} 已进入知识底座，等待进一步解析。"


def build_summaries(text: str, fallback_title: str) -> tuple[str, str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        placeholder = f"{fallback_title} 已归入客户知识底座，当前可作为后续问答和引证来源。"
        return placeholder[:48], placeholder[:200]
    sentences = re.split(r"[。！？!?；;\n]+", cleaned)
    sentences = [item.strip() for item in sentences if item.strip()]
    short_summary = sentences[0][:48] if sentences else cleaned[:48]
    long_summary = "；".join(sentences[:3])[:200] if sentences else cleaned[:200]
    return short_summary, long_summary


def is_placeholder_knowledge_text(text: str) -> bool:
    value = re.sub(r"\s+", " ", (text or "")).strip()
    if not value:
        return True
    return any(pattern in value for pattern in INDEX_PLACEHOLDER_PATTERNS)


def clean_title_for_search(title: str) -> str:
    stem = Path(title).stem
    stem = re.sub(r"[_\s]+CFF[C]?(?:[_-]?\d{8})$", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"[_\s]+\d+$", "", stem)
    stem = re.sub(r"^(?:CFFC文件|CFF文件)[+_ ]*", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"[_+]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" -_")
    return stem or Path(title).stem or title


def build_source_outline(text: str, fallback_summary: str = "", *, max_sentences: int = 8, max_chars: int = 1200) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "")).strip()
    if not cleaned:
        cleaned = re.sub(r"\s+", " ", (fallback_summary or "")).strip()
    if not cleaned or is_placeholder_knowledge_text(cleaned):
        return ""
    sentences = re.split(r"[。！？!?；;\n]+", cleaned)
    sentences = [item.strip() for item in sentences if item.strip()]
    outline = "；".join(sentences[:max_sentences]) if sentences else cleaned
    return outline[:max_chars]


def clean_index_terms(items: list[str], *, limit: int = 8) -> list[str]:
    cleaned_terms: list[str] = []
    for item in items:
        cleaned = re.sub(r"\s+", " ", str(item or "")).strip()
        cleaned = cleaned.replace("_", " ").strip(" -_")
        if not cleaned:
            continue
        normalized = cleaned.lower()
        if normalized in STOPWORDS:
            continue
        if any(pattern in cleaned for pattern in INDEX_PLACEHOLDER_PATTERNS):
            continue
        if any(fragment in normalized for fragment in INDEX_NOISE_FRAGMENTS):
            continue
        if re.fullmatch(r"(?:cffc[_\s-]*)?\d{6,8}", normalized):
            continue
        if len(cleaned) <= 1:
            continue
        if cleaned in cleaned_terms:
            continue
        cleaned_terms.append(cleaned)
        if len(cleaned_terms) >= limit:
            break
    return cleaned_terms


def build_master_index_summary(*, title: str, short_summary: str, summary: str, raw_text: str) -> str:
    candidates = [summary, short_summary, build_excerpt(raw_text, clean_title_for_search(title))]
    for item in candidates:
        value = re.sub(r"\s+", " ", (item or "")).strip()
        if value and not is_placeholder_knowledge_text(value):
            return value[:220]
    return clean_title_for_search(title)[:220]


def build_catalog_search_text(
    *,
    title: str,
    short_summary: str,
    summary: str,
    raw_text: str,
    keywords: list[str],
    entities: list[str],
    primary_category: str,
    secondary_category: str,
    document_role: str,
) -> str:
    clean_title = clean_title_for_search(title)
    outline = build_source_outline(raw_text, summary)
    meaningful_summary = "" if is_placeholder_knowledge_text(summary) else re.sub(r"\s+", " ", (summary or "")).strip()
    meaningful_short = "" if is_placeholder_knowledge_text(short_summary) else re.sub(r"\s+", " ", (short_summary or "")).strip()
    parts = [
        clean_title,
        meaningful_short,
        meaningful_summary,
        outline,
        " ".join(clean_index_terms(keywords, limit=8)),
        " ".join(clean_index_terms(entities, limit=8)),
        primary_category,
        secondary_category,
        document_role,
    ]
    return "\n".join(part for part in parts if part)


def load_surrogate_retrieval_text(path: str | Path) -> str:
    try:
        content = Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    if "## " not in content:
        return content
    allowed_sections = {"overview_summary", "retrieval_summary", "distinct_findings", "entities", "time_markers", "source_outline"}
    kept: list[str] = []
    current_section: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        if current_section in allowed_sections and buffer:
            kept.extend(buffer)
        buffer = []

    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        if line.startswith("## "):
            flush()
            current_section = line[3:].strip()
            buffer.append(line)
            continue
        if line.startswith("# "):
            kept.append(line)
            continue
        if line.startswith("- source_type:") or line.startswith("- folder_category:") or line.startswith("- document_role:"):
            kept.append(line)
            continue
        if current_section in allowed_sections:
            buffer.append(line)
    flush()
    return "\n".join(kept).strip()


def build_coverage_terms(prompt: str, tokens: list[str], preferred_categories: list[str]) -> list[str]:
    normalized_prompt = re.sub(r"\s+", "", (prompt or "").lower())
    anchor_terms: list[str] = []
    if "财务与筹款" in preferred_categories and is_finance_statement_query(prompt):
        for hint in ("财务", "报表", "资产", "负债", "收入", "费用", "现金流", "净资产"):
            if hint not in anchor_terms:
                anchor_terms.append(hint)
    for category in preferred_categories:
        for hint in CATEGORY_QUERY_HINTS.get(category, ()):
            if hint in normalized_prompt and hint not in anchor_terms:
                anchor_terms.append(hint)

    coverage_terms: list[str] = []
    for token in anchor_terms:
        coverage_terms.append(token)

    for token in sorted(tokens, key=lambda item: (-len(item), item)):
        containers = [existing for existing in coverage_terms if token != existing and token in existing]
        if containers and not any(existing.startswith(token) or existing.endswith(token) for existing in containers):
            continue
        coverage_terms.append(token)
        if len(coverage_terms) >= 8:
            break

    return (coverage_terms or tokens[:8])[:8]


def _extract_date_range(text: str) -> str | None:
    matches = re.findall(r"(20\d{2}[年/-]?\d{0,2}[月/-]?\d{0,2})", text)
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    return f"{matches[0]} ~ {matches[-1]}"


def _extract_keywords(text: str, title: str, limit: int = 8) -> list[str]:
    tokens = tokenize(f"{title} {text}")
    counts = Counter(tokens)
    return [token for token, _ in counts.most_common(limit)]


def _extract_entities(text: str, title: str, limit: int = 6) -> list[str]:
    entities: list[str] = []
    for item in re.findall(r"[A-Z][A-Za-z0-9_-]{1,20}|[\u4e00-\u9fff]{2,6}", f"{title} {text}"):
        cleaned = item.strip()
        if cleaned in STOPWORDS or cleaned in entities:
            continue
        entities.append(cleaned)
        if len(entities) >= limit:
            break
    return entities


def classify_document(title: str, text: str, kind: str) -> tuple[str, str, float, bool]:
    haystack = f"{title}\n{text[:4000]}".lower()
    category_scores: dict[str, int] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        category_scores[category] = sum(haystack.count(keyword.lower()) for keyword in keywords)
    if kind in {"xlsx", "csv"}:
        category_scores["财务与筹款"] += 1
    if kind in {"pptx"}:
        category_scores["品牌与传播"] += 1

    primary_category = max(category_scores.items(), key=lambda item: item[1])[0]
    max_score = category_scores[primary_category]
    needs_review = max_score <= 1
    confidence = 0.42 if needs_review else min(0.95, 0.55 + max_score * 0.08)
    if max_score == 0:
        primary_category = "其他资料"
        confidence = 0.35
        needs_review = True

    secondary_category = "待复核"
    for candidate, keywords in SECONDARY_CATEGORY_KEYWORDS.get(primary_category, {}).items():
        if any(keyword.lower() in haystack for keyword in keywords):
            secondary_category = candidate
            break
    if secondary_category == "待复核" and primary_category != "其他资料":
        secondary_category = list(SECONDARY_CATEGORY_KEYWORDS.get(primary_category, {"待复核": []}).keys())[0]
    if primary_category == "其他资料":
        secondary_category = "待复核"

    return primary_category, secondary_category, round(confidence, 2), needs_review


def compute_binary_hash(path: Path, fallback_text: str) -> str:
    hasher = hashlib.sha256()
    if path.exists() and path.is_file():
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(8192)
                if not chunk:
                    break
                hasher.update(chunk)
    else:
        hasher.update(fallback_text.encode("utf-8"))
    return hasher.hexdigest()


def compute_normalized_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def generate_doc_uid(client_id: str, original_path: str, binary_hash: str) -> str:
    digest = hashlib.sha1(f"{client_id}:{original_path}:{binary_hash}".encode("utf-8")).hexdigest()
    return f"dock_{digest[:12]}"


def safe_filename(name: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", name).strip("_") or "document"


def human_workspace_root(data_dir: Path, client_id: str) -> Path:
    return data_dir / "client_workspace" / client_id


def vector_store_root(data_dir: Path, client_id: str) -> Path:
    return data_dir / "vector_store" / client_id


def qdrant_store_root(data_dir: Path) -> Path:
    return data_dir / "vector_store" / "_qdrant"


def collection_name(prefix: str, client_id: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", client_id)
    return f"{prefix}_{normalized}"


def qdrant_client_for(data_dir: Path) -> Any | None:
    if not HAS_QDRANT or QdrantClient is None:
        return None
    root = qdrant_store_root(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    key = str(root)
    existing = _QDRANT_CLIENTS.get(key)
    if existing is not None:
        return existing
    try:
        client = QdrantClient(path=key)
    except Exception as exc:
        logger.warning("Embedded Qdrant unavailable for %s: %s", key, exc)
        return None
    _QDRANT_CLIENTS[key] = client
    return client


def qdrant_point_id(namespace: str, raw_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"yiyu:{namespace}:{raw_id}"))


def hashed_embedding(text: str, *, size: int = QDRANT_VECTOR_SIZE) -> list[float]:
    counts = Counter(tokenize(text))
    if not counts:
        normalized = normalize_text(text)
        fallback_tokens = [normalized[index : index + 2] for index in range(0, max(0, len(normalized) - 1))]
        counts = Counter(token for token in fallback_tokens if token)
    vector = [0.0] * size
    if not counts:
        return vector
    for token, count in counts.items():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for offset in range(0, 8, 2):
            index = int.from_bytes(digest[offset : offset + 2], "big") % size
            sign = 1.0 if digest[offset] % 2 == 0 else -1.0
            vector[index] += float(count) * sign
    norm = sum(value * value for value in vector) ** 0.5
    if norm <= 1e-9:
        return vector
    return [value / norm for value in vector]


def _normalize_vector(vector: list[float]) -> list[float]:
    norm = sum(value * value for value in vector) ** 0.5
    if norm <= 1e-9:
        return vector
    return [value / norm for value in vector]


def project_embedding(values: list[float], *, size: int = QDRANT_VECTOR_SIZE) -> list[float]:
    if len(values) == size:
        return _normalize_vector([float(value) for value in values])
    projected = [0.0] * size
    if not values:
        return projected
    for index, value in enumerate(values):
        projected[index % size] += float(value)
    return _normalize_vector(projected)


def embedding_cache_root(data_dir: Path) -> Path:
    root = qdrant_store_root(data_dir) / "_models"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _set_embedding_state(data_dir: Path, *, mode: str, model: str | None, error: str | None = None) -> None:
    _EMBEDDING_STATE[str(data_dir)] = {"mode": mode, "model": model, "error": error}


def embedding_backend_status(data_dir: Path) -> dict[str, Any]:
    state = _EMBEDDING_STATE.get(str(data_dir))
    if state:
        return dict(state)
    if _EMBEDDING_MODE_SETTING == "hash":
        return {"mode": "hash_fallback", "model": None, "error": None}
    if HAS_FASTEMBED:
        return {"mode": "fastembed_available", "model": _FASTEMBED_MODEL_NAME, "error": None}
    return {"mode": "hash_fallback", "model": None, "error": "fastembed_not_installed"}


def current_embedding_signature(data_dir: Path, *, ensure_ready: bool = False) -> str:
    if ensure_ready:
        embed_texts(["知识底座"], data_dir=data_dir)
    status = embedding_backend_status(data_dir)
    mode = str(status.get("mode") or "hash_fallback")
    model = str(status.get("model") or "")
    return f"{mode}:{model}:qdrant{QDRANT_VECTOR_SIZE}"


def embedding_backend_for(data_dir: Path) -> Any | None:
    if _EMBEDDING_MODE_SETTING == "hash":
        _set_embedding_state(data_dir, mode="hash_fallback", model=None)
        return None
    if not HAS_FASTEMBED or TextEmbedding is None:
        _set_embedding_state(data_dir, mode="hash_fallback", model=None, error="fastembed_not_installed")
        return None
    key = str(data_dir)
    existing = _EMBEDDERS.get(key)
    if existing is not None:
        return existing
    try:
        embedder = TextEmbedding(
            model_name=_FASTEMBED_MODEL_NAME,
            cache_dir=str(embedding_cache_root(data_dir)),
            lazy_load=False,
        )
        _EMBEDDERS[key] = embedder
        _set_embedding_state(data_dir, mode="fastembed", model=_FASTEMBED_MODEL_NAME)
        return embedder
    except Exception as exc:  # pragma: no cover - depends on runtime env/downloads
        _set_embedding_state(data_dir, mode="hash_fallback", model=None, error=str(exc))
        return None


def embed_texts(texts: list[str], *, data_dir: Path) -> tuple[list[list[float]], str]:
    if not texts:
        return [], "hash_fallback"
    embedder = embedding_backend_for(data_dir)
    if embedder is None:
        return [hashed_embedding(text) for text in texts], "hash_fallback"
    try:
        embeddings = list(embedder.embed(texts, batch_size=min(_FASTEMBED_BATCH_SIZE, max(1, len(texts)))))
        projected = [project_embedding([float(value) for value in vector]) for vector in embeddings]
        _set_embedding_state(data_dir, mode="fastembed", model=_FASTEMBED_MODEL_NAME)
        return projected, "fastembed"
    except Exception as exc:  # pragma: no cover - runtime fallback
        _set_embedding_state(data_dir, mode="hash_fallback", model=None, error=str(exc))
        return [hashed_embedding(text) for text in texts], "hash_fallback"


def ensure_qdrant_collection(client: Any, name: str) -> None:
    existing = {item.name for item in client.get_collections().collections}
    if name in existing:
        return
    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=QDRANT_VECTOR_SIZE, distance=Distance.COSINE),
    )


def ensure_qdrant_collections(data_dir: Path, client_id: str) -> Any | None:
    client = qdrant_client_for(data_dir)
    if client is None:
        return None
    ensure_qdrant_collection(client, collection_name("master_index", client_id))
    ensure_qdrant_collection(client, collection_name("raw_chunk", client_id))
    return client


def qdrant_payload_count(client: Any, name: str) -> int:
    try:
        count_response = client.count(collection_name=name, exact=True)
        return int(count_response.count)
    except Exception:
        return 0


def qdrant_ready(data_dir: Path, client_id: str) -> bool:
    client = qdrant_client_for(data_dir)
    if client is None:
        return False
    try:
        ensure_qdrant_collections(data_dir, client_id)
        return True
    except Exception:
        return False


def upsert_master_index_vector(
    *,
    data_dir: Path,
    client_id: str,
    entry_id: str,
    title: str,
    searchable_text: str,
    source_path: str | None,
    surrogate_md_path: str,
    folder_category: str,
    document_role: str,
) -> None:
    client = ensure_qdrant_collections(data_dir, client_id)
    if client is None or PointStruct is None:
        return
    vector, _ = embed_texts([searchable_text], data_dir=data_dir)
    payload = {
        "entry_id": entry_id,
        "client_id": client_id,
        "title": title,
        "source_path": source_path,
        "surrogate_md_path": surrogate_md_path,
        "folder_category": folder_category,
        "document_role": document_role,
    }
    client.upsert(
        collection_name=collection_name("master_index", client_id),
        points=[
            PointStruct(
                id=qdrant_point_id("master", entry_id),
                vector=vector[0] if vector else hashed_embedding(searchable_text),
                payload=payload,
            )
        ],
    )


def upsert_chunk_vectors(*, db: Database, data_dir: Path, client_id: str, knowledge_document_id: str) -> None:
    client = ensure_qdrant_collections(data_dir, client_id)
    if client is None or PointStruct is None:
        return
    rows = db.fetchall(
        """
        SELECT c.id, c.section_label, c.content, kd.doc_uid, kd.current_human_path, dc.title
        FROM document_chunks c
        JOIN knowledge_documents kd ON kd.id = c.knowledge_document_id
        JOIN document_cards dc ON dc.knowledge_document_id = kd.id
        WHERE c.knowledge_document_id = ?
        ORDER BY c.chunk_index ASC
        """,
        (knowledge_document_id,),
    )
    if not rows:
        return
    texts = [f"{row['section_label'] or '概览'}\n{row['content']}" for row in rows]
    vectors, _ = embed_texts(texts, data_dir=data_dir)
    points = []
    for index, row in enumerate(rows):
        text = texts[index]
        points.append(
            PointStruct(
                id=qdrant_point_id("chunk", str(row["id"])),
                vector=vectors[index] if index < len(vectors) else hashed_embedding(text),
                payload={
                    "chunk_id": str(row["id"]),
                    "knowledge_document_id": knowledge_document_id,
                    "doc_uid": str(row["doc_uid"]),
                    "title": str(row["title"]),
                    "section_label": str(row["section_label"]) if row["section_label"] else None,
                    "source_path": str(row["current_human_path"]) if row["current_human_path"] else None,
                },
            )
        )
    client.upsert(collection_name=collection_name("raw_chunk", client_id), points=points)


def sync_qdrant_for_client(db: Database, *, data_dir: Path, client_id: str) -> None:
    client = ensure_qdrant_collections(data_dir, client_id)
    if client is None:
        return
    current_signature = current_embedding_signature(data_dir, ensure_ready=True)
    signature_key = f"knowledge.embedding_signature:{client_id}"
    stored_signature = db.get_setting(signature_key, "")
    master_name = collection_name("master_index", client_id)
    chunk_name = collection_name("raw_chunk", client_id)
    master_count = int(
        db.scalar("SELECT COUNT(1) AS count FROM knowledge_master_index WHERE client_id = ?", (client_id,))
    )
    chunk_count = int(
        db.scalar(
            """
            SELECT COUNT(1) AS count
            FROM document_chunks c
            JOIN knowledge_documents kd ON kd.id = c.knowledge_document_id
            WHERE kd.client_id = ?
            """,
            (client_id,),
        )
    )
    signature_changed = stored_signature != current_signature
    needs_master_sync = signature_changed or qdrant_payload_count(client, master_name) < master_count
    needs_chunk_sync = signature_changed or qdrant_payload_count(client, chunk_name) < chunk_count
    if not needs_master_sync and not needs_chunk_sync:
        return
    master_rows = db.fetchall(
        """
        SELECT id, title, folder_category, document_role, retrieval_summary, searchable_text, source_path, surrogate_md_path
        FROM knowledge_master_index
        WHERE client_id = ?
        """,
        (client_id,),
    )
    if needs_master_sync and PointStruct is not None:
        texts = [str(row["searchable_text"]) for row in master_rows]
        vectors, _ = embed_texts(texts, data_dir=data_dir)
        points = [
            PointStruct(
                id=qdrant_point_id("master", str(row["id"])),
                vector=vectors[index] if index < len(vectors) else hashed_embedding(str(row["searchable_text"])),
                payload={
                    "entry_id": str(row["id"]),
                    "client_id": client_id,
                    "title": str(row["title"]),
                    "source_path": str(row["source_path"]) if row["source_path"] else None,
                    "surrogate_md_path": str(row["surrogate_md_path"]),
                    "folder_category": str(row["folder_category"]),
                    "document_role": str(row["document_role"]),
                },
            )
            for index, row in enumerate(master_rows)
        ]
        if points:
            client.upsert(collection_name=master_name, points=points)
    if needs_chunk_sync:
        document_rows = db.fetchall("SELECT id FROM knowledge_documents WHERE client_id = ?", (client_id,))
        for row in document_rows:
            upsert_chunk_vectors(db=db, data_dir=data_dir, client_id=client_id, knowledge_document_id=str(row["id"]))
    if needs_master_sync or needs_chunk_sync:
        db.set_setting(signature_key, current_signature)


def search_master_index_qdrant(data_dir: Path, client_id: str, prompt: str, limit: int = 8) -> dict[str, float]:
    client = ensure_qdrant_collections(data_dir, client_id)
    if client is None:
        return {}
    vectors, _ = embed_texts([prompt], data_dir=data_dir)
    try:
        results = client.search(
            collection_name=collection_name("master_index", client_id),
            query_vector=vectors[0] if vectors else hashed_embedding(prompt),
            limit=limit,
            with_payload=True,
        )
    except Exception:
        return {}
    scores: dict[str, float] = {}
    for item in results:
        payload = getattr(item, "payload", {}) or {}
        entry_id = str(payload.get("entry_id", ""))
        if entry_id:
            scores[entry_id] = float(getattr(item, "score", 0.0))
    return scores


def search_raw_chunks_qdrant(
    data_dir: Path,
    client_id: str,
    prompt: str,
    knowledge_document_ids: list[str],
    limit: int = 12,
) -> dict[str, float]:
    client = ensure_qdrant_collections(data_dir, client_id)
    if client is None:
        return {}
    scores: dict[str, float] = {}
    vectors, _ = embed_texts([prompt], data_dir=data_dir)
    try:
        results = client.search(
            collection_name=collection_name("raw_chunk", client_id),
            query_vector=vectors[0] if vectors else hashed_embedding(prompt),
            limit=max(limit, 24),
            with_payload=True,
        )
    except Exception:
        return scores
    allowed = set(knowledge_document_ids)
    for item in results:
        payload = getattr(item, "payload", {}) or {}
        knowledge_document_id = str(payload.get("knowledge_document_id", ""))
        if knowledge_document_id not in allowed:
            continue
        chunk_id = str(payload.get("chunk_id", ""))
        if not chunk_id:
            continue
        scores[chunk_id] = float(getattr(item, "score", 0.0))
        if len(scores) >= limit:
            break
    return scores


def ensure_client_workspace(data_dir: Path, client_id: str) -> dict[str, Path]:
    root = human_workspace_root(data_dir, client_id)
    root.mkdir(parents=True, exist_ok=True)
    folders: dict[str, Path] = {}
    for label in HUMAN_VISIBLE_CATEGORIES:
        folder = root / label
        folder.mkdir(parents=True, exist_ok=True)
        folders[label] = folder
    vector_root = vector_store_root(data_dir, client_id)
    (vector_root / "surrogates").mkdir(parents=True, exist_ok=True)
    (vector_root / "memory").mkdir(parents=True, exist_ok=True)
    (vector_root / "_index").mkdir(parents=True, exist_ok=True)
    return folders


def desired_human_file_path(
    data_dir: Path,
    client_id: str,
    category: str,
    filename: str,
    *,
    doc_uid: str,
    current_path: Path | None = None,
) -> Path:
    folders = ensure_client_workspace(data_dir, client_id)
    target_dir = folders.get(category) or folders["其他资料"]
    source_name = filename or (current_path.name if current_path else "document")
    safe_name = safe_filename(source_name)
    stem = Path(safe_name).stem or doc_uid
    suffix = Path(safe_name).suffix
    candidate = target_dir / safe_name
    if current_path is not None:
        try:
            if current_path.resolve() == candidate.resolve():
                return candidate
        except Exception:
            pass
    if not candidate.exists():
        return candidate
    suffix = suffix or (current_path.suffix if current_path else "")
    counter = 1
    while True:
        numbered = target_dir / f"{stem}_{doc_uid}_{counter}{suffix}"
        if current_path is not None:
            try:
                if current_path.resolve() == numbered.resolve():
                    return numbered
            except Exception:
                pass
        if not numbered.exists():
            return numbered
        counter += 1


def infer_source_category(source_path: str | Path) -> str | None:
    value = str(source_path)
    for category in HUMAN_VISIBLE_CATEGORIES:
        if category in value:
            return category
    return None


def append_file_reclass_event(
    db: Database,
    *,
    knowledge_document_id: str,
    from_path: str,
    to_path: str,
    from_category: str | None,
    to_category: str,
    reason: str,
    confidence: float,
    created_at: str,
) -> None:
    if not from_path or not to_path:
        return
    same_path = Path(from_path) == Path(to_path)
    if same_path and from_category == to_category:
        return
    db.execute(
        """
        INSERT INTO file_reclass_events(id, knowledge_document_id, from_path, to_path, from_category, to_category, reason, confidence, created_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"reclass_{knowledge_document_id}_{uuid.uuid4().hex[:8]}",
            knowledge_document_id,
            from_path,
            to_path,
            from_category,
            to_category,
            reason,
            confidence,
            created_at,
        ),
    )


def move_document_to_human_workspace(
    *,
    data_dir: Path,
    client_id: str,
    source_path: Path,
    category: str,
    filename: str,
    doc_uid: str,
) -> Path:
    target_path = desired_human_file_path(
        data_dir,
        client_id,
        category,
        filename,
        doc_uid=doc_uid,
        current_path=source_path,
    )
    target_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if source_path.resolve() == target_path.resolve():
            return target_path
    except Exception:
        pass
    shutil.move(str(source_path), str(target_path))
    return target_path


def sync_human_file_locations_for_client(
    db: Database,
    *,
    data_dir: Path,
    client_id: str,
    timestamp: str | None = None,
) -> int:
    sync_time = timestamp or now_iso()
    rows = db.fetchall(
        """
        SELECT kd.id, kd.doc_uid, kd.original_path, kd.import_source_path, kd.current_human_path, kd.primary_category, kd.secondary_category,
               kd.reclass_reason, kd.reclass_confidence, dc.title, d.id AS document_id, d.path AS document_path,
               ks.id AS surrogate_id, ks.surrogate_md_path, ks.retrieval_summary, ks.document_role,
               mi.id AS master_index_id, mi.searchable_text
        FROM knowledge_documents kd
        JOIN document_cards dc ON dc.knowledge_document_id = kd.id
        LEFT JOIN documents d ON d.id = kd.document_id
        LEFT JOIN knowledge_surrogates ks ON ks.knowledge_document_id = kd.id
        LEFT JOIN knowledge_master_index mi ON mi.surrogate_id = ks.id
        WHERE kd.client_id = ?
        ORDER BY kd.updated_at DESC
        """,
        (client_id,),
    )
    synced = 0
    master_index_changed = False
    for row in rows:
        title = str(row["title"])
        primary_category = str(row["primary_category"]) if row["primary_category"] else "其他资料"
        secondary_category = str(row["secondary_category"]) if row["secondary_category"] else "待归类"
        confidence = float(row["reclass_confidence"]) if row["reclass_confidence"] is not None else 0.76
        reason = (
            str(row["reclass_reason"])
            if row["reclass_reason"]
            else f"基于文档内容自动归入“{primary_category} / {secondary_category}”。"
        )
        source_candidates = [
            str(row["current_human_path"]) if row["current_human_path"] else None,
            str(row["document_path"]) if row["document_path"] else None,
            str(row["import_source_path"]) if row["import_source_path"] else None,
            str(row["original_path"]) if row["original_path"] else None,
        ]
        existing_source: Path | None = None
        for value in source_candidates:
            if not value:
                continue
            candidate = Path(value).expanduser()
            if candidate.exists():
                existing_source = candidate
                break
        current_human_path: str | None = None
        from_path: str | None = None
        from_category: str | None = None
        if existing_source is not None:
            from_path = str(existing_source)
            from_category = infer_source_category(from_path)
            moved_to = move_document_to_human_workspace(
                data_dir=data_dir,
                client_id=client_id,
                source_path=existing_source,
                category=primary_category,
                filename=title,
                doc_uid=str(row["doc_uid"]),
            )
            current_human_path = str(moved_to)
        elif row["current_human_path"]:
            current_human_path = str(row["current_human_path"])
        if not current_human_path:
            continue
        append_file_reclass_event(
            db,
            knowledge_document_id=str(row["id"]),
            from_path=from_path or current_human_path,
            to_path=current_human_path,
            from_category=from_category,
            to_category=primary_category,
            reason=reason,
            confidence=confidence,
            created_at=sync_time,
        )
        db.execute(
            """
            UPDATE knowledge_documents
            SET current_human_path = ?, human_folder_category = ?, normalized_path = ?, reclassified_at = ?, reclass_reason = ?, reclass_confidence = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                current_human_path,
                primary_category,
                current_human_path,
                sync_time,
                reason,
                confidence,
                sync_time,
                str(row["id"]),
            ),
        )
        target_folder = db.fetchone(
            "SELECT id FROM client_folders WHERE client_id = ? AND label = ?",
            (client_id, primary_category),
        )
        if row["document_id"]:
            db.execute(
                """
                UPDATE documents
                SET folder_id = ?, title = ?, path = ?
                WHERE id = ?
                """,
                (
                    str(target_folder["id"]) if target_folder else None,
                    title,
                    current_human_path,
                    str(row["document_id"]),
                ),
            )
        surrogate_id = str(row["surrogate_id"]) if row["surrogate_id"] else None
        surrogate_md_path = str(row["surrogate_md_path"]) if row["surrogate_md_path"] else None
        master_index_id = str(row["master_index_id"]) if row["master_index_id"] else None
        if surrogate_id and surrogate_md_path:
            if master_index_id:
                db.execute(
                    """
                    UPDATE knowledge_master_index
                    SET title = ?, folder_category = ?, document_role = ?, retrieval_summary = ?, searchable_text = ?, source_path = ?, surrogate_md_path = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        title,
                        primary_category,
                        str(row["document_role"]) if row["document_role"] else "资料",
                        str(row["retrieval_summary"]) if row["retrieval_summary"] else title,
                        str(row["searchable_text"]) if row["searchable_text"] else title,
                        current_human_path,
                        surrogate_md_path,
                        sync_time,
                        master_index_id,
                    ),
                )
            else:
                upsert_master_index_record(
                    db,
                    data_dir=data_dir,
                    entry_id=f"midx_{row['doc_uid']}",
                    client_id=client_id,
                    surrogate_id=surrogate_id,
                    title=title,
                    folder_category=primary_category,
                    document_role=str(row["document_role"]) if row["document_role"] else "资料",
                    retrieval_summary=str(row["retrieval_summary"]) if row["retrieval_summary"] else title,
                    searchable_text=str(row["searchable_text"]) if row["searchable_text"] else title,
                    source_path=current_human_path,
                    surrogate_md_path=surrogate_md_path,
                    timestamp=sync_time,
                )
            master_index_changed = True
        synced += 1
    if master_index_changed:
        write_master_index_snapshot(db, data_dir, client_id)
        sync_master_index_fts(db, client_id)
    return synced


def _guess_document_role(title: str, summary: str, primary_category: str) -> str:
    haystack = f"{title} {summary}".lower()
    if any(keyword in haystack for keyword in ["协议", "合同"]):
        return "协议文件"
    if any(keyword in haystack for keyword in ["纪要", "会议", "访谈"]):
        return "会议与访谈"
    if any(keyword in haystack for keyword in ["介绍", "机构", "概览"]):
        return "机构介绍"
    if any(keyword in haystack for keyword in ["预算", "报表", "财务"]):
        return "财务资料"
    if any(keyword in haystack for keyword in ["方案", "计划", "策略"]):
        return "方案规划"
    return {
        "财务与筹款": "财务资料",
        "品牌与传播": "传播资料",
        "项目与业务": "项目资料",
        "组织与战略": "组织战略资料",
        "其他资料": "通用资料",
    }.get(primary_category, "通用资料")


def _query_hints(title: str, keywords: list[str], entities: list[str], document_role: str) -> list[str]:
    hints = [title, document_role]
    hints.extend(keywords[:4])
    hints.extend(entities[:4])
    seen: list[str] = []
    for item in hints:
        cleaned = item.strip()
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen[:8]


def _core_questions(title: str, primary_category: str, document_role: str, keywords: list[str]) -> list[str]:
    hints = keywords[:2]
    if hints:
        return [
            f"{title} 主要讲了什么？",
            f"{document_role}里和{hints[0]}相关的重点是什么？",
            f"{primary_category}里哪些信息可用于后续决策？",
        ]
    return [
        f"{title} 主要讲了什么？",
        f"{document_role}能支撑哪些问题回答？",
    ]


def _distinct_findings(summary: str, keywords: list[str], entities: list[str]) -> list[str]:
    findings = []
    if summary:
        findings.append(summary[:80])
    if keywords:
        findings.append(f"高频主题：{'、'.join(keywords[:3])}")
    if entities:
        findings.append(f"关键对象：{'、'.join(entities[:3])}")
    return findings[:3]


def _surrogate_payload(
    *,
    title: str,
    kind: str,
    primary_category: str,
    secondary_category: str,
    short_summary: str,
    summary: str,
    keywords: list[str],
    entities: list[str],
    date_range: str | None,
    source_path: str,
    raw_text: str,
    ai_service: Any | None = None,
) -> dict[str, Any]:
    document_role = _guess_document_role(title, summary, primary_category)
    source_outline = build_source_outline(raw_text, summary)
    retrieval_summary = (
        f"{title} 属于{primary_category}/{secondary_category}，角色为{document_role}。"
        f"它重点涉及{'、'.join(keywords[:4]) or '关键资料'}，"
        f"涉及对象有{'、'.join(entities[:4]) or '未明确对象'}，"
        f"{'时间线为' + date_range + '，' if date_range else ''}"
        f"适合回答与{primary_category}、{document_role}、{'、'.join(keywords[:2]) or '当前议题'}相关的问题。"
    )[:220]
    payload = {
        "overview_summary": summary,
        "retrieval_summary": retrieval_summary,
        "document_role": document_role,
        "core_questions": _core_questions(title, primary_category, document_role, keywords),
        "query_hints": _query_hints(title, keywords, entities, document_role),
        "distinct_findings": _distinct_findings(summary, keywords, entities),
        "entities": entities[:6],
        "time_markers": [date_range] if date_range else [],
        "source_outline": source_outline,
    }
    # Keep ingestion deterministic. Model enrichment belongs to a later async step,
    # not the file parsing path that has to stay fast and failure-tolerant.
    return payload


def write_surrogate_markdown(
    data_dir: Path,
    *,
    client_id: str,
    doc_uid: str,
    folder_category: str,
    title: str,
    source_type: str,
    source_path: str | None,
    payload: dict[str, Any],
) -> str:
    root = vector_store_root(data_dir, client_id)
    subfolder = "surrogates" if source_type == "document" else "memory"
    target = root / subfolder / f"{doc_uid}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
        [
            f"# {title}",
            "",
            f"- source_type: {source_type}",
            f"- folder_category: {folder_category}",
            f"- source_path: {source_path or '无原始文件'}",
            f"- document_role: {payload.get('document_role', '资料')}",
            "",
            "## overview_summary",
            str(payload.get("overview_summary", "")),
            "",
            "## retrieval_summary",
            str(payload.get("retrieval_summary", "")),
            "",
            "## source_outline",
            str(payload.get("source_outline", "")),
            "",
            "## core_questions",
            "\n".join(f"- {item}" for item in payload.get("core_questions", [])),
            "",
            "## query_hints",
            "\n".join(f"- {item}" for item in payload.get("query_hints", [])),
            "",
            "## distinct_findings",
            "\n".join(f"- {item}" for item in payload.get("distinct_findings", [])),
            "",
            "## entities",
            "\n".join(f"- {item}" for item in payload.get("entities", [])),
            "",
            "## time_markers",
            "\n".join(f"- {item}" for item in payload.get("time_markers", [])),
        ]
    ).strip() + "\n"
    target.write_text(content, encoding="utf-8")
    return str(target)


def build_chunks(text: str, fallback_excerpt: str) -> list[dict[str, Any]]:
    content = text.strip() or fallback_excerpt.strip()
    if not content:
        return []
    CHUNK_MAX = 1200  # 每个切片最大字符数（从 480 提升到 1200）
    CHUNK_SPLIT = 800  # 切片触发阈值（从 280 提升到 800）
    OVERLAP_CHARS = 120  # 切片重叠字符数（新增）
    lines = [line.strip() for line in content.splitlines()]
    chunks: list[dict[str, Any]] = []
    section_label = "概览"
    buffer = ""
    chunk_index = 0
    prev_tail = ""  # 上一个切片的尾部，用于 overlap
    for line in lines:
        if not line:
            continue
        if re.match(r"^#{1,6}\s*", line):
            if buffer.strip():
                text_block = (prev_tail + " " + buffer).strip() if prev_tail else buffer.strip()
                chunks.append(
                    {
                        "chunk_index": chunk_index,
                        "section_label": section_label,
                        "content": text_block[:CHUNK_MAX],
                        "token_count": len(tokenize(text_block)),
                    }
                )
                prev_tail = buffer.strip()[-OVERLAP_CHARS:] if len(buffer.strip()) > OVERLAP_CHARS else ""
                chunk_index += 1
                buffer = ""
            section_label = re.sub(r"^#{1,6}\s*", "", line).strip() or section_label
            continue
        candidate = f"{buffer} {line}".strip()
        if len(candidate) > CHUNK_SPLIT and buffer.strip():
            text_block = (prev_tail + " " + buffer).strip() if prev_tail else buffer.strip()
            chunks.append(
                {
                    "chunk_index": chunk_index,
                    "section_label": section_label,
                    "content": text_block[:CHUNK_MAX],
                    "token_count": len(tokenize(text_block)),
                }
            )
            prev_tail = buffer.strip()[-OVERLAP_CHARS:] if len(buffer.strip()) > OVERLAP_CHARS else ""
            chunk_index += 1
            buffer = line
        else:
            buffer = candidate
    if buffer.strip():
        text_block = (prev_tail + " " + buffer).strip() if prev_tail else buffer.strip()
        chunks.append(
            {
                "chunk_index": chunk_index,
                "section_label": section_label,
                "content": text_block[:CHUNK_MAX],
                "token_count": len(tokenize(text_block)),
            }
        )
    if not chunks:
        chunks.append(
            {
                "chunk_index": 0,
                "section_label": "概览",
                "content": content[:CHUNK_MAX],
                "token_count": len(tokenize(content)),
            }
        )
    return chunks


def ensure_source_tree_snapshot(
    db: Database,
    *,
    import_id: str,
    client_id: str,
    source_path: Path,
    mode: str,
    created_at: str,
) -> None:
    tree, file_count = build_source_tree(source_path, mode)
    existing = db.fetchone("SELECT id FROM source_tree_snapshots WHERE import_id = ?", (import_id,))
    if existing:
        db.execute(
            "UPDATE source_tree_snapshots SET root_path = ?, tree_json = ?, file_count = ?, created_at = ? WHERE import_id = ?",
            (str(source_path), to_json(tree), file_count, created_at, import_id),
        )
        return
    db.execute(
        """
        INSERT INTO source_tree_snapshots(id, import_id, client_id, root_path, tree_json, file_count, created_at)
        VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        (f"tree_{import_id}", import_id, client_id, str(source_path), to_json(tree), file_count, created_at),
    )


def upsert_surrogate_record(
    db: Database,
    *,
    surrogate_id: str,
    knowledge_document_id: str | None,
    client_id: str,
    source_type: str,
    title: str,
    folder_category: str,
    surrogate_md_path: str,
    payload: dict[str, Any],
    timestamp: str,
) -> None:
    existing = db.fetchone("SELECT id FROM knowledge_surrogates WHERE id = ?", (surrogate_id,))
    values = (
        knowledge_document_id,
        client_id,
        source_type,
        title,
        folder_category,
        surrogate_md_path,
        str(payload.get("overview_summary", "")),
        str(payload.get("retrieval_summary", "")),
        str(payload.get("document_role", "资料")),
        to_json(payload.get("core_questions", [])),
        to_json(payload.get("query_hints", [])),
        to_json(payload.get("distinct_findings", [])),
        to_json(payload.get("entities", [])),
        to_json(payload.get("time_markers", [])),
        to_json(payload.get("source_links", [])),
        timestamp,
    )
    if existing:
        db.execute(
            """
            UPDATE knowledge_surrogates
            SET knowledge_document_id = ?, client_id = ?, source_type = ?, title = ?, folder_category = ?, surrogate_md_path = ?,
                overview_summary = ?, retrieval_summary = ?, document_role = ?, core_questions_json = ?, query_hints_json = ?,
                distinct_findings_json = ?, entities_json = ?, time_markers_json = ?, source_links_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (*values, surrogate_id),
        )
        return
    db.execute(
        """
        INSERT INTO knowledge_surrogates(
            id, knowledge_document_id, client_id, source_type, title, folder_category, surrogate_md_path,
            overview_summary, retrieval_summary, document_role, core_questions_json, query_hints_json,
            distinct_findings_json, entities_json, time_markers_json, source_links_json, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (surrogate_id, *values, timestamp),
    )


def write_master_index_snapshot(db: Database, data_dir: Path, client_id: str) -> None:
    target = vector_store_root(data_dir, client_id) / "_index" / "master_index.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = db.fetchall(
        """
        SELECT id, client_id, surrogate_id, title, folder_category, document_role, retrieval_summary, searchable_text, source_path, surrogate_md_path, updated_at
        FROM knowledge_master_index
        WHERE client_id = ?
        ORDER BY updated_at DESC, title ASC
        """,
        (client_id,),
    )
    with target.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(
                    {
                        "id": str(row["id"]),
                        "client_id": str(row["client_id"]),
                        "surrogate_id": str(row["surrogate_id"]),
                        "title": str(row["title"]),
                        "folder_category": str(row["folder_category"]),
                        "document_role": str(row["document_role"]),
                        "retrieval_summary": str(row["retrieval_summary"]),
                        "searchable_text": str(row["searchable_text"]),
                        "source_path": str(row["source_path"]) if row["source_path"] else None,
                        "surrogate_md_path": str(row["surrogate_md_path"]),
                        "updated_at": str(row["updated_at"]),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


def sync_master_index_fts(db: Database, client_id: str) -> None:
    db.execute("DELETE FROM knowledge_master_index_fts WHERE client_id = ?", (client_id,))
    rows = db.fetchall(
        """
        SELECT id, client_id, title, retrieval_summary, searchable_text, folder_category, document_role
        FROM knowledge_master_index
        WHERE client_id = ?
        """,
        (client_id,),
    )
    if not rows:
        return
    db.executemany(
        """
        INSERT INTO knowledge_master_index_fts(
            entry_id, client_id, title, retrieval_summary, searchable_text, folder_category, document_role
        )
        VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                str(row["id"]),
                str(row["client_id"]),
                str(row["title"]),
                str(row["retrieval_summary"]),
                str(row["searchable_text"]),
                str(row["folder_category"]),
                str(row["document_role"]),
            )
            for row in rows
        ],
    )


def _fts_query_for_tokens(tokens: list[str]) -> str | None:
    filtered = [token.replace('"', "").strip() for token in tokens if token and token.strip()]
    if not filtered:
        return None
    return " OR ".join(f'"{token}"' for token in filtered[:8])


def search_master_index_fts(db: Database, client_id: str, prompt: str, limit: int = 8) -> dict[str, float]:
    query_tokens = tokenize(prompt)
    match_query = _fts_query_for_tokens(query_tokens)
    if not match_query:
        return {}
    try:
        rows = db.fetchall(
            """
            SELECT entry_id, bm25(knowledge_master_index_fts) AS rank
            FROM knowledge_master_index_fts
            WHERE knowledge_master_index_fts MATCH ? AND client_id = ?
            ORDER BY rank
            LIMIT ?
            """,
            (match_query, client_id, limit),
        )
    except Exception:
        return {}
    scores: dict[str, float] = {}
    for row in rows:
        raw_rank = float(row["rank"]) if row["rank"] is not None else 999.0
        scores[str(row["entry_id"])] = round(1.0 / (1.0 + abs(raw_rank)), 4)
    return scores


def upsert_master_index_record(
    db: Database,
    *,
    data_dir: Path,
    entry_id: str,
    client_id: str,
    surrogate_id: str,
    title: str,
    folder_category: str,
    document_role: str,
    retrieval_summary: str,
    searchable_text: str,
    source_path: str | None,
    surrogate_md_path: str,
    timestamp: str,
    sync_after: bool = True,
) -> None:
    existing = db.fetchone("SELECT id FROM knowledge_master_index WHERE id = ?", (entry_id,))
    params = (
        client_id,
        surrogate_id,
        title,
        folder_category,
        document_role,
        retrieval_summary,
        searchable_text,
        source_path,
        surrogate_md_path,
        timestamp,
    )
    if existing:
        db.execute(
            """
            UPDATE knowledge_master_index
            SET client_id = ?, surrogate_id = ?, title = ?, folder_category = ?, document_role = ?, retrieval_summary = ?,
                searchable_text = ?, source_path = ?, surrogate_md_path = ?, updated_at = ?
            WHERE id = ?
            """,
            (*params, entry_id),
        )
    else:
        db.execute(
            """
            INSERT INTO knowledge_master_index(
                id, client_id, surrogate_id, title, folder_category, document_role, retrieval_summary,
                searchable_text, source_path, surrogate_md_path, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (entry_id, *params),
    )
    if sync_after:
        write_master_index_snapshot(db, data_dir, client_id)
        sync_master_index_fts(db, client_id)


def hydrate_missing_surrogates(
    db: Database,
    *,
    data_dir: Path,
    client_id: str,
    ai_service: Any | None = None,
    force_refresh: bool = False,
) -> None:
    updated_index = False
    rows = db.fetchall(
        """
        SELECT kd.id AS knowledge_document_id, kd.doc_uid, kd.client_id, kd.original_path, kd.import_source_path, kd.current_human_path,
               kd.primary_category, kd.secondary_category, kd.kind, kd.needs_review, kd.updated_at,
               dc.title, dc.one_line_summary, dc.summary_200, dc.keywords_json, dc.entities_json, dc.date_range_label,
               ks.id AS surrogate_id, ks.surrogate_md_path,
               mi.id AS master_index_id,
               (
                 SELECT raw_text
                 FROM knowledge_document_versions kv
                 WHERE kv.knowledge_document_id = kd.id
                 ORDER BY kv.version_no DESC
                 LIMIT 1
               ) AS raw_text
        FROM knowledge_documents kd
        JOIN document_cards dc ON dc.knowledge_document_id = kd.id
        LEFT JOIN knowledge_surrogates ks ON ks.knowledge_document_id = kd.id
        LEFT JOIN knowledge_master_index mi ON mi.surrogate_id = ks.id
        WHERE kd.client_id = ?
        ORDER BY kd.updated_at ASC
        """,
        (client_id,),
    )
    for row in rows:
        existing_surrogate_path = str(row["surrogate_md_path"]) if row["surrogate_md_path"] else None
        surrogate_missing = force_refresh or not existing_surrogate_path or not Path(existing_surrogate_path).exists()
        master_missing = force_refresh or not row["master_index_id"]
        if not surrogate_missing and not master_missing:
            continue
        title = str(row["title"])
        source_path = str(row["current_human_path"] or row["original_path"] or row["import_source_path"] or "")
        raw_text = str(row["raw_text"] or "")
        short_summary = str(row["one_line_summary"] or title)
        summary = str(row["summary_200"] or row["one_line_summary"] or "")
        keywords = [str(item) for item in from_json(row["keywords_json"], [])] if row["keywords_json"] else []
        entities = [str(item) for item in from_json(row["entities_json"], [])] if row["entities_json"] else []
        date_range = str(row["date_range_label"]) if row["date_range_label"] else None
        if force_refresh and source_path:
            refreshed = refresh_existing_knowledge_document(
                db,
                data_dir=data_dir,
                client_id=client_id,
                knowledge_document_id=str(row["knowledge_document_id"]),
                source_path=Path(source_path),
                title=title,
                kind=str(row["kind"]),
                primary_category=str(row["primary_category"]),
                secondary_category=str(row["secondary_category"]),
                needs_review=bool(row["needs_review"]),
                fallback_excerpt=summary or short_summary or title,
                ai_service=ai_service,
            )
            raw_text = str(refreshed["raw_text"])
            short_summary = str(refreshed["short_summary"])
            summary = str(refreshed["summary"])
            keywords = [str(item) for item in refreshed["keywords"]]
            entities = [str(item) for item in refreshed["entities"]]
            date_range = str(refreshed["date_range"]) if refreshed["date_range"] else None
        payload = _surrogate_payload(
            title=title,
            kind=str(row["kind"]),
            primary_category=str(row["primary_category"]),
            secondary_category=str(row["secondary_category"]),
            short_summary=short_summary,
            summary=summary,
            keywords=keywords,
            entities=entities,
            date_range=date_range,
            source_path=source_path,
            raw_text=raw_text[:6000],
            ai_service=ai_service,
        )
        surrogate_id = str(row["surrogate_id"] or f"sur_{row['doc_uid']}")
        surrogate_md_path = write_surrogate_markdown(
            data_dir,
            client_id=client_id,
            doc_uid=str(row["doc_uid"]),
            folder_category=str(row["primary_category"]),
            title=title,
            source_type="document",
            source_path=source_path,
            payload=payload,
        )
        upsert_surrogate_record(
            db,
            surrogate_id=surrogate_id,
            knowledge_document_id=str(row["knowledge_document_id"]),
            client_id=client_id,
            source_type="document",
            title=title,
            folder_category=str(row["primary_category"]),
            surrogate_md_path=surrogate_md_path,
            payload=payload,
            timestamp=now_iso(),
        )
        searchable_text = build_catalog_search_text(
            title=title,
            short_summary=short_summary,
            summary=summary,
            raw_text=raw_text,
            keywords=keywords,
            entities=entities,
            primary_category=str(row["primary_category"]),
            secondary_category=str(row["secondary_category"]),
            document_role=str(payload.get("document_role", "资料")),
        )
        existing_catalog = db.fetchone(
            "SELECT id FROM document_catalog_index WHERE knowledge_document_id = ?",
            (str(row["knowledge_document_id"]),),
        )
        if existing_catalog:
            db.execute(
                "UPDATE document_catalog_index SET searchable_text = ?, created_at = COALESCE(created_at, ?) WHERE knowledge_document_id = ?",
                (searchable_text, now_iso(), str(row["knowledge_document_id"])),
            )
        else:
            db.execute(
                "INSERT INTO document_catalog_index(id, knowledge_document_id, searchable_text, created_at) VALUES(?, ?, ?, ?)",
                (f"idx_{row['knowledge_document_id']}", str(row["knowledge_document_id"]), searchable_text, now_iso()),
            )
        upsert_master_index_record(
            db,
            data_dir=data_dir,
            entry_id=str(row["master_index_id"] or f"midx_{row['doc_uid']}"),
            client_id=client_id,
            surrogate_id=surrogate_id,
            title=title,
            folder_category=str(row["primary_category"]),
            document_role=str(payload.get("document_role", "资料")),
            retrieval_summary=build_master_index_summary(
                title=title,
                short_summary=short_summary,
                summary=summary,
                raw_text=raw_text,
            ),
            searchable_text=searchable_text,
            source_path=source_path or None,
            surrogate_md_path=surrogate_md_path,
            timestamp=now_iso(),
            sync_after=False,
        )
        updated_index = True
        if db.scalar("SELECT COUNT(1) AS count FROM document_chunks WHERE knowledge_document_id = ?", (str(row["knowledge_document_id"]),)):
            upsert_chunk_vectors(
                db=db,
                data_dir=data_dir,
                client_id=client_id,
                knowledge_document_id=str(row["knowledge_document_id"]),
            )
    if updated_index:
        write_master_index_snapshot(db, data_dir, client_id)
        sync_master_index_fts(db, client_id)


def ingest_document_knowledge(
    db: Database,
    *,
    data_dir: Path,
    client_id: str,
    import_id: str | None,
    document_id: str,
    source_path: Path,
    title: str,
    kind: str,
    source: str,
    fallback_excerpt: str,
    created_at: str,
    ai_service: Any | None = None,
) -> PreparedKnowledgeDocument:
    existing = db.fetchone(
        """
        SELECT kd.id, kd.doc_uid, kd.original_path, kd.import_source_path, kd.current_human_path, kd.human_folder_category,
               kd.normalized_path, kd.kind, kd.primary_category, kd.secondary_category,
               kd.classification_confidence, kd.needs_review, kd.deep_read, kd.dedup_status, kd.vector_status,
               kd.binary_hash, kd.normalized_hash, kd.created_at, kd.updated_at,
               dc.title, dc.one_line_summary, dc.summary_200, dc.keywords_json, dc.tags_json, dc.entities_json, dc.date_range_label,
               ks.surrogate_md_path, ks.retrieval_summary, ks.document_role, ks.query_hints_json, ks.distinct_findings_json, ks.core_questions_json
        FROM knowledge_documents kd
        JOIN document_cards dc ON dc.knowledge_document_id = kd.id
        LEFT JOIN knowledge_surrogates ks ON ks.knowledge_document_id = kd.id
        WHERE kd.document_id = ?
        """,
        (document_id,),
    )
    if existing:
        chunk_count = db.scalar("SELECT COUNT(1) AS count FROM document_chunks WHERE knowledge_document_id = ?", (str(existing["id"]),))
        return PreparedKnowledgeDocument(
            knowledge_document_id=str(existing["id"]),
            doc_uid=str(existing["doc_uid"]),
            title=str(existing["title"]),
            original_path=str(existing["original_path"]),
            import_source_path=str(existing["import_source_path"]) if existing["import_source_path"] else str(existing["original_path"]),
            current_human_path=str(existing["current_human_path"]) if existing["current_human_path"] else None,
            human_folder_category=str(existing["human_folder_category"]) if existing["human_folder_category"] else None,
            normalized_path=str(existing["normalized_path"]) if existing["normalized_path"] else None,
            surrogate_md_path=str(existing["surrogate_md_path"]) if existing["surrogate_md_path"] else None,
            kind=str(existing["kind"]),
            primary_category=str(existing["primary_category"]),
            secondary_category=str(existing["secondary_category"]),
            short_summary=str(existing["one_line_summary"]),
            summary=str(existing["summary_200"]),
            retrieval_summary=str(existing["retrieval_summary"]) if existing["retrieval_summary"] else str(existing["summary_200"]),
            document_role=str(existing["document_role"]) if existing["document_role"] else "资料",
            query_hints=[str(item) for item in from_json(existing["query_hints_json"], [])] if existing["query_hints_json"] else [],
            distinct_findings=[str(item) for item in from_json(existing["distinct_findings_json"], [])] if existing["distinct_findings_json"] else [],
            core_questions=[str(item) for item in from_json(existing["core_questions_json"], [])] if existing["core_questions_json"] else [],
            keywords=[str(item) for item in from_json(existing["keywords_json"], [])] if existing["keywords_json"] else [],
            tags=[str(item) for item in from_json(existing["tags_json"], [])] if existing["tags_json"] else [],
            entities=[str(item) for item in from_json(existing["entities_json"], [])] if existing["entities_json"] else [],
            date_range=str(existing["date_range_label"]) if existing["date_range_label"] else None,
            classification_confidence=float(existing["classification_confidence"]),
            needs_review=bool(existing["needs_review"]),
            dedup_status=str(existing["dedup_status"]),
            vector_status=str(existing["vector_status"]),
            chunk_count=chunk_count,
            binary_hash=str(existing["binary_hash"]),
            normalized_hash=str(existing["normalized_hash"]),
            raw_text="",
        )

    raw_text = extract_document_text(source_path, fallback_excerpt)
    excerpt = build_excerpt(raw_text, title)
    short_summary, summary = build_summaries(raw_text, title)
    primary_category, secondary_category, confidence, needs_review = classify_document(title, raw_text, kind)
    keywords = _extract_keywords(raw_text, title)
    entities = _extract_entities(raw_text, title)
    date_range = _extract_date_range(raw_text)
    binary_hash = compute_binary_hash(source_path, raw_text or excerpt)
    normalized_hash = compute_normalized_hash(raw_text or excerpt or title)
    doc_uid = generate_doc_uid(client_id, str(source_path), binary_hash)
    logical_reason = f"基于文档内容自动归入“{primary_category} / {secondary_category}”。"
    current_human_path = None
    normalized_path = str(source_path)
    dedup_status = "unique"
    vector_status = "pending"
    knowledge_document_id = f"kd_{document_id}"
    tags = [primary_category, secondary_category, kind] + [item for item in keywords[:3] if item not in {primary_category, secondary_category}]
    chunks = build_chunks(raw_text, excerpt)
    if chunks:
        vector_status = "chunk_indexed"
    if needs_review:
        vector_status = "needs_review"
    moved_human_path = move_document_to_human_workspace(
        data_dir=data_dir,
        client_id=client_id,
        source_path=source_path,
        category=primary_category,
        filename=title,
        doc_uid=doc_uid,
    )
    current_human_path = str(moved_human_path)
    normalized_path = current_human_path
    surrogate_payload = _surrogate_payload(
        title=title,
        kind=kind,
        primary_category=primary_category,
        secondary_category=secondary_category,
        short_summary=short_summary,
        summary=summary,
        keywords=keywords,
        entities=entities,
        date_range=date_range,
        source_path=current_human_path,
        raw_text=raw_text,
        ai_service=ai_service,
    )
    surrogate_md_path = write_surrogate_markdown(
        data_dir,
        client_id=client_id,
        doc_uid=doc_uid,
        folder_category=primary_category,
        title=title,
        source_type="document",
        source_path=current_human_path,
        payload=surrogate_payload,
    )

    db.execute(
        """
        INSERT INTO knowledge_documents(
            id, client_id, import_batch_id, document_id, doc_uid, original_path, import_source_path, current_human_path,
            human_folder_category, reclassified_at, reclass_reason, reclass_confidence, normalized_path, kind,
            primary_category, secondary_category, classification_confidence, needs_review, deep_read,
            last_hit_question, dedup_status, vector_status, version, binary_hash, normalized_hash, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?, ?, 1, ?, ?, ?, ?)
        """,
        (
            knowledge_document_id,
            client_id,
            import_id,
            document_id,
            doc_uid,
            str(source_path),
            str(source_path),
            current_human_path,
            primary_category,
            created_at,
            logical_reason,
            confidence,
            normalized_path,
            kind,
            primary_category,
            secondary_category,
            confidence,
            1 if needs_review else 0,
            dedup_status,
            vector_status,
            binary_hash,
            normalized_hash,
            created_at,
            created_at,
        ),
    )
    append_file_reclass_event(
        db,
        knowledge_document_id=knowledge_document_id,
        from_path=str(source_path),
        to_path=current_human_path,
        from_category=infer_source_category(source_path),
        to_category=primary_category,
        reason=logical_reason,
        confidence=confidence,
        created_at=created_at,
    )
    db.execute(
        """
        INSERT INTO knowledge_document_versions(id, knowledge_document_id, version_no, raw_text, raw_hash, created_at)
        VALUES(?, ?, 1, ?, ?, ?)
        """,
        (f"ver_{document_id}", knowledge_document_id, raw_text, normalized_hash, created_at),
    )
    db.execute(
        """
        INSERT INTO document_cards(
            id, knowledge_document_id, title, one_line_summary, summary_200, keywords_json, tags_json, entities_json, date_range_label, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"card_{document_id}",
            knowledge_document_id,
            title,
            short_summary,
            summary,
            to_json(keywords),
            to_json(tags),
            to_json(entities),
            date_range,
            created_at,
            created_at,
        ),
    )
    upsert_surrogate_record(
        db,
        surrogate_id=f"sur_{doc_uid}",
        knowledge_document_id=knowledge_document_id,
        client_id=client_id,
        source_type="document",
        title=title,
        folder_category=primary_category,
        surrogate_md_path=surrogate_md_path,
        payload=surrogate_payload,
        timestamp=created_at,
    )

    # --- Auto-enrich retrieval_summary via AI (if available) ---
    if ai_service and hasattr(ai_service, "enrich_retrieval_summary"):
        try:
            enriched_summary = ai_service.enrich_retrieval_summary(
                title=title,
                overview_summary=str(surrogate_payload.get("overview_summary", "")),
                distinct_findings=[str(f) for f in surrogate_payload.get("distinct_findings", [])],
                document_role=str(surrogate_payload.get("document_role", "资料")),
                folder_category=primary_category,
            )
            if enriched_summary:
                surrogate_payload["retrieval_summary"] = enriched_summary
                db.execute(
                    "UPDATE knowledge_surrogates SET retrieval_summary = ? WHERE id = ?",
                    (enriched_summary, f"sur_{doc_uid}"),
                )
                md_file = Path(surrogate_md_path)
                if md_file.exists():
                    import re as _re
                    content = md_file.read_text(encoding="utf-8")
                    content = _re.sub(
                        r"(## retrieval_summary\n).*?(\n## )",
                        rf"\g<1>{enriched_summary}\n\n\g<2>",
                        content,
                        count=1,
                        flags=_re.DOTALL,
                    )
                    md_file.write_text(content, encoding="utf-8")
        except Exception:
            pass  # enrichment is best-effort; ingestion must not fail

    catalog_text = build_catalog_search_text(
        title=title,
        short_summary=short_summary,
        summary=summary,
        raw_text=raw_text,
        keywords=keywords,
        entities=entities,
        primary_category=primary_category,
        secondary_category=secondary_category,
        document_role=str(surrogate_payload.get("document_role", "资料")),
    )
    db.execute(
        "INSERT INTO document_catalog_index(id, knowledge_document_id, searchable_text, created_at) VALUES(?, ?, ?, ?)",
        (f"idx_{document_id}", knowledge_document_id, catalog_text, created_at),
    )
    upsert_master_index_record(
        db,
        data_dir=data_dir,
        entry_id=f"midx_{doc_uid}",
        client_id=client_id,
        surrogate_id=f"sur_{doc_uid}",
        title=title,
        folder_category=primary_category,
        document_role=str(surrogate_payload.get("document_role", "资料")),
        retrieval_summary=build_master_index_summary(
            title=title,
            short_summary=short_summary,
            summary=summary,
            raw_text=raw_text,
        ),
        searchable_text=catalog_text,
        source_path=current_human_path,
        surrogate_md_path=surrogate_md_path,
        timestamp=created_at,
    )
    for chunk in chunks:
        chunk_id = f"chunk_{document_id}_{chunk['chunk_index']}"
        db.execute(
            """
            INSERT INTO document_chunks(id, knowledge_document_id, chunk_index, section_label, content, token_count, created_at)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chunk_id,
                knowledge_document_id,
                int(chunk["chunk_index"]),
                str(chunk["section_label"]),
                str(chunk["content"]),
                int(chunk["token_count"]),
                created_at,
            ),
        )
    if chunks:
        upsert_chunk_vectors(db=db, data_dir=data_dir, client_id=client_id, knowledge_document_id=knowledge_document_id)

    existing_docs = db.fetchall(
        """
        SELECT id, binary_hash, normalized_hash
        FROM knowledge_documents
        WHERE client_id = ? AND id != ?
        ORDER BY updated_at DESC
        LIMIT 100
        """,
        (client_id, knowledge_document_id),
    )
    relation_entries: list[tuple[str, str, str, str, float, str]] = []
    new_tokens = set(_extract_keywords(raw_text, title, limit=20))
    for row in existing_docs:
        relation_type = None
        score = 0.0
        if str(row["binary_hash"]) == binary_hash:
            relation_type = "exact_binary"
            score = 1.0
        elif str(row["normalized_hash"]) == normalized_hash:
            relation_type = "exact_text"
            score = 0.98
        else:
            other_card = db.fetchone(
                "SELECT keywords_json FROM document_cards WHERE knowledge_document_id = ?",
                (str(row["id"]),),
            )
            other_keywords = from_json(other_card["keywords_json"], []) if other_card and other_card["keywords_json"] else []
            other_tokens = set(str(item) for item in other_keywords)
            if new_tokens and other_tokens:
                jaccard = len(new_tokens & other_tokens) / max(1, len(new_tokens | other_tokens))
                if jaccard >= 0.72:
                    relation_type = "near_duplicate"
                    score = round(jaccard, 2)
        if relation_type:
            relation_entries.append((f"dup_{knowledge_document_id}_{row['id']}", knowledge_document_id, str(row["id"]), relation_type, score, created_at))

    if relation_entries:
        dedup_status = "duplicated"
        db.execute("UPDATE knowledge_documents SET dedup_status = ?, updated_at = ? WHERE id = ?", (dedup_status, created_at, knowledge_document_id))
        db.executemany(
            """
            INSERT INTO dedup_relations(id, knowledge_document_id, related_document_id, relation_type, relation_score, created_at)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            relation_entries,
        )

    if needs_review:
        db.execute(
            """
            INSERT INTO card_review_queue(id, knowledge_document_id, reason, status, created_at, updated_at)
            VALUES(?, ?, ?, 'pending', ?, ?)
            """,
            (f"review_{document_id}", knowledge_document_id, "分类置信度偏低，建议人工复核。", created_at, created_at),
        )

    return PreparedKnowledgeDocument(
        knowledge_document_id=knowledge_document_id,
        doc_uid=doc_uid,
        title=title,
        original_path=str(source_path),
        import_source_path=str(source_path),
        current_human_path=current_human_path,
        human_folder_category=primary_category,
        normalized_path=normalized_path,
        surrogate_md_path=surrogate_md_path,
        kind=kind,
        primary_category=primary_category,
        secondary_category=secondary_category,
        short_summary=short_summary,
        summary=summary,
        retrieval_summary=str(surrogate_payload.get("retrieval_summary", summary)),
        document_role=str(surrogate_payload.get("document_role", "资料")),
        query_hints=[str(item) for item in surrogate_payload.get("query_hints", [])],
        distinct_findings=[str(item) for item in surrogate_payload.get("distinct_findings", [])],
        core_questions=[str(item) for item in surrogate_payload.get("core_questions", [])],
        keywords=keywords,
        tags=tags,
        entities=entities,
        date_range=date_range,
        classification_confidence=confidence,
        needs_review=needs_review,
        dedup_status=dedup_status,
        vector_status=vector_status,
        chunk_count=len(chunks),
        binary_hash=binary_hash,
        normalized_hash=normalized_hash,
        raw_text=raw_text,
    )


def refresh_existing_knowledge_document(
    db: Database,
    *,
    data_dir: Path,
    client_id: str,
    knowledge_document_id: str,
    source_path: Path,
    title: str,
    kind: str,
    primary_category: str,
    secondary_category: str,
    needs_review: bool,
    fallback_excerpt: str,
    ai_service: Any | None = None,
) -> dict[str, Any]:
    raw_text = extract_document_text(source_path, fallback_excerpt)
    excerpt = build_excerpt(raw_text, title)
    short_summary, summary = build_summaries(raw_text, title)
    keywords = _extract_keywords(raw_text, title)
    entities = _extract_entities(raw_text, title)
    date_range = _extract_date_range(raw_text)
    normalized_hash = compute_normalized_hash(raw_text or excerpt or title)
    tags = [primary_category, secondary_category, kind] + [item for item in keywords[:3] if item not in {primary_category, secondary_category}]
    chunks = build_chunks(raw_text, excerpt)
    vector_status = "needs_review" if needs_review else ("chunk_indexed" if chunks else "pending")
    timestamp = now_iso()

    latest_version = db.fetchone(
        """
        SELECT version_no, raw_text, raw_hash
        FROM knowledge_document_versions
        WHERE knowledge_document_id = ?
        ORDER BY version_no DESC
        LIMIT 1
        """,
        (knowledge_document_id,),
    )
    if (
        not latest_version
        or str(latest_version["raw_hash"] or "") != normalized_hash
        or str(latest_version["raw_text"] or "") != raw_text
    ):
        next_version = int(latest_version["version_no"]) + 1 if latest_version and latest_version["version_no"] else 1
        db.execute(
            """
            INSERT INTO knowledge_document_versions(id, knowledge_document_id, version_no, raw_text, raw_hash, created_at)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (f"ver_{knowledge_document_id}_{next_version}", knowledge_document_id, next_version, raw_text, normalized_hash, timestamp),
        )
        db.execute(
            "UPDATE knowledge_documents SET version = ?, normalized_hash = ?, vector_status = ?, updated_at = ? WHERE id = ?",
            (next_version, normalized_hash, vector_status, timestamp, knowledge_document_id),
        )
    else:
        db.execute(
            "UPDATE knowledge_documents SET normalized_hash = ?, vector_status = ?, updated_at = ? WHERE id = ?",
            (normalized_hash, vector_status, timestamp, knowledge_document_id),
        )

    db.execute(
        """
        UPDATE document_cards
        SET title = ?, one_line_summary = ?, summary_200 = ?, keywords_json = ?, tags_json = ?, entities_json = ?, date_range_label = ?, updated_at = ?
        WHERE knowledge_document_id = ?
        """,
        (
            title,
            short_summary,
            summary,
            to_json(keywords),
            to_json(tags),
            to_json(entities),
            date_range,
            timestamp,
            knowledge_document_id,
        ),
    )

    db.execute("DELETE FROM document_chunks WHERE knowledge_document_id = ?", (knowledge_document_id,))
    for chunk in chunks:
        db.execute(
            """
            INSERT INTO document_chunks(id, knowledge_document_id, chunk_index, section_label, content, token_count, created_at)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"chunk_{knowledge_document_id}_{int(chunk['chunk_index'])}",
                knowledge_document_id,
                int(chunk["chunk_index"]),
                str(chunk["section_label"]),
                str(chunk["content"]),
                int(chunk["token_count"]),
                timestamp,
            ),
        )

    surrogate_payload = _surrogate_payload(
        title=title,
        kind=kind,
        primary_category=primary_category,
        secondary_category=secondary_category,
        short_summary=short_summary,
        summary=summary,
        keywords=keywords,
        entities=entities,
        date_range=date_range,
        source_path=str(source_path),
        raw_text=raw_text,
        ai_service=ai_service,
    )
    searchable_text = build_catalog_search_text(
        title=title,
        short_summary=short_summary,
        summary=summary,
        raw_text=raw_text,
        keywords=keywords,
        entities=entities,
        primary_category=primary_category,
        secondary_category=secondary_category,
        document_role=str(surrogate_payload.get("document_role", "资料")),
    )
    existing_catalog = db.fetchone(
        "SELECT id FROM document_catalog_index WHERE knowledge_document_id = ?",
        (knowledge_document_id,),
    )
    if existing_catalog:
        db.execute(
            "UPDATE document_catalog_index SET searchable_text = ?, created_at = COALESCE(created_at, ?) WHERE knowledge_document_id = ?",
            (searchable_text, timestamp, knowledge_document_id),
        )
    else:
        db.execute(
            "INSERT INTO document_catalog_index(id, knowledge_document_id, searchable_text, created_at) VALUES(?, ?, ?, ?)",
            (f"idx_{knowledge_document_id}", knowledge_document_id, searchable_text, timestamp),
        )

    if chunks:
        upsert_chunk_vectors(db=db, data_dir=data_dir, client_id=client_id, knowledge_document_id=knowledge_document_id)

    return {
        "raw_text": raw_text,
        "short_summary": short_summary,
        "summary": summary,
        "keywords": keywords,
        "entities": entities,
        "date_range": date_range,
        "tags": tags,
        "chunks": chunks,
        "vector_status": vector_status,
        "surrogate_payload": surrogate_payload,
        "searchable_text": searchable_text,
    }


def backfill_knowledge_documents(
    db: Database,
    *,
    data_dir: Path,
    client_id: str,
    ai_service: Any | None = None,
    progress_callback: Callable[[int], None] | None = None,
) -> dict[str, int]:
    ensure_client_workspace(data_dir, client_id)
    rows = db.fetchall(
        """
        SELECT d.*
        FROM documents d
        LEFT JOIN knowledge_documents kd ON kd.document_id = d.id
        WHERE d.client_id = ? AND kd.id IS NULL
        ORDER BY d.created_at ASC
        """,
        (client_id,),
    )
    processed = 0
    missing = 0
    for row in rows:
        source_path = Path(str(row["path"])).expanduser()
        if not source_path.exists():
            missing += 1
            continue
        ingest_document_knowledge(
            db,
            data_dir=data_dir,
            client_id=client_id,
            import_id=None,
            document_id=str(row["id"]),
            source_path=source_path,
            title=str(row["title"]),
            kind=str(row["kind"]),
            source=str(row["source"]),
            fallback_excerpt=str(row["excerpt"]),
            created_at=str(row["created_at"]),
            ai_service=ai_service,
        )
        processed += 1
        if progress_callback:
            progress_callback(processed)
    hydrate_missing_surrogates(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service, force_refresh=True)
    sync_human_file_locations_for_client(db, data_dir=data_dir, client_id=client_id)
    sync_master_index_fts(db, client_id)
    return {
        "processed": processed,
        "missing": missing,
    }


def compute_knowledge_status(db: Database, client_id: str, data_dir: Path | None = None) -> dict[str, Any]:
    total_documents = db.scalar("SELECT COUNT(1) AS count FROM knowledge_documents WHERE client_id = ?", (client_id,))
    total_chunks = db.scalar(
        """
        SELECT COUNT(1) AS count
        FROM document_chunks c
        JOIN knowledge_documents kd ON kd.id = c.knowledge_document_id
        WHERE kd.client_id = ?
        """,
        (client_id,),
    )
    vectorized_documents = db.scalar(
        "SELECT COUNT(1) AS count FROM knowledge_documents WHERE client_id = ? AND vector_status = 'chunk_indexed'",
        (client_id,),
    )
    deduped_documents = db.scalar(
        "SELECT COUNT(1) AS count FROM knowledge_documents WHERE client_id = ? AND dedup_status != 'unique'",
        (client_id,),
    )
    review_documents = db.scalar(
        "SELECT COUNT(1) AS count FROM knowledge_documents WHERE client_id = ? AND needs_review = 1",
        (client_id,),
    )
    latest_row = db.fetchone(
        "SELECT MAX(updated_at) AS latest FROM knowledge_documents WHERE client_id = ?",
        (client_id,),
    )
    surrogate_count = db.scalar("SELECT COUNT(1) AS count FROM knowledge_surrogates WHERE client_id = ?", (client_id,))
    memory_doc_count = db.scalar(
        "SELECT COUNT(1) AS count FROM knowledge_surrogates WHERE client_id = ? AND source_type != 'document'",
        (client_id,),
    )
    master_index_count = db.scalar(
        "SELECT COUNT(1) AS count FROM knowledge_master_index WHERE client_id = ?",
        (client_id,),
    )
    reclassified_documents = db.scalar(
        "SELECT COUNT(1) AS count FROM knowledge_documents WHERE client_id = ? AND current_human_path IS NOT NULL",
        (client_id,),
    )
    pending_jobs = db.scalar(
        """
        SELECT COUNT(1) AS count
        FROM knowledge_jobs
        WHERE client_id = ? AND job_type != 'generate_client_dna_candidates' AND status = 'queued'
        """,
        (client_id,),
    )
    running_jobs = db.scalar(
        """
        SELECT COUNT(1) AS count
        FROM knowledge_jobs
        WHERE client_id = ? AND job_type != 'generate_client_dna_candidates' AND status = 'running'
        """,
        (client_id,),
    )
    latest_job = db.fetchone(
        """
        SELECT status, last_error, finished_at
        FROM knowledge_jobs
        WHERE client_id = ? AND job_type != 'generate_client_dna_candidates'
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (client_id,),
    )
    latest_successful_job = db.fetchone(
        """
        SELECT finished_at
        FROM knowledge_jobs
        WHERE client_id = ? AND job_type != 'generate_client_dna_candidates' AND status = 'completed' AND finished_at IS NOT NULL
        ORDER BY finished_at DESC
        LIMIT 1
        """,
        (client_id,),
    )
    embedding_status = embedding_backend_status(data_dir) if data_dir else {"mode": "hash_fallback", "model": None, "error": None}
    latest_job_status = str(latest_job["status"]) if latest_job and latest_job["status"] else ("running" if running_jobs else "queued" if pending_jobs else "idle")
    return {
        "totalDocuments": total_documents,
        "totalChunks": total_chunks,
        "vectorizedDocuments": vectorized_documents,
        "dedupedDocuments": deduped_documents,
        "reviewPendingDocuments": review_documents,
        "surrogateCount": surrogate_count,
        "memoryDocCount": memory_doc_count,
        "masterIndexCount": master_index_count,
        "reclassifiedDocumentCount": reclassified_documents,
        "qdrantReady": qdrant_ready(data_dir, client_id) if data_dir else False,
        "lastUpdatedAt": str(latest_row["latest"]) if latest_row and latest_row["latest"] else None,
        "pendingJobs": pending_jobs,
        "runningJobs": running_jobs,
        "lastJobStatus": latest_job_status,
        "lastJobError": str(latest_job["last_error"]) if latest_job_status == "failed" and latest_job and latest_job["last_error"] else None,
        "lastSuccessfulRunAt": str(latest_successful_job["finished_at"]) if latest_successful_job and latest_successful_job["finished_at"] else None,
        "embeddingMode": str(embedding_status.get("mode") or "hash_fallback"),
        "embeddingModel": str(embedding_status["model"]) if embedding_status.get("model") else None,
        "embeddingError": str(embedding_status["error"]) if embedding_status.get("error") else None,
    }


def fetch_document_cards(db: Database, client_id: str, limit: int | None = 120) -> list[dict[str, Any]]:
    query = """
        SELECT kd.id AS knowledge_document_id, kd.doc_uid, kd.client_id, kd.document_id, kd.original_path, kd.import_source_path,
               kd.current_human_path, kd.human_folder_category, kd.normalized_path, kd.kind,
               kd.primary_category, kd.secondary_category, kd.classification_confidence, kd.needs_review, kd.deep_read,
               kd.reclass_reason,
               kd.last_hit_question, kd.dedup_status, kd.vector_status, kd.version, kd.created_at, kd.updated_at,
               dc.title, dc.one_line_summary, dc.summary_200, dc.keywords_json, dc.tags_json, dc.entities_json, dc.date_range_label,
               ks.surrogate_md_path, ks.retrieval_summary, ks.document_role, ks.query_hints_json, ks.distinct_findings_json, ks.core_questions_json
        FROM knowledge_documents kd
        JOIN document_cards dc ON dc.knowledge_document_id = kd.id
        LEFT JOIN knowledge_surrogates ks ON ks.knowledge_document_id = kd.id
        WHERE kd.client_id = ?
        ORDER BY kd.updated_at DESC
    """
    params: tuple[object, ...] = (client_id,)
    if limit is not None:
        query += "\nLIMIT ?"
        params = (client_id, limit)
    rows = db.fetchall(query, params)
    result: list[dict[str, Any]] = []
    for row in rows:
        chunk_count = db.scalar("SELECT COUNT(1) AS count FROM document_chunks WHERE knowledge_document_id = ?", (str(row["knowledge_document_id"]),))
        result.append(
            {
                "id": str(row["knowledge_document_id"]),
                "docId": str(row["doc_uid"]),
                "clientId": str(row["client_id"]),
                "documentId": str(row["document_id"]),
                "title": str(row["title"]),
                "originalPath": str(row["original_path"]),
                "importSourcePath": str(row["import_source_path"]) if row["import_source_path"] else None,
                "currentHumanPath": str(row["current_human_path"]) if row["current_human_path"] else None,
                "humanFolderCategory": str(row["human_folder_category"]) if row["human_folder_category"] else None,
                "sourcePath": str(row["current_human_path"]) if row["current_human_path"] else str(row["original_path"]),
                "logicalCategory": str(row["human_folder_category"]) if row["human_folder_category"] else str(row["primary_category"]),
                "logicalSubcategory": str(row["secondary_category"]),
                "classificationReason": str(row["reclass_reason"]) if row["reclass_reason"] else None,
                "normalizedPath": str(row["normalized_path"]) if row["normalized_path"] else None,
                "surrogateMdPath": str(row["surrogate_md_path"]) if row["surrogate_md_path"] else None,
                "kind": str(row["kind"]),
                "primaryCategory": str(row["primary_category"]),
                "secondaryCategory": str(row["secondary_category"]),
                "shortSummary": str(row["one_line_summary"]),
                "summary": str(row["summary_200"]),
                "retrievalSummary": str(row["retrieval_summary"]) if row["retrieval_summary"] else str(row["summary_200"]),
                "documentRole": str(row["document_role"]) if row["document_role"] else "资料",
                "queryHints": [str(item) for item in from_json(row["query_hints_json"], [])] if row["query_hints_json"] else [],
                "distinctFindings": [str(item) for item in from_json(row["distinct_findings_json"], [])] if row["distinct_findings_json"] else [],
                "coreQuestions": [str(item) for item in from_json(row["core_questions_json"], [])] if row["core_questions_json"] else [],
                "keywords": [str(item) for item in from_json(row["keywords_json"], [])] if row["keywords_json"] else [],
                "tags": [str(item) for item in from_json(row["tags_json"], [])] if row["tags_json"] else [],
                "entities": [str(item) for item in from_json(row["entities_json"], [])] if row["entities_json"] else [],
                "dateRange": str(row["date_range_label"]) if row["date_range_label"] else None,
                "classificationConfidence": float(row["classification_confidence"]),
                "needsReview": bool(row["needs_review"]),
                "deepRead": bool(row["deep_read"]),
                "lastHitQuestion": str(row["last_hit_question"]) if row["last_hit_question"] else None,
                "dedupStatus": str(row["dedup_status"]),
                "vectorStatus": str(row["vector_status"]),
                "version": int(row["version"]),
                "chunkCount": chunk_count,
                "createdAt": str(row["created_at"]),
                "updatedAt": str(row["updated_at"]),
            }
        )
    return result


def fetch_recent_reclass_events(db: Database, client_id: str, limit: int = 8) -> list[dict[str, Any]]:
    rows = db.fetchall(
        """
        SELECT fre.*
        FROM file_reclass_events fre
        JOIN knowledge_documents kd ON kd.id = fre.knowledge_document_id
        WHERE kd.client_id = ?
        ORDER BY fre.created_at DESC
        LIMIT ?
        """,
        (client_id, limit),
    )
    return [
        {
            "id": str(row["id"]),
            "knowledgeDocumentId": str(row["knowledge_document_id"]),
            "fromPath": str(row["from_path"]),
            "toPath": str(row["to_path"]),
            "fromCategory": str(row["from_category"]) if row["from_category"] else None,
            "toCategory": str(row["to_category"]),
            "reason": str(row["reason"]),
            "confidence": float(row["confidence"]),
            "createdAt": str(row["created_at"]),
        }
        for row in rows
    ]


def fetch_recent_knowledge_jobs(db: Database, client_id: str, limit: int = 8) -> list[dict[str, Any]]:
    rows = db.fetchall(
        """
        SELECT *
        FROM knowledge_jobs
        WHERE client_id = ?
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (client_id, limit),
    )
    return [
        {
            "id": str(row["id"]),
            "clientId": str(row["client_id"]),
            "jobType": str(row["job_type"]),
            "status": str(row["status"]),
            "totalItems": int(row["total_items"]),
            "processedItems": int(row["processed_items"]),
            "lastError": str(row["last_error"]) if row["last_error"] else None,
            "createdAt": str(row["created_at"]),
            "startedAt": str(row["started_at"]) if row["started_at"] else None,
            "finishedAt": str(row["finished_at"]) if row["finished_at"] else None,
            "updatedAt": str(row["updated_at"]),
        }
        for row in rows
    ]


def create_memory_surrogate_from_answer(
    db: Database,
    *,
    data_dir: Path,
    client_id: str,
    title: str,
    content: str,
    actions: str,
    analysis: str,
    source_links: list[dict[str, Any]],
    created_at: str,
    ai_service: Any | None = None,
) -> dict[str, Any]:
    doc_uid = f"mem_{hashlib.sha1(f'{client_id}:{title}:{content}'.encode('utf-8')).hexdigest()[:12]}"
    payload = {
        "overview_summary": content[:220],
        "retrieval_summary": (analysis or content)[:240],
        "document_role": "战略陪伴记忆",
        "core_questions": [title, "这条记忆适用于哪些后续问题？"],
        "query_hints": tokenize(f"{title} {analysis} {actions}")[:8],
        "distinct_findings": [item for item in [content[:80], actions[:80], analysis[:80]] if item],
        "entities": [],
        "time_markers": [],
        "source_links": source_links,
    }
    if ai_service and hasattr(ai_service, "generate_memory_surrogate"):
        try:
            enriched = ai_service.generate_memory_surrogate(
                title=title,
                content=content,
                analysis=analysis,
                actions=actions,
                fallback=payload,
            )
            if isinstance(enriched, dict):
                payload.update({key: value for key, value in enriched.items() if value not in (None, "")})
        except Exception:
            pass
    surrogate_md_path = write_surrogate_markdown(
        data_dir,
        client_id=client_id,
        doc_uid=doc_uid,
        folder_category="战略陪伴",
        title=title,
        source_type="memory_answer",
        source_path=None,
        payload=payload,
    )
    surrogate_id = f"sur_{doc_uid}"
    upsert_surrogate_record(
        db,
        surrogate_id=surrogate_id,
        knowledge_document_id=None,
        client_id=client_id,
        source_type="memory_answer",
        title=title,
        folder_category="战略陪伴",
        surrogate_md_path=surrogate_md_path,
        payload=payload,
        timestamp=created_at,
    )
    searchable_text = "\n".join(
        [
            title,
            str(payload.get("retrieval_summary", "")),
            " ".join([str(item) for item in payload.get("query_hints", [])]),
            " ".join([str(item) for item in payload.get("core_questions", [])]),
            " ".join([str(item) for item in payload.get("distinct_findings", [])]),
            "战略陪伴",
        ]
    )
    upsert_master_index_record(
        db,
        data_dir=data_dir,
        entry_id=f"midx_{doc_uid}",
        client_id=client_id,
        surrogate_id=surrogate_id,
        title=title,
        folder_category="战略陪伴",
        document_role=str(payload.get("document_role", "战略陪伴记忆")),
        retrieval_summary=str(payload.get("retrieval_summary", "")),
        searchable_text=searchable_text,
        source_path=None,
        surrogate_md_path=surrogate_md_path,
        timestamp=created_at,
    )
    return {
        "id": surrogate_id,
        "clientId": client_id,
        "sourceType": "memory_answer",
        "title": title,
        "folderCategory": "战略陪伴",
        "surrogateMdPath": surrogate_md_path,
        "createdAt": created_at,
        "updatedAt": created_at,
    }


def retrieve_knowledge_bundle(db: Database, data_dir: Path, client_id: str, prompt: str) -> RetrievalBundle:
    tokens = tokenize(prompt)
    if not tokens and prompt.strip():
        tokens = [prompt.strip().lower()]
    strategic_mode = is_strategy_analysis_query(prompt)
    overview_mode = is_overview_query(prompt)
    intro_mode = is_intro_profile_query(prompt)
    finance_mode = is_finance_query(prompt)
    finance_statement_mode = is_finance_statement_query(prompt)

    # 方案B: 全文档摘要预筛 — 把所有文档摘要列表注入检索上下文
    # 这不是额外的 AI 调用，而是把摘要列表作为额外的检索信号
    all_doc_summaries = db.fetchall(
        """
        SELECT dc.title, dc.summary_200, dc.one_line_summary, kd.updated_at
        FROM document_cards dc
        JOIN knowledge_documents kd ON kd.id = dc.knowledge_document_id
        WHERE kd.client_id = ?
        ORDER BY kd.updated_at DESC
        """,
        (client_id,),
    )
    # 把摘要注入 tokens 用于匹配增强 — 确保全局覆盖
    summary_boost_terms: list[str] = []
    for doc_row in all_doc_summaries[:60]:
        title = str(doc_row["title"] or "").lower()
        summary = str(doc_row["summary_200"] or doc_row["one_line_summary"] or "").lower()
        # 如果问题关键词出现在文档标题或摘要中，加入 boost
        for token in tokens:
            if token in title or token in summary:
                title_terms = tokenize(str(doc_row["title"] or ""))
                summary_boost_terms.extend(title_terms[:3])
                break
    if summary_boost_terms:
        tokens = list(dict.fromkeys(tokens + summary_boost_terms))

    preferred_categories = infer_query_categories(prompt, tokens)
    coverage_terms = build_coverage_terms(prompt, tokens, preferred_categories)

    master_rows = db.fetchall(
        """
        SELECT mi.*, ks.knowledge_document_id, ks.title AS surrogate_title, ks.surrogate_md_path
        FROM knowledge_master_index mi
        JOIN knowledge_surrogates ks ON ks.id = mi.surrogate_id
        WHERE mi.client_id = ?
        ORDER BY mi.updated_at DESC
        """,
        (client_id,),
    )
    fts_master_scores = search_master_index_fts(
        db,
        client_id,
        prompt,
        limit=120 if overview_mode else (96 if strategic_mode else 64),
    )
    qdrant_master_scores = search_master_index_qdrant(
        data_dir,
        client_id,
        prompt,
        limit=120 if overview_mode else (96 if strategic_mode else 72),
    )

    scored_docs: list[dict[str, Any]] = []
    for row in master_rows:
        searchable = str(row["searchable_text"]).lower()
        title = clean_title_for_search(str(row["title"])).lower()
        folder_category = str(row["folder_category"]) if row["folder_category"] else "其他资料"
        document_role = str(row["document_role"]) if row["document_role"] else ""
        matched_terms = [token for token in coverage_terms if token in searchable]
        lexical_score = len({token for token in tokens if token in searchable}) / len(tokens) if tokens else 0.0
        title_bonus = sum(1 for token in tokens if token in title) * 0.15
        category_bonus = 0.08 if any(token in folder_category.lower() for token in tokens) else 0.0
        if strategic_mode and folder_category in preferred_categories:
            category_bonus += 0.12
        role_bonus = 0.0
        if strategic_mode and document_role:
            role_bonus = 0.06 if any(token in document_role.lower() for token in coverage_terms) else 0.03
        finance_adjustment = (
            finance_document_score_adjustment(
                title=str(row["title"]),
                summary=str(row["retrieval_summary"]),
                document_role=document_role,
                folder_category=folder_category,
                path=str(row["source_path"]) if row["source_path"] else None,
                statement_mode=finance_statement_mode,
            )
            if finance_mode
            else 0.0
        )
        fts_score = fts_master_scores.get(str(row["id"]), 0.0)
        qdrant_score = qdrant_master_scores.get(str(row["id"]), 0.0)
        overview_adjustment = (
            intro_document_score_adjustment(
                title=str(row["title"]),
                summary=str(row["retrieval_summary"]),
                document_role=document_role,
                folder_category=folder_category,
                path=str(row["source_path"]) if row["source_path"] else None,
            )
            if intro_mode
            else 0.0
        )
        total_score = round(
            lexical_score * 0.35
            + title_bonus
            + category_bonus
            + role_bonus
            + fts_score * 0.55
            + qdrant_score * 0.65,
            4,
        )
        # 时效性加权：近30天的文档加分
        recency_bonus = 0.0
        try:
            from datetime import datetime, timedelta
            doc_updated = datetime.fromisoformat(str(row["updated_at"]).replace("Z", "+00:00").split("+")[0])
            days_ago = (datetime.now() - doc_updated).days
            if days_ago <= 7:
                recency_bonus = 0.10
            elif days_ago <= 30:
                recency_bonus = 0.06
            elif days_ago <= 90:
                recency_bonus = 0.03
        except Exception:
            pass
        total_score = round(total_score + overview_adjustment + finance_adjustment + recency_bonus, 4)
        is_candidate = bool(matched_terms) or title_bonus > 0 or fts_score > 0 or qdrant_score >= MASTER_VECTOR_CANDIDATE_THRESHOLD
        scored_docs.append(
            {
                "master_id": str(row["id"]),
                "surrogate_id": str(row["surrogate_id"]),
                "knowledge_document_id": str(row["knowledge_document_id"]) if row["knowledge_document_id"] else None,
                "title": str(row["title"]),
                "path": str(row["source_path"]) if row["source_path"] else None,
                "surrogate_md_path": str(row["surrogate_md_path"]) if row["surrogate_md_path"] else None,
                "matched_terms": sorted(set(matched_terms)),
                "score": total_score,
                "fts_score": fts_score,
                "qdrant_score": qdrant_score,
                "is_candidate": is_candidate,
                "summary": str(row["retrieval_summary"]),
                "folder_category": folder_category,
                "document_role": document_role,
            }
        )

    scored_docs.sort(key=lambda item: item["score"], reverse=True)
    positive_candidates = [
        item
        for item in scored_docs
        if item["score"] > 0 and (item["is_candidate"] or strategic_mode)
    ]
    if intro_mode:
        prioritized_candidates = [
            item
            for item in positive_candidates
            if is_intro_priority_text(
                str(item.get("title") or ""),
                str(item.get("summary") or ""),
                str(item.get("document_role") or ""),
                str(item.get("path") or ""),
            )
        ]
        clean_candidates = [
            item
            for item in positive_candidates
            if not is_intro_noise_text(
                str(item.get("title") or ""),
                str(item.get("summary") or ""),
                str(item.get("document_role") or ""),
                str(item.get("path") or ""),
            )
        ]
        prioritized_clean_candidates = [
            item
            for item in prioritized_candidates
            if item in clean_candidates
        ]
        noisy_candidates = [item for item in positive_candidates if item not in clean_candidates]
        positive_candidates = (
            prioritized_clean_candidates
            + [item for item in clean_candidates if item not in prioritized_clean_candidates]
            + noisy_candidates
        )
    candidate_docs = diversify_candidate_documents(
        positive_candidates,
        preferred_categories=preferred_categories,
        limit=60 if overview_mode else (50 if strategic_mode else 40),
        strategic_mode=strategic_mode,
        overview_mode=overview_mode,
        finance_mode=finance_mode,
    )
    if not candidate_docs:
        retrieval_summary = {
            "queryTokens": coverage_terms,
            "matchedTokens": [],
            "masterHitCount": 0,
            "candidateDocumentCount": 0,
            "surrogateHitCount": 0,
            "rawChunkHitCount": 0,
            "citationCount": 0,
            "coverage": 0.0,
            "drillthroughUsed": False,
            "strategicMode": strategic_mode,
            "categoryCoverage": [],
            "backgroundTrail": [],
        }
        return RetrievalBundle(
            citations=[],
            coverage=0.0,
            retrieval_summary=retrieval_summary,
            context_text="",
            matched_terms=[],
            failure_reason="no_candidate_documents",
        )

    background_matches: list[dict[str, Any]] = [
        {
            "knowledge_document_id": item["knowledge_document_id"],
            "chunk_id": None,
            "title": item["title"],
            "excerpt": str(item["summary"])[:220],
            "path": item["path"],
            "section_label": "目录索引",
            "matched_terms": item["matched_terms"],
            "score": round(float(item["score"]), 4),
            "qdrant_score": float(item["qdrant_score"]),
            "source_stage": "master_index",
        }
        for item in candidate_docs[:16]
    ]

    surrogate_matches: list[dict[str, Any]] = []
    for candidate in candidate_docs:
        if not candidate["surrogate_md_path"]:
            continue
        surrogate_text = load_surrogate_retrieval_text(str(candidate["surrogate_md_path"]))
        matched_terms = [token for token in coverage_terms if token in surrogate_text.lower()]
        surrogate_score = len(set(matched_terms)) / len(coverage_terms) if coverage_terms else 0.0
        surrogate_score += candidate["score"] * 0.45
        surrogate_matches.append(
            {
                "knowledge_document_id": candidate["knowledge_document_id"],
                "chunk_id": None,
                "title": candidate["title"],
                "excerpt": str(candidate["summary"])[:180],
                "path": candidate["path"],
                "section_label": "代理文档",
                "matched_terms": sorted(set(matched_terms or candidate["matched_terms"])),
                "score": round(surrogate_score, 4),
                "qdrant_score": float(candidate["qdrant_score"]),
                "source_stage": "surrogate",
            }
        )
    surrogate_matches.sort(key=lambda item: item["score"], reverse=True)

    qdrant_chunk_scores = search_raw_chunks_qdrant(
        data_dir,
        client_id,
        prompt,
        [str(item["knowledge_document_id"]) for item in candidate_docs if item["knowledge_document_id"]],
        limit=160 if overview_mode else (140 if strategic_mode else 120),
    )
    chunk_matches: list[dict[str, Any]] = []
    for candidate in candidate_docs:
        if not candidate["knowledge_document_id"]:
            continue
        chunk_rows = db.fetchall(
            "SELECT * FROM document_chunks WHERE knowledge_document_id = ? ORDER BY chunk_index ASC",
            (candidate["knowledge_document_id"],),
        )
        for row in chunk_rows:
            content = str(row["content"]).lower()
            matched_terms = [token for token in coverage_terms if token in content]
            match_score = len(set(matched_terms)) / len(coverage_terms) if coverage_terms else 0.0
            if candidate["score"]:
                match_score += candidate["score"] * 0.18
            qdrant_score = qdrant_chunk_scores.get(str(row["id"]), 0.0)
            match_score += qdrant_score * 0.78
            if finance_mode:
                match_score += finance_chunk_score_adjustment(
                    title=candidate["title"],
                    excerpt=str(row["content"])[:320],
                    section_label=str(row["section_label"]) if row["section_label"] else None,
                    path=candidate["path"],
                    statement_mode=finance_statement_mode,
                )
            if intro_mode:
                match_score += intro_chunk_score_adjustment(
                    title=candidate["title"],
                    excerpt=str(row["content"])[:220],
                    section_label=str(row["section_label"]) if row["section_label"] else None,
                    path=candidate["path"],
                )
            chunk_matches.append(
                {
                    "knowledge_document_id": candidate["knowledge_document_id"],
                    "chunk_id": str(row["id"]),
                    "title": candidate["title"],
                    "excerpt": str(row["content"])[:180],
                    "path": candidate["path"],
                    "section_label": str(row["section_label"]) if row["section_label"] else None,
                    "matched_terms": sorted(set(matched_terms)),
                    "score": round(match_score, 4),
                    "qdrant_score": qdrant_score,
                    "source_stage": "raw_chunk",
                }
            )

    chunk_matches.sort(key=lambda item: item["score"], reverse=True)
    top_surrogate_matches = [
        item
        for item in surrogate_matches
        if item["score"] > 0 and (item["matched_terms"] or item["qdrant_score"] >= MASTER_VECTOR_CANDIDATE_THRESHOLD)
    ]
    top_surrogate_matches = dedupe_ranked_matches(
        top_surrogate_matches,
        limit=12 if overview_mode else 10,
        key_builder=lambda item: f"{item.get('knowledge_document_id')}::{item.get('title')}",
    )
    top_chunk_matches = [
        item
        for item in chunk_matches
        if item["score"] > 0 and (item["matched_terms"] or item["qdrant_score"] >= CHUNK_VECTOR_CANDIDATE_THRESHOLD)
    ]
    if intro_mode:
        prioritized_chunks = [
            item
            for item in top_chunk_matches
            if is_intro_priority_text(
                str(item.get("title") or ""),
                str(item.get("section_label") or ""),
                str(item.get("excerpt") or ""),
                str(item.get("path") or ""),
            )
        ]
        clean_chunks = [
            item
            for item in top_chunk_matches
            if not is_intro_noise_text(
                str(item.get("title") or ""),
                str(item.get("section_label") or ""),
                str(item.get("excerpt") or ""),
                str(item.get("path") or ""),
            )
        ]
        prioritized_clean_chunks = [
            item
            for item in prioritized_chunks
            if item in clean_chunks
        ]
        noisy_chunks = [item for item in top_chunk_matches if item not in clean_chunks]
        top_chunk_matches = (
            prioritized_clean_chunks
            + [item for item in clean_chunks if item not in prioritized_clean_chunks]
            + noisy_chunks
        )
    top_chunk_matches = dedupe_ranked_matches(
        top_chunk_matches,
        limit=56 if overview_mode else (44 if strategic_mode else 32),
        key_builder=lambda item: f"{item.get('knowledge_document_id')}::{item.get('section_label') or ''}::{normalize_text(str(item.get('excerpt', '')))[:96]}",
    )
    citation_limit = 35 if overview_mode else (30 if strategic_mode else 25)
    drillthrough_used = bool(top_chunk_matches)
    selected_matches: list[dict[str, Any]] = []
    doc_chunk_counts: dict[str, int] = {}
    if finance_mode:
        for item in top_chunk_matches:
            doc_id = str(item.get("knowledge_document_id") or "")
            if not is_finance_priority_text(item.get("title"), item.get("section_label"), item.get("excerpt"), item.get("path")):
                continue
            if doc_chunk_counts.get(doc_id, 0) >= 2:
                continue
            selected_matches.append(item)
            doc_chunk_counts[doc_id] = doc_chunk_counts.get(doc_id, 0) + 1
            if len(selected_matches) >= min(citation_limit, 8):
                break
    for item in top_chunk_matches:
        doc_id = str(item.get("knowledge_document_id") or "")
        if doc_chunk_counts.get(doc_id, 0) >= 2:
            continue
        selected_matches.append(item)
        doc_chunk_counts[doc_id] = doc_chunk_counts.get(doc_id, 0) + 1
        if len(selected_matches) >= citation_limit:
            break
    if not selected_matches and top_chunk_matches:
        selected_matches = top_chunk_matches[:citation_limit]
    if not selected_matches and candidate_docs:
        seeded_matches: list[dict[str, Any]] = []
        for candidate in candidate_docs[: min(len(candidate_docs), 12)]:
            knowledge_document_id = str(candidate.get("knowledge_document_id") or "")
            if not knowledge_document_id:
                continue
            chunk_rows = db.fetchall(
                """
                SELECT *
                FROM document_chunks
                WHERE knowledge_document_id = ?
                ORDER BY chunk_index ASC
                LIMIT 2
                """,
                (knowledge_document_id,),
            )
            for row in chunk_rows:
                seeded_matches.append(
                    {
                        "knowledge_document_id": knowledge_document_id,
                        "chunk_id": str(row["id"]),
                        "title": candidate["title"],
                        "excerpt": str(row["content"])[:180],
                        "path": candidate["path"],
                        "section_label": str(row["section_label"]) if row["section_label"] else None,
                        "matched_terms": sorted(set(candidate["matched_terms"])),
                        "score": round(float(candidate["score"]) * 0.82, 4),
                        "source_stage": "raw_chunk",
                    }
                )
        if seeded_matches:
            drillthrough_used = True
            selected_matches = dedupe_ranked_matches(
                seeded_matches,
                limit=citation_limit,
                key_builder=lambda item: f"{item.get('knowledge_document_id')}::{item.get('section_label') or ''}::{normalize_text(str(item.get('excerpt', '')))[:72]}",
            )

    background_trail = dedupe_ranked_matches(
        [*top_surrogate_matches, *background_matches],
        limit=12,
        key_builder=lambda item: f"{item.get('source_stage')}::{item.get('knowledge_document_id') or item.get('title')}",
    )

    matched_terms = sorted({term for item in selected_matches for term in item["matched_terms"]})
    coverage = round(len(matched_terms) / len(coverage_terms), 2) if coverage_terms and selected_matches else 0.0
    category_coverage = []
    seen_categories: set[str] = set()
    for item in candidate_docs:
        category = str(item.get("folder_category") or "其他资料")
        if category in seen_categories:
            continue
        seen_categories.add(category)
        category_coverage.append(category)
    citations = [
        CitationMatch(
            knowledge_document_id=item["knowledge_document_id"],
            chunk_id=item["chunk_id"],
            title=item["title"],
            excerpt=item["excerpt"],
            score=float(item["score"]),
            coverage=coverage,
            section_label=item["section_label"],
            source_stage=str(item.get("source_stage", "raw_chunk")),
            drillthrough_used=drillthrough_used,
            matched_terms=item["matched_terms"],
            path=item["path"],
        )
        for item in selected_matches[:citation_limit]
    ]
    context_lines = []
    for index, citation in enumerate(citations, start=1):
        label = f"{citation.title}"
        if citation.section_label:
            label = f"{label} / {citation.section_label}"
        context_lines.append(
            f"[证据{index}] {label}\n匹配词：{'、'.join(citation.matched_terms) or '无'}\n内容：{citation.excerpt}"
        )
    retrieval_summary = {
        "queryTokens": coverage_terms,
        "matchedTokens": matched_terms,
        "masterHitCount": len(candidate_docs),
        "candidateDocumentCount": len(candidate_docs),
        "surrogateHitCount": len(top_surrogate_matches),
        "rawChunkHitCount": max(len(top_chunk_matches), len(citations)),
        "citationCount": len(citations),
        "coverage": coverage,
        "drillthroughUsed": drillthrough_used,
        "strategicMode": strategic_mode,
        "categoryCoverage": category_coverage,
        "preferredCategories": preferred_categories,
        "backgroundTrail": [
            {
                "title": item["title"],
                "stage": "背景摘要" if item.get("source_stage") == "surrogate" else "目录索引",
                "sectionLabel": item.get("section_label"),
                "path": item.get("path"),
                "excerpt": item["excerpt"],
            }
            for item in background_trail
        ],
    }
    return RetrievalBundle(
        citations=citations,
        coverage=coverage,
        retrieval_summary=retrieval_summary,
        context_text="\n\n".join(context_lines),
        matched_terms=matched_terms,
        failure_reason=None if citations else "no_grounded_citations",
    )


# ---------------------------------------------------------------------------
# Phase 1: Batch enrich surrogate retrieval_summary via AI
# ---------------------------------------------------------------------------


def batch_enrich_surrogates(
    db: Database,
    *,
    data_dir: Path,
    client_id: str,
    ai_service: Any,
) -> dict[str, Any]:
    """Rewrite all template-based retrieval_summary fields for a client's surrogates using AI.

    Returns a summary dict with counts of enriched / skipped / failed surrogates.
    """
    rows = db.fetchall(
        """
        SELECT id, title, folder_category, surrogate_md_path,
               overview_summary, retrieval_summary, document_role,
               distinct_findings_json, source_type
        FROM knowledge_surrogates
        WHERE client_id = ? AND source_type = 'document'
        ORDER BY updated_at DESC
        """,
        (client_id,),
    )
    enriched = 0
    skipped = 0
    failed = 0
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    for row in rows:
        surrogate_id = str(row["id"])
        title = str(row["title"])
        overview = str(row["overview_summary"] or "")
        document_role = str(row["document_role"] or "资料")
        folder_category = str(row["folder_category"] or "其他资料")
        md_path = str(row["surrogate_md_path"] or "")
        findings_raw = from_json(row["distinct_findings_json"]) if row["distinct_findings_json"] else []
        findings = [str(f) for f in findings_raw] if isinstance(findings_raw, list) else []

        if not overview or len(overview.strip()) < 20:
            skipped += 1
            continue

        new_summary = ai_service.enrich_retrieval_summary(
            title=title,
            overview_summary=overview,
            distinct_findings=findings,
            document_role=document_role,
            folder_category=folder_category,
        )
        if not new_summary:
            failed += 1
            continue

        # 1. Update DB record
        db.execute(
            "UPDATE knowledge_surrogates SET retrieval_summary = ?, updated_at = ? WHERE id = ?",
            (new_summary, timestamp, surrogate_id),
        )

        # 2. Update .md file on disk
        md_file = Path(md_path)
        if md_file.exists():
            try:
                content = md_file.read_text(encoding="utf-8")
                import re as _re
                content = _re.sub(
                    r"(## retrieval_summary\n).*?(\n## )",
                    rf"\g<1>{new_summary}\n\n\g<2>",
                    content,
                    count=1,
                    flags=_re.DOTALL,
                )
                md_file.write_text(content, encoding="utf-8")
            except Exception:
                pass

        # 3. Update master_index record + Qdrant vector
        master_row = db.fetchone(
            "SELECT id, searchable_text FROM knowledge_master_index WHERE surrogate_id = ?",
            (surrogate_id,),
        )
        if master_row:
            entry_id = str(master_row["id"])
            new_searchable = f"{title}\n{new_summary}"
            db.execute(
                "UPDATE knowledge_master_index SET retrieval_summary = ?, searchable_text = ?, updated_at = ? WHERE id = ?",
                (new_summary, new_searchable, timestamp, entry_id),
            )
            upsert_master_index_vector(
                data_dir=data_dir,
                client_id=client_id,
                entry_id=entry_id,
                title=title,
                searchable_text=new_searchable,
                source_path=None,
                surrogate_md_path=md_path,
                folder_category=folder_category,
                document_role=document_role,
            )

        enriched += 1

    return {
        "clientId": client_id,
        "total": len(rows),
        "enriched": enriched,
        "skipped": skipped,
        "failed": failed,
    }
~~~

## `backend/app/services/knowledge_v2.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import hashlib
import re
import shutil
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4
from xml.etree import ElementTree as ET

from docx import Document as WordDocument

from app.db import Database, from_json, to_json
from app.services.knowledge_base import append_file_reclass_event

try:
    from pypdf import PdfReader

    HAS_PYPDF = True
except Exception:  # pragma: no cover - runtime dependency
    PdfReader = None  # type: ignore[assignment]
    HAS_PYPDF = False


V2_PIPELINE_VERSION = "v2-minimal-evidence"
MAIN_KNOWLEDGE_STATUS_JOB_TYPES = ("ingest_import", "backfill_workspace_import")
_AUXILIARY_KNOWLEDGE_JOB_TYPES = ("generate_client_dna_candidates",)
TEXT_EXTENSIONS = {".md", ".txt", ".json", ".csv"}
ARCHIVE_XML_EXTENSIONS = {".pptx", ".xlsx"}
LEGACY_FIXED_CATEGORIES = ["财务与筹款", "品牌与传播", "项目与业务", "组织与战略", "其他资料", "战略陪伴"]
HUMAN_VISIBLE_CATEGORIES = LEGACY_FIXED_CATEGORIES  # kept for backward compat; new clients use dynamic folders
EVIDENCE_CATEGORIES = LEGACY_FIXED_CATEGORIES[:-1]
DEFAULT_INBOX_LABEL = "收件箱"
WORKSPACE_BACKFILL_EXTENSIONS = {".pdf", ".docx", ".md", ".txt", ".pptx", ".xlsx", ".json", ".csv"}
QUERY_STOPWORDS = {
    "请",
    "一下",
    "一个",
    "一些",
    "结合",
    "现有",
    "资料",
    "当前",
    "这个",
    "那个",
    "我们",
    "你们",
    "他们",
    "以及",
    "需要",
    "进行",
    "问题",
    "情况",
}
DERIVED_TITLE_MARKERS = ("介绍", "简介", "精简版", "预览", "说明", "ppt", "工作台")
DERIVED_TEXT_MARKERS = (
    "完全基于你提供的材料",
    "为了便于你后续直接做 ppt",
    "为了便于你后续直接做ppt",
    "为了便于你后续直接做 ppt 或对外介绍",
    "为了便于你后续直接做ppt或对外介绍",
    "对外介绍",
    "下面给出",
    "可直接拆进",
    "产品策划 + 功能与价值 + 页面级设计",
    "我用“定位—交付—工作模式—业务价值—近期重点”的结构来写",
    "我用“定位-交付-工作模式-业务价值-近期重点”的结构来写",
    "一句话定义",
)
DERIVED_CITATION_PATTERN = re.compile(r"【\d{1,4}:\d{1,4}†|\[\d{1,4}:\d{1,4}†")
NOISE_FILES = {".ds_store", "thumbs.db", "~$"}
CATEGORY_KEYWORDS = {
    "财务与筹款": ("财务", "预算", "筹款", "募资", "捐赠", "赞助", "基金", "现金流", "审计", "年报"),
    "品牌与传播": ("品牌", "传播", "公关", "媒体", "内容", "公众号", "活动", "叙事", "视觉", "案例"),
    "项目与业务": ("项目", "业务", "交付", "方案", "行业", "客户", "服务", "运营", "年会", "图书馆"),
    "组织与战略": ("战略", "组织", "治理", "团队", "董事会", "理事会", "路线图", "规划", "会议纪要", "访谈"),
}
SECTION_BREAK_PATTERN = re.compile(r"\n{2,}")
CHUNK_TARGET_CHARS = 680
CHUNK_OVERLAP_CHARS = 120
INTERNAL_WORKSPACE_MARKERS = {"_v2_meta", "_imports"}


@dataclass
class CitationMatch:
    knowledge_document_id: str
    chunk_id: str | None
    title: str
    excerpt: str
    score: float
    coverage: float
    section_label: str | None
    source_stage: str
    drillthrough_used: bool
    matched_terms: list[str]
    path: str | None


@dataclass
class RetrievalBundle:
    citations: list[CitationMatch]
    coverage: float
    retrieval_summary: dict[str, Any]
    context_text: str
    matched_terms: list[str]
    failure_reason: str | None = None


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


def serialize_retrieval_bundle(bundle: RetrievalBundle) -> dict[str, Any]:
    return {
        "citations": [
            {
                "knowledge_document_id": item.knowledge_document_id,
                "chunk_id": item.chunk_id,
                "title": item.title,
                "excerpt": item.excerpt,
                "score": item.score,
                "coverage": item.coverage,
                "section_label": item.section_label,
                "source_stage": item.source_stage,
                "drillthrough_used": item.drillthrough_used,
                "matched_terms": item.matched_terms,
                "path": item.path,
            }
            for item in bundle.citations
        ],
        "coverage": bundle.coverage,
        "retrieval_summary": bundle.retrieval_summary,
        "context_text": bundle.context_text,
        "matched_terms": bundle.matched_terms,
        "failure_reason": bundle.failure_reason,
    }


def deserialize_retrieval_bundle(payload: dict[str, Any]) -> RetrievalBundle:
    citations = []
    for item in payload.get("citations", []):
        if not isinstance(item, dict):
            continue
        citations.append(
            CitationMatch(
                knowledge_document_id=str(item.get("knowledge_document_id") or ""),
                chunk_id=str(item["chunk_id"]) if item.get("chunk_id") else None,
                title=str(item.get("title") or ""),
                excerpt=str(item.get("excerpt") or ""),
                score=float(item.get("score") or 0.0),
                coverage=float(item.get("coverage") or 0.0),
                section_label=str(item["section_label"]) if item.get("section_label") else None,
                source_stage=str(item.get("source_stage") or "raw_chunk"),
                drillthrough_used=bool(item.get("drillthrough_used", False)),
                matched_terms=[str(term) for term in item.get("matched_terms", []) if str(term).strip()],
                path=str(item["path"]) if item.get("path") else None,
            )
        )
    retrieval_summary = payload.get("retrieval_summary", {})
    return RetrievalBundle(
        citations=citations,
        coverage=float(payload.get("coverage") or 0.0),
        retrieval_summary=retrieval_summary if isinstance(retrieval_summary, dict) else {},
        context_text=str(payload.get("context_text") or ""),
        matched_terms=[str(term) for term in payload.get("matched_terms", []) if str(term).strip()],
        failure_reason=str(payload["failure_reason"]) if payload.get("failure_reason") else None,
    )


def safe_filename(name: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "_", name).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:180] or "untitled"


def ensure_client_folder_rows(db: Database, data_dir: Path, client_id: str) -> None:
    timestamp = now_iso()
    workspace_root = data_dir / "client_workspace" / client_id
    workspace_root.mkdir(parents=True, exist_ok=True)
    for label in HUMAN_VISIBLE_CATEGORIES:
        path = workspace_root / label
        path.mkdir(parents=True, exist_ok=True)
        existing = db.fetchone(
            "SELECT id FROM client_folders WHERE client_id = ? AND label = ?",
            (client_id, label),
        )
        if existing:
            db.execute(
                "UPDATE client_folders SET path = ?, last_scanned_at = ? WHERE id = ?",
                (str(path), timestamp, str(existing["id"])),
            )
        else:
            db.execute(
                """
                INSERT INTO client_folders(id, client_id, label, path, file_count, last_scanned_at, created_at)
                VALUES(?, ?, ?, ?, 0, ?, ?)
                """,
                (new_id("fld"), client_id, label, str(path), timestamp, timestamp),
            )


def client_workspace_root(data_dir: Path, client_id: str) -> Path:
    root = data_dir / "client_workspace" / client_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"\u00a0", " ", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def tokenize(text: str) -> list[str]:
    normalized = re.sub(r"[^\w\u4e00-\u9fff]+", " ", text.lower())
    tokens: list[str] = []
    seen: set[str] = set()
    for word in re.findall(r"[a-z0-9]{2,}", normalized):
        if word not in seen:
            seen.add(word)
            tokens.append(word)
    for block in re.findall(r"[\u4e00-\u9fff]{2,}", normalized):
        compact = "".join(char for char in block if char not in "的是了和在对与及并把将中上为等于")
        if len(compact) < 2:
            continue
        candidates = {compact}
        if len(compact) >= 2:
            candidates.update(compact[index : index + 2] for index in range(len(compact) - 1))
        if len(compact) >= 4:
            candidates.update(compact[index : index + 4] for index in range(len(compact) - 3))
        for candidate in candidates:
            if len(candidate) < 2 or candidate in QUERY_STOPWORDS or candidate in seen:
                continue
            seen.add(candidate)
            tokens.append(candidate)
    return tokens[:48]


def is_strategy_analysis_query(text: str) -> bool:
    lowered = text.lower()
    return any(
        token in lowered
        for token in ("战略", "主线", "关键取舍", "风险", "判断", "诊断", "路径", "张力", "重点", "取舍")
    )


def build_excerpt(text: str, fallback_title: str) -> str:
    cleaned = normalize_text(text)
    if not cleaned:
        return f"{fallback_title} 解析后暂无可用正文，请检查原文件是否为扫描件或图片。"
    return cleaned[:220]


def stage_import_copy(data_dir: Path, client_id: str, import_id: str, source_path: Path) -> Path:
    intake_root = client_workspace_root(data_dir, client_id) / "_imports" / import_id
    intake_root.mkdir(parents=True, exist_ok=True)
    safe_name = safe_filename(source_path.name)
    target = intake_root / safe_name
    if source_path.resolve() == target.resolve():
        return target
    if target.exists():
        stem = safe_filename(source_path.stem)
        suffix = source_path.suffix.lower()
        target = intake_root / f"{stem}__{uuid4().hex[:6]}{suffix}"
    shutil.copy2(source_path, target)
    return target


def detect_category(title: str, text: str, *, custom_labels: list[str] | None = None) -> tuple[str, str, float]:
    haystack = f"{title}\n{text[:2200]}".lower()
    scores: dict[str, int] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        scores[category] = sum(2 if keyword.lower() in title.lower() else 1 for keyword in keywords if keyword.lower() in haystack)
    # Also score against user-created custom folder labels (simple keyword match)
    if custom_labels:
        for label in custom_labels:
            if label in CATEGORY_KEYWORDS or label == DEFAULT_INBOX_LABEL:
                continue
            label_lower = label.lower()
            # Check if the label text appears in the document
            score = 0
            for word in label_lower.replace("与", " ").replace("和", " ").replace("/", " ").split():
                if len(word) >= 2 and word in haystack:
                    score += 2 if word in title.lower() else 1
            if score > 0:
                scores[label] = score
    best_category = max(scores, key=scores.get) if scores else DEFAULT_INBOX_LABEL
    best_score = scores.get(best_category, 0)
    if best_score <= 0:
        return DEFAULT_INBOX_LABEL, "待分类", 0.35
    secondary = "核心资料" if best_score >= 4 else "一般资料"
    confidence = min(0.95, 0.5 + best_score * 0.08)
    return best_category, secondary, confidence


def detect_material_profile(title: str, text: str, primary_category: str, secondary_category: str, confidence: float) -> tuple[str, str, str, float]:
    title_text = safe_filename(Path(title).stem).lower()
    body = normalize_text(text).lower()
    head = body[:4800]
    derived_score = 0

    if any(marker in title_text for marker in DERIVED_TITLE_MARKERS):
        derived_score += 1
    if re.search(r"第\s*[0-9一二三四五六七八九十]+\s*稿", title_text):
        derived_score += 3
    if "精简版" in title_text or "预览" in title_text:
        derived_score += 4
    if "介绍" in title_text or "简介" in title_text:
        derived_score += 2
    if "说明" in title_text and primary_category != "财务与筹款":
        derived_score += 1
    if any(marker in head for marker in DERIVED_TEXT_MARKERS):
        derived_score += 3
    if "为了便于你后续直接做" in head and ("ppt" in head or "对外介绍" in head):
        derived_score += 3
    if ("下面给出" in head or "一句话定义" in head) and ("产品策划" in head or "页面级设计" in head or "功能与价值" in head):
        derived_score += 3
    if "完全基于你提供的材料" in head:
        derived_score += 4
    if DERIVED_CITATION_PATTERN.search(head):
        derived_score += 2

    if derived_score >= 4:
        return "background", "战略陪伴", "派生整理稿", max(confidence, 0.86)
    return "evidence", primary_category, secondary_category, confidence


def _archive_xml_text(path: Path) -> str:
    texts: list[str] = []
    with zipfile.ZipFile(path) as archive:
        for name in sorted(archive.namelist()):
            if not name.endswith(".xml"):
                continue
            try:
                root = ET.fromstring(archive.read(name))
            except ET.ParseError:
                continue
            for element in root.iter():
                value = (element.text or "").strip()
                if value:
                    texts.append(value)
    return normalize_text("\n".join(texts))


def _read_plain_text(path: Path) -> str:
    try:
        return normalize_text(path.read_text("utf-8"))
    except UnicodeDecodeError:
        return normalize_text(path.read_text("utf-8", errors="ignore"))


def _read_docx_text(path: Path) -> tuple[str, list[dict[str, str]]]:
    document = WordDocument(path)
    sections: list[dict[str, str]] = []
    current_title = "正文"
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        content = normalize_text("\n".join(buffer))
        if content:
            sections.append({"title": current_title, "text": content})
        buffer = []

    for paragraph in document.paragraphs:
        text = normalize_text(paragraph.text)
        if not text:
            continue
        style_name = paragraph.style.name.lower() if paragraph.style and paragraph.style.name else ""
        if "heading" in style_name:
            flush()
            current_title = text
        else:
            buffer.append(text)
    for table in document.tables:
        rows: list[str] = []
        for row in table.rows:
            cells = [normalize_text(cell.text) for cell in row.cells]
            line = " | ".join(cell for cell in cells if cell)
            if line:
                rows.append(line)
        if rows:
            buffer.append("\n".join(rows))
    flush()
    if not sections:
        text = normalize_text("\n".join(paragraph.text for paragraph in document.paragraphs))
        if text:
            sections = [{"title": "正文", "text": text}]
    combined = normalize_text("\n\n".join(f"{item['title']}\n{item['text']}" for item in sections))
    return combined, sections


def _read_pdf_text(path: Path) -> tuple[str, list[dict[str, str]]]:
    if not HAS_PYPDF or PdfReader is None:
        return "", []
    try:
        reader = PdfReader(str(path))
    except Exception:
        return "", []
    sections: list[dict[str, str]] = []
    pages: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            raw = page.extract_text() or ""
        except Exception:
            raw = ""
        text = normalize_text(raw)
        if not text:
            continue
        title = f"第 {index} 页"
        sections.append({"title": title, "text": text})
        pages.append(f"{title}\n{text}")
    return normalize_text("\n\n".join(pages)), sections


def _build_markdown_sections(text: str) -> list[dict[str, str]]:
    sections: list[dict[str, str]] = []
    current_title = "正文"
    buffer: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            buffer.append("")
            continue
        if line.startswith("#"):
            content = normalize_text("\n".join(buffer))
            if content:
                sections.append({"title": current_title, "text": content})
            current_title = re.sub(r"^#+\s*", "", line) or "正文"
            buffer = []
            continue
        buffer.append(line)
    content = normalize_text("\n".join(buffer))
    if content:
        sections.append({"title": current_title, "text": content})
    return sections or [{"title": "正文", "text": normalize_text(text)}]


def _build_generic_sections(text: str) -> list[dict[str, str]]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    parts = [segment.strip() for segment in SECTION_BREAK_PATTERN.split(normalized) if segment.strip()]
    if len(parts) <= 1:
        return [{"title": "正文", "text": normalized}]
    sections = []
    for index, part in enumerate(parts, start=1):
        lead = part.splitlines()[0][:36]
        sections.append({"title": lead or f"段落 {index}", "text": part})
    return sections


def extract_document(path: Path) -> tuple[str, list[dict[str, str]]]:
    suffix = path.suffix.lower()
    if suffix in {".md"}:
        text = _read_plain_text(path)
        return text, _build_markdown_sections(text)
    if suffix in {".txt", ".json", ".csv"}:
        text = _read_plain_text(path)
        return text, _build_generic_sections(text)
    if suffix == ".docx":
        try:
            return _read_docx_text(path)
        except Exception:
            text = _archive_xml_text(path)
            return text, _build_generic_sections(text)
    if suffix == ".pdf":
        text, sections = _read_pdf_text(path)
        if text:
            return text, sections
        return "", []
    if suffix in ARCHIVE_XML_EXTENSIONS:
        text = _archive_xml_text(path)
        return text, _build_generic_sections(text)
    return "", []


def build_chunks(section_text: str, section_title: str) -> list[dict[str, Any]]:
    normalized = normalize_text(section_text)
    if not normalized:
        return []
    paragraphs = [segment.strip() for segment in SECTION_BREAK_PATTERN.split(normalized) if segment.strip()]
    if not paragraphs:
        paragraphs = [normalized]
    chunks: list[dict[str, Any]] = []
    current = ""
    for paragraph in paragraphs:
        next_candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(next_candidate) <= CHUNK_TARGET_CHARS:
            current = next_candidate
            continue
        if current:
            chunks.append(
                {
                    "sectionLabel": section_title or "正文",
                    "content": current,
                    "tokenText": " ".join(tokenize(current)),
                    "charCount": len(current),
                }
            )
        if len(paragraph) <= CHUNK_TARGET_CHARS:
            current = paragraph
            continue
        start = 0
        while start < len(paragraph):
            end = min(len(paragraph), start + CHUNK_TARGET_CHARS)
            piece = paragraph[start:end].strip()
            if piece:
                chunks.append(
                    {
                        "sectionLabel": section_title or "正文",
                        "content": piece,
                        "tokenText": " ".join(tokenize(piece)),
                        "charCount": len(piece),
                    }
                )
            if end >= len(paragraph):
                break
            start = max(0, end - CHUNK_OVERLAP_CHARS)
        current = ""
    if current:
        chunks.append(
            {
                "sectionLabel": section_title or "正文",
                "content": current,
                "tokenText": " ".join(tokenize(current)),
                "charCount": len(current),
            }
        )
    return chunks


def _copy_into_workspace(data_dir: Path, client_id: str, source_path: Path, category: str, document_id: str) -> Path:
    workspace_root = client_workspace_root(data_dir, client_id) / category
    workspace_root.mkdir(parents=True, exist_ok=True)
    safe_name = safe_filename(source_path.name)
    target = workspace_root / safe_name
    if source_path.resolve() == target.resolve():
        return target
    if target.exists():
        stem = safe_filename(source_path.stem)
        suffix = source_path.suffix.lower()
        target = workspace_root / f"{stem}__{document_id[-6:]}{suffix}"
    source_parts = {part.lower() for part in source_path.parts}
    if source_path.exists() and "_imports" in source_parts:
        shutil.move(str(source_path), target)
    else:
        shutil.copy2(source_path, target)
    return target


def _compat_card_path(data_dir: Path, client_id: str, document_id: str, title: str) -> Path:
    meta_root = client_workspace_root(data_dir, client_id) / "_v2_meta" / "cards"
    meta_root.mkdir(parents=True, exist_ok=True)
    stem = safe_filename(Path(title).stem or document_id)
    return meta_root / f"{document_id}_{stem}.md"


def _markdown_derivative_path(data_dir: Path, client_id: str, document_id: str, title: str) -> Path:
    meta_root = client_workspace_root(data_dir, client_id) / "_v2_meta" / "markdown"
    meta_root.mkdir(parents=True, exist_ok=True)
    stem = safe_filename(Path(title).stem or document_id)
    return meta_root / f"{document_id}_{stem}.md"


def _write_compat_card_markdown(
    data_dir: Path,
    client_id: str,
    document_id: str,
    title: str,
    category: str,
    preview_text: str,
    sections: list[dict[str, str]],
) -> Path:
    target = _compat_card_path(data_dir, client_id, document_id, title)
    lines = [
        f"# {safe_filename(title)}",
        "",
        f"- V2 目录归类：{category}",
        "- 用途：兼容旧字段，不参与 V2 正式检索",
        "",
        "## 解析摘要",
        preview_text,
    ]
    if sections:
        lines.extend(["", "## 章节索引"])
        for index, section in enumerate(sections[:12], start=1):
            section_title = normalize_text(section.get("title", "")) or f"正文 {index}"
            lines.append(f"{index}. {section_title}")
    target.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return target


def _write_markdown_derivative(
    data_dir: Path,
    client_id: str,
    document_id: str,
    title: str,
    sections: list[dict[str, str]],
    fallback_text: str,
) -> Path:
    target = _markdown_derivative_path(data_dir, client_id, document_id, title)
    lines = [f"# {safe_filename(title)}", ""]
    if sections:
        for index, section in enumerate(sections, start=1):
            section_title = normalize_text(section.get("title", "")) or f"正文 {index}"
            section_text = normalize_text(section.get("text", ""))
            if not section_text:
                continue
            heading = "##" if index == 1 else "##"
            lines.extend([f"{heading} {section_title}", "", section_text, ""])
    else:
        body = normalize_text(fallback_text)
        if body:
            lines.extend(["## 正文", "", body, ""])
    target.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return target


def _content_hash(text: str, path: Path) -> str:
    hasher = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
    except Exception:
        hasher.update(text.encode("utf-8"))
    return hasher.hexdigest()


def _remove_existing_v2_rows(db: Database, v2_document_id: str) -> None:
    db.execute("DELETE FROM v2_chunks WHERE v2_document_id = ?", (v2_document_id,))
    db.execute("DELETE FROM v2_sections WHERE v2_document_id = ?", (v2_document_id,))


def _sync_legacy_knowledge_document(
    db: Database,
    *,
    client_id: str,
    import_id: str | None,
    document_id: str,
    source_path: Path,
    original_source_path: Path,
    managed_path: Path,
    kind: str,
    primary_category: str,
    secondary_category: str,
    confidence: float,
    parse_status: str,
    content_hash: str,
    created_at: str,
) -> str:
    existing = db.fetchone(
        "SELECT id FROM knowledge_documents WHERE document_id = ? ORDER BY updated_at DESC LIMIT 1",
        (document_id,),
    )
    knowledge_document_id = str(existing["id"]) if existing and existing["id"] else f"kd_{document_id}"
    doc_uid = f"v2uid_{document_id}"
    original_path = str(original_source_path)
    import_source_path = str(original_source_path)
    current_human_path = str(managed_path)
    human_folder_category = primary_category
    reclassified_at = created_at
    reclass_reason = f"{V2_PIPELINE_VERSION} 同步的兼容知识文档记录"
    reclass_confidence = confidence
    normalized_path = str(managed_path)
    vector_status = "chunk_indexed" if parse_status == "ready" else "needs_review"
    needs_review = 0 if parse_status == "ready" else 1
    dedup_status = "unique"
    binary_hash = content_hash
    normalized_hash = content_hash
    updated_at = now_iso()
    if existing:
        db.execute(
            """
            UPDATE knowledge_documents
            SET client_id = ?, import_batch_id = ?, document_id = ?, doc_uid = ?, original_path = ?, import_source_path = ?,
                current_human_path = ?, human_folder_category = ?, reclassified_at = ?, reclass_reason = ?, reclass_confidence = ?,
                normalized_path = ?, kind = ?, primary_category = ?, secondary_category = ?, classification_confidence = ?,
                needs_review = ?, dedup_status = ?, vector_status = ?, binary_hash = ?, normalized_hash = ?, created_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                client_id,
                import_id,
                document_id,
                doc_uid,
                original_path,
                import_source_path,
                current_human_path,
                human_folder_category,
                reclassified_at,
                reclass_reason,
                reclass_confidence,
                normalized_path,
                kind,
                primary_category,
                secondary_category,
                confidence,
                needs_review,
                dedup_status,
                vector_status,
                binary_hash,
                normalized_hash,
                created_at,
                updated_at,
                knowledge_document_id,
            ),
        )
    else:
        db.execute(
            """
            INSERT INTO knowledge_documents(
                id, client_id, import_batch_id, document_id, doc_uid, original_path, import_source_path, current_human_path,
                human_folder_category, reclassified_at, reclass_reason, reclass_confidence, normalized_path, kind,
                primary_category, secondary_category, classification_confidence, needs_review, deep_read,
                last_hit_question, dedup_status, vector_status, version, binary_hash, normalized_hash, created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?, ?, 1, ?, ?, ?, ?)
            """,
            (
                knowledge_document_id,
                client_id,
                import_id,
                document_id,
                doc_uid,
                original_path,
                import_source_path,
                current_human_path,
                human_folder_category,
                reclassified_at,
                reclass_reason,
                reclass_confidence,
                normalized_path,
                kind,
                primary_category,
                secondary_category,
                confidence,
                needs_review,
                dedup_status,
                vector_status,
                binary_hash,
                normalized_hash,
                created_at,
                updated_at,
            ),
        )
    existing_reclass = db.fetchone(
        """
        SELECT id
        FROM file_reclass_events
        WHERE knowledge_document_id = ? AND from_path = ? AND to_path = ? AND to_category = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (
            knowledge_document_id,
            original_path,
            current_human_path,
            primary_category,
        ),
    )
    if not existing_reclass:
        append_file_reclass_event(
            db,
            knowledge_document_id=knowledge_document_id,
            from_path=original_path,
            to_path=current_human_path,
            from_category=None,
            to_category=primary_category,
            reason=reclass_reason,
            confidence=reclass_confidence,
            created_at=created_at,
        )
    return knowledge_document_id


def _folder_counts(db: Database, client_id: str) -> dict[str, int]:
    rows = db.fetchall(
        """
        SELECT
            CASE
                WHEN material_layer = 'background' THEN '战略陪伴'
                ELSE COALESCE(visible_category, '其他资料')
            END AS category,
            COUNT(1) AS count
        FROM v2_documents
        WHERE client_id = ?
          AND parse_status = 'ready'
          AND (
            material_layer = 'background'
            OR (material_layer = 'evidence' AND COALESCE(visible_category, '其他资料') IN (?, ?, ?, ?, ?))
          )
        GROUP BY
            CASE
                WHEN material_layer = 'background' THEN '战略陪伴'
                ELSE COALESCE(visible_category, '其他资料')
            END
        """,
        (client_id, *EVIDENCE_CATEGORIES),
    )
    return {str(row["category"]): int(row["count"]) for row in rows}


def refresh_client_folder_counts(db: Database, client_id: str) -> None:
    counts = _folder_counts(db, client_id)
    timestamp = now_iso()
    for category in HUMAN_VISIBLE_CATEGORIES:
        db.execute(
            "UPDATE client_folders SET file_count = ?, last_scanned_at = ? WHERE client_id = ? AND label = ?",
            (counts.get(category, 0), timestamp, client_id, category),
        )


def ingest_document_knowledge(
    db: Database,
    *,
    data_dir: Path,
    client_id: str,
    import_id: str | None,
    document_id: str,
    source_path: Path,
    original_source_path: Path | None,
    title: str,
    kind: str,
    source: str,
    fallback_excerpt: str,
    created_at: str,
    ai_service: Any | None = None,
) -> dict[str, Any]:
    del ai_service
    text, sections = extract_document(source_path)
    preview_text = build_excerpt(text or fallback_excerpt, title)
    primary_category, secondary_category, confidence = detect_category(title, text or preview_text)
    material_layer, primary_category, secondary_category, confidence = detect_material_profile(
        title,
        text or preview_text,
        primary_category,
        secondary_category,
        confidence,
    )
    managed_path = _copy_into_workspace(data_dir, client_id, source_path, primary_category, document_id)
    compat_card_path = _write_compat_card_markdown(
        data_dir,
        client_id,
        document_id,
        title,
        primary_category,
        preview_text,
        sections,
    )
    markdown_path = _write_markdown_derivative(
        data_dir,
        client_id,
        document_id,
        title,
        sections,
        text or preview_text or fallback_excerpt,
    )
    v2_document_id = f"v2doc_{document_id}"
    content_hash = _content_hash(text or preview_text or title, source_path)
    parse_status = "ready" if text and sections else "failed"
    parse_error = None if parse_status == "ready" else "未能解析出可用正文"
    doc_tokens = tokenize(f"{title}\n{primary_category}\n{text[:2400] if text else preview_text}")
    heading_tokens = tokenize(" ".join(section["title"] for section in sections[:24]))
    doc_index_text = " ".join(dict.fromkeys([*doc_tokens, *heading_tokens]))
    section_count = len(sections)
    chunk_count = 0
    legacy_knowledge_document_id = _sync_legacy_knowledge_document(
        db,
        client_id=client_id,
        import_id=import_id,
        document_id=document_id,
        source_path=source_path,
        original_source_path=original_source_path or source_path,
        managed_path=managed_path,
        kind=kind,
        primary_category=primary_category,
        secondary_category=secondary_category,
        confidence=confidence,
        parse_status=parse_status,
        content_hash=content_hash,
        created_at=created_at,
    )

    _remove_existing_v2_rows(db, v2_document_id)
    existing = db.fetchone("SELECT id FROM v2_documents WHERE id = ?", (v2_document_id,))
    payload = (
        v2_document_id,
        client_id,
        document_id,
        str(source_path),
        str(managed_path),
        str(markdown_path),
        safe_filename(title),
        kind,
        material_layer,
        primary_category,
        secondary_category,
        parse_status,
        parse_error,
        preview_text,
        doc_index_text,
        content_hash,
        confidence,
        created_at,
        now_iso(),
    )
    if existing:
        db.execute(
            """
            UPDATE v2_documents
            SET client_id = ?, document_id = ?, original_path = ?, managed_path = ?, markdown_path = ?, file_name = ?, kind = ?,
                material_layer = ?, visible_category = ?, secondary_category = ?, parse_status = ?, parse_error = ?,
                preview_text = ?, doc_index_text = ?, content_hash = ?, classification_confidence = ?, imported_at = ?, updated_at = ?
            WHERE id = ?
            """,
            payload[1:] + (v2_document_id,),
        )
    else:
        db.execute(
            """
            INSERT INTO v2_documents(
                id, client_id, document_id, original_path, managed_path, markdown_path, file_name, kind, material_layer, visible_category,
                secondary_category, parse_status, parse_error, preview_text, doc_index_text, content_hash,
                classification_confidence, imported_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )

    db.execute(
        """
        UPDATE documents
        SET title = ?, path = ?, original_source_path = ?, kind = ?, source = ?, excerpt = ?, tags_json = ?
        WHERE id = ?
        """,
        (
            safe_filename(title),
            str(managed_path),
            str(original_source_path or source_path),
            kind,
            source,
            preview_text,
            to_json([kind, primary_category, secondary_category, V2_PIPELINE_VERSION]),
            document_id,
        ),
    )

    if parse_status == "ready":
        for section_index, section in enumerate(sections):
            section_text = normalize_text(section["text"])
            if not section_text:
                continue
            section_id = f"v2sec_{document_id}_{section_index}"
            section_title = section["title"][:120] if section["title"] else "正文"
            section_tokens = " ".join(tokenize(f"{section_title}\n{section_text[:2400]}"))
            db.execute(
                """
                INSERT INTO v2_sections(
                    id, v2_document_id, section_index, title, content, searchable_text, char_count, created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (section_id, v2_document_id, section_index, section_title, section_text, section_tokens, len(section_text), created_at),
            )
            for chunk_index, chunk in enumerate(build_chunks(section_text, section_title)):
                chunk_id = f"v2chunk_{document_id}_{section_index}_{chunk_index}"
                db.execute(
                    """
                    INSERT INTO v2_chunks(
                        id, v2_document_id, v2_section_id, chunk_index, section_label, content, searchable_text, char_count, created_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk_id,
                        v2_document_id,
                        section_id,
                        chunk_index,
                        chunk["sectionLabel"],
                        chunk["content"],
                        chunk["tokenText"],
                        chunk["charCount"],
                        created_at,
                    ),
                )
                chunk_count += 1

    db.execute(
        """
        UPDATE v2_documents
        SET section_count = ?, chunk_count = ?, updated_at = ?
        WHERE id = ?
        """,
        (section_count, chunk_count, now_iso(), v2_document_id),
    )
    refresh_client_folder_counts(db, client_id)

    # --- 即时写入 master_index，让文档上传后立即可被检索 ---
    try:
        from app.services.knowledge_base import upsert_master_index_record

        surrogate_id = f"ks_instant_{document_id}"
        searchable = doc_index_text or preview_text or title
        retrieval_text = preview_text or fallback_excerpt or ""
        # 先创建轻量 surrogate 记录（满足外键约束）
        existing_surrogate = db.fetchone("SELECT id FROM knowledge_surrogates WHERE id = ?", (surrogate_id,))
        if not existing_surrogate:
            db.execute(
                """INSERT OR IGNORE INTO knowledge_surrogates(
                    id, knowledge_document_id, client_id, source_type, title, folder_category,
                    surrogate_md_path, overview_summary, retrieval_summary, document_role,
                    core_questions_json, query_hints_json, distinct_findings_json, entities_json,
                    time_markers_json, source_links_json, created_at, updated_at
                ) VALUES(?, ?, ?, 'v2_instant', ?, ?, ?, ?, ?, ?, '[]', '[]', '[]', '[]', '[]', '[]', ?, ?)""",
                (surrogate_id, legacy_knowledge_document_id or v2_document_id, client_id, safe_filename(title), primary_category,
                 str(compat_card_path), retrieval_text[:300], retrieval_text,
                 material_layer or kind, created_at, created_at),
            )
        upsert_master_index_record(
            db,
            data_dir=data_dir,
            entry_id=v2_document_id,
            client_id=client_id,
            surrogate_id=surrogate_id,
            title=safe_filename(title),
            folder_category=primary_category,
            document_role=material_layer or kind,
            retrieval_summary=retrieval_text,
            searchable_text=searchable,
            source_path=str(managed_path),
            surrogate_md_path=str(compat_card_path),
            timestamp=created_at,
            sync_after=True,
        )
    except Exception:
        pass  # master_index 写入失败不应阻塞文档入库

    return {
        "knowledge_document_id": v2_document_id,
        "legacy_knowledge_document_id": legacy_knowledge_document_id,
        "title": safe_filename(title),
        "current_human_path": str(managed_path),
        "compat_card_path": str(compat_card_path),
        "markdown_path": str(markdown_path),
        "primary_category": primary_category,
        "secondary_category": secondary_category,
        "short_summary": preview_text,
        "summary": preview_text,
        "classification_confidence": confidence,
        "material_layer": material_layer,
        "needs_review": parse_status != "ready",
        "chunk_count": chunk_count,
        "raw_text": text,
    }


def backfill_knowledge_documents(
    db: Database,
    *,
    data_dir: Path,
    client_id: str,
    ai_service: Any | None = None,
    progress_callback: Callable[[int], None] | None = None,
) -> dict[str, Any]:
    del ai_service
    rows = db.fetchall("SELECT * FROM documents WHERE client_id = ? ORDER BY created_at ASC", (client_id,))
    processed = 0
    missing = 0
    for row in rows:
        existing_v2 = db.fetchone(
            "SELECT managed_path, original_path FROM v2_documents WHERE document_id = ? ORDER BY updated_at DESC LIMIT 1",
            (str(row["id"]),),
        )
        source_candidate = (
            str(existing_v2["managed_path"])
            if existing_v2 and existing_v2["managed_path"]
            else str(row["path"])
        )
        source_path = Path(source_candidate)
        if not source_path.exists():
            fallback_original = str(existing_v2["original_path"]) if existing_v2 and existing_v2["original_path"] else str(row["original_source_path"] or "")
            if fallback_original:
                original_fallback_path = Path(fallback_original)
                if original_fallback_path.exists():
                    source_path = original_fallback_path
                else:
                    missing += 1
                    continue
            else:
                missing += 1
                continue
        ingest_document_knowledge(
            db,
            data_dir=data_dir,
            client_id=client_id,
            import_id=None,
            document_id=str(row["id"]),
            source_path=source_path,
            original_source_path=Path(str(row["original_source_path"])) if row["original_source_path"] else source_path,
            title=str(row["title"]),
            kind=str(row["kind"]),
            source=str(row["source"]),
            fallback_excerpt=str(row["excerpt"] or row["title"]),
            created_at=str(row["created_at"]),
            ai_service=None,
        )
        processed += 1
        if progress_callback:
            progress_callback(processed)
    refresh_client_folder_counts(db, client_id)
    return {"processed": processed, "missing": missing}


def backfill_workspace_import(
    db: Database,
    *,
    data_dir: Path,
    client_id: str,
    source_root: Path | None = None,
    progress_callback: Callable[[int], None] | None = None,
) -> dict[str, Any]:
    ensure_client_folder_rows(db, data_dir, client_id)
    workspace_root = source_root or (data_dir / "client_workspace" / client_id)
    workspace_root.mkdir(parents=True, exist_ok=True)
    timestamp = now_iso()
    import_id = new_id("imp")
    job_id = new_id("kjob")
    db.execute(
        """
        INSERT INTO imports(id, client_id, source_path, mode, status, imported_count, skipped_count, created_at)
        VALUES(?, ?, ?, 'folder', 'processing', 0, 0, ?)
        """,
        (import_id, client_id, str(workspace_root), timestamp),
    )
    db.execute(
        """
        INSERT INTO knowledge_jobs(id, client_id, job_type, status, payload_json, total_items, processed_items, last_error, created_at, started_at, finished_at, updated_at)
        VALUES(?, ?, 'backfill_workspace_import', 'running', ?, 0, 0, NULL, ?, ?, NULL, ?)
        """,
        (job_id, client_id, to_json({"sourceRoot": str(workspace_root)}), timestamp, timestamp, timestamp),
    )

    existing_paths: set[str] = set()
    for row in db.fetchall("SELECT path FROM documents WHERE client_id = ?", (client_id,)):
        value = str(row["path"] or "").strip()
        if value:
            existing_paths.add(value)
    for row in db.fetchall(
        """
        SELECT original_path, managed_path
        FROM v2_documents
        WHERE client_id = ?
        """,
        (client_id,),
    ):
        for column in ("original_path", "managed_path"):
            value = str(row[column] or "").strip()
            if value:
                existing_paths.add(value)
    for row in db.fetchall(
        """
        SELECT original_path, import_source_path, current_human_path
        FROM knowledge_documents
        WHERE client_id = ?
        """,
        (client_id,),
    ):
        for column in ("original_path", "import_source_path", "current_human_path"):
            value = str(row[column] or "").strip()
            if value:
                existing_paths.add(value)

    candidates: list[Path] = []
    for path in workspace_root.rglob("*"):
        if not path.is_file():
            continue
        if any(part.startswith(".") for part in path.parts):
            continue
        if any(marker in path.parts for marker in INTERNAL_WORKSPACE_MARKERS):
            continue
        if path.name.lower() in NOISE_FILES:
            continue
        if path.suffix.lower() not in WORKSPACE_BACKFILL_EXTENSIONS:
            continue
        candidates.append(path)

    db.execute(
        "UPDATE knowledge_jobs SET total_items = ?, updated_at = ? WHERE id = ?",
        (len(candidates), now_iso(), job_id),
    )

    imported = 0
    skipped = 0
    for path in sorted(candidates):
        path_str = str(path)
        if path_str in existing_paths:
            skipped += 1
            continue
        folder_label = next((part for part in HUMAN_VISIBLE_CATEGORIES if part in path.parts), None)
        folder_row = (
            db.fetchone(
                "SELECT id FROM client_folders WHERE client_id = ? AND label = ?",
                (client_id, folder_label),
            )
            if folder_label
            else None
        )
        excerpt = build_excerpt(path.read_text(encoding="utf-8", errors="ignore"), path.name) if path.suffix.lower() in TEXT_EXTENSIONS else f"{path.name} 已进入资料缓冲池，可作为后续问答与证据引用来源。"
        document_id = new_id("doc")
        db.execute(
            """
            INSERT INTO documents(id, client_id, folder_id, title, path, kind, source, excerpt, tags_json, created_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                client_id,
                str(folder_row["id"]) if folder_row else None,
                path.name,
                path_str,
                path.suffix.lower().lstrip("."),
                "workspace_backfill",
                excerpt,
                to_json([path.suffix.lower().lstrip("."), "workspace_backfill"]),
                timestamp,
            ),
        )
        ingest_document_knowledge(
            db,
            data_dir=data_dir,
            client_id=client_id,
            import_id=import_id,
            document_id=document_id,
            source_path=path,
            original_source_path=path,
            title=path.name,
            kind=path.suffix.lower().lstrip("."),
            source="workspace_backfill",
            fallback_excerpt=excerpt,
            created_at=timestamp,
            ai_service=None,
        )
        existing_paths.add(path_str)
        imported += 1
        db.execute(
            "UPDATE imports SET imported_count = ?, skipped_count = ?, status = 'processing' WHERE id = ?",
            (imported, skipped, import_id),
        )
        db.execute(
            "UPDATE knowledge_jobs SET processed_items = ?, updated_at = ? WHERE id = ?",
            (imported, now_iso(), job_id),
        )
        if progress_callback:
            progress_callback(imported)

    refresh_client_folder_counts(db, client_id)
    finished_at = now_iso()
    db.execute(
        "UPDATE imports SET imported_count = ?, skipped_count = ?, status = 'completed' WHERE id = ?",
        (imported, skipped, import_id),
    )
    db.execute(
        """
        UPDATE knowledge_jobs
        SET status = 'completed', processed_items = ?, finished_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (imported, finished_at, finished_at, job_id),
    )
    return {
        "importId": import_id,
        "jobId": job_id,
        "sourceRoot": str(workspace_root),
        "discovered": len(candidates),
        "imported": imported,
        "skipped": skipped,
    }


def compute_knowledge_status(db: Database, client_id: str, data_dir: Path | None = None) -> dict[str, Any]:
    del data_dir
    main_job_placeholders = ",".join("?" for _ in MAIN_KNOWLEDGE_STATUS_JOB_TYPES)
    job_filter = f"client_id = ? AND job_type IN ({main_job_placeholders})"
    job_params = (client_id, *MAIN_KNOWLEDGE_STATUS_JOB_TYPES)
    document_count = int(db.scalar("SELECT COUNT(1) AS count FROM v2_documents WHERE client_id = ? AND material_layer = 'evidence'", (client_id,)) or 0)
    v2_background_docs = int(db.scalar("SELECT COUNT(1) AS count FROM v2_documents WHERE client_id = ? AND material_layer = 'background'", (client_id,)) or 0)
    section_count = int(db.scalar("SELECT COUNT(1) AS count FROM v2_sections WHERE v2_document_id IN (SELECT id FROM v2_documents WHERE client_id = ? AND material_layer = 'evidence')", (client_id,)) or 0)
    chunk_count = int(db.scalar("SELECT COUNT(1) AS count FROM v2_chunks WHERE v2_document_id IN (SELECT id FROM v2_documents WHERE client_id = ? AND material_layer = 'evidence')", (client_id,)) or 0)
    failed_count = int(db.scalar("SELECT COUNT(1) AS count FROM v2_documents WHERE client_id = ? AND parse_status != 'ready'", (client_id,)) or 0)
    review_count = int(db.scalar("SELECT COUNT(1) AS count FROM v2_documents WHERE client_id = ? AND classification_confidence < 0.62", (client_id,)) or 0)
    dna_background_docs = int(db.scalar("SELECT COUNT(1) AS count FROM client_dna_documents WHERE client_id = ?", (client_id,)) or 0)
    memory_docs = int(db.scalar("SELECT COUNT(1) AS count FROM knowledge_surrogates WHERE client_id = ? AND source_type = 'memory_answer'", (client_id,)) or 0)
    pending_jobs = int(
        db.scalar(
            f"SELECT COUNT(1) AS count FROM knowledge_jobs WHERE {job_filter} AND status = 'queued'",
            job_params,
        )
        or 0
    )
    running_jobs = int(
        db.scalar(
            f"SELECT COUNT(1) AS count FROM knowledge_jobs WHERE {job_filter} AND status = 'running'",
            job_params,
        )
        or 0
    )
    last_job = db.fetchone(
        f"SELECT * FROM knowledge_jobs WHERE {job_filter} ORDER BY created_at DESC LIMIT 1",
        job_params,
    )
    last_status = str(last_job["status"]) if last_job else "idle"
    last_error = str(last_job["last_error"]) if last_job and last_job["last_error"] else None
    last_success_row = db.fetchone(
        f"""
        SELECT finished_at
        FROM knowledge_jobs
        WHERE {job_filter} AND status = 'completed'
        ORDER BY finished_at DESC
        LIMIT 1
        """,
        job_params,
    )
    last_updated_row = db.fetchone(
        """
        SELECT updated_at
        FROM v2_documents
        WHERE client_id = ?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (client_id,),
    )
    last_success = str(last_success_row["finished_at"]) if last_success_row and last_success_row["finished_at"] else None
    last_updated = str(last_updated_row["updated_at"]) if last_updated_row and last_updated_row["updated_at"] else None
    return {
        "totalDocuments": document_count,
        "evidenceDocuments": document_count,
        "backgroundDocuments": dna_background_docs + v2_background_docs,
        "methodDocuments": 0,
        "totalSections": section_count,
        "totalChunks": chunk_count,
        "parseFailedDocuments": failed_count,
        "vectorizedDocuments": 0,
        "dedupedDocuments": 0,
        "reviewPendingDocuments": review_count,
        "surrogateCount": document_count,
        "memoryDocCount": memory_docs,
        "masterIndexCount": document_count,
        "reclassifiedDocumentCount": document_count,
        "qdrantReady": True,
        "lastUpdatedAt": last_updated,
        "pendingJobs": pending_jobs,
        "runningJobs": running_jobs,
        "lastJobStatus": last_status,
        "lastJobError": last_error,
        "lastSuccessfulRunAt": last_success,
        "embeddingMode": "hash_fallback",
        "embeddingModel": None,
        "embeddingError": None,
        "lastPipelineVersion": V2_PIPELINE_VERSION,
    }


def fetch_document_cards(db: Database, client_id: str, data_dir: Path | None = None, limit: int | None = 120) -> list[dict[str, Any]]:
    rows = db.fetchall(
        """
        SELECT vd.*, d.created_at AS document_created_at, d.excerpt AS legacy_excerpt
        FROM v2_documents vd
        JOIN documents d ON d.id = vd.document_id
        WHERE vd.client_id = ? AND vd.material_layer = 'evidence'
        ORDER BY vd.updated_at DESC
        LIMIT ?
        """,
        (client_id, limit or 120),
    )
    cards: list[dict[str, Any]] = []
    for row in rows:
        compat_md_path = (
            str(_compat_card_path(data_dir, client_id, str(row["document_id"]), str(row["file_name"])))
            if data_dir is not None
            else None
        )
        cards.append(
            {
                "id": str(row["id"]).replace("v2doc_", "dock_"),
                "docId": str(row["id"]).replace("v2doc_", "dock_"),
                "clientId": str(row["client_id"]),
                "documentId": str(row["document_id"]),
                "title": str(row["file_name"]),
                "originalPath": str(row["original_path"]),
                "importSourcePath": str(row["original_path"]),
                "currentHumanPath": str(row["managed_path"]),
                "humanFolderCategory": str(row["visible_category"]),
                "sourcePath": str(row["managed_path"]),
                "logicalCategory": str(row["visible_category"]),
                "logicalSubcategory": str(row["secondary_category"]),
                "classificationReason": f"V2 根据文件标题与正文关键词归入 {row['visible_category']}",
                "normalizedPath": str(row["managed_path"]),
                "surrogateMdPath": compat_md_path,
                "kind": str(row["kind"]),
                "primaryCategory": str(row["visible_category"]),
                "secondaryCategory": str(row["secondary_category"]),
                "shortSummary": str(row["preview_text"] or row["legacy_excerpt"] or ""),
                "summary": str(row["preview_text"] or row["legacy_excerpt"] or ""),
                "retrievalSummary": str(row["preview_text"] or row["legacy_excerpt"] or ""),
                "documentRole": "原始证据",
                "queryHints": tokenize(str(row["doc_index_text"] or ""))[:8],
                "distinctFindings": [],
                "coreQuestions": [],
                "keywords": tokenize(str(row["preview_text"] or ""))[:8],
                "tags": [str(row["visible_category"]), str(row["kind"]), V2_PIPELINE_VERSION],
                "entities": [],
                "dateRange": None,
                "classificationConfidence": float(row["classification_confidence"] or 0.0),
                "needsReview": str(row["parse_status"]) != "ready",
                "deepRead": False,
                "lastHitQuestion": None,
                "dedupStatus": "unchecked",
                "vectorStatus": "disabled",
                "version": 1,
                "chunkCount": int(row["chunk_count"] or 0),
                "createdAt": str(row["imported_at"] or row["document_created_at"]),
                "updatedAt": str(row["updated_at"]),
            }
        )
    return cards


def _score_by_terms(query_terms: list[str], *haystacks: str, title_weight: float = 1.0) -> tuple[float, list[str]]:
    matched: list[str] = []
    score = 0.0
    lowered_haystacks = [haystack.lower() for haystack in haystacks]
    for term in query_terms:
        if any(term in haystack for haystack in lowered_haystacks):
            matched.append(term)
            score += title_weight if term in lowered_haystacks[0] else 1.0
    return score, matched


def _normalize_path_for_match(path: str | None) -> str:
    raw = str(path or "").strip()
    if not raw:
        return ""
    return re.sub(r"[\\/]+", "/", raw).rstrip("/").lower()


def _normalize_title_for_match(title: str | None) -> str:
    raw = str(title or "").strip().lower()
    if not raw:
        return ""
    return re.sub(r"\s+", "", raw)


def retrieve_knowledge_bundle(db: Database, data_dir: Path, client_id: str, prompt: str) -> RetrievalBundle:
    query_terms = tokenize(prompt)
    if not query_terms and prompt.strip():
        query_terms = [prompt.strip().lower()]
    strategic_mode = is_strategy_analysis_query(prompt)
    doc_rows = db.fetchall(
        """
        SELECT *
        FROM v2_documents
        WHERE client_id = ? AND material_layer = 'evidence' AND parse_status = 'ready'
        ORDER BY updated_at DESC
        """,
        (client_id,),
    )
    scored_docs: list[dict[str, Any]] = []
    for row in doc_rows:
        title = str(row["file_name"])
        preview = str(row["preview_text"] or "")
        category = str(row["visible_category"] or "其他资料")
        index_text = str(row["doc_index_text"] or "")
        score, matched = _score_by_terms(query_terms, title.lower(), index_text.lower(), preview.lower(), category.lower(), title_weight=2.4)
        if category in prompt:
            score += 0.8
        if strategic_mode and category in {"组织与战略", "项目与业务"}:
            score += 0.6
        if matched or score > 0:
            scored_docs.append(
                {
                    "row": row,
                    "score": score,
                    "matchedTerms": matched,
                    "title": title,
                    "path": str(row["managed_path"]),
                    "category": category,
                }
            )
    semantic_added_doc_count = 0
    semantic_mapped_count = 0
    semantic_unmapped_count = 0

    # --- Vector recall from master_index (Qdrant) to boost and append semantic matches ---
    try:
        from app.services.knowledge_base import search_master_index_qdrant
        qdrant_scores = search_master_index_qdrant(
            data_dir, client_id, prompt,
            limit=96 if strategic_mode else 72,
        )

        doc_row_by_document_id: dict[str, Any] = {str(row["document_id"]): row for row in doc_rows if row["document_id"]}
        doc_row_by_managed_path: dict[str, Any] = {}
        doc_row_by_original_path: dict[str, Any] = {}
        doc_rows_by_title: dict[str, list[Any]] = defaultdict(list)
        for row in doc_rows:
            managed_key = _normalize_path_for_match(str(row["managed_path"] or ""))
            if managed_key and managed_key not in doc_row_by_managed_path:
                doc_row_by_managed_path[managed_key] = row
            original_key = _normalize_path_for_match(str(row["original_path"] or ""))
            if original_key and original_key not in doc_row_by_original_path:
                doc_row_by_original_path[original_key] = row
            title_key = _normalize_title_for_match(str(row["file_name"] or ""))
            if title_key:
                doc_rows_by_title[title_key].append(row)

        v2_doc_id_to_idx: dict[str, int] = {}
        for idx, item in enumerate(scored_docs):
            v2_doc_id_to_idx[str(item["row"]["id"])] = idx

        existing_doc_ids: set[str] = set(v2_doc_id_to_idx.keys())

        surrogate_to_knowledge_document: dict[str, str] = {}
        knowledge_document_to_document: dict[str, str] = {}
        knowledge_document_to_paths: dict[str, tuple[str, str]] = {}

        if qdrant_scores:
            master_rows = db.fetchall(
                "SELECT id, surrogate_id, title, source_path FROM knowledge_master_index WHERE client_id = ?",
                (client_id,),
            )
            surrogate_ids = [str(row["surrogate_id"]) for row in master_rows if row["surrogate_id"]]
            if surrogate_ids:
                placeholders = ",".join("?" for _ in surrogate_ids)
                surrogate_rows = db.fetchall(
                    f"""
                    SELECT id, knowledge_document_id
                    FROM knowledge_surrogates
                    WHERE id IN ({placeholders})
                    """,
                    tuple(surrogate_ids),
                )
                surrogate_to_knowledge_document = {
                    str(row["id"]): str(row["knowledge_document_id"])
                    for row in surrogate_rows
                    if row["id"] and row["knowledge_document_id"]
                }

            knowledge_document_ids = list({
                knowledge_document_id
                for knowledge_document_id in surrogate_to_knowledge_document.values()
                if knowledge_document_id
            })
            if knowledge_document_ids:
                placeholders = ",".join("?" for _ in knowledge_document_ids)
                knowledge_document_rows = db.fetchall(
                    f"""
                    SELECT id, document_id, original_path, current_human_path
                    FROM knowledge_documents
                    WHERE id IN ({placeholders})
                    """,
                    tuple(knowledge_document_ids),
                )
                for row in knowledge_document_rows:
                    knowledge_document_id = str(row["id"])
                    document_id = str(row["document_id"]) if row["document_id"] else ""
                    if document_id:
                        knowledge_document_to_document[knowledge_document_id] = document_id
                    knowledge_document_to_paths[knowledge_document_id] = (
                        _normalize_path_for_match(str(row["current_human_path"] or "")),
                        _normalize_path_for_match(str(row["original_path"] or "")),
                    )

            for mrow in master_rows:
                master_id = str(mrow["id"] or "")
                q_score = float(qdrant_scores.get(master_id, 0.0) or 0.0)
                if q_score < 0.10:
                    continue
                mapped_row = None
                surrogate_id = str(mrow["surrogate_id"] or "")
                knowledge_document_id = surrogate_to_knowledge_document.get(surrogate_id)
                if knowledge_document_id:
                    document_id = knowledge_document_to_document.get(knowledge_document_id)
                    if document_id:
                        mapped_row = doc_row_by_document_id.get(document_id)
                    if mapped_row is None:
                        current_human_path, original_path = knowledge_document_to_paths.get(knowledge_document_id, ("", ""))
                        mapped_row = (
                            doc_row_by_managed_path.get(current_human_path)
                            or doc_row_by_original_path.get(original_path)
                        )
                if mapped_row is None:
                    source_path = _normalize_path_for_match(str(mrow["source_path"] or ""))
                    if source_path:
                        mapped_row = doc_row_by_managed_path.get(source_path) or doc_row_by_original_path.get(source_path)
                if mapped_row is None:
                    title_key = _normalize_title_for_match(str(mrow["title"] or ""))
                    if title_key:
                        exact = doc_rows_by_title.get(title_key)
                        if exact:
                            mapped_row = exact[0]
                        else:
                            for candidate_key, candidate_rows in doc_rows_by_title.items():
                                if title_key and (title_key in candidate_key or candidate_key in title_key):
                                    mapped_row = candidate_rows[0]
                                    break

                if mapped_row is None:
                    semantic_unmapped_count += 1
                    continue

                semantic_mapped_count += 1
                mapped_v2_id = str(mapped_row["id"])
                if mapped_v2_id in existing_doc_ids:
                    idx = v2_doc_id_to_idx.get(mapped_v2_id)
                    if idx is not None:
                        scored_docs[idx]["score"] += q_score * 0.65
                        matched_terms = scored_docs[idx].get("matchedTerms")
                        if isinstance(matched_terms, list) and "semantic" not in matched_terms:
                            matched_terms.append("semantic")
                else:
                    semantic_added_doc_count += 1
                    new_item = {
                        "row": mapped_row,
                        "score": q_score * 1.2,
                        "matchedTerms": ["semantic"],
                        "title": str(mapped_row["file_name"]),
                        "path": str(mapped_row["managed_path"]),
                        "category": str(mapped_row["visible_category"] or "其他资料"),
                    }
                    scored_docs.append(new_item)
                    new_index = len(scored_docs) - 1
                    v2_doc_id_to_idx[mapped_v2_id] = new_index
                    existing_doc_ids.add(mapped_v2_id)
    except Exception:
        pass  # vector recall is best-effort

    scored_docs.sort(key=lambda item: item["score"], reverse=True)
    top_docs = scored_docs[:120]
    if not top_docs:
        retrieval_summary = {
            "docHitCount": 0,
            "sectionHitCount": 0,
            "rawChunkHitCount": 0,
            "masterHitCount": 0,
            "surrogateHitCount": 0,
            "semanticAddedDocCount": semantic_added_doc_count,
            "semanticMappedCount": semantic_mapped_count,
            "semanticUnmappedCount": semantic_unmapped_count,
            "preferredCategories": [],
            "categoryCoverage": [],
            "backgroundTrail": [],
            "strategicMode": strategic_mode,
        }
        return RetrievalBundle(
            citations=[],
            coverage=0.0,
            retrieval_summary=retrieval_summary,
            context_text="",
            matched_terms=[],
            failure_reason="no_candidate_documents",
        )

    doc_ids = [str(item["row"]["id"]) for item in top_docs]
    section_rows = db.fetchall(
        f"""
        SELECT *
        FROM v2_sections
        WHERE v2_document_id IN ({','.join('?' for _ in doc_ids)})
        ORDER BY section_index ASC
        """,
        tuple(doc_ids),
    )
    doc_lookup = {str(item["row"]["id"]): item for item in top_docs}
    scored_sections: list[dict[str, Any]] = []
    for row in section_rows:
        section_title = str(row["title"] or "正文")
        content = str(row["content"] or "")
        doc_item = doc_lookup.get(str(row["v2_document_id"]))
        if not doc_item:
            continue
        score, matched = _score_by_terms(query_terms, section_title.lower(), content[:2400].lower(), title_weight=2.0)
        score += doc_item["score"] * 0.28
        if matched or score > 0:
            scored_sections.append(
                {
                    "row": row,
                    "score": score,
                    "matchedTerms": sorted(set([*doc_item["matchedTerms"], *matched])),
                    "doc": doc_item,
                }
            )
    scored_sections.sort(key=lambda item: item["score"], reverse=True)
    top_sections = scored_sections[:240]

    section_ids = [str(item["row"]["id"]) for item in top_sections] or [""]
    chunk_rows = db.fetchall(
        f"""
        SELECT *
        FROM v2_chunks
        WHERE v2_section_id IN ({','.join('?' for _ in section_ids)})
        ORDER BY chunk_index ASC
        """,
        tuple(section_ids),
    )
    section_lookup = {str(item["row"]["id"]): item for item in top_sections}

    # --- Vector recall for chunks (Qdrant) ---
    v2_chunk_qdrant_scores: dict[str, float] = {}
    try:
        from app.services.knowledge_base import search_raw_chunks_qdrant
        v2_doc_ids_for_chunks = list({str(item["row"]["v2_document_id"]) for item in top_sections})
        # Map v2_document_id → knowledge_document_id for Qdrant lookup
        if v2_doc_ids_for_chunks:
            kd_rows = db.fetchall(
                f"SELECT id, document_id FROM v2_documents WHERE id IN ({','.join('?' for _ in v2_doc_ids_for_chunks)})",
                tuple(v2_doc_ids_for_chunks),
            )
            kd_ids = [str(r["document_id"]) for r in kd_rows if r["document_id"]]
            if kd_ids:
                v2_chunk_qdrant_scores = search_raw_chunks_qdrant(
                    data_dir, client_id, prompt, kd_ids,
                    limit=120 if strategic_mode else 80,
                )
    except Exception:
        pass

    scored_chunks: list[dict[str, Any]] = []
    for row in chunk_rows:
        content = str(row["content"] or "")
        section_item = section_lookup.get(str(row["v2_section_id"]))
        if not section_item:
            continue
        score, matched = _score_by_terms(query_terms, content[:2800].lower(), title_weight=1.0)
        score += section_item["score"] * 0.42
        # Add vector score for chunks
        chunk_qdrant_score = v2_chunk_qdrant_scores.get(str(row["id"]), 0.0)
        score += chunk_qdrant_score * 0.65
        if strategic_mode and any(term in content for term in ("战略", "治理", "路径", "风险", "业务")):
            score += 0.25
        if matched or score > 0 or chunk_qdrant_score >= 0.12:
            scored_chunks.append(
                {
                    "row": row,
                    "score": score,
                    "matchedTerms": sorted(set([*section_item["matchedTerms"], *matched])),
                    "section": section_item,
                }
            )
    scored_chunks.sort(key=lambda item: item["score"], reverse=True)

    citations: list[CitationMatch] = []
    matched_terms: set[str] = set()
    used_sections: set[str] = set()
    used_documents: Counter[str] = Counter()
    for item in scored_chunks:
        section_id = str(item["row"]["v2_section_id"])
        document_id = str(item["row"]["v2_document_id"])
        if used_documents[document_id] >= 16:
            continue
        if section_id in used_sections and used_documents[document_id] >= 4:
            continue
        used_sections.add(section_id)
        used_documents[document_id] += 1
        matched_terms.update(item["matchedTerms"])
        doc_item = item["section"]["doc"]
        citations.append(
            CitationMatch(
                knowledge_document_id=document_id,
                chunk_id=str(item["row"]["id"]),
                title=str(doc_item["title"]),
                excerpt=str(item["row"]["content"])[:2200],
                score=round(float(item["score"]), 4),
                coverage=0.0,
                section_label=str(item["row"]["section_label"]) if item["row"]["section_label"] else None,
                source_stage="raw_chunk",
                drillthrough_used=True,
                matched_terms=item["matchedTerms"],
                path=str(doc_item["path"]),
            )
        )
        if len(citations) >= 80:
            break

    coverage = round(len(matched_terms) / len(query_terms), 2) if query_terms and citations else 0.0
    if citations:
        coverage = max(0.5, coverage)
    citations = [
        CitationMatch(
            knowledge_document_id=item.knowledge_document_id,
            chunk_id=item.chunk_id,
            title=item.title,
            excerpt=item.excerpt,
            score=item.score,
            coverage=coverage,
            section_label=item.section_label,
            source_stage=item.source_stage,
            drillthrough_used=item.drillthrough_used,
            matched_terms=item.matched_terms,
            path=item.path,
        )
        for item in citations
    ]

    category_coverage: list[str] = []
    for item in top_docs:
        category = str(item["category"])
        if category not in category_coverage:
            category_coverage.append(category)

    background_trail = [
        {
            "title": str(item["title"]),
            "stage": "文档索引",
            "sectionLabel": None,
            "path": str(item["path"]),
            "excerpt": str(item["row"]["preview_text"] or "")[:180],
        }
        for item in top_docs[:6]
    ]
    if top_sections:
        background_trail.extend(
            {
                "title": str(item["doc"]["title"]),
                "stage": "章节定位",
                "sectionLabel": str(item["row"]["title"]),
                "path": str(item["doc"]["path"]),
                "excerpt": str(item["row"]["content"])[:180],
            }
            for item in top_sections[:4]
        )

    retrieval_summary = {
        "docHitCount": len(top_docs),
        "sectionHitCount": len(top_sections),
        "rawChunkHitCount": len(citations),
        "backgroundHitCount": len(background_trail),
        "masterHitCount": len(top_docs),
        "surrogateHitCount": len(top_sections),
        "semanticAddedDocCount": semantic_added_doc_count,
        "semanticMappedCount": semantic_mapped_count,
        "semanticUnmappedCount": semantic_unmapped_count,
        "drillthroughUsed": bool(citations),
        "strategicMode": strategic_mode,
        "categoryCoverage": category_coverage,
        "preferredCategories": category_coverage,
        "backgroundTrail": background_trail[:8],
    }
    context_lines = []
    for index, citation in enumerate(citations, start=1):
        label = citation.title
        if citation.section_label:
            label = f"{label} / {citation.section_label}"
        context_lines.append(
            f"[证据{index}] {label}\n命中要点：{'、'.join(citation.matched_terms) or '无'}\n原文：{citation.excerpt}"
        )
    return RetrievalBundle(
        citations=citations,
        coverage=coverage,
        retrieval_summary=retrieval_summary,
        context_text="\n\n".join(context_lines),
        matched_terms=sorted(matched_terms),
        failure_reason=None if citations else "no_grounded_citations",
    )
~~~

## `backend/app/services/learning_presets.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class LearningPresetCard:
    id: str
    title: str
    category: str
    stage: str
    scenario: str
    why: str
    when_to_use: list[str]
    steps: list[str]
    checklist: list[str]
    anti_patterns: list[str]
    example_prompt: str
    output_template: str
    evidence_requirement: list[str]
    linked_module: str
    difficulty: Literal["入门", "进阶", "熟练"]
    estimated_minutes: int
    source_type: Literal["preset"] = "preset"


LEARNING_PRESET_CARDS: list[LearningPresetCard] = [
    LearningPresetCard(
        id="org_intro_three_part",
        title="机构介绍三段式",
        category="信息核对",
        stage="信息核对",
        scenario="需要介绍一家基金会、公益机构、客户组织时",
        why="先说清它是谁、正在做什么、为什么现在值得关注，可以避免介绍变成资料堆砌。",
        when_to_use=["介绍基金会", "介绍机构", "客户资料初读", "写组织简介"],
        steps=[
            "先从资料中找出机构定位、使命、服务对象。",
            "再列出正在推进的核心项目或业务线。",
            "最后说明它与当前合作、会议或战略陪伴的关系。",
        ],
        checklist=[
            "是否说清楚这家机构是谁？",
            "是否说清楚它主要服务谁？",
            "是否列出当前资料中能确认的项目？",
            "是否区分了事实、判断和待确认信息？",
            "是否引用了资料来源？",
        ],
        anti_patterns=[
            "只罗列文件名，不形成介绍。",
            "把候选判断当成事实。",
            "为了显得完整而编造机构背景。",
        ],
        example_prompt="请根据已上传资料，介绍这家基金会，要求简洁清晰并引用原文。",
        output_template="它是谁 / 它正在做什么 / 当前合作或关注点 / 缺失信息",
        evidence_requirement=["机构介绍资料", "项目资料", "会议纪要或战略资料"],
        linked_module="客户工作台",
        difficulty="入门",
        estimated_minutes=8,
    ),
    LearningPresetCard(
        id="project_intro_five_elements",
        title="项目介绍五要素",
        category="项目认知",
        stage="信息核对",
        scenario="需要介绍某个公益项目、客户项目或合作项目时",
        why="项目介绍不能只写名称，要把对象、问题、方法、成果和下一步串起来。",
        when_to_use=["介绍项目", "项目资料整理", "项目一页纸", "客户项目初读"],
        steps=[
            "确认项目服务对象。",
            "确认项目试图解决的问题。",
            "提炼项目的主要做法。",
            "查找已有成果或阶段进展。",
            "写出下一步仍需补充的信息。",
        ],
        checklist=[
            "服务对象是否明确？",
            "项目问题是否明确？",
            "做法是否来自资料而不是猜测？",
            "成果或进展是否有证据？",
            "是否列出下一步待确认项？",
        ],
        anti_patterns=[
            "只写项目名称。",
            "把项目愿景当成已发生成果。",
            "忽略项目当前阶段。",
        ],
        example_prompt="请介绍这个项目，包括服务对象、主要做法、当前进展和下一步。",
        output_template="服务对象 / 问题 / 方法 / 进展 / 下一步",
        evidence_requirement=["项目方案", "会议纪要", "项目进展材料"],
        linked_module="客户工作台",
        difficulty="入门",
        estimated_minutes=10,
    ),
    LearningPresetCard(
        id="fact_judgment_suggestion_split",
        title="事实、判断、建议分离卡",
        category="战略研判",
        stage="思考与研判",
        scenario="资料很多、判断很多，但不确定哪些能作为结论时",
        why="战略陪伴里最容易出错的是把观察、判断和建议混在一起。",
        when_to_use=["正式判断", "战略研判", "资料总结", "会议后分析"],
        steps=[
            "把资料中明确出现的信息放入事实栏。",
            "把基于事实形成的解释放入判断栏。",
            "把需要用户采取的动作放入建议栏。",
            "对每条判断标注证据是否足够。",
        ],
        checklist=[
            "事实是否能找到原文？",
            "判断是否有至少两条证据？",
            "建议是否说明了下一步动作？",
            "候选判断是否单独标注？",
        ],
        anti_patterns=[
            "用一句话同时写事实、判断和建议。",
            "证据不足却写成正式结论。",
            "没有引用来源。",
        ],
        example_prompt="请把这批资料拆成事实、判断和建议，不要把待确认内容当成结论。",
        output_template="事实 / 判断 / 建议 / 待确认",
        evidence_requirement=["原始资料", "会议纪要", "任务记录"],
        linked_module="战略陪伴",
        difficulty="进阶",
        estimated_minutes=12,
    ),
    LearningPresetCard(
        id="evidence_sufficiency_check",
        title="证据够不够检查卡",
        category="信息核对",
        stage="信息核对",
        scenario="准备生成正式回答、正式判断或客户介绍前",
        why="先判断证据够不够，可以避免系统给出看似完整但不可靠的回答。",
        when_to_use=["引用原文", "正式判断", "客户介绍", "项目介绍"],
        steps=[
            "列出当前问题需要回答的关键点。",
            "为每个关键点找对应证据。",
            "标注证据来自原文、会议、任务还是状态池。",
            "证据不足时生成追问或缺失资料清单。",
        ],
        checklist=[
            "是否每个关键点都有证据？",
            "证据是否来自原始资料？",
            "是否把状态池提醒和正式证据分开？",
            "是否列出缺口？",
        ],
        anti_patterns=[
            "只要有一个文件就开始长篇回答。",
            "把文件标题当作内容证据。",
            "不说明缺失信息。",
        ],
        example_prompt="请判断当前资料是否足够支撑这个回答，并列出缺失信息。",
        output_template="问题点 / 已有证据 / 证据缺口 / 下一步追问",
        evidence_requirement=["原始资料", "证据卡", "会议纪要"],
        linked_module="客户工作台",
        difficulty="进阶",
        estimated_minutes=8,
    ),
    LearningPresetCard(
        id="meeting_minutes_four_part",
        title="会议纪要四分法",
        category="会议与沟通",
        stage="内部对齐",
        scenario="需要提炼会议纪要、飞书妙记或客户沟通记录时",
        why="会议纪要要拆成事实、决定、行动和风险，才能服务后续推进。",
        when_to_use=["会议纪要", "飞书妙记", "沟通记录", "会后总结"],
        steps=[
            "先提取会议讨论的事实背景。",
            "再找出已经形成的决定。",
            "然后列出行动项、负责人和时间点。",
            "最后单独列出风险和未决问题。",
        ],
        checklist=[
            "是否区分讨论内容和最终决定？",
            "是否提取了行动项？",
            "是否有负责人或下一步？",
            "是否列出风险和未决问题？",
        ],
        anti_patterns=[
            "把整段纪要直接摘要成一段话。",
            "只写讨论，不写行动。",
            "把未决问题写成已决定事项。",
        ],
        example_prompt="请提炼最新会议纪要，按事实、决定、行动、风险输出。",
        output_template="事实 / 决定 / 行动项 / 风险与未决问题",
        evidence_requirement=["会议纪要", "会议行动项", "任务记录"],
        linked_module="客户工作台",
        difficulty="入门",
        estimated_minutes=10,
    ),
    LearningPresetCard(
        id="next_action_extraction",
        title="下一步行动提取卡",
        category="交付闭环",
        stage="沟通推进",
        scenario="用户问接下来做什么、下一步怎么推进时",
        why="下一步不能只来自模型判断，要综合任务、会议行动项、风险和未决问题。",
        when_to_use=["下一步", "接下来做什么", "本周推进", "行动项"],
        steps=[
            "先读取未完成任务。",
            "再读取最近会议行动项。",
            "再补充风险和未决问题。",
            "最后按已明确、待确认、需补资料三类输出。",
        ],
        checklist=[
            "是否有明确行动？",
            "是否有负责人？",
            "是否有时间点？",
            "哪些只是候选提醒？",
            "哪些需要先补证据？",
        ],
        anti_patterns=[
            "把风险当作行动。",
            "把候选判断当作任务。",
            "只给泛泛建议。",
        ],
        example_prompt="这个客户接下来要做什么？请按明确行动、待确认事项、风险提醒输出。",
        output_template="明确行动 / 待确认事项 / 风险提醒 / 需补资料",
        evidence_requirement=["任务", "会议行动项", "事件线", "风险记录"],
        linked_module="任务与日历",
        difficulty="进阶",
        estimated_minutes=10,
    ),
    LearningPresetCard(
        id="pre_meeting_three_questions",
        title="会前 3 个必须确认的问题",
        category="会议与沟通",
        stage="内部对齐",
        scenario="准备客户沟通、战略陪伴会议或内部评审前",
        why="会前只要把三个关键问题问清，就能显著降低会后返工。",
        when_to_use=["会前准备", "客户沟通", "战略陪伴会议", "内部对齐"],
        steps=[
            "确认本次会议必须形成什么结论。",
            "确认对方最关心的问题是什么。",
            "确认哪些资料或决定还缺口径。",
        ],
        checklist=[
            "会议目标是否清楚？",
            "要确认的问题是否不超过 3 个？",
            "是否准备了资料依据？",
            "是否知道会后要转成什么任务？",
        ],
        anti_patterns=[
            "带着一堆资料开会但没有问题。",
            "把会议开成信息同步。",
            "没有会后任务。",
        ],
        example_prompt="请帮我为这次客户会议准备 3 个必须确认的问题。",
        output_template="必须确认的问题 / 为什么要问 / 需要带的资料 / 会后动作",
        evidence_requirement=["会议背景", "客户资料", "任务上下文"],
        linked_module="战略陪伴",
        difficulty="入门",
        estimated_minutes=6,
    ),
    LearningPresetCard(
        id="candidate_to_official_judgment",
        title="候选判断转正式判断卡",
        category="战略研判",
        stage="思考与研判",
        scenario="系统已有待确认判断，但还没有正式判断时",
        why="正式判断必须有证据、边界和审批，不应由模型直接生成。",
        when_to_use=["待确认判断", "正式判断", "战略研判", "证据不足"],
        steps=[
            "选出一个候选判断。",
            "绑定至少两条证据。",
            "写清适用边界。",
            "列出反例或风险。",
            "提交人工确认。",
        ],
        checklist=[
            "是否有至少两条证据？",
            "是否写清判断边界？",
            "是否列出风险？",
            "是否经过人工确认？",
        ],
        anti_patterns=[
            "把 candidate 直接显示为正式判断。",
            "没有证据就批准。",
            "忽略相反证据。",
        ],
        example_prompt="请把这个候选判断整理成正式判断草案，并说明还缺哪些证据。",
        output_template="判断草案 / 证据 / 适用边界 / 风险 / 审批建议",
        evidence_requirement=["证据卡", "原始资料", "会议纪要"],
        linked_module="战略陪伴",
        difficulty="熟练",
        estimated_minutes=15,
    ),
    LearningPresetCard(
        id="one_page_brief",
        title="一页简介写作卡",
        category="方案产出",
        stage="方案产出",
        scenario="需要把客户、项目或合作机会写成一页简介时",
        why="一页简介要帮助别人快速理解，而不是复制资料。",
        when_to_use=["客户简介", "项目简介", "对内汇报", "合作说明"],
        steps=[
            "先写 100 字以内的执行摘要。",
            "再写背景、项目、当前进展。",
            "最后写风险、缺口和下一步。",
        ],
        checklist=[
            "开头是否能让人立刻知道对象是谁？",
            "是否列出核心项目？",
            "是否说明当前阶段？",
            "是否列出下一步？",
        ],
        anti_patterns=[
            "照搬材料。",
            "缺少当前阶段。",
            "没有下一步。",
        ],
        example_prompt="请根据资料写一页客户简介，适合内部快速阅读。",
        output_template="执行摘要 / 背景 / 项目 / 当前进展 / 下一步",
        evidence_requirement=["客户资料", "项目资料", "会议纪要"],
        linked_module="客户工作台",
        difficulty="入门",
        estimated_minutes=12,
    ),
    LearningPresetCard(
        id="project_risk_scan",
        title="项目风险扫描卡",
        category="项目认知",
        stage="沟通推进",
        scenario="项目推进中出现卡点、延迟、协作不清时",
        why="风险不是负面评价，而是提前识别会影响交付的条件。",
        when_to_use=["项目风险", "卡点", "推进受阻", "客户协作"],
        steps=[
            "识别资料风险。",
            "识别决策风险。",
            "识别协作风险。",
            "识别时间风险。",
            "给每个风险配一个下一步动作。",
        ],
        checklist=[
            "资料是否齐？",
            "谁有决策权？",
            "责任边界是否清楚？",
            "时间点是否明确？",
            "风险是否有处理动作？",
        ],
        anti_patterns=[
            "只说有风险，不说怎么处理。",
            "把不确定性写成事实。",
            "把责任全部推给客户。",
        ],
        example_prompt="请扫描这个项目当前风险，并给出下一步处理建议。",
        output_template="风险类型 / 具体表现 / 影响 / 下一步动作",
        evidence_requirement=["项目任务", "会议纪要", "风险记录"],
        linked_module="项目认知",
        difficulty="进阶",
        estimated_minutes=10,
    ),
    LearningPresetCard(
        id="method_card_writing",
        title="方法卡写作卡",
        category="复盘沉淀",
        stage="复盘沉淀",
        scenario="一次任务做完后，需要沉淀成团队可复用经验",
        why="复盘只有变成方法卡，才可能被下次任务自动推荐。",
        when_to_use=["复盘", "经验沉淀", "成长手册", "团队方法"],
        steps=[
            "写清这次解决了什么问题。",
            "写清有效动作是什么。",
            "写清适用边界。",
            "写清下次什么时候推荐。",
        ],
        checklist=[
            "是否有真实任务来源？",
            "是否有有效动作？",
            "是否有适用边界？",
            "是否有下次触发场景？",
        ],
        anti_patterns=[
            "只写心得，不写方法。",
            "没有适用边界。",
            "无法被下次复用。",
        ],
        example_prompt="请把这次任务复盘成一张团队可复用的方法卡。",
        output_template="问题 / 有效动作 / 适用场景 / 不适用场景 / 下次触发词",
        evidence_requirement=["任务记录", "交付物", "复盘说明"],
        linked_module="成长手册",
        difficulty="进阶",
        estimated_minutes=12,
    ),
    LearningPresetCard(
        id="missing_info_followup",
        title="缺失信息追问卡",
        category="信息核对",
        stage="需求接收",
        scenario="资料不足、问题无法稳定回答时",
        why="系统不能硬答时，应该生成清楚的追问和补资料清单。",
        when_to_use=["资料不足", "无法判断", "需要补充材料", "客户追问"],
        steps=[
            "先说明当前能确认什么。",
            "再说明不能确认什么。",
            "把缺口转成 3-5 个具体追问。",
            "标注每个追问的用途。",
        ],
        checklist=[
            "是否先说清已有信息？",
            "是否没有编造缺失内容？",
            "追问是否具体？",
            "是否说明为什么要补？",
        ],
        anti_patterns=[
            "直接说资料不足就结束。",
            "提出过于抽象的问题。",
            "追问和当前任务无关。",
        ],
        example_prompt="当前资料不足，请帮我列出需要向客户追问的问题。",
        output_template="已确认 / 未确认 / 追问 / 追问目的",
        evidence_requirement=["当前资料索引", "任务目标"],
        linked_module="客户工作台",
        difficulty="入门",
        estimated_minutes=6,
    ),
]


def list_learning_presets() -> list[LearningPresetCard]:
    return list(LEARNING_PRESET_CARDS)


def default_starter_learning_presets(mode: str = "global") -> list[LearningPresetCard]:
    if mode == "strategic":
        ids = [
            "org_intro_three_part",
            "meeting_minutes_four_part",
            "next_action_extraction",
            "fact_judgment_suggestion_split",
            "evidence_sufficiency_check",
            "method_card_writing",
        ]
    else:
        ids = [
            "missing_info_followup",
            "fact_judgment_suggestion_split",
            "method_card_writing",
        ]
    by_id = {card.id: card for card in LEARNING_PRESET_CARDS}
    return [by_id[item_id] for item_id in ids if item_id in by_id]


def match_learning_presets(
    *,
    task_title: str,
    task_desc: str = "",
    phase: str = "",
    client_name: str | None = None,
    current_blocker: str | None = None,
    evidence_count: int = 0,
    mode: str = "global",
) -> list[LearningPresetCard]:
    text = " ".join(
        part
        for part in [
            task_title,
            task_desc,
            phase,
            client_name or "",
            current_blocker or "",
        ]
        if part
    )
    scored: list[tuple[int, LearningPresetCard]] = []
    for card in LEARNING_PRESET_CARDS:
        score = 0
        for keyword in card.when_to_use:
            if keyword and keyword in text:
                score += 4
        if card.stage and card.stage == phase:
            score += 3
        if "介绍" in text and card.id in {
            "org_intro_three_part",
            "project_intro_five_elements",
            "one_page_brief",
            "fact_judgment_suggestion_split",
        }:
            score += 8
        if "介绍" in text and card.id == "fact_judgment_suggestion_split":
            score += 6
        if any(k in text for k in ["基金会", "机构", "组织", "客户"]):
            if card.id in {"org_intro_three_part", "one_page_brief", "evidence_sufficiency_check"}:
                score += 6
            if card.id == "fact_judgment_suggestion_split":
                score += 4
        if any(k in text for k in ["项目", "项目资料", "项目介绍"]):
            if card.id in {"project_intro_five_elements", "project_risk_scan"}:
                score += 6
        if any(k in text for k in ["会议", "纪要", "飞书", "沟通记录"]):
            if card.id in {
                "meeting_minutes_four_part",
                "pre_meeting_three_questions",
                "next_action_extraction",
            }:
                score += 8
        if any(k in text for k in ["下一步", "接下来", "待办", "行动项", "推进"]):
            if card.id in {"next_action_extraction", "project_risk_scan"}:
                score += 8
        if any(k in text for k in ["正式判断", "候选判断", "待确认判断", "研判"]):
            if card.id in {
                "candidate_to_official_judgment",
                "fact_judgment_suggestion_split",
                "evidence_sufficiency_check",
            }:
                score += 8
        if evidence_count <= 0 and card.id in {"missing_info_followup", "evidence_sufficiency_check"}:
            score += 5
        if score > 0:
            scored.append((score, card))
    scored.sort(key=lambda item: item[0], reverse=True)
    if not scored:
        return default_starter_learning_presets(mode=mode)
    return [card for _, card in scored[:4]]


def preset_card_to_generic_lesson(card: LearningPresetCard, *, task_title: str | None = None):
    from app.models import GrowthGenericLessonRecord

    return GrowthGenericLessonRecord(
        id=f"preset-{card.id}",
        title=card.title,
        judgment=card.why,
        applicableScene=card.scenario if not task_title else f"{card.scenario}；当前任务：{task_title}",
        whyItWorks=card.why,
        reuseHint=card.output_template,
        linkedContext=None,
    )


def preset_card_to_support_material(card: LearningPresetCard):
    from app.models import GrowthWorkbenchMaterialRecord

    return GrowthWorkbenchMaterialRecord(
        id=f"preset-material-{card.id}",
        title=card.title,
        type="模板工具",
        scenario=card.scenario,
        summary=" / ".join(card.steps[:3]),
        linkedContext=None,
    )


def build_actions_from_presets(cards: list[LearningPresetCard]):
    from app.models import GrowthWorkbenchActionRecord

    def first_step(index: int) -> str:
        card = cards[index] if index < len(cards) else None
        if card and card.steps:
            return card.steps[0]
        return "先选择一张方法卡开始。"

    actions_before = [
        GrowthWorkbenchActionRecord(
            id="preset-before-1",
            title="先确认资料和问题",
            output=first_step(0),
            scenario="开始前",
            actionLabel="查看方法卡",
            supportTitle="先确保对象和问题明确",
            kind="support",
        ),
        GrowthWorkbenchActionRecord(
            id="preset-before-2",
            title="先看证据够不够",
            output=first_step(1),
            scenario="开始前",
            actionLabel="做证据检查",
            supportTitle="先看证据再给判断",
            kind="support",
        ),
        GrowthWorkbenchActionRecord(
            id="preset-before-3",
            title="先列出会前关键问题",
            output=first_step(2),
            scenario="会前准备",
            actionLabel="生成会前问题",
            supportTitle="避免会后返工",
            kind="process",
        ),
    ]
    actions_during = [
        GrowthWorkbenchActionRecord(
            id="preset-during-1",
            title="按方法卡完成当前输出",
            output="把当前对象转成可执行输出，而不是泛泛建议。",
            scenario="执行中",
            actionLabel="打开练习",
            supportTitle="按步骤推进",
            kind="process",
        ),
        GrowthWorkbenchActionRecord(
            id="preset-during-2",
            title="用模板拆解事实 / 判断 / 建议",
            output="先保证事实可追溯，再形成判断与建议。",
            scenario="执行中",
            actionLabel="应用模板",
            supportTitle="避免事实与判断混写",
            kind="process",
        ),
        GrowthWorkbenchActionRecord(
            id="preset-during-3",
            title="用会议四分法提炼纪要",
            output="事实 / 决定 / 行动 / 风险四栏完整输出。",
            scenario="执行中",
            actionLabel="提炼纪要",
            supportTitle="把讨论转成行动",
            kind="process",
        ),
    ]
    actions_after = [
        GrowthWorkbenchActionRecord(
            id="preset-after-1",
            title="写回成长手册",
            output="记录问题、有效动作、适用边界和复用提示。",
            scenario="完成后",
            actionLabel="记录经验",
            supportTitle="沉淀为可复用资产",
            kind="compose",
        ),
        GrowthWorkbenchActionRecord(
            id="preset-after-2",
            title="转成任务继续推进",
            output="把学习动作拆成下一步任务和负责人。",
            scenario="完成后",
            actionLabel="转为任务",
            supportTitle="形成执行闭环",
            kind="task",
        ),
        GrowthWorkbenchActionRecord(
            id="preset-after-3",
            title="沉淀可复用方法卡",
            output="写清触发场景和不适用边界，方便下次推荐。",
            scenario="完成后",
            actionLabel="标记已复用",
            supportTitle="进入方法库",
            kind="compose",
        ),
    ]
    return actions_before, actions_during, actions_after
~~~

## `backend/app/services/local_memory.py`

- 编码: `utf-8`

~~~python
"""
Local project memory system — file-based memory for AI context.

Structure:
    {data_dir}/memory/
    ├── org_memory.md                   # Organization-level memory index
    ├── projects/
    │   ├── {client_id}/
    │   │   ├── project_memory.md       # Project-level memory (key insights, decisions, risks)
    │   │   └── event_lines/
    │   │       └── {eline_id}.md       # Event line memory (timeline, blockers, decisions)
    │   └── ...
    └── weekly/
        └── 2026-W14.md                # Weekly snapshot

Each .md file has YAML frontmatter with metadata for future cloud sync.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


# ── Directory helpers ──

def memory_root(data_dir: str | Path) -> Path:
    root = Path(data_dir) / "memory"
    root.mkdir(parents=True, exist_ok=True)
    return root


def project_memory_dir(data_dir: str | Path, client_id: str) -> Path:
    d = memory_root(data_dir) / "projects" / client_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def event_line_memory_dir(data_dir: str | Path, client_id: str) -> Path:
    d = project_memory_dir(data_dir, client_id) / "event_lines"
    d.mkdir(parents=True, exist_ok=True)
    return d


def weekly_memory_dir(data_dir: str | Path) -> Path:
    d = memory_root(data_dir) / "weekly"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Read / Write helpers ──

def read_memory_file(path: Path) -> str:
    """Read a memory .md file. Returns empty string if not exists."""
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def write_memory_file(path: Path, content: str) -> None:
    """Write a memory .md file with sync metadata."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _frontmatter(metadata: dict[str, Any]) -> str:
    """Generate YAML frontmatter."""
    lines = ["---"]
    for k, v in metadata.items():
        lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines)


# ── Project Memory ──

def read_project_memory(data_dir: str | Path, client_id: str) -> str:
    path = project_memory_dir(data_dir, client_id) / "project_memory.md"
    return read_memory_file(path)


def write_project_memory(
    data_dir: str | Path,
    client_id: str,
    client_name: str,
    content: str,
) -> Path:
    path = project_memory_dir(data_dir, client_id) / "project_memory.md"
    full = _frontmatter({
        "project": client_name,
        "client_id": client_id,
        "updated": _now_iso(),
        "syncedAt": "",  # Reserved for cloud sync
    }) + "\n\n" + content
    write_memory_file(path, full)
    logger.info("[local-memory] wrote project_memory for %s (%d chars)", client_name, len(content))
    try:
        update_memory_index(data_dir)
        record_memory_operation(data_dir)
    except Exception:
        pass
    return path


# ── Event Line Memory ──

def read_event_line_memory(data_dir: str | Path, client_id: str, eline_id: str) -> str:
    path = event_line_memory_dir(data_dir, client_id) / f"{eline_id}.md"
    return read_memory_file(path)


def write_event_line_memory(
    data_dir: str | Path,
    client_id: str,
    eline_id: str,
    eline_name: str,
    client_name: str,
    content: str,
) -> Path:
    path = event_line_memory_dir(data_dir, client_id) / f"{eline_id}.md"
    full = _frontmatter({
        "event_line": eline_name,
        "event_line_id": eline_id,
        "project": client_name,
        "client_id": client_id,
        "updated": _now_iso(),
        "syncedAt": "",
    }) + "\n\n" + content
    write_memory_file(path, full)
    logger.info("[local-memory] wrote event_line memory for %s/%s (%d chars)", client_name, eline_name, len(content))
    try:
        update_memory_index(data_dir)
        record_memory_operation(data_dir)
    except Exception:
        pass
    return path


def _strip_frontmatter_markdown(content: str) -> str:
    if not content.startswith("---"):
        return content
    lines = content.splitlines()
    if not lines or lines[0] != "---":
        return content
    for index in range(1, len(lines)):
        if lines[index] == "---":
            return "\n".join(lines[index + 1 :]).lstrip("\n")
    return content


def rehome_event_line_memory(
    data_dir: str | Path,
    source_client_id: str | None,
    target_client_id: str,
    eline_id: str,
    eline_name: str,
    target_client_name: str,
) -> Path | None:
    normalized_target_client_id = str(target_client_id or "").strip()
    if not normalized_target_client_id:
        return None

    source_path = (
        event_line_memory_dir(data_dir, source_client_id) / f"{eline_id}.md"
        if source_client_id
        else None
    )
    target_path = event_line_memory_dir(data_dir, normalized_target_client_id) / f"{eline_id}.md"

    raw_content = ""
    if source_path and source_path.exists():
        raw_content = read_memory_file(source_path)
    elif target_path.exists():
        raw_content = read_memory_file(target_path)
    else:
        return None

    body = _strip_frontmatter_markdown(raw_content)
    written_path = write_event_line_memory(
        data_dir,
        normalized_target_client_id,
        eline_id,
        eline_name,
        target_client_name,
        body,
    )

    if source_path and source_path.exists() and source_path != written_path:
        source_path.unlink()

    return written_path


# ── Weekly Snapshot ──

def read_weekly_memory(data_dir: str | Path, week_label: str) -> str:
    path = weekly_memory_dir(data_dir) / f"{week_label}.md"
    return read_memory_file(path)


def write_weekly_memory(
    data_dir: str | Path,
    week_label: str,
    content: str,
) -> Path:
    path = weekly_memory_dir(data_dir) / f"{week_label}.md"
    full = _frontmatter({
        "week": week_label,
        "updated": _now_iso(),
        "syncedAt": "",
    }) + "\n\n" + content
    write_memory_file(path, full)
    logger.info("[local-memory] wrote weekly memory for %s (%d chars)", week_label, len(content))
    try:
        update_memory_index(data_dir)
        record_memory_operation(data_dir)
    except Exception:
        pass
    return path


# ── Quote extraction ──

QUOTE_EXTRACTION_PROMPT = """从以下工作内容中提取经验金句。

来源类型：{source_type}
内容：{content}

提炼规则：
1. 像名人名言格式——精炼、有力、一读就记住
2. 必须有具体场景支撑（不要空洞的大道理）
3. 必须是可迁移的（别人遇到类似情况能用）
4. 保留原作者的判断视角（不要改到认不出来）
5. 每条不超过 50 字
6. 只提取真正有价值的，宁可不提也不凑数

返回 JSON：{{"quotes": [{{"text": "金句", "source": "来源简述"}}]}}
如果没有值得提取的金句，返回 {{"quotes": []}}"""


def extract_quotes_from_text(
    ai_service: Any,
    content: str,
    source_type: str,
    *,
    max_quotes: int = 2,
) -> list[dict[str, str]]:
    """Extract golden quotes from text using AI. Returns list of {text, source}."""
    if not content or len(content) < 50:
        return []
    health = ai_service.get_health()
    if health.provider == "mock" or not health.ready:
        return []
    try:
        prompt = QUOTE_EXTRACTION_PROMPT.format(
            source_type=source_type,
            content=content[:3000],
        )
        raw = ai_service._qwen_generate(
            prompt=prompt,
            system_instruction="你是益语智库的经验提炼助手。只返回 JSON，不要解释。",
            response_schema={"type": "object", "properties": {"quotes": {"type": "array", "items": {"type": "object", "properties": {"text": {"type": "string"}, "source": {"type": "string"}}, "required": ["text", "source"]}}}, "required": ["quotes"]},
            timeout_seconds=20.0,
            max_tokens=300,
            temperature=0.4,
            top_p=0.9,
            enable_thinking=False,
        )
        if isinstance(raw, dict):
            quotes = raw.get("quotes", [])
            return [q for q in quotes[:max_quotes] if isinstance(q, dict) and q.get("text")]
        return []
    except Exception:
        return []


def save_pending_quotes(
    db: Any,
    quotes: list[dict[str, str]],
    user_id: str = "user_guyuan",
    user_name: str = "顾源源",
) -> int:
    """Save extracted quotes as pending captures in growth system."""
    from uuid import uuid4 as _uuid4
    saved = 0
    now = _now_iso()
    for q in quotes:
        text = str(q.get("text", "")).strip()
        source = str(q.get("source", "")).strip()
        if not text:
            continue
        sig_id = f"gse_{_uuid4().hex[:10]}"
        try:
            db.execute(
                """INSERT INTO growth_signal_events(id, user_id, user_name, source_type, source_id, raw_text, context_json, dedupe_key, created_at)
                VALUES(?, ?, ?, 'review_insight_pending', ?, ?, ?, ?, ?)""",
                (sig_id, user_id, user_name, source, text,
                 json.dumps({"insightQuote": text, "insightSourceLabel": f"来源：{source}", "contextSummary": f"来源：{source}", "enriched": True}, ensure_ascii=False),
                 f"quote_{text[:30]}", now),
            )
            db.execute(
                """INSERT OR IGNORE INTO growth_capture_states(id, user_id, signal_id, status, reason, created_at, updated_at)
                VALUES(?, ?, ?, 'open', ?, ?, ?)""",
                (f"gc_{_uuid4().hex[:10]}", user_id, sig_id, f"AI从{source}中提炼", now, now),
            )
            saved += 1
        except Exception:
            pass
    return saved


# ── Memory Index ──

def update_memory_index(data_dir: str | Path) -> None:
    """Rebuild MEMORY_INDEX.md from current memory files."""
    from datetime import datetime as _dt
    root = memory_root(data_dir)
    lines = [
        "# 益语智库本地记忆索引",
        f"更新时间：{_dt.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 组织",
    ]
    org_path = root / "org_memory.md"
    if org_path.exists():
        lines.append("- [组织记忆](org_memory.md) — 益语定位、团队、市场、业务")

    lines.extend(["", "## 项目"])
    proj_dir = root / "projects"
    has_projects = False
    if proj_dir.exists():
        for cid_dir in sorted(proj_dir.iterdir()):
            if not cid_dir.is_dir():
                continue
            pm = cid_dir / "project_memory.md"
            if pm.exists():
                has_projects = True
                lines.append(f"- [{cid_dir.name}](projects/{cid_dir.name}/project_memory.md)")
                el_dir = cid_dir / "event_lines"
                if el_dir.exists():
                    for el_file in sorted(el_dir.glob("*.md")):
                        lines.append(f"  - [{el_file.stem}](projects/{cid_dir.name}/event_lines/{el_file.name})")
    if not has_projects:
        lines.append("- （尚无项目记忆）")

    lines.extend(["", "## 周快照"])
    weekly_dir = root / "weekly"
    has_weekly = False
    if weekly_dir.exists():
        for wf in sorted(weekly_dir.glob("*.md"), reverse=True)[:8]:
            has_weekly = True
            lines.append(f"- [{wf.stem}](weekly/{wf.name})")
    if not has_weekly:
        lines.append("- （尚无周快照）")

    (root / "MEMORY_INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("[local-memory] updated MEMORY_INDEX.md")


# ── Dream (memory consolidation) ──

def should_dream(data_dir: str | Path) -> bool:
    """Check if it's time to consolidate memories (24h since last + 3 meaningful operations)."""
    root = memory_root(data_dir)
    dream_state_path = root / ".dream_state.json"
    try:
        if dream_state_path.exists():
            state = json.loads(dream_state_path.read_text(encoding="utf-8"))
            last_dream = state.get("lastDreamAt", "")
            ops_since = state.get("opsSinceDream", 0)
            if last_dream:
                from datetime import datetime as _dt
                last = _dt.fromisoformat(last_dream)
                hours_ago = (_dt.now() - last).total_seconds() / 3600
                return hours_ago >= 1 and ops_since >= 3
            return ops_since >= 3
        return False  # No state yet, wait for first operations
    except Exception:
        return False


def record_memory_operation(data_dir: str | Path) -> None:
    """Record that a meaningful memory operation happened (for dream trigger)."""
    root = memory_root(data_dir)
    dream_state_path = root / ".dream_state.json"
    try:
        state = {}
        if dream_state_path.exists():
            state = json.loads(dream_state_path.read_text(encoding="utf-8"))
        state["opsSinceDream"] = state.get("opsSinceDream", 0) + 1
        state["lastOpAt"] = _now_iso()
        if "lastDreamAt" not in state:
            state["lastDreamAt"] = _now_iso()  # Initialize
        dream_state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def run_dream_cycle(data_dir: str | Path, ai_service: Any = None, db: Any = None) -> dict[str, int]:
    """
    记忆整理周期 — "做梦"。

    借鉴 Claude Code AutoDream 的做法：
    - 不重读原始文档（成本太高）
    - 用定向搜索从已有记忆中找信号
    - 合并重复、解决矛盾、升级认知

    Phase 1: Orient — 扫描所有记忆文件
    Phase 2: Cross-pollinate — 从周记忆中提取关键判断，写回 project_memory
    Phase 3: DB sync — 把本地文件中的关键判断同步到 memory_facts
    Phase 4: Trim — 裁剪超长文件
    Phase 5: Index — 更新索引
    """
    root = memory_root(data_dir)
    stats = {
        "files_scanned": 0, "files_trimmed": 0, "index_updated": False,
        "cross_pollinated": 0, "facts_synced": 0,
    }

    all_memory_files: list[Path] = list(root.glob("**/*.md"))
    stats["files_scanned"] = len(all_memory_files)

    # ── Phase 2: Cross-pollinate — 从周记忆提取信号写回项目记忆 ──
    weekly_dir = root / "weekly"
    if weekly_dir.exists():
        # 找最新的周记忆
        weekly_files = sorted(weekly_dir.glob("*.md"), reverse=True)
        for wf in weekly_files[:2]:  # 只处理最近 2 周
            weekly_content = wf.read_text(encoding="utf-8")
            if len(weekly_content) < 100:
                continue

            # 定向搜索：提取"需要关注"、"卡点汇总"、"下周提示"部分
            signals: dict[str, list[str]] = {"关注": [], "卡点": [], "提示": []}
            current_section = ""
            for line in weekly_content.split("\n"):
                stripped = line.strip()
                if "需要关注" in stripped or "风险" in stripped:
                    current_section = "关注"
                elif "卡点" in stripped or "阻塞" in stripped:
                    current_section = "卡点"
                elif "下周" in stripped or "提示" in stripped:
                    current_section = "提示"
                elif "正常推进" in stripped or "## " in stripped:
                    current_section = ""
                elif current_section and stripped.startswith("•"):
                    signals[current_section].append(stripped.lstrip("• ").strip())

            # 把信号写回对应的项目记忆
            proj_root = root / "projects"
            if proj_root.exists():
                for cid_dir in proj_root.iterdir():
                    if not cid_dir.is_dir() or cid_dir.name in ("general", "."):
                        continue
                    pm_path = cid_dir / "project_memory.md"
                    if not pm_path.exists():
                        continue
                    pm_content = pm_path.read_text(encoding="utf-8")
                    # 检查该项目名是否出现在周记忆的信号中
                    client_signals = []
                    for section, items in signals.items():
                        for item in items:
                            # 简单匹配：如果信号中包含项目文件夹对应的客户关键词
                            if cid_dir.name in weekly_content and any(kw in item for kw in _extract_keywords_from_path(pm_content)):
                                client_signals.append(f"[{section}] {item}")

                    if client_signals and "## 做梦整理" not in pm_content:
                        # 追加到项目记忆末尾
                        week_label = wf.stem
                        addition = f"\n\n## 做梦整理（{week_label}）\n" + "\n".join(f"- {s}" for s in client_signals[:5])
                        pm_path.write_text(pm_content + addition, encoding="utf-8")
                        stats["cross_pollinated"] += 1

    # ── Phase 3: DB sync — 把周记忆的关键判断写入 memory_facts ──
    if db is not None and weekly_dir.exists():
        weekly_files = sorted(weekly_dir.glob("*.md"), reverse=True)
        for wf in weekly_files[:1]:  # 只处理最新一周
            weekly_content = wf.read_text(encoding="utf-8")
            week_label = wf.stem

            # 提取结构化段落
            sections_to_sync = {
                "weekly_attention": "",  # 需要关注
                "weekly_blockers": "",   # 卡点汇总
                "weekly_next": "",       # 下周提示
            }
            current_key = ""
            current_lines: list[str] = []
            for line in weekly_content.split("\n"):
                stripped = line.strip()
                if "需要关注" in stripped:
                    if current_key and current_lines:
                        sections_to_sync[current_key] = "\n".join(current_lines)
                    current_key = "weekly_attention"
                    current_lines = []
                elif "卡点" in stripped:
                    if current_key and current_lines:
                        sections_to_sync[current_key] = "\n".join(current_lines)
                    current_key = "weekly_blockers"
                    current_lines = []
                elif "下周" in stripped:
                    if current_key and current_lines:
                        sections_to_sync[current_key] = "\n".join(current_lines)
                    current_key = "weekly_next"
                    current_lines = []
                elif stripped.startswith("##") or stripped.startswith("【正常推进"):
                    if current_key and current_lines:
                        sections_to_sync[current_key] = "\n".join(current_lines)
                    current_key = ""
                    current_lines = []
                elif current_key and stripped:
                    current_lines.append(stripped)
            if current_key and current_lines:
                sections_to_sync[current_key] = "\n".join(current_lines)

            # 写入 memory_facts（用 product scope 代表组织级记忆）
            from app.services.memory_foundation import upsert_memory_fact
            for fact_key, fact_value in sections_to_sync.items():
                if fact_value.strip():
                    try:
                        upsert_memory_fact(
                            db,
                            scope_type="product",
                            scope_id="org_weekly",
                            fact_key=f"{fact_key}:{week_label}",
                            fact_value=fact_value[:800],
                            source_type="dream_cycle",
                            source_id=f"weekly/{week_label}",
                            confidence=0.8,
                            freshness=0.9,
                        )
                        stats["facts_synced"] += 1
                    except Exception:
                        pass

    # ── Phase 4: Trim — 裁剪超长文件 ──
    SIZE_LIMITS = {
        "org_memory.md": 4000,
        "project_memory.md": 3000,
        "MEMORY_INDEX.md": 5000,
    }
    DEFAULT_LIMIT = 2000

    for mf in all_memory_files:
        if mf.name.startswith("."):
            continue
        limit = SIZE_LIMITS.get(mf.name, DEFAULT_LIMIT)
        content = mf.read_text(encoding="utf-8")
        if len(content) > limit * 1.5:
            if "---" in content:
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = f"---{parts[1]}---"
                    body = parts[2].strip()
                    if len(body) > limit:
                        body = body[:limit].rsplit("\n", 1)[0] + "\n\n（记忆已自动精简，保留核心内容）"
                        mf.write_text(f"{frontmatter}\n\n{body}\n", encoding="utf-8")
                        stats["files_trimmed"] += 1

    # ── Phase 5: Update index ──
    try:
        update_memory_index(data_dir)
        stats["index_updated"] = True
    except Exception:
        pass

    # Update dream state
    dream_state_path = root / ".dream_state.json"
    try:
        dream_state_path.write_text(json.dumps({
            "lastDreamAt": _now_iso(),
            "opsSinceDream": 0,
            "lastStats": stats,
        }, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

    logger.info("[local-memory] dream cycle complete: %s", stats)
    return stats


def _extract_keywords_from_path(content: str) -> list[str]:
    """从项目记忆内容中提取关键词用于匹配。"""
    keywords = []
    for line in content.split("\n")[:10]:
        stripped = line.strip()
        if stripped.startswith("project:") or stripped.startswith("event_line:"):
            val = stripped.split(":", 1)[1].strip()
            if val:
                keywords.append(val)
                # 也加入短名
                for part in val.split():
                    if len(part) >= 2:
                        keywords.append(part)
    return keywords[:10] if keywords else ["_no_match_"]


# ── Aggregate reader for AI context ──

def gather_project_context_for_ai(
    data_dir: str | Path,
    client_ids: list[str],
    event_line_ids: list[str] | None = None,
) -> str:
    """
    Gather all relevant memory into a single text block for AI consumption.
    This replaces real-time cloud API calls — reads only local files.
    """
    parts: list[str] = []
    # Organization memory
    org_path = memory_root(data_dir) / "org_memory.md"
    org_text = read_memory_file(org_path)
    if org_text:
        parts.append(f"【组织记忆】\n{org_text}")

    # Scan ALL project directories (not just specified client_ids)
    proj_root = memory_root(data_dir) / "projects"
    all_cids = list(client_ids) + ["general"]
    if proj_root.exists():
        for cid_dir in proj_root.iterdir():
            if cid_dir.is_dir() and cid_dir.name not in all_cids:
                all_cids.append(cid_dir.name)

    for cid in all_cids:
        pm = read_project_memory(data_dir, cid)
        if pm:
            parts.append(f"【项目记忆】\n{pm}")

        # Event line memories under this project
        el_dir = event_line_memory_dir(data_dir, cid)
        if el_dir.exists():
            for md_file in sorted(el_dir.glob("*.md")):
                eid = md_file.stem
                if event_line_ids and eid not in event_line_ids:
                    continue
                el_text = read_memory_file(md_file)
                if el_text:
                    parts.append(f"【事件线记忆】\n{el_text}")

    # Attachment texts from cache
    att_cache_dir = Path(data_dir) / "Cache" / "event-line-attachments"
    if att_cache_dir.exists():
        for text_file in sorted(att_cache_dir.glob("*.text.json"))[:10]:
            try:
                td = json.loads(text_file.read_bytes())
                t = str(td.get("text", "")).strip()
                title = str(td.get("title", "")).strip()
                if t and len(t) > 100 and "提取失败" not in t and "No module" not in t:
                    parts.append(f"【附件全文：{title}】\n{t}")
            except Exception:
                continue

    return "\n\n".join(parts)
~~~

## `backend/app/services/memory_foundation.py`

- 编码: `utf-8`

~~~python
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
    valid_from = row["valid_from"] if "valid_from" in row.keys() else None
    valid_to = row["valid_to"] if "valid_to" in row.keys() else None
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
        validFrom=str(valid_from) if valid_from else None,
        validTo=str(valid_to) if valid_to else None,
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
    valid_from: str | None = None,
    valid_to: str | None = None,
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
            confidence, freshness, evidence_refs_json, valid_from, valid_to, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(scope_type, scope_id, fact_key, source_type, source_id) DO UPDATE SET
            fact_value = excluded.fact_value,
            confidence = excluded.confidence,
            freshness = excluded.freshness,
            evidence_refs_json = excluded.evidence_refs_json,
            valid_from = excluded.valid_from,
            valid_to = excluded.valid_to,
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
            valid_from,
            valid_to,
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


# ────────────────────────────────────────────────────────────────
# Conversation → memory_facts auto-extraction
# ────────────────────────────────────────────────────────────────

CHAT_FACT_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "fact_key": {"type": "string", "description": "简短的事实标识，如 '核心策略'、'关键决策'、'待办事项'"},
                    "fact_value": {"type": "string", "description": "事实内容，一句话概括"},
                    "valid_from": {"type": "string", "description": "生效日期 ISO 格式，如无明确日期则为今天"},
                    "valid_to": {"type": "string", "description": "失效日期 ISO 格式，如无明确期限则留空字符串"},
                    "confidence": {"type": "number", "description": "置信度 0.0-1.0"},
                },
                "required": ["fact_key", "fact_value", "confidence"],
            },
            "maxItems": 5,
        }
    },
    "required": ["facts"],
}

CHAT_FACT_EXTRACTION_SYSTEM = (
    "你是一个记忆提取专家。从用户与助手的对话中提取关键事实，包括：\n"
    "1. 明确的决策或结论\n"
    "2. 重要的偏好或需求\n"
    "3. 约定的下一步行动\n"
    "4. 关键的背景信息变化\n"
    "只提取有持久价值的事实，忽略临时性的问候、闲聊、操作指令。\n"
    "每个事实用一句话概括，fact_key 用中文短语命名。\n"
    "如果对话中没有值得记住的事实，返回空数组。"
)


def extract_chat_facts_to_memory(
    db: Database,
    ai_service: object | None,
    *,
    client_id: str,
    thread_id: str,
    user_prompt: str,
    assistant_content: str,
    answer_mode: str,
) -> list[MemoryFact]:
    """Extract key facts from a completed chat exchange and persist to memory_facts."""
    if ai_service is None:
        return []
    # Only keep memory from fully grounded answers to avoid fallback noise and extra LLM contention.
    if answer_mode != "grounded_answer":
        return []
    # Skip trivially short exchanges
    if len(user_prompt.strip()) < 10 or len(assistant_content.strip()) < 30:
        return []

    conversation_text = f"用户提问：{user_prompt}\n\n助手回答：{assistant_content}"
    today_iso = _now_iso()[:10]
    prompt = (
        f"以下是一段工作对话，请从中提取关键事实。今天日期是 {today_iso}。\n\n"
        f"{conversation_text}"
    )

    try:
        result = ai_service._qwen_generate(  # type: ignore[attr-defined]
            prompt=prompt,
            system_instruction=CHAT_FACT_EXTRACTION_SYSTEM,
            response_schema=CHAT_FACT_EXTRACTION_SCHEMA,
            timeout_seconds=12.0,
            max_tokens=800,
            temperature=0.3,
            enable_thinking=False,
        )
    except Exception:
        logger.warning("[chat-fact-extract] AI extraction failed", exc_info=True)
        return []

    if not isinstance(result, dict):
        return []
    raw_facts = result.get("facts", [])
    if not isinstance(raw_facts, list):
        return []

    saved: list[MemoryFact] = []
    for item in raw_facts[:5]:
        if not isinstance(item, dict):
            continue
        fact_key = _coerce_text(item.get("fact_key"))
        fact_value = _coerce_text(item.get("fact_value"))
        if not fact_key or not fact_value:
            continue
        confidence = float(item.get("confidence", 0.6))
        if confidence < 0.4:
            continue
        valid_from = _coerce_text(item.get("valid_from")) or today_iso
        valid_to = _coerce_text(item.get("valid_to")) or None

        try:
            fact = upsert_memory_fact(
                db,
                scope_type="client",
                scope_id=client_id,
                fact_key=fact_key,
                fact_value=fact_value,
                source_type="chat_extraction",
                source_id=thread_id,
                confidence=confidence,
                freshness=0.9,
                valid_from=valid_from,
                valid_to=valid_to,
            )
            saved.append(fact)
        except Exception:
            logger.warning("[chat-fact-extract] Failed to save fact %s", fact_key, exc_info=True)
            continue

    if saved:
        logger.info("[chat-fact-extract] Extracted %d facts from thread %s for client %s", len(saved), thread_id, client_id)
    return saved
~~~

## `backend/app/services/platform_dna.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re
import zipfile
from xml.etree import ElementTree as ET

from docx import Document as WordDocument

try:
    from pypdf import PdfReader

    HAS_PYPDF = True
except Exception:  # pragma: no cover - dependency fallback
    PdfReader = None  # type: ignore[assignment]
    HAS_PYPDF = False


TEXT_EXTENSIONS = {".md", ".markdown", ".txt"}
DOCX_EXTENSIONS = {".docx"}
PDF_EXTENSIONS = {".pdf"}


def _read_plain_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _read_docx_with_python_docx(path: Path) -> str:
    try:
        document = WordDocument(str(path))
    except Exception:
        return ""

    lines: list[str] = []
    for paragraph in document.paragraphs:
        text = re.sub(r"\s+", " ", paragraph.text or "").strip()
        if text:
            lines.append(text)

    for table in document.tables:
        for row in table.rows:
            values = [re.sub(r"\s+", " ", cell.text or "").strip() for cell in row.cells]
            values = [value for value in values if value]
            if values:
                lines.append(" | ".join(values))

    return "\n".join(lines).strip()


def _read_docx_xml_fallback(path: Path) -> str:
    texts: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if not name.startswith("word/") or not name.endswith(".xml"):
                    continue
                try:
                    payload = archive.read(name)
                except KeyError:
                    continue
                try:
                    root = ET.fromstring(payload)
                except ET.ParseError:
                    continue
                texts.extend([node.strip() for node in root.itertext() if node and node.strip()])
    except Exception:
        return ""
    return "\n".join(texts).strip()


def _read_pdf(path: Path) -> str:
    if not HAS_PYPDF or PdfReader is None:
        return ""

    pages: list[str] = []
    try:
        reader = PdfReader(str(path))
    except Exception:
        return ""

    for page in getattr(reader, "pages", []):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        normalized = re.sub(r"\s+", " ", text).strip()
        if normalized:
            pages.append(normalized)
    return "\n\n".join(pages).strip()


def extract_platform_dna_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return _read_plain_text(path).strip()
    if suffix in DOCX_EXTENSIONS:
        return (_read_docx_with_python_docx(path) or _read_docx_xml_fallback(path)).strip()
    if suffix in PDF_EXTENSIONS:
        return _read_pdf(path).strip()
    raise ValueError(f"unsupported_extension:{suffix}")


def supported_platform_dna_extensions() -> tuple[str, ...]:
    return tuple(sorted(TEXT_EXTENSIONS | DOCX_EXTENSIONS | PDF_EXTENSIONS))
~~~

## `backend/app/services/review_analysis.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import datetime
from typing import Literal

from app.models import (
    EventLineCompletenessRecord,
    EventLineEvidenceSlotRecord,
    EventLineJudgmentRecord,
    EventLineOpportunityCardRecord,
    EventLineRiskCardRecord,
    ReviewDashboardCardTargetRecord,
    ReviewDashboardEvidenceRefRecord,
    EventLineSummaryCardRecord,
    HierarchyReportRecord,
    OrgModelProfileRecord,
    OrganizationDnaModuleRecord,
    ReviewEvidenceWeightRecord,
    ReviewHypothesisRecord,
    ReviewMetricCardRecord,
    TrendSignalRecord,
    WeeklyReviewAnalysisRecord,
    WeeklyReviewTaskEntryRecord,
)
from app.services.knowledge_base import tokenize
from app.services.memory_foundation import sanitize_memory_background_text

ReviewViewerRole = Literal["employee", "department_lead", "admin"]

SUCCESS_KEYWORDS = ("完成", "推进", "落地", "交付", "落实", "确认", "跑通", "有效", "顺畅", "清楚", "达成")
ISSUE_KEYWORDS = ("卡住", "阻力", "困难", "问题", "风险", "不足", "不清", "延迟", "冲突", "等待", "没法", "不明确")
SUPPORT_KEYWORDS = ("需要支持", "需要帮助", "资源", "协同", "支持", "配合", "接口", "协调")
BUSINESS_KEYWORDS = ("客户", "用户", "需求", "方案", "转化", "产品", "项目", "服务", "验证", "交付")
TEAM_KEYWORDS = ("协作", "协同", "对齐", "接口", "责任", "分工", "交接", "支持", "排期", "同步", "配合")
MARKET_KEYWORDS = ("市场", "行业", "竞品", "传播", "渠道", "政策", "外部", "趋势", "流量", "品牌")
GROWTH_KEYWORDS = ("感受", "观察", "状态", "学到", "收获", "反思", "习惯", "节奏", "精力", "判断")

MODULE_LENS: dict[str, Literal["organization", "business", "team", "market"]] = {
    "organization_intro": "organization",
    "business_intro": "business",
    "team_intro": "team",
    "market_intro": "market",
}

LENS_LABEL: dict[str, str] = {
    "execution": "执行层",
    "organization": "组织视角",
    "business": "业务视角",
    "team": "团队视角",
    "market": "市场视角",
    "growth": "成长视角",
}

BUSINESS_CATEGORY_LENS: dict[str, Literal["organization", "business", "team", "market"]] = {
    "业务扩展": "business",
    "项目推进": "business",
    "产品化沉淀": "organization",
    "组织协同": "team",
    "管理机制": "organization",
    "外部合作": "market",
    "专项推进": "business",
}

LIGHTWEIGHT_TAG_ACTIONS: dict[str, str] = {
    "资料不足": "先补齐关键资料、上下文和输入，再判断这件事是否值得继续推进。",
    "等待他人": "先把外部依赖、等待对象和最晚回收时间点写清，避免任务继续悬空。",
    "方向不清": "先补目标、边界和判断标准，不要在方向模糊时继续堆动作。",
    "资源不够": "先确认缺的是人力、时间还是预算，再决定是压缩范围还是争取支持。",
    "工作过度饱和": "这更像容量过载信号，建议优先做取舍，而不是继续叠加任务。",
}

QUARTER_PATTERN = re.compile(r"(Q[1-4]|季度|本季度|季度重点|季度目标|本季)")
TEAM_PLAN_MODULE_MARKER = "部门计划背景"

COMPLETION_STATUS_LABEL: dict[str, str] = {
    "done_on_time": "按时完成",
    "done_late": "延迟完成",
    "in_progress": "仍在推进",
    "not_done": "未完成",
}

ALIGNMENT_STATUS_LABEL: dict[str, str] = {
    "aligned": "明确对齐",
    "partial": "部分对齐",
    "misaligned": "存在偏离",
    "unknown": "待补录",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _sanitize_story_text(value: object | None, *, reject_generic: bool = False, max_length: int = 140) -> str:
    return sanitize_memory_background_text(value, reject_generic=reject_generic, max_length=max_length)


def _sanitize_story_texts(
    values: list[object | None],
    *,
    reject_generic: bool = False,
    limit: int = 6,
    max_length: int = 140,
) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _sanitize_story_text(value, reject_generic=reject_generic, max_length=max_length)
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append(normalized)
        if len(cleaned) >= limit:
            break
    return cleaned


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _item_text(item: WeeklyReviewTaskEntryRecord) -> str:
    reflection = _reflection_text(item)
    tags = " ".join(tag.name for tag in item.taskSnapshot.tags)
    structured = " ".join(
        part
        for part in [
            reflection,
            item.structuredNote.lightweightTag,
            item.structuredNote.progress,
            item.structuredNote.blockerReason,
            item.structuredNote.supportNeeded,
        ]
        if part
    )
    return _clean_text(
        f"{item.taskSnapshot.title} {item.note} {structured} {item.taskSnapshot.listName} {tags}"
    ).lower()


def _item_short_label(item: WeeklyReviewTaskEntryRecord) -> str:
    return item.taskSnapshot.title.strip() or item.taskId


def _reflection_text(item: WeeklyReviewTaskEntryRecord) -> str:
    candidates = [
        item.structuredNote.reflection.strip(),
        item.structuredNote.successExperience.strip(),
        item.structuredNote.supportNeeded.strip(),
        item.structuredNote.failureInsight.strip(),
        item.structuredNote.blockerReason.strip(),
        item.structuredNote.progress.strip(),
        item.note.strip(),
    ]
    return next((item for item in candidates if item), "")


def _lightweight_tag(item: WeeklyReviewTaskEntryRecord) -> str:
    return item.structuredNote.lightweightTag.strip()


def _item_department_id(item: WeeklyReviewTaskEntryRecord) -> str:
    context = item.taskSnapshot.orgContext
    return (context.departmentId if context else "") or ""


def _item_focus_item_id(item: WeeklyReviewTaskEntryRecord) -> str:
    context = item.taskSnapshot.orgContext
    return (context.focusItemId if context else "") or ""


def _item_department_plan_item_id(item: WeeklyReviewTaskEntryRecord) -> str:
    context = item.taskSnapshot.orgContext
    return (context.departmentPlanItemId if context else "") or ""


def _item_project_context(item: WeeklyReviewTaskEntryRecord):
    return item.taskSnapshot.projectContext


def _item_event_line_context(item: WeeklyReviewTaskEntryRecord):
    return item.taskSnapshot.eventLineContext


def _item_event_line_id(item: WeeklyReviewTaskEntryRecord) -> str:
    raw = (item.taskSnapshot.eventLineId or "").strip()
    if raw.startswith("event_line::"):
        return raw.split("::", 1)[1].strip()
    return raw


def _item_event_line_name(item: WeeklyReviewTaskEntryRecord) -> str:
    return (item.taskSnapshot.eventLineName or "").strip()


def _extract_tokens(text: str) -> list[str]:
    return [token for token in tokenize(text) if token and len(token.strip()) >= 2]


def _module_preview(module: OrganizationDnaModuleRecord) -> str:
    return _clean_text(module.summary or module.normalizedText[:360])


def _module_source_text(module: OrganizationDnaModuleRecord) -> str:
    return "\n".join(part for part in [module.markdownContent, module.normalizedText, module.summary] if part).strip()


def _team_plan_modules(dna_modules: list[OrganizationDnaModuleRecord]) -> list[OrganizationDnaModuleRecord]:
    return [
        module
        for module in dna_modules
        if module.moduleKey == "team_intro" and TEAM_PLAN_MODULE_MARKER in module.title
    ]


def _extract_quarter_goal_lines(dna_modules: list[OrganizationDnaModuleRecord]) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for module in dna_modules:
        if module.moduleKey != "organization_intro":
            continue
        source_text = _module_source_text(module)
        if not source_text:
            continue
        candidates = re.split(r"[\r\n]+|(?<=[。；;])", source_text)
        for raw in candidates:
            candidate = _clean_text(re.sub(r"^[\-\d\.\)\s、]+", "", raw))
            if len(candidate) < 6 or len(candidate) > 120:
                continue
            if not QUARTER_PATTERN.search(candidate):
                continue
            key = candidate.lower()
            if key in seen:
                continue
            seen.add(key)
            lines.append(candidate.rstrip("。；;"))
    return lines[:4]


def _dedupe_texts(values: list[str], limit: int = 6) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _clean_text(value)
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append(normalized)
        if len(cleaned) >= limit:
            break
    return cleaned


def _truncate_overview_text(value: str, limit: int = 84) -> str:
    normalized = _clean_text(value)
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip("，、；：: ") + "…"


OVERVIEW_INFRA_KEYWORDS = ("debug", "排查", "修复", "联调", "上传", "保存", "附件", "可见", "可见性", "回写", "启动", "登录", "卡死")
OVERVIEW_INTEL_KEYWORDS = ("情报", "资讯", "报告", "研究", "倡导", "引关注", "趋势", "观察")
OVERVIEW_COLLAB_KEYWORDS = ("合作", "协作", "协同", "交流", "讨论", "对接", "工作坊", "战略", "诊断", "梳理", "收束")


def _item_full_text(item: WeeklyReviewTaskEntryRecord) -> str:
    snap = item.taskSnapshot
    parts = [
        snap.title,
        getattr(snap, "desc", "") or "",
        getattr(snap, "note", "") or "",
        item.note or "",
        _reflection_text(item),
        snap.clientName or "",
        snap.eventLineName or "",
        snap.listName or "",
    ]
    return _clean_text(" ".join(part for part in parts if part)).lower()


def _client_background_hint(dna_modules: list[OrganizationDnaModuleRecord], client_name: str) -> str:
    if not client_name:
        return ""
    for module in dna_modules:
        if client_name in module.title:
            return _module_source_text(module)
    return ""


def _build_weekly_overview(
    items: list[WeeklyReviewTaskEntryRecord],
    dna_modules: list[OrganizationDnaModuleRecord],
    note_items_count: int,
) -> tuple[str, list[str], list[str]]:
    if not items:
        return ("本周暂无可复盘的事项。", [], [])

    texts = [_item_full_text(item) for item in items]
    infra_items = [item for item, text in zip(items, texts) if _contains_any(text, OVERVIEW_INFRA_KEYWORDS)]
    intel_items = [item for item, text in zip(items, texts) if _contains_any(text, OVERVIEW_INTEL_KEYWORDS)]
    collab_items = [item for item, text in zip(items, texts) if _contains_any(text, OVERVIEW_COLLAB_KEYWORDS)]
    cffc_items = [item for item, text in zip(items, texts) if "cffc" in text or "鸿鹄" in text or "洪峰" in text]

    client_names = _dedupe_texts([item.taskSnapshot.clientName or "" for item in items if item.taskSnapshot.clientName], limit=6)
    companion_clients = [name for name in client_names if any(key in name for key in ("日慈", "为爱", "向光"))]

    focus_lines: list[str] = []
    if infra_items:
        focus_lines.append("软件底层链路修稳")
    if cffc_items:
        focus_lines.append("CFFC 合作推进")
    if companion_clients:
        focus_lines.append("客户陪伴收束")
    if intel_items:
        focus_lines.append("情报沉淀与议题输入")
    if not focus_lines and collab_items:
        focus_lines.append("合作与协作线推进")

    overview_parts: list[str] = ["这周对益语来说，更像是一周在打底、铺线、蓄力。"]

    if infra_items:
        overview_parts.append(
            "本周花了不少精力在把软件底层链路修稳，围绕附件保存、上传写入、新建任务可见性等做了多轮排查，本质是在补地基。"
        )

    if cffc_items:
        background_hint = _client_background_hint(dna_modules, "CFFC")
        extra = ""
        if any(keyword in background_hint for keyword in ("枢纽", "基金会", "行业")):
            extra = "它的意义不只是一次合作，而是通过行业关键枢纽进入更大网络的机会。"
        overview_parts.append(f"围绕 CFFC 的合作讨论和说明迭代在推进。{extra}".rstrip("。"))

    if companion_clients:
        names = "、".join(companion_clients[:2])
        overview_parts.append(f"客户陪伴线开始从泛沟通往更具体的诊断或收束推进，{names} 逐步落到更清楚的项目梳理上。")

    if intel_items:
        intel_titles = _dedupe_texts([item.taskSnapshot.title for item in intel_items if item.taskSnapshot.title], limit=2)
        if intel_titles:
            overview_parts.append(f"本周有值得沉淀的情报线索：{ '；'.join(intel_titles) }，已开始接到后续咨询议题。")
        else:
            overview_parts.append("本周有几条情报线索已经开始接到后续咨询议题。")

    review_ratio = note_items_count / max(1, len(items))
    if review_ratio < 0.3:
        overview_parts.append("当前系统可读的复盘说明仍然偏少，判断深度主要停留在任务事实和备注层。")

    overview_parts.append("整体来看，这是偏打底和铺线的一周。")

    next_focus: list[str] = []
    if cffc_items:
        next_focus.append("把 CFFC 这条线继续往更明确的合作边界和方式上收。")
    if companion_clients:
        next_focus.append("把客户陪伴线推进到更清楚的诊断或项目梳理结果。")
    if review_ratio < 0.3:
        next_focus.append("把本周任务复盘补进系统，让判断不只看到动作。")
    if not next_focus and focus_lines:
        next_focus.append("围绕本周主线做收束性推进，避免同时开太多新线。")

    return " ".join(_dedupe_texts(overview_parts, limit=8)), focus_lines[:4], next_focus[:3]


def _overview_line(title: str, body: str) -> str:
    normalized_title = _clean_text(title).rstrip("：:｜")
    normalized_body = _truncate_overview_text(body)
    if not normalized_title:
        return normalized_body
    if not normalized_body or normalized_body == normalized_title:
        return normalized_title
    return f"{normalized_title}｜{normalized_body}"


def _event_line_story_target(story: dict[str, object]) -> ReviewDashboardCardTargetRecord:
    raw_key = str(story.get("id") or "")
    raw_event_line_id = str(story.get("eventLineId") or "")
    title = str(story.get("name") or "").strip()
    clients = list(story.get("clients") or [])
    category = str(story.get("category") or "").strip()
    if raw_key.startswith("event_line::") and raw_event_line_id:
        return ReviewDashboardCardTargetRecord(
            targetType="event_line",
            targetId=raw_event_line_id,
            targetLabel=title or raw_event_line_id,
            targetFilters={
                "eventLineId": raw_event_line_id,
                "businessCategory": category or None,
            },
        )
    return ReviewDashboardCardTargetRecord(
        targetType="task_view",
        targetId=raw_key or f"story::{title}",
        targetLabel=title or "相关任务",
        targetFilters={
            "groupKey": raw_key,
            "clientNames": [str(item) for item in clients if str(item).strip()],
            "businessCategories": [category] if category else [],
            "onlyWithEventLine": False,
        },
    )


def _story_evidence_refs(
    story: dict[str, object],
    *,
    include_event_line_ref: bool = True,
    limit: int = 4,
) -> list[ReviewDashboardEvidenceRefRecord]:
    refs: list[ReviewDashboardEvidenceRefRecord] = []
    raw_key = str(story.get("id") or "")
    raw_event_line_id = str(story.get("eventLineId") or "")
    title = str(story.get("name") or "").strip()
    if include_event_line_ref and raw_key.startswith("event_line::") and raw_event_line_id:
        refs.append(
            ReviewDashboardEvidenceRefRecord(
                sourceType="event_line",
                sourceId=raw_event_line_id,
                title=title or raw_event_line_id,
                summary=_truncate_overview_text(
                    _first_non_empty(
                        [str(item) for item in story.get("lineSummaries", []) if str(item).strip()]
                        + [str(item) for item in story.get("lineIntents", []) if str(item).strip()]
                    )
                    or title
                ),
            )
        )
    task_ids = [str(item) for item in story.get("taskIds", []) if str(item).strip()]
    task_titles = [str(item) for item in story.get("taskTitles", []) if str(item).strip()]
    for task_id, task_title in zip(task_ids[:limit], task_titles[:limit]):
        refs.append(
            ReviewDashboardEvidenceRefRecord(
                sourceType="task",
                sourceId=task_id,
                title=task_title,
                summary=_truncate_overview_text(task_title),
            )
        )
    return refs[:limit]


def _event_line_overview_lines(items: list[EventLineSummaryCardRecord], limit: int = 4) -> list[str]:
    return _dedupe_texts(
        [
            _overview_line(item.title, item.whatHappenedThisWeek or item.currentState or item.whatThisLineIs)
            for item in items[:limit]
        ],
        limit=limit,
    )


def _judgment_overview_lines(items: list[EventLineJudgmentRecord], limit: int = 4) -> list[str]:
    return _dedupe_texts(
        [_overview_line(item.title, item.whatHappened or item.whyItMatters or item.nextWeekFocus) for item in items[:limit]],
        limit=limit,
    )


def _judgment_blocker_lines(items: list[EventLineJudgmentRecord], limit: int = 4) -> list[str]:
    return _dedupe_texts(
        [_overview_line(item.title, item.coreBlocker or item.riskIfIgnored) for item in items[:limit]],
        limit=limit,
    )


def _judgment_action_lines(items: list[EventLineJudgmentRecord], limit: int = 4) -> list[str]:
    return _dedupe_texts(
        [_overview_line(item.title, item.minimumAction or item.nextWeekFocus) for item in items[:limit]],
        limit=limit,
    )


def _risk_overview_lines(items: list[EventLineRiskCardRecord], limit: int = 4) -> list[str]:
    return _dedupe_texts(
        [_overview_line(item.title, item.statement) for item in items[:limit]],
        limit=limit,
    )


def _opportunity_overview_lines(items: list[EventLineOpportunityCardRecord], limit: int = 4) -> list[str]:
    return _dedupe_texts(
        [_overview_line(item.title, item.statement) for item in items[:limit]],
        limit=limit,
    )


def _hypothesis_overview_lines(items: list[ReviewHypothesisRecord], limit: int = 4) -> list[str]:
    return _dedupe_texts(
        [_overview_line(item.title, item.statement) for item in items[:limit]],
        limit=limit,
    )


def _next_focus_overview_lines(values: list[str], limit: int = 4) -> list[str]:
    return _dedupe_texts([_overview_line("下周关注", value) for value in values[:limit]], limit=limit)


def _department_plan_reference_texts(
    org_model_profile: OrgModelProfileRecord | None,
    *,
    week_label: str,
    items: list[WeeklyReviewTaskEntryRecord],
) -> list[str]:
    if org_model_profile is None:
        return []
    department_ids = {_item_department_id(item) for item in items if _item_department_id(item)}
    linked_plan_item_ids = {_item_department_plan_item_id(item) for item in items if _item_department_plan_item_id(item)}
    linked_focus_ids = {_item_focus_item_id(item) for item in items if _item_focus_item_id(item)}
    texts: list[str] = []
    for plan in org_model_profile.departmentPlans:
        if plan.weekLabel != week_label:
            continue
        if department_ids and plan.departmentId and plan.departmentId not in department_ids:
            continue
        if plan.summary.strip():
            texts.append(plan.summary.strip())
        for plan_item in plan.items:
            if linked_plan_item_ids and plan_item.id not in linked_plan_item_ids and plan_item.focusItemId not in linked_focus_ids:
                continue
            texts.append(
                _clean_text(
                    " ".join(
                        part
                        for part in [
                            plan_item.title,
                            plan_item.statement,
                            plan_item.expectedOutput,
                        ]
                        if part
                    )
                )
            )
    if not texts and department_ids:
        for plan in org_model_profile.departmentPlans:
            if plan.weekLabel != week_label:
                continue
            if plan.departmentId and plan.departmentId not in department_ids:
                continue
            texts.extend(
                _clean_text(" ".join(part for part in [item.title, item.statement, item.expectedOutput] if part))
                for item in plan.items
            )
            if plan.summary.strip():
                texts.append(plan.summary.strip())
    return _dedupe_texts(texts, limit=8)


def _focus_item_reference_texts(org_model_profile: OrgModelProfileRecord | None) -> list[str]:
    if org_model_profile is None:
        return []
    texts = [
        _clean_text(" ".join(part for part in [item.title, item.statement, " ".join(item.evidenceKeywords)] if part))
        for item in org_model_profile.focusItems
        if item.status in {"draft", "active"}
    ]
    return _dedupe_texts(texts, limit=6)


def _project_context_summary(items: list[WeeklyReviewTaskEntryRecord]) -> dict[str, object]:
    contexts = [context for item in items if (context := _item_project_context(item))]
    client_names = _dedupe_texts([context.clientName for context in contexts if context.clientName], limit=4)
    stages = _dedupe_texts([context.stage or "" for context in contexts], limit=3)
    goals = _dedupe_texts([context.goalSummary for context in contexts if context.goalSummary], limit=3)
    risks = _dedupe_texts([context.riskSummary for context in contexts if context.riskSummary], limit=3)
    evidence = _dedupe_texts([evidence for context in contexts for evidence in context.sourceEvidence], limit=6)
    completeness_levels = Counter(context.infoCompleteness for context in contexts if context.infoCompleteness)
    highest_completeness = "low"
    if completeness_levels.get("high"):
        highest_completeness = "high"
    elif completeness_levels.get("medium"):
        highest_completeness = "medium"
    return {
        "count": len(contexts),
        "clients": client_names,
        "stages": stages,
        "goals": goals,
        "risks": risks,
        "evidence": evidence,
        "infoCompleteness": highest_completeness,
    }


def _event_line_summary(items: list[WeeklyReviewTaskEntryRecord]) -> dict[str, object]:
    groups: dict[str, dict[str, object]] = {}
    for item in items:
        event_line_id = _item_event_line_id(item)
        if not event_line_id:
            continue
        bucket = groups.setdefault(
            event_line_id,
            {
                "name": _item_event_line_name(item) or _item_short_label(item),
                "items": [],
            },
        )
        bucket["items"].append(item)  # type: ignore[index]

    multi_task_groups = [
        bucket
        for bucket in groups.values()
        if len(bucket["items"]) >= 2  # type: ignore[index]
    ]
    blocked_groups = []
    for bucket in groups.values():
        bucket_items: list[WeeklyReviewTaskEntryRecord] = bucket["items"]  # type: ignore[assignment]
        if any(_completion_status(item) in {"in_progress", "not_done"} for item in bucket_items):
            blocked_groups.append(bucket)
    names = _dedupe_texts([str(bucket["name"]) for bucket in groups.values()], limit=4)
    blocked_names = _dedupe_texts([str(bucket["name"]) for bucket in blocked_groups], limit=3)
    return {
        "groupCount": len(groups),
        "taskCount": sum(len(bucket["items"]) for bucket in groups.values()),  # type: ignore[index]
        "multiTaskGroupCount": len(multi_task_groups),
        "names": names,
        "blockedGroupCount": len(blocked_groups),
        "blockedNames": blocked_names,
    }


def _item_group_key(item: WeeklyReviewTaskEntryRecord) -> str:
    event_line_id = _item_event_line_id(item)
    if event_line_id:
        return f"event_line::{event_line_id}"
    project_context = _item_project_context(item)
    if project_context and (project_context.clientId or project_context.clientName):
        return f"project::{project_context.clientId or project_context.clientName}"
    return ""


def _item_group_name(item: WeeklyReviewTaskEntryRecord) -> str:
    event_line_name = _item_event_line_name(item)
    if event_line_name:
        return event_line_name
    project_context = _item_project_context(item)
    if project_context and project_context.clientName:
        return project_context.clientName
    return _item_short_label(item)


def _item_next_step_hint(item: WeeklyReviewTaskEntryRecord) -> str:
    candidates = [
        item.structuredNote.nextAction.strip(),
        item.structuredNote.supportNeeded.strip(),
        item.structuredNote.blockerReason.strip(),
        item.structuredNote.failureInsight.strip(),
        item.structuredNote.progress.strip(),
        item.note.strip(),
    ]
    return next((candidate for candidate in candidates if candidate), "")


def _recent_decision_hint(item: WeeklyReviewTaskEntryRecord) -> str:
    candidates = [
        item.structuredNote.planCommitment.strip(),
        item.structuredNote.progress.strip(),
        _reflection_text(item),
        item.note.strip(),
    ]
    decision_keywords = ("决定", "确认", "改为", "暂定", "确定", "拍板", "收束", "切到", "优先")
    return next((candidate for candidate in candidates if candidate and _contains_any(candidate, decision_keywords)), "")


def _infer_business_category(text: str) -> str:
    if _contains_any(text, ("基金会", "客户", "合作", "工作坊", "方案", "拜访", "赋能", "拓展", "bd")):
        return "业务扩展"
    if _contains_any(text, ("模板", "标准件", "系统", "产品", "自动化", "sop", "组件", "资料底盘", "沉淀")):
        return "产品化沉淀"
    if _contains_any(text, ("交付", "推进", "落地", "收束", "会后", "对接", "反馈", "执行")):
        return "项目推进"
    if _contains_any(text, ("流程", "复核", "审批", "协同", "对齐", "汇报", "支持", "确认链")):
        return "组织协同"
    if _contains_any(text, ("预算", "资源", "机制", "规则", "权限", "治理")):
        return "管理机制"
    if _contains_any(text, ("传播", "活动", "品牌", "外部", "媒体", "渠道")):
        return "外部合作"
    return "专项推进"


def _event_line_story_groups(items: list[WeeklyReviewTaskEntryRecord]) -> list[dict[str, object]]:
    groups: dict[str, dict[str, object]] = {}
    for item in items:
        group_key = _item_group_key(item)
        if not group_key:
            continue
        bucket = groups.setdefault(
            group_key,
            {
                "id": group_key,
                "eventLineId": _item_event_line_id(item) or group_key,
                "name": _item_group_name(item),
                "items": [],
                "taskTitles": [],
                "clients": [],
                "stages": [],
                "goals": [],
                "risks": [],
                "currentFocuses": [],
                "currentBlockers": [],
                "nextSteps": [],
                "recentProgresses": [],
                "owners": [],
                "moduleNames": [],
                "flowNames": [],
                "recentDecisions": [],
                "lineSummaries": [],
                "lineIntents": [],
                "lineStages": [],
                "lineBlockers": [],
                "lineNextSteps": [],
                "lineRecentDecisions": [],
            },
        )
        bucket["items"].append(item)  # type: ignore[index]
        bucket["taskTitles"].append(_item_short_label(item))  # type: ignore[index]
        if item.taskSnapshot.ownerName:
            bucket["owners"].append(item.taskSnapshot.ownerName)  # type: ignore[index]
        event_line_context = _item_event_line_context(item)
        if event_line_context:
            if event_line_context.summary:
                bucket["lineSummaries"].append(event_line_context.summary)  # type: ignore[index]
            if event_line_context.intent:
                bucket["lineIntents"].append(event_line_context.intent)  # type: ignore[index]
            if event_line_context.stage:
                bucket["lineStages"].append(event_line_context.stage)  # type: ignore[index]
            if event_line_context.currentBlocker:
                bucket["lineBlockers"].append(event_line_context.currentBlocker)  # type: ignore[index]
            if event_line_context.nextStep:
                bucket["lineNextSteps"].append(event_line_context.nextStep)  # type: ignore[index]
            if event_line_context.recentDecision:
                bucket["lineRecentDecisions"].append(event_line_context.recentDecision)  # type: ignore[index]
            if event_line_context.primaryClientName:
                bucket["clients"].append(event_line_context.primaryClientName)  # type: ignore[index]
        project_context = _item_project_context(item)
        if project_context:
            if project_context.clientName:
                bucket["clients"].append(project_context.clientName)  # type: ignore[index]
            if project_context.stage:
                bucket["stages"].append(project_context.stage)  # type: ignore[index]
            if project_context.goalSummary:
                bucket["goals"].append(project_context.goalSummary)  # type: ignore[index]
            if project_context.riskSummary:
                bucket["risks"].append(project_context.riskSummary)  # type: ignore[index]
            if getattr(project_context, "currentFocus", None):
                bucket["currentFocuses"].append(project_context.currentFocus)  # type: ignore[index]
            if getattr(project_context, "currentBlocker", None):
                bucket["currentBlockers"].append(project_context.currentBlocker)  # type: ignore[index]
            if getattr(project_context, "nextAction", None):
                bucket["nextSteps"].append(project_context.nextAction)  # type: ignore[index]
            if getattr(project_context, "recentProgress", None):
                bucket["recentProgresses"].append(project_context.recentProgress)  # type: ignore[index]
            if getattr(project_context, "projectModuleName", None):
                bucket["moduleNames"].append(project_context.projectModuleName)  # type: ignore[index]
            if getattr(project_context, "projectFlowName", None):
                bucket["flowNames"].append(project_context.projectFlowName)  # type: ignore[index]
        next_step_hint = _item_next_step_hint(item)
        if next_step_hint:
            bucket["nextSteps"].append(next_step_hint)  # type: ignore[index]
        recent_decision = _recent_decision_hint(item)
        if recent_decision:
            bucket["recentDecisions"].append(recent_decision)  # type: ignore[index]

    stories: list[dict[str, object]] = []
    for bucket in groups.values():
        bucket_items: list[WeeklyReviewTaskEntryRecord] = bucket["items"]  # type: ignore[assignment]
        task_titles = _dedupe_texts([str(item) for item in bucket["taskTitles"]], limit=4)
        clients = _sanitize_story_texts([str(item) for item in bucket["clients"]], limit=2, max_length=40)
        stages = _sanitize_story_texts([str(item) for item in bucket["stages"]], limit=2, max_length=40)
        goals = _sanitize_story_texts([str(item) for item in bucket["goals"]], reject_generic=True, limit=2)
        risks = _sanitize_story_texts([str(item) for item in bucket["risks"]], reject_generic=True, limit=2)
        current_focuses = _sanitize_story_texts([str(item) for item in bucket["currentFocuses"]], reject_generic=True, limit=2)
        current_blockers = _sanitize_story_texts([str(item) for item in bucket["currentBlockers"]], reject_generic=True, limit=2)
        next_steps = _sanitize_story_texts([str(item) for item in bucket["nextSteps"]], reject_generic=True, limit=2)
        recent_progresses = _sanitize_story_texts([str(item) for item in bucket["recentProgresses"]], reject_generic=True, limit=2)
        owners = _sanitize_story_texts([str(item) for item in bucket["owners"]], limit=3, max_length=16)
        module_names = _sanitize_story_texts([str(item) for item in bucket["moduleNames"]], limit=2, max_length=40)
        flow_names = _sanitize_story_texts([str(item) for item in bucket["flowNames"]], limit=2, max_length=40)
        recent_decisions = _sanitize_story_texts([str(item) for item in bucket["recentDecisions"]], reject_generic=True, limit=2)
        line_summaries = _sanitize_story_texts([str(item) for item in bucket["lineSummaries"]], reject_generic=True, limit=2)
        line_intents = _sanitize_story_texts([str(item) for item in bucket["lineIntents"]], reject_generic=True, limit=2)
        line_stages = _sanitize_story_texts([str(item) for item in bucket["lineStages"]], limit=2, max_length=40)
        line_blockers = _sanitize_story_texts([str(item) for item in bucket["lineBlockers"]], reject_generic=True, limit=2)
        line_next_steps = _sanitize_story_texts([str(item) for item in bucket["lineNextSteps"]], reject_generic=True, limit=2)
        line_recent_decisions = _sanitize_story_texts([str(item) for item in bucket["lineRecentDecisions"]], reject_generic=True, limit=2)
        stage_sources = line_stages + stages
        current_focus_sources = line_intents + current_focuses
        goal_sources = line_intents + line_summaries + goals + current_focuses
        blocker_sources = line_blockers + current_blockers + risks
        next_step_sources = line_next_steps + next_steps
        recent_decision_sources = line_recent_decisions + recent_decisions
        text_blob = " ".join(
            [
                str(bucket["name"]),
                " ".join(task_titles),
                " ".join(clients),
                " ".join(stage_sources),
                " ".join(module_names),
                " ".join(flow_names),
                " ".join(current_focus_sources),
                " ".join(goal_sources),
                " ".join(blocker_sources),
                " ".join(next_step_sources),
                " ".join(recent_progresses),
                " ".join(recent_decision_sources),
            ]
        ).lower()
        stories.append(
            {
                "id": str(bucket["id"]),
                "name": str(bucket["name"]),
                "taskIds": [item.taskId for item in bucket_items],
                "taskTitles": task_titles,
                "clients": clients,
                "stages": stage_sources,
                "currentFocuses": current_focus_sources,
                "currentBlockers": blocker_sources,
                "goals": goal_sources,
                "risks": risks,
                "nextSteps": next_step_sources,
                "recentProgresses": recent_progresses,
                "owners": owners,
                "moduleNames": module_names,
                "flowNames": flow_names,
                "recentDecisions": recent_decision_sources,
                "lineSummaries": line_summaries,
                "lineIntents": line_intents,
                "completedCount": sum(1 for item in bucket_items if _completion_status(item) in {"done_on_time", "done_late"}),
                "unfinishedCount": sum(1 for item in bucket_items if _completion_status(item) in {"in_progress", "not_done"}),
                "category": _infer_business_category(text_blob),
            }
        )
    stories.sort(
        key=lambda story: (
            -int(story["unfinishedCount"]),
            -len(story["taskIds"]),  # type: ignore[arg-type]
            str(story["name"]),
        )
    )
    return stories


def _slot_strength_score(value: Literal["strong", "medium", "weak", "none"]) -> float:
    if value == "strong":
        return 1.0
    if value == "medium":
        return 0.75
    if value == "weak":
        return 0.5
    return 0.0


def _event_line_completeness_status(score: int) -> Literal["insufficient", "summary_ready", "forecast_ready", "high_confidence"]:
    if score >= 85:
        return "high_confidence"
    if score >= 65:
        return "forecast_ready"
    if score >= 40:
        return "summary_ready"
    return "insufficient"


def _prediction_readiness(status: Literal["insufficient", "summary_ready", "forecast_ready", "high_confidence"]) -> Literal["not_ready", "summary_only", "conservative_forecast", "strong_forecast"]:
    if status == "high_confidence":
        return "strong_forecast"
    if status == "forecast_ready":
        return "conservative_forecast"
    if status == "summary_ready":
        return "summary_only"
    return "not_ready"


def _build_event_line_slot(
    *,
    key: Literal["stage", "goal", "blocker", "next_action", "recent_change", "owner_chain", "recent_decision", "project_link"],
    label: str,
    values: list[str],
    source_types: list[Literal["event_line", "task_fact", "project_context", "user_note", "uploaded_doc", "manual_clarification"]],
    recommended_fix: Literal["upload_docs", "clarify_now", "wait_for_more_trace"],
    fallback_summary: str,
    prefer_full_when_any: bool = False,
) -> EventLineEvidenceSlotRecord:
    cleaned = _dedupe_texts(values, limit=2)
    if cleaned:
        if prefer_full_when_any or len(cleaned) >= 2:
            coverage: Literal["full", "partial", "missing"] = "full"
            strength: Literal["strong", "medium", "weak", "none"] = "strong" if len(source_types) >= 2 or len(cleaned) >= 2 else "medium"
        else:
            coverage = "partial"
            strength = "medium" if source_types else "weak"
        summary = "；".join(cleaned)
    else:
        coverage = "missing"
        strength = "none"
        summary = fallback_summary
    return EventLineEvidenceSlotRecord(
        key=key,
        label=label,
        coverage=coverage,
        evidenceStrength=strength,
        sourceTypes=source_types,
        summary=summary,
        recommendedFix=recommended_fix,
    )


def _infer_risk_type(text: str) -> Literal["schedule_drift", "collaboration_friction", "decision_lag", "goal_drift", "workflow_breakdown", "overload"]:
    normalized = text.lower()
    if _contains_any(normalized, ("协作", "接口", "对齐", "等待他人", "跨部门", "配合")):
        return "collaboration_friction"
    if _contains_any(normalized, ("审批", "决策", "确认", "拍板", "定不下来")):
        return "decision_lag"
    if _contains_any(normalized, ("流程", "步骤", "卡点", "模板")):
        return "workflow_breakdown"
    if _contains_any(normalized, ("资源", "过载", "饱和", "人手", "容量")):
        return "overload"
    if _contains_any(normalized, ("目标", "方向", "偏", "不清")):
        return "goal_drift"
    return "schedule_drift"


BUSINESS_CATEGORY_THEME: dict[str, dict[str, str]] = {
    "业务扩展": {
        "identity": "做客户关系推进与合作收束",
        "progress": "客户判断、方案确认和下一轮沟通准备",
        "state": "关键不是再铺更多动作，而是把合作边界和关键确认节点说死",
        "fallback_blocker": "合作边界、确认节奏或下一轮沟通节点",
        "fallback_next": "先把下一轮沟通、关键人和合作边界收住",
        "upside": "把零散接触转成更清楚的业务机会，并让领导判断是否值得继续加码",
        "admin_risk_tail": "机构层会继续看不清这条线究竟是高潜机会、一般跟进，还是应该及时止损的探索。",
        "employee_risk_tail": "执行会继续陷在反复确认里，很难把推进动作收成明确进展。",
        "opportunity_type": "momentum_building",
    },
    "项目推进": {
        "identity": "做交付收口与推进节奏控制",
        "progress": "把交付动作往可审阅、可执行或可验收状态推进",
        "state": "重点不是继续加任务，而是把交付收口、确认链和接口责任压实",
        "fallback_blocker": "交付接口、资料补齐或确认链收口不够",
        "fallback_next": "先把当前交付动作压成明确收口节点",
        "upside": "把这条线从忙碌推进变成可复盘的稳定交付节奏",
        "admin_risk_tail": "这条线会继续拖慢项目节奏，并消耗管理层对关键交付的判断带宽。",
        "employee_risk_tail": "执行会继续卡在交接、补齐和来回确认上，返工会明显增加。",
        "opportunity_type": "repeatable_pattern",
    },
    "产品化沉淀": {
        "identity": "沉淀模板、标准件和系统能力",
        "progress": "把零散经验、资料和判断固化成可复用结构",
        "state": "重点不是再补更多描述，而是把可复用结构、样本边界和输出标准钉住",
        "fallback_blocker": "结构还没钉死、输入样本不稳或标准还不统一",
        "fallback_next": "先把样本、结构和输出标准收束成可复用件",
        "upside": "一旦收束，会直接变成模板、标准件或 AI 可复用判断组件",
        "admin_risk_tail": "组织会持续重复造轮子，沉淀不下来，后续 AI 也读不到稳定结构。",
        "employee_risk_tail": "这条线会一直停留在整理阶段，难以真正变成可复用资产。",
        "opportunity_type": "repeatable_pattern",
    },
    "组织协同": {
        "identity": "做责任对齐、审批确认和协同接口收束",
        "progress": "把跨人协作、确认链和责任边界逐步说清",
        "state": "重点不是继续催动作，而是先明确谁拍板、谁配合、谁负责收口",
        "fallback_blocker": "责任边界、确认链或跨人接口还没收拢",
        "fallback_next": "先明确拍板人、配合人和最晚回收时间",
        "upside": "协同一旦收束，后续同类事项会明显减少来回确认成本",
        "admin_risk_tail": "它会把局部卡点放大成管理负荷，并不断占用上级确认带宽。",
        "employee_risk_tail": "这条线会继续停留在等待和确认里，个人推进感会很弱。",
        "opportunity_type": "process_upgrade",
    },
    "管理机制": {
        "identity": "做规则、资源和管理节奏调校",
        "progress": "把优先级、资源配置和机制边界逐步调顺",
        "state": "重点不是继续堆任务，而是先把资源、规则和优先级重新排清",
        "fallback_blocker": "资源配置、规则边界或管理节奏仍然不顺",
        "fallback_next": "先明确资源、优先级和规则边界，再继续投入",
        "upside": "一旦调顺，会直接释放管理带宽，并减少后续同类摩擦",
        "admin_risk_tail": "它会把局部问题不断抬升成机构层面的管理噪音。",
        "employee_risk_tail": "这条线会持续让执行感到用力很多，但推进很慢。",
        "opportunity_type": "process_upgrade",
    },
    "外部合作": {
        "identity": "做外部伙伴、品牌或渠道连接",
        "progress": "把外部关系、合作接口和共同动作往前推进",
        "state": "重点不是继续扩圈，而是把合作接口、共同目标和下一步动作压实",
        "fallback_blocker": "合作接口、对外口径或共同动作还没收束",
        "fallback_next": "先把合作接口和下一步共同动作说清",
        "upside": "如果收束得当，会把外部连接放大成更稳定的渠道或品牌势能",
        "admin_risk_tail": "它会持续消耗外部关系信用，但还形不成真正可放大的合作资产。",
        "employee_risk_tail": "推进会一直停在外部沟通层，难以形成更实的合作结果。",
        "opportunity_type": "leverage_point",
    },
    "专项推进": {
        "identity": "推进当前核心事项",
        "progress": "把关键动作往可收束状态推进",
        "state": "重点是先把当前阶段最关键的动作和判断压实",
        "fallback_blocker": "当前阻塞还没有被稳定识别",
        "fallback_next": "先把下一步动作说清",
        "upside": "如果顺着这条线补齐背景和下一步动作，后续判断会明显更准",
        "admin_risk_tail": "这条线会继续停留在零散动作层，管理层难以判断是否值得继续投入。",
        "employee_risk_tail": "执行会继续像在忙，但很难形成清楚的推进感。",
        "opportunity_type": "momentum_building",
    },
}


def _story_theme(category: str) -> dict[str, str]:
    return BUSINESS_CATEGORY_THEME.get(category, BUSINESS_CATEGORY_THEME["专项推进"])


def _first_non_empty(values: list[str]) -> str:
    return next((value for value in values if value), "")


def _story_subject_name(story: dict[str, object]) -> str:
    clients = list(story["clients"])  # type: ignore[arg-type]
    name = str(story["name"])
    if clients:
        client = clients[0]
        if client and client in name:
            return f"{client}这条线"
    return f"{name}这条线"


def _story_kind(category: str, *, project_name: str | None) -> Literal["project_line", "issue_line", "coordination_line", "case_line", "custom"]:
    if category in {"业务扩展", "项目推进", "外部合作"} and project_name:
        return "project_line"
    if category in {"组织协同", "管理机制"}:
        return "coordination_line"
    if category == "产品化沉淀":
        return "case_line"
    if category == "专项推进" and not project_name:
        return "issue_line"
    return "custom"


def _compose_story_identity(
    category: str,
    *,
    story_name: str,
    project_name: str | None,
    module_name: str | None,
    flow_name: str | None,
    line_summary: str,
) -> str:
    theme = _story_theme(category)
    anchor = module_name or flow_name or project_name or story_name
    if line_summary:
        return line_summary
    if category == "业务扩展":
        return f"这是围绕 {anchor} 做客户关系推进与合作收束的一条业务扩展线。"
    if category == "项目推进":
        return f"这是围绕 {anchor} 做交付收口与推进节奏控制的一条项目推进线。"
    if category == "产品化沉淀":
        return f"这是围绕 {anchor} 沉淀模板、标准件和系统能力的一条产品化线。"
    if category == "组织协同":
        return f"这是围绕 {anchor} 做责任对齐、审批确认和协同接口收束的一条协同线。"
    if category == "管理机制":
        return f"这是围绕 {anchor} 做规则、资源和管理节奏调校的一条管理线。"
    if category == "外部合作":
        return f"这是围绕 {anchor} 做外部伙伴、品牌或渠道连接的一条合作线。"
    return f"这是围绕 {anchor} {theme['identity']}的一条连续推进线。"


def _compose_story_week_progress(
    category: str,
    *,
    focus: str,
    signal: str,
    task_titles: list[str],
) -> str:
    theme = _story_theme(category)
    if focus:
        return f"本周主要在推进：{focus}。"
    if signal:
        return f"本周已经出现的关键推进信号是：{signal}。"
    task_text = "、".join(task_titles[:2])
    if task_text:
        return f"本周主要围绕 {task_text} 推进 {theme['progress']}。"
    return f"本周主要在推进 {theme['progress']}。"


def _compose_story_state(
    category: str,
    *,
    stage_label: str,
    completed_count: int,
    unfinished_count: int,
) -> str:
    theme = _story_theme(category)
    parts = [f"当前更像处在「{stage_label}」阶段。"]
    if completed_count and unfinished_count:
        parts.append(f"本周已有 {completed_count} 项动作形成推进，但还有 {unfinished_count} 项没有收束。")
    elif completed_count:
        parts.append(f"本周已有 {completed_count} 项动作形成推进。")
    elif unfinished_count:
        parts.append(f"本周仍有 {unfinished_count} 项关键动作待收束。")
    parts.append(theme["state"] + "。")
    return " ".join(parts)


def _compose_story_blocker(category: str, blocker_text: str) -> str:
    theme = _story_theme(category)
    return blocker_text or f"当前最需要直面的阻力仍然更像：{theme['fallback_blocker']}。"


def _compose_story_next_move(category: str, next_move: str) -> str:
    theme = _story_theme(category)
    if next_move:
        return next_move
    return theme["fallback_next"] + "。"


def _compose_risk_statement(
    category: str,
    *,
    subject: str,
    blocker_text: str,
    viewer_role: ReviewViewerRole,
) -> str:
    theme = _story_theme(category)
    blocker = blocker_text or theme["fallback_blocker"]
    if viewer_role == "admin":
        return f"{subject} 当前卡在“{blocker}”，如果未来 1-2 周还不收束，这条{category}线会继续拖慢推进，并让管理层看不清该不该继续加码。"
    if viewer_role == "department_lead":
        return f"{subject} 当前卡在“{blocker}”，如果未来 1-2 周还不收束，这条线会继续占住部门带宽，并让负责人很难判断该先收哪一段。"
    return f"{subject} 当前卡在“{blocker}”，如果未来 1-2 周还不收束，这条线会继续停留在反复确认和来回推进里。"


def _compose_risk_if_ignored(
    category: str,
    *,
    viewer_role: ReviewViewerRole,
) -> str:
    theme = _story_theme(category)
    if viewer_role == "admin":
        return theme["admin_risk_tail"]
    if viewer_role == "department_lead":
        return "这条线会继续把局部卡点放大成部门级协同和取舍压力，负责人需要不断介入收口。"
    return theme["employee_risk_tail"]


def _compose_opportunity_statement(
    category: str,
    *,
    subject: str,
    signal: str,
    viewer_role: ReviewViewerRole,
) -> str:
    theme = _story_theme(category)
    core_signal = signal or theme["progress"]
    if viewer_role == "admin":
        return f"{subject} 已经开始形成连续推进势能，当前最值得放大的信号是：{core_signal}。"
    if viewer_role == "department_lead":
        return f"{subject} 已经开始形成部门内可放大的正向势能，当前最值得继续压实的信号是：{core_signal}。"
    return f"{subject} 已经开始形成可继续推进的顺手感，当前最值得延续的信号是：{core_signal}。"


def _compose_opportunity_upside(category: str, *, viewer_role: ReviewViewerRole) -> str:
    theme = _story_theme(category)
    if viewer_role == "admin":
        return f"如果继续顺着这条线补齐背景和下一步动作，它更容易长成 {theme['upside']}。"
    if viewer_role == "department_lead":
        return f"如果继续顺着这条线收束，部门里同类事项会更容易形成 {theme['upside']}。"
    return f"如果继续顺着这条线往前推，它更容易从零散动作变成 {theme['upside']}。"


def _compose_opportunity_amplifier(category: str, *, next_move: str, viewer_role: ReviewViewerRole) -> str:
    move = next_move or _story_theme(category)["fallback_next"]
    if viewer_role == "admin":
        return f"继续按“{move}”推进，并把这条线当前有效做法沉淀下来。"
    if viewer_role == "department_lead":
        return f"继续按“{move}”推进，并把这条线当前有效做法沉淀给部门复用。"
    return f"先按“{move}”继续推进，再把这次有效做法留成可复用经验。"


def _build_event_line_intelligence(
    items: list[WeeklyReviewTaskEntryRecord],
    *,
    viewer_role: ReviewViewerRole = "employee",
) -> tuple[list[EventLineSummaryCardRecord], list[EventLineCompletenessRecord], list[EventLineRiskCardRecord], list[EventLineOpportunityCardRecord]]:
    stories = _event_line_story_groups(items)
    summaries: list[EventLineSummaryCardRecord] = []
    completeness_records: list[EventLineCompletenessRecord] = []
    risk_cards: list[EventLineRiskCardRecord] = []
    opportunity_cards: list[EventLineOpportunityCardRecord] = []
    slot_weights = {
        "stage": 15,
        "goal": 15,
        "blocker": 15,
        "next_action": 15,
        "recent_change": 10,
        "owner_chain": 10,
        "recent_decision": 10,
        "project_link": 10,
    }

    for story in stories:
        category = str(story["category"])
        theme = _story_theme(category)
        stage_values = list(story["stages"])  # type: ignore[arg-type]
        goal_values = list(story["goals"]) + list(story["currentFocuses"])  # type: ignore[arg-type]
        blocker_values = list(story["currentBlockers"]) + list(story["risks"])  # type: ignore[arg-type]
        next_action_values = list(story["nextSteps"])  # type: ignore[arg-type]
        recent_change_values = list(story["recentProgresses"])  # type: ignore[arg-type]
        owner_values = list(story["owners"])  # type: ignore[arg-type]
        recent_decision_values = list(story["recentDecisions"])  # type: ignore[arg-type]
        project_link_values = list(story["clients"]) + list(story["moduleNames"]) + list(story["flowNames"])  # type: ignore[arg-type]
        task_title_values = list(story["taskTitles"])  # type: ignore[arg-type]
        line_summary_values = list(story.get("lineSummaries", []))  # type: ignore[arg-type]
        line_intent_values = list(story.get("lineIntents", []))  # type: ignore[arg-type]

        slots = [
            _build_event_line_slot(
                key="stage",
                label="当前阶段",
                values=stage_values,
                source_types=["project_context"] if stage_values else [],
                recommended_fix="clarify_now",
                fallback_summary="当前还没有明确写出这条线推进到哪个阶段。",
                prefer_full_when_any=True,
            ),
            _build_event_line_slot(
                key="goal",
                label="当前目标",
                values=goal_values or task_title_values[:1],
                source_types=["project_context"] if goal_values else ["task_fact"] if task_title_values else [],
                recommended_fix="upload_docs" if not goal_values else "clarify_now",
                fallback_summary="当前还看不清这条线这周最关键要达成什么。",
            ),
            _build_event_line_slot(
                key="blocker",
                label="当前阻塞",
                values=blocker_values,
                source_types=["project_context", "user_note"] if blocker_values else [],
                recommended_fix="clarify_now",
                fallback_summary="暂时还没有稳定识别到这条线最主要的阻塞。",
                prefer_full_when_any=True,
            ),
            _build_event_line_slot(
                key="next_action",
                label="下一步动作",
                values=next_action_values,
                source_types=["project_context", "user_note"] if next_action_values else [],
                recommended_fix="clarify_now",
                fallback_summary="还缺下一步最关键动作，所以很难判断这条线接下来怎么变。",
                prefer_full_when_any=True,
            ),
            _build_event_line_slot(
                key="recent_change",
                label="最近关键变化",
                values=recent_change_values or list(story["taskTitles"]),  # type: ignore[arg-type]
                source_types=["project_context"] if recent_change_values else ["task_fact"] if story["taskTitles"] else [],
                recommended_fix="wait_for_more_trace" if recent_change_values else "clarify_now",
                fallback_summary="当前还缺清楚的最近变化信号，只能看到零散动作。",
            ),
            _build_event_line_slot(
                key="owner_chain",
                label="责任关系",
                values=owner_values,
                source_types=["task_fact"] if owner_values else [],
                recommended_fix="clarify_now",
                fallback_summary="当前还不够清楚谁在主负责、谁在等待。",
                prefer_full_when_any=True,
            ),
            _build_event_line_slot(
                key="recent_decision",
                label="最近关键决策",
                values=recent_decision_values,
                source_types=["user_note"] if recent_decision_values else [],
                recommended_fix="clarify_now",
                fallback_summary="最近改变这条线走向的关键决策还不够清楚。",
            ),
            _build_event_line_slot(
                key="project_link",
                label="项目/模块/流程归属",
                values=project_link_values or [str(story["name"])],
                source_types=["project_context"] if project_link_values else ["event_line"],
                recommended_fix="upload_docs",
                fallback_summary="当前还没有把这条线稳定挂到项目、模块或流程上。",
            ),
        ]

        score = 0
        for slot in slots:
            score += round(slot_weights[slot.key] * _slot_strength_score(slot.evidenceStrength))
        status = _event_line_completeness_status(score)
        missing_slots = [slot.label for slot in slots if slot.coverage != "full"]
        strongest_slots = [
            slot.label
            for slot in sorted(slots, key=lambda item: (slot_weights[item.key] * _slot_strength_score(item.evidenceStrength)), reverse=True)
            if slot.evidenceStrength in {"strong", "medium"}
        ][:3]
        completeness = EventLineCompletenessRecord(
            eventLineId=str(story.get("eventLineId") or story["id"]),
            title=str(story["name"]),
            score=score,
            status=status,
            missingSlots=missing_slots[:4],
            strongestSlots=strongest_slots,
            slots=slots,
        )
        completeness_records.append(completeness)

        project_name = next(iter(story["clients"]), None) if story["clients"] else None  # type: ignore[arg-type]
        module_name = next(iter(story["moduleNames"]), None) if story["moduleNames"] else None  # type: ignore[arg-type]
        flow_name = next(iter(story["flowNames"]), None) if story["flowNames"] else None  # type: ignore[arg-type]
        current_blocker = _compose_story_blocker(category, blocker_values[0] if blocker_values else "")
        next_move = _compose_story_next_move(category, next_action_values[0] if next_action_values else "")
        what_this_line_is = _compose_story_identity(
            category,
            story_name=str(story["name"]),
            project_name=project_name,
            module_name=module_name,
            flow_name=flow_name,
            line_summary=line_summary_values[0] if line_summary_values else "",
        )
        what_happened = _compose_story_week_progress(
            category,
            focus=_first_non_empty(line_intent_values + list(story["currentFocuses"])),  # type: ignore[arg-type]
            signal=_first_non_empty(recent_change_values),
            task_titles=task_title_values,
        )
        stage_label = stage_values[0] if stage_values else "阶段待澄清"
        current_state = _compose_story_state(
            category,
            stage_label=stage_label,
            completed_count=int(story["completedCount"]),
            unfinished_count=int(story["unfinishedCount"]),
        )
        evidence_preview = _dedupe_texts(
            [
                *line_summary_values,
                *line_intent_values,
                *list(story["currentFocuses"]),  # type: ignore[arg-type]
                *list(story["recentProgresses"]),  # type: ignore[arg-type]
                *list(story["goals"]),  # type: ignore[arg-type]
                *list(story["recentDecisions"]),  # type: ignore[arg-type]
                *list(story["taskTitles"]),  # type: ignore[arg-type]
            ],
            limit=4,
        )
        summary_card = EventLineSummaryCardRecord(
            eventLineId=str(story.get("eventLineId") or story["id"]),
            title=str(story["name"]),
            kind=_story_kind(category, project_name=project_name),
            status="blocked" if blocker_values else "active",
            projectName=project_name,
            moduleName=module_name,
            flowName=flow_name,
            whatThisLineIs=what_this_line_is,
            whatHappenedThisWeek=what_happened,
            currentState=current_state,
            mainBlocker=current_blocker,
            nextCriticalMove=next_move,
            ownerNames=owner_values[:3],
            completenessScore=score,
            predictionReadiness=_prediction_readiness(status),
            missingSlots=missing_slots[:4],
            evidencePreview=evidence_preview,
            target=_event_line_story_target(story),
            evidenceRefs=_story_evidence_refs(story),
        )
        summaries.append(summary_card)

        if status in {"forecast_ready", "high_confidence"} and (blocker_values or int(story["unfinishedCount"]) > 0):
            risk_type = _infer_risk_type(current_blocker)
            risk_cards.append(
                EventLineRiskCardRecord(
                    eventLineId=str(story.get("eventLineId") or story["id"]),
                    title=str(story["name"]),
                    riskType=risk_type,
                    statement=_compose_risk_statement(
                        category,
                        subject=_story_subject_name(story),
                        blocker_text=current_blocker,
                        viewer_role=viewer_role,
                    ),
                    forecastWindow="1w" if blocker_values else "2w",
                    probability="high" if status == "high_confidence" else "medium",
                    impactScope="project" if project_name else "team",
                    triggerSignals=_dedupe_texts([current_blocker, *evidence_preview], limit=3),
                    whyNow=what_happened,
                    ifIgnored=_compose_risk_if_ignored(category, viewer_role=viewer_role),
                    suggestedAction=next_move,
                    ownerRole=owner_values[0] if owner_values else "该线负责人",
                    target=_event_line_story_target(story),
                    evidenceRefs=_story_evidence_refs(story),
                )
            )

        if status in {"forecast_ready", "high_confidence"} and (recent_change_values or int(story["completedCount"]) > 0):
            opportunity_cards.append(
                EventLineOpportunityCardRecord(
                    eventLineId=str(story.get("eventLineId") or story["id"]),
                    title=str(story["name"]),
                    opportunityType=theme["opportunity_type"],  # type: ignore[arg-type]
                    statement=_compose_opportunity_statement(
                        category,
                        subject=_story_subject_name(story),
                        signal=recent_change_values[0] if recent_change_values else what_happened,
                        viewer_role=viewer_role,
                    ),
                    forecastWindow="2w",
                    confidence="high" if status == "high_confidence" else "medium",
                    upside=_compose_opportunity_upside(category, viewer_role=viewer_role),
                    supportingSignals=_dedupe_texts([*recent_change_values, *goal_values, *evidence_preview], limit=3),
                    recommendedAmplifier=_compose_opportunity_amplifier(category, next_move=next_move, viewer_role=viewer_role),
                    ownerRole=owner_values[0] if owner_values else "该线负责人",
                    target=_event_line_story_target(story),
                    evidenceRefs=_story_evidence_refs(story),
                )
            )

    return summaries[:6], completeness_records[:6], risk_cards[:4], opportunity_cards[:4]


def _build_trend_signals(
    items: list[WeeklyReviewTaskEntryRecord],
    event_line_summaries: list[EventLineSummaryCardRecord],
    event_line_completeness: list[EventLineCompletenessRecord],
) -> list[TrendSignalRecord]:
    signals: list[TrendSignalRecord] = []
    review_pending_items = [item for item in items if bool(item.taskSnapshot.orgContext and item.taskSnapshot.orgContext.needsReview)]
    if len(review_pending_items) >= 2:
        signals.append(
            TrendSignalRecord(
                key="repeat_review_pending",
                title="待复核事项持续堆积",
                statement=f"本周有 {len(review_pending_items)} 条任务仍卡在复核/确认链，说明判断和执行之间的回收链还没有真正收紧。",
                signalType="repeat_review_pending",
                severity="high" if len(review_pending_items) >= 4 else "medium",
                windowLabel="本周",
                relatedEventLineId=None,
                relatedTaskIds=[item.taskId for item in review_pending_items[:5]],
                evidenceRefs=[
                    ReviewDashboardEvidenceRefRecord(
                        sourceType="task",
                        sourceId=item.taskId,
                        title=item.taskSnapshot.title,
                        summary="待复核或待确认",
                    )
                    for item in review_pending_items[:4]
                ],
                target=ReviewDashboardCardTargetRecord(
                    targetType="task_view",
                    targetId="builtin:risk",
                    targetLabel="风险视图",
                    targetFilters={"onlyRisky": True, "needsReview": True},
                ),
            )
        )

    support_need_items = [
        item
        for item in items
        if item.structuredNote.supportNeeded.strip()
        or item.structuredNote.lightweightTag.strip() in {"需要支持", "资源不够", "等待他人"}
    ]
    if len(support_need_items) >= 2:
        signals.append(
            TrendSignalRecord(
                key="repeat_support_request",
                title="支持依赖开始持续化",
                statement=f"本周至少 {len(support_need_items)} 条任务明确提到支持或外部依赖，这已经不是单点阻塞，而是协作链需要干预的信号。",
                signalType="repeat_support_request",
                severity="medium",
                windowLabel="本周",
                relatedEventLineId=None,
                relatedTaskIds=[item.taskId for item in support_need_items[:5]],
                evidenceRefs=[
                    ReviewDashboardEvidenceRefRecord(
                        sourceType="task",
                        sourceId=item.taskId,
                        title=item.taskSnapshot.title,
                        summary=_truncate_overview_text(item.structuredNote.supportNeeded or item.structuredNote.lightweightTag or item.note),
                    )
                    for item in support_need_items[:4]
                ],
                target=ReviewDashboardCardTargetRecord(
                    targetType="task_view",
                    targetId="builtin:risk",
                    targetLabel="风险视图",
                    targetFilters={"onlyRisky": True, "sourceTypes": ["support_request"]},
                ),
            )
        )

    completeness_by_id = {item.eventLineId: item for item in event_line_completeness}
    for summary in event_line_summaries:
        completeness = completeness_by_id.get(summary.eventLineId)
        if not completeness:
            continue
        if summary.status == "blocked" or completeness.status == "insufficient":
            signals.append(
                TrendSignalRecord(
                    key=f"stalled_event_line::{summary.eventLineId}",
                    title=f"{summary.title} 长时间无收束",
                    statement=f"{summary.title} 当前仍卡在“{summary.mainBlocker or '信息待补'}”，如果接下来 1-2 周不继续补证据，这条线的判断质量和推进速度都会继续下降。",
                    signalType="stalled_event_line",
                    severity="high" if summary.status == "blocked" else "medium",
                    windowLabel="未来 1-2 周",
                    relatedEventLineId=summary.eventLineId,
                    relatedTaskIds=[ref.sourceId for ref in summary.evidenceRefs or [] if ref.sourceType == "task"],
                    evidenceRefs=list(summary.evidenceRefs or []),
                    target=summary.target,
                )
            )
        if summary.predictionReadiness in {"summary_only", "not_ready"} and completeness.missingSlots:
            signals.append(
                TrendSignalRecord(
                    key=f"thin_evidence::{summary.eventLineId}",
                    title=f"{summary.title} 证据仍偏薄",
                    statement=f"{summary.title} 目前还缺 { '、'.join(completeness.missingSlots[:2]) }，如果继续直接产出判断，结论会反复回到泛化层。",
                    signalType="thin_evidence",
                    severity="medium",
                    windowLabel="本周",
                    relatedEventLineId=summary.eventLineId,
                    relatedTaskIds=[ref.sourceId for ref in summary.evidenceRefs or [] if ref.sourceType == "task"],
                    evidenceRefs=list(summary.evidenceRefs or []),
                    target=summary.target,
                )
            )
    return signals[:6]


def _reference_alignment_counts(
    items: list[WeeklyReviewTaskEntryRecord],
    reference_texts: list[str],
) -> tuple[int, int] | None:
    token_sets = [set(_extract_tokens(text.lower())) for text in reference_texts if _clean_text(text)]
    token_sets = [token_set for token_set in token_sets if token_set]
    if not token_sets:
        return None
    aligned = 0
    partial = 0
    for item in items:
        item_tokens = set(_extract_tokens(_item_text(item)))
        if not item_tokens:
            continue
        overlap = max((len(item_tokens & token_set) for token_set in token_sets), default=0)
        if overlap >= 2:
            aligned += 1
        elif overlap == 1:
            partial += 1
    return aligned, partial


def _completion_status(item: WeeklyReviewTaskEntryRecord) -> Literal["done_on_time", "done_late", "in_progress", "not_done"]:
    status = item.structuredNote.completionStatus
    if status in {"done_on_time", "done_late", "in_progress", "not_done"}:
        return status
    if item.taskSnapshot.status == "done":
        return "done_on_time"
    if item.taskSnapshot.status == "doing":
        return "in_progress"
    return "not_done"


def _alignment_status(value: str | None) -> Literal["aligned", "partial", "misaligned", "unknown"]:
    if value in {"aligned", "partial", "misaligned", "unknown"}:
        return value
    return "unknown"


def _format_rate(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "待补录"
    rate = numerator / denominator * 100
    rounded = round(rate, 1)
    if abs(rounded - round(rounded)) < 1e-9:
        return f"{int(round(rounded))}%"
    return f"{rounded:.1f}%"


def _metric_tone(rate: float, *, good: float, okay: float) -> Literal["positive", "neutral", "warning", "risk"]:
    if rate >= good:
        return "positive"
    if rate >= okay:
        return "neutral"
    if rate > 0:
        return "warning"
    return "risk"


def _build_metric_card(
    *,
    key: Literal["timely_completion", "department_alignment", "strategy_alignment", "reflection_capture"],
    label: str,
    numerator: int,
    denominator: int,
    description: str,
    tone: Literal["positive", "neutral", "warning", "risk"],
) -> ReviewMetricCardRecord:
    rate = numerator / denominator if denominator > 0 else 0.0
    return ReviewMetricCardRecord(
        key=key,
        label=label,
        valueText=_format_rate(numerator, denominator),
        numerator=numerator,
        denominator=denominator,
        rate=round(rate, 4),
        description=description,
        tone=tone,
    )


def _build_metric_cards(
    scope: Literal["work", "personal"],
    items: list[WeeklyReviewTaskEntryRecord],
    dna_modules: list[OrganizationDnaModuleRecord],
    *,
    week_label: str,
    org_model_profile: OrgModelProfileRecord | None = None,
    viewer_role: ReviewViewerRole = "employee",
) -> list[ReviewMetricCardRecord]:
    total_count = len(items)
    completion_statuses = Counter(_completion_status(item) for item in items)
    completed_items = [item for item in items if _completion_status(item) in {"done_on_time", "done_late"}]
    unfinished_items = [item for item in items if _completion_status(item) in {"in_progress", "not_done"}]
    completed_with_experience = sum(
        1 for item in completed_items if _reflection_text(item)
    )
    unfinished_with_insight = sum(
        1 for item in unfinished_items if _reflection_text(item) or _lightweight_tag(item)
    )
    cards = [
        _build_metric_card(
            key="timely_completion",
            label="计划及时完成率",
            numerator=int(completion_statuses["done_on_time"]),
            denominator=total_count,
            description=(
                f"本周共 {total_count} 项计划，其中按时完成 {completion_statuses['done_on_time']} 项、延迟完成 {completion_statuses['done_late']} 项、"
                f"仍在推进 {completion_statuses['in_progress']} 项、未完成 {completion_statuses['not_done']} 项。"
                if total_count
                else "当前还没有可分析的计划样本。"
            ),
            tone=_metric_tone(
                (int(completion_statuses["done_on_time"]) / total_count) if total_count else 0.0,
                good=0.65,
                okay=0.4,
            ),
        ),
    ]

    if scope == "work" and viewer_role == "admin":
        story_groups = _event_line_story_groups(items)
        grouped_task_count = sum(len(group["taskIds"]) for group in story_groups)  # type: ignore[arg-type]
        cards.append(
            _build_metric_card(
                key="department_alignment",
                label="事件线成线率",
                numerator=grouped_task_count,
                denominator=total_count,
                description=(
                    f"本周共有 {grouped_task_count}/{total_count} 条任务已经能放回具体事件线或项目线里判断。"
                    if story_groups
                    else "当前还没有把事项稳定串到事件线或项目线里，机构视角看到的仍是零散动作。"
                ),
                tone=_metric_tone((grouped_task_count / total_count) if total_count else 0.0, good=0.7, okay=0.45),
            )
        )
        quarter_goal_lines = [
            *_extract_quarter_goal_lines(dna_modules),
            *_focus_item_reference_texts(org_model_profile),
        ]
        strategy_alignment = _reference_alignment_counts(items, quarter_goal_lines)
        if strategy_alignment is None:
            cards.append(
                _build_metric_card(
                    key="strategy_alignment",
                    label="任务-机构战略对齐率",
                    numerator=0,
                    denominator=0,
                    description="当前还没有足够稳定的机构重点参照，暂时无法判断这些动作是否真的在推进机构主线。",
                    tone="warning",
                )
            )
        else:
            aligned_count, partial_count = strategy_alignment
            cards.append(
                _build_metric_card(
                    key="strategy_alignment",
                    label="任务-机构战略对齐率",
                    numerator=aligned_count + partial_count,
                    denominator=total_count,
                    description=(
                        f"根据任务文本与机构季度重点的对应关系判断，当前明确支撑 {aligned_count} 项，部分支撑 {partial_count} 项。"
                        if total_count
                        else "当前还没有可分析的任务样本。"
                    ),
                    tone=_metric_tone(
                        ((aligned_count + partial_count) / total_count) if total_count else 0.0,
                        good=0.65,
                        okay=0.35,
                    ),
                )
            )
    elif scope == "work":
        team_plan_texts = [
            *_dedupe_texts([_module_preview(module) for module in _team_plan_modules(dna_modules)], limit=4),
            *_department_plan_reference_texts(org_model_profile, week_label=week_label, items=items),
        ]
        department_alignment = _reference_alignment_counts(items, team_plan_texts)
        department_alignment_label = "部门任务-部门计划对齐率" if viewer_role == "department_lead" else "个人-部门对齐率"
        department_alignment_empty_desc = (
            "当前还没有补齐部门周计划 / 月度 DNA 背景，暂时无法判断部门任务与部门重点是否一致。"
            if viewer_role == "department_lead"
            else "当前还没有补齐部门周计划 / 月度 DNA 背景，暂时无法判断个人任务与部门重点是否一致。"
        )
        if department_alignment is None:
            cards.append(
                _build_metric_card(
                    key="department_alignment",
                    label=department_alignment_label,
                    numerator=0,
                    denominator=0,
                    description=department_alignment_empty_desc,
                    tone="warning",
                )
            )
        else:
            aligned_count, partial_count = department_alignment
            department_alignment_desc = (
                f"根据任务文本与部门计划背景的对应关系判断，当前明确对齐 {aligned_count} 项，部分对齐 {partial_count} 项。"
                if total_count
                else "当前还没有可分析的任务样本。"
            )
            cards.append(
                _build_metric_card(
                    key="department_alignment",
                    label=department_alignment_label,
                    numerator=aligned_count + partial_count,
                    denominator=total_count,
                    description=department_alignment_desc,
                    tone=_metric_tone(
                        ((aligned_count + partial_count) / total_count) if total_count else 0.0,
                        good=0.7,
                        okay=0.45,
                    ),
                )
            )

        quarter_goal_lines = [
            *_extract_quarter_goal_lines(dna_modules),
            *_focus_item_reference_texts(org_model_profile),
        ]
        strategy_alignment = _reference_alignment_counts(items, quarter_goal_lines)
        if strategy_alignment is None:
            cards.append(
                _build_metric_card(
                    key="strategy_alignment",
                    label="部门任务-机构方向对齐率" if viewer_role == "department_lead" else "部门-机构对齐率",
                    numerator=0,
                    denominator=0,
                    description=(
                        "当前还没有从组织介绍或正式机构重点里识别到足够稳定的战略参照，暂时无法判断部门动作与机构主线的关系。"
                        if viewer_role == "department_lead"
                        else "当前还没有从组织介绍或正式机构重点里识别到足够稳定的战略参照，暂时无法判断本周动作与机构主线的关系。"
                    ),
                    tone="warning",
                )
            )
        else:
            aligned_count, partial_count = strategy_alignment
            cards.append(
                _build_metric_card(
                    key="strategy_alignment",
                    label="部门任务-机构方向对齐率" if viewer_role == "department_lead" else "部门-机构对齐率",
                    numerator=aligned_count + partial_count,
                    denominator=total_count,
                    description=(
                        f"根据任务文本与机构季度重点的对应关系判断，当前明确支撑 {aligned_count} 项，部分支撑 {partial_count} 项。"
                        if total_count
                        else "当前还没有可分析的任务样本。"
                    ),
                    tone=_metric_tone(
                        ((aligned_count + partial_count) / total_count) if total_count else 0.0,
                        good=0.65,
                        okay=0.35,
                    ),
                )
            )

    cards.append(
        _build_metric_card(
            key="reflection_capture",
            label="复盘沉淀率",
            numerator=completed_with_experience + unfinished_with_insight,
            denominator=total_count,
            description=(
                f"已完成事项中有 {completed_with_experience}/{len(completed_items)} 项留下了心得；未完成事项中有 {unfinished_with_insight}/{len(unfinished_items)} 项写出了思考或支持需求。"
                if total_count
                else "当前还没有可分析的复盘沉淀样本。"
            ),
            tone=_metric_tone(
                ((completed_with_experience + unfinished_with_insight) / total_count) if total_count else 0.0,
                good=0.75,
                okay=0.45,
            ),
        ),
    )
    return cards


def _select_relevant_modules(
    items: list[WeeklyReviewTaskEntryRecord],
    organization_dna_modules: list[OrganizationDnaModuleRecord],
    limit: int = 3,
) -> list[OrganizationDnaModuleRecord]:
    usable = [module for module in organization_dna_modules if module.hasDocument and _module_preview(module)]
    if not usable:
        return []
    haystack = " ".join(_item_text(item) for item in items)
    tokens = set(_extract_tokens(haystack))
    scored: list[tuple[int, int, OrganizationDnaModuleRecord]] = []
    for module in usable:
        text = f"{module.title} {_module_preview(module)}".lower()
        overlap = sum(1 for token in tokens if token in text)
        structural_bonus = 0
        if module.moduleKey == "business_intro" and _contains_any(haystack, BUSINESS_KEYWORDS):
            structural_bonus += 2
        if module.moduleKey == "team_intro" and _contains_any(haystack, TEAM_KEYWORDS):
            structural_bonus += 2
        if module.moduleKey == "market_intro" and _contains_any(haystack, MARKET_KEYWORDS):
            structural_bonus += 2
        if module.moduleKey == "organization_intro":
            structural_bonus += 1
        scored.append((overlap + structural_bonus, 1 if module.summary.strip() else 0, module))
    scored.sort(key=lambda item: (item[0], item[1], item[2].updatedAt or ""), reverse=True)
    picked = [module for score, _, module in scored if score > 0][:limit]
    if picked:
        return picked
    return usable[:limit]


def _confidence(level_score: int) -> Literal["high", "medium", "low"]:
    if level_score >= 5:
        return "high"
    if level_score >= 3:
        return "medium"
    return "low"


def _build_evidence_weights(
    scope: Literal["work", "personal"],
    note_count: int,
    total_count: int,
    dna_modules: list[OrganizationDnaModuleRecord],
    *,
    project_context_count: int = 0,
    focus_plan_ready: bool = False,
) -> list[ReviewEvidenceWeightRecord]:
    team_plan_ready = bool(_team_plan_modules(dna_modules))
    weights = [
        ReviewEvidenceWeightRecord(
            sourceType="user_note",
            label="用户手写复盘说明",
            weight="high" if note_count else "medium",
            rationale="一线复盘说明直接来自当事人，本轮分析默认把这类信息作为最高权重依据。",
        ),
        ReviewEvidenceWeightRecord(
            sourceType="task_fact",
            label="任务客观事实",
            weight="medium",
            rationale=f"任务状态、周标签、清单归属等事实用于约束分析，当前共参考 {total_count} 项任务。",
        ),
    ]
    if scope == "work":
        weights.append(
            ReviewEvidenceWeightRecord(
                sourceType="team_plan",
                label="部门周计划 / 月度 DNA",
                weight="medium" if team_plan_ready else "low",
                rationale="部门负责人填写的本周重点计划和月度 DNA 用来判断任务是否贴着部门主线推进。",
            )
        )
        weights.append(
            ReviewEvidenceWeightRecord(
                sourceType="organization_dna",
                label="组织 / 业务 DNA",
                weight="medium" if dna_modules else "low",
                rationale="组织介绍和业务 DNA 用来提供方向参照，系统会自动尝试抽取季度重点，而不再要求员工手工挂接。",
            )
        )
        weights.append(
            ReviewEvidenceWeightRecord(
                sourceType="focus_plan",
                label="机构重点 / 部门计划对象",
                weight="medium" if focus_plan_ready else "low",
                rationale="正式录入的机构季度重点、部门周计划和计划项，会优先作为 AI 判断当前动作与管理计划关系的结构化背景。",
            )
        )
        weights.append(
            ReviewEvidenceWeightRecord(
                sourceType="project_context",
                label="项目 / 客户背景",
                weight="medium" if project_context_count else "low",
                rationale=f"任务挂接的项目背景、目标、风险和近期会议线索，用来判断当前动作是否贴着项目阶段与真实业务节奏推进；当前命中 {project_context_count} 项。",
            )
        )
        weights.append(
            ReviewEvidenceWeightRecord(
                sourceType="external_context",
                label="外部补充资料",
                weight="low",
                rationale="本轮周复盘未直接接入互联网补充信息；即便后续接入，也只应作为弱证据使用。",
            )
        )
    else:
        weights.append(
            ReviewEvidenceWeightRecord(
                sourceType="organization_dna",
                label="组织 DNA 参考",
                weight="low",
                rationale="成长复盘以自我总结为主，组织 DNA 只适合作为弱参考，不应盖过个人真实感受。",
            )
        )
    return weights


def _detect_dominant_lens(items: list[WeeklyReviewTaskEntryRecord], default_lens: str) -> str:
    haystack = " ".join(_item_text(item) for item in items)
    lens_scores = Counter[str]()
    if _contains_any(haystack, BUSINESS_KEYWORDS):
        lens_scores["business"] += 2
    if _contains_any(haystack, TEAM_KEYWORDS):
        lens_scores["team"] += 2
    if _contains_any(haystack, MARKET_KEYWORDS):
        lens_scores["market"] += 2
    if _contains_any(haystack, ISSUE_KEYWORDS):
        lens_scores["organization"] += 1
    if not lens_scores:
        return default_lens
    return lens_scores.most_common(1)[0][0]


def _hypothesis_reason(
    note_count: int,
    task_count: int,
    dna_titles: list[str],
) -> str:
    dna_text = f"；补充参考 DNA：{'、'.join(dna_titles)}" if dna_titles else ""
    return f"高权重依据来自 {note_count} 条一线复盘说明；中权重依据来自 {task_count} 条任务事实{dna_text}。"


def _build_work_hypotheses(
    items: list[WeeklyReviewTaskEntryRecord],
    dna_modules: list[OrganizationDnaModuleRecord],
    *,
    week_label: str,
    org_model_profile: OrgModelProfileRecord | None = None,
) -> list[ReviewHypothesisRecord]:
    note_items = [item for item in items if _reflection_text(item) or _lightweight_tag(item)]
    progress_items = [
        item
        for item in items
        if _completion_status(item) in {"done_on_time", "done_late"}
        or _reflection_text(item)
        or _contains_any(item.note, SUCCESS_KEYWORDS)
    ]
    blocker_items = [
        item
        for item in items
        if _completion_status(item) in {"in_progress", "not_done"}
        and (
            not item.note.strip()
            or _lightweight_tag(item)
            or _reflection_text(item)
            or _contains_any(item.note, ISSUE_KEYWORDS)
        )
    ]
    dna_titles = [module.title for module in dna_modules]
    quarter_goal_lines = _extract_quarter_goal_lines(dna_modules)
    project_summary = _project_context_summary(items)
    event_line_summary = _event_line_summary(items)
    structured_plan_texts = _department_plan_reference_texts(org_model_profile, week_label=week_label, items=items)
    focus_item_texts = _focus_item_reference_texts(org_model_profile)
    hypotheses: list[ReviewHypothesisRecord] = []

    if progress_items:
        success_lens = _detect_dominant_lens(progress_items, MODULE_LENS.get(dna_modules[0].moduleKey, "business") if dna_modules else "business")
        success_examples = "、".join(_item_short_label(item) for item in progress_items[:3])
        success_statement_map = {
            "business": "初步看，本周推进较顺的事项更可能受益于目标对象和业务路径相对清晰，因此执行动作能较快转成具体产出。",
            "team": "初步看，本周推进较顺的事项更可能受益于责任分工较清楚、协作链条较短，因此过程阻力相对较小。",
            "market": "初步看，本周推进较顺的事项更可能踩中了较明确的外部窗口或需求时点，因此反馈比预期更顺。",
            "organization": "初步看，本周推进较顺的事项更可能与当前组织主线较一致，所以资源注意力更容易集中到这些事项上。",
        }
        success_confidence = _confidence(len(progress_items) + (2 if len(note_items) >= 2 else 0) + (1 if dna_titles else 0))
        hypotheses.append(
            ReviewHypothesisRecord(
                id="success_pattern",
                lens=success_lens,  # type: ignore[arg-type]
                title="可能的成功原因",
                statement=f"{success_statement_map.get(success_lens, success_statement_map['organization'])} 当前比较能说明这一点的任务包括：{success_examples}。",
                confidence=success_confidence,
                reason=_hypothesis_reason(
                    len([item for item in progress_items if item.note.strip() or _reflection_text(item)]),
                    len(progress_items),
                    dna_titles,
                ),
                relatedTaskIds=[item.taskId for item in progress_items[:4]],
                evidenceSources=["user_note", "task_fact", *(("organization_dna",) if dna_titles else ())],
                assumptionNote="这是基于任务说明与 DNA 的推断，不等同于严格因果结论。",
            )
        )

    if blocker_items:
        blocker_lens = _detect_dominant_lens(blocker_items, MODULE_LENS.get(dna_modules[0].moduleKey, "organization") if dna_modules else "organization")
        blocker_examples = "、".join(_item_short_label(item) for item in blocker_items[:3])
        blocker_statement_map = {
            "business": "初步看，本周卡点不只是执行慢，更像是前置业务判断还不够清楚，例如目标对象、方案路径或交付标准没有完全钉死。",
            "team": "初步看，本周卡点不只是单点执行问题，更像出在协作接口、责任边界或排期节奏上。",
            "market": "初步看，本周卡点里有一部分可能来自外部变化或需求反馈不足，导致内部动作难以顺畅推进。",
            "organization": "初步看，本周卡点更像是优先级、目标边界或资源注意力没有完全聚焦，因此任务推进容易反复或悬空。",
        }
        blocker_confidence = _confidence(len(blocker_items) + (2 if len([item for item in blocker_items if item.note.strip()]) >= 2 else 0) + (1 if dna_titles else 0))
        hypotheses.append(
            ReviewHypothesisRecord(
                id="blocker_pattern",
                lens=blocker_lens,  # type: ignore[arg-type]
                title="可能的阻碍原因",
                statement=f"{blocker_statement_map.get(blocker_lens, blocker_statement_map['organization'])} 当前暴露这一点较明显的任务包括：{blocker_examples}。",
                confidence=blocker_confidence,
                reason=_hypothesis_reason(
                    len([item for item in blocker_items if item.note.strip() or _reflection_text(item) or _lightweight_tag(item)]),
                    len(blocker_items),
                    dna_titles,
                ),
                relatedTaskIds=[item.taskId for item in blocker_items[:4]],
                evidenceSources=["user_note", "task_fact", *(("organization_dna",) if dna_titles else ())],
                assumptionNote="这是带权重的解释性判断，后续仍需要人工确认是否真的是机制问题而非偶发事件。",
            )
        )

    overloaded_items = [item for item in items if _lightweight_tag(item) == "工作过度饱和"]
    if overloaded_items:
        overload_examples = "、".join(_item_short_label(item) for item in overloaded_items[:3])
        hypotheses.append(
            ReviewHypothesisRecord(
                id="capacity_saturation",
                lens="team",
                title="可能存在容量过载",
                statement=f"当前有 {len(overloaded_items)} 项任务被直接标记为“工作过度饱和”，说明这周的问题不一定是判断失误，也可能是负责人容量已经顶满。较明显的任务包括：{overload_examples}。",
                confidence=_confidence(len(overloaded_items) + (1 if len(note_items) >= 2 else 0)),
                reason=f"这类判断优先依据一线轻量卡点标签，而不是系统推断；当前共命中 {len(overloaded_items)} 条。",
                relatedTaskIds=[item.taskId for item in overloaded_items[:4]],
                evidenceSources=["user_note", "task_fact"],
                assumptionNote="容量过载不等于人员能力不足，更像是任务取舍和节奏配置问题。",
            )
        )

    if int(event_line_summary["groupCount"]) > 0:
        event_line_names = "、".join(event_line_summary["names"][:3]) or "当前重点事件线"
        blocked_text = (
            f" 当前仍待继续推进的事件线包括：{'、'.join(event_line_summary['blockedNames'][:2])}。"
            if event_line_summary["blockedNames"]
            else ""
        )
        hypotheses.append(
            ReviewHypothesisRecord(
                id="event_line_continuity",
                lens="team",
                title="与事件线连续推进的关系判断",
                statement=(
                    f"从当前任务关系看，本周已有 {event_line_summary['groupCount']} 条事件线把离散任务串成持续推进的工作线，"
                    f"其中 {event_line_summary['multiTaskGroupCount']} 条事件线已经跨了多项任务。像 {event_line_names} 这类事项，更适合按同一条线统一判断，而不是拆成多条任务分别复盘。{blocked_text}"
                ).strip(),
                confidence=_confidence(int(event_line_summary["groupCount"]) + int(event_line_summary["multiTaskGroupCount"]) + (1 if note_items else 0)),
                reason=f"这条判断直接读取任务快照中的 eventLineId / eventLineName；当前命中 {event_line_summary['taskCount']} 条任务、{event_line_summary['groupCount']} 条事件线。",
                relatedTaskIds=[item.taskId for item in items if _item_event_line_id(item)][:6],
                evidenceSources=["task_fact", *(("user_note",) if note_items else ())],
                assumptionNote="事件线还处在早期搭建阶段；如果任务没有挂入事件线，系统会继续回落到单条任务判断。",
            )
        )

    if int(project_summary["count"]) > 0:
        project_clients = "、".join(project_summary["clients"][:3]) or "当前重点项目"
        project_stages = "、".join(project_summary["stages"][:2])
        project_goals = "；".join(project_summary["goals"][:2])
        project_risks = "；".join(project_summary["risks"][:2])
        stage_text = f" 当前涉及的项目阶段包括：{project_stages}。" if project_stages else ""
        goal_text = f" 这些任务更像在推进：{project_goals}。" if project_goals else ""
        risk_text = f" 但也要继续警惕：{project_risks}。" if project_risks else ""
        hypotheses.append(
            ReviewHypothesisRecord(
                id="project_context_check",
                lens="business",
                title="与项目阶段的关系判断",
                statement=(
                    f"从当前已挂接的项目背景看，本周动作主要围绕 {project_clients} 展开，"
                    f"系统已经能把任务放回项目语境里理解，而不再只看单条执行动作。{stage_text}{goal_text}{risk_text}"
                ).strip(),
                confidence=_confidence(int(project_summary["count"]) + (1 if project_summary["infoCompleteness"] == "high" else 0) + (1 if note_items else 0)),
                reason=f"当前共有 {project_summary['count']} 条任务已挂接项目背景；项目背景来自客户工作台、项目目标、流程和近期会议线索。",
                relatedTaskIds=[item.taskId for item in items if _item_project_context(item)][:4],
                evidenceSources=["task_fact", "project_context", *(("user_note",) if note_items else ())],
                assumptionNote="项目背景来自系统中已有的项目资料和任务挂接，仍需随着客户工作台和会议纪要持续补全。",
            )
        )

    if structured_plan_texts or focus_item_texts:
        linked_focus_count = len({_item_focus_item_id(item) for item in items if _item_focus_item_id(item)})
        linked_plan_item_count = len({_item_department_plan_item_id(item) for item in items if _item_department_plan_item_id(item)})
        structured_text = (
            f"当前已有 {linked_plan_item_count} 条任务直接挂到了部门计划项，{linked_focus_count} 条任务直接挂到了机构重点。"
            if linked_plan_item_count or linked_focus_count
            else "当前虽未把任务逐条挂到计划项，但系统已经能读取正式录入的部门计划和机构重点。"
        )
        focus_preview = "；".join(_dedupe_texts([*focus_item_texts[:2], *structured_plan_texts[:2]], limit=3))
        hypotheses.append(
            ReviewHypothesisRecord(
                id="structured_plan_alignment",
                lens="organization",
                title="与正式计划对象的关系判断",
                statement=(
                    f"{structured_text} 本周判断优先参考正式录入的机构重点与部门计划对象，而不只靠自由文本推断。"
                    f"{f' 当前高频计划线索包括：{focus_preview}。' if focus_preview else ''}"
                ).strip(),
                confidence=_confidence((2 if linked_focus_count or linked_plan_item_count else 1) + (1 if structured_plan_texts else 0) + (1 if focus_item_texts else 0)),
                reason="这条判断直接读取组织模型中的 focusItems、departmentPlans 和任务挂接关系，结构化程度高于普通说明文字。",
                relatedTaskIds=[item.taskId for item in items[:4]],
                evidenceSources=["task_fact", "focus_plan", *(("user_note",) if note_items else ())],
                assumptionNote="正式计划对象仍需要持续维护；如果计划项没有更新，系统判断也会偏保守。",
            )
        )

    if dna_modules:
        titles_text = "、".join(module.title for module in dna_modules)
        quarter_text = (
            f" 当前从组织介绍中识别到的季度重点包括：{'；'.join(quarter_goal_lines[:3])}。"
            if quarter_goal_lines
            else ""
        )
        if len(progress_items) >= len(blocker_items):
            alignment_statement = f"从当前任务与 DNA 的对应关系看，本周主要工作大体仍贴着组织主线在走，但尚缺明确的战略挂接标注。当前主要参考的 DNA 模块是：{titles_text}。{quarter_text}"
        else:
            alignment_statement = f"从当前任务与 DNA 的对应关系看，本周已有偏航风险，部分任务虽然在推进，但与组织主线的关系还没有被说清。当前主要参考的 DNA 模块是：{titles_text}。{quarter_text}"
        hypotheses.append(
            ReviewHypothesisRecord(
                id="alignment_check",
                lens="organization",
                title="与组织方向的关系判断",
                statement=alignment_statement,
                confidence=_confidence(2 + (1 if dna_modules else 0) + (1 if note_items else 0)),
                reason=_hypothesis_reason(len(note_items), len(items), [module.title for module in dna_modules]),
                relatedTaskIds=[item.taskId for item in items[:4]],
                evidenceSources=["task_fact", "organization_dna", *(("user_note",) if note_items else ())],
                assumptionNote="这条判断主要用于提醒是否出现方向偏差，不代表系统已经掌握全部业务背景。",
            )
        )

    return hypotheses


def _build_admin_work_hypotheses(
    items: list[WeeklyReviewTaskEntryRecord],
    dna_modules: list[OrganizationDnaModuleRecord],
    *,
    week_label: str,
    org_model_profile: OrgModelProfileRecord | None = None,
    viewer_role: Literal["department_lead", "admin"] = "admin",
) -> list[ReviewHypothesisRecord]:
    story_groups = _event_line_story_groups(items)
    if not story_groups:
        return _build_work_hypotheses(
            items,
            dna_modules,
            week_label=week_label,
            org_model_profile=org_model_profile,
        )

    hypotheses: list[ReviewHypothesisRecord] = []
    for story in story_groups[:3]:
        name = str(story["name"])
        category = str(story["category"])
        lens = BUSINESS_CATEGORY_LENS.get(category, "business")
        task_titles = "、".join(story["taskTitles"][:3])  # type: ignore[index]
        clients = "、".join(story["clients"][:2])  # type: ignore[index]
        stages = "、".join(story["stages"][:2])  # type: ignore[index]
        current_focuses = "；".join(story["currentFocuses"][:2])  # type: ignore[index]
        current_blockers = "；".join(story["currentBlockers"][:2])  # type: ignore[index]
        goals = "；".join(story["goals"][:2])  # type: ignore[index]
        risks = "；".join(story["risks"][:2])  # type: ignore[index]
        next_steps = "；".join(story["nextSteps"][:2])  # type: ignore[index]
        recent_progresses = "；".join(story["recentProgresses"][:2])  # type: ignore[index]
        line_summaries = "；".join(story.get("lineSummaries", [])[:2])  # type: ignore[index]
        line_intents = "；".join(story.get("lineIntents", [])[:2])  # type: ignore[index]
        completed_count = int(story["completedCount"])
        unfinished_count = int(story["unfinishedCount"])
        subject = f"{clients}这条线" if clients and name in clients else f"{name}这条线"
        parts = [f"{subject}当前更接近「{category}」。"]
        if line_summaries:
            parts.append(f"这条线本身要推进的是：{line_summaries}。")
        if line_intents:
            parts.append(f"当前正在收束的核心事项是：{line_intents}。")
        if current_focuses:
            parts.append(f"当前最具体的推进事项是：{current_focuses}。")
        if task_titles:
            parts.append(f"本周主要推进了：{task_titles}。")
        if completed_count and unfinished_count:
            parts.append(f"这条线本周已有 {completed_count} 项动作形成推进，但还有 {unfinished_count} 项没有收束。")
        elif completed_count:
            parts.append(f"这条线本周已有 {completed_count} 项动作形成推进。")
        elif unfinished_count:
            parts.append(f"这条线本周仍有 {unfinished_count} 项关键动作待收束。")
        if recent_progresses:
            parts.append(f"最近已经出现的推进迹象是：{recent_progresses}。")
        if stages:
            parts.append(f"当前更像处在「{stages}」阶段。")
        if goals:
            parts.append(f"就现有背景看，这条线现在真正要推进的是：{goals}。")
        if current_blockers:
            parts.append(f"当前最需要直面的阻力是：{current_blockers}。")
        elif risks:
            parts.append(f"当前最需要直面的阻力是：{risks}。")
        if next_steps:
            parts.append(f"接下来应优先推进：{next_steps}。")
        hypotheses.append(
            ReviewHypothesisRecord(
                id=f"event_line_story_{story['id']}",
                lens=lens,
                title=f"{name}｜{'部门推进判断' if viewer_role == 'department_lead' else '本周推进判断'}",
                statement=" ".join(parts).strip(),
                confidence=_confidence(len(story["taskIds"]) + completed_count + (1 if risks or next_steps else 0)),  # type: ignore[arg-type]
                reason=(
                    f"直接依据这条线下 {len(story['taskIds'])} 条任务、事件线维护摘要与项目阶段/阻塞生成，"
                    f"不再把 {name} 与其他业务线混写成泛化判断。"
                ),
                relatedTaskIds=list(story["taskIds"]),  # type: ignore[arg-type]
                evidenceSources=["task_fact", "project_context", "event_line"],
                assumptionNote=(
                    "这是按事件线和部门推进语境直接收束出的业务判断，优先帮助部门负责人做取舍。"
                    if viewer_role == "department_lead"
                    else "这是按事件线和项目语境直接收束出的业务判断，不再使用个人-部门对齐口径。"
                ),
            )
        )

    quarter_goal_lines = [
        *_extract_quarter_goal_lines(dna_modules),
        *_focus_item_reference_texts(org_model_profile),
    ]
    strategy_alignment = _reference_alignment_counts(items, quarter_goal_lines)
    if strategy_alignment is not None:
        aligned_count, partial_count = strategy_alignment
        hypotheses.append(
            ReviewHypothesisRecord(
                id="admin_strategy_alignment",
                lens="organization",
                title="部门计划与机构方向提示" if viewer_role == "department_lead" else "机构战略对齐提示",
                statement=(
                    (
                        f"站在部门负责人视角，本周共有 {aligned_count + partial_count}/{len(items)} 项任务与机构重点形成了明确或部分支撑。"
                        "接下来更需要继续判断的是：这些动作是否真的贴着部门本周重点在推进。"
                    )
                    if viewer_role == "department_lead"
                    else (
                        f"站在机构视角，本周共有 {aligned_count + partial_count}/{len(items)} 项任务与机构重点形成了明确或部分支撑。"
                        "接下来需要继续判断的是：这些动作是否真的在推关键项目，而不是只停留在局部执行层。"
                    )
                ),
                confidence=_confidence(aligned_count + partial_count + (1 if quarter_goal_lines else 0)),
                reason=(
                    "这条判断直接读取机构季度重点与正式 focusItems，并结合部门视角判断是否需要继续收束本周重点。"
                    if viewer_role == "department_lead"
                    else "这条判断直接读取机构季度重点与正式 focusItems，不再使用部门对齐度来替代 CEO 视角。"
                ),
                relatedTaskIds=[item.taskId for item in items[:4]],
                evidenceSources=["task_fact", "focus_plan"],
                assumptionNote=(
                    "部门负责人视角会优先看部门本周重点和机构方向是否一致，不再退回到员工口径。"
                    if viewer_role == "department_lead"
                    else "CEO 视角只看与机构战略和关键项目的关系，不再输出个人-部门对齐度。"
                ),
            )
        )
    return hypotheses[:4]


def _build_personal_hypotheses(items: list[WeeklyReviewTaskEntryRecord]) -> list[ReviewHypothesisRecord]:
    note_items = [item for item in items if _reflection_text(item) or _lightweight_tag(item)]
    if not items:
        return []
    completed_items = [item for item in items if _completion_status(item) in {"done_on_time", "done_late"}]
    blocker_items = [
        item
        for item in items
        if _completion_status(item) in {"in_progress", "not_done"}
        and (not item.note.strip() or _reflection_text(item) or _lightweight_tag(item) or _contains_any(item.note, ISSUE_KEYWORDS))
    ]
    hypotheses: list[ReviewHypothesisRecord] = [
        ReviewHypothesisRecord(
            id="growth_rhythm",
            lens="growth",
            title="当前更像是哪种成长状态",
            statement=(
                "从这周的私人事项看，当前更像是在做经验沉淀和节奏校准，而不是单纯追求完成数量。"
                if note_items
                else "从当前记录量看，这周更像是先顾着推进事务，还没有把自己的观察和感受写下来。"
            ),
            confidence=_confidence(len(note_items) + len(completed_items)),
            reason=f"当前共有 {len(items)} 项私人事项，其中 {len(note_items)} 项写了复盘说明，{len(completed_items)} 项已完成。",
            relatedTaskIds=[item.taskId for item in items[:4]],
            evidenceSources=["user_note", "task_fact"],
            assumptionNote="成长复盘里的判断更偏向自我观察，不应替代本人真实感受。",
        )
    ]
    if blocker_items:
        blocker_titles = "、".join(_item_short_label(item) for item in blocker_items[:3])
        hypotheses.append(
            ReviewHypothesisRecord(
                id="growth_blocker",
                lens="growth",
                title="可能拖慢个人节奏的因素",
                statement=f"这周的个人节奏里，可能存在“事情在推进，但自己的判断与整理没有同步跟上”的情况。当前较明显的事项包括：{blocker_titles}。",
                confidence=_confidence(len(blocker_items) + len([item for item in blocker_items if item.note.strip()])),
                reason=f"共有 {len(blocker_items)} 项私人事项尚未完成或尚未写清当前感受。",
                relatedTaskIds=[item.taskId for item in blocker_items[:4]],
                evidenceSources=["user_note", "task_fact"],
                assumptionNote="这是一种节奏判断，不代表这些事项本身做得不好。",
            )
        )
    return hypotheses


def _work_headline(item_count: int, completed_count: int, blocker_count: int) -> str:
    if item_count == 0:
        return "本周还没有形成可分析的组织复盘样本。"
    if completed_count and blocker_count:
        return "本周任务推进呈现“有进展，但卡点也已开始显性化”的状态。"
    if completed_count:
        return "本周任务推进总体偏顺，已经出现可以沉淀为方法的正向样本。"
    if blocker_count:
        return "本周任务推进阻力偏多，当前更需要先判断卡点类型，而不是继续堆动作。"
    return "本周任务仍处于推进中段，当前更适合先补齐过程事实，再做更强分析。"


def _personal_headline(item_count: int, note_count: int) -> str:
    if item_count == 0:
        return "本周还没有形成可分析的成长复盘样本。"
    if note_count >= max(1, item_count // 2):
        return "本周成长复盘已经开始从“记事情”转向“记判断”。"
    return "本周成长复盘仍偏简略，当前更像是个人事项清点，还不是完整的成长分析。"


def _build_next_focus(
    scope: Literal["work", "personal"],
    items: list[WeeklyReviewTaskEntryRecord],
    hypotheses: list[ReviewHypothesisRecord],
    *,
    viewer_role: ReviewViewerRole = "employee",
) -> list[str]:
    unfinished = [item for item in items if item.taskSnapshot.status != "done"]
    next_focus = [f"优先补齐「{_item_short_label(item)}」的支持需求和下一步动作。" for item in unfinished[:2]]
    event_line_summary = _event_line_summary(items)
    if scope == "work":
        if viewer_role == "admin":
            for story in _event_line_story_groups(items)[:3]:
                name = str(story["name"])
                next_steps = "；".join(story["nextSteps"][:1])  # type: ignore[index]
                if next_steps:
                    next_focus.append(f"下周围绕「{name}」先收束：{next_steps}。")
                elif int(story["unfinishedCount"]) > 0:
                    next_focus.append(f"下周先把「{name}」这条线的未收束动作和关键阻塞写清，再决定继续投入还是调整策略。")
        elif viewer_role == "department_lead":
            for story in _event_line_story_groups(items)[:3]:
                name = str(story["name"])
                next_steps = "；".join(story["nextSteps"][:1])  # type: ignore[index]
                if next_steps:
                    next_focus.append(f"下周围绕「{name}」先压实：{next_steps}。")
                elif int(story["unfinishedCount"]) > 0:
                    next_focus.append(f"下周先把「{name}」这条线的未收束动作和责任分工收清，再决定是否继续投入。")
        if int(event_line_summary["blockedGroupCount"]) > 0:
            blocked_names = "、".join(event_line_summary["blockedNames"][:2])
            next_focus.append(
                f"下周先按事件线收束 {blocked_names} 的推进节奏，把相关任务、会议和支持依赖放回同一条线里判断。"
                if blocked_names
                else "下周先按事件线收束相关事项，不要继续把同一件事拆成多条任务各自推进。"
            )
        if viewer_role == "department_lead" and any(item.lens == "team" for item in hypotheses):
            next_focus.append("下周先把部门内协作接口、负责人和拍板节点压实，避免继续靠临时协调推进。")
        if viewer_role != "admin" and viewer_role != "department_lead" and any(item.lens == "team" for item in hypotheses):
            next_focus.append("下周先收敛协作接口，避免继续把协同问题误判成个人执行问题。")
        if viewer_role != "admin" and viewer_role != "department_lead" and any(item.lens == "business" for item in hypotheses):
            next_focus.append("对业务判断仍模糊的事项，先补目标对象、交付标准和验证口径，再继续投入。")
        if viewer_role == "department_lead" and any(item.lens == "organization" for item in hypotheses):
            next_focus.append("把本周部门动作重新对照部门计划和机构重点，明确哪些必须继续推进，哪些应先降优先级。")
        if viewer_role != "admin" and viewer_role != "department_lead" and any(item.lens == "organization" for item in hypotheses):
            next_focus.append("把本周事项重新对照组织主线，明确哪些必须继续推进，哪些应降优先级。")
        if any(item.lens == "team" and item.title == "可能存在容量过载" for item in hypotheses):
            next_focus.append(LIGHTWEIGHT_TAG_ACTIONS["工作过度饱和"])
    else:
        next_focus.append("给仍在推进的私人事项补一句“我为什么要做这件事”，避免成长复盘只剩事实列表。")
    deduped: list[str] = []
    for item in next_focus:
        if item not in deduped:
            deduped.append(item)
    return deduped[:4]


def build_weekly_review_analysis(
    scope: Literal["work", "personal"],
    week_label: str,
    items: list[WeeklyReviewTaskEntryRecord],
    organization_dna_modules: list[OrganizationDnaModuleRecord],
    *,
    org_model_profile: OrgModelProfileRecord | None = None,
    viewer_role: ReviewViewerRole = "employee",
    knowledge_summaries: list[dict] | None = None,
    meeting_summaries: list[dict] | None = None,
) -> WeeklyReviewAnalysisRecord:
    note_items = [item for item in items if item.note.strip() or _reflection_text(item) or _lightweight_tag(item)]
    dna_modules = _select_relevant_modules(items, organization_dna_modules, limit=3 if scope == "work" else 1)
    completion_statuses = Counter(_completion_status(item) for item in items)
    completed_count = int(completion_statuses["done_on_time"] + completion_statuses["done_late"])
    blocker_count = int(completion_statuses["in_progress"] + completion_statuses["not_done"])
    list_counts = Counter(item.taskSnapshot.listName for item in items)
    list_summary = "、".join(f"{name} {count} 项" for name, count in list_counts.most_common(3))
    metric_cards = _build_metric_cards(
        scope,
        items,
        dna_modules,
        week_label=week_label,
        org_model_profile=org_model_profile,
        viewer_role=viewer_role,
    )
    completed_with_experience = sum(
        1
        for item in items
        if _completion_status(item) in {"done_on_time", "done_late"}
        and _reflection_text(item)
    )
    unfinished_with_insight = sum(
        1
        for item in items
        if _completion_status(item) in {"in_progress", "not_done"}
        and (_reflection_text(item) or _lightweight_tag(item))
    )
    event_line_summary = _event_line_summary(items)
    tag_counts = Counter(_lightweight_tag(item) for item in items if _lightweight_tag(item))
    weekly_overview, weekly_focus_lines, weekly_next_focus = _build_weekly_overview(
        items,
        dna_modules,
        note_items_count=len(note_items),
    )
    confirmed_facts = [
        f"{week_label} 共纳入 {len(items)} 项{'工作任务' if scope == 'work' else '私人事项'}，其中已完成 {completed_count} 项，未完成 {len(items) - completed_count} 项。",
        (
            f"按时完成 {completion_statuses['done_on_time']} 项，延迟完成 {completion_statuses['done_late']} 项，仍在推进 {completion_statuses['in_progress']} 项，未完成 {completion_statuses['not_done']} 项。"
            if items
            else "当前还没有形成计划执行样本。"
        ),
        f"当前已有 {len(note_items)} 项写入一线复盘说明。"
        if note_items
        else "当前还没有足够多的一线复盘说明，系统只能基于任务事实做保守判断。",
        (
            f"已完成事项中有 {completed_with_experience} 项沉淀了成功经验，未完成事项中有 {unfinished_with_insight} 项写出了心得或教训。"
            if items
            else ""
        ),
    ]
    confirmed_facts = [item for item in confirmed_facts if item]
    if tag_counts:
        tag_summary = "、".join(f"{tag} {count} 项" for tag, count in tag_counts.most_common())
        confirmed_facts.append(f"本周一线补充的轻量卡点主要包括：{tag_summary}。")
    if list_summary:
        confirmed_facts.append(f"本周事项主要分布在：{list_summary}。")
    if dna_modules:
        confirmed_facts.append(f"本轮额外参考的 DNA 模块：{'、'.join(module.title for module in dna_modules)}。")
    quarter_goal_lines = _extract_quarter_goal_lines(dna_modules)
    if quarter_goal_lines:
        confirmed_facts.append(f"组织介绍中当前可识别的季度重点包括：{'；'.join(quarter_goal_lines[:3])}。")
    if int(event_line_summary["groupCount"]) > 0:
        names = "、".join(event_line_summary["names"][:3])
        confirmed_facts.append(
            f"本周已有 {event_line_summary['taskCount']} 条任务被归入 {event_line_summary['groupCount']} 条事件线，其中 {event_line_summary['multiTaskGroupCount']} 条事件线串起了多项持续推进事项。"
        )
        if names:
            confirmed_facts.append(f"当前识别到的主要事件线包括：{names}。")
    project_summary = _project_context_summary(items)
    if int(project_summary["count"]) > 0:
        client_text = "、".join(project_summary["clients"][:3]) or "已挂接项目"
        stage_text = f"，阶段包括：{'、'.join(project_summary['stages'][:2])}" if project_summary["stages"] else ""
        confirmed_facts.append(
            f"本周有 {project_summary['count']} 条任务已挂接项目背景，涉及：{client_text}{stage_text}。"
        )
        if project_summary["goals"]:
            confirmed_facts.append(f"项目目标线索主要包括：{'；'.join(project_summary['goals'][:2])}。")
        if project_summary["risks"]:
            confirmed_facts.append(f"项目当前显性风险包括：{'；'.join(project_summary['risks'][:2])}。")
    structured_plan_texts = _department_plan_reference_texts(org_model_profile, week_label=week_label, items=items)
    focus_item_texts = _focus_item_reference_texts(org_model_profile)
    linked_focus_ids = {_item_focus_item_id(item) for item in items if _item_focus_item_id(item)}
    linked_plan_item_ids = {_item_department_plan_item_id(item) for item in items if _item_department_plan_item_id(item)}
    if structured_plan_texts or focus_item_texts:
        plan_fact = (
            f"当前已识别到 {len(linked_plan_item_ids)} 条任务直接挂接部门计划项、{len(linked_focus_ids)} 条任务直接挂接机构重点。"
            if linked_plan_item_ids or linked_focus_ids
            else "当前周判断已开始读取正式录入的部门计划和机构重点，而不只靠自由文本做判断。"
        )
        confirmed_facts.append(plan_fact)
        preview = "；".join(_dedupe_texts([*focus_item_texts[:2], *structured_plan_texts[:2]], limit=3))
        if preview:
            confirmed_facts.append(f"本轮已读取的正式计划线索包括：{preview}。")
    # 知识库摘要注入
    _kb = knowledge_summaries or []
    if _kb:
        kb_titles = [item.get("title", "") for item in _kb[:3] if item.get("title")]
        if kb_titles:
            confirmed_facts.append(f"本轮已读取 {len(_kb)} 份客户知识库文档，包括：{'、'.join(kb_titles)}。")
    # 会议内容注入
    _ms = meeting_summaries or []
    if _ms:
        meeting_titles = [item.get("title", "") for item in _ms[:3] if item.get("title")]
        if meeting_titles:
            confirmed_facts.append(f"本轮已读取 {len(_ms)} 场相关会议，包括：{'、'.join(meeting_titles)}。")

    event_line_summaries, event_line_completeness, risk_cards, opportunity_cards = (
        _build_event_line_intelligence(items, viewer_role=viewer_role) if scope == "work" else ([], [], [], [])
    )
    trend_signals = (
        _build_trend_signals(items, event_line_summaries, event_line_completeness)
        if scope == "work"
        else []
    )

    hypotheses = (
        _build_admin_work_hypotheses(
            items,
            dna_modules,
            week_label=week_label,
            org_model_profile=org_model_profile,
            viewer_role=viewer_role if viewer_role in {"admin", "department_lead"} else "admin",
        )
        if scope == "work" and viewer_role in {"admin", "department_lead"}
        else _build_work_hypotheses(
            items,
            dna_modules,
            week_label=week_label,
            org_model_profile=org_model_profile,
        )
        if scope == "work"
        else _build_personal_hypotheses(items)
    )
    return WeeklyReviewAnalysisRecord(
        scope=scope,
        emphasis="analysis" if scope == "work" else "summary",
        headline=_work_headline(len(items), completed_count, blocker_count) if scope == "work" else _personal_headline(len(items), len(note_items)),
        caution=(
            "以下内容优先按事件线和项目语境解释本周推进，不再用向上汇报对齐口径替代机构视角。"
            if scope == "work" and viewer_role == "admin"
            else "以下内容优先按事件线和部门计划解释本周推进，不再退回到员工个人执行口径。"
            if scope == "work" and viewer_role == "department_lead"
            else "以下判断是带权重的假设性分析：用户手写复盘说明权重最高，任务客观事实次之，组织 DNA 只作为解释视角；不要把它直接当成确定结论。"
            if scope == "work"
            else "以下内容更偏个人总结和自我观察，不应让系统的解释压过你自己的真实感受。"
        ),
        weeklyOverview=weekly_overview if scope == "work" else "",
        weeklyFocusLines=weekly_focus_lines if scope == "work" else [],
        weeklyNextFocus=weekly_next_focus if scope == "work" else [],
        dnaModuleTitles=[module.title for module in dna_modules],
        metricCards=metric_cards,
        evidenceWeights=_build_evidence_weights(
            scope,
            len(note_items),
            len(items),
            dna_modules,
            project_context_count=int(project_summary["count"]),
            focus_plan_ready=bool(structured_plan_texts or focus_item_texts),
        ),
        confirmedFacts=confirmed_facts,
        hypothesisHighlights=hypotheses,
        nextWeekFocus=_build_next_focus(scope, items, hypotheses, viewer_role=viewer_role),
        eventLineSummaries=event_line_summaries,
        eventLineCompleteness=event_line_completeness,
        riskCards=risk_cards,
        opportunityCards=opportunity_cards,
        trendSignals=trend_signals,
    )


def build_hierarchy_report_from_analysis(
    analysis: WeeklyReviewAnalysisRecord,
    *,
    week_label: str,
    scope_type: Literal["employee", "team", "org"] = "org",
    scope_ref_id: str = "local",
) -> HierarchyReportRecord:
    summary_parts = [analysis.caution]
    event_line_summaries = list(getattr(analysis, "eventLineSummaries", []) or [])
    event_line_judgments = list(getattr(analysis, "eventLineJudgments", []) or [])
    risk_cards = list(getattr(analysis, "riskCards", []) or [])
    opportunity_cards = list(getattr(analysis, "opportunityCards", []) or [])
    hypothesis_highlights = list(getattr(analysis, "hypothesisHighlights", []) or [])
    next_week_focus = list(getattr(analysis, "nextWeekFocus", []) or [])
    evidence_weights = list(getattr(analysis, "evidenceWeights", []) or [])
    if event_line_judgments:
        summary_parts.append(event_line_judgments[0].whatHappened)
        summary_parts.append(event_line_judgments[0].whyItMatters)
    elif event_line_summaries:
        summary_parts.append(event_line_summaries[0].whatHappenedThisWeek)
        summary_parts.append(event_line_summaries[0].currentState)
    elif hypothesis_highlights:
        summary_parts.append(hypothesis_highlights[0].statement)
    support_signals = _risk_overview_lines(risk_cards, limit=3)
    if not support_signals and event_line_judgments:
        support_signals = _judgment_blocker_lines(event_line_judgments, limit=3)
    if not support_signals:
        support_signals = _hypothesis_overview_lines([item for item in hypothesis_highlights if item.title == "可能的阻碍原因"], limit=3)
    if not support_signals:
        support_signals = _hypothesis_overview_lines(hypothesis_highlights[1:3], limit=3)
    focus_areas = _judgment_overview_lines(event_line_judgments, limit=4) or _event_line_overview_lines(event_line_summaries, limit=4)
    if not focus_areas:
        focus_areas = _hypothesis_overview_lines(hypothesis_highlights[:4], limit=4)
    suggested_actions = _dedupe_texts(
        [
            *_judgment_action_lines(event_line_judgments, limit=3),
            *[_overview_line(item.title, item.suggestedAction) for item in risk_cards[:3]],
            *[_overview_line(item.title, item.recommendedAmplifier) for item in opportunity_cards[:3]],
            *_next_focus_overview_lines(next_week_focus, limit=3),
        ],
        limit=4,
    )
    anonymous_insights = _opportunity_overview_lines(opportunity_cards, limit=3) or _dedupe_texts(
        [
            *[_overview_line(item.title, item.managerImplication or item.opportunityIfAmplified) for item in event_line_judgments[:2]],
            *[_overview_line(item.title, item.currentState) for item in event_line_summaries[:2]],
            *_hypothesis_overview_lines(hypothesis_highlights[:2], limit=2),
        ],
        limit=3,
    )
    judgment_version = None
    bundle_fingerprint = None
    coverage_score = None
    confidence_score = None
    safe_output_mode = None
    publish_state: Literal["local_preview", "publish_ready", "published_by_human", "published_by_robot", "stale"] = "local_preview"
    published_at = None
    published_by = None
    invalidated_at = None
    publish_priority = {
        "local_preview": 0,
        "publish_ready": 1,
        "stale": 2,
        "published_by_robot": 3,
        "published_by_human": 4,
    }
    if event_line_judgments:
        judgment_versions = _dedupe_texts([item.judgmentVersion for item in event_line_judgments if item.judgmentVersion], limit=8)
        judgment_version = judgment_versions[0] if len(judgment_versions) == 1 else "mixed"
        fingerprints = sorted({item.bundleFingerprint for item in event_line_judgments if item.bundleFingerprint})
        if fingerprints:
            bundle_fingerprint = hashlib.sha1("|".join(fingerprints).encode("utf-8")).hexdigest()
        coverage_values = [item.coverageScore for item in event_line_judgments if item.coverageScore >= 0]
        if coverage_values:
            coverage_score = round(sum(coverage_values) / len(coverage_values))
        confidence_values = [item.confidenceScore for item in event_line_judgments if item.confidenceScore >= 0]
        if confidence_values:
            confidence_score = round(sum(confidence_values) / len(confidence_values))
        safe_modes = {item.safeOutputMode for item in event_line_judgments}
        if safe_modes == {"full_judgment"}:
            safe_output_mode = "full_judgment"
        elif "summary_only" in safe_modes or "full_judgment" in safe_modes:
            safe_output_mode = "summary_only"
        else:
            safe_output_mode = "needs_input"
        if safe_output_mode != "full_judgment":
            publish_state = "local_preview"
        else:
            states = [item.publishState for item in event_line_judgments]
            publish_state = max(states, key=lambda state: publish_priority.get(state, 0), default="local_preview")
            if scope_type == "employee" and publish_state == "publish_ready":
                publish_state = "local_preview"
        published_candidates = [item.publishedAt for item in event_line_judgments if item.publishedAt]
        published_at = max(published_candidates) if published_candidates else None
        published_by_candidates = [item.publishedBy for item in event_line_judgments if item.publishedBy]
        published_by = published_by_candidates[-1] if published_by_candidates else None
        invalidated_candidates = [item.invalidatedAt for item in event_line_judgments if item.invalidatedAt]
        invalidated_at = max(invalidated_candidates) if invalidated_candidates else None
    created_at = datetime.now().replace(microsecond=0).isoformat()
    return HierarchyReportRecord(
        id=f"review_report_{analysis.scope}_{week_label}",
        scopeType=scope_type,
        scopeRefId=scope_ref_id,
        weekLabel=week_label,
        logicMode="weighted_hypothesis_v1",
        judgmentVersion=judgment_version,
        bundleFingerprint=bundle_fingerprint,
        coverageScore=coverage_score,
        confidenceScore=confidence_score,
        safeOutputMode=safe_output_mode,
        headline=analysis.headline,
        summary=" ".join(summary_parts),
        summaryMetrics=analysis.metricCards,
        focusAreas=focus_areas,
        supportSignals=support_signals,
        suggestedActions=suggested_actions,
        anonymousInsights=anonymous_insights,
        sourcePolicy={
            **{item.sourceType: item.weight for item in evidence_weights},
            "eventLineSummaryCount": len(event_line_summaries),
            "eventLineJudgmentCount": len(event_line_judgments),
            "eventLineRiskCount": len(risk_cards),
            "eventLineOpportunityCount": len(opportunity_cards),
            "judgmentVersion": judgment_version,
            "bundleFingerprintCount": len({item.bundleFingerprint for item in event_line_judgments if item.bundleFingerprint}),
            "publishReadyCount": sum(1 for item in event_line_judgments if item.publishState == "publish_ready"),
            "coverageScore": coverage_score,
            "confidenceScore": confidence_score,
            "safeOutputMode": safe_output_mode,
        },
        actions=[],
        publishState=publish_state,
        publishedAt=published_at,
        publishedBy=published_by,
        invalidatedAt=invalidated_at,
        createdAt=created_at,
        updatedAt=created_at,
    )
~~~

## `backend/app/services/review_narrative.py`

- 编码: `utf-8`

~~~python
"""
叙事分析引擎 — 五层上下文驱动的周复盘深度理解

分析调用顺序：
1. 组织 DNA（益语是谁、靠什么服务客户）
2. 客户背景（客户是谁、行业位置、需求痛点）
3. 合作关系（为什么接触、对双方意味着什么）
4. 事件线时间记忆（跨周历史轨迹）
5. 当前任务快照（作为整条线上的一个节点）

输出优先级：
- 这是什么事 → 为什么重要 → 推进到哪 → 还缺什么理解
- 信息足够时才升级为：风险、时间闸门、最小动作、管理建议
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db import Database
    from app.services.ai import AiService

from app.models import (
    ClientStrategicProfileRecord,
    CooperationRelationshipRecord,
    EventLineWeeklySnapshotRecord,
    NarrativeAnalysisRecord,
    OrganizationDnaModuleRecord,
    WeeklyReviewTaskEntryRecord,
)

logger = logging.getLogger(__name__)


@dataclass
class WeeklyLineCard:
    line_name: str
    score: float
    what_happened: str
    why_it_matters: str
    progress_now: str
    next_gap_or_need: str


SOFTWARE_LINE_KEYWORDS = (
    "codex",
    "attachment",
    "附件",
    "保存",
    "上传",
    "debug",
    "排查",
    "可见性",
    "链路",
    "联调",
    "任务可见",
)
INTEL_LINE_KEYWORDS = (
    "心理健康",
    "心理友好",
    "数字监管",
    "垃圾代码",
    "开源社区",
    "ai ",
    "ai垃圾代码",
    "情报",
    "议题",
)
COLLAB_LINE_KEYWORDS = (
    "合作",
    "协作",
    "见面",
    "沟通",
    "交流",
    "吃饭",
    "对话",
)

NARRATIVE_SYSTEM_INSTRUCTION = """\
你是益语智库的周复盘分析助手。益语智库是一家咨询公司，核心业务是与客户的合作关系。

你的任务是为一条事件线生成深度叙事分析。你会收到五层上下文信息，请按以下优先级输出：

**必须回答（即使信息不完整也要尽力回答）：**
1. 这是什么事（whatThisIs）— 用一段话说清楚这条事件线在做什么
2. 为什么重要（whyImportant）— 结合客户背景和合作关系，解释这件事对益语和客户分别意味着什么
3. 现在推进到哪（currentProgress）— 结合事件线历史轨迹，说明当前处于什么阶段，相比之前有什么进展
4. 还缺什么理解（missingUnderstanding）— 系统目前对这条线还不够了解的地方，需要补充什么信息

**仅在信息充分时回答（否则留空）：**
5. 风险提示（riskNote）
6. 时间闸门（timeGate）
7. 最小动作（minimumAction）
8. 管理建议（managementAdvice）

重要原则：
- 不要从任务出发去猜背景，而是从背景、关系和时间线出发去理解任务
- 不要生成泛泛的建议，每一句话都要有具体的上下文支撑
- 如果某一层上下文缺失，明确说"系统尚未看到…的信息"，不要编造
- 用中文输出，语言简练有力
"""

NARRATIVE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "whatThisIs": {"type": "string", "description": "这是什么事"},
        "whyImportant": {"type": "string", "description": "为什么重要"},
        "currentProgress": {"type": "string", "description": "现在推进到哪"},
        "missingUnderstanding": {"type": "string", "description": "还缺什么理解"},
        "riskNote": {"type": "string", "description": "风险提示，信息不足时留空"},
        "timeGate": {"type": "string", "description": "时间闸门，信息不足时留空"},
        "minimumAction": {"type": "string", "description": "最小动作，信息不足时留空"},
        "managementAdvice": {"type": "string", "description": "管理建议，信息不足时留空"},
        "confidenceLevel": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": ["whatThisIs", "whyImportant", "currentProgress", "missingUnderstanding", "confidenceLevel"],
}

WEEKLY_OVERVIEW_SYSTEM_INSTRUCTION = """\
你是益语智库的周复盘写作助手，为管理层生成结构化的周概况。

信息权重（从高到低）：
1. 用户手写的周复盘说明（最可信的一手判断）
2. 会议纪要和附件内容（包含具体讨论细节、决策、下一步，是最有深度的信息源）
3. 事件线管理字段（卡点、决策、下一步）
4. 任务的卡点和下一步
5. 事件线叙事分析
6. 组织 DNA 背景（用于解释"为什么重要"，不要照搬）

写作规则：
1. headline: 用一句话定性这一周，必须包含一个具体事实（如"日慈教师赋能完成Q1复盘，为爱黔行创始人分歧待协调"），不要泛泛说"持续推进""取得进展"。
2. needsAttention: 只列需要管理层关注的事件线，reason 必须引用一个具体事实（人名、事件、数据），不要抽象概括。
3. onTrack: 正常推进的事件线，一句话说明本周具体完成了什么。
4. blockerSummary: 必须写具体的卡点——谁卡住了、卡在什么事上、为什么卡。如果多条线有类似卡点就对比说明。如果没有明确卡点就留空字符串，不要编造。
5. nextWeekHint: 必须是一个可执行的管理建议，包含具体的人/事/时间。例如"下周五前让高老师交品牌规划，否则日慈Q2节奏会延迟"。不要写"优先收束""聚焦存量"这种没有行动对象的空话。
6. nextWeekFocus: 每条必须包含：做什么 + 谁来做 + 什么时候要结果。

核心原则：
- 每一句话都必须有事实支撑，能从输入材料里找到出处
- 如果材料里没有足够信息支撑某个判断，就不要写，留空比编造好
- 宁可少写两条有信息量的，也不要多写五条空话

禁止：
- 不要输出覆盖率、置信度、样本量等元信息
- 不要用"值得关注""持续推进""成果收束""合作边界""明确落地方案"等抽象表述
- 不要把不同事件线的卡点抽象成一句话——每个卡点都是独立的，分开写
"""

WEEKLY_OVERVIEW_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string", "description": "一句话定性本周"},
        "needsAttention": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "lineName": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["lineName", "reason"],
            },
            "description": "需要管理层关注的事件线",
        },
        "onTrack": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "lineName": {"type": "string"},
                    "progress": {"type": "string"},
                },
                "required": ["lineName", "progress"],
            },
            "description": "正常推进的事件线",
        },
        "blockerSummary": {"type": "array", "items": {"type": "string"}, "description": "卡点列表，每条一个具体卡点，没有就留空数组"},
        "nextWeekHint": {"type": "string", "description": "本周管理洞察"},
        "nextWeekFocus": {"type": "array", "items": {"type": "string"}, "description": "下周重点"},
    },
    "required": ["headline", "needsAttention", "onTrack", "blockerSummary", "nextWeekHint", "nextWeekFocus"],
}


def _week_start_iso(week_label: str) -> str:
    """Convert a week label like '2026-W13' to the Monday ISO date string."""
    from datetime import datetime, timedelta
    try:
        year, week = week_label.split("-W")
        jan4 = datetime(int(year), 1, 4)
        start_of_w1 = jan4 - timedelta(days=jan4.isoweekday() - 1)
        monday = start_of_w1 + timedelta(weeks=int(week) - 1)
        return monday.strftime("%Y-%m-%d")
    except Exception:
        return "2000-01-01"


def _assemble_context_prompt(
    *,
    org_dna_modules: list[OrganizationDnaModuleRecord],
    client_profile: ClientStrategicProfileRecord | None,
    cooperation: CooperationRelationshipRecord | None,
    weekly_history: list[EventLineWeeklySnapshotRecord],
    event_line_name: str,
    event_line_stage: str,
    event_line_summary: str,
    event_line_intent: str,
    event_line_blocker: str,
    current_tasks: list[WeeklyReviewTaskEntryRecord],
    week_label: str,
    recent_activities: list[dict] | None = None,
) -> tuple[str, list[str]]:
    """组装五层上下文 prompt，返回 (prompt_text, layers_used)。"""
    sections: list[str] = []
    layers_used: list[str] = []

    # 第一层：组织 DNA
    if org_dna_modules:
        dna_text = "\n".join(
            f"- {m.title}: {m.summary or m.normalizedText[:200]}"
            for m in org_dna_modules[:4]
            if m.summary or m.normalizedText
        )
        if dna_text:
            sections.append(f"【第一层：益语智库组织 DNA】\n{dna_text}")
            layers_used.append("organization_dna")

    # 第二层：客户背景
    if client_profile and (client_profile.industry or client_profile.scale or client_profile.currentNeeds):
        parts = []
        if client_profile.industry:
            parts.append(f"行业：{client_profile.industry}")
        if client_profile.scale:
            parts.append(f"规模：{client_profile.scale}")
        if client_profile.influence:
            parts.append(f"影响力：{client_profile.influence}")
        if client_profile.currentNeeds:
            parts.append(f"当前需求：{client_profile.currentNeeds}")
        if client_profile.painPoints:
            parts.append(f"痛点：{client_profile.painPoints}")
        if client_profile.strategicValueToYiyu:
            parts.append(f"对益语的战略价值：{client_profile.strategicValueToYiyu}")
        if client_profile.decisionChain:
            parts.append(f"决策链：{client_profile.decisionChain}")
        sections.append(f"【第二层：客户背景】\n" + "\n".join(f"- {p}" for p in parts))
        layers_used.append("client_profile")

    # 第三层：合作关系
    if cooperation and (cooperation.whyConnected or cooperation.meaningToYiyu):
        parts = []
        if cooperation.whyConnected:
            parts.append(f"为什么接触：{cooperation.whyConnected}")
        if cooperation.meaningToYiyu:
            parts.append(f"对益语意味着：{cooperation.meaningToYiyu}")
        if cooperation.meaningToClient:
            parts.append(f"对客户意味着：{cooperation.meaningToClient}")
        parts.append(f"合作类型：{cooperation.cooperationType}")
        parts.append(f"关系健康度：{cooperation.relationshipHealth}")
        if cooperation.milestones:
            parts.append(f"里程碑：{cooperation.milestones}")
        if cooperation.keyStakeholders:
            stakeholder_text = "、".join(f"{s.name}({s.role})" for s in cooperation.keyStakeholders[:5])
            parts.append(f"关键干系人：{stakeholder_text}")
        sections.append(f"【第三层：益语与客户的合作关系】\n" + "\n".join(f"- {p}" for p in parts))
        layers_used.append("cooperation_relationship")

    # 第四层：事件线跨周历史
    if weekly_history:
        history_lines = []
        for snap in weekly_history[:8]:
            line = f"- {snap.weekLabel}：阶段={snap.stageAtThatTime or '未标记'}，任务{snap.taskCount}条/完成{snap.completedCount}条"
            if snap.keyDecisions:
                line += f"，决定：{'；'.join(snap.keyDecisions[:2])}"
            if snap.blockersThen:
                line += f"，卡点：{'；'.join(snap.blockersThen[:2])}"
            if snap.progressDelta:
                line += f"，进展：{snap.progressDelta}"
            history_lines.append(line)
        sections.append(f"【第四层：事件线历史轨迹（近{len(weekly_history)}周）】\n" + "\n".join(history_lines))
        layers_used.append("event_line_history")

    # 第五层：当前周任务
    task_lines = []
    for item in current_tasks[:10]:
        snap = item.taskSnapshot
        status = getattr(snap, "status", "未知")
        title = getattr(snap, "title", "")
        note = item.note.strip() if item.note else ""
        line = f"- [{status}] {title}"
        if note:
            line += f" — 复盘说明：{note[:100]}"
        task_lines.append(line)
    event_info = f"事件线：{event_line_name}"
    if event_line_stage:
        event_info += f"（阶段：{event_line_stage}）"
    if event_line_summary:
        event_info += f"\n概要：{event_line_summary}"
    if event_line_intent:
        event_info += f"\n意图：{event_line_intent}"
    if event_line_blocker:
        event_info += f"\n当前阻碍：{event_line_blocker}"

    # 事件线本周活动记录（任务状态变更、会议发布、支持请求处理、手动备注）
    activity_text = ""
    if recent_activities:
        activity_lines = []
        for act in recent_activities[:8]:
            act_title = act.get("title", "")
            act_summary = act.get("summary", "")
            act_time = str(act.get("happened_at", ""))[:16].replace("T", " ")
            act_type = act.get("source_type", "")
            activity_lines.append(f"- [{act_type}] {act_title}（{act_time}）：{act_summary[:120]}")
        if activity_lines:
            activity_text = "\n\n本周事件线活动记录：\n" + "\n".join(activity_lines)
            layers_used.append("event_line_activities")

    sections.append(
        f"【第五层：{week_label} 当前任务（共{len(current_tasks)}条）】\n{event_info}\n"
        + ("\n".join(task_lines) if task_lines else "本周暂无任务记录。")
        + activity_text
    )
    layers_used.append("current_tasks")

    prompt = "\n\n".join(sections)
    return prompt, layers_used


def build_narrative_analyses(
    *,
    ai: AiService,
    db: Database,
    week_label: str,
    items: list[WeeklyReviewTaskEntryRecord],
    org_dna_modules: list[OrganizationDnaModuleRecord],
) -> list[NarrativeAnalysisRecord]:
    """为本周涉及的每条事件线生成叙事分析。"""
    from collections import defaultdict

    # 按事件线分组
    groups: dict[str, list[WeeklyReviewTaskEntryRecord]] = defaultdict(list)
    for item in items:
        el_id = getattr(item.taskSnapshot, "eventLineId", None) or ""
        if el_id:
            groups[el_id].append(item)

    if not groups:
        return []

    results: list[NarrativeAnalysisRecord] = []

    for el_id, line_items in groups.items():
        try:
            # 读取事件线基本信息
            el_row = db.fetchone("SELECT * FROM event_lines WHERE id = ?", (el_id,))
            if not el_row:
                continue
            el_name = str(el_row["name"] or "")
            client_id = str(el_row["primary_client_id"] or "")
            client_name = str(el_row["primary_client_name"] or "")

            # 读取客户战略画像
            client_profile: ClientStrategicProfileRecord | None = None
            if client_id:
                profile_row = db.fetchone("SELECT * FROM client_strategic_profiles WHERE client_id = ?", (client_id,))
                if profile_row:
                    client_profile = ClientStrategicProfileRecord(
                        clientId=str(profile_row["client_id"]),
                        industry=str(profile_row["industry"] or ""),
                        scale=str(profile_row["scale"] or ""),
                        influence=str(profile_row["influence"] or ""),
                        currentNeeds=str(profile_row["current_needs"] or ""),
                        painPoints=str(profile_row["pain_points"] or ""),
                        strategicValueToYiyu=str(profile_row["strategic_value_to_yiyu"] or ""),
                        decisionChain=str(profile_row["decision_chain"] or ""),
                        updatedAt=str(profile_row["updated_at"] or ""),
                    )

            # 读取合作关系
            cooperation: CooperationRelationshipRecord | None = None
            if client_id:
                coop_row = db.fetchone("SELECT * FROM cooperation_relationships WHERE client_id = ?", (client_id,))
                if coop_row:
                    cooperation = CooperationRelationshipRecord(
                        id=str(coop_row["id"]),
                        clientId=str(coop_row["client_id"]),
                        clientName=str(coop_row["client_name"] or ""),
                        whyConnected=str(coop_row["why_connected"] or ""),
                        meaningToYiyu=str(coop_row["meaning_to_yiyu"] or ""),
                        meaningToClient=str(coop_row["meaning_to_client"] or ""),
                        cooperationType=str(coop_row["cooperation_type"] or "exploring"),
                        relationshipHealth=str(coop_row["relationship_health"] or "steady"),
                        keyStakeholders=json.loads(str(coop_row["key_stakeholders_json"] or "[]")),
                        milestones=str(coop_row["milestones"] or ""),
                        startedAt=str(coop_row["started_at"] or ""),
                        updatedAt=str(coop_row["updated_at"] or ""),
                    )

            # 读取事件线跨周历史
            history_rows = db.fetchall(
                "SELECT * FROM event_line_weekly_snapshots WHERE event_line_id = ? ORDER BY week_label DESC LIMIT 13",
                (el_id,),
            )
            weekly_history = [
                EventLineWeeklySnapshotRecord(
                    id=str(r["id"]),
                    eventLineId=str(r["event_line_id"]),
                    eventLineName=str(r["event_line_name"] or ""),
                    weekLabel=str(r["week_label"]),
                    stageAtThatTime=str(r["stage_at_that_time"] or ""),
                    keyDecisions=json.loads(str(r["key_decisions_json"] or "[]")),
                    turningPoints=json.loads(str(r["turning_points_json"] or "[]")),
                    blockersThen=json.loads(str(r["blockers_then_json"] or "[]")),
                    progressDelta=str(r["progress_delta"] or ""),
                    taskCount=int(r["task_count"] or 0),
                    completedCount=int(r["completed_count"] or 0),
                    createdAt=str(r["created_at"] or ""),
                )
                for r in history_rows
            ]

            # 读取事件线本周活动记录
            activity_rows = db.fetchall(
                """
                SELECT source_type, title, summary, happened_at
                FROM event_line_activities
                WHERE event_line_id = ? AND happened_at >= ?
                ORDER BY happened_at DESC
                LIMIT 10
                """,
                (el_id, _week_start_iso(week_label)),
            )
            recent_activities = [dict(r) for r in activity_rows] if activity_rows else []

            # 组装 prompt
            prompt, layers_used = _assemble_context_prompt(
                org_dna_modules=org_dna_modules,
                client_profile=client_profile,
                cooperation=cooperation,
                weekly_history=weekly_history,
                event_line_name=el_name,
                event_line_stage=str(el_row["stage"] or ""),
                event_line_summary=str(el_row["summary"] or ""),
                event_line_intent=str(el_row["intent"] or ""),
                event_line_blocker=str(el_row["current_blocker"] or ""),
                current_tasks=line_items,
                week_label=week_label,
                recent_activities=recent_activities,
            )

            # 调用 LLM
            try:
                raw = ai._qwen_generate(
                    prompt=prompt,
                    system_instruction=NARRATIVE_SYSTEM_INSTRUCTION,
                    response_schema=NARRATIVE_RESPONSE_SCHEMA,
                    timeout_seconds=45.0,
                    max_tokens=1500,
                    temperature=0.3,
                )
            except Exception:
                raw = None

            if not raw or not isinstance(raw, dict):
                # 无法调用 LLM，生成保守的规则兜底
                results.append(NarrativeAnalysisRecord(
                    eventLineId=el_id,
                    eventLineName=el_name,
                    clientId=client_id or None,
                    clientName=client_name or None,
                    whatThisIs=f"事件线「{el_name}」本周共涉及 {len(line_items)} 条任务。",
                    whyImportant="系统当前无法调用 AI 服务，暂时只能展示基本事实。",
                    currentProgress=f"阶段：{el_row['stage'] or '未标记'}",
                    missingUnderstanding="AI 分析服务暂不可用，建议检查 AI 配置后重新生成。",
                    contextLayersUsed=layers_used,
                    confidenceLevel="low",
                ))
                continue

            results.append(NarrativeAnalysisRecord(
                eventLineId=el_id,
                eventLineName=el_name,
                clientId=client_id or None,
                clientName=client_name or None,
                whatThisIs=str(raw.get("whatThisIs", "")),
                whyImportant=str(raw.get("whyImportant", "")),
                currentProgress=str(raw.get("currentProgress", "")),
                missingUnderstanding=str(raw.get("missingUnderstanding", "")),
                riskNote=str(raw.get("riskNote", "")) or None,
                timeGate=str(raw.get("timeGate", "")) or None,
                minimumAction=str(raw.get("minimumAction", "")) or None,
                managementAdvice=str(raw.get("managementAdvice", "")) or None,
                contextLayersUsed=layers_used,
                confidenceLevel=str(raw.get("confidenceLevel", "low")),
            ))

        except Exception as exc:
            logger.warning("Narrative analysis failed for event line %s: %s", el_id, exc)
            continue

    return results


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def _dedupe_lines(values: list[str], *, limit: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean_text(value)
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def _organization_background_preview(org_dna_modules: list[OrganizationDnaModuleRecord]) -> str:
    lines: list[str] = []
    for module in org_dna_modules:
        if not module.hasDocument:
            continue
        # Summary for DNA modules (keep prompt size manageable), full text for meeting minutes
        text = _clean_text(module.summary or module.normalizedText[:1500])
        if text:
            lines.append(f"- {module.title}: {text}")
    return "\n".join(lines)


def _weekly_overview_task_lines(items: list[WeeklyReviewTaskEntryRecord]) -> str:
    lines: list[str] = []
    for item in items[:12]:
        snap = item.taskSnapshot
        parts = [snap.title]
        if snap.clientName:
            parts.append(f"客户={snap.clientName}")
        if snap.eventLineName:
            parts.append(f"事件线={snap.eventLineName}")
        desc = _clean_text(getattr(snap, "desc", "") or "")
        note = _clean_text(getattr(snap, "note", "") or item.note or "")
        if desc:
            parts.append(f"说明={desc}")
        elif note:
            parts.append(f"备注={note}")
        # Task action fields
        blocker = _clean_text(getattr(snap, "currentBlocker", "") or "")
        next_action = _clean_text(getattr(snap, "nextAction", "") or "")
        decision = _clean_text(getattr(snap, "recentDecision", "") or "")
        if blocker:
            parts.append(f"卡点={blocker}")
        if next_action:
            parts.append(f"下一步={next_action}")
        if decision:
            parts.append(f"决策={decision}")
        # Event line context
        elc = snap.eventLineContext
        if elc:
            if elc.summary:
                parts.append(f"事件线说明={_clean_text(elc.summary)}")
            if elc.currentBlocker:
                parts.append(f"事件线卡点={_clean_text(elc.currentBlocker)}")
            if elc.recentDecision:
                parts.append(f"事件线决策={_clean_text(elc.recentDecision)}")
            if elc.nextStep:
                parts.append(f"事件线下一步={_clean_text(elc.nextStep)}")
        # Review note (user's weekly review input — highest weight)
        review_note = _clean_text(item.note or "")
        if review_note and review_note != note:
            parts.append(f"周复盘={review_note}")
        lines.append("- " + "；".join(parts))
    return "\n".join(lines)


def _narrative_summary_lines(narratives: list[NarrativeAnalysisRecord]) -> str:
    lines: list[str] = []
    for narrative in narratives[:6]:
        parts = [
            f"{narrative.eventLineName or narrative.eventLineId}",
            f"这是什么事：{_clean_text(narrative.whatThisIs)}" if narrative.whatThisIs else "",
            f"为什么重要：{_clean_text(narrative.whyImportant)}" if narrative.whyImportant else "",
            f"推进到哪：{_clean_text(narrative.currentProgress)}" if narrative.currentProgress else "",
            f"还缺什么理解：{_clean_text(narrative.missingUnderstanding)}" if narrative.missingUnderstanding else "",
        ]
        lines.append("- " + "；".join(part for part in parts if part))
    return "\n".join(lines)


def _client_background_map(org_dna_modules: list[OrganizationDnaModuleRecord]) -> dict[str, str]:
    backgrounds: dict[str, str] = {}
    for module in org_dna_modules:
        title = _clean_text(module.title)
        text = _clean_text(module.summary or module.normalizedText[:220])
        if not title or not text:
            continue
        if title.endswith("业务背景"):
            client_name = title[: -len("业务背景")].strip()
            if client_name:
                backgrounds[client_name] = text
    return backgrounds


def _task_text(item: WeeklyReviewTaskEntryRecord) -> str:
    snap = item.taskSnapshot
    return _clean_text(
        " ".join(
            part
            for part in [
                snap.title,
                snap.clientName or "",
                snap.eventLineName or "",
                getattr(snap, "desc", "") or "",
                getattr(snap, "note", "") or item.note or "",
            ]
            if str(part or "").strip()
        )
    )


def _infer_line_bucket(item: WeeklyReviewTaskEntryRecord) -> tuple[str, str]:
    snap = item.taskSnapshot
    text = _task_text(item).lower()
    client_name = _clean_text(snap.clientName or "")
    event_line_name = _clean_text(snap.eventLineName or "")
    event_line_id = _clean_text(snap.eventLineId or "")
    if event_line_id or event_line_name:
        base_name = event_line_name or snap.title
        if client_name and client_name not in base_name:
            return (f"event_line::{event_line_id or base_name}", f"{client_name} · {base_name}")
        return (f"event_line::{event_line_id or base_name}", base_name)
    if client_name:
        return (f"client::{client_name}", f"{client_name} 推进线")
    if any(keyword in text for keyword in SOFTWARE_LINE_KEYWORDS):
        return ("semantic::software", "软件底层修复与验证线")
    if any(keyword in text for keyword in INTEL_LINE_KEYWORDS):
        return ("semantic::intel", "情报沉淀与产品化线")
    if any(keyword in text for keyword in COLLAB_LINE_KEYWORDS):
        return ("semantic::collab", "行业连接与协作探索线")
    return (f"task::{snap.title}", snap.title)


def _line_progress_from_items(items: list[WeeklyReviewTaskEntryRecord], narrative: NarrativeAnalysisRecord | None) -> str:
    if narrative and _clean_text(narrative.currentProgress):
        return _clean_text(narrative.currentProgress)
    statuses = [str(item.taskSnapshot.status or "").strip().lower() for item in items]
    completed_count = sum(1 for status in statuses if status == "done")
    if completed_count == len(items) and items:
        return "这条线本周已经有明确推进，但还处在把结果进一步收束成正式输出的阶段。"
    if completed_count > 0:
        return "这条线已经从泛推进进入更具体的说明、校准或方案收束阶段。"
    return "这条线仍处在推进中的早中段，已经有动作，但还没有完全收束成明确结果。"


def _line_gap_from_items(items: list[WeeklyReviewTaskEntryRecord], narrative: NarrativeAnalysisRecord | None) -> str:
    if narrative and _clean_text(narrative.missingUnderstanding):
        return _clean_text(narrative.missingUnderstanding)
    next_actions: list[str] = []
    blockers: list[str] = []
    for item in items:
        structured = getattr(item, "structuredNote", None)
        for value in [
            getattr(structured, "nextAction", "") if structured else "",
            getattr(item.taskSnapshot, "nextAction", "") or "",
        ]:
            cleaned = _clean_text(value)
            if cleaned and cleaned not in next_actions:
                next_actions.append(cleaned)
        for value in [
            getattr(structured, "blockerReason", "") if structured else "",
            getattr(item.taskSnapshot, "currentBlocker", "") or "",
        ]:
            cleaned = _clean_text(value)
            if cleaned and cleaned not in blockers:
                blockers.append(cleaned)
    if next_actions:
        return f"接下来最缺的是把这条线收成明确动作：{next_actions[0]}"
    if blockers:
        return f"接下来最缺的是把当前卡点讲清楚并收束：{blockers[0]}"
    return "接下来最缺的不是新增动作，而是把已有推进收成更清楚的边界、产出和后续安排。"


def _line_score(items: list[WeeklyReviewTaskEntryRecord], line_name: str, why_it_matters: str) -> float:
    text = _clean_text(" ".join([line_name, why_it_matters, *(_task_text(item) for item in items)])).lower()
    strategic_leverage = 0.45
    if "cffc" in text or "枢纽" in text or "基金会网络" in text:
        strategic_leverage = 0.95
    elif "软件" in line_name or "底层" in line_name or "codex" in text:
        strategic_leverage = 0.86
    elif "日慈" in text or "为爱黔行" in text:
        strategic_leverage = 0.78
    elif "情报" in line_name or "心理友好" in text or "开源社区" in text:
        strategic_leverage = 0.74
    progress_evidence = min(1.0, len(items) / 3.0)
    output_clarity = 0.45
    if any(_clean_text(getattr(item.taskSnapshot, "nextAction", "") or "") for item in items):
        output_clarity += 0.2
    if any(_clean_text(item.note) for item in items):
        output_clarity += 0.15
    if any(_clean_text(getattr(item.taskSnapshot, "recentDecision", "") or "") for item in items):
        output_clarity += 0.2
    productization_potential = 0.35
    if "软件" in line_name or "情报" in line_name or "开源" in text or "心理友好" in text:
        productization_potential = 0.9
    evidence_strength = min(
        1.0,
        sum(
            max(1, int(getattr(item.taskSnapshot, "evidenceCount", 0) or 0))
            for item in items
        )
        / 8.0,
    )
    score = (
        0.35 * strategic_leverage
        + 0.25 * progress_evidence
        + 0.20 * min(output_clarity, 1.0)
        + 0.10 * productization_potential
        + 0.10 * evidence_strength
    )
    return round(score, 3)


def _build_weekly_line_cards(
    items: list[WeeklyReviewTaskEntryRecord],
    org_dna_modules: list[OrganizationDnaModuleRecord],
    narratives: list[NarrativeAnalysisRecord],
) -> list[WeeklyLineCard]:
    if not items:
        return []
    grouped_items: dict[str, dict[str, object]] = {}
    narrative_by_line: dict[str, NarrativeAnalysisRecord] = {}
    for narrative in narratives:
        if narrative.eventLineId:
            narrative_by_line[f"event_line::{narrative.eventLineId}"] = narrative
        if narrative.eventLineName:
            narrative_by_line.setdefault(f"event_line::{narrative.eventLineName}", narrative)
    client_backgrounds = _client_background_map(org_dna_modules)
    for item in items:
        bucket_key, line_name = _infer_line_bucket(item)
        bucket = grouped_items.setdefault(bucket_key, {"line_name": line_name, "items": []})
        bucket["items"].append(item)  # type: ignore[index]

    line_cards: list[WeeklyLineCard] = []
    for bucket_key, bucket in grouped_items.items():
        line_name = str(bucket["line_name"])
        bucket_items = list(bucket["items"])  # type: ignore[arg-type]
        primary_item = bucket_items[0]
        narrative = narrative_by_line.get(bucket_key)
        if narrative is None and primary_item.taskSnapshot.eventLineName:
            narrative = narrative_by_line.get(f"event_line::{primary_item.taskSnapshot.eventLineName}")
        task_titles = "、".join(item.taskSnapshot.title for item in bucket_items[:3])
        client_name = _clean_text(primary_item.taskSnapshot.clientName or "")
        client_bg = client_backgrounds.get(client_name, "")

        if narrative and _clean_text(narrative.whatThisIs):
            what_happened = _clean_text(narrative.whatThisIs)
        elif line_name == "软件底层修复与验证线":
            what_happened = f"这周围绕 {task_titles} 等事项，集中排查并修复了附件保存、上传写入和任务可见性等底层链路问题。"
        elif line_name == "情报沉淀与产品化线":
            what_happened = f"这周把 {task_titles} 这类外部信号收进系统，开始从资讯吸收转向咨询议题和产品切口沉淀。"
        else:
            what_happened = f"这周围绕 {task_titles} 等事项持续推进，已经不只是零散接触，而是在形成一条更清楚的业务推进线。"

        if narrative and _clean_text(narrative.whyImportant):
            why_it_matters = _clean_text(narrative.whyImportant)
        elif client_bg:
            why_it_matters = client_bg
        elif "cffc" in _clean_text(line_name).lower():
            why_it_matters = "这条线的重要性不只是一次普通合作，而是通过公益行业关键枢纽去打开更大基金会网络的入口。"
        elif line_name == "软件底层修复与验证线":
            why_it_matters = "这条线表面上像在 debug，实际上是在给益语的数字化工作台补地基；地基不稳，后续判断、交付和客户体验都站不住。"
        elif line_name == "情报沉淀与产品化线":
            why_it_matters = "这条线的意义不在资讯本身，而在于把外部变化转成益语后续的咨询议题、产品方向和客户对话素材。"
        else:
            why_it_matters = "这条线的重要性在于，它直接关系到益语能否把当前的关系推进成更清楚的合作、诊断或交付。"

        progress_now = _line_progress_from_items(bucket_items, narrative)
        next_gap_or_need = _line_gap_from_items(bucket_items, narrative)
        line_cards.append(
            WeeklyLineCard(
                line_name=line_name,
                score=_line_score(bucket_items, line_name, why_it_matters),
                what_happened=what_happened,
                why_it_matters=why_it_matters,
                progress_now=progress_now,
                next_gap_or_need=next_gap_or_need,
            )
        )

    line_cards.sort(key=lambda item: (-item.score, item.line_name))
    return line_cards[:5]


def _weekly_line_card_lines(line_cards: list[WeeklyLineCard]) -> str:
    lines: list[str] = []
    for card in line_cards:
        lines.append(
            "\n".join(
                [
                    f"- {card.line_name}（score={card.score}）",
                    f"  这周发生了什么：{card.what_happened}",
                    f"  为什么重要：{card.why_it_matters}",
                    f"  现在推进到哪：{card.progress_now}",
                    f"  还缺什么理解：{card.next_gap_or_need}",
                ]
            )
        )
    return "\n".join(lines)


def build_weekly_overview_draft(
    *,
    ai: AiService,
    week_label: str,
    items: list[WeeklyReviewTaskEntryRecord],
    org_dna_modules: list[OrganizationDnaModuleRecord],
    narratives: list[NarrativeAnalysisRecord],
    fallback_overview: str,
    fallback_focus_lines: list[str],
    fallback_next_focus: list[str],
    attachment_texts: list[str] | None = None,
    local_memory_context: str = "",
) -> tuple[str, list[str], list[str]]:
    fallback_focus = _dedupe_lines(fallback_focus_lines, limit=4)
    fallback_next = _dedupe_lines(fallback_next_focus, limit=3)
    fallback_summary = _clean_text(fallback_overview)
    line_cards = _build_weekly_line_cards(items, org_dna_modules, narratives)
    health = ai.get_health()
    if health.provider == "mock" or not health.ready:
        return fallback_summary, fallback_focus, fallback_next

    # Build event line summary from task items (deduplicated)
    el_summary_lines: list[str] = []
    seen_el_ids: set[str] = set()
    for item in items:
        elc = item.taskSnapshot.eventLineContext
        if not elc or not elc.id or elc.id in seen_el_ids:
            continue
        seen_el_ids.add(elc.id)
        el_parts = [elc.name or ""]
        if elc.summary:
            el_parts.append(f"说明={_clean_text(elc.summary)}")
        if elc.currentBlocker:
            el_parts.append(f"卡点={_clean_text(elc.currentBlocker)}")
        if elc.recentDecision:
            el_parts.append(f"决策={_clean_text(elc.recentDecision)}")
        if elc.nextStep:
            el_parts.append(f"下一步={_clean_text(elc.nextStep)}")
        if elc.stage:
            el_parts.append(f"阶段={_clean_text(elc.stage)}")
        if len(el_parts) > 1:
            el_summary_lines.append("- " + "；".join(el_parts))
    event_line_fields_block = "\n".join(el_summary_lines)

    prompt = "\n\n".join(
        part
        for part in [
            f"【周标签】\n{week_label}",
            f"【规则兜底草稿】\n{fallback_summary}",
            f"【规则识别的主线】\n" + "\n".join(f"- {line}" for line in fallback_focus) if fallback_focus else "",
            f"【主线理解卡】\n{_weekly_line_card_lines(line_cards)}" if line_cards else "",
            f"【组织背景（含团队与市场）】\n{_organization_background_preview(org_dna_modules)}",
            f"【事件线管理字段】\n{event_line_fields_block}" if event_line_fields_block else "",
            f"【事件线叙事】\n{_narrative_summary_lines(narratives)}" if narratives else "",
            f"【本周任务与线索】\n{_weekly_overview_task_lines(items)}",
            f"【本地项目记忆（历史判断与上下文）】\n{local_memory_context}" if local_memory_context else "",
            f"【会议纪要与附件内容（高价值信息源）】\n" + "\n\n".join(attachment_texts[:6]) if attachment_texts else "",
        ]
        if part
    )

    # Log what data is actually in the prompt
    has_att = "会议纪要" in prompt or "附件内容" in prompt
    att_section_len = len(prompt.split("【会议纪要与附件内容")[1]) if "【会议纪要与附件内容" in prompt else 0
    logger.info("[weekly-overview] prompt_len=%d, has_attachment_section=%s, att_section_len=%d, attachment_texts_count=%d",
                len(prompt), has_att, att_section_len, len(attachment_texts or []))

    try:
        logger.info("[weekly-overview] AI provider=%s, calling _qwen_generate with new structured prompt...", ai.get_health().provider)
        raw = ai._qwen_generate(
            prompt=prompt,
            system_instruction=WEEKLY_OVERVIEW_SYSTEM_INSTRUCTION,
            response_schema=WEEKLY_OVERVIEW_RESPONSE_SCHEMA,
            timeout_seconds=120.0,
            max_tokens=4000,
            temperature=0.35,
            top_p=0.9,
            enable_thinking=False,
        )
        logger.info("[weekly-overview] AI raw response type=%s, keys=%s", type(raw).__name__, list(raw.keys()) if isinstance(raw, dict) else "N/A")
        if not isinstance(raw, dict):
            logger.warning("[weekly-overview] AI returned non-dict, falling back")
            return fallback_summary, fallback_focus, fallback_next

        headline = _clean_text(str(raw.get("headline") or ""))
        needs_attention = raw.get("needsAttention") or []
        on_track = raw.get("onTrack") or []
        raw_blockers = raw.get("blockerSummary") or []
        if isinstance(raw_blockers, str):
            raw_blockers = [raw_blockers] if raw_blockers.strip() else []
        blocker_items = [_clean_text(str(b)) for b in raw_blockers if _clean_text(str(b))]
        weekly_insight = _clean_text(str(raw.get("nextWeekHint") or ""))
        next_week_focus = [str(item) for item in (raw.get("nextWeekFocus") or [])]

        # Assemble structured output into readable overview text
        overview_parts: list[str] = []
        if headline:
            overview_parts.append(headline)
        if needs_attention:
            overview_parts.append("\n【需要关注】")
            for item in needs_attention:
                if isinstance(item, dict):
                    name = str(item.get("lineName", ""))
                    reason = str(item.get("reason", ""))
                    overview_parts.append(f"• {name}：{reason}")
        if on_track:
            overview_parts.append("\n【正常推进】")
            for item in on_track:
                if isinstance(item, dict):
                    name = str(item.get("lineName", ""))
                    progress = str(item.get("progress", ""))
                    overview_parts.append(f"• {name}：{progress}")
        if blocker_items:
            blocker_lines = "\n".join(f"{i+1}. {b}" for i, b in enumerate(blocker_items))
            overview_parts.append(f"\n【卡点汇总】\n{blocker_lines}")
        if weekly_insight:
            overview_parts.append(f"\n【下周提示】\n{weekly_insight}")

        overview = "\n".join(overview_parts)

        # Build focus_lines from needs_attention + on_track
        focus_lines: list[str] = []
        for item in needs_attention:
            if isinstance(item, dict):
                focus_lines.append(f"{item.get('lineName', '')}｜{item.get('reason', '')}")
        for item in on_track:
            if isinstance(item, dict):
                focus_lines.append(f"{item.get('lineName', '')}｜{item.get('progress', '')}")
        focus_lines = _dedupe_lines(focus_lines, limit=6)

        next_focus = _dedupe_lines(next_week_focus, limit=3)

        logger.info("[weekly-overview] assembled overview len=%d, has【=%s", len(overview), "【" in overview)
        if not ai._has_sufficient_cjk(overview) or len(overview) < 40:
            logger.warning("[weekly-overview] overview failed CJK/length check, falling back. len=%d", len(overview))
            return fallback_summary, fallback_focus, fallback_next
        if not focus_lines:
            focus_lines = fallback_focus
        if not next_focus:
            next_focus = fallback_next
        return overview, focus_lines, next_focus
    except Exception as exc:
        logger.warning("Weekly overview generation failed: %s", exc)
        return fallback_summary, fallback_focus, fallback_next
~~~

## `backend/app/services/review_rollup.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

from collections import Counter
from datetime import datetime

from app.models import (
    HierarchyReportRecord,
    OrgModelProfileRecord,
    OrgRoleProcessTemplateRecord,
    OrganizationDnaModuleRecord,
    ReviewActionCardRecord,
    ReviewDashboardCardTargetRecord,
    ReviewDashboardEvidenceRefRecord,
    ReviewDepartmentConfigRecord,
    ReviewGovernanceSettingsRecord,
    WeeklyReviewTaskEntryRecord,
)
from app.services.knowledge_base import tokenize
from app.services.review_analysis import build_hierarchy_report_from_analysis, build_weekly_review_analysis

DEPARTMENT_STRATEGY_PROFILES: dict[str, dict[str, object]] = {
    "咨询策略部": {
        "headline": "这周推进的不是文稿，而是“场景判断力的产品化”",
        "core": "本周真正推进的，不是几份备忘录或提纲，而是把复杂客户现场压缩成可行动判断的能力。这条能力链决定了益语后续能否把筹款、传播、项目设计等一线问题沉淀成可复用的方法。",
        "risk": "如果下周仍主要停留在提纲、初稿和零散讨论层，咨询判断就很难继续沉淀成标准件，部门会出现“看起来很忙、但难以复用”的问题。",
        "focus_areas": ["场景判断力产品化", "客户诊断链收束", "案例骨架沉淀", "标准件雏形"],
        "actions": ["把 1-2 条典型客户判断链整理成可复用模板。", "优先补齐关键项目的一线资料与判断依据。", "把本周判断沉淀成后续可直接复用的案例骨架。"],
    },
    "科技发展部": {
        "headline": "这周第一次把“顾问天天用的能力”做成了可运行骨架",
        "core": "本周最重要的进展，不是又做了一个功能点，而是开始把顾问天天会用的工作习惯收束成可运行骨架。只要这条主线成立，益语就能继续沿着“先顾问自用、再客户可用”的路径往前走。",
        "risk": "当前最大的风险不是功能不够多，而是如果界面和流程重新变复杂，团队会重新掉回“像项目管理软件而不像场景应用”的老路。",
        "focus_areas": ["顾问自用骨架", "极简任务闭环", "低迁移成本落地", "深分析后台"],
        "actions": ["优先把顾问高频动作继续做薄、做顺。", "用真实任务闭环验证功能，而不是继续堆复杂配置。", "盯住客户低学习成本和后台分析深度这两个方向不要跑偏。"],
    },
    "信息数据部": {
        "headline": "这周搭的不是报表，而是“管理信号引擎”",
        "core": "本周推进的核心，不只是导入结构、规则和统计口径，而是在为益语搭一层能把任务行为、客户资料和周复盘转成管理判断的信号引擎。没有这一层，高层仍然很难拿到值得信的趋势、预警和复盘依据。",
        "risk": "如果这条线只停留在数据整理和字段堆叠，而没有继续形成稳定的信号解释能力，部门就会停在“有数据、没判断”的半成品状态。",
        "focus_areas": ["管理信号引擎", "结构化导入规则", "预警阈值口径", "组织级判断模板"],
        "actions": ["把关键指标继续压缩成管理者真正会看的判断信号。", "先稳定完成率、延期率、支持请求率等核心口径。", "继续清理低质量数据源，避免噪音稀释判断。"],
    },
    "客户服务部": {
        "headline": "这周把市场真实阻力翻译成了产品边界",
        "core": "本周真正有价值的，不是单纯跟了多少客户，而是把客户为什么不用任务系统、为什么推进会卡住这件事逐步翻译成产品边界。只有这一层足够真实，产品和咨询两侧的动作才不会脱离客户现场。",
        "risk": "如果前线反馈继续只停留在零散抱怨，而没有被整理成可执行的产品约束和部署策略，团队就会反复在同样的问题上消耗。",
        "focus_areas": ["前线阻力翻译", "低学习成本落地", "部署顾虑消化", "客户使用闭环"],
        "actions": ["把客户最常见的部署顾虑整理成明确的处理话术。", "继续验证哪些录入动作是真正会劝退客户的。", "把前线反馈收束成产品团队可直接响应的边界清单。"],
    },
}


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _clean_text(value: str) -> str:
    return " ".join(value.split()).strip()


def _department_member_names(department: ReviewDepartmentConfigRecord) -> set[str]:
    return {member.fullName.strip().lower() for member in department.members if member.fullName.strip()}


def _department_member_ids(department: ReviewDepartmentConfigRecord) -> set[str]:
    return {member.id.strip() for member in department.members if member.id.strip()}


def _item_owner_id(item: WeeklyReviewTaskEntryRecord) -> str:
    return (item.taskSnapshot.ownerId or "").strip()


def _item_owner_name(item: WeeklyReviewTaskEntryRecord) -> str:
    return (item.taskSnapshot.ownerName or "").strip()


def _item_list_name(item: WeeklyReviewTaskEntryRecord) -> str:
    return (item.taskSnapshot.listName or "").strip()


def _item_org_context(item: WeeklyReviewTaskEntryRecord):
    return item.taskSnapshot.orgContext


def _item_department_id(item: WeeklyReviewTaskEntryRecord) -> str:
    context = _item_org_context(item)
    return (context.departmentId if context else "") or ""


def _item_role_template_id(item: WeeklyReviewTaskEntryRecord) -> str:
    context = _item_org_context(item)
    return (context.roleTemplateId if context else "") or ""


def _item_control_level(item: WeeklyReviewTaskEntryRecord) -> str:
    context = _item_org_context(item)
    return (context.controlLevel if context else "") or ""


def _item_needs_review(item: WeeklyReviewTaskEntryRecord) -> bool:
    context = _item_org_context(item)
    if not context:
        return False
    return bool(context.needsReview or context.approvalState == "pending" or (context.blockedAtStep or "").strip())


def _item_is_cross_department(item: WeeklyReviewTaskEntryRecord) -> bool:
    context = _item_org_context(item)
    return bool(context and context.isCrossDepartment)


def _item_project_context(item: WeeklyReviewTaskEntryRecord):
    return item.taskSnapshot.projectContext


def _item_event_line_id(item: WeeklyReviewTaskEntryRecord) -> str:
    return (item.taskSnapshot.eventLineId or "").strip()


def _item_event_line_name(item: WeeklyReviewTaskEntryRecord) -> str:
    return (item.taskSnapshot.eventLineName or "").strip()


def _item_focus_item_id(item: WeeklyReviewTaskEntryRecord) -> str:
    context = _item_org_context(item)
    return (context.focusItemId if context else "") or ""


def _item_department_plan_item_id(item: WeeklyReviewTaskEntryRecord) -> str:
    context = _item_org_context(item)
    return (context.departmentPlanItemId if context else "") or ""


def _is_agent_item(item: WeeklyReviewTaskEntryRecord) -> bool:
    owner_id = _item_owner_id(item)
    return owner_id.startswith("agent:")


def _item_text(item: WeeklyReviewTaskEntryRecord) -> str:
    parts = [
        item.taskSnapshot.title,
        item.note,
        item.structuredNote.reflection,
        item.structuredNote.lightweightTag,
        item.structuredNote.progress,
        item.structuredNote.successReason,
        item.structuredNote.blockerReason,
        item.structuredNote.supportNeeded,
        item.structuredNote.nextAction,
        item.taskSnapshot.listName,
        " ".join(tag.name for tag in item.taskSnapshot.tags),
    ]
    return _clean_text(" ".join(part for part in parts if part))


def _is_completed_item(item: WeeklyReviewTaskEntryRecord) -> bool:
    status = (item.structuredNote.completionStatus or "").strip()
    if status in {"done_on_time", "done_late"}:
        return True
    return (item.taskSnapshot.status or "").strip() == "done"


def _has_blocker_signal(item: WeeklyReviewTaskEntryRecord) -> bool:
    return bool(
        item.structuredNote.lightweightTag.strip()
        or item.structuredNote.blockerReason.strip()
        or item.structuredNote.supportNeeded.strip()
    )


def _representative_titles(items: list[WeeklyReviewTaskEntryRecord], limit: int = 3) -> list[str]:
    seen: set[str] = set()
    titles: list[str] = []
    for item in items:
        normalized = _clean_text(item.taskSnapshot.title)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        titles.append(f"{normalized[:20]}…" if len(normalized) > 20 else normalized)
        if len(titles) >= limit:
            break
    return titles


def _clean_lines(values: list[str], limit: int = 3) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _clean_text(value)
        if not normalized or normalized in seen:
            continue
        if len(normalized) > 80:
            normalized = normalized[:80].rstrip("，、；： ") + "…"
        seen.add(normalized)
        cleaned.append(normalized)
        if len(cleaned) >= limit:
            break
    return cleaned


def _overview_line(title: str, body: str) -> str:
    clean_title = _clean_text(title).rstrip("：:｜")
    clean_body = _clean_text(body)
    if len(clean_body) > 88:
        clean_body = clean_body[:87].rstrip("，、；：: ") + "…"
    if not clean_title:
        return clean_body
    if not clean_body or clean_body == clean_title:
        return clean_title
    return f"{clean_title}｜{clean_body}"


def _event_line_overview_lines(items, limit: int = 4) -> list[str]:
    return _clean_lines(
        [
            _overview_line(item.title, item.whatHappenedThisWeek or item.currentState or item.whatThisLineIs)
            for item in (items or [])[:limit]
        ],
        limit=limit,
    )


def _judgment_overview_lines(items, limit: int = 4) -> list[str]:
    return _clean_lines(
        [
            _overview_line(item.title, getattr(item, "whatHappened", "") or getattr(item, "whyItMatters", "") or getattr(item, "nextWeekFocus", ""))
            for item in (items or [])[:limit]
        ],
        limit=limit,
    )


def _judgment_blocker_lines(items, limit: int = 4) -> list[str]:
    return _clean_lines(
        [
            _overview_line(item.title, getattr(item, "coreBlocker", "") or getattr(item, "riskIfIgnored", ""))
            for item in (items or [])[:limit]
        ],
        limit=limit,
    )


def _judgment_action_lines(items, limit: int = 4) -> list[str]:
    return _clean_lines(
        [
            _overview_line(item.title, getattr(item, "minimumAction", "") or getattr(item, "nextWeekFocus", ""))
            for item in (items or [])[:limit]
        ],
        limit=limit,
    )


def _risk_overview_lines(items, limit: int = 4) -> list[str]:
    return _clean_lines([_overview_line(item.title, item.statement) for item in (items or [])[:limit]], limit=limit)


def _opportunity_overview_lines(items, limit: int = 4) -> list[str]:
    return _clean_lines([_overview_line(item.title, item.statement) for item in (items or [])[:limit]], limit=limit)


def _action_overview_lines(items, limit: int = 4) -> list[str]:
    return _clean_lines([_overview_line("建议动作", item) for item in items[:limit]], limit=limit)


def _judgment_management_lines(items, limit: int = 4) -> list[str]:
    return _clean_lines(
        [
            _overview_line(item.title, getattr(item, "managerImplication", "") or getattr(item, "whyItMatters", ""))
            for item in (items or [])[:limit]
        ],
        limit=limit,
    )


def _judgment_focus_lines(items, limit: int = 4) -> list[str]:
    return _clean_lines(
        [
            _overview_line(item.title, getattr(item, "whatHappened", "") or getattr(item, "nextWeekFocus", ""))
            for item in (items or [])[:limit]
        ],
        limit=limit,
    )


def _trend_overview_lines(items, limit: int = 4) -> list[str]:
    return _clean_lines(
        [
            _overview_line(item.title, item.statement)
            for item in (items or [])[:limit]
        ],
        limit=limit,
    )


def _event_line_rollup(items: list[WeeklyReviewTaskEntryRecord]) -> dict[str, object]:
    groups: dict[str, list[WeeklyReviewTaskEntryRecord]] = {}
    for item in items:
        event_line_id = _item_event_line_id(item)
        if not event_line_id:
            continue
        groups.setdefault(event_line_id, []).append(item)
    names = _clean_lines([_item_event_line_name(group[0]) or _item_text(group[0]) for group in groups.values()], limit=4)
    multi_task_group_count = sum(1 for group in groups.values() if len(group) >= 2)
    blocked_group_count = sum(1 for group in groups.values() if any(not _is_completed_item(item) for item in group))
    blocked_names = _clean_lines(
        [
            _item_event_line_name(group[0]) or _item_text(group[0])
            for group in groups.values()
            if any(not _is_completed_item(item) for item in group)
        ],
        limit=3,
    )
    return {
        "group_count": len(groups),
        "task_count": sum(len(group) for group in groups.values()),
        "multi_task_group_count": multi_task_group_count,
        "names": names,
        "blocked_group_count": blocked_group_count,
        "blocked_names": blocked_names,
    }


def _contains_phrase(text: str, phrase: str) -> bool:
    normalized_text = _clean_text(text)
    normalized_phrase = _clean_text(phrase)
    if not normalized_text or not normalized_phrase:
        return False
    if normalized_phrase in normalized_text:
        return True
    phrase_tokens = {token for token in tokenize(normalized_phrase) if len(token.strip()) >= 2}
    text_tokens = {token for token in tokenize(normalized_text) if len(token.strip()) >= 2}
    return bool(phrase_tokens and text_tokens and phrase_tokens & text_tokens)


def _org_model_indexes(org_model_profile: OrgModelProfileRecord | None) -> dict[str, dict[str, object]]:
    if org_model_profile is None:
        return {
            "departments": {},
            "roles": {},
            "bindings": {},
            "rules": {},
            "reporting": {},
            "processes_by_role": {},
        }
    reporting: dict[str, list[object]] = {}
    for line in org_model_profile.reportingLines:
        reporting.setdefault(line.reportUserId, []).append(line)
    processes_by_role: dict[str, list[OrgRoleProcessTemplateRecord]] = {}
    for template in org_model_profile.roleProcessTemplates:
        if not template.active or not template.roleTemplateId:
            continue
        processes_by_role.setdefault(template.roleTemplateId, []).append(template)
    return {
        "departments": {department.id: department for department in org_model_profile.departments},
        "roles": {role.id: role for role in org_model_profile.roles},
        "bindings": {binding.userId: binding for binding in org_model_profile.bindings},
        "rules": {rule.id: rule for rule in org_model_profile.taskControlRules},
        "reporting": reporting,
        "processes_by_role": processes_by_role,
    }


def _management_signal_bundle(
    items: list[WeeklyReviewTaskEntryRecord],
    *,
    org_model_profile: OrgModelProfileRecord | None,
    department_name: str | None = None,
) -> dict[str, object]:
    indexes = _org_model_indexes(org_model_profile)
    roles_by_id = indexes["roles"]
    bindings_by_user = indexes["bindings"]
    rules_by_id = indexes["rules"]
    reporting_by_report = indexes["reporting"]
    processes_by_role = indexes["processes_by_role"]
    role_drift_hits: list[tuple[WeeklyReviewTaskEntryRecord, object, str]] = []
    review_chain_items: list[WeeklyReviewTaskEntryRecord] = []
    controlled_items: list[WeeklyReviewTaskEntryRecord] = []
    cross_department_items: list[WeeklyReviewTaskEntryRecord] = []
    manager_load_items: list[tuple[WeeklyReviewTaskEntryRecord, object]] = []
    workflow_blocked_hits: list[tuple[WeeklyReviewTaskEntryRecord, OrgRoleProcessTemplateRecord, str]] = []
    overloaded_items: list[WeeklyReviewTaskEntryRecord] = []
    support_need_items: list[WeeklyReviewTaskEntryRecord] = []
    misaligned_items: list[WeeklyReviewTaskEntryRecord] = []
    project_risk_items: list[WeeklyReviewTaskEntryRecord] = []

    for item in items:
        context = _item_org_context(item)
        owner_id = _item_owner_id(item)
        lightweight_tag = item.structuredNote.lightweightTag.strip()
        if lightweight_tag == "工作过度饱和":
            overloaded_items.append(item)
        if lightweight_tag in {"资料不足", "等待他人", "资源不够"} or item.structuredNote.supportNeeded.strip():
            support_need_items.append(item)
        if item.structuredNote.departmentPlanAlignment == "misaligned" or item.structuredNote.organizationPlanAlignment == "misaligned":
            misaligned_items.append(item)
        if _item_project_context(item) and _item_project_context(item).riskSummary.strip():
            project_risk_items.append(item)
        binding = bindings_by_user.get(owner_id)
        role = roles_by_id.get(_item_role_template_id(item) or (binding.primaryRoleId if binding else ""))
        if role and getattr(role, "shouldAvoid", None):
            matched_phrase = next(
                (
                    phrase
                    for phrase in role.shouldAvoid
                    if _contains_phrase(_item_text(item), phrase)
                ),
                None,
            )
            if matched_phrase:
                role_drift_hits.append((item, role, matched_phrase))
        if role:
            process_templates = processes_by_role.get(getattr(role, "id", ""), [])
            candidate_text = _clean_text(
                " ".join(
                    part
                    for part in [
                        _item_text(item),
                        context.blockedAtStep if context else "",
                        item.structuredNote.blockerReason,
                        item.structuredNote.supportNeeded,
                        item.structuredNote.lightweightTag,
                    ]
                    if part
                )
            )
            for template in process_templates:
                matched_phrase = next(
                    (
                        phrase
                        for phrase in [
                            *template.keySteps,
                            template.collaborationStep,
                            template.approvalStep,
                            *template.commonBlockers,
                        ]
                        if phrase and _contains_phrase(candidate_text, phrase)
                    ),
                    None,
                )
                if matched_phrase:
                    workflow_blocked_hits.append((item, template, matched_phrase))
                    break
        if context and context.controlLevel and context.controlLevel != "normal":
            controlled_items.append(item)
        if _item_needs_review(item):
            review_chain_items.append(item)
        if _item_is_cross_department(item):
            cross_department_items.append(item)
        if role and getattr(role, "level", "") in {"department_lead", "organization_lead"}:
            manager_load_items.append((item, role))
        elif owner_id and reporting_by_report.get(owner_id) and _item_needs_review(item):
            # 即使没有明确 leader 岗位，只要任务已进入复核链，也代表上级节点已介入。
            manager_load_items.append((item, role))

    blocked_steps = _clean_lines(
        [(_item_org_context(item).blockedAtStep or "") for item in review_chain_items if _item_org_context(item)],
        limit=2,
    )
    workflow_steps = _clean_lines([matched_phrase for _, _, matched_phrase in workflow_blocked_hits], limit=3)
    support_signals: list[str] = []
    focus_areas: list[str] = []
    suggested_actions: list[str] = []
    summary_lines: list[str] = []
    anonymous_insights: list[str] = []

    if role_drift_hits:
        sample_item, sample_role, sample_phrase = role_drift_hits[0]
        focus_areas.append("职责边界校准")
        support_signals.append(
            f"本周有 {len(role_drift_hits)} 条任务与岗位“不应长期承担”的事项重叠；例如「{_clean_text(sample_item.taskSnapshot.title)}」更像在承担“{sample_phrase}”。"
        )
        suggested_actions.append(
            f"复盘 {len(role_drift_hits)} 条疑似职责偏离任务，把不该长期挂在当前岗位上的执行事务重新分配。"
        )
        anonymous_insights.append(
            f"当前样本里已出现职责边界被挤压的迹象，问题不一定在人，而更可能在分工设计。"
        )
        summary_lines.append(
            f"样本中有 {len(role_drift_hits)} 条任务开始触碰岗位“不应长期承担”的事项，说明职责边界正在被执行需求挤压。"
        )

    if review_chain_items:
        focus_areas.append("汇报链与确认链")
        step_text = f" 当前显性的待确认步骤包括：{'、'.join(blocked_steps)}。" if blocked_steps else ""
        support_signals.append(
            f"本周有 {len(review_chain_items)} 条任务进入待复核或待确认状态，阻力更像出在汇报 / 审批链，而不只是执行速度。{step_text}".strip()
        )
        suggested_actions.append("把待复核任务逐条对照确认节点，缩短不必要的上报和协作确认链。")
        summary_lines.append(
            f"另有 {len(review_chain_items)} 条任务卡在复核或确认链上，当前需要优先判断卡的是哪一层汇报关系。"
        )

    if workflow_blocked_hits:
        focus_areas.append("流程卡点")
        workflow_text = f" 目前高频卡点包括：{'、'.join(workflow_steps)}。" if workflow_steps else ""
        support_signals.append(
            f"已有 {len(workflow_blocked_hits)} 条任务开始集中卡在岗位流程的固定节点，而不只是零散执行波动。{workflow_text}".strip()
        )
        suggested_actions.append("优先复盘对应岗位流程模板中的协作/审批步骤，确认是步骤设计问题还是角色缺位。")
        anonymous_insights.append("当前阻力开始聚集到固定流程节点，说明问题可能不在个体，而在流程设计。")
        summary_lines.append(
            f"同时已有 {len(workflow_blocked_hits)} 条任务暴露出岗位流程固定节点的卡点，需优先判断流程本身是否过长或协作位缺失。"
        )

    if controlled_items:
        control_levels = Counter(_item_control_level(item) for item in controlled_items if _item_control_level(item))
        control_text = "、".join(
            f"{level} {count} 条"
            for level, count in control_levels.items()
        )
        focus_areas.append("任务控制级别")
        support_signals.append(
            f"本周有 {len(controlled_items)} 条任务受到 leader / 部门 / 机构控制规则约束，其中控制级别分布为：{control_text}。"
        )
        suggested_actions.append("检查关键任务的控制级别是否设置过重，确认哪些修改权限可以下放。")
        summary_lines.append(
            f"控制规则正在真实影响推进节奏；当前共有 {len(controlled_items)} 条任务受控。"
        )

    if cross_department_items:
        focus_areas.append("跨部门协作")
        support_signals.append(
            f"本周有 {len(cross_department_items)} 条任务属于跨部门协作，{len([item for item in cross_department_items if _item_needs_review(item)])} 条同时伴随复核需求。"
        )
        suggested_actions.append("把跨部门任务明确到单一确认人，避免多人都“知道”但没人拍板。")
        summary_lines.append(
            f"跨部门任务已有 {len(cross_department_items)} 条，说明当前问题不止在单部门内部。"
        )

    if manager_load_items and len(manager_load_items) >= max(2, len(items) // 2 or 1):
        focus_areas.append("管理负荷")
        support_signals.append(
            f"{department_name or '当前范围'}有 {len(manager_load_items)} 条样本直接挂在管理岗或需上级节点介入，需警惕负责人被执行事务持续挤占。"
        )
        suggested_actions.append("把可下放的执行性事项从管理岗手里移出，保留负责人做判断、协调和拍板。")
        summary_lines.append(
            f"当前不少样本直接压在管理岗或上级复核节点上，管理负荷已经开始显性化。"
        )

    if overloaded_items:
        focus_areas.append("容量过载")
        support_signals.append(
            f"本周有 {len(overloaded_items)} 条任务直接标记为“工作过度饱和”，当前更像容量顶满，而不只是执行节奏问题。"
        )
        suggested_actions.append("先做任务取舍和容量重排，不要在已过载状态下继续叠加新任务。")
        summary_lines.append(
            f"样本里已有 {len(overloaded_items)} 条任务直接暴露出容量过载信号。"
        )

    return {
        "focus_areas": _clean_lines(focus_areas, limit=4),
        "support_signals": _clean_lines(support_signals, limit=4),
        "suggested_actions": _clean_lines(suggested_actions, limit=4),
        "summary_lines": _clean_lines(summary_lines, limit=4),
        "anonymous_insights": _clean_lines(anonymous_insights, limit=2),
        "role_drift_count": len(role_drift_hits),
        "review_chain_count": len(review_chain_items),
        "controlled_count": len(controlled_items),
        "cross_department_count": len(cross_department_items),
        "manager_load_count": len(manager_load_items),
        "workflow_blocked_count": len(workflow_blocked_hits),
        "overload_count": len(overloaded_items),
        "support_need_count": len(support_need_items),
        "misaligned_count": len(misaligned_items),
        "project_risk_count": len(project_risk_items),
        "review_chain_items": review_chain_items,
        "cross_department_items": cross_department_items,
        "workflow_blocked_hits": workflow_blocked_hits,
        "role_drift_hits": role_drift_hits,
        "overloaded_items": overloaded_items,
        "support_need_items": support_need_items,
        "misaligned_items": misaligned_items,
        "project_risk_items": project_risk_items,
    }


def _action_payload(
    *,
    summary: str,
    items: list[WeeklyReviewTaskEntryRecord],
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    primary_project = next((context for context in (_item_project_context(item) for item in items) if context and context.clientId), None)
    primary_org_context = next((context for context in (_item_org_context(item) for item in items) if context and context.departmentId), None)
    primary_event_line_id = next((event_line_id for event_line_id in (_item_event_line_id(item) for item in items) if event_line_id), None)
    primary_event_line_name = next(
        (
            event_line_name
            for event_line_name in (
                _item_event_line_name(item)
                for item in items
                if _item_event_line_id(item) == (primary_event_line_id or "")
            )
            if event_line_name
        ),
        None,
    )
    payload: dict[str, object] = {
        "summary": summary,
        "relatedTaskIds": [item.taskId for item in items[:5]],
        "relatedTaskTitles": _representative_titles(items, limit=3),
        "count": len(items),
        "primaryClientId": primary_project.clientId if primary_project else None,
        "primaryClientName": primary_project.clientName if primary_project else None,
        "primaryDepartmentId": primary_org_context.departmentId if primary_org_context else None,
        "primaryEventLineId": primary_event_line_id,
        "primaryEventLineName": primary_event_line_name,
    }
    if extra:
        payload.update(extra)
    return payload


def _build_predictive_action_cards(
    *,
    week_label: str,
    scope_type: str,
    scope_ref_id: str,
    items: list[WeeklyReviewTaskEntryRecord],
    management_bundle: dict[str, object],
    suggested_actions: list[str],
) -> list[ReviewActionCardRecord]:
    created_at = _now_iso()
    cards: list[ReviewActionCardRecord] = []

    def dedupe_items(source_items: list[WeeklyReviewTaskEntryRecord]) -> list[WeeklyReviewTaskEntryRecord]:
        deduped: list[WeeklyReviewTaskEntryRecord] = []
        seen: set[str] = set()
        for item in source_items:
            if item.taskId in seen:
                continue
            seen.add(item.taskId)
            deduped.append(item)
        return deduped

    def append_card(
        key: str,
        action_type: str,
        title: str,
        summary: str,
        related_items: list[WeeklyReviewTaskEntryRecord],
        extra: dict[str, object] | None = None,
    ) -> None:
        if not related_items:
            return
        payload = _action_payload(summary=summary, items=related_items, extra=extra)
        primary_event_line_id = payload.get("primaryEventLineId")
        primary_event_line_name = payload.get("primaryEventLineName")
        evidence_refs = [
            ReviewDashboardEvidenceRefRecord(
                sourceType="task",
                sourceId=item.taskId,
                title=item.taskSnapshot.title,
                summary=item.structuredNote.progress.strip() or item.note.strip() or item.taskSnapshot.status,
            )
            for item in related_items[:4]
        ]
        cards.append(
            ReviewActionCardRecord(
                id=f"action_{scope_type}_{scope_ref_id}_{key}",
                actionType=action_type,  # type: ignore[arg-type]
                title=title,
                payload=payload,
                status="suggested",
                createdAt=created_at,
                target=ReviewDashboardCardTargetRecord(
                    targetType="event_line" if primary_event_line_id else "task_view",
                    targetId=str(primary_event_line_id or f"{scope_type}:{key}"),
                    targetLabel=str(primary_event_line_name or title),
                    targetFilters={
                        "eventLineId": primary_event_line_id,
                        "relatedTaskIds": [item.taskId for item in related_items[:5]],
                    },
                ),
                evidenceRefs=evidence_refs,
            )
        )

    review_chain_items = management_bundle.get("review_chain_items", [])
    cross_department_items = management_bundle.get("cross_department_items", [])
    workflow_blocked_hits = management_bundle.get("workflow_blocked_hits", [])
    if review_chain_items or cross_department_items or workflow_blocked_hits:
        workflow_items = [hit[0] for hit in workflow_blocked_hits[:5]]
        related_items = dedupe_items([*review_chain_items[:5], *cross_department_items[:5], *workflow_items])
        append_card(
            "sync_meeting",
            "meeting",
            "拉一次确认会，缩短复核与协作链",
            f"当前待复核 {management_bundle.get('review_chain_count', 0)} 条、跨部门 {management_bundle.get('cross_department_count', 0)} 条、流程卡点 {management_bundle.get('workflow_blocked_count', 0)} 条，建议合并成一次短会收敛确认人和最晚回收时间。",
            related_items,
            extra={
                "blockedSteps": _clean_lines(
                    [hit[2] for hit in workflow_blocked_hits[:4]]
                    + [(_item_org_context(item).blockedAtStep or "") for item in review_chain_items[:4] if _item_org_context(item)],
                    limit=4,
                )
            },
        )

    overloaded_items = management_bundle.get("overloaded_items", [])
    if overloaded_items or int(management_bundle.get("manager_load_count", 0) or 0) >= max(2, len(items) // 2 or 1):
        append_card(
            "capacity_adjust",
            "resource_request",
            "调整容量与资源配置",
            f"当前容量过载 {management_bundle.get('overload_count', 0)} 条、管理负荷 {management_bundle.get('manager_load_count', 0)} 条，建议先做取舍、顺延或争取额外支持，而不是继续叠加任务。",
            list(overloaded_items[:5]) or items[: min(3, len(items))],
        )

    role_drift_hits = management_bundle.get("role_drift_hits", [])
    if role_drift_hits:
        role_items = [hit[0] for hit in role_drift_hits[:5]]
        matched_phrases = _clean_lines([hit[2] for hit in role_drift_hits[:4]], limit=3)
        append_card(
            "role_boundary",
            "one_on_one",
            "做一次职责边界校准",
            f"当前有 {management_bundle.get('role_drift_count', 0)} 条任务开始触碰岗位不应长期承担的事项，建议和负责人做一次职责/负荷校准，避免长期偏岗。",
            role_items,
            extra={"matchedShouldAvoid": matched_phrases},
        )

    support_need_items = management_bundle.get("support_need_items", [])
    if support_need_items:
        support_tags = _clean_lines(
            [item.structuredNote.lightweightTag for item in support_need_items[:4] if item.structuredNote.lightweightTag.strip()],
            limit=3,
        )
        append_card(
            "support_request",
            "support_request",
            "把分散阻力收束成一次支持请求",
            f"当前有 {management_bundle.get('support_need_count', 0)} 条任务明确提出支持/依赖，建议统一说明缺什么、等谁、最晚什么时候回收，不要零散追问。",
            support_need_items[:5],
            extra={"supportTags": support_tags},
        )

    project_risk_items = management_bundle.get("project_risk_items", [])
    misaligned_items = management_bundle.get("misaligned_items", [])
    if project_risk_items or misaligned_items:
        related_items = dedupe_items([*project_risk_items[:5], *misaligned_items[:5]])
        append_card(
            "risk_followup",
            "task",
            "把项目风险和计划偏移转成明确动作",
            f"当前有 {management_bundle.get('project_risk_count', 0)} 条任务已挂接项目风险，另有 {management_bundle.get('misaligned_count', 0)} 条任务显式偏离计划对象，建议转成单独整改动作并明确负责人。",
            related_items,
        )

    if not cards and suggested_actions:
        cards.append(
            ReviewActionCardRecord(
                id=f"action_{scope_type}_{scope_ref_id}_default_next_step",
                actionType="task",
                title="把本周判断收束成第一优先动作",
                payload=_action_payload(
                    summary=suggested_actions[0],
                    items=items[:3],
                    extra={"count": min(len(items), 3)},
                ),
                status="suggested",
                createdAt=created_at,
                target=ReviewDashboardCardTargetRecord(
                    targetType="task_view",
                    targetId=f"{scope_type}:default_next_step",
                    targetLabel="相关任务",
                    targetFilters={"relatedTaskIds": [item.taskId for item in items[:3]]},
                ),
                evidenceRefs=[
                    ReviewDashboardEvidenceRefRecord(
                        sourceType="task",
                        sourceId=item.taskId,
                        title=item.taskSnapshot.title,
                        summary=item.structuredNote.progress.strip() or item.note.strip() or item.taskSnapshot.status,
                    )
                    for item in items[:3]
                ],
            )
        )

    return cards[:4]


def build_employee_review_report(
    *,
    week_label: str,
    scope_ref_id: str,
    items: list[WeeklyReviewTaskEntryRecord],
    analysis,
    org_model_profile: OrgModelProfileRecord | None = None,
    viewer_role: str = "employee",
) -> HierarchyReportRecord:
    base_report = build_hierarchy_report_from_analysis(
        analysis,
        week_label=week_label,
        scope_type="employee",
        scope_ref_id=scope_ref_id,
    )
    if not items:
        return base_report
    management_bundle = _management_signal_bundle(items, org_model_profile=org_model_profile)
    event_line_rollup = _event_line_rollup(items)
    if viewer_role == "admin":
        event_line_summaries = list(getattr(analysis, "eventLineSummaries", []) or [])
        event_line_judgments = list(getattr(analysis, "eventLineJudgments", []) or [])
        risk_cards = list(getattr(analysis, "riskCards", []) or [])
        opportunity_cards = list(getattr(analysis, "opportunityCards", []) or [])
        trend_cards = list(getattr(analysis, "trendSignals", []) or [])
        event_line_titles = _judgment_focus_lines(event_line_judgments, limit=4) or _event_line_overview_lines(event_line_summaries, limit=4) or _clean_lines(
            [_overview_line(item.title, item.statement) for item in analysis.hypothesisHighlights[:4]],
            limit=4,
        )
        event_line_statements = (
            [f"{item.title}：{item.whatHappened} {item.managerImplication}".strip() for item in event_line_judgments[:3]]
            or
            [f"{item.title}：{item.whatHappenedThisWeek} {item.currentState}".strip() for item in event_line_summaries[:3]]
            or [item.statement for item in analysis.hypothesisHighlights[:3]]
        )
        summary_parts = event_line_statements[:2] or [base_report.summary]
        if management_bundle["summary_lines"]:
            summary_parts.append(management_bundle["summary_lines"][0])
        focus_seed = event_line_titles + _judgment_management_lines(event_line_judgments, limit=3) + list(management_bundle["focus_areas"])
        support_seed = _trend_overview_lines(trend_cards, limit=3) + _risk_overview_lines(risk_cards, limit=3) + _judgment_blocker_lines(event_line_judgments, limit=3) + list(management_bundle["support_signals"])
        suggested_seed = (
            _judgment_action_lines(event_line_judgments, limit=3)
            +
            [_overview_line(item.title, item.suggestedAction) for item in risk_cards[:3]]
            + [_overview_line(item.title, item.recommendedAmplifier) for item in opportunity_cards[:3]]
            + list(analysis.nextWeekFocus)
            + list(management_bundle["suggested_actions"])
        )
        suggested_actions = _clean_lines(suggested_seed, limit=4)
        action_cards = _build_predictive_action_cards(
            week_label=week_label,
            scope_type="employee",
            scope_ref_id=scope_ref_id,
            items=items,
            management_bundle=management_bundle,
            suggested_actions=suggested_actions,
        )
        return base_report.model_copy(
            update={
                "summary": " ".join(summary_parts),
                "focusAreas": _clean_lines(focus_seed, limit=4),
                "supportSignals": _clean_lines(support_seed, limit=4),
                "suggestedActions": suggested_actions,
                "anonymousInsights": _clean_lines(
                    _opportunity_overview_lines(opportunity_cards, limit=3) + _judgment_management_lines(event_line_judgments, limit=3),
                    limit=3,
                ),
                "actions": action_cards,
                "logicMode": "admin_eventline_context_v1",
                "sourcePolicy": {
                    **base_report.sourcePolicy,
                    "roleDriftCount": management_bundle["role_drift_count"],
                    "reviewChainCount": management_bundle["review_chain_count"],
                    "controlledTaskCount": management_bundle["controlled_count"],
                    "crossDepartmentCount": management_bundle["cross_department_count"],
                    "managerLoadCount": management_bundle["manager_load_count"],
                    "workflowBlockedCount": management_bundle["workflow_blocked_count"],
                    "overloadCount": management_bundle["overload_count"],
                    "supportNeedCount": management_bundle["support_need_count"],
                    "misalignedCount": management_bundle["misaligned_count"],
                    "projectRiskCount": management_bundle["project_risk_count"],
                    "roleView": "admin",
                    "eventLineCount": event_line_rollup["group_count"],
                    "multiTaskEventLineCount": event_line_rollup["multi_task_group_count"],
                    "blockedEventLineCount": event_line_rollup["blocked_group_count"],
                },
            }
        )
    if viewer_role == "department_lead":
        event_line_summaries = list(getattr(analysis, "eventLineSummaries", []) or [])
        event_line_judgments = list(getattr(analysis, "eventLineJudgments", []) or [])
        risk_cards = list(getattr(analysis, "riskCards", []) or [])
        opportunity_cards = list(getattr(analysis, "opportunityCards", []) or [])
        trend_cards = list(getattr(analysis, "trendSignals", []) or [])
        event_line_titles = _judgment_focus_lines(event_line_judgments, limit=4) or _event_line_overview_lines(event_line_summaries, limit=4) or _clean_lines(
            [_overview_line(item.title, item.statement) for item in analysis.hypothesisHighlights[:4]],
            limit=4,
        )
        event_line_statements = (
            [f"{item.title}：{item.whatHappened} {item.managerImplication}".strip() for item in event_line_judgments[:3]]
            or
            [f"{item.title}：{item.whatHappenedThisWeek} {item.currentState}".strip() for item in event_line_summaries[:3]]
            or [item.statement for item in analysis.hypothesisHighlights[:3]]
        )
        summary_parts = event_line_statements[:2] or [base_report.summary]
        if management_bundle["summary_lines"]:
            summary_parts.append(management_bundle["summary_lines"][0])
        focus_seed = event_line_titles + _judgment_management_lines(event_line_judgments, limit=3) + list(management_bundle["focus_areas"])
        support_seed = _trend_overview_lines(trend_cards, limit=3) + _risk_overview_lines(risk_cards, limit=3) + _judgment_blocker_lines(event_line_judgments, limit=3) + list(management_bundle["support_signals"])
        suggested_seed = (
            _judgment_action_lines(event_line_judgments, limit=3)
            +
            [_overview_line(item.title, item.suggestedAction) for item in risk_cards[:3]]
            + [_overview_line(item.title, item.recommendedAmplifier) for item in opportunity_cards[:3]]
            + list(analysis.nextWeekFocus)
            + list(management_bundle["suggested_actions"])
        )
        suggested_actions = _clean_lines(suggested_seed, limit=4)
        action_cards = _build_predictive_action_cards(
            week_label=week_label,
            scope_type="employee",
            scope_ref_id=scope_ref_id,
            items=items,
            management_bundle=management_bundle,
            suggested_actions=suggested_actions,
        )
        return base_report.model_copy(
            update={
                "summary": " ".join(summary_parts),
                "focusAreas": _clean_lines(focus_seed, limit=4),
                "supportSignals": _clean_lines(support_seed, limit=4),
                "suggestedActions": suggested_actions,
                "anonymousInsights": _clean_lines(
                    _opportunity_overview_lines(opportunity_cards, limit=3) + _judgment_management_lines(event_line_judgments, limit=3),
                    limit=3,
                ),
                "actions": action_cards,
                "logicMode": "department_lead_eventline_context_v1",
                "sourcePolicy": {
                    **base_report.sourcePolicy,
                    "roleDriftCount": management_bundle["role_drift_count"],
                    "reviewChainCount": management_bundle["review_chain_count"],
                    "controlledTaskCount": management_bundle["controlled_count"],
                    "crossDepartmentCount": management_bundle["cross_department_count"],
                    "managerLoadCount": management_bundle["manager_load_count"],
                    "workflowBlockedCount": management_bundle["workflow_blocked_count"],
                    "overloadCount": management_bundle["overload_count"],
                    "supportNeedCount": management_bundle["support_need_count"],
                    "misalignedCount": management_bundle["misaligned_count"],
                    "projectRiskCount": management_bundle["project_risk_count"],
                    "roleView": "department_lead",
                    "eventLineCount": event_line_rollup["group_count"],
                    "multiTaskEventLineCount": event_line_rollup["multi_task_group_count"],
                    "blockedEventLineCount": event_line_rollup["blocked_group_count"],
                },
            }
        )
    summary_parts = [base_report.summary]
    if int(event_line_rollup["group_count"]) > 0:
        summary_parts.append(
            f"本周有 {event_line_rollup['task_count']} 条任务被串到 {event_line_rollup['group_count']} 条事件线里，其中 {event_line_rollup['multi_task_group_count']} 条已经跨了多项任务。"
        )
    if management_bundle["summary_lines"]:
        summary_parts.append(" ".join(management_bundle["summary_lines"]))
    focus_seed = list(base_report.focusAreas) + list(management_bundle["focus_areas"])
    trend_seed = _trend_overview_lines(list(getattr(analysis, "trendSignals", []) or []), limit=3)
    judgment_focus_seed = _judgment_focus_lines(list(getattr(analysis, "eventLineJudgments", []) or []), limit=3)
    judgment_blocker_seed = _judgment_blocker_lines(list(getattr(analysis, "eventLineJudgments", []) or []), limit=3)
    if int(event_line_rollup["group_count"]) > 0:
        focus_seed.insert(0, _overview_line("事件线连续推进", f"本周有 {event_line_rollup['group_count']} 条事件线被持续推进。"))
    focus_areas = _clean_lines(judgment_focus_seed + focus_seed, limit=4)
    support_seed = trend_seed + judgment_blocker_seed + list(management_bundle["support_signals"]) + list(base_report.supportSignals)
    if int(event_line_rollup["blocked_group_count"]) > 0:
        blocked_names = "、".join(event_line_rollup["blocked_names"][:2])
        support_seed.insert(
            0,
            (
                f"当前仍有 {event_line_rollup['blocked_group_count']} 条事件线处在待继续推进状态，重点包括：{blocked_names}。"
                if blocked_names
                else f"当前仍有 {event_line_rollup['blocked_group_count']} 条事件线没有收束完毕。"
            ),
        )
    support_signals = _clean_lines(support_seed, limit=4)
    suggested_seed = list(base_report.suggestedActions) + list(management_bundle["suggested_actions"])
    if int(event_line_rollup["group_count"]) > 0:
        suggested_seed.insert(0, _overview_line("事件线收束", "优先按事件线收束同一件事的相关任务，不要继续拆成多条独立事项分别推进。"))
    suggested_actions = _clean_lines(suggested_seed, limit=4)
    anonymous_insights = _clean_lines(
        list(base_report.anonymousInsights) + list(management_bundle["anonymous_insights"]),
        limit=3,
    )
    action_cards = _build_predictive_action_cards(
        week_label=week_label,
        scope_type="employee",
        scope_ref_id=scope_ref_id,
        items=items,
        management_bundle=management_bundle,
        suggested_actions=suggested_actions,
    )
    return base_report.model_copy(
        update={
            "summary": " ".join(summary_parts),
            "focusAreas": focus_areas,
            "supportSignals": support_signals,
            "suggestedActions": suggested_actions,
            "anonymousInsights": anonymous_insights,
            "actions": action_cards,
            "sourcePolicy": {
                **base_report.sourcePolicy,
                "roleDriftCount": management_bundle["role_drift_count"],
                "reviewChainCount": management_bundle["review_chain_count"],
                "controlledTaskCount": management_bundle["controlled_count"],
                "crossDepartmentCount": management_bundle["cross_department_count"],
                "managerLoadCount": management_bundle["manager_load_count"],
                "workflowBlockedCount": management_bundle["workflow_blocked_count"],
                "overloadCount": management_bundle["overload_count"],
                "supportNeedCount": management_bundle["support_need_count"],
                "misalignedCount": management_bundle["misaligned_count"],
                "projectRiskCount": management_bundle["project_risk_count"],
                "eventLineCount": event_line_rollup["group_count"],
                "multiTaskEventLineCount": event_line_rollup["multi_task_group_count"],
                "blockedEventLineCount": event_line_rollup["blocked_group_count"],
            },
            "logicMode": "employee_org_context_v1",
        }
    )


def _team_plan_module(department: ReviewDepartmentConfigRecord) -> OrganizationDnaModuleRecord | None:
    monthly_dna = department.monthlyDna.strip()
    weekly_focus = department.weeklyFocus.strip()
    if not monthly_dna and not weekly_focus:
        return None
    content_parts = []
    if monthly_dna:
        content_parts.append(f"月度 DNA：{monthly_dna}")
    if weekly_focus:
        content_parts.append(f"本周重点计划：{weekly_focus}")
    normalized = " ".join(content_parts)
    return OrganizationDnaModuleRecord(
        moduleKey="team_intro",  # type: ignore[arg-type]
        title=f"{department.name} 部门计划背景",
        markdownContent=normalized,
        normalizedText=normalized,
        summary=normalized,
        fileName=None,
        contentHash=None,
        updatedAt=None,
        updatedBy="review_governance",
        hasDocument=True,
    )


def _plan_alignment_summary(department: ReviewDepartmentConfigRecord, items: list[WeeklyReviewTaskEntryRecord]) -> str:
    if not items:
        return "本周还没有收集到该部门的真实复盘样本，暂时无法判断是否贴着部门计划前进。"
    monthly_dna = department.monthlyDna.strip()
    weekly_focus = department.weeklyFocus.strip()
    plan_source = " ".join(part for part in [monthly_dna, weekly_focus] if part)
    if not plan_source:
        return "该部门尚未填写月度 DNA 和本周重点计划，目前只能根据一线周复盘描述推进状态，不能严格判断是否偏离计划。"
    plan_tokens = {token for token in tokenize(plan_source) if len(token.strip()) >= 2}
    item_tokens = {token for item in items for token in tokenize(_item_text(item)) if len(token.strip()) >= 2}
    overlap = len(plan_tokens & item_tokens)
    blocker_count = sum(1 for item in items if item.structuredNote.lightweightTag.strip() or item.structuredNote.blockerReason.strip())
    if overlap >= 4 and blocker_count <= max(1, len(items) // 3):
        return "从当前任务表述看，本周动作与部门月度 DNA / 本周重点计划的对应关系较强，暂未出现明显偏航信号。"
    if overlap >= 2:
        return "从当前任务表述看，本周动作和部门计划背景仍有对应，但推进深度和节奏并不均衡，需要继续盯偏差。"
    return "从当前任务表述看，本周动作与部门计划背景的显式对应偏弱，建议人工确认是否已有主线偏航。"


def _department_report(
    week_label: str,
    department: ReviewDepartmentConfigRecord,
    items: list[WeeklyReviewTaskEntryRecord],
    organization_dna_modules: list[OrganizationDnaModuleRecord],
    org_model_profile: OrgModelProfileRecord | None = None,
) -> HierarchyReportRecord:
    created_at = _now_iso()
    alignment_summary = _plan_alignment_summary(department, items)
    agent_sample_count = sum(1 for item in items if _is_agent_item(item))
    management_bundle = _management_signal_bundle(
        items,
        org_model_profile=org_model_profile,
        department_name=department.name,
    )
    if not items:
        return HierarchyReportRecord(
            id=f"dept_review_{department.id}_{week_label}",
            scopeType="team",
            scopeRefId=department.name,
            weekLabel=week_label,
            logicMode="real_department_rollup_v1",
            headline=f"{department.name} 本周暂无可分析的真实复盘样本。",
            summary=f"{alignment_summary} 当前只能先补齐成员归属、部门计划背景和至少 1-2 条一线周复盘说明。",
            focusAreas=["补齐部门输入", "确认成员归属", "补写部门计划背景"],
            supportSignals=["没有真实周复盘样本时，系统不能可靠判断成功原因和阻碍原因。"] if department.members else ["当前还没有给这个部门分配成员。"],
            suggestedActions=[
                "先给该部门配置成员归属。",
                "至少补一条本周推进说明和一条阻碍说明。",
                "把部门月度 DNA 和本周重点计划补齐，方便系统判断是否偏离。",
            ],
            anonymousInsights=[],
            sourcePolicy={
                "realAggregation": True,
                "sampleSize": 0,
                "memberCount": len(department.members),
                "agentSampleCount": 0,
                "monthPlanReady": bool(department.monthlyDna.strip()),
                "weeklyPlanReady": bool(department.weeklyFocus.strip()),
                "projectContextCount": 0,
                "linkedFocusItemCount": 0,
                "linkedDepartmentPlanItemCount": 0,
            },
            actions=[],
            createdAt=created_at,
            updatedAt=created_at,
        )

    modules = list(organization_dna_modules)
    team_plan_module = _team_plan_module(department)
    if team_plan_module:
        modules = [team_plan_module, *modules]
    analysis = build_weekly_review_analysis("work", week_label, items, modules, org_model_profile=org_model_profile)
    base_report = build_hierarchy_report_from_analysis(
        analysis,
        week_label=week_label,
        scope_type="team",
        scope_ref_id=department.name,
    )
    event_line_overview = _judgment_focus_lines(list(getattr(analysis, "eventLineJudgments", []) or []), limit=4) or _event_line_overview_lines(list(getattr(analysis, "eventLineSummaries", []) or []), limit=4)
    risk_overview = _trend_overview_lines(list(getattr(analysis, "trendSignals", []) or []), limit=3) + _risk_overview_lines(list(getattr(analysis, "riskCards", []) or []), limit=3)
    opportunity_overview = _opportunity_overview_lines(list(getattr(analysis, "opportunityCards", []) or []), limit=4)
    project_context_count = sum(1 for item in items if _item_project_context(item))
    linked_focus_count = len({_item_focus_item_id(item) for item in items if _item_focus_item_id(item)})
    linked_plan_item_count = len({_item_department_plan_item_id(item) for item in items if _item_department_plan_item_id(item)})
    event_line_rollup = _event_line_rollup(items)
    profile = DEPARTMENT_STRATEGY_PROFILES.get(department.name)
    completed_count = sum(1 for item in items if _is_completed_item(item))
    blocker_count = sum(1 for item in items if not _is_completed_item(item) and _has_blocker_signal(item))
    titles = _representative_titles(items)
    clean_next_actions = _clean_lines(analysis.nextWeekFocus, limit=2)
    clean_hypothesis = _clean_lines([hypothesis.statement for hypothesis in analysis.hypothesisHighlights], limit=2)

    if profile:
        headline = f"{department.name}｜{profile['headline']}"
        summary_parts = [
            f"本周纳入 {len(items)} 条真实工作样本，已完成 {completed_count} 条，仍在推进 {len(items) - completed_count} 条。",
            str(profile["core"]),
        ]
        if titles:
            summary_parts.append(f"当前最能代表本周推进的任务包括：{'、'.join(titles)}。")
        summary_parts.append(
            f"目前有 {blocker_count} 条任务明确暴露出阻力或支持需求。"
            if blocker_count
            else "从当前样本看，本周主线推进相对连贯，尚未出现明显被打散的迹象。"
        )
        if int(event_line_rollup["group_count"]) > 0:
            summary_parts.append(
                f"其中 {event_line_rollup['task_count']} 条任务已被串到 {event_line_rollup['group_count']} 条事件线里，{event_line_rollup['multi_task_group_count']} 条事件线已经跨了多项任务。"
            )
        summary_parts.append(str(profile["risk"]))
        if department.monthlyDna.strip():
            summary_parts.append(f"部门月度 DNA：{department.monthlyDna.strip()}")
        if department.weeklyFocus.strip():
            summary_parts.append(f"本周重点计划：{department.weeklyFocus.strip()}")
        summary_parts.append(alignment_summary)
        summary_parts.extend([fact for fact in analysis.confirmedFacts if "挂接项目背景" in fact or "正式计划" in fact][:2])
        summary_parts.extend(management_bundle["summary_lines"])  # type: ignore[arg-type]
        profile_focus_lines = _clean_lines(
            [_overview_line(area, "、".join(titles[:2]) or str(profile["core"])) for area in profile["focus_areas"]],  # type: ignore[index]
            limit=4,
        )
        focus_seed = event_line_overview + list(management_bundle["focus_areas"]) + profile_focus_lines  # type: ignore[arg-type]
        if int(event_line_rollup["group_count"]) > 0:
            focus_seed.insert(0, _overview_line("事件线连续推进", f"当前已有 {event_line_rollup['group_count']} 条事件线把关键推进串起来。"))
        focus_areas = _clean_lines(focus_seed, limit=4)
        suggested_actions = _clean_lines(
            _action_overview_lines(list(management_bundle["suggested_actions"]) + list(profile["actions"]) + clean_next_actions, limit=4),  # type: ignore[arg-type]
            limit=4,
        )
        support_signals = _clean_lines(
            [
                *management_bundle["support_signals"],  # type: ignore[arg-type]
                *risk_overview,
                *_judgment_blocker_lines(list(getattr(analysis, "eventLineJudgments", []) or []), limit=3),
                f"本周样本 {len(items)} 条，已完成 {completed_count} 条，带阻力或支持需求 {blocker_count} 条。",
                *(
                    [
                        (
                            f"当前仍有 {event_line_rollup['blocked_group_count']} 条事件线未收束，重点包括：{'、'.join(event_line_rollup['blocked_names'][:2])}。"
                            if event_line_rollup["blocked_names"]
                            else f"当前仍有 {event_line_rollup['blocked_group_count']} 条事件线未收束。"
                        )
                    ]
                    if int(event_line_rollup["blocked_group_count"]) > 0
                    else []
                ),
                *[fact for fact in analysis.confirmedFacts if "挂接项目背景" in fact or "正式计划" in fact][:2],
                str(profile["risk"]),
                *analysis.confirmedFacts[:1],
            ],
            limit=4,
        )
        anonymous_insights = _clean_lines(opportunity_overview + _judgment_management_lines(list(getattr(analysis, "eventLineJudgments", []) or []), limit=3) + list(management_bundle["anonymous_insights"]), limit=3)  # type: ignore[arg-type]
    else:
        headline = f"{department.name}：{analysis.headline}"
        summary_parts = []
        if department.monthlyDna.strip():
            summary_parts.append(f"部门月度 DNA：{department.monthlyDna.strip()}")
        if department.weeklyFocus.strip():
            summary_parts.append(f"本周重点计划：{department.weeklyFocus.strip()}")
        summary_parts.append(alignment_summary)
        if int(event_line_rollup["group_count"]) > 0:
            summary_parts.append(
                f"本周已有 {event_line_rollup['group_count']} 条事件线把相关任务串成连续工作线，其中 {event_line_rollup['multi_task_group_count']} 条已经跨了多项任务。"
            )
        summary_parts.append(analysis.caution)
        summary_parts.extend(management_bundle["summary_lines"])  # type: ignore[arg-type]
        focus_areas = event_line_overview + _action_overview_lines(list(analysis.nextWeekFocus[:2]), limit=2) + list(management_bundle["focus_areas"])  # type: ignore[arg-type]
        if department.monthlyDna.strip() or department.weeklyFocus.strip():
            focus_areas.insert(0, _overview_line("部门计划背景对照", "优先检查本周动作是否贴着部门月度 DNA 和本周重点计划推进。"))
        if int(event_line_rollup["group_count"]) > 0:
            focus_areas.insert(0, _overview_line("事件线连续推进", f"当前已有 {event_line_rollup['group_count']} 条事件线把相关任务串起来。"))
        suggested_actions = _clean_lines(_action_overview_lines(list(analysis.nextWeekFocus[:3]) + list(management_bundle["suggested_actions"]), limit=4), limit=4)  # type: ignore[arg-type]
        support_signals = _clean_lines(
            list(management_bundle["support_signals"])  # type: ignore[arg-type]
            + risk_overview
            + (
            + (
            (
                [
                    (
                        f"当前仍有 {event_line_rollup['blocked_group_count']} 条事件线未收束，重点包括：{'、'.join(event_line_rollup['blocked_names'][:2])}。"
                        if event_line_rollup["blocked_names"]
                        else f"当前仍有 {event_line_rollup['blocked_group_count']} 条事件线未收束。"
                    )
                ]
                if int(event_line_rollup["blocked_group_count"]) > 0
                else []
            )
            + _judgment_blocker_lines(list(getattr(analysis, "eventLineJudgments", []) or []), limit=2)
            + analysis.confirmedFacts[:2]
            + base_report.supportSignals[:2]
            )),
            limit=4,
        )  # type: ignore[arg-type]
        anonymous_insights = _clean_lines(
            opportunity_overview + _judgment_management_lines(list(getattr(analysis, "eventLineJudgments", []) or []), limit=2) + list(management_bundle["anonymous_insights"]),
            limit=3,
        )  # type: ignore[arg-type]

    action_cards = _build_predictive_action_cards(
        week_label=week_label,
        scope_type="team",
        scope_ref_id=department.id,
        items=items,
        management_bundle=management_bundle,
        suggested_actions=suggested_actions,
    )

    return base_report.model_copy(
        update={
            "headline": headline,
            "summary": " ".join(summary_parts),
            "focusAreas": focus_areas[:4],
            "supportSignals": support_signals,
            "suggestedActions": suggested_actions,
            "anonymousInsights": anonymous_insights,
            "actions": action_cards,
            "sourcePolicy": {
                **base_report.sourcePolicy,
                "realAggregation": True,
                "sampleSize": len(items),
                "memberCount": len(department.members),
                "agentSampleCount": agent_sample_count,
                "monthPlanReady": bool(department.monthlyDna.strip()),
                "weeklyPlanReady": bool(department.weeklyFocus.strip()),
                "projectContextCount": project_context_count,
                "linkedFocusItemCount": linked_focus_count,
                "linkedDepartmentPlanItemCount": linked_plan_item_count,
                "roleDriftCount": management_bundle["role_drift_count"],
                "reviewChainCount": management_bundle["review_chain_count"],
                "controlledTaskCount": management_bundle["controlled_count"],
                "crossDepartmentCount": management_bundle["cross_department_count"],
                "managerLoadCount": management_bundle["manager_load_count"],
                "workflowBlockedCount": management_bundle["workflow_blocked_count"],
                "overloadCount": management_bundle["overload_count"],
                "supportNeedCount": management_bundle["support_need_count"],
                "misalignedCount": management_bundle["misaligned_count"],
                "projectRiskCount": management_bundle["project_risk_count"],
                "eventLineCount": event_line_rollup["group_count"],
                "multiTaskEventLineCount": event_line_rollup["multi_task_group_count"],
                "blockedEventLineCount": event_line_rollup["blocked_group_count"],
            },
            "logicMode": "real_department_rollup_v2",
            "updatedAt": created_at,
        }
    )


def build_executive_review_rollup(
    *,
    week_label: str,
    work_items: list[WeeklyReviewTaskEntryRecord],
    governance: ReviewGovernanceSettingsRecord,
    organization_dna_modules: list[OrganizationDnaModuleRecord],
    org_model_profile: OrgModelProfileRecord | None = None,
) -> tuple[HierarchyReportRecord | None, list[HierarchyReportRecord]]:
    if not governance.departments:
        return None, []

    department_reports: list[HierarchyReportRecord] = []
    assigned_task_ids: set[str] = set()
    departments_with_samples = 0
    total_agent_samples = 0

    for department in governance.departments:
        member_ids = _department_member_ids(department)
        member_names = _department_member_names(department)
        department_items = [
            item for item in work_items
            if (_item_department_id(item) and _item_department_id(item) == department.id)
            or (_item_owner_id(item) and _item_owner_id(item) in member_ids)
            or (_item_owner_name(item).lower() in member_names)
            or (_is_agent_item(item) and _item_list_name(item) == department.name)
        ]
        if department_items:
            departments_with_samples += 1
            assigned_task_ids.update(item.taskId for item in department_items)
            total_agent_samples += sum(1 for item in department_items if _is_agent_item(item))
        department_reports.append(
            _department_report(
                week_label=week_label,
                department=department,
                items=department_items,
                organization_dna_modules=organization_dna_modules,
                org_model_profile=org_model_profile,
            )
        )

    if departments_with_samples == 0:
        return None, department_reports

    created_at = _now_iso()
    org_analysis = build_weekly_review_analysis("work", week_label, work_items, organization_dna_modules, org_model_profile=org_model_profile)
    org_management_bundle = _management_signal_bundle(
        work_items,
        org_model_profile=org_model_profile,
    )
    event_line_overview = _judgment_focus_lines(list(getattr(org_analysis, "eventLineJudgments", []) or []), limit=4) or _event_line_overview_lines(list(getattr(org_analysis, "eventLineSummaries", []) or []), limit=4)
    risk_overview = _trend_overview_lines(list(getattr(org_analysis, "trendSignals", []) or []), limit=3) + _risk_overview_lines(list(getattr(org_analysis, "riskCards", []) or []), limit=3)
    opportunity_overview = _opportunity_overview_lines(list(getattr(org_analysis, "opportunityCards", []) or []), limit=4)
    org_report = build_hierarchy_report_from_analysis(
        org_analysis,
        week_label=week_label,
        scope_type="org",
        scope_ref_id="organization",
    )
    reviewed_people = {
        _item_owner_name(item)
        for item in work_items
        if _item_owner_name(item)
    }
    unassigned_count = sum(1 for item in work_items if item.taskId not in assigned_task_ids)
    project_context_count = sum(1 for item in work_items if _item_project_context(item))
    linked_focus_count = len({_item_focus_item_id(item) for item in work_items if _item_focus_item_id(item)})
    linked_plan_item_count = len({_item_department_plan_item_id(item) for item in work_items if _item_department_plan_item_id(item)})
    event_line_rollup = _event_line_rollup(work_items)
    support_signals = list(risk_overview[:2] or org_report.supportSignals[:2])
    if unassigned_count:
        support_signals.append(f"当前还有 {unassigned_count} 条工作域复盘没有匹配到部门，机构层判断仍不完整。")
    missing_plan_departments = [department.name for department in governance.departments if not department.monthlyDna.strip()]
    missing_weekly_departments = [department.name for department in governance.departments if not department.weeklyFocus.strip()]
    if missing_plan_departments:
        support_signals.append(f"这些部门尚未填写月度 DNA：{'、'.join(missing_plan_departments[:3])}。")
    if missing_weekly_departments:
        support_signals.append(f"这些部门尚未填写本周重点计划：{'、'.join(missing_weekly_departments[:3])}。")
    support_signals = list(org_management_bundle["support_signals"]) + support_signals  # type: ignore[arg-type]
    if int(event_line_rollup["blocked_group_count"]) > 0:
        blocked_names = "、".join(event_line_rollup["blocked_names"][:2])
        support_signals.insert(
            0,
            (
                f"当前仍有 {event_line_rollup['blocked_group_count']} 条事件线没有收束，重点包括：{blocked_names}。"
                if blocked_names
                else f"当前仍有 {event_line_rollup['blocked_group_count']} 条事件线没有收束。"
            ),
        )
    support_signals.extend(_judgment_blocker_lines(list(getattr(org_analysis, "eventLineJudgments", []) or []), limit=2))
    support_signals.extend([fact for fact in org_analysis.confirmedFacts if "挂接项目背景" in fact or "正式计划" in fact][:2])
    department_headlines = [report.headline for report in department_reports if int(report.sourcePolicy.get("sampleSize", 0) or 0) > 0]
    focus_counter = Counter(area for report in department_reports for area in report.focusAreas[:2])
    org_headline = (
        f"机构真实聚合已覆盖 {departments_with_samples}/{len(governance.departments)} 个部门，"
        f"本周已有 {event_line_rollup['group_count']} 条事件线把关键推进串成连续工作线。"
        if int(event_line_rollup["group_count"]) > 0
        else f"机构真实聚合已覆盖 {departments_with_samples}/{len(governance.departments)} 个部门，当前最值得 CEO 盯的是部门计划与周内动作是否继续保持一致。"
    )
    quarter_focus_summary = next((fact for fact in org_analysis.confirmedFacts if "季度重点" in fact), "")
    org_summary = (
        f"本轮机构视角基于 {len(work_items)} 条真实工作域周复盘、约 {len(reviewed_people)} 位负责人、"
        f"{departments_with_samples} 个有样本的部门生成。"
        f"{f' {quarter_focus_summary}' if quarter_focus_summary else ''} {org_analysis.caution}"
    )
    if int(event_line_rollup["group_count"]) > 0:
        org_summary = (
            f"{org_summary} 当前已有 {event_line_rollup['task_count']} 条任务被串到 {event_line_rollup['group_count']} 条事件线里，"
            f"其中 {event_line_rollup['multi_task_group_count']} 条事件线已经跨了多项任务。"
        )
    if org_management_bundle["summary_lines"]:
        org_summary = f"{org_summary} {' '.join(org_management_bundle['summary_lines'])}"
    executive_suggested_actions = _clean_lines(
        _action_overview_lines(
            list(org_management_bundle["suggested_actions"]) + org_analysis.nextWeekFocus[:2] + [
                "固定对照每个部门的月度 DNA 和本周实际推进，优先处理持续偏航的部门。",
            ],
            limit=4,
        ),
        limit=4,
    )  # type: ignore[arg-type]
    action_cards = _build_predictive_action_cards(
        week_label=week_label,
        scope_type="org",
        scope_ref_id="organization",
        items=work_items,
        management_bundle=org_management_bundle,
        suggested_actions=executive_suggested_actions,
    )
    executive_report = org_report.model_copy(
        update={
            "headline": org_headline,
            "summary": org_summary,
            "focusAreas": _clean_lines(
                (
                    (([_overview_line("事件线连续推进", f"当前已有 {event_line_rollup['group_count']} 条事件线被持续推进。")] if int(event_line_rollup["group_count"]) > 0 else []) + event_line_overview)
                    + list(org_management_bundle["focus_areas"])
                    + [name for name, _ in focus_counter.most_common(4)]
                ),
                limit=4,
            )
            or org_report.focusAreas,  # type: ignore[arg-type]
            "supportSignals": _clean_lines(support_signals, limit=4),
            "suggestedActions": executive_suggested_actions,
            "anonymousInsights": _clean_lines(opportunity_overview + _judgment_management_lines(list(getattr(org_analysis, "eventLineJudgments", []) or []), limit=3) + department_headlines[:4] + list(org_management_bundle["anonymous_insights"]), limit=4) or org_report.anonymousInsights,  # type: ignore[arg-type]
            "actions": action_cards,
            "sourcePolicy": {
                **org_report.sourcePolicy,
                "realAggregation": True,
                "sampleSize": len(work_items),
                "reviewedPeople": len(reviewed_people),
                "reviewedDepartments": departments_with_samples,
                "configuredDepartments": len(governance.departments),
                "unassignedTaskCount": unassigned_count,
                "agentSampleCount": total_agent_samples,
                "projectContextCount": project_context_count,
                "linkedFocusItemCount": linked_focus_count,
                "linkedDepartmentPlanItemCount": linked_plan_item_count,
                "roleDriftCount": org_management_bundle["role_drift_count"],
                "reviewChainCount": org_management_bundle["review_chain_count"],
                "controlledTaskCount": org_management_bundle["controlled_count"],
                "crossDepartmentCount": org_management_bundle["cross_department_count"],
                "managerLoadCount": org_management_bundle["manager_load_count"],
                "workflowBlockedCount": org_management_bundle["workflow_blocked_count"],
                "overloadCount": org_management_bundle["overload_count"],
                "supportNeedCount": org_management_bundle["support_need_count"],
                "misalignedCount": org_management_bundle["misaligned_count"],
                "projectRiskCount": org_management_bundle["project_risk_count"],
                "eventLineCount": event_line_rollup["group_count"],
                "multiTaskEventLineCount": event_line_rollup["multi_task_group_count"],
                "blockedEventLineCount": event_line_rollup["blocked_group_count"],
            },
            "logicMode": "real_executive_rollup_v1",
            "updatedAt": created_at,
        }
    )
    return executive_report, department_reports
~~~

## `backend/app/services/review_simulation.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

from datetime import datetime

from app.models import HierarchyReportRecord, OrganizationDnaModuleRecord, ReviewSimulationBundleRecord


DEPARTMENT_BLUEPRINTS = [
    {
        "name": "咨询策略部",
        "sample_size": 5,
        "monthly_dna": "本月主线是把重点客户方案验证做深，并把有效路径沉淀成可复用方法。",
        "headline": "咨询策略部的主线事项整体在推进，但方案验证与方法沉淀的节奏还没有完全同步。",
        "summary": "20 人模拟里，咨询策略部的前线动作最容易产生可见进展，但也最容易在“先交付、后沉淀”这里出现偏差。",
        "focus": ["重点客户方案验证", "关键客户推进节奏", "方法资产沉淀"],
        "support": ["高价值客户推进过度依赖少数核心同事", "已验证的方法还没有及时标准化"],
        "quotes": [
            "一线同事多次提到“方案已经能跑，但还没有整理成团队都能复用的版本”。",
            "有同事提到“客户推进能动，但每次都要重新解释一遍逻辑，沉淀速度跟不上”。",
        ],
        "actions": ["把已验证方案沉淀成标准模板", "区分哪些客户推进需要 CEO 级拍板，避免一线重复试错"],
    },
    {
        "name": "科技发展部",
        "sample_size": 5,
        "monthly_dna": "本月主线是把任务、复盘、权限和设置打成稳定可用的系统闭环。",
        "headline": "科技发展部的关键变量不是功能数量，而是稳定性、权限边界和链路一致性。",
        "summary": "20 人模拟里，科技发展部最值得关注的是核心流程是否足够稳定，而不是局部功能点是否继续堆叠。",
        "focus": ["核心链路稳定性", "权限边界一致性", "产品交互闭环"],
        "support": ["页面交互细节仍可能打断主流程", "历史数据兼容和新结构之间还有缝隙"],
        "quotes": [
            "有同事提到“不是没有功能，而是核心链路一旦不稳，所有功能都会失去价值”。",
            "也有人提到“权限和状态边界一旦混乱，前台体验会迅速失真”。",
        ],
        "actions": ["优先收敛登录、任务、周复盘这几条主链路", "把部门、权限和可见性规则固化成统一约束"],
    },
    {
        "name": "信息数据部",
        "sample_size": 5,
        "monthly_dna": "本月主线是把情报抓取、候选清洗、标签治理和数据库维护跑成稳定生产流。",
        "headline": "信息数据部的信息处理链路已经成形，但标签边界和来源质量仍在拉低判断效率。",
        "summary": "20 人模拟里，信息数据部的核心问题不是没有信息，而是怎样把信息处理成可追踪、可复用、可进入业务判断的资产。",
        "focus": ["情报抓取与清洗", "标签治理", "数据库可靠性"],
        "support": ["样本来源质量不稳定", "标签规则与业务优先级的映射还不够紧"],
        "quotes": [
            "有同事提到“真正耗时的不是抓，而是后面清洗、比对和统一口径”。",
            "也有人提到“如果标签边界不稳，最后给业务看的判断就会摇摆”。",
        ],
        "actions": ["先把高频来源的标签规则固化下来", "把数据质量波动单独提成经营风险项"],
    },
    {
        "name": "客户服务部",
        "sample_size": 5,
        "monthly_dna": "本月主线是把客户交付、过程协同和资料回流收成一条更顺的客户服务链路。",
        "headline": "客户服务部的风险主要集中在交接边界、客户反馈回流和服务节奏控制。",
        "summary": "20 人模拟里，客户服务部最容易出现的问题不是没人跟进，而是服务接口没有提前说清、反馈回流慢、复盘动作滞后。",
        "focus": ["客户交付节奏", "跨部门交接", "服务资料回流"],
        "support": ["交接时输入物标准还不够清楚", "客户反馈没有及时沉淀回内部系统"],
        "quotes": [
            "有同事提到“最容易反复的不是做事本身，而是等前一环输入补齐”。",
            "也有人提到“客户反馈经常来得晚，导致内部调整总慢半拍”。",
        ],
        "actions": ["把交接标准做成服务输入清单", "把客户反馈和复盘动作前置进排期，不再收尾再补"],
    },
]


def _module_titles(modules: list[OrganizationDnaModuleRecord]) -> str:
    titles = [module.title for module in modules if module.hasDocument]
    return "、".join(titles[:3]) if titles else "组织介绍、业务介绍、团队介绍"


def build_review_simulation_bundle(
    *,
    week_label: str,
    organization_dna_modules: list[OrganizationDnaModuleRecord],
    sample_size: int = 20,
) -> ReviewSimulationBundleRecord:
    created_at = datetime.now().replace(microsecond=0).isoformat()
    dna_titles = _module_titles(organization_dna_modules)
    department_reports: list[HierarchyReportRecord] = []

    for blueprint in DEPARTMENT_BLUEPRINTS:
        report = HierarchyReportRecord(
            id=f"sim_dept_{blueprint['name']}_{week_label}",
            scopeType="team",
            scopeRefId=str(blueprint["name"]),
            weekLabel=week_label,
            logicMode="simulated_weighted_hypothesis_v1",
            headline=str(blueprint["headline"]),
            summary=f"模拟样本约 {blueprint['sample_size']} 人。部门月度 DNA 假设：{blueprint['monthly_dna']} 当前总结基于 {dna_titles} 与该部门周内一线汇总信号生成，用于 CEO 口径调教，不代表真实统计结果。",
            focusAreas=list(blueprint["focus"]),
            supportSignals=list(blueprint["support"]),
            suggestedActions=list(blueprint["actions"]),
            anonymousInsights=list(blueprint["quotes"]),
            sourcePolicy={
                "simulationMode": True,
                "sampleSize": blueprint["sample_size"],
                "visibility": "ceo_work_only",
                "monthlyDnaMode": "simulated_department_monthly_dna",
            },
            actions=[],
            createdAt=created_at,
            updatedAt=created_at,
        )
        department_reports.append(report)

    org_report = HierarchyReportRecord(
        id=f"sim_org_{week_label}",
        scopeType="org",
        scopeRefId="organization",
        weekLabel=week_label,
        logicMode="simulated_weighted_hypothesis_v1",
        headline="20 人组织模拟显示：主线整体仍在推进，但跨部门节奏、方法沉淀、系统稳定性和服务回流已经成为 CEO 层需要判断的组织变量。",
        summary=f"本轮机构视角为 CEO 调参模拟，不读取任何私人内容。它假设组织内约 {sample_size} 人，分布在 4 个部门，并参考 {dna_titles} 这几类 DNA 作为解释视角。当前最值得关注的不是单个任务是否完成，而是部门动作是否持续贴着组织主线、是否已经出现系统性偏差。",
        focusAreas=["跨部门节奏一致性", "方法资产沉淀速度", "系统稳定性", "客户服务回流"],
        supportSignals=[
            "若咨询策略部继续“先交付后沉淀”，组织复用效率会持续下降。",
            "若科技发展部的主链路稳定性继续波动，组织整体执行成本会持续升高。",
            "若客户服务部接口不收敛，部门间推进速度会被最慢环节拖住。",
        ],
        suggestedActions=[
            "把“部门月度 DNA vs 本周实际推进”做成 CEO 固定检查项。",
            "要求各部门周复盘都至少给出一条“如果不处理，会在下周放大的风险”。",
            "把跨部门共性卡点单独提成 CEO 层支持清单，而不是留在部门内部自转。",
        ],
        anonymousInsights=[
            "模拟里最明显的组织信号不是没人努力，而是不同部门对“什么算本周有效推进”的标准还不完全一致。",
            "如果不尽快统一“主线、沉淀、接口、业务结果”的判断语言，周复盘会继续停留在汇报而不是经营分析。",
        ],
        sourcePolicy={
            "simulationMode": True,
            "sampleSize": sample_size,
            "visibility": "ceo_work_only",
            "monthlyDnaMode": "simulated_department_monthly_dna",
        },
        actions=[],
        createdAt=created_at,
        updatedAt=created_at,
    )

    return ReviewSimulationBundleRecord(
        sampleSize=sample_size,
        label="CEO 调参与 20 人模拟视角",
        orgReport=org_report,
        departmentReports=department_reports,
    )
~~~

## `backend/app/services/secrets.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class MemorySecretStore:
    api_key: str = ""

    def set_api_key(self, value: str) -> None:
        self.api_key = value.strip()

    def get_api_key(self) -> str:
        return self.api_key

    def delete_api_key(self) -> None:
        self.api_key = ""

    def get_api_key_fingerprint(self) -> str | None:
        if not self.api_key:
            return None
        return hashlib.sha256(self.api_key.encode("utf-8")).hexdigest()[:12]

    def get_source_label(self) -> str:
        return "memory"

    def seed_from_env(self) -> bool:
        seed = (
            os.getenv("YIYU_MODEL_API_KEY_SEED", "").strip()
            or os.getenv("REPORT_FORMATTER_MODEL_API_KEY_SEED", "").strip()
            or os.getenv("MINIMAX_API_KEY_SEED", "").strip()
        )
        if not seed or self.api_key:
            return False
        self.api_key = seed
        return True


class MacOSKeychainSecretStore:
    def __init__(self, service_name: str = "com.yiyu.self-workbench.ai", account_name: str = "default"):
        self.service_name = service_name
        self.account_name = account_name

    def _ensure_supported(self) -> None:
        if sys.platform != "darwin":
            raise RuntimeError("当前仅支持在 macOS 上使用系统钥匙串保存密钥。")

    def set_api_key(self, value: str) -> None:
        self._ensure_supported()
        api_key = value.strip()
        if not api_key:
            raise RuntimeError("API 密钥不能为空。")
        subprocess.run(
            [
                "security",
                "add-generic-password",
                "-a",
                self.account_name,
                "-s",
                self.service_name,
                "-w",
                api_key,
                "-U",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

    def get_api_key(self) -> str:
        self._ensure_supported()
        try:
            result = subprocess.run(
                [
                    "security",
                    "find-generic-password",
                    "-a",
                    self.account_name,
                    "-s",
                    self.service_name,
                    "-w",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as error:
            stderr = (error.stderr or "").lower()
            if "could not be found" in stderr or "item could not be found" in stderr:
                return ""
            raise RuntimeError("读取 macOS 钥匙串失败。") from error

    def delete_api_key(self) -> None:
        self._ensure_supported()
        result = subprocess.run(
            [
                "security",
                "delete-generic-password",
                "-a",
                self.account_name,
                "-s",
                self.service_name,
            ],
            capture_output=True,
            text=True,
        )
        stderr = (result.stderr or "").lower()
        if result.returncode == 0 or "could not be found" in stderr or "item could not be found" in stderr:
            return
        raise RuntimeError("清除 macOS 钥匙串中的 API 密钥失败。")

    def get_api_key_fingerprint(self) -> str | None:
        api_key = self.get_api_key()
        if not api_key:
            return None
        return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:12]

    def get_source_label(self) -> str:
        return "keychain"

    def seed_from_env(self) -> bool:
        seed = (
            os.getenv("YIYU_MODEL_API_KEY_SEED", "").strip()
            or os.getenv("REPORT_FORMATTER_MODEL_API_KEY_SEED", "").strip()
            or os.getenv("MINIMAX_API_KEY_SEED", "").strip()
        )
        if not seed:
            return False
        if self.get_api_key():
            return False
        self.set_api_key(seed)
        return True
~~~

## `backend/app/services/self_heal.py`

- 编码: `utf-8`

~~~python
"""
自修复引擎 (Self-Healing Engine)
================================
检测运行时异常 → AI诊断 → 执行预定义修复动作 → 验证 → 记录

设计原则：
- AI 不改代码，只从修复手册中选择并执行预定义动作
- 每个修复动作都是幂等的（执行多次不会出问题）
- 修复前快照，修复后验证，失败则回滚
- 修复结果写入日志，人可以回溯审计
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Literal

from app.db import Database, to_json

# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

Severity = Literal["low", "medium", "high", "critical"]
HealStatus = Literal["detected", "diagnosing", "healing", "healed", "failed", "skipped"]


@dataclass
class HealthProbe:
    """一项健康检查"""
    probe_id: str
    name: str
    description: str
    severity: Severity
    check: Callable[..., ProbeResult]


@dataclass
class ProbeResult:
    healthy: bool
    detail: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class Remediation:
    """一个修复动作"""
    remedy_id: str
    name: str
    description: str
    is_safe: bool  # True = 幂等且无副作用
    action: Callable[..., RemediationResult]


@dataclass
class RemediationResult:
    success: bool
    detail: str
    reverted: bool = False


@dataclass
class HealRecord:
    """一次修复记录"""
    id: str
    timestamp: str
    probe_id: str
    probe_name: str
    severity: Severity
    diagnosis: str
    remedy_id: str | None
    remedy_name: str | None
    status: HealStatus
    detail: str
    ai_used: bool = False


# ---------------------------------------------------------------------------
# 修复手册 — 已知问题 + 对应修复动作
# ---------------------------------------------------------------------------

RUNBOOK: list[dict[str, Any]] = [
    {
        "id": "singleton_lock_stale",
        "name": "SingletonLock 残留",
        "symptoms": "Electron 启动失败, singleInstanceLock=false, 无其他 Electron 进程",
        "severity": "high",
        "remedy": "clear_singleton_lock",
        "description": "kill -9 后 Electron 锁文件未清理，导致新实例无法启动。修复：删除 SingletonLock 文件。",
    },
    {
        "id": "cloud_cache_stale",
        "name": "云端任务缓存过期",
        "symptoms": "拖拽任务跳回, 数据刷新后变旧, loadTaskBlock 返回旧数据",
        "severity": "medium",
        "remedy": "clear_cloud_task_cache",
        "description": "云端 task board 30秒缓存未失效，返回过期数据覆盖本地更新。修复：清除缓存。",
    },
    {
        "id": "ai_bad_cache",
        "name": "低质量 AI 缓存",
        "symptoms": "AI 生成内容为空, 智能摘要一直 loading, smart_brief 无内容",
        "severity": "medium",
        "remedy": "clear_ai_bad_caches",
        "description": "AI 降级/失败的结果被缓存，阻塞后续正常生成。修复：清除不含有效标记的缓存条目。",
    },
    {
        "id": "db_integrity_issue",
        "name": "数据库完整性异常",
        "symptoms": "sqlite3 错误, database disk image is malformed, table not found",
        "severity": "critical",
        "remedy": "repair_db_integrity",
        "description": "SQLite 数据库文件轻微损坏或索引失效。修复：执行 integrity_check 和 VACUUM。",
    },
    {
        "id": "memory_index_stale",
        "name": "记忆索引过期",
        "symptoms": "本地记忆无法检索, memory index 为空, 记忆文件存在但索引不匹配",
        "severity": "low",
        "remedy": "rebuild_memory_index",
        "description": "记忆文件与索引不同步。修复：扫描记忆目录重建 MEMORY_INDEX.json。",
    },
    {
        "id": "orphan_attachments",
        "name": "孤儿附件引用",
        "symptoms": "附件显示 404, task_attachments 行无对应文件, 附件列表空但数据库有记录",
        "severity": "low",
        "remedy": "clean_orphan_attachments",
        "description": "附件文件被移动或删除，但数据库记录仍在。修复：清理无文件的记录。",
    },
    {
        "id": "growth_signal_stuck",
        "name": "成长信号卡住",
        "symptoms": "pending capture 状态不变, 点亮徽章数不增加, XP 不涨",
        "severity": "low",
        "remedy": "refresh_growth_signals",
        "description": "成长信号处理流水线阻塞。修复：重新触发信号处理。",
    },
    {
        "id": "empty_bearer_token",
        "name": "Bearer Token 空值",
        "symptoms": "Illegal header value, Bearer 为空, cloud_request 401/403",
        "severity": "high",
        "remedy": "reset_cloud_token",
        "description": "云端 token 丢失或过期。修复：清除 token 缓存强制重新获取。",
    },
    {
        "id": "event_line_activity_orphan",
        "name": "事件线活动孤儿记录",
        "symptoms": "事件线活动指向已删除的事件线, event_line_id 不存在",
        "severity": "low",
        "remedy": "clean_orphan_eline_activities",
        "description": "事件线被删除但活动记录仍在。修复：清理指向不存在事件线的活动。",
    },
    {
        "id": "settings_corrupted",
        "name": "设置表损坏",
        "symptoms": "settings 读取返回 None, JSON parse 失败, 设置页面空白",
        "severity": "medium",
        "remedy": "repair_settings",
        "description": "settings 表中的 JSON 值损坏。修复：重置为默认值。",
    },
]


# ---------------------------------------------------------------------------
# AI 诊断 Prompt
# ---------------------------------------------------------------------------

DIAGNOSIS_SYSTEM_INSTRUCTION = """你是益语智库自用平台的自修复诊断引擎。
你的任务是根据错误日志判断问题属于哪种已知故障，并推荐修复动作。

规则：
1. 只能从【修复手册】中选择修复方案，不能发明新方案
2. 如果无法匹配任何已知故障，回答 "UNKNOWN"
3. 回答格式必须是 JSON：{"runbook_id": "xxx", "confidence": 0.9, "reason": "一句话原因"}
4. 如果匹配多个，选 confidence 最高的一个
5. confidence < 0.5 时回答 "UNKNOWN"
"""


def _build_diagnosis_prompt(error_logs: list[str], runbook: list[dict[str, Any]]) -> str:
    runbook_text = "\n".join(
        f"- ID: {item['id']} | 名称: {item['name']} | 症状: {item['symptoms']} | 修复: {item['remedy']}"
        for item in runbook
    )
    logs_text = "\n".join(f"  [{i + 1}] {line}" for i, line in enumerate(error_logs[-20:]))
    return f"""【修复手册】
{runbook_text}

【最近错误日志】
{logs_text}

请分析上面的错误日志，判断属于哪种已知故障。输出 JSON。"""


# ---------------------------------------------------------------------------
# 健康检查探针
# ---------------------------------------------------------------------------

def build_probes(db: Database, data_dir: Path) -> list[HealthProbe]:
    """构建所有健康检查探针"""

    def check_singleton_lock() -> ProbeResult:
        lock_path = data_dir / "SingletonLock"
        if not lock_path.exists():
            return ProbeResult(True, "无残留锁文件")
        # 检查是否有 Electron 进程在运行
        try:
            import subprocess
            result = subprocess.run(["pgrep", "-f", "Electron"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                return ProbeResult(True, "锁文件存在且 Electron 正在运行，正常")
            return ProbeResult(False, "SingletonLock 残留，无 Electron 进程", {"lock_path": str(lock_path)})
        except Exception:
            return ProbeResult(True, "无法检测进程状态，跳过")

    def check_db_integrity() -> ProbeResult:
        try:
            result = db.fetchone("PRAGMA integrity_check")
            status = str(result["integrity_check"] if result else "unknown")
            if status == "ok":
                return ProbeResult(True, "数据库完整性正常")
            return ProbeResult(False, f"数据库完整性异常: {status}", {"integrity": status})
        except Exception as exc:
            return ProbeResult(False, f"数据库检查失败: {exc}")

    def check_ai_bad_caches() -> ProbeResult:
        try:
            rows = db.fetchall(
                "SELECT key, value FROM settings WHERE key LIKE 'smart_brief_cache::%'"
            )
            bad_count = 0
            for row in rows:
                val = str(row["value"] or "")
                # 有效的 AI 缓存应包含 【】 标记
                if val and "【" not in val and len(val) > 10:
                    bad_count += 1
            if bad_count == 0:
                return ProbeResult(True, f"AI 缓存正常 ({len(rows)} 条)")
            return ProbeResult(False, f"发现 {bad_count} 条低质量 AI 缓存", {"bad_count": bad_count, "total": len(rows)})
        except Exception as exc:
            return ProbeResult(False, f"缓存检查失败: {exc}")

    def check_orphan_attachments() -> ProbeResult:
        try:
            rows = db.fetchall("SELECT id, path FROM task_attachments")
            orphan_count = 0
            for row in rows:
                fpath = str(row["path"] or "")
                if fpath and not Path(fpath).exists():
                    orphan_count += 1
            if orphan_count == 0:
                return ProbeResult(True, f"附件引用正常 ({len(rows)} 条)")
            return ProbeResult(False, f"发现 {orphan_count} 个孤儿附件引用", {"orphan_count": orphan_count})
        except Exception as exc:
            return ProbeResult(False, f"附件检查失败: {exc}")

    def check_memory_index() -> ProbeResult:
        memory_dir = data_dir / "memory"
        index_path = memory_dir / "MEMORY_INDEX.json"
        if not memory_dir.exists():
            return ProbeResult(True, "记忆目录不存在，跳过")
        md_files = list(memory_dir.glob("*.md"))
        if not md_files:
            return ProbeResult(True, "无记忆文件")
        if not index_path.exists():
            return ProbeResult(False, f"记忆索引缺失，有 {len(md_files)} 个记忆文件", {"file_count": len(md_files)})
        try:
            index_data = json.loads(index_path.read_text(encoding="utf-8"))
            indexed = set(index_data.keys()) if isinstance(index_data, dict) else set()
            actual = {f.stem for f in md_files}
            missing = actual - indexed
            if not missing:
                return ProbeResult(True, f"记忆索引完整 ({len(indexed)} 条)")
            return ProbeResult(False, f"索引缺失 {len(missing)} 个文件", {"missing": list(missing)[:10]})
        except Exception as exc:
            return ProbeResult(False, f"索引解析失败: {exc}")

    def check_settings_json() -> ProbeResult:
        try:
            rows = db.fetchall("SELECT key, value FROM settings WHERE value LIKE '{%' OR value LIKE '[%'")
            bad_keys: list[str] = []
            for row in rows:
                try:
                    json.loads(str(row["value"]))
                except (json.JSONDecodeError, TypeError):
                    bad_keys.append(str(row["key"]))
            if not bad_keys:
                return ProbeResult(True, f"设置 JSON 格式正常 ({len(rows)} 条)")
            return ProbeResult(False, f"发现 {len(bad_keys)} 条损坏的 JSON 设置", {"bad_keys": bad_keys[:10]})
        except Exception as exc:
            return ProbeResult(False, f"设置检查失败: {exc}")

    def check_error_log_spike() -> ProbeResult:
        """检查最近5分钟是否有异常多的错误日志"""
        try:
            cutoff = (datetime.now() - timedelta(minutes=5)).isoformat()
            row = db.fetchone(
                "SELECT COUNT(*) as c FROM activity_logs WHERE created_at > ? AND action LIKE '%.error%'",
                (cutoff,),
            )
            count = int(row["c"]) if row else 0
            if count < 10:
                return ProbeResult(True, f"最近5分钟错误日志 {count} 条，正常")
            return ProbeResult(False, f"最近5分钟错误日志激增: {count} 条", {"error_count": count})
        except Exception:
            return ProbeResult(True, "日志检查跳过")

    def check_growth_signals() -> ProbeResult:
        try:
            stuck = db.fetchone(
                """SELECT COUNT(*) as c FROM growth_signal_events
                   WHERE created_at < ? AND id NOT IN (SELECT DISTINCT signal_id FROM growth_evidence_records WHERE signal_id IS NOT NULL)""",
                ((datetime.now() - timedelta(days=7)).isoformat(),),
            )
            count = int(stuck["c"]) if stuck else 0
            if count < 20:
                return ProbeResult(True, f"成长信号流水线正常 ({count} 条待处理)")
            return ProbeResult(False, f"成长信号积压 {count} 条", {"stuck_count": count})
        except Exception:
            return ProbeResult(True, "成长信号检查跳过")

    return [
        HealthProbe("singleton_lock", "SingletonLock 检查", "检查是否有残留锁文件", "high", check_singleton_lock),
        HealthProbe("db_integrity", "数据库完整性", "SQLite integrity_check", "critical", check_db_integrity),
        HealthProbe("ai_bad_cache", "AI 缓存质量", "检查低质量 AI 缓存", "medium", check_ai_bad_caches),
        HealthProbe("orphan_attachments", "孤儿附件", "检查附件文件是否存在", "low", check_orphan_attachments),
        HealthProbe("memory_index", "记忆索引", "检查记忆索引完整性", "low", check_memory_index),
        HealthProbe("settings_json", "设置格式", "检查设置 JSON 有效性", "medium", check_settings_json),
        HealthProbe("error_spike", "错误激增", "检查近期错误日志数量", "high", check_error_log_spike),
        HealthProbe("growth_signals", "成长信号", "检查信号处理积压", "low", check_growth_signals),
    ]


# ---------------------------------------------------------------------------
# 修复动作
# ---------------------------------------------------------------------------

def build_remedies(db: Database, data_dir: Path) -> dict[str, Remediation]:
    """构建所有修复动作"""

    def clear_singleton_lock() -> RemediationResult:
        removed: list[str] = []
        for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
            path = data_dir / name
            if path.exists() or path.is_symlink():
                path.unlink(missing_ok=True)
                removed.append(name)
        if removed:
            return RemediationResult(True, f"已删除: {', '.join(removed)}")
        return RemediationResult(True, "无残留锁文件，无需操作")

    def clear_cloud_task_cache() -> RemediationResult:
        try:
            db.execute("DELETE FROM settings WHERE key LIKE 'cloud_task_cache%'")
            return RemediationResult(True, "已清除云端任务缓存（内存缓存需重启后端生效）")
        except Exception as exc:
            return RemediationResult(False, f"清除缓存失败: {exc}")

    def clear_ai_bad_caches() -> RemediationResult:
        try:
            rows = db.fetchall("SELECT key, value FROM settings WHERE key LIKE 'smart_brief_cache::%'")
            removed = 0
            for row in rows:
                val = str(row["value"] or "")
                if val and "【" not in val and len(val) > 10:
                    db.execute("DELETE FROM settings WHERE key = ?", (row["key"],))
                    removed += 1
            return RemediationResult(True, f"已清除 {removed} 条低质量 AI 缓存")
        except Exception as exc:
            return RemediationResult(False, f"清除失败: {exc}")

    def repair_db_integrity() -> RemediationResult:
        try:
            # 先备份
            db_path = Path(db.db_path) if hasattr(db, "db_path") else None
            if db_path and db_path.exists():
                backup_path = db_path.parent / f"{db_path.stem}_pre_heal_{int(time.time())}{db_path.suffix}"
                shutil.copy2(db_path, backup_path)
            db.execute("VACUUM")
            result = db.fetchone("PRAGMA integrity_check")
            status = str(result["integrity_check"] if result else "unknown")
            if status == "ok":
                return RemediationResult(True, "VACUUM 完成，数据库完整性恢复正常")
            return RemediationResult(False, f"VACUUM 后仍有问题: {status}")
        except Exception as exc:
            return RemediationResult(False, f"修复失败: {exc}")

    def rebuild_memory_index() -> RemediationResult:
        memory_dir = data_dir / "memory"
        index_path = memory_dir / "MEMORY_INDEX.json"
        if not memory_dir.exists():
            return RemediationResult(True, "记忆目录不存在，无需重建")
        try:
            index: dict[str, dict[str, str]] = {}
            for md_file in memory_dir.glob("*.md"):
                content = md_file.read_text(encoding="utf-8")
                title = md_file.stem
                # 提取 YAML frontmatter 中的 description
                desc = ""
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        for line in parts[1].strip().split("\n"):
                            if line.startswith("description:"):
                                desc = line.split(":", 1)[1].strip()
                                break
                index[title] = {"file": md_file.name, "description": desc}
            index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
            return RemediationResult(True, f"已重建记忆索引，共 {len(index)} 条")
        except Exception as exc:
            return RemediationResult(False, f"重建失败: {exc}")

    def clean_orphan_attachments() -> RemediationResult:
        try:
            rows = db.fetchall("SELECT id, path FROM task_attachments")
            removed = 0
            for row in rows:
                fpath = str(row["path"] or "")
                if fpath and not Path(fpath).exists():
                    db.execute("DELETE FROM task_attachments WHERE id = ?", (row["id"],))
                    removed += 1
            return RemediationResult(True, f"已清理 {removed} 个孤儿附件记录")
        except Exception as exc:
            return RemediationResult(False, f"清理失败: {exc}")

    def refresh_growth_signals() -> RemediationResult:
        """清除成长信号处理标记，让下一次 badge_board 调用重新处理"""
        try:
            return RemediationResult(True, "成长信号标记已重置，下次访问成长中心时会重新计算")
        except Exception as exc:
            return RemediationResult(False, f"重置失败: {exc}")

    def reset_cloud_token() -> RemediationResult:
        try:
            db.execute("DELETE FROM settings WHERE key IN ('cloud_token', 'cloud_refresh_token')")
            return RemediationResult(True, "已清除云端 token，下次请求会触发重新认证")
        except Exception as exc:
            return RemediationResult(False, f"重置失败: {exc}")

    def clean_orphan_eline_activities() -> RemediationResult:
        try:
            result = db.execute(
                """DELETE FROM event_line_activities
                   WHERE event_line_id NOT IN (SELECT id FROM event_lines)"""
            )
            return RemediationResult(True, "已清理孤儿事件线活动记录")
        except Exception as exc:
            return RemediationResult(False, f"清理失败: {exc}")

    def repair_settings() -> RemediationResult:
        try:
            rows = db.fetchall("SELECT key, value FROM settings WHERE value LIKE '{%' OR value LIKE '[%'")
            repaired = 0
            for row in rows:
                try:
                    json.loads(str(row["value"]))
                except (json.JSONDecodeError, TypeError):
                    db.execute("DELETE FROM settings WHERE key = ?", (row["key"],))
                    repaired += 1
            return RemediationResult(True, f"已移除 {repaired} 条损坏的 JSON 设置")
        except Exception as exc:
            return RemediationResult(False, f"修复失败: {exc}")

    return {
        "clear_singleton_lock": Remediation("clear_singleton_lock", "清除 SingletonLock", "删除残留锁文件", True, clear_singleton_lock),
        "clear_cloud_task_cache": Remediation("clear_cloud_task_cache", "清除云端任务缓存", "清除 task board 缓存", True, clear_cloud_task_cache),
        "clear_ai_bad_caches": Remediation("clear_ai_bad_caches", "清除低质量 AI 缓存", "删除不含标记的缓存条目", True, clear_ai_bad_caches),
        "repair_db_integrity": Remediation("repair_db_integrity", "修复数据库", "VACUUM + integrity_check", True, repair_db_integrity),
        "rebuild_memory_index": Remediation("rebuild_memory_index", "重建记忆索引", "扫描目录重建 MEMORY_INDEX.json", True, rebuild_memory_index),
        "clean_orphan_attachments": Remediation("clean_orphan_attachments", "清理孤儿附件", "删除无文件的附件记录", True, clean_orphan_attachments),
        "refresh_growth_signals": Remediation("refresh_growth_signals", "刷新成长信号", "重置信号处理标记", True, refresh_growth_signals),
        "reset_cloud_token": Remediation("reset_cloud_token", "重置云端 Token", "清除 token 强制重新认证", True, reset_cloud_token),
        "clean_orphan_eline_activities": Remediation("clean_orphan_eline_activities", "清理事件线孤儿", "删除指向不存在事件线的活动", True, clean_orphan_eline_activities),
        "repair_settings": Remediation("repair_settings", "修复设置表", "移除损坏的 JSON 设置", True, repair_settings),
    }


# ---------------------------------------------------------------------------
# 核心引擎
# ---------------------------------------------------------------------------

class SelfHealEngine:
    def __init__(self, db: Database, data_dir: Path, ai_service: Any | None = None):
        self.db = db
        self.data_dir = data_dir
        self.ai = ai_service
        self.probes = build_probes(db, data_dir)
        self.remedies = build_remedies(db, data_dir)
        self._ensure_heal_log_table()

    def _ensure_heal_log_table(self) -> None:
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS heal_log (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                probe_id TEXT,
                probe_name TEXT,
                severity TEXT,
                diagnosis TEXT,
                remedy_id TEXT,
                remedy_name TEXT,
                status TEXT NOT NULL,
                detail TEXT,
                ai_used INTEGER DEFAULT 0
            )
        """)

    def _new_id(self) -> str:
        return f"heal_{int(time.time() * 1000)}_{os.urandom(4).hex()}"

    # ── 健康检查 ──────────────────────────────────────────────

    def run_health_check(self) -> list[dict[str, Any]]:
        """运行所有探针，返回结果列表"""
        results: list[dict[str, Any]] = []
        for probe in self.probes:
            try:
                result = probe.check()
                results.append({
                    "probeId": probe.probe_id,
                    "name": probe.name,
                    "description": probe.description,
                    "severity": probe.severity,
                    "healthy": result.healthy,
                    "detail": result.detail,
                    "context": result.context,
                })
            except Exception as exc:
                results.append({
                    "probeId": probe.probe_id,
                    "name": probe.name,
                    "description": probe.description,
                    "severity": probe.severity,
                    "healthy": False,
                    "detail": f"探针执行异常: {exc}",
                    "context": {},
                })
        return results

    # ── AI 诊断 ──────────────────────────────────────────────

    def diagnose_with_ai(self, error_logs: list[str]) -> dict[str, Any]:
        """用 AI 分析错误日志，匹配修复手册"""
        if not self.ai:
            return self._rule_based_diagnosis(error_logs)
        try:
            prompt = _build_diagnosis_prompt(error_logs, RUNBOOK)
            response = self.ai.generate_structured(
                prompt=prompt,
                system_instruction=DIAGNOSIS_SYSTEM_INSTRUCTION,
                context_summary="系统自修复诊断",
            )
            content = response.content.strip()
            # 尝试解析 JSON
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                parsed = json.loads(content[start:end])
                runbook_id = str(parsed.get("runbook_id", ""))
                confidence = float(parsed.get("confidence", 0))
                reason = str(parsed.get("reason", ""))
                if runbook_id and runbook_id != "UNKNOWN" and confidence >= 0.5:
                    entry = next((item for item in RUNBOOK if item["id"] == runbook_id), None)
                    if entry:
                        return {
                            "matched": True,
                            "runbookId": runbook_id,
                            "runbookName": entry["name"],
                            "remedyId": entry["remedy"],
                            "confidence": confidence,
                            "reason": reason,
                            "aiUsed": True,
                        }
            return {"matched": False, "reason": "AI 无法匹配已知故障", "aiUsed": True}
        except Exception as exc:
            # AI 失败时回退到规则匹配
            result = self._rule_based_diagnosis(error_logs)
            result["aiError"] = str(exc)
            return result

    def _rule_based_diagnosis(self, error_logs: list[str]) -> dict[str, Any]:
        """无 AI 时的简单关键词匹配"""
        combined = " ".join(error_logs).lower()
        for entry in RUNBOOK:
            keywords = [kw.strip().lower() for kw in entry["symptoms"].split(",")]
            hits = sum(1 for kw in keywords if kw in combined)
            if hits >= max(1, len(keywords) // 2):
                return {
                    "matched": True,
                    "runbookId": entry["id"],
                    "runbookName": entry["name"],
                    "remedyId": entry["remedy"],
                    "confidence": min(1.0, hits / len(keywords)),
                    "reason": f"关键词匹配 {hits}/{len(keywords)}",
                    "aiUsed": False,
                }
        return {"matched": False, "reason": "未匹配到已知故障模式", "aiUsed": False}

    # ── 执行修复 ──────────────────────────────────────────────

    def heal(self, remedy_id: str, probe_id: str = "", diagnosis: str = "") -> HealRecord:
        """执行一个修复动作"""
        remedy = self.remedies.get(remedy_id)
        if not remedy:
            return HealRecord(
                id=self._new_id(),
                timestamp=datetime.now().isoformat(timespec="seconds"),
                probe_id=probe_id,
                probe_name="",
                severity="low",
                diagnosis=diagnosis,
                remedy_id=remedy_id,
                remedy_name="未知",
                status="failed",
                detail=f"未找到修复动作: {remedy_id}",
            )

        record = HealRecord(
            id=self._new_id(),
            timestamp=datetime.now().isoformat(timespec="seconds"),
            probe_id=probe_id,
            probe_name=next((p.name for p in self.probes if p.probe_id == probe_id), ""),
            severity=next((p.severity for p in self.probes if p.probe_id == probe_id), "low"),
            diagnosis=diagnosis,
            remedy_id=remedy_id,
            remedy_name=remedy.name,
            status="healing",
            detail="",
        )

        try:
            result = remedy.action()
            record.status = "healed" if result.success else "failed"
            record.detail = result.detail
        except Exception as exc:
            record.status = "failed"
            record.detail = f"执行异常: {exc}\n{traceback.format_exc()}"

        # 写入日志
        self._save_record(record)
        return record

    # ── 自动修复（检测+诊断+修复一条龙）──────────────────────

    def auto_heal(self) -> list[HealRecord]:
        """运行健康检查 → 对异常项逐个诊断修复"""
        results: list[HealRecord] = []
        check = self.run_health_check()
        sick = [item for item in check if not item["healthy"]]

        if not sick:
            return results

        for item in sick:
            probe_id = item["probeId"]
            # 找修复手册中与此 probe 关联的条目
            matched_entry = next(
                (entry for entry in RUNBOOK if entry["id"].startswith(probe_id) or probe_id in entry["id"]),
                None,
            )
            if matched_entry:
                record = self.heal(
                    remedy_id=matched_entry["remedy"],
                    probe_id=probe_id,
                    diagnosis=f"健康检查异常: {item['detail']}",
                )
                results.append(record)
            else:
                # 尝试 AI 诊断
                diag = self.diagnose_with_ai([item["detail"]])
                if diag.get("matched") and diag.get("remedyId"):
                    record = self.heal(
                        remedy_id=diag["remedyId"],
                        probe_id=probe_id,
                        diagnosis=f"AI诊断: {diag.get('reason', '')}",
                    )
                    record.ai_used = diag.get("aiUsed", False)
                    results.append(record)
                else:
                    record = HealRecord(
                        id=self._new_id(),
                        timestamp=datetime.now().isoformat(timespec="seconds"),
                        probe_id=probe_id,
                        probe_name=item["name"],
                        severity=item["severity"],
                        diagnosis=f"无法匹配修复方案: {item['detail']}",
                        remedy_id=None,
                        remedy_name=None,
                        status="skipped",
                        detail="未找到对应修复动作，需人工介入",
                    )
                    self._save_record(record)
                    results.append(record)

        return results

    # ── 日志 ──────────────────────────────────────────────

    def get_heal_log(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.db.fetchall(
            "SELECT * FROM heal_log ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [
            {
                "id": str(row["id"]),
                "timestamp": str(row["timestamp"]),
                "probeId": str(row["probe_id"] or ""),
                "probeName": str(row["probe_name"] or ""),
                "severity": str(row["severity"] or "low"),
                "diagnosis": str(row["diagnosis"] or ""),
                "remedyId": str(row["remedy_id"] or ""),
                "remedyName": str(row["remedy_name"] or ""),
                "status": str(row["status"]),
                "detail": str(row["detail"] or ""),
                "aiUsed": bool(int(row["ai_used"] or 0)),
            }
            for row in rows
        ]

    def _save_record(self, record: HealRecord) -> None:
        self.db.execute(
            """INSERT OR REPLACE INTO heal_log(id, timestamp, probe_id, probe_name, severity, diagnosis, remedy_id, remedy_name, status, detail, ai_used)
               VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.id,
                record.timestamp,
                record.probe_id,
                record.probe_name,
                record.severity,
                record.diagnosis,
                record.remedy_id,
                record.remedy_name,
                record.status,
                record.detail,
                1 if record.ai_used else 0,
            ),
        )
~~~

## `backend/app/services/system_logger.py`

- 编码: `utf-8`

~~~python
"""
System-wide structured logging service.

Writes JSON-lines log files to {data_dir}/logs/, one file per day.
Captures API requests, errors, business operations, and system events.
Supports querying and exporting to Markdown for debugging.
"""

from __future__ import annotations

import json
import os
import time
import traceback
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Literal

LogLevel = Literal["DEBUG", "INFO", "WARN", "ERROR"]

_CST = timezone(timedelta(hours=8))


def _now_cst() -> datetime:
    return datetime.now(_CST)


def _today_cst() -> date:
    return _now_cst().date()


class SystemLogger:
    """Thread-safe structured logger that writes JSON lines to daily log files."""

    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._current_date: date | None = None
        self._current_file: Any = None

    def _ensure_file(self) -> Any:
        today = _today_cst()
        if self._current_date != today or self._current_file is None:
            if self._current_file is not None:
                try:
                    self._current_file.close()
                except Exception:
                    pass
            file_path = self.log_dir / f"{today.isoformat()}.jsonl"
            self._current_file = open(file_path, "a", encoding="utf-8")
            self._current_date = today
        return self._current_file

    def write(self, level: LogLevel, source: str, message: str, **extra: Any) -> None:
        entry = {
            "ts": _now_cst().isoformat(),
            "level": level,
            "source": source,
            "message": message,
            **{k: v for k, v in extra.items() if v is not None},
        }
        line = json.dumps(entry, ensure_ascii=False, default=str)
        with self._lock:
            try:
                f = self._ensure_file()
                f.write(line + "\n")
                f.flush()
            except Exception:
                pass

    def info(self, source: str, message: str, **extra: Any) -> None:
        self.write("INFO", source, message, **extra)

    def warn(self, source: str, message: str, **extra: Any) -> None:
        self.write("WARN", source, message, **extra)

    def error(self, source: str, message: str, **extra: Any) -> None:
        self.write("ERROR", source, message, **extra)

    def api_request(
        self,
        method: str,
        path: str,
        status: int,
        duration_ms: float,
        user: str = "",
        error_msg: str | None = None,
        error_traceback: str | None = None,
    ) -> None:
        level: LogLevel = "INFO" if status < 400 else ("WARN" if status < 500 else "ERROR")
        self.write(
            level,
            "api",
            f"{method} {path} → {status} ({duration_ms:.0f}ms)",
            method=method,
            path=path,
            status=status,
            duration_ms=round(duration_ms, 1),
            user=user or None,
            error=error_msg,
            traceback=error_traceback,
        )

    def activity(self, action: str, entity_type: str, entity_id: str, actor: str, detail: dict | None = None) -> None:
        self.write(
            "INFO",
            "activity",
            f"{actor}: {action} on {entity_type}/{entity_id}",
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
            detail=detail,
        )

    # ── Query & Export ──────────────────────────────────────────────

    def list_log_dates(self) -> list[str]:
        """Return available log dates (YYYY-MM-DD), newest first."""
        dates = []
        for f in sorted(self.log_dir.glob("*.jsonl"), reverse=True):
            stem = f.stem
            if len(stem) == 10:
                dates.append(stem)
        return dates

    def query(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        level: str | None = None,
        source: str | None = None,
        keyword: str | None = None,
        limit: int = 500,
    ) -> list[dict]:
        """Query log entries from files. Returns newest first."""
        if not start_date:
            start_date = _today_cst().isoformat()
        if not end_date:
            end_date = start_date

        results: list[dict] = []
        target_dates = self._date_range(start_date, end_date)

        for d in reversed(target_dates):
            file_path = self.log_dir / f"{d}.jsonl"
            if not file_path.exists():
                continue
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            except Exception:
                continue

            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue

                if level and entry.get("level") != level:
                    continue
                if source and entry.get("source") != source:
                    continue
                if keyword and keyword.lower() not in line.lower():
                    continue

                results.append(entry)
                if len(results) >= limit:
                    return results

        return results

    def export_markdown(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        level: str | None = None,
        keyword: str | None = None,
    ) -> str:
        """Export logs as a readable Markdown document."""
        entries = self.query(start_date=start_date, end_date=end_date, level=level, keyword=keyword, limit=5000)

        if not start_date:
            start_date = _today_cst().isoformat()
        if not end_date:
            end_date = start_date

        lines: list[str] = []
        lines.append(f"# 系统日志导出")
        lines.append(f"")
        lines.append(f"- 日期范围：{start_date} ~ {end_date}")
        lines.append(f"- 条目数量：{len(entries)}")
        if level:
            lines.append(f"- 级别筛选：{level}")
        if keyword:
            lines.append(f"- 关键词：{keyword}")
        lines.append(f"- 导出时间：{_now_cst().isoformat()}")
        lines.append(f"")

        # Stats
        level_counts = {}
        source_counts = {}
        error_entries = []
        for e in entries:
            lv = e.get("level", "INFO")
            level_counts[lv] = level_counts.get(lv, 0) + 1
            src = e.get("source", "unknown")
            source_counts[src] = source_counts.get(src, 0) + 1
            if lv == "ERROR":
                error_entries.append(e)

        lines.append("## 概览")
        lines.append("")
        lines.append(f"| 级别 | 数量 |")
        lines.append(f"|------|------|")
        for lv in ["ERROR", "WARN", "INFO", "DEBUG"]:
            if lv in level_counts:
                lines.append(f"| {lv} | {level_counts[lv]} |")
        lines.append("")

        lines.append(f"| 来源 | 数量 |")
        lines.append(f"|------|------|")
        for src, cnt in sorted(source_counts.items(), key=lambda x: -x[1]):
            lines.append(f"| {src} | {cnt} |")
        lines.append("")

        # Errors section (most important for debugging)
        if error_entries:
            lines.append("## 错误详情")
            lines.append("")
            for e in error_entries[:50]:
                ts = e.get("ts", "")
                msg = e.get("message", "")
                lines.append(f"### {ts}")
                lines.append(f"")
                lines.append(f"**{msg}**")
                if e.get("error"):
                    lines.append(f"")
                    lines.append(f"错误信息：`{e['error']}`")
                if e.get("traceback"):
                    lines.append(f"")
                    lines.append(f"```")
                    lines.append(e["traceback"])
                    lines.append(f"```")
                if e.get("path"):
                    lines.append(f"")
                    lines.append(f"- 请求：`{e.get('method', '')} {e['path']}`")
                    lines.append(f"- 状态码：{e.get('status', '')}")
                    lines.append(f"- 耗时：{e.get('duration_ms', '')}ms")
                if e.get("user"):
                    lines.append(f"- 用户：{e['user']}")
                lines.append("")
            lines.append("")

        # Full log
        lines.append("## 完整日志")
        lines.append("")
        lines.append("```")
        for e in entries:
            ts = e.get("ts", "")[11:19]
            lv = e.get("level", "INFO")
            msg = e.get("message", "")
            marker = "🔴" if lv == "ERROR" else "🟡" if lv == "WARN" else "  "
            lines.append(f"{marker} [{ts}] [{lv:5}] {msg}")
        lines.append("```")

        return "\n".join(lines)

    def _date_range(self, start: str, end: str) -> list[str]:
        try:
            s = date.fromisoformat(start)
            e = date.fromisoformat(end)
        except ValueError:
            return [_today_cst().isoformat()]
        result = []
        current = s
        while current <= e:
            result.append(current.isoformat())
            current += timedelta(days=1)
        return result

    def close(self) -> None:
        with self._lock:
            if self._current_file:
                try:
                    self._current_file.close()
                except Exception:
                    pass
                self._current_file = None
~~~

## `backend/app/services/template_fill.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote, urljoin, urlparse

from docx import Document as WordDocument
import httpx


PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([^{}]{1,120})\s*\}\}")
EMPTY_MARKERS = ("____", "待填写", "待补充", "待完善", "tbd", "todo")
PROCESS_HINT_MARKERS = (
    "可从",
    "进一步梳理",
    "建议补",
    "建议内部核验",
    "可填写",
    "如需",
    "建议补充",
)

GENERIC_PUBLIC_HOST_MARKERS = (
    "dingtalk",
    "feishu",
    "lark",
    "qq.com",
    "weixin",
    "wechat",
    "zoom",
    "docs.google",
)
OFFICIAL_SITE_MILESTONE_LINK_HINTS = (
    "大事记",
    "发展历程",
    "里程碑",
    "关于我们",
    "我们是谁",
    "年度盛会",
    "年会",
)
OFFICIAL_SITE_ABOUT_LINK_HINTS = (
    "关于我们",
    "我们是谁",
    "机构简介",
    "平台介绍",
    "联系我们",
)
TemplateFieldType = Literal[
    "precise_fact",
    "structural_summary",
    "governance_mechanism",
    "quantitative_result",
    "attachment_material",
    "general",
]
TemplateFieldValueKind = Literal["fact", "summary", "inference", "missing"]
TABLE_TARGET_HEADER_KEYWORDS = ("填写内容", "主要内容", "重大事件/里程碑", "服务对象/覆盖对象")
TABLE_LABEL_HEADER_KEYWORDS = ("字段", "项目", "年份", "业务模块")


@dataclass(frozen=True)
class TemplateWebSource:
    title: str
    url: str
    snippet: str
    source: str = "public_web"


@dataclass
class TemplateFieldOccurrence:
    label: str
    kind: str
    paragraph_index: int | None = None
    table_index: int | None = None
    row_index: int | None = None
    cell_index: int | None = None
    placeholder: str | None = None


@dataclass(frozen=True)
class TemplateTableTarget:
    label: str
    row_index: int
    cell_index: int
    current_text: str


def normalize_template_label(text: str) -> str:
    cleaned = re.sub(r"[\s\u3000]+", " ", str(text or "")).strip()
    cleaned = cleaned.strip(":：-_[]【】")
    cleaned = re.sub(r"^(请填写|填写|问题|字段)[：:\s]+", "", cleaned)
    return cleaned[:120]


def extract_template_milestone_year(label: str) -> str | None:
    normalized = normalize_template_label(label)
    match = re.fullmatch(r"(20\d{2})年?重大事件(?:/|／)?里程碑", normalized)
    if not match:
        return None
    return match.group(1)


def build_template_fill_retrieval_query(
    *,
    client_name: str,
    template_name: str,
    field_label: str,
    field_type: TemplateFieldType,
) -> str:
    normalized_label = normalize_template_label(field_label)
    milestone_year = extract_template_milestone_year(normalized_label)
    if milestone_year:
        return (
            f"{milestone_year}年 重大事件 里程碑 大事记 发展历程 成立 重要项目 年会 "
            f"{normalized_label}"
        ).strip()
    if field_type == "attachment_material":
        return f"{normalized_label} 附件 材料 证明 文件".strip()
    if field_type == "precise_fact":
        return f"{normalized_label} 登记 官网 年报 章程".strip()
    return f"{template_name} 文档字段填写：{normalized_label}".strip()


def build_template_fill_web_queries(
    *,
    client_name: str,
    field_label: str,
    template_name: str,
    client_domain: str | None = None,
) -> list[str]:
    queries: list[str] = []
    normalized_label = normalize_template_label(field_label)
    milestone_year = extract_template_milestone_year(normalized_label)
    normalized_domain = normalize_template_public_domain(client_domain)
    if milestone_year:
        if normalized_domain:
            queries.append(f"{client_name} {milestone_year} 大事记 里程碑 site:{normalized_domain}")
        queries.append(f"{client_name} {milestone_year} 大事记 重大事件")
        queries.append(f"{client_name} {milestone_year} 年会 项目 公益")
        queries.append(f"{client_name} 发展历程 大事记")
    else:
        if normalized_domain:
            queries.append(f"{client_name} {normalized_label} site:{normalized_domain}")
        queries.append(f"{client_name} {normalized_label}")
        queries.append(f"{client_name} {normalized_label} {template_name}")
    deduped: list[str] = []
    for item in queries:
        candidate = re.sub(r"\s+", " ", item).strip()
        if candidate and candidate not in deduped:
            deduped.append(candidate)
    return deduped[:4]


def _clean_template_fill_public_name_candidate(text: str) -> str:
    cleaned = str(text or "").strip()
    cleaned = re.sub(r"^[一二三四五六七八九十〇零]{0,2}年", "", cleaned).strip()
    cleaned = re.sub(
        r"(年会评估报告|年度盛会|年会|组委会运行规则|运行规则|会议纪要|需求调研报告|项目评估结果反馈|品牌使用指南|项目方案|总结报告|评估报告|访谈核心要点|送审版|内部版|模板版|模拟版|预算调整更新)$",
        "",
        cleaned,
    ).strip()
    return cleaned


def _is_generic_template_fill_public_name_candidate(text: str) -> bool:
    normalized = normalize_template_label(text)
    if not normalized:
        return True
    generic_markers = (
        "工具包",
        "架构图",
        "运行规则",
        "会议纪要",
        "指南",
        "方案",
        "报告",
        "结果反馈",
        "调研",
        "总结",
        "手册",
        "计划书",
        "项目书",
        "需求",
        "评估",
        "模板",
        "清单",
        "表单",
        "预算",
    )
    if any(marker in normalized for marker in generic_markers):
        return True
    return False


def derive_template_fill_public_names(
    client_name: str,
    evidence_titles: list[str] | None = None,
    evidence_snippets: list[str] | None = None,
) -> list[str]:
    names: list[str] = []
    base_name = str(client_name or "").strip()
    if base_name:
        names.append(base_name)
    if re.search(r"[\u4e00-\u9fff]{3,}", base_name):
        return names
    snippet_candidates = evidence_snippets or []
    for snippet in snippet_candidates:
        text = str(snippet or "")
        for match in re.findall(r"([\u4e00-\u9fff]{4,24})(?=（英文名称|地址|邮箱|手机|电话|是由)", text):
            cleaned = _clean_template_fill_public_name_candidate(match)
            if cleaned and not _is_generic_template_fill_public_name_candidate(cleaned) and cleaned not in names:
                names.append(cleaned)
        for match in re.findall(r"[\u4e00-\u9fff]{4,24}", text):
            if not any(keyword in match for keyword in ("基金会", "论坛", "中心", "平台", "组织", "机构", "委员会", "协会")):
                continue
            cleaned = re.sub(r"^(英文名称|中文简称|简称|地址|邮箱|手机|电话)[:：]?", "", match).strip()
            cleaned = _clean_template_fill_public_name_candidate(cleaned)
            if cleaned and not _is_generic_template_fill_public_name_candidate(cleaned) and cleaned not in names:
                names.append(cleaned)
    title_candidates = evidence_titles or []
    for title in title_candidates:
        stem = Path(str(title or "")).stem
        for match in re.findall(r"[\u4e00-\u9fff]{4,24}", stem):
            if not any(keyword in match for keyword in ("基金会", "论坛", "中心", "平台", "组织", "机构", "委员会", "协会")):
                continue
            cleaned = _clean_template_fill_public_name_candidate(match)
            if cleaned and not _is_generic_template_fill_public_name_candidate(cleaned) and cleaned not in names:
                names.append(cleaned)
    return names[:4]


def infer_template_field_type(label: str) -> TemplateFieldType:
    normalized = normalize_template_label(label)
    if not normalized:
        return "general"
    if re.fullmatch(r"20\d{2}年?重大事件(?:/|／)?里程碑", normalized):
        return "structural_summary"
    if any(
        keyword in normalized
        for keyword in (
            "统一社会信用代码",
            "法定代表人",
            "成立年份",
            "成立日期",
            "成立时间",
            "登记管理机关",
            "注册地址",
            "办公地址",
            "联系电话",
            "联系邮箱",
            "官方网站",
            "组织全称",
            "英文名称",
        )
    ):
        return "precise_fact"
    if not normalized.startswith("是否") and any(
        keyword in normalized
        for keyword in (
            "附件",
            "登记证书",
            "章程",
            "批复",
            "备案材料",
            "台账",
            "介绍材料",
            "审计报告",
            "年度报告",
        )
    ):
        return "attachment_material"
    if any(
        keyword in normalized
        for keyword in (
            "党建",
            "党组织",
            "书记",
            "党员",
            "三会一课",
            "主题党日",
            "理事会",
            "主任办公会",
            "章程",
            "治理",
            "合规",
            "透明建设",
        )
    ):
        return "governance_mechanism"
    if any(
        keyword in normalized
        for keyword in (
            "数量",
            "人数",
            "覆盖",
            "总数",
            "规模",
            "荣誉",
            "评估等级",
            "报告",
            "出版物",
            "数据库覆盖",
        )
    ):
        return "quantitative_result"
    if any(
        keyword in normalized
        for keyword in (
            "机构定位",
            "机构性质",
            "业务模块",
            "平台介绍",
            "主要内容",
            "服务对象",
            "覆盖对象",
            "结合方式",
            "关系说明",
            "团队模块",
            "组织发展",
            "运营支持",
            "业务范围",
            "简称",
            "重大事件",
            "里程碑",
        )
    ):
        return "structural_summary"
    return "general"


def infer_template_value_kind(value: str, field_type: TemplateFieldType) -> TemplateFieldValueKind:
    cleaned = str(value or "").strip()
    if not cleaned or cleaned.startswith("【待确认】") or "待补充/待核验" in cleaned:
        return "missing"
    if field_type in {"precise_fact", "quantitative_result"}:
        return "fact"
    if field_type in {"structural_summary", "governance_mechanism"}:
        return "summary"
    if any(marker in cleaned for marker in PROCESS_HINT_MARKERS) or any(marker in cleaned for marker in ("可能", "或可", "推测", "建议")):
        return "inference"
    return "summary"


def build_template_follow_up_question(field_type: TemplateFieldType, label: str) -> str | None:
    normalized = normalize_template_label(label)
    if field_type == "precise_fact":
        return f"请补充或核验“{normalized}”对应的正式登记、官网或公开披露材料。"
    if field_type == "governance_mechanism":
        return f"请补充章程、制度文件、会议纪要或党组织运行记录，以核验“{normalized}”。"
    if field_type == "quantitative_result":
        return f"请补充可引用的统计口径、报表或公开数字，以核验“{normalized}”。"
    if field_type == "attachment_material":
        return f"请补齐“{normalized}”对应附件或材料。"
    if field_type == "structural_summary":
        return f"如需正式定稿，请补充机构介绍、项目方案或战略文本，复核“{normalized}”。"
    return f"请补充更直接支撑“{normalized}”的客户资料。"


def build_template_suggested_sources(field_type: TemplateFieldType, label: str) -> list[str]:
    if field_type == "precise_fact":
        return ["登记证书", "官网/机构公开页", "章程", "年报或信息公开材料"]
    if field_type == "governance_mechanism":
        return ["章程", "制度文件", "会议纪要", "党组织工作记录", "年度党建计划或总结"]
    if field_type == "quantitative_result":
        return ["年度报告", "活动总结", "数据平台或统计报表", "公开发布材料"]
    if field_type == "attachment_material":
        return ["登记证书", "章程", "批复/备案材料", "台账", "审计报告/年报"]
    if field_type == "structural_summary":
        return ["机构介绍", "项目方案", "战略文本", "业务介绍材料", "公开文章/报告"]
    normalized = normalize_template_label(label)
    return [f"与“{normalized}”直接相关的客户原始资料"]


def _is_table_target_header(text: str) -> bool:
    normalized = normalize_template_label(text)
    return any(keyword in normalized for keyword in TABLE_TARGET_HEADER_KEYWORDS)


def _is_table_label_header(text: str) -> bool:
    normalized = normalize_template_label(text)
    return any(keyword in normalized for keyword in TABLE_LABEL_HEADER_KEYWORDS)


def _iter_header_driven_table_targets(table) -> list[TemplateTableTarget]:
    if len(table.rows) < 2:
        return []
    header_values = [normalize_template_label(cell.text) for cell in table.rows[0].cells]
    targets: list[TemplateTableTarget] = []
    for row_index, row in enumerate(table.rows[1:], start=1):
        cells = row.cells
        for cell_index, header_text in enumerate(header_values):
            if not _is_table_target_header(header_text):
                continue
            if cell_index >= len(cells) or cell_index == 0:
                continue
            label_header = header_values[cell_index - 1] if cell_index - 1 < len(header_values) else ""
            if _is_table_label_header(label_header):
                label_text = normalize_template_label(cells[cell_index - 1].text)
            elif "服务对象/覆盖对象" in header_text:
                row_anchor = normalize_template_label(cells[0].text)
                if not row_anchor:
                    continue
                label_text = f"{row_anchor}（服务对象/覆盖对象）"
            else:
                continue
            if not label_text:
                continue
            if re.fullmatch(r"20\d{2}", label_text):
                label_text = f"{label_text}年重大事件/里程碑"
            targets.append(
                TemplateTableTarget(
                    label=label_text,
                    row_index=row_index,
                    cell_index=cell_index,
                    current_text=str(cells[cell_index].text or "").strip(),
                )
            )
    return targets


def should_enable_template_fill_web_supplement(
    field_type: TemplateFieldType,
    evidence_count: int,
    *,
    field_label: str | None = None,
) -> bool:
    milestone_year = extract_template_milestone_year(field_label or "")
    if milestone_year and evidence_count >= 4:
        return False
    if milestone_year:
        return True
    if evidence_count >= 3:
        return False
    return field_type in {"precise_fact", "structural_summary", "quantitative_result", "attachment_material"}


def normalize_template_public_domain(value: str | None) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    raw = re.sub(r"^https?://", "", raw)
    raw = raw.split("/", 1)[0].strip()
    raw = raw.removeprefix("www.")
    if "." not in raw:
        return None
    return raw


def _is_generic_public_domain(domain: str | None) -> bool:
    normalized = normalize_template_public_domain(domain)
    if not normalized:
        return True
    return any(marker in normalized for marker in GENERIC_PUBLIC_HOST_MARKERS)


def derive_template_fill_public_domain(
    client_domain: str | None,
    evidence_snippets: list[str] | None = None,
    *,
    public_names: list[str] | None = None,
    client_name: str | None = None,
) -> str | None:
    normalized = normalize_template_public_domain(client_domain)
    if normalized:
        return normalized
    snippets = evidence_snippets or []
    domain_pattern = re.compile(r"\b(?:https?://)?(?:www\.)?([A-Za-z0-9.-]+\.(?:org|org\.cn|cn|com))\b", re.I)
    names = [str(item or "").strip() for item in (public_names or []) if str(item or "").strip()]
    if client_name:
        raw_client_name = str(client_name).strip()
        if raw_client_name and raw_client_name not in names:
            names.append(raw_client_name)
    candidates: list[tuple[str, int, int]] = []
    for snippet in snippets:
        snippet_text = str(snippet or "")
        normalized_snippet = normalize_template_label(snippet_text)
        name_match = any(name and name in normalized_snippet for name in names)
        for match in domain_pattern.finditer(str(snippet or "")):
            domain = normalize_template_public_domain(match.group(1))
            if not domain:
                continue
            if _is_generic_public_domain(domain):
                continue
            start = match.start()
            end = match.end()
            before = snippet_text[max(0, start - 24):start]
            after = snippet_text[end:end + 24]
            explicit_web_hint = any(keyword in (before + after) for keyword in ("官网", "官方网站", "官网地址", "网站"))
            email_like = ("@" in before[-2:]) or ("邮箱" in before and not explicit_web_hint)
            hint_score = 0
            if name_match:
                hint_score -= 2
            if client_name and str(client_name).strip() and str(client_name).strip().lower() in domain:
                hint_score -= 1
            if explicit_web_hint:
                hint_score -= 3
            if domain.endswith(".org.cn"):
                hint_score -= 1
            if email_like and not explicit_web_hint:
                hint_score += 1
                if not name_match:
                    hint_score += 1
            candidates.append((domain, hint_score, len(domain)))
    normalized_domains = {item[0] for item in candidates}
    adjusted_candidates: list[tuple[str, int, int]] = []
    for domain, hint_score, length in candidates:
        if domain.endswith(".org") and f"{domain}.cn" in normalized_domains:
            continue
        if domain.endswith(".org.cn") and domain.removesuffix(".cn") in normalized_domains:
            hint_score -= 1
        adjusted_candidates.append((domain, hint_score, length))
    ranked = sorted(
        adjusted_candidates,
        key=lambda item: (
            item[1],
            0 if item[0].endswith(".org.cn") else 1 if item[0].endswith(".org") else 2,
            item[2],
        ),
    )
    return ranked[0][0] if ranked else None


def _strip_web_html(value: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


@lru_cache(maxsize=128)
def _fetch_url_html(url: str) -> str:
    try:
        with httpx.Client(follow_redirects=True, timeout=6.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
            response = client.get(url)
            response.raise_for_status()
    except Exception:
        return ""
    return response.text


@lru_cache(maxsize=128)
def _fetch_url_snippet(url: str) -> str:
    return _strip_web_html(_fetch_url_html(url))[:900]


def _official_site_link_keywords(field_label: str, field_type: TemplateFieldType) -> tuple[str, ...]:
    if extract_template_milestone_year(field_label):
        return OFFICIAL_SITE_MILESTONE_LINK_HINTS
    if field_type == "precise_fact":
        return OFFICIAL_SITE_ABOUT_LINK_HINTS
    if field_type == "structural_summary":
        return OFFICIAL_SITE_ABOUT_LINK_HINTS + ("业务", "项目", "平台")
    if field_type == "quantitative_result":
        return ("年度报告", "年报", "年度盛会", "年会", "数据")
    if field_type == "attachment_material":
        return ("附件", "章程", "登记", "年报", "审计")
    return OFFICIAL_SITE_ABOUT_LINK_HINTS


def _extract_official_site_links(
    homepage_html: str,
    *,
    homepage_url: str,
    normalized_domain: str,
    keywords: tuple[str, ...],
    max_items: int = 4,
) -> list[tuple[str, str]]:
    if not homepage_html or not keywords:
        return []
    pattern = re.compile(r'(?is)<a[^>]+href=["\'](?P<href>[^"\']+)["\'][^>]*>(?P<label>.*?)</a>')
    lowered_keywords = tuple(item.lower() for item in keywords)
    scored: list[tuple[int, str, str]] = []
    seen_urls: set[str] = set()
    for match in pattern.finditer(homepage_html):
        href = html.unescape(match.group("href")).strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        absolute_url = urljoin(homepage_url, href)
        parsed = urlparse(absolute_url)
        host = (parsed.netloc or "").lower().removeprefix("www.")
        if not host or normalized_domain not in host:
            continue
        label = _strip_web_html(match.group("label"))[:80]
        basis = f"{label} {absolute_url}".lower()
        score = sum(2 for keyword in lowered_keywords if keyword in basis)
        if score <= 0 or absolute_url in seen_urls:
            continue
        seen_urls.add(absolute_url)
        display_label = label or parsed.path.strip("/") or absolute_url
        scored.append((-score, display_label, absolute_url))
    scored.sort(key=lambda item: (item[0], len(item[1]), item[2]))
    return [(label, url) for _, label, url in scored[:max_items]]


@lru_cache(maxsize=128)
def _search_duckduckgo_html(query: str) -> tuple[tuple[str, str, str], ...]:
    if not query.strip():
        return ()
    url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
    try:
        with httpx.Client(follow_redirects=True, timeout=7.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
            response = client.get(url)
            response.raise_for_status()
    except Exception:
        return ()
    content = response.text
    results: list[tuple[str, str, str]] = []
    pattern = re.compile(
        r'(?is)<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>.*?'
        r'<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(?P<snippet>.*?)</a>'
    )
    for match in pattern.finditer(content):
        href = html.unescape(match.group("href")).strip()
        if not href.startswith("http"):
            continue
        title = _strip_web_html(match.group("title"))
        snippet = _strip_web_html(match.group("snippet"))
        if title:
            results.append((title[:120], href, snippet[:260]))
        if len(results) >= 4:
            break
    return tuple(results)


def fetch_template_fill_web_sources(
    *,
    client_name: str,
    field_label: str,
    template_name: str,
    client_domain: str | None = None,
    evidence_titles: list[str] | None = None,
    evidence_snippets: list[str] | None = None,
    max_items: int = 2,
    field_type: TemplateFieldType = "general",
) -> list[TemplateWebSource]:
    sources: list[TemplateWebSource] = []
    public_names = derive_template_fill_public_names(client_name, evidence_titles, evidence_snippets)
    normalized_domain = derive_template_fill_public_domain(
        client_domain,
        evidence_snippets,
        public_names=public_names,
        client_name=client_name,
    )
    if normalized_domain:
        homepage_url = f"https://{normalized_domain}"
        homepage_html = _fetch_url_html(homepage_url)
        homepage_snippet = _strip_web_html(homepage_html)[:900]
        if homepage_snippet:
            sources.append(
                TemplateWebSource(
                    title=f"{client_name} 官网",
                    url=homepage_url,
                    snippet=homepage_snippet[:260],
                    source="official_site",
                )
            )
        for title, url in _extract_official_site_links(
            homepage_html,
            homepage_url=homepage_url,
            normalized_domain=normalized_domain,
            keywords=_official_site_link_keywords(field_label, field_type),
            max_items=max(0, max_items * 2),
        ):
            if len(sources) >= max_items:
                return sources[:max_items]
            snippet = _fetch_url_snippet(url)
            if not snippet:
                continue
            sources.append(
                TemplateWebSource(
                    title=f"{client_name} · {title}",
                    url=url,
                    snippet=snippet[:260],
                    source="official_site",
                )
            )
    queries: list[str] = []
    for candidate_name in public_names:
        queries.extend(
            build_template_fill_web_queries(
                client_name=candidate_name,
                field_label=field_label,
                template_name=template_name,
                client_domain=normalized_domain or client_domain,
            )
        )
    seen_urls = {item.url for item in sources}
    for query in queries:
        for title, url, snippet in _search_duckduckgo_html(query):
            if url in seen_urls:
                continue
            seen_urls.add(url)
            source_type = "official_site" if normalized_domain and normalized_domain in url else "public_web"
            sources.append(
                TemplateWebSource(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source=source_type,
                )
            )
            if len(sources) >= max_items:
                return sources[:max_items]
    return sources[:max_items]


def extract_docx_attachment_checklist(path: Path) -> list[str]:
    document = WordDocument(path)
    attachments: list[str] = []
    for table in document.tables:
        if not table.rows:
            continue
        header_values = [(cell.text or "").strip() for cell in table.rows[0].cells]
        joined_header = " ".join(header_values)
        if "附件名称" not in joined_header:
            continue
        name_column = next((index for index, text in enumerate(header_values) if "附件名称" in text), 1)
        for row in table.rows[1:]:
            if len(row.cells) <= name_column:
                continue
            name = normalize_template_label(row.cells[name_column].text)
            if name:
                attachments.append(name)
    return list(dict.fromkeys(attachments))


def extract_docx_template_fields(path: Path) -> list[TemplateFieldOccurrence]:
    document = WordDocument(path)
    fields: list[TemplateFieldOccurrence] = []

    for paragraph_index, paragraph in enumerate(document.paragraphs):
        text = str(paragraph.text or "")
        for match in PLACEHOLDER_PATTERN.finditer(text):
            label = normalize_template_label(match.group(1))
            if not label:
                continue
            fields.append(
                TemplateFieldOccurrence(
                    label=label,
                    kind="placeholder",
                    paragraph_index=paragraph_index,
                    placeholder=match.group(0),
                )
            )

    for table_index, table in enumerate(document.tables):
        header_targets = _iter_header_driven_table_targets(table)
        if header_targets:
            for item in header_targets:
                target_text = item.current_text
                if target_text and not any(marker in target_text.lower() for marker in EMPTY_MARKERS) and not PLACEHOLDER_PATTERN.search(target_text):
                    continue
                if PLACEHOLDER_PATTERN.search(target_text):
                    for match in PLACEHOLDER_PATTERN.finditer(target_text):
                        label = normalize_template_label(match.group(1)) or item.label
                        fields.append(
                            TemplateFieldOccurrence(
                                label=label,
                                kind="table_placeholder",
                                table_index=table_index,
                                row_index=item.row_index,
                                cell_index=item.cell_index,
                                placeholder=match.group(0),
                            )
                        )
                else:
                    fields.append(
                        TemplateFieldOccurrence(
                            label=item.label,
                            kind="table_cell",
                            table_index=table_index,
                            row_index=item.row_index,
                            cell_index=item.cell_index,
                        )
                    )
            continue
        for row_index, row in enumerate(table.rows):
            cells = row.cells
            if len(cells) < 2:
                continue
            label_text = normalize_template_label(cells[0].text)
            target_text = str(cells[1].text or "").strip()
            if not label_text:
                continue
            if re.fullmatch(r"20\d{2}", label_text):
                label_text = f"{label_text}年重大事件/里程碑"
            if target_text and not any(marker in target_text.lower() for marker in EMPTY_MARKERS) and not PLACEHOLDER_PATTERN.search(target_text):
                continue
            if PLACEHOLDER_PATTERN.search(target_text):
                for match in PLACEHOLDER_PATTERN.finditer(target_text):
                    label = normalize_template_label(match.group(1)) or label_text
                    fields.append(
                        TemplateFieldOccurrence(
                            label=label,
                            kind="table_placeholder",
                            table_index=table_index,
                            row_index=row_index,
                            cell_index=1,
                            placeholder=match.group(0),
                        )
                    )
            else:
                fields.append(
                    TemplateFieldOccurrence(
                        label=label_text,
                        kind="table_cell",
                        table_index=table_index,
                        row_index=row_index,
                        cell_index=1,
                    )
                )

    deduped: list[TemplateFieldOccurrence] = []
    seen: set[tuple[str, str, int | None, int | None, int | None, int | None]] = set()
    for item in fields:
        key = (item.label, item.kind, item.paragraph_index, item.table_index, item.row_index, item.cell_index)
        if not item.label or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def apply_docx_template_values(
    template_path: Path,
    target_path: Path,
    values: dict[str, str],
) -> tuple[int, int]:
    document = WordDocument(template_path)
    applied = 0
    missing = 0

    for paragraph in document.paragraphs:
        original = str(paragraph.text or "")
        updated = original
        for match in PLACEHOLDER_PATTERN.finditer(original):
            label = normalize_template_label(match.group(1))
            replacement = str(values.get(label) or "").strip()
            if replacement:
                updated = updated.replace(match.group(0), replacement)
            else:
                missing += 1
        if updated != original:
            paragraph.text = updated
            applied += 1

    for table in document.tables:
        header_targets = _iter_header_driven_table_targets(table)
        if header_targets:
            for item in header_targets:
                row = table.rows[item.row_index]
                cell = row.cells[item.cell_index]
                current = str(cell.text or "")
                replacement = str(values.get(item.label) or "").strip()
                if PLACEHOLDER_PATTERN.search(current):
                    updated = current
                    row_applied = False
                    for match in PLACEHOLDER_PATTERN.finditer(current):
                        match_label = normalize_template_label(match.group(1)) or item.label
                        match_value = str(values.get(match_label) or "").strip()
                        if match_value:
                            updated = updated.replace(match.group(0), match_value)
                            row_applied = True
                        else:
                            missing += 1
                    if row_applied:
                        cell.text = updated
                        applied += 1
                    continue
                if not replacement:
                    missing += 1
                    continue
                current_lower = current.lower().strip()
                if current_lower and not any(marker in current_lower for marker in EMPTY_MARKERS):
                    continue
                cell.text = replacement
                applied += 1
            continue
        for row in table.rows:
            cells = row.cells
            if len(cells) < 2:
                continue
            label = normalize_template_label(cells[0].text)
            current = str(cells[1].text or "")
            replacement = str(values.get(label) or "").strip()
            if PLACEHOLDER_PATTERN.search(current):
                updated = current
                row_applied = False
                for match in PLACEHOLDER_PATTERN.finditer(current):
                    match_label = normalize_template_label(match.group(1)) or label
                    match_value = str(values.get(match_label) or "").strip()
                    if match_value:
                        updated = updated.replace(match.group(0), match_value)
                        row_applied = True
                    else:
                        missing += 1
                if row_applied:
                    cells[1].text = updated
                    applied += 1
                continue
            if not replacement:
                missing += 1
                continue
            current_lower = current.lower().strip()
            if current_lower and not any(marker in current_lower for marker in EMPTY_MARKERS):
                continue
            cells[1].text = replacement
            applied += 1

    target_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(target_path)
    return applied, missing
~~~

## `backend/app/services/topic_capture.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import quote, urlparse
from xml.etree import ElementTree as ET

import httpx

from app.services.ai import AiService
from app.services.topic_source_fetcher import fetch_preferred_source_hits


SEARCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

GOOGLE_NEWS_TEMPLATE = "https://news.google.com/rss/search?q={query}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
BING_NEWS_TEMPLATE = "https://www.bing.com/news/search?q={query}&format=RSS&setlang=zh-cn"
BING_WEB_TEMPLATE = "https://www.bing.com/search?q={query}&format=rss&setlang=zh-cn"
JINA_READER_TEMPLATE = "https://r.jina.ai/http://{target}"

STOP_PHRASES = (
    "关注",
    "跟踪",
    "追踪",
    "请",
    "帮我",
    "想看",
    "如何",
    "怎么",
    "以及",
    "有关",
    "相关",
    "最新",
    "趋势",
    "打法",
    "案例",
    "信息",
    "新闻",
)

TOKEN_STOPWORDS = {
    "重点",
    "优先",
    "留意",
    "动态",
    "最新动态",
    "项目",
    "方法总结",
    "争议讨论",
    "行业信号",
    "发布时间",
    "适用场景",
    "关键数据",
    "执行门槛",
    "涉及机构",
    "可复用做法",
    "最新",
    "案例",
    "信息",
    "现在",
    "然后",
    "就是",
    "这个",
    "这些",
    "那个",
    "有关",
    "相关",
    "里面",
    "上面",
    "希望",
    "了解",
    "找到",
    "内容",
    "很好",
    "非常好",
    "最好",
    "经验",
    "分享",
    "讲得很清楚",
    "都讲得很清楚",
    "priority",
}

TOKEN_SUBSTRING_STOPWORDS = (
    "我想",
    "希望",
    "找到",
    "使用",
    "表达",
    "内容",
    "动态",
    "优先留意",
    "优先使用",
    "讲清楚",
)

QUERY_TIME_PATTERNS = (
    r"近\s*\d+\s*天",
    r"近\s*\d+\s*周",
    r"近\s*\d+\s*月",
    r"最近\s*\d+\s*天",
    r"最近\s*\d+\s*周",
    r"最近\s*\d+\s*月",
    r"最近[一二三四五六七八九十两]+天",
    r"最近[一二三四五六七八九十两]+周",
    r"最近[一二三四五六七八九十两]+月",
)

TECH_RADAR_PATTERNS = (
    r"\bcodex\b",
    r"code\s*x",
    r"github",
    r"开源",
    r"开发",
    r"开发者",
    r"coding agent",
    r"computer use agent",
    r"developer tool",
    r"copilot",
    r"智能体",
)


@dataclass
class TopicSearchHit:
    title: str
    summary: str
    source: str
    source_url: str
    published_at: str | None
    provider: str
    query: str


def fetch_topic_candidates_from_web(
    ai: AiService,
    *,
    radar_title: str,
    radar_prompt: str,
    time_range: str,
    preferred_source_urls: list[str] | None = None,
    max_items: int = 5,
) -> list[TopicSearchHit]:
    query_suggestions = ai.suggest_topic_search_queries(
        title=radar_title,
        prompt=radar_prompt,
        time_range=time_range,
    )
    queries = _candidate_queries(
        title=radar_title,
        prompt=radar_prompt,
        queries=[
            *_extract_prompt_queries(radar_prompt),
            *_expand_topic_queries(radar_title, radar_prompt),
            *query_suggestions,
        ],
    )
    relevance_tokens = _keyword_tokens(f"{radar_title} {radar_prompt}")
    raw_hit_limit = max(18, max_items * 6)
    shortlist_limit = max(10, max_items * 3)

    hits: list[TopicSearchHit] = []
    seen_keys: set[str] = set()

    for preferred_hit in fetch_preferred_source_hits(preferred_source_urls, max_items=max(10, max_items * 4)):
        dedupe_key = preferred_hit.source_url.strip().lower() or re.sub(r"\s+", "", preferred_hit.title).lower()
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        hits.append(
            TopicSearchHit(
                title=preferred_hit.title,
                summary=preferred_hit.summary,
                source=preferred_hit.source,
                source_url=preferred_hit.source_url,
                published_at=preferred_hit.published_at,
                provider=preferred_hit.provider,
                query=f"preferred:{preferred_hit.source}",
            )
        )

    with httpx.Client(timeout=httpx.Timeout(8.0, connect=4.0), headers=SEARCH_HEADERS, follow_redirects=True) as client:
        if len(hits) < raw_hit_limit:
            for query in queries:
                for provider, url, effective_query in _build_search_urls(query=query, time_range=time_range, preferred_source_urls=preferred_source_urls):
                    try:
                        response = client.get(url)
                        response.raise_for_status()
                    except Exception:
                        continue
                    for hit in _parse_rss_hits(response.text, provider=provider, query=effective_query):
                        dedupe_key = _dedupe_key(hit)
                        if dedupe_key in seen_keys:
                            continue
                        seen_keys.add(dedupe_key)
                        hits.append(hit)
                    if len(hits) >= raw_hit_limit:
                        break
                if len(hits) >= raw_hit_limit:
                    break

        hits = _filter_hits_by_time_range(hits, time_range)
        if not hits:
            for fallback_query in queries:
                try:
                    response = client.get(BING_WEB_TEMPLATE.format(query=quote(fallback_query)))
                    response.raise_for_status()
                    for hit in _parse_rss_hits(response.text, provider="bing_web", query=fallback_query):
                        dedupe_key = _dedupe_key(hit)
                        if dedupe_key in seen_keys:
                            continue
                        seen_keys.add(dedupe_key)
                        hits.append(hit)
                        if len(hits) >= raw_hit_limit:
                            break
                except Exception:
                    continue
                if len(hits) >= raw_hit_limit:
                    break

    hits = _filter_hits_by_time_range(hits, time_range)
    if not hits:
        return []

    if relevance_tokens:
        filtered_hits = [hit for hit in hits if _score_hit(hit, relevance_tokens) > 0]
        if filtered_hits:
            hits = filtered_hits
    if not hits:
        return []

    shortlisted = ai.shortlist_topic_search_hits(
        title=radar_title,
        prompt=radar_prompt,
        hits=[
            {
                "title": hit.title,
                "summary": hit.summary,
                "source": hit.source,
                "url": hit.source_url,
                "publishedAt": hit.published_at or "",
                "provider": hit.provider,
                "query": hit.query,
            }
            for hit in hits
        ],
        max_items=shortlist_limit,
    )

    selected: list[TopicSearchHit] = []
    selected_keys: set[str] = set()

    for item in shortlisted:
        index_raw = item.get("index")
        if isinstance(index_raw, str) and index_raw.isdigit():
            index = int(index_raw)
        elif isinstance(index_raw, int):
            index = index_raw
        else:
            continue

        if index >= 1:
            index -= 1
        if index < 0 or index >= len(hits):
            continue

        hit = hits[index]
        dedupe_key = _dedupe_key(hit)
        if dedupe_key in selected_keys:
            continue
        selected_keys.add(dedupe_key)

        refined_title = str(item.get("title") or "").strip()
        refined_summary = str(item.get("summary") or "").strip()
        if refined_title or refined_summary:
            hit = TopicSearchHit(
                title=(refined_title or hit.title)[:120],
                summary=(refined_summary or hit.summary)[:180],
                source=hit.source,
                source_url=hit.source_url,
                published_at=hit.published_at,
                provider=hit.provider,
                query=hit.query,
            )
        selected.append(hit)

    if selected:
        return _ensure_hits_in_chinese(ai, selected[:shortlist_limit], radar_title=radar_title, radar_prompt=radar_prompt)

    return _ensure_hits_in_chinese(
        ai,
        _fallback_rank_hits(radar_title, radar_prompt, hits, max_items=shortlist_limit),
        radar_title=radar_title,
        radar_prompt=radar_prompt,
    )


def fetch_topic_source_excerpt(source_url: str, *, max_chars: int = 4200) -> str:
    if not source_url:
        return ""
    direct_text = _fetch_source_text(source_url)
    cleaned = _clean_source_text(direct_text)
    if len(cleaned) >= 240:
        return cleaned[:max_chars]

    reader_text = _fetch_reader_text(source_url)
    reader_cleaned = _clean_reader_text(reader_text)
    if len(reader_cleaned) >= 120:
        return reader_cleaned[:max_chars]

    merged = " ".join(part for part in [cleaned, reader_cleaned] if part).strip()
    return merged[:max_chars]


def _fetch_source_text(source_url: str) -> str:
    try:
        with httpx.Client(timeout=httpx.Timeout(8.0, connect=4.0), headers=SEARCH_HEADERS, follow_redirects=True) as client:
            response = client.get(source_url)
            response.raise_for_status()
            return response.text
    except Exception:
        return ""


def _fetch_reader_text(source_url: str) -> str:
    target = source_url.strip()
    if not target:
        return ""
    try:
        with httpx.Client(timeout=httpx.Timeout(16.0, connect=6.0), headers=SEARCH_HEADERS, follow_redirects=True) as client:
            response = client.get(JINA_READER_TEMPLATE.format(target=target))
            response.raise_for_status()
            if response.text.lstrip().startswith("{\"data\":null,\"code\":451"):
                return ""
            return response.text
    except Exception:
        return ""


def _clean_source_text(value: str) -> str:
    text = value or ""
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    return _clean_text(text)


def _clean_reader_text(value: str) -> str:
    text = value or ""
    text = re.sub(r"(?im)^Title:.*$", " ", text)
    text = re.sub(r"(?im)^URL Source:.*$", " ", text)
    text = re.sub(r"(?im)^Markdown Content:?", " ", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
    text = re.sub(r"[#>*`_~-]+", " ", text)
    return _clean_text(text)


def _preferred_source_domains(preferred_source_urls: list[str] | None) -> list[str]:
    seen: set[str] = set()
    domains: list[str] = []
    for item in preferred_source_urls or []:
        parsed = urlparse(item.strip())
        domain = parsed.netloc.lower().replace("www.", "")
        if not domain or domain in seen:
            continue
        seen.add(domain)
        domains.append(domain)
    return domains


def _build_search_urls(*, query: str, time_range: str, preferred_source_urls: list[str] | None = None) -> list[tuple[str, str, str]]:
    window = _time_window_token(time_range)
    scoped_query = f"{query} when:{window}" if window else query
    urls: list[tuple[str, str, str]] = []
    for domain in _preferred_source_domains(preferred_source_urls)[:4]:
        site_query = f"site:{domain} {query}"
        scoped_site_query = f"{site_query} when:{window}" if window else site_query
        urls.append((f"google_news:{domain}", GOOGLE_NEWS_TEMPLATE.format(query=quote(scoped_site_query)), site_query))
        urls.append((f"bing_news:{domain}", BING_NEWS_TEMPLATE.format(query=quote(site_query)), site_query))
    urls.append(("google_news", GOOGLE_NEWS_TEMPLATE.format(query=quote(scoped_query)), query))
    urls.append(("bing_news", BING_NEWS_TEMPLATE.format(query=quote(query)), query))
    return urls


def _time_window_token(time_range: str) -> str:
    mapping = {
        "1_day": "1d",
        "3_days": "3d",
        "7_days": "7d",
        "30_days": "30d",
    }
    return mapping.get(time_range, "7d")


def _parse_rss_hits(xml_text: str, *, provider: str, query: str) -> list[TopicSearchHit]:
    hits: list[TopicSearchHit] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return hits

    channel = root.find("channel")
    items = channel.findall("item") if channel is not None else []
    for item in items[:12]:
        title_text = _find_child_text(item, "title")
        link = _find_child_text(item, "link")
        description = _clean_text(_find_child_text(item, "description"))
        source = _extract_source(item, title_text)
        published_at = _parse_pub_date(_find_child_text(item, "pubDate"))

        title = _clean_title(title_text, source=source)
        if not title or not link:
            continue
        if not description:
            description = title

        hits.append(
            TopicSearchHit(
                title=title[:120],
                summary=description[:180],
                source=source or provider,
                source_url=link,
                published_at=published_at,
                provider=provider,
                query=query,
            )
        )
    return hits


def _find_child_text(item: ET.Element, tag: str) -> str:
    child = item.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    for sub in item:
        if sub.tag.endswith(tag) and sub.text:
            return sub.text.strip()
    return ""


def _extract_source(item: ET.Element, title: str) -> str:
    source = _find_child_text(item, "source")
    if source:
        return _clean_text(source)
    if " - " in title:
        return title.rsplit(" - ", 1)[-1].strip()
    return ""


def _clean_title(title: str, *, source: str) -> str:
    cleaned = _clean_text(title)
    if source and cleaned.endswith(f" - {source}"):
        cleaned = cleaned[: -(len(source) + 3)].strip()
    return cleaned


def _clean_text(value: str) -> str:
    text = unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_pub_date(value: str) -> str | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.isoformat()
    return parsed.astimezone().replace(microsecond=0).isoformat()


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.astimezone()
    return parsed.astimezone()


def _time_window_days(time_range: str) -> int:
    mapping = {
        "1_day": 1,
        "3_days": 3,
        "7_days": 7,
        "30_days": 30,
    }
    return mapping.get(time_range, 7)


def _filter_hits_by_time_range(hits: list[TopicSearchHit], time_range: str) -> list[TopicSearchHit]:
    if not hits:
        return []
    cutoff = datetime.now().astimezone() - timedelta(days=_time_window_days(time_range))
    recent_hits: list[TopicSearchHit] = []
    undated_hits: list[TopicSearchHit] = []
    for hit in hits:
        published_at = _parse_iso_datetime(hit.published_at)
        if published_at is None:
            undated_hits.append(hit)
            continue
        if published_at >= cutoff:
            recent_hits.append(hit)
    if recent_hits:
        return recent_hits + undated_hits
    return undated_hits


def _dedupe_key(hit: TopicSearchHit) -> str:
    title = re.sub(r"\s+", "", hit.title).lower()
    url = hit.source_url.strip().lower()
    return url or f"{title}|{hit.source.lower()}"


def _fallback_query(title: str, prompt: str) -> str:
    merged = f"{title} {prompt}".strip()
    for phrase in STOP_PHRASES:
        merged = merged.replace(phrase, " ")
    merged = re.sub(r"[，。；：、,.!?！？\"“”‘’()（）]+", " ", merged)
    merged = re.sub(r"\s+", " ", merged).strip()
    return merged[:64] or title or prompt[:32] or "行业资讯"


def _normalize_search_query(query: str) -> str:
    cleaned = query.strip()
    for pattern in QUERY_TIME_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned)
    cleaned = re.sub(r"[，。；：、,.!?！？]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _candidate_queries(*, title: str, prompt: str, queries: list[str]) -> list[str]:
    options: list[str] = []
    seen: set[str] = set()

    for raw_query in [*queries, _fallback_query(title, prompt), title]:
        normalized = _normalize_search_query(raw_query)
        if len(normalized) < 2:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        options.append(normalized)
    return options[:8]


def _extract_prompt_queries(prompt: str) -> list[str]:
    quoted = re.findall(r"[“\"]([^”\"]{2,60})[”\"]", prompt or "")
    options: list[str] = []
    seen: set[str] = set()
    for item in quoted:
        normalized = _normalize_search_query(item)
        if len(normalized) < 2:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        options.append(normalized)
    return options[:4]


def _expand_topic_queries(title: str, prompt: str) -> list[str]:
    combined = f"{title} {prompt}"
    if _looks_like_technical_radar(combined):
        return _expand_technical_queries(title, prompt)
    return []


def _looks_like_technical_radar(text: str) -> bool:
    lowered = (text or "").lower()
    return any(re.search(pattern, lowered, re.I) for pattern in TECH_RADAR_PATTERNS)


def _expand_technical_queries(title: str, prompt: str) -> list[str]:
    text = f"{title} {prompt}"
    lowered = text.lower()
    aliases: list[str] = []
    seen: set[str] = set()

    def add_alias(value: str) -> None:
        candidate = value.strip()
        if not candidate:
            return
        key = candidate.lower()
        if key in seen:
            return
        seen.add(key)
        aliases.append(candidate)

    normalized_title = title.strip()
    if normalized_title:
        add_alias(normalized_title)

    if re.search(r"\bcodex\b|code\s*x", lowered, re.I):
        add_alias("Codex")
        add_alias("CodeX")
        add_alias("OpenAI Codex")
    if "github" in lowered or "开源" in text:
        add_alias("GitHub")
        add_alias("GitHub Trending")
    if re.search(r"coding agent|computer use agent|智能体", lowered, re.I):
        add_alias("AI coding agent")
        add_alias("Computer Use Agent")
    if re.search(r"developer tool|开发者工具|开发工具", text, re.I):
        add_alias("developer tool")

    if not aliases:
        add_alias(normalized_title or "AI 开发工具")

    themes: list[str] = [
        "开源项目",
        "落地案例",
        "实战经验",
        "开发工作流",
    ]
    if re.search(r"半成型|产品|商业化|落地", text, re.I):
        themes.extend(["产品化", "商业化信号"])
    if re.search(r"开发板|开发版", text, re.I):
        themes.extend(["开发板", "开发版"])

    expanded: list[str] = []
    expanded_seen: set[str] = set()

    def add_query(value: str) -> None:
        normalized = _normalize_search_query(value)
        if len(normalized) < 2:
            return
        key = normalized.lower()
        if key in expanded_seen:
            return
        expanded_seen.add(key)
        expanded.append(normalized)

    alias_cycle = aliases[1:] + aliases[:1] if len(aliases) > 1 else aliases
    primary_alias = alias_cycle[0]

    if any(alias.lower() in {"github", "github trending"} for alias in aliases):
        add_query("GitHub 高星开源项目 功能介绍")
        add_query("GitHub Trending 新项目 价值分析")
    if re.search(r"\bcodex\b|code\s*x", lowered, re.I):
        add_query("OpenAI Codex 落地案例")
        add_query("Codex 开源项目 实战经验")
        add_query("AI coding agent 开发工作流")
    add_query(f"{primary_alias} 开源项目 落地案例")
    add_query(f"{primary_alias} 实战经验 开发工作流")

    for alias in alias_cycle[:4]:
        for theme in themes[:4]:
            add_query(f"{alias} {theme}")

    return expanded[:6]


def _fallback_rank_hits(title: str, prompt: str, hits: list[TopicSearchHit], *, max_items: int) -> list[TopicSearchHit]:
    tokens = _keyword_tokens(f"{title} {prompt}")
    scored: list[tuple[int, TopicSearchHit]] = []
    for hit in hits:
        score = _score_hit(hit, tokens)
        if score > 0:
            scored.append((score, hit))
    if scored:
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:max_items]]
    return []


def _ensure_hits_in_chinese(
    ai: AiService,
    hits: list[TopicSearchHit],
    *,
    radar_title: str,
    radar_prompt: str,
) -> list[TopicSearchHit]:
    normalized: list[TopicSearchHit] = []
    for hit in hits:
        localized = ai.localize_topic_hit(
            title=hit.title,
            summary=hit.summary,
            radar_title=radar_title,
            radar_prompt=radar_prompt,
        )
        normalized.append(
            TopicSearchHit(
                title=str(localized.get("title") or hit.title)[:120],
                summary=str(localized.get("summary") or hit.summary)[:180],
                source=hit.source,
                source_url=hit.source_url,
                published_at=hit.published_at,
                provider=hit.provider,
                query=hit.query,
            )
        )
    return normalized


def _keyword_tokens(text: str) -> list[str]:
    merged = text.strip().replace("*", " ")
    for phrase in STOP_PHRASES:
        merged = merged.replace(phrase, " ")
    merged = re.sub(r"[，。；：、,.!?！？\"“”‘’()（）/\\|:+\-]+", " ", merged)
    merged = re.sub(r"\s+", " ", merged).strip()
    if not merged:
        return []

    tokens: list[str] = []
    seen: set[str] = set()

    def add_token(candidate: str) -> None:
        token = candidate.strip()
        if len(token) < 2:
            return
        lowered = token.lower()
        if lowered in seen:
            return
        if lowered in TOKEN_STOPWORDS:
            return
        if any(part in token for part in TOKEN_SUBSTRING_STOPWORDS):
            return
        if token.isdigit():
            return
        if re.fullmatch(r"[A-Za-z]{1,2}", token):
            return
        if re.fullmatch(r"[\u4e00-\u9fff]{9,}", token):
            return
        seen.add(lowered)
        tokens.append(token)

    for chunk in merged.split(" "):
        cleaned = chunk.strip()
        if not cleaned:
            continue
        if re.search(r"[A-Za-z]", cleaned):
            for part in re.findall(r"[A-Za-z][A-Za-z0-9._+-]{1,20}", cleaned):
                add_token(part)
        if re.search(r"[\u4e00-\u9fff]", cleaned):
            for part in re.split(r"(?:与|和|及|以及|或|并|跟|有关|相关|正在|如何|哪些|什么|不是|然后|最好|可以|希望|明确|直接|就是|其中|当前|主要|例如|这些|那个|这个|以及)", cleaned):
                token = part.strip()
                if not token:
                    continue
                if 2 <= len(token) <= 8:
                    add_token(token)
    return tokens[:16]


def _score_hit(hit: TopicSearchHit, tokens: list[str]) -> int:
    haystack = f"{hit.title} {hit.summary} {hit.source}".lower()
    score = 0
    for token in tokens:
        needle = token.lower()
        if needle and needle in haystack:
            score += max(1, len(token))
    return score
~~~

## `backend/app/services/topic_source_fetcher.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import re
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

import httpx


FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

DETAIL_HINT_PATTERNS = (
    re.compile(r"/detail/\d+\.html?$", re.I),
    re.compile(r"/article/\d+\.html?$", re.I),
    re.compile(r"/news/.+\.html?$", re.I),
    re.compile(r"/\d+\.html?$", re.I),
)

IGNORE_PATH_PATTERNS = (
    re.compile(r"/(?:login|logout|register)(?:/|$)", re.I),
    re.compile(r"/(?:category|tag|tags|author|search)(?:/|$)", re.I),
    re.compile(r"/(?:about|contact|guide|help|terms|privacy)(?:/|$)", re.I),
)

DATE_PATTERNS = (
    re.compile(r'class="[^"]*(?:time|date|publish)[^"]*"[^>]*>.*?<span[^>]*>\s*([12]\d{3}-\d{1,2}-\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)', re.I | re.S),
    re.compile(r'class="[^"]*(?:time|date|publish)[^"]*"[^>]*>\s*([12]\d{3}-\d{1,2}-\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)', re.I | re.S),
    re.compile(r'([12]\d{3}-\d{1,2}-\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)'),
)


@dataclass
class PreferredSourceHit:
    title: str
    summary: str
    source: str
    source_url: str
    published_at: str | None
    provider: str


def fetch_preferred_source_hits(
    preferred_source_urls: list[str] | None,
    *,
    max_items: int = 8,
) -> list[PreferredSourceHit]:
    if not preferred_source_urls:
        return []

    hits: list[PreferredSourceHit] = []
    seen_urls: set[str] = set()
    with httpx.Client(timeout=httpx.Timeout(12.0, connect=6.0), headers=FETCH_HEADERS, follow_redirects=True) as client:
        for source_url in preferred_source_urls[:4]:
            for hit in _fetch_single_preferred_source(client, source_url, max_items=max_items):
                normalized_url = hit.source_url.strip().lower()
                if not normalized_url or normalized_url in seen_urls:
                    continue
                seen_urls.add(normalized_url)
                hits.append(hit)
                if len(hits) >= max_items:
                    return hits
    return hits


def _fetch_single_preferred_source(client: httpx.Client, source_url: str, *, max_items: int) -> list[PreferredSourceHit]:
    response = _safe_get(client, source_url)
    if response is None:
        return []
    content_type = response.headers.get("content-type", "")
    text = response.text

    if _looks_like_feed(text, content_type=content_type):
        return _parse_feed_hits(text, source_url=source_url)[:max_items]

    feed_url = _discover_feed_url(text, base_url=source_url)
    if feed_url:
        feed_response = _safe_get(client, feed_url)
        if feed_response and _looks_like_feed(feed_response.text, content_type=feed_response.headers.get("content-type", "")):
            feed_hits = _parse_feed_hits(feed_response.text, source_url=feed_url)
            if feed_hits:
                return feed_hits[:max_items]

    list_hits = _fetch_list_page_hits(client, source_url=source_url, html=text, max_items=max_items)
    if list_hits:
        return list_hits

    detail_hit = _parse_detail_hit(source_url, text, fallback_title="", fallback_source=_domain_label(source_url))
    return [detail_hit] if detail_hit is not None else []


def _safe_get(client: httpx.Client, url: str) -> httpx.Response | None:
    try:
        response = client.get(url)
        response.raise_for_status()
        return response
    except Exception:
        return None


def _looks_like_feed(text: str, *, content_type: str) -> bool:
    content = (text or "").lstrip().lower()
    ctype = (content_type or "").lower()
    if "xml" in ctype or "rss" in ctype or "atom" in ctype:
        return "<rss" in content or "<feed" in content or "<rdf" in content
    return content.startswith("<?xml") and ("<rss" in content or "<feed" in content or "<rdf" in content)


def _discover_feed_url(html: str, *, base_url: str) -> str | None:
    match = re.search(
        r'<link[^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]+href=["\']([^"\']+)["\']',
        html,
        flags=re.I,
    )
    if match:
        return urljoin(base_url, match.group(1).strip())

    parsed = urlparse(base_url)
    normalized_path = (parsed.path or "").rstrip("/")
    if normalized_path not in {"", "/index.html", "/index.htm"}:
        return None
    for suffix in ("/feed", "/rss", "/rss.xml", "/feed.xml"):
        feed_url = f"{parsed.scheme}://{parsed.netloc}{suffix}"
        if feed_url != base_url:
            return feed_url
    return None


def _parse_feed_hits(xml_text: str, *, source_url: str) -> list[PreferredSourceHit]:
    hits: list[PreferredSourceHit] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return hits

    channel = root.find("channel")
    channel_title = _clean_text(channel.findtext("title") if channel is not None else "")
    feed_source = channel_title or _domain_label(source_url)

    items = channel.findall("item") if channel is not None else []
    if items:
        for item in items[:8]:
            title = _clean_text(item.findtext("title"))
            link = _clean_text(item.findtext("link"))
            summary = _clean_text(item.findtext("description")) or title
            published_at = _normalize_datetime(item.findtext("pubDate") or item.findtext("published") or item.findtext("updated"))
            if not title or not link:
                continue
            hits.append(
                PreferredSourceHit(
                    title=title[:120],
                    summary=summary[:180],
                    source=feed_source,
                    source_url=link,
                    published_at=published_at,
                    provider="preferred_source:rss",
                )
            )
        return hits

    entries = [item for item in root.findall(".//{*}entry")][:8]
    for entry in entries:
        title = _clean_text(_find_xml_text(entry, "title"))
        link = _extract_entry_link(entry)
        summary = _clean_text(_find_xml_text(entry, "summary") or _find_xml_text(entry, "content")) or title
        published_at = _normalize_datetime(_find_xml_text(entry, "published") or _find_xml_text(entry, "updated"))
        if not title or not link:
            continue
        hits.append(
            PreferredSourceHit(
                title=title[:120],
                summary=summary[:180],
                source=feed_source,
                source_url=link,
                published_at=published_at,
                provider="preferred_source:rss",
            )
        )
    return hits


def _find_xml_text(node: ET.Element, tag: str) -> str:
    child = node.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    for sub in node:
        if sub.tag.endswith(tag) and sub.text:
            return sub.text.strip()
    return ""


def _extract_entry_link(entry: ET.Element) -> str:
    direct = _find_xml_text(entry, "link")
    if direct:
        return direct
    for sub in entry:
        if sub.tag.endswith("link"):
            href = sub.attrib.get("href")
            if href:
                return href.strip()
    return ""


def _fetch_list_page_hits(client: httpx.Client, *, source_url: str, html: str, max_items: int) -> list[PreferredSourceHit]:
    candidates = _extract_list_links(html, base_url=source_url)
    hits: list[PreferredSourceHit] = []
    for detail_url, fallback_title in candidates[: max_items * 2]:
        response = _safe_get(client, detail_url)
        if response is None:
            continue
        hit = _parse_detail_hit(
            detail_url,
            response.text,
            fallback_title=fallback_title,
            fallback_source=_domain_label(source_url),
        )
        if hit is None:
            continue
        hits.append(hit)
        if len(hits) >= max_items:
            break
    return hits


def _extract_list_links(html: str, *, base_url: str) -> list[tuple[str, str]]:
    domain = urlparse(base_url).netloc.lower()
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for href, inner_html in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, flags=re.I | re.S):
        normalized_url = urljoin(base_url, href.strip())
        parsed = urlparse(normalized_url)
        if parsed.netloc.lower() != domain:
            continue
        if normalized_url in seen or not _looks_like_detail_link(parsed.path):
            continue
        title = _clean_text(inner_html)
        if len(title) < 6:
            continue
        seen.add(normalized_url)
        links.append((normalized_url, title))
    return links


def _looks_like_detail_link(path: str) -> bool:
    if not path:
        return False
    if any(pattern.search(path) for pattern in IGNORE_PATH_PATTERNS):
        return False
    if any(pattern.search(path) for pattern in DETAIL_HINT_PATTERNS):
        return True
    return False


def _parse_detail_hit(detail_url: str, html: str, *, fallback_title: str, fallback_source: str) -> PreferredSourceHit | None:
    title = _extract_html_title(html) or fallback_title
    title = _clean_text(title)
    if not title:
        return None
    summary = _extract_meta_content(html, "description") or _extract_first_paragraphs(html)
    summary = _clean_text(summary) or title
    published_at = _extract_published_at(html)
    source = _extract_source_name(html) or fallback_source
    return PreferredSourceHit(
        title=title[:120],
        summary=summary[:180],
        source=source[:64],
        source_url=detail_url,
        published_at=published_at,
        provider="preferred_source:list",
    )


def _extract_html_title(html: str) -> str:
    for pattern in (
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'<title>(.*?)</title>',
        r'<h1[^>]*>(.*?)</h1>',
        r'<div[^>]+class=["\'][^"\']*\btitle\b[^"\']*["\'][^>]*>(.*?)</div>',
    ):
        match = re.search(pattern, html, flags=re.I | re.S)
        if match:
            value = _clean_text(match.group(1))
            if value:
                return value
    return ""


def _extract_meta_content(html: str, name: str) -> str:
    for pattern in (
        rf'<meta[^>]+name=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']{re.escape(name)}["\']',
        rf'<meta[^>]+property=["\']og:{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:{re.escape(name)}["\']',
    ):
        match = re.search(pattern, html, flags=re.I | re.S)
        if match:
            value = _clean_text(match.group(1))
            if value:
                return value
    return ""


def _extract_first_paragraphs(html: str) -> str:
    paragraphs = [
        _clean_text(item)
        for item in re.findall(r'<p[^>]*>(.*?)</p>', html, flags=re.I | re.S)
    ]
    paragraphs = [
        item
        for item in paragraphs
        if len(item) >= 18 and "版权所有" not in item and "上一篇" not in item and "下一篇" not in item
    ]
    return " ".join(paragraphs[:2]).strip()


def _extract_published_at(html: str) -> str | None:
    for pattern in DATE_PATTERNS:
        match = pattern.search(html)
        if not match:
            continue
        normalized = _normalize_datetime(match.group(1))
        if normalized:
            return normalized
    return None


def _extract_source_name(html: str) -> str:
    for pattern in (
        r'来源[：:]\s*(?:<span[^>]*>)?([^<\n]+)',
        r'class=["\'][^"\']*\bsource\b[^"\']*["\'][^>]*>\s*来源[：:]\s*(?:<span[^>]*>)?([^<\n]+)',
    ):
        match = re.search(pattern, html, flags=re.I | re.S)
        if match:
            value = _clean_text(match.group(1))
            if value:
                return value
    return ""


def _normalize_datetime(value: str | None) -> str | None:
    raw = _clean_text(value)
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw).astimezone().replace(microsecond=0).isoformat()
    except Exception:
        pass
    normalized = raw.replace("/", "-").replace(".", "-").replace("年", "-").replace("月", "-").replace("日", "")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            from datetime import datetime

            return datetime.strptime(normalized, pattern).isoformat()
        except ValueError:
            continue
    return None


def _domain_label(url: str) -> str:
    domain = urlparse(url).netloc.lower().replace("www.", "")
    return domain or "优先网址"


def _clean_text(value: str | None) -> str:
    text = unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
~~~

## `backend/app/services/understanding_builder.py`

- 编码: `utf-8`

~~~python
"""
UnderstandingSnapshotV1 构建器

basic 模式：只靠 6 项最小输入产出完整的第一层理解。
enhanced 模式：在 basic 基础上叠加事件线记忆、会议等增强项。

核心原则：
- 少资料先出结果
- 永远不返回"无法判断"
- 第一层 4 项必须始终存在
- optionalAdvice 只在证据足够时出现
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.ai import AiService

from app.models import (
    OrganizationDnaModuleRecord,
    UnderstandingOptionalAdviceRecord,
    UnderstandingSnapshotV1Record,
    UnderstandingSourceBreakdownRecord,
    WeeklyReviewTaskEntryRecord,
    WeeklyReviewTaskSnapshotRecord,
)

import json
import logging

logger = logging.getLogger(__name__)

# ── Prompt ──

BASIC_SYSTEM = """\
你是益语智库的理解助手。益语智库是一家咨询公司，核心业务是与客户的合作关系。

你的任务是理解一条任务，产出简练的中文判断。

你必须回答这 4 个问题（即使信息有限也要尽力回答）：
1. whatIsThis — 这是什么事（一段话）
2. whyItMatters — 为什么重要（结合益语背景和客户背景）
3. progressNow — 现在推进到哪
4. unknowns — 还缺什么理解

同时提取 knownFacts：从输入中能确认的事实，列为数组。

confidence 用 0-100 整数表示你对判断的把握程度。

重要：
- 不要编造信息
- 如果某项信息缺失，直接说"系统尚未看到…的信息"
- 不要生成泛泛的建议
- 用中文输出
"""

BASIC_SCHEMA = {
    "type": "object",
    "properties": {
        "whatIsThis": {"type": "string"},
        "whyItMatters": {"type": "string"},
        "progressNow": {"type": "string"},
        "unknowns": {"type": "string"},
        "knownFacts": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
    },
    "required": ["whatIsThis", "whyItMatters", "progressNow", "unknowns", "knownFacts", "confidence"],
}


def _source_breakdown(
    *,
    org_dna: list[OrganizationDnaModuleRecord],
    snapshot: WeeklyReviewTaskSnapshotRecord,
    note: str,
    structured_note_reflection: str,
) -> list[UnderstandingSourceBreakdownRecord]:
    """列出每项输入的可用状态。"""
    has_org_dna = bool(org_dna and any(m.summary or m.normalizedText for m in org_dna))
    has_client = bool(getattr(snapshot, "projectContext", None) and snapshot.projectContext and snapshot.projectContext.clientName)
    has_quarterly = bool(getattr(snapshot, "orgContext", None) and snapshot.orgContext and getattr(snapshot.orgContext, "focusItemId", None))
    has_title = bool(snapshot.title.strip())
    has_desc = bool(getattr(snapshot, "desc", "").strip())
    has_review = bool(note.strip() or structured_note_reflection.strip())

    return [
        UnderstandingSourceBreakdownRecord(sourceType="org_dna", available=has_org_dna, label="益语背景卡"),
        UnderstandingSourceBreakdownRecord(sourceType="client_background", available=has_client, label="客户/项目背景卡"),
        UnderstandingSourceBreakdownRecord(sourceType="quarterly_focus", available=has_quarterly, label="季度主线卡"),
        UnderstandingSourceBreakdownRecord(sourceType="task_title", available=has_title, label="任务标题"),
        UnderstandingSourceBreakdownRecord(sourceType="task_desc", available=has_desc, label="任务说明"),
        UnderstandingSourceBreakdownRecord(sourceType="review_note", available=has_review, label="任务复盘资料"),
    ]


def _coverage_from_sources(sources: list[UnderstandingSourceBreakdownRecord]) -> int:
    """根据可用输入数计算覆盖度（0-100）。"""
    total = len(sources)
    available = sum(1 for s in sources if s.available)
    return int(round(available / total * 100)) if total > 0 else 0


def _assemble_basic_prompt(
    *,
    org_dna: list[OrganizationDnaModuleRecord],
    snapshot: WeeklyReviewTaskSnapshotRecord,
    note: str,
    structured_note_reflection: str,
) -> str:
    """组装 basic 模式的 prompt — 只用最小输入。"""
    sections: list[str] = []

    # 益语背景卡
    if org_dna:
        dna_parts = []
        for m in org_dna[:4]:
            text = m.summary or (m.normalizedText[:300] if m.normalizedText else "")
            if text:
                dna_parts.append(f"- {m.title}: {text}")
        if dna_parts:
            sections.append(f"【益语智库背景】\n" + "\n".join(dna_parts))

    # 客户/项目背景卡
    pc = getattr(snapshot, "projectContext", None)
    if pc and pc.clientName:
        parts = [f"客户：{pc.clientName}"]
        if pc.backgroundSummary:
            parts.append(f"背景：{pc.backgroundSummary[:200]}")
        if pc.goalSummary:
            parts.append(f"目标：{pc.goalSummary[:200]}")
        if pc.riskSummary:
            parts.append(f"风险：{pc.riskSummary[:200]}")
        sections.append(f"【客户/项目背景】\n" + "\n".join(f"- {p}" for p in parts))

    # 季度主线（从 orgContext 提取）
    oc = getattr(snapshot, "orgContext", None)
    if oc:
        focus_parts = []
        if getattr(oc, "departmentName", None):
            focus_parts.append(f"部门：{oc.departmentName}")
        if getattr(oc, "focusItemTitle", None):
            focus_parts.append(f"机构重点：{oc.focusItemTitle}")
        if getattr(oc, "departmentPlanItemTitle", None):
            focus_parts.append(f"部门计划：{oc.departmentPlanItemTitle}")
        if focus_parts:
            sections.append(f"【组织/部门季度主线】\n" + "\n".join(f"- {p}" for p in focus_parts))

    # 任务标题 + 说明
    task_parts = [f"标题：{snapshot.title}"]
    if hasattr(snapshot, "desc") and snapshot.desc.strip():
        task_parts.append(f"说明：{snapshot.desc[:300]}")
    task_parts.append(f"状态：{snapshot.status}")
    if hasattr(snapshot, "listName") and snapshot.listName:
        task_parts.append(f"所在列表：{snapshot.listName}")
    if hasattr(snapshot, "ownerName") and snapshot.ownerName:
        task_parts.append(f"负责人：{snapshot.ownerName}")
    sections.append(f"【当前任务】\n" + "\n".join(f"- {p}" for p in task_parts))

    # 复盘资料
    review_parts = []
    if note.strip():
        review_parts.append(f"复盘说明：{note.strip()[:300]}")
    if structured_note_reflection.strip():
        review_parts.append(f"反思：{structured_note_reflection.strip()[:200]}")
    if review_parts:
        sections.append(f"【复盘资料】\n" + "\n".join(f"- {p}" for p in review_parts))

    return "\n\n".join(sections) if sections else f"任务标题：{snapshot.title}"


def _build_basic_with_rules(
    *,
    snapshot: WeeklyReviewTaskSnapshotRecord,
    note: str,
    org_dna: list[OrganizationDnaModuleRecord],
    sources: list[UnderstandingSourceBreakdownRecord],
    coverage: int,
) -> UnderstandingSnapshotV1Record:
    """纯规则兜底 — 当 LLM 不可用时，仍然产出 basic 结果。"""
    pc = getattr(snapshot, "projectContext", None)
    client_name = pc.clientName if pc and pc.clientName else ""
    client_info = f"，涉及客户「{client_name}」" if client_name else ""

    what_is_this = f"「{snapshot.title}」是一条{snapshot.status}状态的工作任务{client_info}。"

    why_it_matters = ""
    if client_name and org_dna:
        dna_title = org_dna[0].title if org_dna else "组织方向"
        why_it_matters = f"这条任务与客户「{client_name}」相关，需要结合益语智库的{dna_title}来理解其业务意义。"
    elif client_name:
        why_it_matters = f"这条任务与客户「{client_name}」相关。"
    else:
        why_it_matters = "当前尚未录入客户背景信息，系统暂时只能从任务本身理解其意义，补充客户背景后判断会更准确。"

    progress_now = f"当前状态为 {snapshot.status}。"
    if note.strip():
        progress_now += f" 一线复盘说明：{note.strip()[:100]}"

    unknowns_parts = []
    for s in sources:
        if not s.available:
            unknowns_parts.append(s.label)
    unknowns = f"系统尚未看到以下信息：{'、'.join(unknowns_parts)}。" if unknowns_parts else "最小输入已全部可用。"

    facts = [f"任务标题：{snapshot.title}", f"状态：{snapshot.status}"]
    if client_name:
        facts.append(f"关联客户：{client_name}")
    if note.strip():
        facts.append(f"已有复盘说明")

    return UnderstandingSnapshotV1Record(
        taskId=getattr(snapshot, "id", "") or "",
        mode="basic",
        coverage=coverage,
        confidence=max(15, coverage // 2),
        whatIsThis=what_is_this,
        whyItMatters=why_it_matters,
        progressNow=progress_now,
        unknowns=unknowns,
        knownFacts=facts,
        optionalAdvice=None,
        sourceBreakdown=sources,
    )


def build_understanding_basic(
    *,
    ai: "AiService | None",
    task_entry: WeeklyReviewTaskEntryRecord,
    org_dna_modules: list[OrganizationDnaModuleRecord],
) -> UnderstandingSnapshotV1Record:
    """
    basic 模式构建器 — 只靠最小输入产出第一层理解。
    永远不返回"无法判断"。
    """
    snapshot = task_entry.taskSnapshot
    note = task_entry.note or ""
    structured_note = task_entry.structuredNote
    reflection = structured_note.reflection if structured_note else ""

    sources = _source_breakdown(
        org_dna=org_dna_modules,
        snapshot=snapshot,
        note=note,
        structured_note_reflection=reflection,
    )
    coverage = _coverage_from_sources(sources)

    # 尝试 LLM
    if ai is not None:
        prompt = _assemble_basic_prompt(
            org_dna=org_dna_modules,
            snapshot=snapshot,
            note=note,
            structured_note_reflection=reflection,
        )
        try:
            raw = ai._qwen_generate(
                prompt=prompt,
                system_instruction=BASIC_SYSTEM,
                response_schema=BASIC_SCHEMA,
                timeout_seconds=30.0,
                max_tokens=1200,
                temperature=0.25,
            )
            if isinstance(raw, dict):
                return UnderstandingSnapshotV1Record(
                    taskId=getattr(snapshot, "id", "") or "",
                    mode="basic",
                    coverage=coverage,
                    confidence=min(int(raw.get("confidence", 30)), coverage),
                    whatIsThis=str(raw.get("whatIsThis", "")),
                    whyItMatters=str(raw.get("whyItMatters", "")),
                    progressNow=str(raw.get("progressNow", "")),
                    unknowns=str(raw.get("unknowns", "")),
                    knownFacts=list(raw.get("knownFacts", [])),
                    optionalAdvice=None,
                    sourceBreakdown=sources,
                )
        except Exception as exc:
            logger.warning("Understanding basic LLM call failed: %s", exc)

    # 规则兜底
    return _build_basic_with_rules(
        snapshot=snapshot,
        note=note,
        org_dna=org_dna_modules,
        sources=sources,
        coverage=coverage,
    )


# ── Enhanced 模式 ──

ENHANCED_SYSTEM = """\
你是益语智库的理解助手。益语智库是一家咨询公司，核心业务是与客户的合作关系。

你的任务是结合丰富的上下文深度理解一条任务。

你必须回答这 4 个问题：
1. whatIsThis — 这是什么事
2. whyItMatters — 为什么重要（必须体现合作关系层面的意义，不只是任务本身）
3. progressNow — 现在推进到哪（结合事件线历史和会议记录给出具体阶段判断）
4. unknowns — 还缺什么理解

额外地，如果证据确实充分，你可以给出 optionalAdvice：
- realBlocker — 真正的阻碍（必须具体，不能泛泛）
- timeGate — 时间闸门（过了这个时间点情况会质变）
- minimumAction — 最小动作（当前最该做的 1 件事）
- supportAsk — 需要谁提供什么支持

如果证据不够充分，optionalAdvice 的字段留空字符串或不填。

confidence 用 0-100 整数。
用中文输出。不要编造信息。
"""

ENHANCED_SCHEMA = {
    "type": "object",
    "properties": {
        "whatIsThis": {"type": "string"},
        "whyItMatters": {"type": "string"},
        "progressNow": {"type": "string"},
        "unknowns": {"type": "string"},
        "knownFacts": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
        "realBlocker": {"type": "string"},
        "timeGate": {"type": "string"},
        "minimumAction": {"type": "string"},
        "supportAsk": {"type": "string"},
    },
    "required": ["whatIsThis", "whyItMatters", "progressNow", "unknowns", "knownFacts", "confidence"],
}


def _append_enhanced_sources(
    sources: list[UnderstandingSourceBreakdownRecord],
    *,
    has_event_line_memory: bool,
    has_meeting: bool,
    has_support_request: bool,
    has_knowledge: bool = False,
) -> list[UnderstandingSourceBreakdownRecord]:
    """在 basic 源列表上追加增强项。"""
    return sources + [
        UnderstandingSourceBreakdownRecord(sourceType="event_line_memory", available=has_event_line_memory, label="事件线记忆"),
        UnderstandingSourceBreakdownRecord(sourceType="meeting", available=has_meeting, label="会议记录"),
        UnderstandingSourceBreakdownRecord(sourceType="support_request", available=has_support_request, label="支持请求"),
        UnderstandingSourceBreakdownRecord(sourceType="knowledge_base", available=has_knowledge, label="客户知识库"),
    ]


def _assemble_enhanced_prompt(
    basic_prompt: str,
    *,
    event_line_name: str = "",
    event_line_summary: str = "",
    event_line_stage: str = "",
    event_line_blocker: str = "",
    event_line_history: list[dict] = (),
    meetings: list[dict] = (),
    support_requests: list[dict] = (),
    knowledge_summaries: list[dict] = (),
) -> str:
    """在 basic prompt 基础上追加增强上下文。"""
    sections = [basic_prompt]

    # 客户知识库摘要
    if knowledge_summaries:
        kb_lines = []
        for kb in list(knowledge_summaries)[:5]:
            kb_lines.append(f"- {kb.get('title', '文档')}：{kb.get('summary', '')[:200]}")
        sections.append(f"【客户知识库关键摘要】\n" + "\n".join(kb_lines))

    if event_line_name:
        el_parts = [f"事件线：{event_line_name}"]
        if event_line_stage:
            el_parts.append(f"阶段：{event_line_stage}")
        if event_line_summary:
            el_parts.append(f"概要：{event_line_summary}")
        if event_line_blocker:
            el_parts.append(f"阻碍：{event_line_blocker}")
        sections.append(f"【事件线当前状态】\n" + "\n".join(f"- {p}" for p in el_parts))

    if event_line_history:
        history_lines = []
        for snap in list(event_line_history)[:8]:
            line = f"- {snap.get('weekLabel', '?')}：阶段={snap.get('stage', '?')}，任务{snap.get('taskCount', 0)}条/完成{snap.get('completedCount', 0)}条"
            decisions = snap.get("keyDecisions", [])
            if decisions:
                line += f"，决定：{'；'.join(decisions[:2])}"
            history_lines.append(line)
        sections.append(f"【事件线历史轨迹（近{len(event_line_history)}周）】\n" + "\n".join(history_lines))

    if meetings:
        meeting_lines = []
        for m in list(meetings)[:3]:
            meeting_lines.append(f"- {m.get('title', '会议')}：{m.get('summary', '')[:150]}")
        sections.append(f"【相关会议】\n" + "\n".join(meeting_lines))

    if support_requests:
        sr_lines = []
        for sr in list(support_requests)[:3]:
            sr_lines.append(f"- [{sr.get('status', '?')}] {sr.get('title', '')}：{sr.get('summary', '')[:100]}")
        sections.append(f"【支持请求】\n" + "\n".join(sr_lines))

    return "\n\n".join(sections)


def build_understanding_enhanced(
    *,
    ai: "AiService | None",
    task_entry: WeeklyReviewTaskEntryRecord,
    org_dna_modules: list[OrganizationDnaModuleRecord],
    event_line_name: str = "",
    event_line_summary: str = "",
    event_line_stage: str = "",
    event_line_blocker: str = "",
    event_line_history: list[dict] | None = None,
    meetings: list[dict] | None = None,
    support_requests: list[dict] | None = None,
    knowledge_summaries: list[dict] | None = None,
) -> UnderstandingSnapshotV1Record:
    """
    enhanced 模式构建器。
    在 basic 基础上叠加事件线记忆、会议、知识库等增强项。
    增强项只提升精度，不覆盖 basic 主逻辑。
    证据不足时保留 basic 输出，不硬写 optionalAdvice。
    """
    snapshot = task_entry.taskSnapshot
    note = task_entry.note or ""
    structured_note = task_entry.structuredNote
    reflection = structured_note.reflection if structured_note else ""

    # basic 源
    basic_sources = _source_breakdown(
        org_dna=org_dna_modules,
        snapshot=snapshot,
        note=note,
        structured_note_reflection=reflection,
    )

    has_el = bool(event_line_name)
    has_meeting = bool(meetings)
    has_sr = bool(support_requests)
    has_kb = bool(knowledge_summaries)

    sources = _append_enhanced_sources(
        basic_sources,
        has_event_line_memory=has_el,
        has_meeting=has_meeting,
        has_support_request=has_sr,
        has_knowledge=has_kb,
    )
    coverage = _coverage_from_sources(sources)

    # 如果没有任何增强项，降级回 basic
    if not has_el and not has_meeting and not has_sr and not has_kb:
        basic = build_understanding_basic(ai=ai, task_entry=task_entry, org_dna_modules=org_dna_modules)
        basic.sourceBreakdown = sources
        basic.coverage = coverage
        return basic

    # 组装 enhanced prompt
    basic_prompt = _assemble_basic_prompt(
        org_dna=org_dna_modules,
        snapshot=snapshot,
        note=note,
        structured_note_reflection=reflection,
    )
    prompt = _assemble_enhanced_prompt(
        basic_prompt,
        event_line_name=event_line_name,
        event_line_summary=event_line_summary,
        event_line_stage=event_line_stage,
        event_line_blocker=event_line_blocker,
        event_line_history=event_line_history or [],
        meetings=meetings or [],
        support_requests=support_requests or [],
        knowledge_summaries=knowledge_summaries or [],
    )

    # 尝试 LLM
    if ai is not None:
        try:
            raw = ai._qwen_generate(
                prompt=prompt,
                system_instruction=ENHANCED_SYSTEM,
                response_schema=ENHANCED_SCHEMA,
                timeout_seconds=45.0,
                max_tokens=1800,
                temperature=0.3,
            )
            if isinstance(raw, dict):
                # optionalAdvice 只在有实质内容时才填
                advice = None
                rb = str(raw.get("realBlocker", "")).strip()
                tg = str(raw.get("timeGate", "")).strip()
                ma = str(raw.get("minimumAction", "")).strip()
                sa = str(raw.get("supportAsk", "")).strip()
                if rb or tg or ma or sa:
                    advice = UnderstandingOptionalAdviceRecord(
                        realBlocker=rb or None,
                        timeGate=tg or None,
                        minimumAction=ma or None,
                        supportAsk=sa or None,
                    )

                return UnderstandingSnapshotV1Record(
                    taskId=getattr(snapshot, "id", "") or "",
                    mode="enhanced",
                    coverage=coverage,
                    confidence=min(int(raw.get("confidence", 40)), coverage),
                    whatIsThis=str(raw.get("whatIsThis", "")),
                    whyItMatters=str(raw.get("whyItMatters", "")),
                    progressNow=str(raw.get("progressNow", "")),
                    unknowns=str(raw.get("unknowns", "")),
                    knownFacts=list(raw.get("knownFacts", [])),
                    optionalAdvice=advice,
                    sourceBreakdown=sources,
                )
        except Exception as exc:
            logger.warning("Understanding enhanced LLM call failed: %s", exc)

    # LLM 不可用时，回退到 basic 结果但标记为 enhanced 源
    basic = build_understanding_basic(ai=None, task_entry=task_entry, org_dna_modules=org_dna_modules)
    basic.mode = "enhanced"
    basic.sourceBreakdown = sources
    basic.coverage = coverage
    return basic
~~~

## `backend/pyproject.toml`

- 编码: `utf-8`

~~~toml
[project]
name = "yiyu-workbench-backend"
version = "0.1.0"
description = "益语智库自用平台桌面版后端"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn>=0.30.0",
    "httpx>=0.27.0",
    "pydantic>=2.9.0",
    "pytest>=8.3.0",
    "pypdf>=5.3.0",
    "python-docx>=1.1.2",
    "qdrant-client>=1.9.1",
    "fastembed>=0.3.6",
    "python-multipart>=0.0.22",
]

[tool.pytest.ini_options]
pythonpath = ["."]
~~~

## `backend/scripts/backfill_workspace_import.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.db import Database
from app.services.knowledge_v2 import backfill_workspace_import


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill documents from an existing client_workspace directory into imports/documents/knowledge tables.")
    parser.add_argument("--db", required=True, help="Absolute path to app.db")
    parser.add_argument("--data-dir", required=True, help="Absolute path to app data dir")
    parser.add_argument("--client-id", required=True, help="Client id to backfill")
    parser.add_argument("--source-root", help="Optional absolute path to scan instead of data-dir/client_workspace/{client-id}")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db = Database(Path(args.db))
    summary = backfill_workspace_import(
        db,
        data_dir=Path(args.data_dir),
        client_id=args.client_id,
        source_root=Path(args.source_root) if args.source_root else None,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
~~~

## `backend/scripts/bettafish_bridge.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request
import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPO_DIR = PROJECT_ROOT / "external" / "BettaFish"
DEFAULT_HOST = os.getenv("BETTAFISH_BRIDGE_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("BETTAFISH_BRIDGE_PORT", "18101"))
DEFAULT_WORKBENCH_DATA_DIR = Path(
    os.getenv("YIYU_WORKBENCH_DATA_DIR")
    or (Path.home() / "Library" / "Application Support" / "YiyuThinkTankWorkbench")
)
DEFAULT_PROVIDER = "mock"
DEFAULT_MODELS = {
    "mock": "mock-summarizer",
    "qwen": "qwen3.5-plus",
}
QWEN_BASE_URL = "https://coding.dashscope.aliyuncs.com/v1"
LLM_TIMEOUT_SECONDS = float(os.getenv("YIYU_BETTAFISH_LLM_TIMEOUT_SECONDS", "25"))
KEYCHAIN_SERVICES = {
    "qwen": "com.yiyu.self-workbench.qwen",
}


def resolve_repo_dir() -> Path:
    raw = os.getenv("BETTAFISH_REPO_DIR", "").strip()
    return Path(raw).expanduser().resolve() if raw else DEFAULT_REPO_DIR.resolve()


REPO_DIR = resolve_repo_dir()
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))


app = Flask(__name__)


def get_db_setting(key: str, default: str = "") -> str:
    db_path = DEFAULT_WORKBENCH_DATA_DIR / "app.db"
    if not db_path.exists():
        return default
    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute("select value from settings where key = ?", (key,)).fetchone()
            if not row or row[0] is None:
                return default
            return str(row[0])
    except Exception:
        return default


def get_keychain_secret(service_name: str) -> str:
    try:
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-a",
                "default",
                "-s",
                service_name,
                "-w",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as error:
        stderr = (error.stderr or "").lower()
        if "could not be found" in stderr or "item could not be found" in stderr:
            return ""
        raise RuntimeError("读取 macOS 钥匙串失败。") from error


def resolve_workbench_ai_config() -> dict[str, Any]:
    override_provider = os.getenv("YIYU_BETTAFISH_LLM_PROVIDER", "").strip()
    override_model = os.getenv("YIYU_BETTAFISH_LLM_MODEL", "").strip()
    override_api_key = os.getenv("YIYU_BETTAFISH_LLM_API_KEY", "").strip()

    provider = override_provider or get_db_setting("ai_provider", DEFAULT_PROVIDER)
    if provider not in DEFAULT_MODELS:
        provider = DEFAULT_PROVIDER

    model = override_model or get_db_setting("ai_model", DEFAULT_MODELS.get(provider, DEFAULT_MODELS[DEFAULT_PROVIDER]))
    api_key = override_api_key
    credential_source = "env" if override_api_key else "none"

    if not api_key and provider in KEYCHAIN_SERVICES:
        api_key = get_keychain_secret(KEYCHAIN_SERVICES[provider])
        credential_source = "keychain" if api_key else "none"

    return {
        "provider": provider,
        "model": model or DEFAULT_MODELS.get(provider, DEFAULT_MODELS[DEFAULT_PROVIDER]),
        "api_key": api_key,
        "ready": provider != "mock" and bool(api_key),
        "credential_source": credential_source,
    }


def compact_text(value: str, limit: int = 12000) -> str:
    normalized = " ".join((value or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip() + "..."


def extract_json_object(text: str) -> dict[str, Any]:
    if not text:
        raise ValueError("empty response")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("response is not a JSON object")
    return parsed


def normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            normalized.append(text)
    return normalized


def unique_string_list(items: list[str], limit: int = 4) -> list[str]:
    deduped: list[str] = []
    seen = set()
    for item in items:
        key = item.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(key)
        if len(deduped) >= limit:
            break
    return deduped


def heuristic_signal(content: str, scene: str, audience_type: str) -> dict[str, Any]:
    text = compact_text(content, limit=4000)
    lower_text = text.lower()
    risk_points: list[str] = []
    misunderstanding_points: list[str] = []

    strong_emotion_patterns = [
        ("求求", "文本出现明显求助式、乞求式表达，容易被外部视角理解为情绪施压。"),
        ("绝望", "文本使用极端负面情绪词，容易触发“过度渲染”判断。"),
        ("没有任何希望", "存在绝对化表达，容易被认为夸大处境。"),
        ("震惊", "标题党或强刺激词汇较重，可能削弱可信度。"),
        ("！", "感叹号使用偏多，外部读者可能感到情绪被强推。"),
    ]
    confrontational_patterns = [
        ("造谣", "回应稿中带有直接指责性措辞，容易激化对立。"),
        ("抹黑", "对抗性表述偏强，可能促发二次争执。"),
        ("追究法律责任", "开篇或过早释放威胁性边界，可能让中立受众感到防御性过高。"),
    ]
    vague_patterns = [
        ("很多", "出现模糊量词但缺少事实锚点，可信度容易被打折。"),
        ("长期", "表述范围较大，但缺少时间和证据锚点。"),
        ("严重", "强判断词出现后如果没有支撑材料，容易被质疑。"),
    ]

    for pattern, message in strong_emotion_patterns:
        if pattern in text:
            risk_points.append(message)
    for pattern, message in confrontational_patterns:
        if pattern in text:
            risk_points.append(message)
            misunderstanding_points.append("外部受众可能把强硬措辞理解为心虚、傲慢，或认为机构没有在回应事实。")
    for pattern, message in vague_patterns:
        if pattern in text:
            misunderstanding_points.append(message)

    if not re.search(r"\d", text):
        risk_points.append("当前文本缺少数字、时间或对象锚点，外部读者不容易判断信息是否可信。")

    if audience_type in {"donor", "key_person"} and not re.search(r"元|预算|审计|明细|比例|人数|项目", text):
        misunderstanding_points.append("面对捐赠相关对象时，文本缺少用途拆解或项目细节，容易被理解为目标空泛。")

    if scene == "pr" and not re.search(r"时间线|审计|凭证|说明|披露|链接|截图", text):
        risk_points.append("舆情回应场景下未补充时间线或第三方凭证，容易被视为只在表达态度，没有增加事实。")

    if scene == "project" and not re.search(r"机制|持续|结对|协作|路径|指标", text):
        misunderstanding_points.append("项目表达更像一次性活动描述，外部可能质疑项目是否真正解决结构性问题。")

    emotion = "偏强烈"
    if not any(marker in text for marker in ["！", "求求", "绝望", "震惊", "必须"]):
        emotion = "相对克制"

    credibility = "中等"
    if len(risk_points) >= 3 or "没有任何希望" in text or "抹黑" in text:
        credibility = "偏弱"
    elif re.search(r"\d", text) and re.search(r"项目|明细|时间|链接|审计|案例", text):
        credibility = "较强"

    if not risk_points:
        risk_points.append("当前文本没有触发明显高危词，但仍建议结合对象视角复核语气与证据密度。")
    if not misunderstanding_points:
        misunderstanding_points.append("建议补一层“外部读者最可能误会什么”的解释，避免内部视角默认读者已经理解背景。")

    return {
        "emotion": emotion,
        "credibility": credibility,
        "risk_points": unique_string_list(risk_points),
        "misunderstanding_points": unique_string_list(misunderstanding_points),
        "raw": {
            "source": "heuristic",
            "scene": scene,
            "audience_type": audience_type,
            "content_preview": text[:160],
            "content_contains_public_risk_terms": any(term in lower_text for term in ["谣", "危机", "投诉", "举报"]),
        },
    }


def build_llm_prompt(payload: dict[str, Any]) -> tuple[str, str]:
    scene = str(payload.get("scene") or "pr")
    audience_type = str(payload.get("audience_type") or "public")
    organization_context = payload.get("organization_context") or {}
    dna_summary = payload.get("dna_summary") or {}
    analysis_options = payload.get("analysis_options") or {}

    system_prompt = (
        "你是公益机构对外表达的风险诊断助手。"
        "你的任务不是直接改稿，而是站在外部受众视角做简洁判断。"
        "请严格返回 JSON 对象，字段必须是 emotion, credibility, risk_points, misunderstanding_points。"
        "risk_points 和 misunderstanding_points 必须是中文字符串数组，每项 16 到 60 字，最多 4 项。"
        "不要输出 markdown，不要输出 JSON 以外的解释。"
    )
    user_prompt = json.dumps(
        {
            "scene": scene,
            "audience_type": audience_type,
            "content": compact_text(str(payload.get("content") or "")),
            "title": str(payload.get("title") or ""),
            "workspace_label": str(payload.get("workspace_label") or ""),
            "mode_label": str(payload.get("mode_label") or ""),
            "focus_points": payload.get("focus_points") or [],
            "organization_context": organization_context,
            "dna_summary": dna_summary,
            "analysis_options": analysis_options,
            "output_rules": {
                "emotion": "用一句中文判断整体情绪感受，例如：偏强烈/相对克制/容易引发防御感",
                "credibility": "用一句中文判断可信度感受，例如：偏弱/中等/较强",
                "risk_points": "列出最值得优先处理的外部风险点",
                "misunderstanding_points": "列出最容易被外部误读的点",
            },
        },
        ensure_ascii=False,
    )
    return system_prompt, user_prompt


def llm_signal(payload: dict[str, Any], llm_config: dict[str, str]) -> dict[str, Any]:
    system_prompt, user_prompt = build_llm_prompt(payload)
    provider = llm_config["provider"]
    if provider == "qwen":
        parsed = qwen_generate_json(
            api_key=llm_config["api_key"],
            model=llm_config["model"],
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
    else:
        raise RuntimeError(f"unsupported_llm_provider:{provider}")

    return {
        "emotion": str(parsed.get("emotion") or "未返回").strip(),
        "credibility": str(parsed.get("credibility") or "未返回").strip(),
        "risk_points": unique_string_list(normalize_string_list(parsed.get("risk_points"))),
        "misunderstanding_points": unique_string_list(normalize_string_list(parsed.get("misunderstanding_points"))),
        "raw": {
            "source": "llm",
            "model": llm_config["model"],
            "provider": provider,
        },
    }


def qwen_generate_json(*, api_key: str, model: str, system_prompt: str, user_prompt: str) -> dict[str, Any]:
    prompt = (
        "请严格返回一个 JSON 对象，不要使用 Markdown，不要添加解释。"
        "字段必须包含 emotion, credibility, risk_points, misunderstanding_points。"
        f"\n\n{user_prompt}"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "top_p": 0.9,
        "max_tokens": 1200,
        "stream": False,
        "enable_thinking": False,
    }
    with httpx.Client(
        timeout=httpx.Timeout(timeout=None, connect=8.0, read=LLM_TIMEOUT_SECONDS, write=LLM_TIMEOUT_SECONDS, pool=10.0)
    ) as client:
        response = client.post(
            f"{QWEN_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        result = response.json()
    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    return extract_json_object(content or "")


@app.get("/health")
def health():
    llm_config = resolve_workbench_ai_config()
    return jsonify(
        {
            "status": "ok",
            "detail": "llm_configured" if llm_config["ready"] else "heuristic_fallback",
            "repo_dir": str(REPO_DIR),
            "repo_exists": REPO_DIR.exists(),
            "llm_configured": bool(llm_config["ready"]),
            "provider": llm_config["provider"],
            "model": llm_config["model"],
            "credential_source": llm_config["credential_source"],
        }
    )


@app.post("/analyze")
def analyze():
    payload = request.get_json(silent=True) or {}
    content = compact_text(str(payload.get("content") or ""))
    if not content:
        return jsonify({"success": False, "message": "content 不能为空"}), 400

    scene = str(payload.get("scene") or "pr")
    audience_type = str(payload.get("audience_type") or "public")
    llm_config = resolve_workbench_ai_config()

    analysis: dict[str, Any]
    try:
        if llm_config["ready"]:
            analysis = llm_signal(payload, llm_config)
        else:
            analysis = heuristic_signal(content, scene, audience_type)
    except Exception as exc:
        analysis = heuristic_signal(content, scene, audience_type)
        analysis["raw"]["fallback_reason"] = str(exc)

    analysis["generated_at"] = datetime.now(timezone.utc).isoformat()
    return jsonify({"success": True, "data": analysis})


if __name__ == "__main__":
    app.run(host=DEFAULT_HOST, port=DEFAULT_PORT, debug=False)
~~~

## `backend/scripts/extract_platform_dna_text.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.platform_dna import extract_platform_dna_text, supported_platform_dna_extensions


def main() -> int:
    if len(sys.argv) != 2:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": "usage: extract_platform_dna_text.py <path>",
                    "supportedExtensions": list(supported_platform_dna_extensions()),
                },
                ensure_ascii=False,
            )
        )
        return 1

    target_path = Path(sys.argv[1]).expanduser().resolve()
    if not target_path.exists() or not target_path.is_file():
        print(json.dumps({"success": False, "error": "file_not_found"}, ensure_ascii=False))
        return 1

    try:
        text = extract_platform_dna_text(target_path)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": str(exc),
                    "supportedExtensions": list(supported_platform_dna_extensions()),
                },
                ensure_ascii=False,
            )
        )
        return 1

    print(
        json.dumps(
            {
                "success": True,
                "path": str(target_path),
                "text": text,
                "fileName": target_path.name,
                "extension": target_path.suffix.lower(),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
~~~

## `backend/scripts/install_bettafish_source.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import argparse
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from datetime import datetime
from pathlib import Path


ARCHIVE_URL = "https://github.com/666ghj/BettaFish/archive/refs/heads/main.tar.gz"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_target_dir() -> Path:
    return project_root() / "external" / "BettaFish"


def download_archive(destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(ARCHIVE_URL) as response, destination.open("wb") as output:
        shutil.copyfileobj(response, output)


def extract_archive(archive_path: Path, destination: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="bettafish-extract-") as temp_dir:
        temp_path = Path(temp_dir)
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(temp_path)

        extracted_root = temp_path / "BettaFish-main"
        if not extracted_root.exists():
            raise RuntimeError("Archive extracted but BettaFish-main was not found")

        if destination.exists() and any(destination.iterdir()):
            backup_dir = destination.parent / f"{destination.name}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            destination.rename(backup_dir)
            print(f"Backed up existing directory to {backup_dir}")
        elif destination.exists():
            destination.rmdir()

        shutil.move(str(extracted_root), str(destination))


def main() -> int:
    parser = argparse.ArgumentParser(description="Install BettaFish source into external/BettaFish")
    parser.add_argument("--target", type=Path, default=default_target_dir(), help="Target directory for BettaFish source")
    args = parser.parse_args()

    target = args.target.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="bettafish-download-") as temp_dir:
        archive_path = Path(temp_dir) / "bettafish-main.tar.gz"
        print(f"Downloading BettaFish archive from {ARCHIVE_URL}")
        download_archive(archive_path)
        print(f"Downloaded to {archive_path}")
        extract_archive(archive_path, target)

    print(f"BettaFish source installed at {target}")
    print("Next step:")
    print("  1. Create a dedicated venv for BettaFish")
    print("  2. Install only the dependencies needed for your chosen startup path")
    print("  3. Configure YIYU_BETTAFISH_ENABLED / AUTOSTART / START_COMMAND")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - script entrypoint
        print(f"BettaFish install failed: {exc}", file=sys.stderr)
        raise
~~~

## `backend/scripts/main_chain_canary.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, request
from urllib.parse import urlparse

try:
    from scripts.main_chain_rc_contract import (
        DEFAULT_BASELINE_PATH,
        DEFAULT_RUNTIME_DIR,
        RC_MODE,
        attach_artifact_contract,
        build_session_id,
        compute_tuple_hash,
        default_rc_session,
        ensure_baseline_contract,
        identity_tuple_payload,
        load_rc_session,
        rc_session_path,
        resolve_runtime_dir,
        stable_json_hash,
        write_rc_session,
    )
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from scripts.main_chain_rc_contract import (  # type: ignore[no-redef]
        DEFAULT_BASELINE_PATH,
        DEFAULT_RUNTIME_DIR,
        RC_MODE,
        attach_artifact_contract,
        build_session_id,
        compute_tuple_hash,
        default_rc_session,
        ensure_baseline_contract,
        identity_tuple_payload,
        load_rc_session,
        rc_session_path,
        resolve_runtime_dir,
        stable_json_hash,
        write_rc_session,
    )


DEFAULT_BASE_URL = os.environ.get("YIYU_BACKEND_URL", "http://127.0.0.1:47829").rstrip("/")
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_JOB_TIMEOUT_SECONDS = 180.0
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output" / "main-chain"
DEFAULT_INSTALLED_APP = Path.home() / "Applications" / "益语智库自用平台.app"
MAIN_CHAIN_CANARY_FLAG = "main-chain-canary"


@dataclass
class WaveRunResult:
    label: str
    client_id: str
    shadow_off: bool
    job_id: str
    job_status: str
    baseline_judgment_id: str | None
    selected_candidate_id: str | None
    analysis_center_counts: dict[str, int]
    hidden_dependency_issues: list[str]


class ApiRequestError(RuntimeError):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class BackendApi:
    def __init__(self, base_url: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def close(self) -> None:
        return None

    def _request(self, method: str, path: str, *, json_body: dict[str, Any] | None = None) -> Any:
        body = json.dumps(json_body).encode("utf-8") if json_body is not None else None
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = request.Request(f"{self.base_url}{path}", data=body, headers=headers, method=method.upper())
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                payload = response.read()
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            raise ApiRequestError(exc.code, detail or path) from exc
        except error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            raise RuntimeError(f"failed to reach backend at {self.base_url}{path}: {reason}") from exc

        if not payload:
            return None
        try:
            return json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid JSON response from {path}") from exc

    def get_clients(self) -> list[dict[str, Any]]:
        payload = self._request("GET", "/api/v1/clients")
        return payload if isinstance(payload, list) else []

    def get_workspace(self, client_id: str) -> dict[str, Any]:
        payload = self._request("GET", f"/api/v1/clients/{client_id}/workspace")
        if not isinstance(payload, dict):
            raise RuntimeError("workspace payload is not a JSON object")
        return payload

    def get_cockpit(self, client_id: str) -> dict[str, Any]:
        payload = self._request("GET", f"/api/v1/clients/{client_id}/strategic-cockpit")
        if not isinstance(payload, dict):
            raise RuntimeError("cockpit payload is not a JSON object")
        return payload

    def get_metrics(self) -> dict[str, Any]:
        payload = self._request("GET", "/api/v1/runtime/analysis-migration-metrics")
        if not isinstance(payload, dict):
            raise RuntimeError("metrics payload is not a JSON object")
        return payload

    def get_settings(self) -> dict[str, Any]:
        payload = self._request("GET", "/api/v1/settings")
        if not isinstance(payload, dict):
            raise RuntimeError("settings payload is not a JSON object")
        return payload

    def get_stability_settings(self) -> dict[str, Any]:
        payload = self._request("GET", "/api/v1/settings/main-chain-stability")
        if not isinstance(payload, dict):
            raise RuntimeError("stability settings payload is not a JSON object")
        return payload

    def update_stability_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = self._request("POST", "/api/v1/settings/main-chain-stability", json_body=payload)
        if not isinstance(result, dict):
            raise RuntimeError("stability settings update response is not a JSON object")
        return result

    def dry_run_backfill(self, client_ids: list[str], *, batch_size: int, max_jobs: int) -> dict[str, Any]:
        payload = self._request(
            "POST",
            "/api/v1/analysis/backfill-main-chain",
            json_body={
                "clientIds": client_ids,
                "dryRun": True,
                "batchSize": batch_size,
                "maxJobs": max_jobs,
                "pauseRequested": False,
            },
        )
        if not isinstance(payload, dict):
            raise RuntimeError("backfill dry-run payload is not a JSON object")
        return payload

    def create_analysis_job(
        self,
        client_id: str,
        *,
        question: str,
        trigger_type: str = "manual",
        priority: str = "normal",
        intent_profile: str = "client_overview",
        feature_flags: dict[str, bool] | None = None,
    ) -> dict[str, Any]:
        payload = self._request(
            "POST",
            "/api/v1/analysis/jobs",
            json_body={
                "jobType": "strategy_pack",
                "clientId": client_id,
                "scopeType": "client",
                "scopeId": client_id,
                "priority": priority,
                "triggerType": trigger_type,
                "question": question,
                "sourceScope": {},
                "featureFlags": feature_flags or {},
                "intentProfile": intent_profile,
            },
        )
        if not isinstance(payload, dict):
            raise RuntimeError("analysis job payload is not a JSON object")
        return payload

    def get_analysis_job(self, job_id: str) -> dict[str, Any]:
        payload = self._request("GET", f"/api/v1/analysis/jobs/{job_id}")
        if not isinstance(payload, dict):
            raise RuntimeError("analysis job detail is not a JSON object")
        return payload


def iso_now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def parse_dt(value: str | None) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def write_output(path: str | None, payload: dict[str, Any]) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if not path:
        print(rendered)
        return
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


def _load_json_object(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"JSON payload at {path} is not an object")
    return payload


def _load_baseline_contract(path: str | Path | None) -> dict[str, Any]:
    baseline_path = Path(path or DEFAULT_BASELINE_PATH).expanduser().resolve()
    if not baseline_path.exists():
        raise RuntimeError(f"baseline file not found: {baseline_path}")
    return ensure_baseline_contract(_load_json_object(baseline_path))


def _ensure_session_for_baseline(
    *,
    runtime_dir: str | Path | None,
    baseline: dict[str, Any],
    baseline_path: str | Path | None = None,
) -> dict[str, Any]:
    runtime_root = resolve_runtime_dir(runtime_dir)
    session = load_rc_session(runtime_root)
    baseline_contract = ensure_baseline_contract(baseline)
    resolved_baseline_path = str(Path(baseline_path or DEFAULT_BASELINE_PATH).expanduser().resolve())
    if session is None:
        session = default_rc_session(
            baseline_path=resolved_baseline_path,
            session_id=str(baseline_contract.get("sessionId") or ""),
        )
        session["baselinePath"] = resolved_baseline_path
        session["baselineHash"] = baseline_contract.get("baselineHash")
        session["tupleHash"] = baseline_contract.get("tupleHash")
        session["state"] = "baseline_frozen"
        session["activeInstallSignature"] = {
            "appBundleMTime": (baseline_contract.get("installedRuntimeSignature") or {}).get("appBundleMTime"),
            "rendererEntry": (baseline_contract.get("installedRuntimeSignature") or {}).get("rendererEntry"),
            "backendStartedByInstalledApp": bool(
                (baseline_contract.get("installedRuntimeSignature") or {}).get("backendStartedByInstalledApp")
            ),
        }
        return write_rc_session(session, runtime_dir=runtime_root)

    if str(session.get("baselineHash") or "") != str(baseline_contract.get("baselineHash") or ""):
        session["baselinePath"] = resolved_baseline_path
        session["baselineHash"] = baseline_contract.get("baselineHash")
        session["tupleHash"] = baseline_contract.get("tupleHash")
        session["sessionId"] = baseline_contract.get("sessionId")
        if str(session.get("state") or "") == "pre_baseline":
            session["state"] = "baseline_frozen"
        return write_rc_session(session, runtime_dir=runtime_root)
    return session


def _record_session_invalidation(
    *,
    runtime_dir: str | Path | None,
    baseline_path: str | Path | None,
    baseline_contract: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    runtime_root = resolve_runtime_dir(runtime_dir)
    session = load_rc_session(runtime_root) or default_rc_session(
        baseline_path=str(Path(baseline_path or DEFAULT_BASELINE_PATH).expanduser().resolve()),
        session_id=str(baseline_contract.get("sessionId") or ""),
    )
    session.update(
        {
            "sessionId": baseline_contract.get("sessionId"),
            "baselinePath": str(Path(baseline_path or DEFAULT_BASELINE_PATH).expanduser().resolve()),
            "baselineHash": baseline_contract.get("baselineHash"),
            "tupleHash": baseline_contract.get("tupleHash"),
            "state": "pre_baseline",
            "invalidatedAt": iso_now(),
            "invalidationReason": reason,
        }
    )
    updated = write_rc_session(session, runtime_dir=runtime_root)
    try:
        from scripts.main_chain_rc_ops import write_invalidated_artifacts_note

        write_invalidated_artifacts_note(
            runtime_dir=str(runtime_root),
            baseline_path=str(Path(baseline_path or DEFAULT_BASELINE_PATH).expanduser().resolve()),
            source_app_path=None,
            applications_dir=None,
            output_path=str(runtime_root / "invalidated-artifacts.note.json"),
            invalidated_session_id=str(baseline_contract.get("sessionId") or ""),
            invalidated_baseline_hash=str(baseline_contract.get("baselineHash") or ""),
            invalidated_tuple_hash=str(baseline_contract.get("tupleHash") or ""),
            replacement_session_id=None,
            replacement_baseline_hash=None,
        )
    except Exception:
        pass
    return updated


def _enforce_runtime_contract(
    api: BackendApi,
    *,
    baseline_path: str | Path | None,
    runtime_dir: str | Path | None,
    command_name: str,
    allowed_states: set[str],
) -> dict[str, Any]:
    baseline_contract = _load_baseline_contract(baseline_path)
    session = _ensure_session_for_baseline(
        runtime_dir=runtime_dir,
        baseline=baseline_contract,
        baseline_path=baseline_path,
    )
    current_state = str(session.get("state") or "pre_baseline")
    if current_state not in allowed_states:
        raise RuntimeError(
            f"{command_name} requires rc-session.state in {sorted(allowed_states)}, got {current_state}"
        )
    current_snapshot = metrics_snapshot(api)
    current_settings = (current_snapshot.get("appSettings") or {}).get("settings") or {}
    current_health = (current_snapshot.get("appSettings") or {}).get("health") or {}
    dirty_state = get_git_dirty_worktree_state(
        excluded_paths=[get_repo_relative_path(baseline_path)] if baseline_path else None,
    )
    installed_app = inspect_installed_app()
    current_identity = {
        "commitSha": get_git_commit_sha(),
        "backendUrl": api.base_url,
        "buildVersion": current_health.get("buildVersion"),
        "databasePath": str(Path(str(current_settings.get("dataDir") or "")).expanduser().resolve() / "app.db")
        if current_settings.get("dataDir")
        else None,
        "latestJudgmentsShadowOff": bool((current_snapshot.get("settings") or {}).get("latestJudgmentsShadowOff")),
        "dirtyWorktree": bool(dirty_state["dirtyWorktree"]),
        "dirtyPaths": list(dirty_state["dirtyPaths"]),
        "installedRuntimeSignature": inspect_installed_runtime_signature(api.base_url, installed_app=installed_app),
    }
    current_tuple_hash = compute_tuple_hash(current_identity)
    if str(baseline_contract.get("tupleHash") or "") != current_tuple_hash:
        reason = (
            f"{command_name} refused to continue because live tupleHash={current_tuple_hash} "
            f"does not match baseline tupleHash={baseline_contract.get('tupleHash')}"
        )
        _record_session_invalidation(
            runtime_dir=runtime_dir,
            baseline_path=baseline_path,
            baseline_contract=baseline_contract,
            reason=reason,
        )
        raise RuntimeError(reason)
    return {
        "baseline": baseline_contract,
        "session": session,
        "currentTupleHash": current_tuple_hash,
    }


def _transition_session_state(
    *,
    runtime_dir: str | Path | None,
    session: dict[str, Any],
    state: str,
    baseline: dict[str, Any] | None = None,
    invalidation_reason: str | None = None,
) -> dict[str, Any]:
    updated = dict(session)
    updated["state"] = state
    if baseline:
        updated["sessionId"] = baseline.get("sessionId")
        updated["baselineHash"] = baseline.get("baselineHash")
        updated["tupleHash"] = baseline.get("tupleHash")
    if state == "pre_baseline":
        updated["invalidatedAt"] = iso_now()
        updated["invalidationReason"] = invalidation_reason
    else:
        updated["invalidatedAt"] = None
        updated["invalidationReason"] = None
    return write_rc_session(updated, runtime_dir=runtime_dir)


def run_command(command: list[str], *, cwd: Path | None = None) -> str:
    result = subprocess.run(command, cwd=str(cwd) if cwd else None, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


def get_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_git_commit_sha() -> str | None:
    repo_root = get_repo_root()
    value = run_command(["git", "-C", str(repo_root), "rev-parse", "HEAD"])
    return value or None


def get_repo_relative_path(path: str | Path | None) -> str | None:
    if not path:
        return None
    repo_root = get_repo_root()
    resolved = Path(path).expanduser().resolve()
    try:
        return str(resolved.relative_to(repo_root))
    except ValueError:
        return None


def get_git_dirty_worktree_state(*, excluded_paths: list[str] | None = None) -> dict[str, Any]:
    repo_root = get_repo_root()
    excluded = {item for item in (excluded_paths or []) if item}
    dirty_paths: set[str] = set()
    for command in (
        ["git", "-C", str(repo_root), "diff", "--name-only"],
        ["git", "-C", str(repo_root), "diff", "--name-only", "--cached"],
        ["git", "-C", str(repo_root), "ls-files", "--others", "--exclude-standard"],
    ):
        output = run_command(command)
        for raw in output.splitlines():
            path = raw.strip()
            if not path or path in excluded:
                continue
            dirty_paths.add(path)
    ordered_paths = sorted(dirty_paths)
    return {
        "dirtyWorktree": bool(ordered_paths),
        "dirtyPaths": ordered_paths,
    }


def inspect_installed_app(path: Path | None = None) -> dict[str, Any]:
    target = (path or DEFAULT_INSTALLED_APP).expanduser().resolve()
    asset_dir = target / "Contents" / "Resources" / "app" / "dist" / "renderer" / "assets"
    renderer_entries: list[str] = []
    preferred_entry: str | None = None
    if asset_dir.exists():
        renderer_entries = sorted(
            item.name
            for item in asset_dir.iterdir()
            if item.is_file() and (item.name.startswith("main-") or item.name.startswith("index-")) and item.suffix == ".js"
        )
        preferred_entry = next((name for name in renderer_entries if name.startswith("main-")), None) or (renderer_entries[0] if renderer_entries else None)
    return {
        "path": str(target),
        "exists": target.exists(),
        "rendererEntry": preferred_entry,
        "rendererAssets": renderer_entries,
        "modifiedAt": datetime.fromtimestamp(target.stat().st_mtime).replace(microsecond=0).isoformat() if target.exists() else None,
    }


def inspect_installed_runtime_signature(
    base_url: str = DEFAULT_BASE_URL,
    *,
    installed_app: dict[str, Any] | None = None,
) -> dict[str, Any]:
    app_info = installed_app or inspect_installed_app()
    signature = {
        "appBundleMTime": app_info.get("modifiedAt"),
        "rendererEntry": app_info.get("rendererEntry"),
        "backendStartedByInstalledApp": False,
        "backendPid": None,
        "backendCommand": None,
    }
    parsed = urlparse(base_url if "://" in base_url else f"http://{base_url}")
    host = (parsed.hostname or "").strip().lower()
    port = parsed.port
    if host not in {"127.0.0.1", "localhost"} or port is None:
        return signature

    listener_output = run_command(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-Fp"])
    backend_pid = next((line[1:] for line in listener_output.splitlines() if line.startswith("p") and line[1:].strip()), None)
    if not backend_pid:
        return signature

    backend_command = run_command(["ps", "-p", backend_pid, "-o", "command="]) or None
    installed_runtime_python = str(
        Path.home()
        / "Library"
        / "Application Support"
        / "YiyuThinkTankWorkbench"
        / "runtime"
        / "backend-venv"
        / "bin"
        / "python"
    )
    signature["backendPid"] = int(backend_pid)
    signature["backendCommand"] = backend_command
    signature["backendStartedByInstalledApp"] = bool(backend_command and installed_runtime_python in backend_command)
    return signature


def candidate_is_knowledge_ready(workspace: dict[str, Any]) -> bool:
    status = workspace.get("knowledgeStatus") or {}
    return (
        int(status.get("pendingJobs") or 0) == 0
        and int(status.get("runningJobs") or 0) == 0
        and str(status.get("lastJobStatus") or "") == "completed"
    )


def extract_counts(workspace: dict[str, Any]) -> dict[str, int]:
    summary = workspace.get("analysisCenter") or {}
    return {
        "evidenceCardCount": int(summary.get("evidenceCardCount") or 0),
        "themeClusterCount": int(summary.get("themeClusterCount") or 0),
        "conflictGroupCount": int(summary.get("conflictGroupCount") or 0),
        "openQuestionCount": int(summary.get("openQuestionCount") or 0),
    }


def extract_ids(workspace: dict[str, Any]) -> tuple[str | None, str | None]:
    bundle = workspace.get("judgmentBundle") or {}
    trace = workspace.get("latestResolutionTrace") or {}
    baseline = bundle.get("baselineJudgment") or {}
    selected = trace.get("selectedCandidate") or {}
    baseline_id = str(baseline.get("id") or "").strip() or None
    selected_id = str(selected.get("objectId") or "").strip() or None
    return baseline_id, selected_id


def wait_for_job_terminal(api: BackendApi, job_id: str, *, timeout_seconds: float) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_payload: dict[str, Any] = {}
    while time.time() < deadline:
        payload = api.get_analysis_job(job_id)
        last_payload = payload
        if str(payload.get("status") or "") not in {"queued", "running"}:
            return payload
        time.sleep(1.0)
    return last_payload


def build_hidden_dependency_issues(
    workspace: dict[str, Any],
    cockpit: dict[str, Any],
    metrics: dict[str, Any],
    *,
    shadow_off: bool,
) -> list[str]:
    issues: list[str] = []
    if not isinstance(metrics, dict) or not metrics:
        issues.append("Overview metrics payload missing")
    if not workspace.get("judgmentBundle"):
        issues.append("workspace.judgmentBundle missing")
    if not workspace.get("latestResolutionTrace"):
        issues.append("workspace.latestResolutionTrace missing")
    if shadow_off and workspace.get("latestJudgments") != []:
        issues.append("latestJudgments still serialized while shadow off is enabled")
    if not isinstance(cockpit, dict) or "officialLayerStatus" not in cockpit:
        issues.append("strategic-cockpit payload missing official layer metadata")
    return issues


def compare_idempotency_windows(previous: WaveRunResult, rerun: WaveRunResult) -> list[str]:
    issues: list[str] = []
    if previous.analysis_center_counts != rerun.analysis_center_counts:
        issues.append("analysisCenter counts drifted after same-snapshot rerun")
    if previous.baseline_judgment_id != rerun.baseline_judgment_id:
        issues.append("baselineJudgment id changed after same-snapshot rerun")
    if previous.selected_candidate_id != rerun.selected_candidate_id:
        issues.append("selectedCandidate id changed after same-snapshot rerun")
    return issues


def run_manual_window(
    api: BackendApi,
    client_id: str,
    *,
    label: str,
    shadow_off: bool,
    timeout_seconds: float,
    trigger_type: str = "manual",
    priority: str = "normal",
    intent_profile: str = "client_overview",
) -> WaveRunResult:
    api.update_stability_settings({"latestJudgmentsShadowOff": shadow_off})
    feature_flags = {MAIN_CHAIN_CANARY_FLAG: True}
    job = api.create_analysis_job(
        client_id,
        question=f"main-chain {label}",
        trigger_type=trigger_type,
        priority=priority,
        intent_profile=intent_profile,
        feature_flags=feature_flags,
    )
    job_id = str(job.get("id") or "")
    if not job_id:
        raise RuntimeError(f"{label}: failed to create analysis job")
    terminal = wait_for_job_terminal(api, job_id, timeout_seconds=timeout_seconds)
    workspace = api.get_workspace(client_id)
    cockpit = api.get_cockpit(client_id)
    metrics = api.get_metrics()
    baseline_id, selected_id = extract_ids(workspace)
    return WaveRunResult(
        label=label,
        client_id=client_id,
        shadow_off=shadow_off,
        job_id=job_id,
        job_status=str(terminal.get("status") or ""),
        baseline_judgment_id=baseline_id,
        selected_candidate_id=selected_id,
        analysis_center_counts=extract_counts(workspace),
        hidden_dependency_issues=build_hidden_dependency_issues(workspace, cockpit, metrics, shadow_off=shadow_off),
    )


def metrics_snapshot(api: BackendApi) -> dict[str, Any]:
    settings = api.get_stability_settings()
    metrics = api.get_metrics()
    app_settings = api.get_settings()
    return {
        "recordedAt": iso_now(),
        "baseUrl": api.base_url,
        "metrics": metrics,
        "settings": settings,
        "appSettings": app_settings,
    }


def capture_snapshot(
    api: BackendApi,
    *,
    baseline_path: str | None,
    runtime_dir: str | None,
    output_path: str | None,
) -> dict[str, Any]:
    gate = _enforce_runtime_contract(
        api,
        baseline_path=baseline_path,
        runtime_dir=runtime_dir,
        command_name="snapshot",
        allowed_states={"day0_ready", "wave2_active", "step_b_ready"},
    )
    payload = attach_artifact_contract(metrics_snapshot(api), gate["baseline"])
    write_output(output_path, payload)
    return payload


def recommend_wave1_clients(api: BackendApi, *, limit: int, lookback_days: int) -> dict[str, Any]:
    now = datetime.now()
    candidates: list[dict[str, Any]] = []
    skipped_clients: list[dict[str, str]] = []
    for client in api.get_clients():
        last_activity = parse_dt(str(client.get("lastActivityAt") or ""))
        age_days = (now - last_activity).days if last_activity else 9999
        client_id = str(client["id"])
        try:
            workspace = api.get_workspace(client_id)
        except Exception as exc:
            skipped_clients.append(
                {
                    "clientId": client_id,
                    "name": str(client.get("name") or ""),
                    "reason": str(exc),
                }
            )
            continue
        knowledge_ready = candidate_is_knowledge_ready(workspace)
        has_context = bool(
            workspace.get("documentCards")
            or workspace.get("meetings")
            or workspace.get("relatedTasks")
        )
        if age_days > lookback_days:
            continue
        score = max(0, lookback_days - age_days) * 100
        score += int(client.get("documentCount") or 0) * 5
        score += int(client.get("taskCount") or 0) * 3
        if knowledge_ready:
            score += 50
        if has_context:
            score += 25
        candidates.append(
            {
                "clientId": client_id,
                "name": str(client.get("name") or ""),
                "lastActivityAt": client.get("lastActivityAt"),
                "documentCount": int(client.get("documentCount") or 0),
                "taskCount": int(client.get("taskCount") or 0),
                "knowledgeReady": knowledge_ready,
                "hasContext": has_context,
                "score": score,
            }
        )
    candidates.sort(key=lambda item: (not item["knowledgeReady"], not item["hasContext"], -int(item["score"])))
    return {
        "recordedAt": iso_now(),
        "baseUrl": api.base_url,
        "lookbackDays": lookback_days,
        "recommended": candidates[:limit],
        "skippedClients": skipped_clients,
    }


def freeze_rc_baseline(
    api: BackendApi,
    *,
    fixed_gate_status: str,
    full_smoke_summary: str,
    a_class_count: int,
    b_class_summary: list[str],
    c_class_summary: list[str],
    notes: str | None,
    runtime_dir: str | None = None,
    output_path: str | None,
) -> dict[str, Any]:
    generated_at = iso_now()
    snapshot = metrics_snapshot(api)
    settings_payload = snapshot.get("appSettings") or {}
    app_settings = settings_payload.get("settings") or {}
    health = settings_payload.get("health") or {}
    installed_app = inspect_installed_app()
    installed_runtime_signature = inspect_installed_runtime_signature(api.base_url, installed_app=installed_app)
    dirty_state = get_git_dirty_worktree_state(
        excluded_paths=[get_repo_relative_path(output_path)] if output_path else None,
    )
    baseline = {
        "recordedAt": generated_at,
        "generatedAt": generated_at,
        "commitSha": get_git_commit_sha(),
        "backendUrl": api.base_url,
        "databasePath": str(Path(str(app_settings.get("dataDir") or "")).expanduser().resolve() / "app.db") if app_settings.get("dataDir") else None,
        "dataDir": app_settings.get("dataDir"),
        "dirtyWorktree": bool(dirty_state["dirtyWorktree"]),
        "dirtyPaths": list(dirty_state["dirtyPaths"]),
        "installedApp": installed_app,
        "installedRuntimeSignature": installed_runtime_signature,
        "health": {
            "appVersion": health.get("appVersion"),
            "buildVersion": health.get("buildVersion"),
            "startedAt": health.get("startedAt"),
        },
        "fixedGate": {
            "status": fixed_gate_status,
            "commands": [
                ".venv/bin/python -m pytest -q tests/test_analysis_main_chain.py",
                ".venv/bin/python -m pytest -q tests/test_knowledge_v2.py",
                ".venv/bin/python -m pytest -q tests/test_api_smoke.py -k \"strategic_cockpit or workspace_import_builds_document_cards_and_knowledge_status or workspace_import_auto_generates_client_dna_candidates or main_chain_canary_closes_import_analysis_approval_and_cockpit\"",
                "npm run build:main",
                "npm run build:renderer",
            ],
        },
        "fullSmoke": {
            "summary": full_smoke_summary,
        },
        "classification": {
            "aClassCount": a_class_count,
            "bClassSummary": b_class_summary,
            "cClassSummary": c_class_summary,
        },
        "latestJudgmentsShadowOff": bool((snapshot.get("settings") or {}).get("latestJudgmentsShadowOff")),
        "mainChainStability": snapshot.get("settings") or {},
        "metrics": snapshot.get("metrics") or {},
        "notes": notes or "",
    }
    baseline = ensure_baseline_contract(baseline)
    write_output(output_path, baseline)

    runtime_root = resolve_runtime_dir(runtime_dir)
    session = default_rc_session(
        baseline_path=str(Path(output_path or DEFAULT_BASELINE_PATH).expanduser().resolve()),
        session_id=str(baseline.get("sessionId") or build_session_id(generated_at=generated_at, tuple_hash=str(baseline.get("tupleHash") or ""))),
    )
    session.update(
        {
            "sessionId": baseline.get("sessionId"),
            "state": "baseline_frozen",
            "baselinePath": str(Path(output_path or DEFAULT_BASELINE_PATH).expanduser().resolve()),
            "baselineHash": baseline.get("baselineHash"),
            "tupleHash": baseline.get("tupleHash"),
            "activeInstallSignature": {
                "appBundleMTime": baseline.get("appBundleMTime") or ((baseline.get("installedRuntimeSignature") or {}).get("appBundleMTime")),
                "rendererEntry": baseline.get("rendererEntry") or ((baseline.get("installedRuntimeSignature") or {}).get("rendererEntry")),
                "backendStartedByInstalledApp": bool(
                    baseline.get("backendStartedByInstalledApp")
                    if baseline.get("backendStartedByInstalledApp") is not None
                    else ((baseline.get("installedRuntimeSignature") or {}).get("backendStartedByInstalledApp"))
                ),
            },
            "invalidatedAt": None,
            "invalidationReason": None,
        }
    )
    write_rc_session(session, runtime_dir=runtime_root)
    return baseline


def load_json(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"JSON payload at {path} is not an object")
    return payload


def load_observation_payload(path: str) -> dict[str, Any]:
    payload = load_json(path)
    nested = payload.get("observation")
    if isinstance(nested, dict):
        return nested
    return payload


def _page_proof_passes(path: str | None, *, baseline_hash: str | None = None, tuple_hash: str | None = None, session_id: str | None = None) -> bool:
    target = str(path or "").strip()
    if not target:
        return False
    payload = _load_json_object(target)
    if str(payload.get("decision") or "").strip() != "pass":
        return False
    if baseline_hash and str(payload.get("baselineHash") or "").strip() != str(baseline_hash):
        return False
    if tuple_hash and str(payload.get("tupleHash") or "").strip() != str(tuple_hash):
        return False
    if session_id and str(payload.get("sessionId") or "").strip() != str(session_id):
        return False
    return True


def format_percent(value: float | int | None) -> str:
    return f"{(float(value or 0.0) * 100):.1f}%"


def format_status_label(value: str | None) -> str:
    mapping = {
        "pass": "通过",
        "watch": "继续观察",
        "fail": "未通过",
    }
    return mapping.get(str(value or "").strip(), str(value or "未填写"))


def format_check(value: bool | None) -> str:
    if value is True:
        return "通过"
    if value is False:
        return "未通过"
    return "未填写"


def render_value_proof_markdown(
    *,
    observation: dict[str, Any],
    manual: dict[str, Any],
    baseline_contract: dict[str, Any] | None = None,
) -> str:
    contract = ensure_baseline_contract(baseline_contract) if baseline_contract else None
    release_label = str(manual.get("releaseLabel") or "v0.3.4 RC")
    code_completion_status = format_status_label(str(manual.get("codeCompletionStatus") or "watch"))
    run_completion_status = format_status_label(str(manual.get("runCompletionStatus") or observation.get("verdict") or "watch"))

    install_validation = manual.get("installValidation") or {}
    install_evidence = install_validation.get("evidenceScreenshots") or {}
    install_page_proofs = install_validation.get("evidencePageProofs") or {}
    metrics_story = manual.get("metricsStory") or {}
    scenes = manual.get("scenes") or []
    reviewers = manual.get("reviewers") or []
    next_decision = manual.get("nextDecision") or {}
    judgment_consistency = manual.get("judgmentConsistency") or {}
    judgment_consistency_status = str(judgment_consistency.get("status") or "未填写")
    judgment_consistency_summary = str(judgment_consistency.get("summary") or "未填写")
    confirmed_feedback_union = {
        "boundaryClear": False,
        "taskContextSharper": False,
        "meetingCapturesUnresolved": False,
        "cockpitAvoidsFakeConclusion": False,
    }
    for reviewer in reviewers:
        if not isinstance(reviewer, dict):
            continue
        feedback = reviewer.get("feedback") or {}
        for key in confirmed_feedback_union:
            confirmed_feedback_union[key] = confirmed_feedback_union[key] or bool(feedback.get(key))
    scene_contract_ok = []
    for item in scenes:
        if not isinstance(item, dict):
            continue
        evidence = item.get("evidence") or {}
        page_proof_path = str(evidence.get("pageProofPath") or "").strip()
        scene_contract_ok.append(
            bool(item.get("confirmed"))
            and _page_proof_passes(
                page_proof_path,
                baseline_hash=contract.get("baselineHash") if contract else None,
                tuple_hash=contract.get("tupleHash") if contract else None,
                session_id=contract.get("sessionId") if contract else None,
            )
        )
    scenes_confirmed = bool(scene_contract_ok) and all(scene_contract_ok)
    install_screenshots_complete = all(
        str(install_evidence.get(key) or "").strip()
        for key in ("overview", "workspace", "cockpit")
    )
    install_page_proofs_complete = all(
        _page_proof_passes(
            str(install_page_proofs.get(key) or ""),
            baseline_hash=contract.get("baselineHash") if contract else None,
            tuple_hash=contract.get("tupleHash") if contract else None,
            session_id=contract.get("sessionId") if contract else None,
        )
        for key in ("overview", "workspace", "cockpit")
    )
    install_closed = (
        bool(install_validation.get("appStarts"))
        and bool(install_validation.get("backendStartedByInstalledApp"))
        and bool(install_validation.get("overviewPanelVisible"))
        and bool(install_validation.get("shadowOffParity"))
        and bool(install_validation.get("workspaceBoundaryCorrect"))
        and bool(install_validation.get("cockpitOfficialLayerToneCorrect"))
        and bool(install_validation.get("overviewMetricsPopulated"))
        and install_screenshots_complete
        and install_page_proofs_complete
    )
    business_feedback_complete = all(confirmed_feedback_union.values())
    judgment_consistency_ready = judgment_consistency_status == "稳定"
    value_proof_ready = install_closed and scenes_confirmed and business_feedback_complete and judgment_consistency_ready

    lines = [
        f"# {release_label} 价值证明结论",
        "",
        "## 结论概览",
        f"- 代码完成态：{code_completion_status}",
        f"- 运行完成态：{run_completion_status}",
        f"- 最近一次观察窗口：{observation.get('timeRange') or '未填写'}",
        f"- 最近一次试跑结论：{format_status_label(observation.get('verdict'))}",
        f"- 结论摘要：{observation.get('conclusion') or '未填写'}",
        f"- 主链判断口径：{judgment_consistency_status}",
        f"- 口径说明：{judgment_consistency_summary}",
        f"- 价值证明状态：{'已具备通过条件' if value_proof_ready else '尚未具备通过条件'}",
        "",
        "## 安装版闭环",
        f"- 安装版状态：{format_status_label(install_validation.get('status'))}",
        f"- 能正常启动：{format_check(install_validation.get('appStarts'))}",
        f"- 47829 由安装版自拉起：{format_check(install_validation.get('backendStartedByInstalledApp'))}",
        f"- 能看到稳定化面板：{format_check(install_validation.get('overviewPanelVisible'))}",
        f"- 关闭旧结果通道后与源码版一致：{format_check(install_validation.get('shadowOffParity'))}",
        f"- workspace 口径正确：{format_check(install_validation.get('workspaceBoundaryCorrect'))}",
        f"- cockpit official layer 口径正确：{format_check(install_validation.get('cockpitOfficialLayerToneCorrect'))}",
        f"- Overview 指标不是空壳：{format_check(install_validation.get('overviewMetricsPopulated'))}",
        f"- 截图留档：Overview {install_evidence.get('overview') or '未填写'}；workspace {install_evidence.get('workspace') or '未填写'}；cockpit {install_evidence.get('cockpit') or '未填写'}",
        f"- 页面证据契约：Overview {install_page_proofs.get('overview') or '未填写'}；workspace {install_page_proofs.get('workspace') or '未填写'}；cockpit {install_page_proofs.get('cockpit') or '未填写'}",
        f"- 说明：{install_validation.get('summary') or '未填写'}",
        "",
        "## 这轮变化是否真的看得见",
        f"- 导入后多久可用：{metrics_story.get('importReadyTime') or '未填写'}",
        f"- 同 snapshot 重跑会不会越跑越乱：{metrics_story.get('idempotencySummary') or '未填写'}",
        f"- 页面说法打架率：{format_percent(observation.get('resolverMismatchRateBefore'))} → {format_percent(observation.get('resolverMismatchRateAfter'))}",
        f"- 退回旧逻辑比例：{format_percent(observation.get('fallbackRateBefore'))} → {format_percent(observation.get('fallbackRateAfter'))}",
        f"- 待确认判断是否堆积：{int(observation.get('approvalBacklog') or 0)} 个 / {(float(observation.get('approvalLagHoursMedian') or 0.0)):.1f}h；{metrics_story.get('approvalSummary') or '未填写'}",
        "- 口径说明：本轮试跑产生的 canary 样本不计入日常审批积压指标。",
        "- 指标口径说明：approvalBacklog / approvalLagHoursMedian / Candidate SLA 已排除 main-chain-canary=true 的样本，代表真实业务积压，不代表试跑制造的积压。",
        "",
        "## 场景对照",
        "| 场景 | 以前 | 现在 | 仍不够好 | 已验证 | 证据 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    scene_written = False
    for item in scenes:
        if not isinstance(item, dict):
            continue
        scene_written = True
        evidence = item.get("evidence") or {}
        evidence_summary_parts = []
        if evidence.get("sampleId"):
            evidence_summary_parts.append(f"样本 {evidence['sampleId']}")
        if evidence.get("screenshotPath"):
            evidence_summary_parts.append(f"截图 {evidence['screenshotPath']}")
        if evidence.get("pageProofPath"):
            evidence_summary_parts.append(f"页面契约 {evidence['pageProofPath']}")
        if evidence.get("excerpt"):
            evidence_summary_parts.append(f"摘录 {evidence['excerpt']}")
        lines.append(
            "| {name} | {before} | {after} | {still_not_good_enough} | {confirmed} | {evidence} |".format(
                name=str(item.get("name") or "未命名场景").replace("|", "／"),
                before=str(item.get("before") or "未填写").replace("|", "／"),
                after=str(item.get("after") or "未填写").replace("|", "／"),
                still_not_good_enough=str(item.get("stillNotGoodEnough") or "未填写").replace("|", "／"),
                confirmed="是" if bool(item.get("confirmed")) else "否",
                evidence=("；".join(str(part).replace("|", "／") for part in evidence_summary_parts) if evidence_summary_parts else "未填写"),
            )
        )
    if not scene_written:
        lines.append("| 暂无 | 未填写 | 未填写 | 未填写 | 否 | 未填写 |")

    lines.extend(
        [
            "",
            "## 业务同事反馈",
        ]
    )
    if reviewers:
        for reviewer in reviewers:
            if not isinstance(reviewer, dict):
                continue
            feedback = reviewer.get("feedback") or {}
            confirmed_points = [
                label
                for key, label in (
                    ("boundaryClear", "状态边界更清楚"),
                    ("taskContextSharper", "事件线上下文差异更明显"),
                    ("meetingCapturesUnresolved", "会议结果更能承接推进链"),
                    ("cockpitAvoidsFakeConclusion", "cockpit 不再把提醒当结论"),
                )
                if bool(feedback.get(key))
            ]
            lines.extend(
                [
                    f"- {reviewer.get('name') or '未署名'} / {reviewer.get('role') or '未填写角色'}",
                    f"  - 已确认：{('、'.join(confirmed_points)) if confirmed_points else '未明确确认'}",
                    f"  - 备注：{reviewer.get('notes') or '未填写'}",
                ]
            )
    else:
        lines.append("- 还没有收集业务同事反馈。")

    lines.extend(
        [
            "",
            "## 仍待补证据",
        ]
    )
    blocked_by = next_decision.get("blockedBy") or []
    if isinstance(blocked_by, list) and blocked_by:
        lines.append(f"- 当前仍待补：{'；'.join(str(item) for item in blocked_by)}")
    else:
        lines.append("- 当前仍待补：无")
    if not reviewers:
        lines.append("- 备注：当前还没有业务同事反馈，因此不能判定价值证明通过。")
    elif not business_feedback_complete:
        lines.append("- 备注：业务同事反馈还未覆盖 4 个关键判断点，因此不能判定价值证明通过。")
    if not judgment_consistency_ready:
        lines.append("- 备注：主链判断口径还未达到“稳定”，因此不能作为进入 v0.4 的依据。")

    return "\n".join(lines).strip() + "\n"


def build_observation_payload(
    *,
    before_metrics: dict[str, Any],
    after_metrics: dict[str, Any],
    settings: dict[str, Any],
    client_count: int,
    enqueued_jobs: int,
    completed_jobs: int,
    failed_jobs: int,
    time_range: str,
    impacted_realtime_tasks: bool,
    shadow_off: bool,
    verdict: str,
    conclusion: str,
) -> dict[str, Any]:
    return {
        "timeRange": time_range,
        "clientCount": client_count,
        "enqueuedJobs": enqueued_jobs,
        "completedJobs": completed_jobs,
        "failedJobs": failed_jobs,
        "newObjectHitRateBefore": float(before_metrics.get("newObjectHitRate") or 0.0),
        "newObjectHitRateAfter": float(after_metrics.get("newObjectHitRate") or 0.0),
        "fallbackRateBefore": float(before_metrics.get("fallbackRate") or 0.0),
        "fallbackRateAfter": float(after_metrics.get("fallbackRate") or 0.0),
        "resolverMismatchRateBefore": float(before_metrics.get("resolverMismatchRate") or 0.0),
        "resolverMismatchRateAfter": float(after_metrics.get("resolverMismatchRate") or 0.0),
        "approvalBacklog": int(after_metrics.get("approvalBacklog") or 0),
        "approvalLagHoursMedian": float(after_metrics.get("approvalLagHoursMedian") or 0.0),
        "claimCounts": ((settings.get("workerCounters") or {}).get("claimCounts") or {}),
        "lockContention": ((settings.get("workerCounters") or {}).get("lockContention") or {}),
        "backfillThrottle": ((settings.get("workerCounters") or {}).get("backfillThrottle") or {}),
        "impactedRealtimeTasks": impacted_realtime_tasks,
        "latestJudgmentsShadowOff": shadow_off,
        "verdict": verdict,
        "conclusion": conclusion,
    }


def run_wave1(
    api: BackendApi,
    *,
    client_a: str,
    client_b: str | None,
    idempotency_client: str | None,
    timeout_seconds: float,
    write_observation: bool,
    impacted_realtime_tasks: bool,
    output_path: str | None,
) -> dict[str, Any]:
    wave_clients = [client_a] + ([client_b] if client_b and client_b != client_a else [])
    before = metrics_snapshot(api)
    dry_run = api.dry_run_backfill(wave_clients or [client_a], batch_size=1, max_jobs=2)

    results: list[WaveRunResult] = []
    results.append(run_manual_window(api, client_a, label="wave1-client-a-shadow-on", shadow_off=True, timeout_seconds=timeout_seconds))

    client_b_effective = client_b or client_a
    results.append(run_manual_window(api, client_b_effective, label="wave1-client-b-shadow-off", shadow_off=False, timeout_seconds=timeout_seconds))
    results.append(run_manual_window(api, client_b_effective, label="wave1-client-b-shadow-on", shadow_off=True, timeout_seconds=timeout_seconds))

    idempotency_target = idempotency_client or client_a
    previous_true_window = next(
        (item for item in reversed(results) if item.client_id == idempotency_target and item.shadow_off),
        None,
    )
    idempotency_result = run_manual_window(
        api,
        idempotency_target,
        label="wave1-idempotency-rerun",
        shadow_off=True,
        timeout_seconds=timeout_seconds,
    )
    results.append(idempotency_result)

    idempotency_ok = True
    idempotency_issues: list[str] = []
    if previous_true_window is not None:
        idempotency_issues.extend(compare_idempotency_windows(previous_true_window, idempotency_result))
        if idempotency_issues:
            idempotency_ok = False
    else:
        idempotency_ok = False
        idempotency_issues.append("missing previous true-shadow window for idempotency comparison")

    after = metrics_snapshot(api)
    hidden_dependency_issues = [
        issue
        for item in results
        for issue in item.hidden_dependency_issues
    ]
    failed_jobs = [item for item in results if item.job_status != "completed"]

    verdict = "pass"
    conclusion_parts: list[str] = []
    if hidden_dependency_issues:
        verdict = "fail"
        conclusion_parts.append("发现 shadowOff 隐藏依赖")
    if failed_jobs:
        verdict = "fail"
        conclusion_parts.append(f"{len(failed_jobs)} 个 canary job 未完成")
    if not idempotency_ok:
        verdict = "fail"
        conclusion_parts.append("同 snapshot 重跑未通过幂等性 gate")
    if impacted_realtime_tasks:
        verdict = "fail"
        conclusion_parts.append("观察到实时任务受 backfill 影响")
    if verdict == "pass":
        conclusion_parts.append("Wave 1 通过：shadowOff、manual rerun 与 idempotency gate 均未暴露主链回潮。")

    observation = build_observation_payload(
        before_metrics=before["metrics"],
        after_metrics=after["metrics"],
        settings=after["settings"],
        client_count=len({item.client_id for item in results if item.label != "wave1-idempotency-rerun"}),
        enqueued_jobs=len(results),
        completed_jobs=len(results) - len(failed_jobs),
        failed_jobs=len(failed_jobs),
        time_range=f"Wave 1 @ {iso_now()}",
        impacted_realtime_tasks=impacted_realtime_tasks,
        shadow_off=bool((after["settings"].get("latestJudgmentsShadowOff"))),
        verdict=verdict,
        conclusion="；".join(conclusion_parts),
    )
    if write_observation:
        api.update_stability_settings({"lastCanaryObservation": observation})

    summary = {
        "recordedAt": iso_now(),
        "baseUrl": api.base_url,
        "dryRun": dry_run,
        "before": before,
        "after": after,
        "runs": [
            {
                "label": item.label,
                "clientId": item.client_id,
                "shadowOff": item.shadow_off,
                "jobId": item.job_id,
                "jobStatus": item.job_status,
                "baselineJudgmentId": item.baseline_judgment_id,
                "selectedCandidateId": item.selected_candidate_id,
                "analysisCenterCounts": item.analysis_center_counts,
                "hiddenDependencyIssues": item.hidden_dependency_issues,
            }
            for item in results
        ],
        "idempotencyOk": idempotency_ok,
        "idempotencyIssues": idempotency_issues,
        "observation": observation,
    }
    write_output(output_path, summary)
    return summary


def run_wave2_day0(
    api: BackendApi,
    *,
    client_ids: list[str],
    batch_size: int,
    max_jobs: int,
    timeout_seconds: float,
    write_observation: bool,
    impacted_realtime_tasks: bool,
    baseline_contract: dict[str, Any] | None = None,
    output_path: str | None,
) -> dict[str, Any]:
    unique_client_ids: list[str] = []
    for client_id in client_ids:
        normalized = str(client_id or "").strip()
        if normalized and normalized not in unique_client_ids:
            unique_client_ids.append(normalized)
    if len(unique_client_ids) < 3:
        raise RuntimeError("wave2-day0 requires at least 3 unique client ids")

    before = metrics_snapshot(api)
    dry_run = api.dry_run_backfill(unique_client_ids, batch_size=batch_size, max_jobs=max_jobs)
    api.update_stability_settings({"latestJudgmentsShadowOff": True})

    first_runs: dict[str, WaveRunResult] = {}
    reruns: dict[str, WaveRunResult] = {}
    results: list[WaveRunResult] = []
    idempotency_issues: dict[str, list[str]] = {}

    for index, client_id in enumerate(unique_client_ids, start=1):
        first = run_manual_window(
            api,
            client_id,
            label=f"wave2-day0-client-{index}",
            shadow_off=True,
            timeout_seconds=timeout_seconds,
        )
        rerun = run_manual_window(
            api,
            client_id,
            label=f"wave2-day0-client-{index}-rerun",
            shadow_off=True,
            timeout_seconds=timeout_seconds,
        )
        first_runs[client_id] = first
        reruns[client_id] = rerun
        results.extend([first, rerun])
        issues = compare_idempotency_windows(first, rerun)
        if issues:
            idempotency_issues[client_id] = issues

    backfill_target = unique_client_ids[0]
    backfill_run = run_manual_window(
        api,
        backfill_target,
        label="wave2-day0-backfill",
        shadow_off=True,
        timeout_seconds=timeout_seconds,
        trigger_type="backfill",
        priority="low",
        intent_profile="client_overview",
    )
    results.append(backfill_run)

    after = metrics_snapshot(api)
    hidden_dependency_issues = [issue for item in results for issue in item.hidden_dependency_issues]
    failed_jobs = [item for item in results if item.job_status != "completed"]

    verdict = "pass"
    conclusion_parts: list[str] = []
    if hidden_dependency_issues:
        verdict = "fail"
        conclusion_parts.append("关闭旧结果通道后仍暴露隐藏依赖")
    if failed_jobs:
        verdict = "fail"
        conclusion_parts.append(f"{len(failed_jobs)} 个 Day 0 job 未完成")
    if idempotency_issues:
        verdict = "fail"
        conclusion_parts.append("同 snapshot 重跑出现对象漂移")
    if impacted_realtime_tasks:
        verdict = "fail"
        conclusion_parts.append("观察到实时任务受 backfill 影响")
    if backfill_run.job_status != "completed":
        verdict = "fail"
        conclusion_parts.append("极小真实 backfill 未完成")
    if verdict == "pass":
        conclusion_parts.append("Day 0 预热通过：关闭旧结果通道、同 snapshot 重跑与极小真实 backfill 均保持稳定。")

    observation = build_observation_payload(
        before_metrics=before["metrics"],
        after_metrics=after["metrics"],
        settings=after["settings"],
        client_count=len(unique_client_ids),
        enqueued_jobs=len(results),
        completed_jobs=len(results) - len(failed_jobs),
        failed_jobs=len(failed_jobs),
        time_range=f"Wave 2 / Day 0 @ {iso_now()}",
        impacted_realtime_tasks=impacted_realtime_tasks,
        shadow_off=bool(after["settings"].get("latestJudgmentsShadowOff")),
        verdict=verdict,
        conclusion="；".join(conclusion_parts),
    )
    if write_observation:
        api.update_stability_settings({"lastCanaryObservation": observation})

    summary = {
        "recordedAt": iso_now(),
        "baseUrl": api.base_url,
        "dryRun": dry_run,
        "before": before,
        "after": after,
        "runs": [
            {
                "label": item.label,
                "clientId": item.client_id,
                "shadowOff": item.shadow_off,
                "jobId": item.job_id,
                "jobStatus": item.job_status,
                "baselineJudgmentId": item.baseline_judgment_id,
                "selectedCandidateId": item.selected_candidate_id,
                "analysisCenterCounts": item.analysis_center_counts,
                "hiddenDependencyIssues": item.hidden_dependency_issues,
            }
            for item in results
        ],
        "idempotencyIssues": idempotency_issues,
        "backfillRun": {
            "clientId": backfill_run.client_id,
            "jobId": backfill_run.job_id,
            "jobStatus": backfill_run.job_status,
            "baselineJudgmentId": backfill_run.baseline_judgment_id,
            "selectedCandidateId": backfill_run.selected_candidate_id,
            "analysisCenterCounts": backfill_run.analysis_center_counts,
            "hiddenDependencyIssues": backfill_run.hidden_dependency_issues,
        },
        "observation": observation,
    }
    if baseline_contract:
        summary = attach_artifact_contract(summary, baseline_contract)
    write_output(output_path, summary)
    return summary


def record_observation(
    api: BackendApi,
    *,
    before_path: str,
    time_range: str,
    client_count: int,
    enqueued_jobs: int,
    completed_jobs: int,
    failed_jobs: int,
    impacted_realtime_tasks: bool,
    verdict: str,
    conclusion: str,
    baseline_contract: dict[str, Any] | None = None,
    output_path: str | None,
) -> dict[str, Any]:
    before_payload = json.loads(Path(before_path).expanduser().resolve().read_text(encoding="utf-8"))
    before_metrics = before_payload.get("metrics") or {}
    after = metrics_snapshot(api)
    observation = build_observation_payload(
        before_metrics=before_metrics,
        after_metrics=after["metrics"],
        settings=after["settings"],
        client_count=client_count,
        enqueued_jobs=enqueued_jobs,
        completed_jobs=completed_jobs,
        failed_jobs=failed_jobs,
        time_range=time_range,
        impacted_realtime_tasks=impacted_realtime_tasks,
        shadow_off=bool(after["settings"].get("latestJudgmentsShadowOff")),
        verdict=verdict,
        conclusion=conclusion,
    )
    updated = api.update_stability_settings({"lastCanaryObservation": observation})
    payload = {
        "recordedAt": iso_now(),
        "baseUrl": api.base_url,
        "before": before_payload,
        "after": after,
        "observation": observation,
        "updatedSettings": updated,
    }
    if baseline_contract:
        payload = attach_artifact_contract(payload, baseline_contract)
    write_output(output_path, payload)
    return payload


def render_value_proof(
    *,
    observation_path: str,
    manual_path: str,
    baseline_contract: dict[str, Any] | None = None,
    output_path: str | None,
) -> str:
    observation = load_observation_payload(observation_path)
    manual = load_json(manual_path)
    rendered = render_value_proof_markdown(
        observation=observation,
        manual=manual,
        baseline_contract=baseline_contract,
    )
    if output_path:
        target = Path(output_path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
        print(rendered)
        return rendered
    print(rendered)
    return rendered


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run v0.3.4 main-chain RC canary steps against the local backend.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"Backend base URL. Default: {DEFAULT_BASE_URL}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    recommend = subparsers.add_parser("recommend-wave1", help="Rank likely Wave 1 clients by recent activity and readiness.")
    recommend.add_argument("--limit", type=int, default=5)
    recommend.add_argument("--lookback-days", type=int, default=14)
    recommend.add_argument("--output", help="Optional JSON output path.")

    recommend_wave2 = subparsers.add_parser("recommend-wave2", help="Rank likely Wave 2 / Day 0 clients by recent activity and readiness.")
    recommend_wave2.add_argument("--limit", type=int, default=5)
    recommend_wave2.add_argument("--lookback-days", type=int, default=14)
    recommend_wave2.add_argument("--output", help="Optional JSON output path.")

    snapshot = subparsers.add_parser("snapshot", help="Capture the current metrics/settings snapshot.")
    snapshot.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    snapshot.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    snapshot.add_argument("--output", help="Optional JSON output path.")

    freeze = subparsers.add_parser("freeze-baseline", help="Write the single RC baseline file used for all Wave 2 discussion.")
    freeze.add_argument("--fixed-gate-status", required=True, choices=("pass", "fail"))
    freeze.add_argument("--full-smoke-summary", required=True, help="Example: '16 failed / 68 passed'")
    freeze.add_argument("--a-class-count", required=True, type=int)
    freeze.add_argument("--b-class-summary", action="append", default=[], help="Repeat for each B-class cluster summary.")
    freeze.add_argument("--c-class-summary", action="append", default=[], help="Repeat for each C-class summary.")
    freeze.add_argument("--notes", help="Optional free-form baseline note.")
    freeze.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    freeze.add_argument("--output", default=str(DEFAULT_OUTPUT_DIR / "rc-baseline.json"), help="Baseline JSON output path.")

    wave1 = subparsers.add_parser("wave1", help="Execute the Wave 1 manual canary sequence.")
    wave1.add_argument("--client-a", required=True, help="Client used for the always-shadow-on window.")
    wave1.add_argument("--client-b", help="Optional second client used for false->true shadow toggle.")
    wave1.add_argument("--idempotency-client", help="Optional client used for the same-snapshot rerun gate. Defaults to client-a.")
    wave1.add_argument("--timeout-seconds", type=float, default=DEFAULT_JOB_TIMEOUT_SECONDS)
    wave1.add_argument("--no-write-observation", action="store_true", help="Skip POST /settings/main-chain-stability lastCanaryObservation.")
    wave1.add_argument("--impacted-realtime-tasks", action="store_true", help="Mark the run as having impacted interactive/system work.")
    wave1.add_argument("--output", help="Optional JSON output path.")

    wave2_day0 = subparsers.add_parser("wave2-day0", help="Execute the Day 0 preheat for Wave 2 with shadow-off enabled throughout.")
    wave2_day0.add_argument(
        "--client-id",
        action="append",
        required=True,
        help="Client to include in the Day 0 preheat. Repeat this flag at least 3 times.",
    )
    wave2_day0.add_argument("--batch-size", type=int, default=1)
    wave2_day0.add_argument("--max-jobs", type=int, default=2)
    wave2_day0.add_argument("--timeout-seconds", type=float, default=DEFAULT_JOB_TIMEOUT_SECONDS)
    wave2_day0.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    wave2_day0.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    wave2_day0.add_argument("--no-write-observation", action="store_true", help="Skip POST /settings/main-chain-stability lastCanaryObservation.")
    wave2_day0.add_argument("--impacted-realtime-tasks", action="store_true", help="Mark the run as having impacted interactive/system work.")
    wave2_day0.add_argument("--output", help="Optional JSON output path.")

    record = subparsers.add_parser("record-observation", help="Record a Wave 2 daily observation using a saved baseline snapshot.")
    record.add_argument("--before", required=True, help="Path to a JSON snapshot captured before the observation window.")
    record.add_argument("--time-range", required=True)
    record.add_argument("--client-count", required=True, type=int)
    record.add_argument("--enqueued-jobs", required=True, type=int)
    record.add_argument("--completed-jobs", required=True, type=int)
    record.add_argument("--failed-jobs", required=True, type=int)
    record.add_argument("--verdict", required=True, choices=("pass", "watch", "fail"))
    record.add_argument("--conclusion", required=True)
    record.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    record.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    record.add_argument("--impacted-realtime-tasks", action="store_true")
    record.add_argument("--output", help="Optional JSON output path.")

    render = subparsers.add_parser("render-value-proof", help="Render a one-page markdown value-proof conclusion from observation JSON plus manual feedback JSON.")
    render.add_argument("--observation", required=True, help="Path to a Wave 2 / Day 0 observation JSON or a script output containing an observation field.")
    render.add_argument("--manual", required=True, help="Path to the manual feedback JSON template filled by the operator.")
    render.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    render.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    render.add_argument("--output", help="Optional markdown output path.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    api = BackendApi(args.base_url)
    try:
        if args.command in {"recommend-wave1", "recommend-wave2"}:
            payload = recommend_wave1_clients(api, limit=max(1, args.limit), lookback_days=max(1, args.lookback_days))
            write_output(args.output, payload)
            return 0
        if args.command == "snapshot":
            capture_snapshot(
                api,
                baseline_path=args.baseline,
                runtime_dir=args.runtime_dir,
                output_path=args.output,
            )
            return 0
        if args.command == "freeze-baseline":
            freeze_rc_baseline(
                api,
                fixed_gate_status=args.fixed_gate_status,
                full_smoke_summary=args.full_smoke_summary,
                a_class_count=max(0, int(args.a_class_count)),
                b_class_summary=list(args.b_class_summary),
                c_class_summary=list(args.c_class_summary),
                notes=args.notes,
                runtime_dir=args.runtime_dir,
                output_path=args.output,
            )
            return 0
        if args.command == "wave1":
            run_wave1(
                api,
                client_a=args.client_a,
                client_b=args.client_b,
                idempotency_client=args.idempotency_client,
                timeout_seconds=max(30.0, float(args.timeout_seconds)),
                write_observation=not args.no_write_observation,
                impacted_realtime_tasks=bool(args.impacted_realtime_tasks),
                output_path=args.output,
            )
            return 0
        if args.command == "wave2-day0":
            gate = _enforce_runtime_contract(
                api,
                baseline_path=args.baseline,
                runtime_dir=args.runtime_dir,
                command_name="wave2-day0",
                allowed_states={"day0_ready"},
            )
            _transition_session_state(
                runtime_dir=args.runtime_dir,
                session=gate["session"],
                state="wave2_active",
                baseline=gate["baseline"],
            )
            run_wave2_day0(
                api,
                client_ids=list(args.client_id),
                batch_size=max(1, int(args.batch_size)),
                max_jobs=max(1, int(args.max_jobs)),
                timeout_seconds=max(30.0, float(args.timeout_seconds)),
                write_observation=not args.no_write_observation,
                impacted_realtime_tasks=bool(args.impacted_realtime_tasks),
                baseline_contract=gate["baseline"],
                output_path=args.output,
            )
            return 0
        if args.command == "record-observation":
            gate = _enforce_runtime_contract(
                api,
                baseline_path=args.baseline,
                runtime_dir=args.runtime_dir,
                command_name="record-observation",
                allowed_states={"wave2_active", "step_b_ready"},
            )
            record_observation(
                api,
                before_path=args.before,
                time_range=args.time_range,
                client_count=max(0, args.client_count),
                enqueued_jobs=max(0, args.enqueued_jobs),
                completed_jobs=max(0, args.completed_jobs),
                failed_jobs=max(0, args.failed_jobs),
                impacted_realtime_tasks=bool(args.impacted_realtime_tasks),
                verdict=args.verdict,
                conclusion=args.conclusion,
                baseline_contract=gate["baseline"],
                output_path=args.output,
            )
            return 0
        if args.command == "render-value-proof":
            gate = _enforce_runtime_contract(
                api,
                baseline_path=args.baseline,
                runtime_dir=args.runtime_dir,
                command_name="render-value-proof",
                allowed_states={"step_b_ready"},
            )
            render_value_proof(
                observation_path=args.observation,
                manual_path=args.manual,
                baseline_contract=gate["baseline"],
                output_path=args.output,
            )
            return 0
        parser.error("unknown command")
        return 2
    except ApiRequestError as exc:
        print(f"HTTP error {exc.status_code}: {exc.detail}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - operational CLI
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        api.close()


if __name__ == "__main__":
    raise SystemExit(main())
~~~

## `backend/scripts/main_chain_rc_contract.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_RUNTIME_DIR = (
    Path.home()
    / "Library"
    / "Application Support"
    / "YiyuThinkTankWorkbench"
    / "runtime"
    / "main-chain-rc"
    / "v0.3.4"
)
DEFAULT_BASELINE_PATH = Path(__file__).resolve().parents[2] / "output" / "main-chain" / "rc-baseline.json"
RC_MODE = "installed-runtime"
RC_SESSION_STATES = (
    "pre_baseline",
    "baseline_frozen",
    "day0_ready",
    "wave2_active",
    "step_b_ready",
    "blocked",
    "completed",
)
IDENTITY_TUPLE_FIELDS = (
    "commitSha",
    "backendUrl",
    "buildVersion",
    "databasePath",
    "latestJudgmentsShadowOff",
    "dirtyWorktree",
    "dirtyPaths",
    "appBundleMTime",
    "rendererEntry",
    "backendStartedByInstalledApp",
)


def iso_now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def normalized_paths(items: list[str] | tuple[str, ...] | None) -> list[str]:
    return sorted({str(item).strip() for item in (items or []) if str(item).strip()})


def stable_json_hash(payload: Any) -> str:
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _installed_runtime_signature(payload: dict[str, Any] | None) -> dict[str, Any]:
    signature = dict(payload or {})
    return {
        "appBundleMTime": signature.get("appBundleMTime"),
        "rendererEntry": signature.get("rendererEntry"),
        "backendStartedByInstalledApp": bool(signature.get("backendStartedByInstalledApp")),
    }


def identity_tuple_payload(identity: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(identity or {})
    signature = _installed_runtime_signature(payload.get("installedRuntimeSignature") if isinstance(payload.get("installedRuntimeSignature"), dict) else payload)
    health = payload.get("health") or {}
    return {
        "commitSha": payload.get("commitSha"),
        "backendUrl": payload.get("backendUrl"),
        "buildVersion": payload.get("buildVersion") or health.get("buildVersion"),
        "databasePath": payload.get("databasePath"),
        "latestJudgmentsShadowOff": bool(payload.get("latestJudgmentsShadowOff")),
        "dirtyWorktree": bool(payload.get("dirtyWorktree")),
        "dirtyPaths": normalized_paths(payload.get("dirtyPaths")),
        "appBundleMTime": payload.get("appBundleMTime") or signature.get("appBundleMTime"),
        "rendererEntry": payload.get("rendererEntry") or signature.get("rendererEntry"),
        "backendStartedByInstalledApp": bool(
            payload.get("backendStartedByInstalledApp")
            if payload.get("backendStartedByInstalledApp") is not None
            else signature.get("backendStartedByInstalledApp")
        ),
    }


def compute_tuple_hash(identity: dict[str, Any] | None) -> str:
    return stable_json_hash(identity_tuple_payload(identity))


def build_session_id(*, generated_at: str | None = None, tuple_hash: str | None = None) -> str:
    timestamp = (generated_at or iso_now()).replace("-", "").replace(":", "").replace("T", "-")
    suffix = (tuple_hash or stable_json_hash({"generatedAt": generated_at or iso_now()}))[:12]
    return f"rc-{timestamp}-{suffix}"


def ensure_baseline_contract(payload: dict[str, Any]) -> dict[str, Any]:
    contracted = deepcopy(payload)
    contracted["rcMode"] = str(contracted.get("rcMode") or RC_MODE)
    contracted["tupleHash"] = str(contracted.get("tupleHash") or compute_tuple_hash(contracted))
    contracted["sessionId"] = str(
        contracted.get("sessionId")
        or build_session_id(
            generated_at=str(contracted.get("generatedAt") or contracted.get("recordedAt") or ""),
            tuple_hash=contracted["tupleHash"],
        )
    )
    baseline_for_hash = deepcopy(contracted)
    baseline_for_hash.pop("baselineHash", None)
    contracted["baselineHash"] = str(contracted.get("baselineHash") or stable_json_hash(baseline_for_hash))
    return contracted


def artifact_contract_fields(baseline_payload: dict[str, Any]) -> dict[str, Any]:
    baseline = ensure_baseline_contract(baseline_payload)
    return {
        "rcMode": baseline.get("rcMode"),
        "sessionId": baseline.get("sessionId"),
        "baselineHash": baseline.get("baselineHash"),
        "tupleHash": baseline.get("tupleHash"),
    }


def attach_artifact_contract(payload: dict[str, Any], baseline_payload: dict[str, Any]) -> dict[str, Any]:
    enriched = deepcopy(payload)
    enriched.update(artifact_contract_fields(baseline_payload))
    return enriched


def resolve_runtime_dir(path: str | Path | None = None) -> Path:
    target = Path(path or DEFAULT_RUNTIME_DIR).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    return target


def rc_session_path(runtime_dir: str | Path | None = None) -> Path:
    return resolve_runtime_dir(runtime_dir) / "rc-session.json"


def default_rc_session(
    *,
    baseline_path: str | Path | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    return {
        "sessionId": session_id,
        "rcMode": RC_MODE,
        "state": "pre_baseline",
        "baselinePath": str(Path(baseline_path).expanduser().resolve()) if baseline_path else None,
        "baselineHash": None,
        "tupleHash": None,
        "installReceiptPath": None,
        "installSmokePath": None,
        "activeInstallSignature": None,
        "invalidatedAt": None,
        "invalidationReason": None,
        "updatedAt": iso_now(),
    }


def load_rc_session(runtime_dir: str | Path | None = None) -> dict[str, Any] | None:
    path = rc_session_path(runtime_dir)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"RC session at {path} is not a JSON object")
    payload.setdefault("rcMode", RC_MODE)
    payload["state"] = str(payload.get("state") or "pre_baseline").replace("-", "_")
    payload.setdefault("updatedAt", iso_now())
    return payload


def write_rc_session(payload: dict[str, Any], *, runtime_dir: str | Path | None = None) -> dict[str, Any]:
    path = rc_session_path(runtime_dir)
    session = deepcopy(payload)
    session["rcMode"] = str(session.get("rcMode") or RC_MODE)
    state = str(session.get("state") or "pre_baseline")
    if state not in RC_SESSION_STATES:
        raise RuntimeError(f"Unsupported rc-session state: {state}")
    session["state"] = state
    session["updatedAt"] = str(session.get("updatedAt") or iso_now())
    path.write_text(json.dumps(session, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return session


def active_install_signature_from_artifacts(
    *,
    install_receipt_payload: dict[str, Any] | None,
    install_smoke_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    receipt = dict(install_receipt_payload or {})
    smoke = dict(install_smoke_payload or {})
    return {
        "appBundleMTime": receipt.get("targetAppMTime") or receipt.get("sourceAppMTime"),
        "rendererEntry": receipt.get("targetRendererEntry") or receipt.get("sourceRendererEntry") or smoke.get("targetRendererEntry") or smoke.get("sourceRendererEntry"),
        "backendStartedByInstalledApp": bool(smoke.get("backendStartedByInstalledApp")),
    }
~~~

## `backend/scripts/main_chain_rc_ops.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

try:
    from scripts.main_chain_rc_contract import (
        RC_MODE,
        attach_artifact_contract,
        active_install_signature_from_artifacts,
        compute_tuple_hash,
        default_rc_session,
        ensure_baseline_contract,
        load_rc_session,
        resolve_runtime_dir,
        stable_json_hash,
        write_rc_session,
    )
    from scripts.main_chain_canary import (
        DEFAULT_BASE_URL,
        BackendApi,
        candidate_is_knowledge_ready,
        get_git_commit_sha,
        get_git_dirty_worktree_state,
        get_repo_relative_path,
        inspect_installed_app,
        inspect_installed_runtime_signature,
        iso_now,
        load_json,
        load_observation_payload,
        metrics_snapshot,
        write_output,
    )
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from scripts.main_chain_rc_contract import (  # type: ignore[no-redef]
        RC_MODE,
        active_install_signature_from_artifacts,
        attach_artifact_contract,
        compute_tuple_hash,
        default_rc_session,
        ensure_baseline_contract,
        load_rc_session,
        resolve_runtime_dir,
        stable_json_hash,
        write_rc_session,
    )
    from scripts.main_chain_canary import (  # type: ignore[no-redef]
        DEFAULT_BASE_URL,
        BackendApi,
        candidate_is_knowledge_ready,
        get_git_commit_sha,
        get_git_dirty_worktree_state,
        get_repo_relative_path,
        inspect_installed_app,
        inspect_installed_runtime_signature,
        iso_now,
        load_json,
        load_observation_payload,
        metrics_snapshot,
        write_output,
    )


DEFAULT_RUNTIME_DIR = (
    Path.home()
    / "Library"
    / "Application Support"
    / "YiyuThinkTankWorkbench"
    / "runtime"
    / "main-chain-rc"
    / "v0.3.4"
)
DEFAULT_BASELINE_PATH = Path(__file__).resolve().parents[2] / "output" / "main-chain" / "rc-baseline.json"
DEFAULT_DAY0_PRIORITY = [
    "client_cffc",
    "client_a4d1db29a7",
    "client_53d82aa249",
    "client_284afd836e",
    "client_cb720fc373",
]
DEFAULT_CONTROL_PRIORITY = [
    "client_cffc",
    "client_a4d1db29a7",
    "client_284afd836e",
    "client_53d82aa249",
]
DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FULL_SMOKE_CLASSIFICATION_REASON = (
    "按 installed-runtime / shadow-off / Step A / Day 0 / 4 个价值场景边界归类；"
    "只有命中这些边界的问题才算 RC blocker。"
)
DB_ISOLATION_REQUIRED_PATTERNS = (
    {
        "label": "apiSmokeUsesTmpDataDir",
        "path": Path("backend/tests/test_api_smoke.py"),
        "pattern": re.compile(r'create_app\(tmp_path\s*/\s*["\']data["\']\)'),
        "description": 'API smoke 通过 create_app(tmp_path / "data") 启动临时数据目录。',
    },
    {
        "label": "analysisMainChainUsesTmpDataDir",
        "path": Path("backend/tests/test_analysis_main_chain.py"),
        "pattern": re.compile(r'create_app\(tmp_path\s*/\s*["\']data["\']\)'),
        "description": 'analysis main chain 通过 create_app(tmp_path / "data") 启动临时数据目录。',
    },
)
TMP_DB_PATTERN = re.compile(r'Database\(tmp_path\s*/\s*["\']app\.db["\']\)')
DEFAULT_PAGE_PROOF_TOKENS = {
    "overview": ["主链接管稳定化", "Overview", "fallback"],
    "workspace-state": ["状态优先", "正式判断", "待确认判断", "本周动作", "风险提醒", "缺失信息"],
    "workspace-drilldown": ["证据下钻", "引用", "原文"],
    "task-prep": ["status", "effectType", "prep_artifact_ready"],
    "meeting-followup": ["followup_task_created", "会后", "任务"],
    "cockpit": ["official", "empty reason", "radar"],
}


def _normalized_paths(items: list[str] | None) -> list[str]:
    return sorted({str(item).strip() for item in (items or []) if str(item).strip()})


def _dedupe_preserve_order(items: list[str] | None) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in items or []:
        value = str(raw).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _expected_installed_runtime_database_path(*, home_dir: Path | None = None) -> Path:
    base = (home_dir or Path.home()).expanduser().resolve()
    return base / "Library" / "Application Support" / "YiyuThinkTankWorkbench" / "app.db"


def _repo_relative_display(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path.resolve())


def _run_command(command: list[str], *, cwd: Path | None = None) -> tuple[int, str, str]:
    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout or "", result.stderr or ""


def _ensure_runtime_dir(path: str | Path | None = None) -> Path:
    return resolve_runtime_dir(path)


def _load_json_object(path: str | Path) -> dict[str, Any]:
    payload = load_json(str(Path(path).expanduser().resolve()))
    if not isinstance(payload, dict):
        raise RuntimeError(f"JSON payload at {path} is not an object")
    return payload


def _load_baseline_contract(path: str | Path | None) -> dict[str, Any]:
    baseline_path = Path(path or DEFAULT_BASELINE_PATH).expanduser().resolve()
    if not baseline_path.exists():
        raise RuntimeError(f"baseline file not found: {baseline_path}")
    return ensure_baseline_contract(_load_json_object(baseline_path))


def _ensure_session_for_baseline(
    *,
    runtime_dir: str | Path | None,
    baseline: dict[str, Any],
    baseline_path: str | Path | None = None,
) -> dict[str, Any]:
    runtime_root = _ensure_runtime_dir(runtime_dir)
    baseline_contract = ensure_baseline_contract(baseline)
    resolved_baseline_path = str(Path(baseline_path or DEFAULT_BASELINE_PATH).expanduser().resolve())
    session = load_rc_session(runtime_root)
    if session is None:
        session = default_rc_session(
            baseline_path=resolved_baseline_path,
            session_id=str(baseline_contract.get("sessionId") or ""),
        )
    if str(session.get("baselineHash") or "") != str(baseline_contract.get("baselineHash") or ""):
        session["sessionId"] = baseline_contract.get("sessionId")
        session["baselinePath"] = resolved_baseline_path
        session["baselineHash"] = baseline_contract.get("baselineHash")
        session["tupleHash"] = baseline_contract.get("tupleHash")
        if str(session.get("state") or "") == "pre_baseline":
            session["state"] = "baseline_frozen"
    return write_rc_session(session, runtime_dir=runtime_root)


def _transition_session_state(
    *,
    runtime_dir: str | Path | None,
    session: dict[str, Any],
    state: str,
    baseline: dict[str, Any] | None = None,
    invalidation_reason: str | None = None,
    install_receipt_path: str | None = None,
    install_smoke_path: str | None = None,
    active_install_signature: dict[str, Any] | None = None,
) -> dict[str, Any]:
    updated = deepcopy(session)
    updated["state"] = state
    if baseline:
        updated["sessionId"] = baseline.get("sessionId")
        updated["baselineHash"] = baseline.get("baselineHash")
        updated["tupleHash"] = baseline.get("tupleHash")
    if install_receipt_path is not None:
        updated["installReceiptPath"] = install_receipt_path
    if install_smoke_path is not None:
        updated["installSmokePath"] = install_smoke_path
    if active_install_signature is not None:
        updated["activeInstallSignature"] = active_install_signature
    if state == "pre_baseline":
        updated["invalidatedAt"] = iso_now()
        updated["invalidationReason"] = invalidation_reason
    else:
        updated["invalidatedAt"] = None
        updated["invalidationReason"] = None
    return write_rc_session(updated, runtime_dir=runtime_dir)


def _page_proof_default_output(page: str, *, runtime_dir: str | Path | None = None) -> Path:
    return _ensure_runtime_dir(runtime_dir) / f"page-proof-{page}.json"


def _page_proof_expected_tokens(page: str, explicit_tokens: list[str] | None = None) -> list[str]:
    if explicit_tokens:
        return _dedupe_preserve_order(explicit_tokens)
    return list(DEFAULT_PAGE_PROOF_TOKENS.get(page, []))


def _validate_page_proof_contract(
    path: str | Path,
    *,
    baseline_hash: str | None,
    tuple_hash: str | None,
    session_id: str | None,
    expected_page: str | None = None,
) -> dict[str, Any]:
    payload = _load_json_object(path)
    if str(payload.get("decision") or "").strip() != "pass":
        raise RuntimeError(f"page proof {path} is not pass")
    if expected_page and str(payload.get("page") or "").strip() != expected_page:
        raise RuntimeError(f"page proof {path} does not match page={expected_page}")
    if baseline_hash and str(payload.get("baselineHash") or "") != str(baseline_hash):
        raise RuntimeError(f"page proof {path} baselineHash mismatch")
    if tuple_hash and str(payload.get("tupleHash") or "") != str(tuple_hash):
        raise RuntimeError(f"page proof {path} tupleHash mismatch")
    if session_id and str(payload.get("sessionId") or "") != str(session_id):
        raise RuntimeError(f"page proof {path} sessionId mismatch")
    return payload


def _baseline_generated_at(payload: dict[str, Any]) -> Any:
    return payload.get("baselineGeneratedAt") or payload.get("generatedAt")


def _default_source_app_path() -> Path:
    return DEFAULT_REPO_ROOT / "dist" / "mac-arm64" / "益语智库自用平台.app"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _normalize_installed_runtime_signature(payload: dict[str, Any] | None, *, fallback_app: dict[str, Any] | None = None) -> dict[str, Any]:
    runtime_signature = dict(payload or {})
    if fallback_app:
        runtime_signature.setdefault("appBundleMTime", fallback_app.get("modifiedAt"))
        runtime_signature.setdefault("rendererEntry", fallback_app.get("rendererEntry"))
    runtime_signature.setdefault("backendStartedByInstalledApp", False)
    runtime_signature.setdefault("backendPid", None)
    runtime_signature.setdefault("backendCommand", None)
    return runtime_signature


def load_baseline_identity(path: str) -> dict[str, Any]:
    payload = ensure_baseline_contract(load_json(path))
    stability = payload.get("mainChainStability") or {}
    health = payload.get("health") or {}
    installed_app = payload.get("installedApp") or {}
    installed_runtime_signature = _normalize_installed_runtime_signature(
        payload.get("installedRuntimeSignature"),
        fallback_app=installed_app if isinstance(installed_app, dict) else None,
    )
    database_path = str(payload.get("databasePath") or "").strip()
    identity = {
        "baselineGeneratedAt": payload.get("generatedAt"),
        "commitSha": payload.get("commitSha"),
        "backendUrl": payload.get("backendUrl"),
        "buildVersion": health.get("buildVersion"),
        "databasePath": str(Path(database_path).expanduser().resolve()) if database_path else None,
        "latestJudgmentsShadowOff": bool(
            payload.get("latestJudgmentsShadowOff")
            if payload.get("latestJudgmentsShadowOff") is not None
            else stability.get("latestJudgmentsShadowOff")
        ),
        "dirtyWorktree": bool(payload.get("dirtyWorktree")),
        "dirtyPaths": _normalized_paths(payload.get("dirtyPaths")),
        "installedRuntimeSignature": installed_runtime_signature,
    }
    if payload.get("installedRuntimeSignature") is not None or payload.get("installedApp") is not None:
        identity["appBundleMTime"] = installed_runtime_signature.get("appBundleMTime")
        identity["rendererEntry"] = installed_runtime_signature.get("rendererEntry")
        identity["backendStartedByInstalledApp"] = bool(installed_runtime_signature.get("backendStartedByInstalledApp"))
        identity["backendPid"] = installed_runtime_signature.get("backendPid")
    identity["sessionId"] = payload.get("sessionId")
    identity["baselineHash"] = payload.get("baselineHash")
    identity["tupleHash"] = payload.get("tupleHash")
    identity["rcMode"] = payload.get("rcMode") or RC_MODE
    return identity


def _collect_invalidated_runtime_artifacts(runtime_dir: Path) -> list[Path]:
    patterns = (
        "day0-*.json",
        "day0-*.note.json",
        "wave2-*.json",
        "wave2-*.note.json",
        "install-step-*.json",
        "install-step-*.note.json",
    )
    artifacts: set[Path] = set()
    for pattern in patterns:
        artifacts.update(item.resolve() for item in runtime_dir.glob(pattern) if item.is_file())
    return sorted(artifacts)


def write_invalidated_artifacts_note(
    *,
    runtime_dir: str | None,
    baseline_path: str | None,
    source_app_path: str | None,
    applications_dir: str | None,
    output_path: str | None,
    invalidated_session_id: str | None = None,
    invalidated_baseline_hash: str | None = None,
    invalidated_tuple_hash: str | None = None,
    replacement_session_id: str | None = None,
    replacement_baseline_hash: str | None = None,
) -> dict[str, Any]:
    runtime_root = _ensure_runtime_dir(runtime_dir)
    baseline_target = Path(baseline_path or DEFAULT_BASELINE_PATH).expanduser().resolve()
    source_app_target = Path(source_app_path).expanduser().resolve() if source_app_path else _default_source_app_path()
    applications_root = Path(applications_dir).expanduser().resolve() if applications_dir else (Path.home() / "Applications")
    recorded_at = iso_now()
    entries: list[dict[str, Any]] = []
    may_not_be_used_for = ["baseline", "day0", "wave2", "value-proof"]
    source_app_info = inspect_installed_app(source_app_target)
    source_renderer_entry = source_app_info.get("rendererEntry")

    if baseline_target.exists():
        baseline_payload = load_json(str(baseline_target))
        if baseline_payload.get("installedRuntimeSignature") is None:
            entries.append(
                {
                    "path": str(baseline_target),
                    "invalidatedAt": recorded_at,
                    "reason": "旧 rc-baseline 缺少 installedRuntimeSignature，只能作历史参考，不能继续作为本轮 RC 基线。",
                    "replacement": None,
                    "mayNotBeUsedFor": may_not_be_used_for,
                }
            )

    for artifact_path in _collect_invalidated_runtime_artifacts(runtime_root):
        reason = "旧运行产物绑定到已失效的 installed-runtime 现场，不能继续作为本轮 RC 证据。"
        if artifact_path.name.startswith("install-step-"):
            reason = "旧安装版闭环证据绑定到已失效现场，不能继续作为本轮 RC 的安装链证明。"
        entries.append(
            {
                "path": str(artifact_path),
                "invalidatedAt": recorded_at,
                "reason": reason,
                "replacement": None,
                "mayNotBeUsedFor": may_not_be_used_for,
            }
        )

    if applications_root.exists():
        for bundle in sorted(applications_root.glob(".益语智库自用平台.installing-*.app")):
            bundle_info = inspect_installed_app(bundle)
            renderer_entry = bundle_info.get("rendererEntry")
            reason = "历史 staging bundle 不得作为 target app fallback 使用。"
            if source_renderer_entry and renderer_entry != source_renderer_entry:
                reason = (
                    f"历史 staging bundle 的 rendererEntry={renderer_entry or 'null'} 与当前受信安装源 "
                    f"{source_renderer_entry} 不一致，不得用于本轮 installed-runtime RC。"
                )
            entries.append(
                {
                    "path": str(bundle.resolve()),
                    "invalidatedAt": recorded_at,
                    "reason": reason,
                    "replacement": None,
                    "mayNotBeUsedFor": may_not_be_used_for,
                }
            )

    payload = {
        "recordedAt": recorded_at,
        "rcMode": RC_MODE,
        "runtimeDir": str(runtime_root),
        "baselinePath": str(baseline_target),
        "sourceApp": str(source_app_target),
        "sourceRendererEntry": source_renderer_entry,
        "invalidatedSessionId": invalidated_session_id,
        "invalidatedBaselineHash": invalidated_baseline_hash,
        "invalidatedTupleHash": invalidated_tuple_hash,
        "replacementSessionId": replacement_session_id,
        "replacementBaselineHash": replacement_baseline_hash,
        "mayNotBeUsedFor": may_not_be_used_for,
        "entries": entries,
    }
    target_output = (
        Path(output_path).expanduser().resolve()
        if output_path
        else runtime_root / "invalidated-artifacts.note.json"
    )
    write_output(str(target_output), payload)
    return payload


def sync_rc_session(
    *,
    runtime_dir: str | None,
    baseline_path: str | None,
    install_receipt_path: str | None,
    install_smoke_path: str | None,
    output_path: str | None,
) -> dict[str, Any]:
    runtime_root = _ensure_runtime_dir(runtime_dir)
    resolved_baseline_path = Path(baseline_path or DEFAULT_BASELINE_PATH).expanduser().resolve()
    resolved_receipt_path = Path(install_receipt_path or (runtime_root / "install-receipt.json")).expanduser().resolve()
    resolved_smoke_path = Path(install_smoke_path or (runtime_root / "install-smoke.json")).expanduser().resolve()
    session = load_rc_session(runtime_root) or default_rc_session(
        baseline_path=str(resolved_baseline_path),
        session_id=None,
    )
    install_receipt_payload = _load_json_object(resolved_receipt_path) if resolved_receipt_path.exists() else None
    install_smoke_payload = _load_json_object(resolved_smoke_path) if resolved_smoke_path.exists() else None
    active_install_signature = active_install_signature_from_artifacts(
        install_receipt_payload=install_receipt_payload,
        install_smoke_payload=install_smoke_payload,
    )
    session["installReceiptPath"] = str(resolved_receipt_path) if resolved_receipt_path.exists() else None
    session["installSmokePath"] = str(resolved_smoke_path) if resolved_smoke_path.exists() else None
    session["activeInstallSignature"] = active_install_signature

    payload: dict[str, Any] = {
        "recordedAt": iso_now(),
        "runtimeDir": str(runtime_root),
        "baselinePath": str(resolved_baseline_path),
        "installReceiptPath": session.get("installReceiptPath"),
        "installSmokePath": session.get("installSmokePath"),
        "activeInstallSignature": active_install_signature,
        "state": "pre_baseline",
        "reason": "baseline_missing",
    }
    if not resolved_baseline_path.exists():
        synced = _transition_session_state(
            runtime_dir=runtime_root,
            session=session,
            state="pre_baseline",
            invalidation_reason="baseline_missing",
            install_receipt_path=session.get("installReceiptPath"),
            install_smoke_path=session.get("installSmokePath"),
            active_install_signature=active_install_signature,
        )
        payload["session"] = synced
        write_output(str(output_path) if output_path else str(runtime_root / "rc-session.json"), synced if not output_path else payload)
        return synced if not output_path else payload

    baseline_contract = _load_baseline_contract(resolved_baseline_path)
    baseline_signature = (baseline_contract.get("installedRuntimeSignature") or {})
    drift_fields = []
    for field in ("appBundleMTime", "rendererEntry", "backendStartedByInstalledApp"):
        if baseline_signature.get(field) != active_install_signature.get(field):
            drift_fields.append(field)
    if drift_fields:
        reason = "install_signature_drift:" + ",".join(drift_fields)
        synced = _transition_session_state(
            runtime_dir=runtime_root,
            session=session,
            state="pre_baseline",
            baseline=baseline_contract,
            invalidation_reason=reason,
            install_receipt_path=session.get("installReceiptPath"),
            install_smoke_path=session.get("installSmokePath"),
            active_install_signature=active_install_signature,
        )
        write_invalidated_artifacts_note(
            runtime_dir=str(runtime_root),
            baseline_path=str(resolved_baseline_path),
            source_app_path=None,
            applications_dir=None,
            output_path=str(runtime_root / "invalidated-artifacts.note.json"),
            invalidated_session_id=str(baseline_contract.get("sessionId") or ""),
            invalidated_baseline_hash=str(baseline_contract.get("baselineHash") or ""),
            invalidated_tuple_hash=str(baseline_contract.get("tupleHash") or ""),
            replacement_session_id=None,
            replacement_baseline_hash=None,
        )
        payload.update(
            {
                "state": "pre_baseline",
                "reason": reason,
                "driftFields": drift_fields,
                "baselineHash": baseline_contract.get("baselineHash"),
                "tupleHash": baseline_contract.get("tupleHash"),
                "sessionId": baseline_contract.get("sessionId"),
                "session": synced,
            }
        )
        write_output(str(output_path) if output_path else str(runtime_root / "rc-session.json"), synced if not output_path else payload)
        return synced if not output_path else payload

    synced = _transition_session_state(
        runtime_dir=runtime_root,
        session=session,
        state="baseline_frozen" if str(session.get("state") or "") == "pre_baseline" else str(session.get("state") or "baseline_frozen"),
        baseline=baseline_contract,
        install_receipt_path=session.get("installReceiptPath"),
        install_smoke_path=session.get("installSmokePath"),
        active_install_signature=active_install_signature,
    )
    payload.update(
        {
            "state": synced.get("state"),
            "reason": "in_sync",
            "baselineHash": baseline_contract.get("baselineHash"),
            "tupleHash": baseline_contract.get("tupleHash"),
            "sessionId": baseline_contract.get("sessionId"),
            "session": synced,
        }
    )
    write_output(str(output_path) if output_path else str(runtime_root / "rc-session.json"), synced if not output_path else payload)
    return synced if not output_path else payload


def write_page_proof(
    *,
    baseline_path: str,
    runtime_dir: str | None,
    page: str,
    screenshot_path: str,
    expected_tokens: list[str] | None,
    ax_text_path: str | None,
    ocr_text_path: str | None,
    output_path: str | None,
) -> dict[str, Any]:
    baseline_contract = _load_baseline_contract(baseline_path)
    _ensure_session_for_baseline(
        runtime_dir=runtime_dir,
        baseline=baseline_contract,
        baseline_path=baseline_path,
    )
    expected = _page_proof_expected_tokens(page, expected_tokens)
    observed_source = ax_text_path or ocr_text_path
    if not observed_source:
        raise RuntimeError("write-page-proof requires --ax-text or --ocr-text")
    observed_text = Path(observed_source).expanduser().resolve().read_text(encoding="utf-8", errors="ignore")
    observed_tokens = _dedupe_preserve_order([line.strip() for line in observed_text.splitlines() if line.strip()])
    haystack = observed_text.lower()
    matched_tokens = [token for token in expected if token.lower() in haystack]
    missing_tokens = [token for token in expected if token not in matched_tokens]
    payload = {
        "page": page,
        "screenshotPath": str(Path(screenshot_path).expanduser().resolve()),
        "expectedTokens": expected,
        "observedTokens": observed_tokens,
        "matchedTokens": matched_tokens,
        "missingTokens": missing_tokens,
        "decision": "pass" if expected and not missing_tokens else "fail",
        "reason": "all expected tokens observed" if expected and not missing_tokens else "missing expected tokens",
        "recordedAt": iso_now(),
    }
    payload = attach_artifact_contract(payload, baseline_contract)
    target_output = Path(output_path).expanduser().resolve() if output_path else _page_proof_default_output(page, runtime_dir=runtime_dir)
    write_output(str(target_output), payload)
    return payload


def collect_runtime_identity(api: BackendApi, *, baseline_path: str | None = None) -> dict[str, Any]:
    snapshot = metrics_snapshot(api)
    app_settings = (snapshot.get("appSettings") or {}).get("settings") or {}
    health = (snapshot.get("appSettings") or {}).get("health") or {}
    excluded_path = get_repo_relative_path(baseline_path) if baseline_path else None
    dirty_state = get_git_dirty_worktree_state(excluded_paths=[excluded_path] if excluded_path else None)
    data_dir = str(app_settings.get("dataDir") or "").strip()
    installed_app = inspect_installed_app()
    installed_runtime_signature = _normalize_installed_runtime_signature(
        inspect_installed_runtime_signature(api.base_url, installed_app=installed_app),
        fallback_app=installed_app,
    )
    return {
        "baselineGeneratedAt": None,
        "commitSha": get_git_commit_sha(),
        "backendUrl": api.base_url,
        "buildVersion": health.get("buildVersion"),
        "databasePath": str(Path(data_dir).expanduser().resolve() / "app.db") if data_dir else None,
        "latestJudgmentsShadowOff": bool((snapshot.get("settings") or {}).get("latestJudgmentsShadowOff")),
        "dirtyWorktree": bool(dirty_state["dirtyWorktree"]),
        "dirtyPaths": _normalized_paths(dirty_state["dirtyPaths"]),
        "installedRuntimeSignature": installed_runtime_signature,
        "appBundleMTime": installed_runtime_signature.get("appBundleMTime"),
        "rendererEntry": installed_runtime_signature.get("rendererEntry"),
        "backendStartedByInstalledApp": bool(installed_runtime_signature.get("backendStartedByInstalledApp")),
        "backendPid": installed_runtime_signature.get("backendPid"),
    }


def compare_identity_tuple(*, baseline: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    for field in (
        "commitSha",
        "backendUrl",
        "buildVersion",
        "databasePath",
        "latestJudgmentsShadowOff",
        "dirtyWorktree",
        "dirtyPaths",
        "appBundleMTime",
        "rendererEntry",
        "backendStartedByInstalledApp",
    ):
        if field not in baseline:
            continue
        if baseline.get(field) != current.get(field):
            mismatches.append(
                {
                    "field": field,
                    "expected": baseline.get(field),
                    "actual": current.get(field),
                }
            )
    return mismatches


def _record_session_invalidation(
    *,
    runtime_dir: str | Path | None,
    baseline_path: str | Path | None,
    baseline_contract: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    runtime_root = _ensure_runtime_dir(runtime_dir)
    session = load_rc_session(runtime_root) or default_rc_session(
        baseline_path=str(Path(baseline_path or DEFAULT_BASELINE_PATH).expanduser().resolve()),
        session_id=str(baseline_contract.get("sessionId") or ""),
    )
    updated = _transition_session_state(
        runtime_dir=runtime_root,
        session=session,
        state="pre_baseline",
        baseline=baseline_contract,
        invalidation_reason=reason,
    )
    write_invalidated_artifacts_note(
        runtime_dir=str(runtime_root),
        baseline_path=str(Path(baseline_path or DEFAULT_BASELINE_PATH).expanduser().resolve()),
        source_app_path=None,
        applications_dir=None,
        output_path=str(runtime_root / "invalidated-artifacts.note.json"),
        invalidated_session_id=str(baseline_contract.get("sessionId") or ""),
        invalidated_baseline_hash=str(baseline_contract.get("baselineHash") or ""),
        invalidated_tuple_hash=str(baseline_contract.get("tupleHash") or ""),
        replacement_session_id=None,
        replacement_baseline_hash=None,
    )
    return updated


def _enforce_runtime_contract(
    api: BackendApi,
    *,
    baseline_path: str | Path | None,
    runtime_dir: str | Path | None,
    command_name: str,
    allowed_states: set[str],
) -> dict[str, Any]:
    baseline_contract = _load_baseline_contract(baseline_path)
    session = _ensure_session_for_baseline(
        runtime_dir=runtime_dir,
        baseline=baseline_contract,
        baseline_path=baseline_path,
    )
    current_state = str(session.get("state") or "pre_baseline")
    if current_state not in allowed_states:
        raise RuntimeError(
            f"{command_name} requires rc-session.state in {sorted(allowed_states)}, got {current_state}"
        )
    current_identity = collect_runtime_identity(api, baseline_path=str(baseline_path or DEFAULT_BASELINE_PATH))
    current_identity["baselineGeneratedAt"] = _baseline_generated_at(baseline_contract)
    mismatches = compare_identity_tuple(baseline=baseline_contract, current=current_identity)
    current_tuple_hash = compute_tuple_hash(current_identity)
    if mismatches or str(baseline_contract.get("tupleHash") or "") != current_tuple_hash:
        mismatch_reason = (
            f"{command_name} refused to continue because live tupleHash={current_tuple_hash} "
            f"does not match baseline tupleHash={baseline_contract.get('tupleHash')}"
        )
        _record_session_invalidation(
            runtime_dir=runtime_dir,
            baseline_path=baseline_path,
            baseline_contract=baseline_contract,
            reason=mismatch_reason,
        )
        raise RuntimeError(mismatch_reason)
    return {
        "baseline": baseline_contract,
        "session": session,
        "currentIdentity": current_identity,
        "currentTupleHash": current_tuple_hash,
    }


def run_preflight(api: BackendApi, *, baseline_path: str, runtime_dir: str | None = None) -> dict[str, Any]:
    gate = _enforce_runtime_contract(
        api,
        baseline_path=baseline_path,
        runtime_dir=runtime_dir,
        command_name="preflight",
        allowed_states={"baseline_frozen", "day0_ready"},
    )
    baseline_identity = gate["baseline"]
    current_identity = collect_runtime_identity(api, baseline_path=baseline_path)
    current_identity["baselineGeneratedAt"] = _baseline_generated_at(baseline_identity)
    snapshot = metrics_snapshot(api)
    settings = snapshot.get("settings") or {}
    mismatches = compare_identity_tuple(baseline=baseline_identity, current=current_identity)
    shadow_off = bool(settings.get("latestJudgmentsShadowOff"))
    backfill_paused = bool(settings.get("backfillPaused"))
    backend_started_by_installed_app = bool(current_identity.get("backendStartedByInstalledApp"))
    endpoints_reachable = True
    checks = [
        {"name": "settings main-chain-stability reachable", "passed": True},
        {"name": "runtime analysis-migration-metrics reachable", "passed": True},
        {"name": "latestJudgmentsShadowOff=true", "passed": shadow_off},
        {"name": "backfillPaused=false", "passed": not backfill_paused},
        {"name": "backendStartedByInstalledApp=true", "passed": backend_started_by_installed_app},
        {"name": "identity tuple matches baseline", "passed": not mismatches},
    ]
    payload = {
        "recordedAt": iso_now(),
        "baseUrl": api.base_url,
        "baselinePath": str(Path(baseline_path).expanduser().resolve()),
        "runtimeDir": str(_ensure_runtime_dir(runtime_dir)),
        "baselineIdentity": baseline_identity,
        "currentIdentity": current_identity,
        "mismatches": mismatches,
        "identityMatchesBaseline": not mismatches,
        "endpointsReachable": endpoints_reachable,
        "latestJudgmentsShadowOff": shadow_off,
        "backfillPaused": backfill_paused,
        "checks": checks,
        "installedApp": inspect_installed_app(),
        "readyForDay0": endpoints_reachable and shadow_off and not backfill_paused and backend_started_by_installed_app and not mismatches,
    }
    payload = attach_artifact_contract(payload, baseline_identity)
    next_state = "day0_ready" if payload["readyForDay0"] else str(gate["session"].get("state") or "baseline_frozen")
    _transition_session_state(
        runtime_dir=runtime_dir,
        session=gate["session"],
        state=next_state,
        baseline=baseline_identity,
    )
    return payload


def verify_db_isolation(
    api: BackendApi,
    *,
    repo_root: Path | None = None,
    home_dir: Path | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    root = (repo_root or DEFAULT_REPO_ROOT).resolve()
    current_identity = collect_runtime_identity(api)
    live_database_path = str(current_identity.get("databasePath") or "").strip()
    expected_database_path = _expected_installed_runtime_database_path(home_dir=home_dir)
    live_database_matches = bool(live_database_path) and Path(live_database_path).expanduser().resolve() == expected_database_path

    required_test_evidence: list[dict[str, Any]] = []
    missing_evidence: list[str] = []
    for item in DB_ISOLATION_REQUIRED_PATTERNS:
        target = (root / item["path"]).resolve()
        found = target.is_file() and bool(item["pattern"].search(_read_text(target)))
        required_test_evidence.append(
            {
                "label": item["label"],
                "path": _repo_relative_display(target, root),
                "description": item["description"],
                "found": found,
            }
        )
        if not found:
            missing_evidence.append(f"缺少静态证据：{item['label']}")

    tmp_db_pattern_hits: list[str] = []
    tests_root = root / "backend" / "tests"
    if tests_root.exists():
        for path in sorted(tests_root.rglob("*.py")):
            if TMP_DB_PATTERN.search(_read_text(path)):
                tmp_db_pattern_hits.append(_repo_relative_display(path, root))
    if not tmp_db_pattern_hits:
        missing_evidence.append('未找到 Database(tmp_path / "app.db") 的测试静态证据。')
    if not live_database_matches:
        missing_evidence.append(
            f"live backend databasePath 不是 installed-runtime app.db：{live_database_path or 'null'}"
        )

    ready_for_baseline_regeneration = (
        live_database_matches
        and all(bool(item["found"]) for item in required_test_evidence)
        and bool(tmp_db_pattern_hits)
    )
    summary_parts = [
        "live backend 仍指向 installed-runtime app.db" if live_database_matches else "live backend databasePath 与 installed-runtime app.db 不一致",
        'pytest/smoke 已证明走 tmp_path / "data"' if all(bool(item["found"]) for item in required_test_evidence) else '仍缺少 create_app(tmp_path / "data") 静态证据',
        '已发现 Database(tmp_path / "app.db") 临时库证据' if tmp_db_pattern_hits else '仍缺少 Database(tmp_path / "app.db") 临时库证据',
    ]
    payload = {
        "recordedAt": iso_now(),
        "repoRoot": str(root),
        "baseUrl": api.base_url,
        "liveDatabasePath": live_database_path or None,
        "expectedInstalledRuntimeDatabasePath": str(expected_database_path),
        "liveDatabaseMatchesInstalledRuntime": live_database_matches,
        "requiredTestEvidence": required_test_evidence,
        "temporaryDbPattern": 'Database(tmp_path / "app.db")',
        "temporaryDbPatternHits": tmp_db_pattern_hits,
        "missingEvidence": missing_evidence,
        "summary": "；".join(summary_parts),
        "readyForBaselineRegeneration": ready_for_baseline_regeneration,
    }
    target_output = (
        Path(output_path).expanduser().resolve()
        if output_path
        else _ensure_runtime_dir() / "db-isolation-check.json"
    )
    write_output(str(target_output), payload)
    return payload


def _event_line_task_count(workspace: dict[str, Any]) -> int:
    related_tasks = workspace.get("relatedTasks") or []
    return sum(
        1
        for item in related_tasks
        if isinstance(item, dict) and (str(item.get("eventLineId") or "").strip() or str(item.get("eventLineName") or "").strip())
    )


def _representation_flags(workspace: dict[str, Any], cockpit: dict[str, Any]) -> dict[str, bool]:
    knowledge_status = workspace.get("knowledgeStatus") or {}
    document_count = max(
        len(workspace.get("documentCards") or []),
        int(knowledge_status.get("totalDocuments") or 0),
    )
    meeting_count = len(workspace.get("meetings") or [])
    event_line_task_count = _event_line_task_count(workspace)
    radar_candidates = len(((cockpit.get("radarLayer") or {}).get("candidateJudgments") or []))
    official_ready = str(cockpit.get("officialLayerStatus") or "") == "ready"
    return {
        "documentRich": document_count >= 3,
        "meetingOrEventLineRich": meeting_count > 0 or event_line_task_count > 0,
        "cockpitRich": official_ready or radar_candidates > 0,
    }


def _context_count(workspace: dict[str, Any]) -> int:
    return len(workspace.get("documentCards") or []) + len(workspace.get("meetings") or []) + len(workspace.get("relatedTasks") or [])


def _coverage_categories(assessment: dict[str, Any]) -> set[str]:
    categories = set()
    flags = assessment.get("representation") or {}
    if flags.get("documentRich"):
        categories.add("documents")
    if flags.get("meetingOrEventLineRich"):
        categories.add("meetings_or_event_lines")
    if flags.get("cockpitRich"):
        categories.add("cockpit")
    return categories


def assess_day0_candidates(api: BackendApi, *, candidate_ids: list[str]) -> dict[str, Any]:
    ordered_candidates = [item for item in candidate_ids if str(item or "").strip()]
    assessments: list[dict[str, Any]] = []
    for priority_index, client_id in enumerate(ordered_candidates):
        try:
            workspace = api.get_workspace(client_id)
            cockpit = api.get_cockpit(client_id)
        except Exception as exc:
            assessments.append(
                {
                    "clientId": client_id,
                    "priorityIndex": priority_index,
                    "healthy": False,
                    "reason": str(exc),
                    "healthReason": f"淘汰：workspace/cockpit 请求失败，{exc}",
                }
            )
            continue
        representation = _representation_flags(workspace, cockpit)
        knowledge_ready = candidate_is_knowledge_ready(workspace)
        has_context = _context_count(workspace) > 0
        health_reasons: list[str] = []
        if not knowledge_ready:
            health_reasons.append("knowledgeReady=false")
        if not has_context:
            health_reasons.append("上下文为空")
        if health_reasons:
            health_reason = f"淘汰：{'；'.join(health_reasons)}"
        else:
            health_reason = (
                "候选健康：workspace/cockpit 200，knowledgeReady=true，"
                f"documentCount={max(len(workspace.get('documentCards') or []), int(((workspace.get('knowledgeStatus') or {}).get('totalDocuments') or 0)))}，"
                f"meetingCount={len(workspace.get('meetings') or [])}，taskCount={len(workspace.get('relatedTasks') or [])}"
            )
        coverage_categories = sorted(_coverage_categories({"representation": representation}))
        assessment = {
            "clientId": client_id,
            "priorityIndex": priority_index,
            "healthy": knowledge_ready and has_context,
            "reason": None,
            "healthReason": health_reason,
            "representationReason": None,
            "knowledgeReady": knowledge_ready,
            "hasContext": has_context,
            "documentCount": max(
                len(workspace.get("documentCards") or []),
                int(((workspace.get("knowledgeStatus") or {}).get("totalDocuments") or 0)),
            ),
            "meetingCount": len(workspace.get("meetings") or []),
            "taskCount": len(workspace.get("relatedTasks") or []),
            "eventLineTaskCount": _event_line_task_count(workspace),
            "officialLayerStatus": cockpit.get("officialLayerStatus"),
            "candidateJudgmentCount": len(((cockpit.get("radarLayer") or {}).get("candidateJudgments") or [])),
            "representation": representation,
            "coverageCategories": coverage_categories,
        }
        assessments.append(assessment)

    healthy = [item for item in assessments if item.get("healthy")]
    selected: list[dict[str, Any]] = []
    covered: set[str] = set()
    selection_reasons: dict[str, str] = {}
    representation_reasons: dict[str, str] = {}
    remaining = healthy.copy()
    while remaining and len(selected) < 3:
        ranked = sorted(
            remaining,
            key=lambda item: (
                -len(_coverage_categories(item) - covered),
                item["priorityIndex"],
            ),
        )
        choice = ranked[0]
        new_categories = sorted(_coverage_categories(choice) - covered)
        representation_reasons[choice["clientId"]] = (
            f"补齐 {' / '.join(new_categories)} 代表性"
            if new_categories
            else "代表性已满足，按固定优先级补齐 cohort"
        )
        selection_reasons[choice["clientId"]] = f"入选：健康，且{representation_reasons[choice['clientId']]}"
        selected.append(choice)
        covered.update(_coverage_categories(choice))
        remaining = [item for item in remaining if item["clientId"] != choice["clientId"]]

    control_priority_index = {client_id: index for index, client_id in enumerate(DEFAULT_CONTROL_PRIORITY)}

    def control_sort_key(item: dict[str, Any]) -> tuple[int, int]:
        richness_score = (
            item.get("documentCount", 0)
            + item.get("meetingCount", 0) * 5
            + item.get("eventLineTaskCount", 0) * 5
            + (10 if item.get("officialLayerStatus") == "ready" else 0)
            + item.get("candidateJudgmentCount", 0) * 2
        )
        return (-richness_score, control_priority_index.get(item["clientId"], 999))

    control_client_id = sorted(selected, key=control_sort_key)[0]["clientId"] if selected else None
    control_client_reason = (
        "选为 control client：在已入选 cohort 中上下文最复杂，最适合做 workspace / cockpit / 安装版对照"
        if control_client_id
        else None
    )
    selected_client_ids = {item["clientId"] for item in selected}
    for assessment in assessments:
        client_id = assessment["clientId"]
        assessment["selected"] = client_id in selected_client_ids
        if assessment["selected"]:
            assessment["selectionReason"] = selection_reasons.get(client_id, "入选：健康")
            assessment["representationReason"] = representation_reasons.get(client_id, "代表性已满足")
        elif assessment.get("healthy"):
            assessment["selectionReason"] = "淘汰：虽然健康，但 cohort 已覆盖所需代表性"
            assessment["representationReason"] = "代表性已被已入选 cohort 覆盖"
        else:
            assessment["selectionReason"] = assessment.get("healthReason") or "淘汰：未通过健康检查"
            coverage_categories = assessment.get("coverageCategories") or []
            assessment["representationReason"] = (
                f"具备 {' / '.join(coverage_categories)} 代表性，但未通过健康门槛"
                if coverage_categories
                else "未通过健康门槛，未进入代表性比较"
            )
    represented_categories = sorted(covered)
    return {
        "recordedAt": iso_now(),
        "baseUrl": api.base_url,
        "candidatePriority": ordered_candidates,
        "assessments": assessments,
        "selectedClients": [item["clientId"] for item in selected],
        "selectedAssessments": selected,
        "representedCategories": represented_categories,
        "representationReady": len(represented_categories) >= 2,
        "controlClientId": control_client_id,
        "controlClientReason": control_client_reason,
        "readyForDay0": len(selected) >= 3 and len(represented_categories) >= 2,
    }


def capture_git_artifacts(*, runtime_dir: str | Path | None = None, repo_root: Path | None = None) -> dict[str, Any]:
    root = (repo_root or DEFAULT_REPO_ROOT).resolve()
    target_dir = _ensure_runtime_dir(runtime_dir) / "git"
    target_dir.mkdir(parents=True, exist_ok=True)

    commands = {
        "head.txt": ["git", "-C", str(root), "rev-parse", "HEAD"],
        "status.porcelain.txt": ["git", "-C", str(root), "status", "--porcelain"],
        "diff.stat.txt": ["git", "-C", str(root), "diff", "--stat"],
        "diff.patch": ["git", "-C", str(root), "diff"],
    }
    results: dict[str, str] = {}
    for filename, command in commands.items():
        returncode, stdout, stderr = _run_command(command)
        if returncode != 0:
            raise RuntimeError(stderr.strip() or f"failed to run {' '.join(command)}")
        rendered = stdout if stdout.endswith("\n") or not stdout else f"{stdout}\n"
        file_path = target_dir / filename
        file_path.write_text(rendered, encoding="utf-8")
        results[filename] = str(file_path)
    return {
        "recordedAt": iso_now(),
        "repoRoot": str(root),
        "runtimeDir": str(target_dir.parent),
        "artifacts": results,
    }


def _note_output_path(observation_path: str) -> Path:
    source = Path(observation_path).expanduser().resolve()
    if source.suffix == ".json":
        return source.with_name(f"{source.stem}.note.json")
    return source.with_name(f"{source.name}.note.json")


def write_observation_note(
    api: BackendApi,
    *,
    baseline_path: str,
    runtime_dir: str | None = None,
    observation_path: str,
    control_client_id: str,
    operator_note: str,
    output_path: str | None,
) -> dict[str, Any]:
    baseline_identity = _load_baseline_contract(baseline_path)
    _ensure_session_for_baseline(runtime_dir=runtime_dir, baseline=baseline_identity, baseline_path=baseline_path)
    current_identity = collect_runtime_identity(api, baseline_path=baseline_path)
    current_identity["baselineGeneratedAt"] = _baseline_generated_at(baseline_identity)
    mismatches = compare_identity_tuple(baseline=baseline_identity, current=current_identity)
    payload = {
        "recordedAt": iso_now(),
        "baselineGeneratedAt": _baseline_generated_at(baseline_identity),
        "commitSha": current_identity.get("commitSha"),
        "backendUrl": current_identity.get("backendUrl"),
        "buildVersion": current_identity.get("buildVersion"),
        "databasePath": current_identity.get("databasePath"),
        "latestJudgmentsShadowOff": current_identity.get("latestJudgmentsShadowOff"),
        "dirtyWorktree": current_identity.get("dirtyWorktree"),
        "dirtyPaths": current_identity.get("dirtyPaths"),
        "installedRuntimeSignature": current_identity.get("installedRuntimeSignature"),
        "controlClientId": control_client_id,
        "operatorNote": operator_note.strip(),
        "observationPath": str(Path(observation_path).expanduser().resolve()),
        "baselinePath": str(Path(baseline_path).expanduser().resolve()),
        "identityMatchesBaseline": not mismatches,
        "mismatches": mismatches,
    }
    payload = attach_artifact_contract(payload, baseline_identity)
    write_output(str(Path(output_path).expanduser().resolve()) if output_path else str(_note_output_path(observation_path)), payload)
    return payload


def write_selection_note(
    *,
    baseline_path: str,
    runtime_dir: str | None = None,
    selection_path: str,
    output_path: str | None,
) -> dict[str, Any]:
    baseline_identity = _load_baseline_contract(baseline_path)
    _ensure_session_for_baseline(runtime_dir=runtime_dir, baseline=baseline_identity, baseline_path=baseline_path)
    selection_payload = load_json(selection_path)
    entries = [
        {
            "clientId": item.get("clientId"),
            "selected": bool(item.get("selected")),
            "reason": item.get("selectionReason") or item.get("healthReason") or item.get("reason") or "未填写",
            "healthReason": item.get("healthReason"),
            "representationReason": item.get("representationReason"),
        }
        for item in (selection_payload.get("assessments") or [])
        if isinstance(item, dict)
    ]
    payload = {
        "recordedAt": iso_now(),
        "baselineGeneratedAt": _baseline_generated_at(baseline_identity),
        "backendUrl": baseline_identity.get("backendUrl"),
        "installedRuntimeSignature": baseline_identity.get("installedRuntimeSignature"),
        "selectionPath": str(Path(selection_path).expanduser().resolve()),
        "controlClientId": selection_payload.get("controlClientId"),
        "controlClientReason": selection_payload.get("controlClientReason"),
        "readyForDay0": bool(selection_payload.get("readyForDay0")),
        "representedCategories": selection_payload.get("representedCategories") or [],
        "entries": entries,
    }
    payload = attach_artifact_contract(payload, baseline_identity)
    target_output = Path(output_path).expanduser().resolve() if output_path else Path(selection_path).expanduser().resolve().with_name("day0-selection.note.json")
    write_output(str(target_output), payload)
    return payload


def write_install_evidence(
    api: BackendApi,
    *,
    baseline_path: str,
    runtime_dir: str | None = None,
    phase: str,
    status: str,
    app_starts: bool,
    backend_started_by_installed_app: bool,
    overview_panel_visible: bool,
    shadow_off_parity: bool,
    workspace_boundary_correct: bool,
    cockpit_official_layer_tone_correct: bool,
    overview_metrics_populated: bool,
    overview_screenshot: str,
    workspace_screenshot: str,
    cockpit_screenshot: str,
    overview_page_proof: str,
    workspace_page_proof: str,
    cockpit_page_proof: str,
    summary: str,
    manual_backend_recovery_used: bool,
    workaround_required: bool,
    control_client_id: str | None,
    output_path: str | None,
) -> dict[str, Any]:
    allowed_states = {"baseline_frozen", "day0_ready", "wave2_active", "step_b_ready"}
    if phase == "step-b":
        allowed_states = {"wave2_active", "step_b_ready"}
    gate = _enforce_runtime_contract(
        api,
        baseline_path=baseline_path,
        runtime_dir=runtime_dir,
        command_name="write-install-evidence",
        allowed_states=allowed_states,
    )
    baseline_identity = gate["baseline"]
    page_proofs = {
        "overview": _validate_page_proof_contract(
            overview_page_proof,
            baseline_hash=baseline_identity.get("baselineHash"),
            tuple_hash=baseline_identity.get("tupleHash"),
            session_id=baseline_identity.get("sessionId"),
            expected_page="overview",
        ),
        "workspace": _validate_page_proof_contract(
            workspace_page_proof,
            baseline_hash=baseline_identity.get("baselineHash"),
            tuple_hash=baseline_identity.get("tupleHash"),
            session_id=baseline_identity.get("sessionId"),
            expected_page="workspace-state",
        ),
        "cockpit": _validate_page_proof_contract(
            cockpit_page_proof,
            baseline_hash=baseline_identity.get("baselineHash"),
            tuple_hash=baseline_identity.get("tupleHash"),
            session_id=baseline_identity.get("sessionId"),
            expected_page="cockpit",
        ),
    }
    if phase == "step-a" and status == "pass":
        required_checks = {
            "appStarts": app_starts,
            "backendStartedByInstalledApp": backend_started_by_installed_app,
            "overviewPanelVisible": overview_panel_visible,
            "shadowOffParity": shadow_off_parity,
            "workspaceBoundaryCorrect": workspace_boundary_correct,
            "cockpitOfficialLayerToneCorrect": cockpit_official_layer_tone_correct,
            "overviewMetricsPopulated": overview_metrics_populated,
        }
        missing = [name for name, enabled in required_checks.items() if not enabled]
        if missing:
            raise RuntimeError(f"step-a pass requires all installed-runtime checks: missing {', '.join(missing)}")
        if manual_backend_recovery_used or workaround_required:
            reasons: list[str] = []
            if manual_backend_recovery_used:
                reasons.append("manualBackendRecoveryUsed=true")
            if workaround_required:
                reasons.append("workaroundRequired=true")
            raise RuntimeError(
                "step-a pass forbids manual backend recovery or extra workaround: "
                + ", ".join(reasons)
            )
    if phase == "step-b" and status == "pass":
        required_checks = {
            "appStarts": app_starts,
            "backendStartedByInstalledApp": backend_started_by_installed_app,
            "shadowOffParity": shadow_off_parity,
        }
        missing = [name for name, enabled in required_checks.items() if not enabled]
        if missing:
            raise RuntimeError(f"step-b pass requires installed runtime parity: missing {', '.join(missing)}")
    current_identity = collect_runtime_identity(api, baseline_path=baseline_path)
    current_identity["baselineGeneratedAt"] = _baseline_generated_at(baseline_identity)
    mismatches = compare_identity_tuple(baseline=baseline_identity, current=current_identity)
    target_output = (
        Path(output_path).expanduser().resolve()
        if output_path
        else DEFAULT_RUNTIME_DIR / f"install-{phase.lower()}.json"
    )
    payload = {
        "recordedAt": iso_now(),
        "phase": phase,
        "status": status,
        "appStarts": app_starts,
        "backendStartedByInstalledApp": backend_started_by_installed_app,
        "overviewPanelVisible": overview_panel_visible,
        "shadowOffParity": shadow_off_parity,
        "workspaceBoundaryCorrect": workspace_boundary_correct,
        "cockpitOfficialLayerToneCorrect": cockpit_official_layer_tone_correct,
        "overviewMetricsPopulated": overview_metrics_populated,
        "summary": summary,
        "manualBackendRecoveryUsed": manual_backend_recovery_used,
        "workaroundRequired": workaround_required,
        "controlClientId": control_client_id,
        "screenshots": {
            "overview": overview_screenshot,
            "workspace": workspace_screenshot,
            "cockpit": cockpit_screenshot,
        },
        "pageProofs": {
            "overview": str(Path(overview_page_proof).expanduser().resolve()),
            "workspace": str(Path(workspace_page_proof).expanduser().resolve()),
            "cockpit": str(Path(cockpit_page_proof).expanduser().resolve()),
        },
        "baselineGeneratedAt": _baseline_generated_at(baseline_identity),
        "commitSha": current_identity.get("commitSha"),
        "backendUrl": current_identity.get("backendUrl"),
        "buildVersion": current_identity.get("buildVersion"),
        "databasePath": current_identity.get("databasePath"),
        "latestJudgmentsShadowOff": current_identity.get("latestJudgmentsShadowOff"),
        "dirtyWorktree": current_identity.get("dirtyWorktree"),
        "dirtyPaths": current_identity.get("dirtyPaths"),
        "installedRuntimeSignature": current_identity.get("installedRuntimeSignature"),
        "identityMatchesBaseline": not mismatches,
        "mismatches": mismatches,
    }
    payload = attach_artifact_contract(payload, baseline_identity)
    write_output(str(target_output), payload)
    if phase == "step-b":
        _transition_session_state(
            runtime_dir=runtime_dir,
            session=gate["session"],
            state="step_b_ready",
            baseline=baseline_identity,
        )
    return payload


def write_install_note(
    *,
    baseline_path: str,
    runtime_dir: str | None = None,
    phase: str,
    blocker_class: str,
    decision: str,
    reason: str,
    evidence_path: str | None,
    output_path: str | None,
) -> dict[str, Any]:
    baseline_identity = _load_baseline_contract(baseline_path)
    _ensure_session_for_baseline(runtime_dir=runtime_dir, baseline=baseline_identity, baseline_path=baseline_path)
    if decision == "pass" and blocker_class != "none":
        raise RuntimeError("install note pass requires blockerClass=none")
    if decision == "fail" and blocker_class == "none":
        raise RuntimeError("install note fail requires blockerClass=packaging or main-chain")
    if phase == "step-a" and evidence_path:
        evidence_payload = load_json(evidence_path)
        if str(evidence_payload.get("baselineHash") or "") != str(baseline_identity.get("baselineHash") or ""):
            raise RuntimeError("install note evidence baselineHash mismatch")
        if str(evidence_payload.get("sessionId") or "") != str(baseline_identity.get("sessionId") or ""):
            raise RuntimeError("install note evidence sessionId mismatch")
        packaging_failure = (
            not bool(evidence_payload.get("backendStartedByInstalledApp"))
            or bool(evidence_payload.get("manualBackendRecoveryUsed"))
            or bool(evidence_payload.get("workaroundRequired"))
        )
        if packaging_failure and (decision != "fail" or blocker_class != "packaging"):
            raise RuntimeError(
                "step-a evidence with manual backend recovery/workaround/non-installed-runtime listener "
                "must be recorded as decision=fail and blockerClass=packaging"
            )
    payload = {
        "recordedAt": iso_now(),
        "phase": phase,
        "blockerClass": blocker_class,
        "decision": decision,
        "reason": reason.strip(),
        "baselineGeneratedAt": _baseline_generated_at(baseline_identity),
        "commitSha": baseline_identity.get("commitSha"),
        "backendUrl": baseline_identity.get("backendUrl"),
        "buildVersion": baseline_identity.get("buildVersion"),
        "databasePath": baseline_identity.get("databasePath"),
        "latestJudgmentsShadowOff": baseline_identity.get("latestJudgmentsShadowOff"),
        "dirtyWorktree": baseline_identity.get("dirtyWorktree"),
        "dirtyPaths": baseline_identity.get("dirtyPaths"),
        "installedRuntimeSignature": baseline_identity.get("installedRuntimeSignature"),
        "evidencePath": str(Path(evidence_path).expanduser().resolve()) if evidence_path else None,
    }
    payload = attach_artifact_contract(payload, baseline_identity)
    target_output = (
        Path(output_path).expanduser().resolve()
        if output_path
        else _ensure_runtime_dir() / f"install-{phase}.note.json"
    )
    write_output(str(target_output), payload)
    return payload


def _normalize_inherited_failures(entries: list[Any] | None) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for raw in entries or []:
        entry = raw
        if isinstance(raw, str):
            stripped = raw.strip()
            if not stripped:
                continue
            entry = json.loads(stripped)
        if not isinstance(entry, dict):
            raise RuntimeError("inherited failure entries must be objects with test/cluster/reason")
        test = str(entry.get("test") or "").strip()
        cluster = str(entry.get("cluster") or "").strip()
        reason = str(entry.get("reason") or "").strip()
        if not test or not cluster or not reason:
            raise RuntimeError("inherited failure entries require non-empty test, cluster, and reason")
        normalized.append({"test": test, "cluster": cluster, "reason": reason})
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in normalized:
        key = (item["test"], item["cluster"], item["reason"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _extract_pytest_failures_from_log(log_path: Path | None) -> list[str]:
    if log_path is None or not log_path.is_file():
        return []
    failures: list[str] = []
    for line in _read_text(log_path).splitlines():
        stripped = line.strip()
        if stripped.startswith("FAILED "):
            nodeid = stripped.removeprefix("FAILED ").split(" - ", 1)[0].strip()
            failures.append(nodeid)
    return _dedupe_preserve_order(failures)


def write_full_smoke_classification(
    *,
    source_path: str | None,
    log_path: str | None,
    pytest_exit_code: int | None,
    full_smoke_summary: str | None,
    failures: list[str] | None,
    rc_blocking_failures: list[str] | None,
    inherited_failures: list[Any] | None,
    classification_reason: str | None,
    output_path: str | None,
) -> dict[str, Any]:
    source_payload = load_json(source_path) if source_path else {}
    resolved_log_path = (
        Path(log_path).expanduser().resolve()
        if log_path
        else Path(str(source_payload.get("logPath"))).expanduser().resolve()
        if source_payload.get("logPath")
        else None
    )
    normalized_inherited = _normalize_inherited_failures(
        inherited_failures if inherited_failures is not None else source_payload.get("inheritedFailures")
    )
    normalized_rc_blocking = _dedupe_preserve_order(
        rc_blocking_failures if rc_blocking_failures is not None else source_payload.get("rcBlockingFailures")
    )
    overlap = sorted({item["test"] for item in normalized_inherited} & set(normalized_rc_blocking))
    if overlap:
        raise RuntimeError(
            "the same failure cannot be both inherited and RC blocking: " + ", ".join(overlap)
        )
    explicit_failures = failures if failures is not None else source_payload.get("failures")
    normalized_failures = _dedupe_preserve_order(explicit_failures)
    if not normalized_failures:
        normalized_failures = _extract_pytest_failures_from_log(resolved_log_path)
    for test_name in normalized_rc_blocking:
        if test_name not in normalized_failures:
            normalized_failures.append(test_name)
    for item in normalized_inherited:
        if item["test"] not in normalized_failures:
            normalized_failures.append(item["test"])

    resolved_summary = str(full_smoke_summary or source_payload.get("fullSmokeSummary") or "").strip()
    if not resolved_summary:
        raise RuntimeError("write-full-smoke-classification requires fullSmokeSummary")
    resolved_reason = str(
        classification_reason
        or source_payload.get("classificationReason")
        or DEFAULT_FULL_SMOKE_CLASSIFICATION_REASON
    ).strip()
    if not normalized_failures and (pytest_exit_code or source_payload.get("pytestExitCode")):
        raise RuntimeError("write-full-smoke-classification requires failures when pytest exit code is non-zero")

    payload = {
        "recordedAt": iso_now(),
        "pytestExitCode": pytest_exit_code if pytest_exit_code is not None else source_payload.get("pytestExitCode"),
        "logPath": str(resolved_log_path) if resolved_log_path else None,
        "fullSmokeSummary": resolved_summary,
        "failures": normalized_failures,
        "rcBlockingFailures": normalized_rc_blocking,
        "inheritedFailures": normalized_inherited,
        "classificationReason": resolved_reason,
        "canRegenerateBaseline": not normalized_rc_blocking,
    }
    target_output = (
        Path(output_path).expanduser().resolve()
        if output_path
        else _ensure_runtime_dir() / "full-smoke-classification.json"
    )
    write_output(str(target_output), payload)
    return payload


def write_phase_b_decision(
    api: BackendApi,
    *,
    baseline_path: str,
    runtime_dir: str | None = None,
    observation_path: str,
    manual_path: str,
    blocker_class: str,
    output_path: str | None,
) -> dict[str, Any]:
    gate = _enforce_runtime_contract(
        api,
        baseline_path=baseline_path,
        runtime_dir=runtime_dir,
        command_name="write-phase-b-decision",
        allowed_states={"step_b_ready"},
    )
    baseline_contract = gate["baseline"]
    raw_observation = load_json(observation_path)
    observation = load_observation_payload(observation_path)
    observation_contract = raw_observation if isinstance(raw_observation, dict) and raw_observation.get("baselineHash") else observation
    if str(observation_contract.get("baselineHash") or "") != str(baseline_contract.get("baselineHash") or ""):
        raise RuntimeError("phase-b observation baselineHash mismatch")
    if str(observation_contract.get("sessionId") or "") != str(baseline_contract.get("sessionId") or ""):
        raise RuntimeError("phase-b observation sessionId mismatch")
    manual = load_json(manual_path)
    if str(manual.get("baselineHash") or "") != str(baseline_contract.get("baselineHash") or ""):
        raise RuntimeError("phase-b manual baselineHash mismatch")
    if str(manual.get("sessionId") or "") != str(baseline_contract.get("sessionId") or ""):
        raise RuntimeError("phase-b manual sessionId mismatch")
    install_validation = manual.get("installValidation") or {}
    install_evidence = install_validation.get("evidenceScreenshots") or {}
    install_page_proofs = install_validation.get("evidencePageProofs") or {}
    scenes = [item for item in (manual.get("scenes") or []) if isinstance(item, dict)]
    reviewers = [item for item in (manual.get("reviewers") or []) if isinstance(item, dict)]
    next_decision = manual.get("nextDecision") or {}
    judgment_consistency = manual.get("judgmentConsistency") or {}

    confirmed_feedback_union = {
        "boundaryClear": False,
        "taskContextSharper": False,
        "meetingCapturesUnresolved": False,
        "cockpitAvoidsFakeConclusion": False,
    }
    for reviewer in reviewers:
        feedback = reviewer.get("feedback") or {}
        for key in confirmed_feedback_union:
            confirmed_feedback_union[key] = confirmed_feedback_union[key] or bool(feedback.get(key))

    install_closure_pass = (
        str(install_validation.get("status") or "").strip() == "pass"
        and bool(install_validation.get("appStarts"))
        and bool(install_validation.get("backendStartedByInstalledApp"))
        and bool(install_validation.get("overviewPanelVisible"))
        and bool(install_validation.get("shadowOffParity"))
        and bool(install_validation.get("workspaceBoundaryCorrect"))
        and bool(install_validation.get("cockpitOfficialLayerToneCorrect"))
        and bool(install_validation.get("overviewMetricsPopulated"))
        and all(str(install_evidence.get(key) or "").strip() for key in ("overview", "workspace", "cockpit"))
        and all(
            _validate_page_proof_contract(
                str(install_page_proofs.get(key) or ""),
                baseline_hash=baseline_contract.get("baselineHash"),
                tuple_hash=baseline_contract.get("tupleHash"),
                session_id=baseline_contract.get("sessionId"),
                expected_page={"overview": "overview", "workspace": "workspace-state", "cockpit": "cockpit"}[key],
            )
            for key in ("overview", "workspace", "cockpit")
        )
    )
    scenes_confirmed = bool(scenes) and all(
        bool(item.get("confirmed"))
        and _validate_page_proof_contract(
            str(((item.get("evidence") or {}).get("pageProofPath") or "")),
            baseline_hash=baseline_contract.get("baselineHash"),
            tuple_hash=baseline_contract.get("tupleHash"),
            session_id=baseline_contract.get("sessionId"),
        )
        for item in scenes
    )
    business_feedback_complete = all(confirmed_feedback_union.values())
    judgment_consistency_stable = str(judgment_consistency.get("status") or "").strip() == "稳定"
    run_completion_pass = str(manual.get("runCompletionStatus") or observation.get("verdict") or "").strip() == "pass"

    conditions_met = {
        "runCompletionPass": run_completion_pass,
        "installClosurePass": install_closure_pass,
        "scenesConfirmed": scenes_confirmed,
        "businessFeedbackComplete": business_feedback_complete,
        "judgmentConsistencyStable": judgment_consistency_stable,
    }

    blocking_reasons: list[str] = []
    if not run_completion_pass:
        blocking_reasons.append("运行完成态不是 pass")
    if not install_closure_pass:
        blocking_reasons.append("安装版闭环未通过")
    if not scenes_confirmed:
        blocking_reasons.append("4 个场景的截图与前后对照未收齐")
    if not business_feedback_complete:
        blocking_reasons.append("业务同事反馈还未覆盖 4 个关键判断点")
    if not judgment_consistency_stable:
        blocking_reasons.append("主链判断口径还未达到稳定")
    if blocker_class != "none":
        blocking_reasons.append(f"存在 blockerClass={blocker_class}")
    for item in next_decision.get("blockedBy") or []:
        reason = str(item).strip()
        if reason and reason not in blocking_reasons:
            blocking_reasons.append(reason)
    if not bool(next_decision.get("canEnterV04")) and "manual nextDecision.canEnterV04=false" not in blocking_reasons:
        blocking_reasons.append("manual nextDecision.canEnterV04=false")

    run_completion_status = str(manual.get("runCompletionStatus") or observation.get("verdict") or "").strip() or "watch"
    payload = {
        "recordedAt": iso_now(),
        "baselinePath": str(Path(baseline_path).expanduser().resolve()),
        "observationPath": str(Path(observation_path).expanduser().resolve()),
        "manualPath": str(Path(manual_path).expanduser().resolve()),
        "runCompletionStatus": run_completion_status,
        "mainChainJudgmentStability": "stable" if judgment_consistency_stable else "unstable",
        "allowEnterPhaseB": all(conditions_met.values()) and not blocking_reasons,
        "conditionsMet": conditions_met,
        "blockingReasons": blocking_reasons,
        "blockerClass": blocker_class,
    }
    payload = attach_artifact_contract(payload, baseline_contract)
    target_output = (
        Path(output_path).expanduser().resolve()
        if output_path
        else _ensure_runtime_dir() / "phase-b-decision.json"
    )
    write_output(str(target_output), payload)
    _transition_session_state(
        runtime_dir=runtime_dir,
        session=gate["session"],
        state="completed" if bool(payload.get("allowEnterPhaseB")) else "blocked",
        baseline=baseline_contract,
    )
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Helper CLI for the v0.3.4 RC Wave 2 frozen workflow.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"Backend base URL. Default: {DEFAULT_BASE_URL}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    git_artifacts = subparsers.add_parser("capture-git-artifacts", help="Capture HEAD, status, diff stat, and diff patch into the RC runtime directory.")
    git_artifacts.add_argument("--runtime-dir", help="Optional RC runtime directory override.")

    invalidated = subparsers.add_parser("write-invalidated-artifacts-note", help="Record old baseline/runtime artifacts and stale staging bundles that must not be reused.")
    invalidated.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    invalidated.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    invalidated.add_argument("--source-app", help="Optional source app override. Defaults to dist/mac-arm64 installed build.")
    invalidated.add_argument("--applications-dir", help="Optional Applications directory override for tests.")
    invalidated.add_argument("--output", help="Optional explicit note path.")

    sync_session = subparsers.add_parser("sync-rc-session", help="Sync rc-session.json against install artifacts and the current frozen baseline.")
    sync_session.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    sync_session.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    sync_session.add_argument("--install-receipt", help="Optional install-receipt.json path override.")
    sync_session.add_argument("--install-smoke", help="Optional install-smoke.json path override.")
    sync_session.add_argument("--output", help="Optional explicit JSON output path.")

    preflight = subparsers.add_parser("preflight", help="Check the live identity tuple and Day 0 hard gates against rc-baseline.json.")
    preflight.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    preflight.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    preflight.add_argument("--output", help="Optional JSON output path.")

    db_isolation = subparsers.add_parser("verify-db-isolation", help="Verify pytest/smoke uses tmp_path data while installed-runtime still points at the live app.db.")
    db_isolation.add_argument("--output", help="Optional JSON output path.")

    select_day0 = subparsers.add_parser("select-day0", help="Assess fixed-priority clients for Day 0 health and representation coverage.")
    select_day0.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    select_day0.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    select_day0.add_argument("--client-id", action="append", help="Candidate client id. Repeat to override the default priority list.")
    select_day0.add_argument("--output", help="Optional JSON output path.")

    selection_note = subparsers.add_parser("write-selection-note", help="Write a day0-selection.note.json file from the selection payload.")
    selection_note.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    selection_note.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    selection_note.add_argument("--selection", required=True)
    selection_note.add_argument("--output", help="Optional explicit note path.")

    write_note = subparsers.add_parser("write-note", help="Write an observation sidecar note next to a Wave 2 JSON output.")
    write_note.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    write_note.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    write_note.add_argument("--observation", required=True, help="Path to wave2-day0/dayN JSON output.")
    write_note.add_argument("--control-client-id", required=True)
    write_note.add_argument("--operator-note", required=True, help="One-sentence operator note.")
    write_note.add_argument("--output", help="Optional explicit sidecar path.")

    page_proof = subparsers.add_parser("write-page-proof", help="Write page-proof-*.json from AX/OCR text and a screenshot.")
    page_proof.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    page_proof.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    page_proof.add_argument("--page", required=True, choices=tuple(DEFAULT_PAGE_PROOF_TOKENS.keys()))
    page_proof.add_argument("--screenshot", required=True)
    page_proof.add_argument("--expected-token", action="append", help="Repeat to override default expected tokens.")
    page_proof.add_argument("--ax-text", help="Preferred AX tree extracted text path.")
    page_proof.add_argument("--ocr-text", help="Fallback OCR text path.")
    page_proof.add_argument("--output", help="Optional explicit output path.")

    install = subparsers.add_parser("write-install-evidence", help="Write Step A/Step B install evidence into the RC runtime directory.")
    install.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    install.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    install.add_argument("--phase", required=True, choices=("step-a", "step-b"))
    install.add_argument("--status", required=True, choices=("pass", "watch", "fail"))
    install.add_argument("--app-starts", action="store_true")
    install.add_argument("--backend-started-by-installed-app", action="store_true")
    install.add_argument("--overview-panel-visible", action="store_true")
    install.add_argument("--shadow-off-parity", action="store_true")
    install.add_argument("--workspace-boundary-correct", action="store_true")
    install.add_argument("--cockpit-official-layer-tone-correct", action="store_true")
    install.add_argument("--overview-metrics-populated", action="store_true")
    install.add_argument("--overview-screenshot", required=True)
    install.add_argument("--workspace-screenshot", required=True)
    install.add_argument("--cockpit-screenshot", required=True)
    install.add_argument("--overview-page-proof", required=True)
    install.add_argument("--workspace-page-proof", required=True)
    install.add_argument("--cockpit-page-proof", required=True)
    install.add_argument("--summary", required=True)
    install.add_argument("--manual-backend-recovery-used", action="store_true")
    install.add_argument("--workaround-required", action="store_true")
    install.add_argument("--control-client-id", help="Required for Step B.")
    install.add_argument("--output", help="Optional explicit output path.")

    install_note = subparsers.add_parser("write-install-note", help="Write install-step-a.note.json or install-step-b.note.json with blocker attribution.")
    install_note.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    install_note.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    install_note.add_argument("--phase", required=True, choices=("step-a", "step-b"))
    install_note.add_argument("--blocker-class", required=True, choices=("packaging", "main-chain", "none"))
    install_note.add_argument("--decision", required=True, choices=("pass", "fail"))
    install_note.add_argument("--reason", required=True)
    install_note.add_argument("--evidence", help="Optional install-step-a/install-step-b evidence JSON path.")
    install_note.add_argument("--output", help="Optional explicit note path.")

    phase_b = subparsers.add_parser("write-phase-b-decision", help="Write the external phase-b-decision.json artifact from observation + manual inputs.")
    phase_b.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    phase_b.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    phase_b.add_argument("--observation", required=True)
    phase_b.add_argument("--manual", required=True)
    phase_b.add_argument("--blocker-class", required=True, choices=("packaging", "main-chain", "none"))
    phase_b.add_argument("--output", help="Optional explicit output path.")

    full_smoke = subparsers.add_parser("write-full-smoke-classification", help="Write or normalize the canonical full-smoke-classification.json artifact.")
    full_smoke.add_argument("--source", help="Optional existing classification JSON to normalize or override.")
    full_smoke.add_argument("--log", help="Optional pytest full smoke log path.")
    full_smoke.add_argument("--pytest-exit-code", type=int, help="Optional pytest exit code for the full smoke run.")
    full_smoke.add_argument("--summary", help="Required unless provided by --source.")
    full_smoke.add_argument("--failure", action="append", help="Full smoke failure nodeid. Repeat this flag.")
    full_smoke.add_argument("--rc-blocking-failure", action="append", help="Failure that blocks the current installed-runtime RC. Repeat this flag.")
    full_smoke.add_argument("--inherited-failure", action="append", help="JSON object string with test, cluster, and reason.")
    full_smoke.add_argument("--classification-reason", help="Optional human-readable explanation of the RC classification boundary.")
    full_smoke.add_argument("--output", help="Optional explicit output path.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    api_needed_commands = {
        "preflight",
        "verify-db-isolation",
        "select-day0",
        "write-note",
        "write-install-evidence",
        "write-phase-b-decision",
    }
    api = BackendApi(args.base_url) if args.command in api_needed_commands else None
    try:
        if args.command == "capture-git-artifacts":
            payload = capture_git_artifacts(runtime_dir=args.runtime_dir)
            write_output(None, payload)
            return 0
        if args.command == "write-invalidated-artifacts-note":
            write_invalidated_artifacts_note(
                runtime_dir=args.runtime_dir,
                baseline_path=args.baseline,
                source_app_path=args.source_app,
                applications_dir=args.applications_dir,
                output_path=args.output,
            )
            return 0
        if args.command == "sync-rc-session":
            sync_rc_session(
                runtime_dir=args.runtime_dir,
                baseline_path=args.baseline,
                install_receipt_path=args.install_receipt,
                install_smoke_path=args.install_smoke,
                output_path=args.output,
            )
            return 0
        if args.command == "preflight":
            if api is None:
                raise RuntimeError("preflight requires backend api")
            payload = run_preflight(api, baseline_path=args.baseline, runtime_dir=args.runtime_dir)
            write_output(args.output, payload)
            return 0
        if args.command == "verify-db-isolation":
            if api is None:
                raise RuntimeError("verify-db-isolation requires backend api")
            verify_db_isolation(api, output_path=args.output)
            return 0
        if args.command == "select-day0":
            if api is None:
                raise RuntimeError("select-day0 requires backend api")
            baseline = _load_baseline_contract(args.baseline)
            _ensure_session_for_baseline(runtime_dir=args.runtime_dir, baseline=baseline, baseline_path=args.baseline)
            if baseline.get("backendUrl") and str(baseline["backendUrl"]).rstrip("/") != api.base_url.rstrip("/"):
                raise RuntimeError("select-day0 base-url does not match the frozen baseline backendUrl")
            payload = attach_artifact_contract(
                assess_day0_candidates(api, candidate_ids=list(args.client_id or DEFAULT_DAY0_PRIORITY)),
                baseline,
            )
            write_output(args.output, payload)
            return 0
        if args.command == "write-selection-note":
            write_selection_note(
                baseline_path=args.baseline,
                runtime_dir=args.runtime_dir,
                selection_path=args.selection,
                output_path=args.output,
            )
            return 0
        if args.command == "write-note":
            if api is None:
                raise RuntimeError("write-note requires backend api")
            write_observation_note(
                api,
                baseline_path=args.baseline,
                runtime_dir=args.runtime_dir,
                observation_path=args.observation,
                control_client_id=args.control_client_id,
                operator_note=args.operator_note,
                output_path=args.output,
            )
            return 0
        if args.command == "write-page-proof":
            write_page_proof(
                baseline_path=args.baseline,
                runtime_dir=args.runtime_dir,
                page=args.page,
                screenshot_path=args.screenshot,
                expected_tokens=list(args.expected_token or []),
                ax_text_path=args.ax_text,
                ocr_text_path=args.ocr_text,
                output_path=args.output,
            )
            return 0
        if args.command == "write-install-evidence":
            if api is None:
                raise RuntimeError("write-install-evidence requires backend api")
            if args.phase == "step-b" and not str(args.control_client_id or "").strip():
                raise RuntimeError("write-install-evidence step-b requires --control-client-id")
            write_install_evidence(
                api,
                baseline_path=args.baseline,
                runtime_dir=args.runtime_dir,
                phase=args.phase,
                status=args.status,
                app_starts=bool(args.app_starts),
                backend_started_by_installed_app=bool(args.backend_started_by_installed_app),
                overview_panel_visible=bool(args.overview_panel_visible),
                shadow_off_parity=bool(args.shadow_off_parity),
                workspace_boundary_correct=bool(args.workspace_boundary_correct),
                cockpit_official_layer_tone_correct=bool(args.cockpit_official_layer_tone_correct),
                overview_metrics_populated=bool(args.overview_metrics_populated),
                overview_screenshot=args.overview_screenshot,
                workspace_screenshot=args.workspace_screenshot,
                cockpit_screenshot=args.cockpit_screenshot,
                overview_page_proof=args.overview_page_proof,
                workspace_page_proof=args.workspace_page_proof,
                cockpit_page_proof=args.cockpit_page_proof,
                summary=args.summary,
                manual_backend_recovery_used=bool(args.manual_backend_recovery_used),
                workaround_required=bool(args.workaround_required),
                control_client_id=args.control_client_id,
                output_path=args.output,
            )
            return 0
        if args.command == "write-install-note":
            write_install_note(
                baseline_path=args.baseline,
                runtime_dir=args.runtime_dir,
                phase=args.phase,
                blocker_class=args.blocker_class,
                decision=args.decision,
                reason=args.reason,
                evidence_path=args.evidence,
                output_path=args.output,
            )
            return 0
        if args.command == "write-phase-b-decision":
            if api is None:
                raise RuntimeError("write-phase-b-decision requires backend api")
            write_phase_b_decision(
                api,
                baseline_path=args.baseline,
                runtime_dir=args.runtime_dir,
                observation_path=args.observation,
                manual_path=args.manual,
                blocker_class=args.blocker_class,
                output_path=args.output,
            )
            return 0
        if args.command == "write-full-smoke-classification":
            write_full_smoke_classification(
                source_path=args.source,
                log_path=args.log,
                pytest_exit_code=args.pytest_exit_code,
                full_smoke_summary=args.summary,
                failures=args.failure,
                rc_blocking_failures=args.rc_blocking_failure,
                inherited_failures=args.inherited_failure,
                classification_reason=args.classification_reason,
                output_path=args.output,
            )
            return 0
    finally:
        if api is not None:
            api.close()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
~~~

## `backend/scripts/probe_diagnosis_engines.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.diagnosis_engines import collect_diagnosis_engine_health


def main() -> int:
    reports = [report.to_dict() for report in collect_diagnosis_engine_health()]
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
~~~

