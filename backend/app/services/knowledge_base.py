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
from app.services.embedding_provider import build_embedding_provider
from app.services.retrieval_model_settings import get_retrieval_model_settings, retrieval_embedding_signature

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
    del text
    return False


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
    del title, summary, document_role, folder_category, path
    return 0.0


def intro_chunk_score_adjustment(*, title: str, excerpt: str, section_label: str | None, path: str | None) -> float:
    del title, excerpt, section_label, path
    return 0.0


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


def collection_name(prefix: str, client_id: str, embedding_signature: str | None = None) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", client_id)
    if not embedding_signature:
        return f"{prefix}_{normalized}"
    suffix = hashlib.sha1(embedding_signature.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}_{normalized}_{suffix}"


def legacy_collection_name(prefix: str, client_id: str) -> str:
    return collection_name(prefix, client_id, embedding_signature=None)


def active_collection_name(prefix: str, client_id: str, embedding_signature: str) -> str:
    return collection_name(prefix, client_id, embedding_signature=embedding_signature)


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


def current_embedding_signature(
    data_dir: Path,
    *,
    db: Database | None = None,
    ensure_ready: bool = False,
    ai_service: Any | None = None,
) -> str:
    if db is not None:
        settings = get_retrieval_model_settings(db)
        if ensure_ready:
            embed_texts(["知识底座"], data_dir=data_dir, db=db, ai_service=ai_service)
        return retrieval_embedding_signature(settings)
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


def embed_texts(
    texts: list[str],
    *,
    data_dir: Path,
    db: Database | None = None,
    ai_service: Any | None = None,
) -> tuple[list[list[float]], str]:
    if not texts:
        return [], "hash_fallback"
    if db is not None:
        settings = get_retrieval_model_settings(db)
        provider = build_embedding_provider(settings, ai_service=ai_service)
        vectors, meta = provider.embed_texts(texts)
        _set_embedding_state(
            data_dir,
            mode=meta.provider,
            model=meta.model if meta.model else None,
            error=meta.error,
        )
        return vectors, meta.provider
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


def ensure_qdrant_collection(client: Any, name: str, *, vector_size: int = QDRANT_VECTOR_SIZE) -> None:
    existing = {item.name for item in client.get_collections().collections}
    if name in existing:
        return
    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def ensure_qdrant_collections(
    data_dir: Path,
    client_id: str,
    *,
    embedding_signature: str | None = None,
    vector_size: int = QDRANT_VECTOR_SIZE,
) -> Any | None:
    client = qdrant_client_for(data_dir)
    if client is None:
        return None
    ensure_qdrant_collection(
        client,
        collection_name("master_index", client_id, embedding_signature=embedding_signature),
        vector_size=vector_size,
    )
    ensure_qdrant_collection(
        client,
        collection_name("raw_chunk", client_id, embedding_signature=embedding_signature),
        vector_size=vector_size,
    )
    return client


def qdrant_payload_count(client: Any, name: str) -> int:
    try:
        count_response = client.count(collection_name=name, exact=True)
        return int(count_response.count)
    except Exception:
        return 0


def _resolve_vector_runtime(
    db: Database | None,
    *,
    data_dir: Path,
    client_id: str,
    ai_service: Any | None = None,
) -> tuple[str | None, int]:
    if db is None:
        return None, QDRANT_VECTOR_SIZE
    settings = get_retrieval_model_settings(db)
    signature = retrieval_embedding_signature(settings)
    dimension = int(settings.embeddingDimension or QDRANT_VECTOR_SIZE)
    if dimension <= 0:
        dimension = QDRANT_VECTOR_SIZE
    _ = ai_service
    return signature, dimension


def resolve_vector_collection_names(
    db: Database | None,
    *,
    data_dir: Path,
    client_id: str,
    ai_service: Any | None = None,
) -> dict[str, str]:
    signature, _dimension = _resolve_vector_runtime(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service)
    return {
        "masterActive": collection_name("master_index", client_id, embedding_signature=signature),
        "chunkActive": collection_name("raw_chunk", client_id, embedding_signature=signature),
        "masterLegacy": legacy_collection_name("master_index", client_id),
        "chunkLegacy": legacy_collection_name("raw_chunk", client_id),
        "signature": signature or "",
    }


