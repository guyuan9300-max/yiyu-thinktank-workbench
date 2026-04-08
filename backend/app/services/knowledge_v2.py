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
TEXT_EXTENSIONS = {".md", ".txt", ".json", ".csv"}
ARCHIVE_XML_EXTENSIONS = {".pptx", ".xlsx"}
HUMAN_VISIBLE_CATEGORIES = ["财务与筹款", "品牌与传播", "项目与业务", "组织与战略", "其他资料", "战略陪伴"]
EVIDENCE_CATEGORIES = HUMAN_VISIBLE_CATEGORIES[:-1]
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


def detect_category(title: str, text: str) -> tuple[str, str, float]:
    haystack = f"{title}\n{text[:2200]}".lower()
    scores: dict[str, int] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        scores[category] = sum(2 if keyword.lower() in title.lower() else 1 for keyword in keywords if keyword.lower() in haystack)
    best_category = max(scores, key=scores.get) if scores else "其他资料"
    best_score = scores.get(best_category, 0)
    if best_score <= 0:
        return "其他资料", "待人工复核", 0.45
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
    document_count = int(db.scalar("SELECT COUNT(1) AS count FROM v2_documents WHERE client_id = ? AND material_layer = 'evidence'", (client_id,)) or 0)
    v2_background_docs = int(db.scalar("SELECT COUNT(1) AS count FROM v2_documents WHERE client_id = ? AND material_layer = 'background'", (client_id,)) or 0)
    section_count = int(db.scalar("SELECT COUNT(1) AS count FROM v2_sections WHERE v2_document_id IN (SELECT id FROM v2_documents WHERE client_id = ? AND material_layer = 'evidence')", (client_id,)) or 0)
    chunk_count = int(db.scalar("SELECT COUNT(1) AS count FROM v2_chunks WHERE v2_document_id IN (SELECT id FROM v2_documents WHERE client_id = ? AND material_layer = 'evidence')", (client_id,)) or 0)
    failed_count = int(db.scalar("SELECT COUNT(1) AS count FROM v2_documents WHERE client_id = ? AND parse_status != 'ready'", (client_id,)) or 0)
    review_count = int(db.scalar("SELECT COUNT(1) AS count FROM v2_documents WHERE client_id = ? AND classification_confidence < 0.62", (client_id,)) or 0)
    dna_background_docs = int(db.scalar("SELECT COUNT(1) AS count FROM client_dna_documents WHERE client_id = ?", (client_id,)) or 0)
    memory_docs = int(db.scalar("SELECT COUNT(1) AS count FROM knowledge_surrogates WHERE client_id = ? AND source_type = 'memory_answer'", (client_id,)) or 0)
    pending_jobs = int(db.scalar("SELECT COUNT(1) AS count FROM knowledge_jobs WHERE client_id = ? AND status = 'queued'", (client_id,)) or 0)
    running_jobs = int(db.scalar("SELECT COUNT(1) AS count FROM knowledge_jobs WHERE client_id = ? AND status = 'running'", (client_id,)) or 0)
    last_job = db.fetchone("SELECT * FROM knowledge_jobs WHERE client_id = ? ORDER BY created_at DESC LIMIT 1", (client_id,))
    last_status = str(last_job["status"]) if last_job else "idle"
    last_error = str(last_job["last_error"]) if last_job and last_job["last_error"] else None
    last_success_row = db.fetchone(
        """
        SELECT finished_at
        FROM knowledge_jobs
        WHERE client_id = ? AND status = 'completed'
        ORDER BY finished_at DESC
        LIMIT 1
        """,
        (client_id,),
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
    # --- Vector recall from master_index (Qdrant) to boost semantic matches ---
    try:
        from app.services.knowledge_base import search_master_index_qdrant
        qdrant_scores = search_master_index_qdrant(
            data_dir, client_id, prompt,
            limit=96 if strategic_mode else 72,
        )
        # Build a lookup from v2_document_id to scored_doc for boosting
        v2_doc_id_to_idx: dict[str, int] = {}
        for idx, item in enumerate(scored_docs):
            v2_doc_id_to_idx[str(item["row"]["id"])] = idx

        # Qdrant returns master_index entry_ids (midx_xxx), need to map back to v2_documents
        if qdrant_scores:
            master_rows = db.fetchall(
                "SELECT id, surrogate_id, title FROM knowledge_master_index WHERE client_id = ?",
                (client_id,),
            )
            for mrow in master_rows:
                master_id = str(mrow["id"])
                q_score = qdrant_scores.get(master_id, 0.0)
                if q_score < 0.10:
                    continue
                # Find matching v2_document by title
                m_title = str(mrow["title"]).lower()
                for idx, item in enumerate(scored_docs):
                    if str(item["title"]).lower() == m_title:
                        scored_docs[idx]["score"] += q_score * 0.65
                        break
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