def _pick_collection_with_fallback(
    client: Any,
    *,
    active_name: str,
    legacy_name: str,
) -> str:
    active_count = qdrant_payload_count(client, active_name)
    if active_count > 0:
        return active_name
    legacy_count = qdrant_payload_count(client, legacy_name)
    if legacy_count > 0:
        return legacy_name
    return active_name


def qdrant_ready(
    data_dir: Path,
    client_id: str,
    *,
    db: Database | None = None,
    ai_service: Any | None = None,
) -> bool:
    client = qdrant_client_for(data_dir)
    if client is None:
        return False
    try:
        signature, dimension = _resolve_vector_runtime(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service)
        ensure_qdrant_collections(
            data_dir,
            client_id,
            embedding_signature=signature,
            vector_size=dimension,
        )
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
    db: Database | None = None,
    ai_service: Any | None = None,
) -> None:
    signature, dimension = _resolve_vector_runtime(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service)
    client = ensure_qdrant_collections(
        data_dir,
        client_id,
        embedding_signature=signature,
        vector_size=dimension,
    )
    if client is None or PointStruct is None:
        return
    vector, _ = embed_texts([searchable_text], data_dir=data_dir, db=db, ai_service=ai_service)
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
        collection_name=collection_name("master_index", client_id, embedding_signature=signature),
        points=[
            PointStruct(
                id=qdrant_point_id("master", entry_id),
                vector=vector[0] if vector else hashed_embedding(searchable_text, size=dimension),
                payload=payload,
            )
        ],
    )


def upsert_chunk_vectors(
    *,
    db: Database,
    data_dir: Path,
    client_id: str,
    knowledge_document_id: str,
    ai_service: Any | None = None,
) -> None:
    signature, dimension = _resolve_vector_runtime(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service)
    client = ensure_qdrant_collections(
        data_dir,
        client_id,
        embedding_signature=signature,
        vector_size=dimension,
    )
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
    vectors, _ = embed_texts(texts, data_dir=data_dir, db=db, ai_service=ai_service)
    points = []
    for index, row in enumerate(rows):
        text = texts[index]
        points.append(
            PointStruct(
                id=qdrant_point_id("chunk", str(row["id"])),
                vector=vectors[index] if index < len(vectors) else hashed_embedding(text, size=dimension),
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
    client.upsert(
        collection_name=collection_name("raw_chunk", client_id, embedding_signature=signature),
        points=points,
    )


def sync_qdrant_for_client(
    db: Database,
    *,
    data_dir: Path,
    client_id: str,
    ai_service: Any | None = None,
) -> None:
    signature, dimension = _resolve_vector_runtime(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service)
    client = ensure_qdrant_collections(
        data_dir,
        client_id,
        embedding_signature=signature,
        vector_size=dimension,
    )
    if client is None:
        return
    current_signature = current_embedding_signature(data_dir, db=db, ensure_ready=True, ai_service=ai_service)
    signature_key = f"knowledge.embedding_signature:{client_id}"
    stored_signature = db.get_setting(signature_key, "")
    master_name = collection_name("master_index", client_id, embedding_signature=signature)
    chunk_name = collection_name("raw_chunk", client_id, embedding_signature=signature)
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
        vectors, _ = embed_texts(texts, data_dir=data_dir, db=db, ai_service=ai_service)
        points = [
            PointStruct(
                id=qdrant_point_id("master", str(row["id"])),
                vector=vectors[index] if index < len(vectors) else hashed_embedding(str(row["searchable_text"]), size=dimension),
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
            upsert_chunk_vectors(
                db=db,
                data_dir=data_dir,
                client_id=client_id,
                knowledge_document_id=str(row["id"]),
                ai_service=ai_service,
            )
    if needs_master_sync or needs_chunk_sync:
        db.set_setting(signature_key, current_signature)


def search_master_index_qdrant(
    data_dir: Path,
    client_id: str,
    prompt: str,
    limit: int = 8,
    *,
    db: Database | None = None,
    ai_service: Any | None = None,
) -> dict[str, float]:
    signature, dimension = _resolve_vector_runtime(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service)
    client = ensure_qdrant_collections(
        data_dir,
        client_id,
        embedding_signature=signature,
        vector_size=dimension,
    )
    if client is None:
        return {}
    vectors, _ = embed_texts([prompt], data_dir=data_dir, db=db, ai_service=ai_service)
    active_name = collection_name("master_index", client_id, embedding_signature=signature)
    legacy_name = legacy_collection_name("master_index", client_id)
    target_collection = _pick_collection_with_fallback(client, active_name=active_name, legacy_name=legacy_name)
    try:
        results = client.search(
            collection_name=target_collection,
            query_vector=vectors[0] if vectors else hashed_embedding(prompt, size=dimension),
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
    *,
    db: Database | None = None,
    ai_service: Any | None = None,
) -> dict[str, float]:
    signature, dimension = _resolve_vector_runtime(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service)
    client = ensure_qdrant_collections(
        data_dir,
        client_id,
        embedding_signature=signature,
        vector_size=dimension,
    )
    if client is None:
        return {}
    scores: dict[str, float] = {}
    vectors, _ = embed_texts([prompt], data_dir=data_dir, db=db, ai_service=ai_service)
    active_name = collection_name("raw_chunk", client_id, embedding_signature=signature)
    legacy_name = legacy_collection_name("raw_chunk", client_id)
    target_collection = _pick_collection_with_fallback(client, active_name=active_name, legacy_name=legacy_name)
    try:
        results = client.search(
            collection_name=target_collection,
            query_vector=vectors[0] if vectors else hashed_embedding(prompt, size=dimension),
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


def reindex_client_vector(
    db: Database,
    *,
    data_dir: Path,
    client_id: str,
    ai_service: Any | None = None,
) -> dict[str, Any]:
    ensure_vector_manifest_schema(db)
    signature, dimension = _resolve_vector_runtime(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service)
    if signature is None:
        signature = current_embedding_signature(data_dir, db=db, ensure_ready=True, ai_service=ai_service)
    names = resolve_vector_collection_names(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service)
    upsert_vector_manifest(
        db,
        client_id=client_id,
        embedding_signature=signature,
        active_collection=names["masterActive"],
        legacy_collection=names["masterLegacy"],
        status="building",
        master_indexed=0,
        chunk_indexed=0,
        error=None,
    )
    client = ensure_qdrant_collections(
        data_dir,
        client_id,
        embedding_signature=signature,
        vector_size=dimension,
    )
    if client is None:
        return {
            "clientId": client_id,
            "embeddingSignature": signature,
            "masterIndexed": 0,
            "chunkIndexed": 0,
            "fallbackUsed": True,
            "status": "failed",
        }
    names = resolve_vector_collection_names(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service)
    sync_qdrant_for_client(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service)
    master_indexed = qdrant_payload_count(client, names["masterActive"])
    chunk_indexed = qdrant_payload_count(client, names["chunkActive"])
    db.set_setting(f"knowledge.active_embedding_signature:{client_id}", signature)
    upsert_vector_manifest(
        db,
        client_id=client_id,
        embedding_signature=signature,
        active_collection=names["masterActive"],
        legacy_collection=names["masterLegacy"],
        status="ready" if (master_indexed + chunk_indexed) > 0 else "stale",
        master_indexed=int(master_indexed),
        chunk_indexed=int(chunk_indexed),
        error=None,
    )
    return {
        "clientId": client_id,
        "embeddingSignature": signature,
        "masterIndexed": int(master_indexed),
        "chunkIndexed": int(chunk_indexed),
        "fallbackUsed": False,
        "status": "completed",
    }


def get_vector_runtime_status(
    db: Database,
    *,
    data_dir: Path,
    client_id: str,
    ai_service: Any | None = None,
) -> dict[str, Any]:
    ensure_vector_manifest_schema(db)
    settings = get_retrieval_model_settings(db)
    signature = retrieval_embedding_signature(settings)
    active_signature = db.get_setting(f"knowledge.active_embedding_signature:{client_id}", "")
    names = resolve_vector_collection_names(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service)
    client = qdrant_client_for(data_dir)
    active_master_count = qdrant_payload_count(client, names["masterActive"]) if client is not None else 0
    active_chunk_count = qdrant_payload_count(client, names["chunkActive"]) if client is not None else 0
    legacy_master_count = qdrant_payload_count(client, names["masterLegacy"]) if client is not None else 0
    legacy_chunk_count = qdrant_payload_count(client, names["chunkLegacy"]) if client is not None else 0
    active_ready = (active_master_count + active_chunk_count) > 0 and active_signature == signature
    if client is None:
        vector_index_status = "failed"
    elif active_ready:
        vector_index_status = "ready"
    elif active_signature != signature:
        vector_index_status = "stale"
    elif (legacy_master_count + legacy_chunk_count) > 0:
        vector_index_status = "stale"
    else:
        vector_index_status = "building"

    provider_error = None
    embedding_status = embedding_backend_status(data_dir)
    if settings.embeddingProvider == "doubao" and ai_service is not None:
        try:
            store = ai_service._store_for("doubao")  # type: ignore[attr-defined]
            has_key = bool(store and str(store.get_api_key() or "").strip())
        except Exception:
            has_key = False
        if not has_key:
            provider_error = "doubao_api_key_missing"
    if provider_error is None:
        provider_error = embedding_status.get("error")

    active_collection = names["masterActive"] if active_ready else (names["masterLegacy"] if legacy_master_count > 0 else names["masterActive"])
    upsert_vector_manifest(
        db,
        client_id=client_id,
        embedding_signature=signature,
        active_collection=names["masterActive"],
        legacy_collection=names["masterLegacy"],
        status=vector_index_status,
        master_indexed=int(active_master_count),
        chunk_indexed=int(active_chunk_count),
        error=provider_error,
    )
    return {
        "embeddingProvider": settings.embeddingProvider,
        "embeddingModel": settings.embeddingModel,
        "embeddingDimension": int(settings.embeddingDimension or QDRANT_VECTOR_SIZE),
        "embeddingSignature": signature,
        "activeVectorCollection": active_collection,
        "vectorIndexStatus": vector_index_status,
        "qdrantReady": client is not None,
        "embeddingMode": settings.embeddingMode,
        "embeddingError": provider_error,
        "routerEnabled": settings.routerEnabled,
        "routerModel": settings.routerModel or None,
        "rerankEnabled": settings.rerankEnabled,
    }


def ensure_vector_manifest_schema(db: Database) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS vector_index_manifests (
            client_id TEXT NOT NULL,
            embedding_signature TEXT NOT NULL,
            active_collection TEXT NOT NULL DEFAULT '',
            legacy_collection TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'stale',
            master_indexed INTEGER NOT NULL DEFAULT 0,
            chunk_indexed INTEGER NOT NULL DEFAULT 0,
            error TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (client_id, embedding_signature)
        )
        """
    )


def upsert_vector_manifest(
    db: Database,
    *,
    client_id: str,
    embedding_signature: str,
    active_collection: str,
    legacy_collection: str,
    status: str,
    master_indexed: int,
    chunk_indexed: int,
    error: str | None,
) -> None:
    ensure_vector_manifest_schema(db)
    db.execute(
        """
        INSERT INTO vector_index_manifests(
            client_id, embedding_signature, active_collection, legacy_collection,
            status, master_indexed, chunk_indexed, error, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(client_id, embedding_signature) DO UPDATE SET
            active_collection = excluded.active_collection,
            legacy_collection = excluded.legacy_collection,
            status = excluded.status,
            master_indexed = excluded.master_indexed,
            chunk_indexed = excluded.chunk_indexed,
            error = excluded.error,
            updated_at = excluded.updated_at
        """,
        (
            client_id,
            embedding_signature,
            active_collection,
            legacy_collection,
            status,
            int(master_indexed),
            int(chunk_indexed),
            error,
            now_iso(),
        ),
    )


def get_vector_index_manifest_status(
    db: Database,
    *,
    data_dir: Path,
    client_id: str,
    ai_service: Any | None = None,
) -> dict[str, Any]:
    runtime = get_vector_runtime_status(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service)
    signature = str(runtime.get("embeddingSignature") or "")
    ensure_vector_manifest_schema(db)
    row = db.fetchone(
        """
        SELECT *
        FROM vector_index_manifests
        WHERE client_id = ? AND embedding_signature = ?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (client_id, signature),
    )
    if row is None:
        return {
            "clientId": client_id,
            "embeddingSignature": signature,
            "activeCollection": runtime.get("activeVectorCollection"),
            "legacyCollection": None,
            "status": runtime.get("vectorIndexStatus", "stale"),
            "masterIndexed": 0,
            "chunkIndexed": 0,
            "error": runtime.get("embeddingError"),
            "updatedAt": now_iso(),
        }
    return {
        "clientId": client_id,
        "embeddingSignature": signature,
        "activeCollection": str(row["active_collection"] or ""),
        "legacyCollection": str(row["legacy_collection"] or "") or None,
        "status": str(row["status"] or runtime.get("vectorIndexStatus") or "stale"),
        "masterIndexed": int(row["master_indexed"] or 0),
        "chunkIndexed": int(row["chunk_indexed"] or 0),
        "error": str(row["error"]) if row["error"] else runtime.get("embeddingError"),
        "updatedAt": str(row["updated_at"] or now_iso()),
    }


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
    def _job_item_labels(row: Any) -> list[str]:
        payload = from_json(str(row["payload_json"] or "{}"), {})
        documents = payload.get("documents") if isinstance(payload, dict) else None
        if not isinstance(documents, list):
            return []
        labels: list[str] = []
        for item in documents:
            if not isinstance(item, dict):
                continue
            label = str(item.get("title") or item.get("originalSourcePath") or item.get("sourcePath") or "").strip()
            if label:
                labels.append(Path(label).name)
        return labels

    def _job_recent_events(job_id: str) -> list[dict[str, Any]]:
        event_rows = db.fetchall(
            """
            SELECT *
            FROM knowledge_job_events
            WHERE job_id = ?
            ORDER BY created_at DESC
            LIMIT 6
            """,
            (job_id,),
        )
        events: list[dict[str, Any]] = []
        for event_row in event_rows:
            detail = from_json(str(event_row["detail_json"] or "{}"), {})
            processed = detail.get("processedItems") if isinstance(detail, dict) else None
            message = str(event_row["message"] or "")
            item_label = message.removeprefix("已处理 ").strip() if message.startswith("已处理 ") else None
            events.append(
                {
                    "level": str(event_row["level"]),
                    "message": message,
                    "processedItems": int(processed) if isinstance(processed, (int, float)) else None,
                    "itemLabel": item_label,
                    "createdAt": str(event_row["created_at"]),
                }
            )
        return events

    def _current_item_label(row: Any, labels: list[str], events: list[dict[str, Any]]) -> str | None:
        status = str(row["status"] or "")
        processed = int(row["processed_items"] or 0)
        total = int(row["total_items"] or 0)
        if status in {"queued", "running"} and labels and processed < len(labels):
            return labels[processed]
        for event in events:
            label = event.get("itemLabel")
            if isinstance(label, str) and label.strip():
                return label.strip()
        if labels and total > 0:
            return labels[min(processed, len(labels) - 1)]
        return None

    return [
        (
            lambda labels, events: {
                "id": str(row["id"]),
                "clientId": str(row["client_id"]),
                "jobType": str(row["job_type"]),
                "status": str(row["status"]),
                "totalItems": int(row["total_items"]),
                "processedItems": int(row["processed_items"]),
                "lastError": str(row["last_error"]) if row["last_error"] else None,
                "currentItemLabel": _current_item_label(row, labels, events),
                "lastEventMessage": events[0]["message"] if events else None,
                "recentEvents": events,
                "queuedItemLabels": labels[:20],
                "createdAt": str(row["created_at"]),
                "startedAt": str(row["started_at"]) if row["started_at"] else None,
                "finishedAt": str(row["finished_at"]) if row["finished_at"] else None,
                "updatedAt": str(row["updated_at"]),
            }
        )(_job_item_labels(row), _job_recent_events(str(row["id"])))
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
                db=db,
            )

        enriched += 1

    return {
        "clientId": client_id,
        "total": len(rows),
        "enriched": enriched,
        "skipped": skipped,
        "failed": failed,
    }
