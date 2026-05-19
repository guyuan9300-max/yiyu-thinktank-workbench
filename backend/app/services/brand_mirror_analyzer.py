"""品牌镜子 LLM 画像生成 (P13-D, 2026-05-20).

输入: brand_official_corpus (官网 + 公众号摘要) + website_audit_snapshots (Lighthouse).
处理: 一次 LLM 调用 (qwen3-vl:32b, 按 memory project_yiyu_model_reuse 必须复用此模型),
     吃下 title + excerpt 列表 + 客观评分, 输出严格 JSON.
输出: 五块 (selfPresentation/blindspots/consistency/mediaCoverage/partners) + 50 词云,
     入库 brand_mirror_snapshots, 同 client_id 历史可对比.
"""
from __future__ import annotations

import json
import logging
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.db import Database

logger = logging.getLogger(__name__)

DEFAULT_WORD_CLOUD_TARGET = 50


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


def _new_id() -> str:
    return "bms_" + secrets.token_hex(5)


def _normalize_excerpt(raw: str, *, limit: int = 260) -> str:
    text = re.sub(r"\s+", " ", (raw or "").strip())
    return text[:limit]


@dataclass(frozen=True)
class BrandMirrorSnapshot:
    snapshot_id: str
    client_id: str
    corpus_doc_count: int
    corpus_char_count: int
    website_audit_id: str | None
    self_presentation: list[dict[str, Any]]
    blindspots: list[dict[str, Any]]
    consistency: str
    media_coverage: list[dict[str, Any]]
    partners: list[dict[str, Any]]
    word_cloud: list[dict[str, Any]]
    llm_model: str
    error: str | None
    created_at: str


def _collect_corpus(db: Database, client_id: str) -> list[dict[str, Any]]:
    """读 brand_official_corpus 全部文档 → (title, source_label, excerpt) list."""
    cur = db.conn.execute(
        """
        SELECT d.id, d.title, d.kind, d.source, d.excerpt, d.path
        FROM documents d
        WHERE d.client_id = ? AND d.content_domain = 'brand_official_corpus'
        ORDER BY d.created_at DESC
        """,
        (client_id,),
    )
    items: list[dict[str, Any]] = []
    for row in cur.fetchall():
        title = str(row[1] or "").strip()
        kind = str(row[2] or "")
        source = str(row[3] or "")
        excerpt = _normalize_excerpt(str(row[4] or ""))
        path = str(row[5] or "")
        if not title or not excerpt:
            continue
        source_label = (
            "微信公众号" if kind == "wechat_excerpt"
            else "百度百科" if "baike.baidu.com" in path
            else "中国发展简报" if "chinadevelopmentbrief" in path
            else "全思案例" if "quansitech" in path
            else "官网"
        )
        items.append({
            "title": title,
            "source_label": source_label,
            "excerpt": excerpt,
        })
    return items


def _build_prompt(
    *, client_name: str, items: list[dict[str, Any]],
    lighthouse: dict[str, Any] | None,
) -> str:
    corpus_lines: list[str] = []
    for index, item in enumerate(items, 1):
        corpus_lines.append(
            f"[{index}] 来源={item['source_label']} | 标题: {item['title']}\n  摘要: {item['excerpt']}"
        )
    corpus_text = "\n".join(corpus_lines)

    lh_text = ""
    if lighthouse:
        scores = lighthouse.get("scores") or {}
        lh_text = (
            "\n\n## 网站客观指标（Lighthouse 评测）\n"
            f"- Performance: {scores.get('performance')}\n"
            f"- Accessibility: {scores.get('accessibility')}\n"
            f"- Best Practices: {scores.get('bestPractices')}\n"
            f"- SEO: {scores.get('seo')}\n"
            f"- 移动端友好: {'是' if lighthouse.get('mobileFriendly') else '否'}\n"
            f"- 站内可下载文档数: {lighthouse.get('downloadableDocsCount', 0)}\n"
        )

    return f"""下面是「{client_name}」的官方语料（共 {len(items)} 篇，含官网内容/媒体报道/微信公众号摘要）。请基于这些语料，输出一份「品牌镜子」结构化报告。

## 任务要求

输出严格 JSON, 含以下六个字段:

1. `self_presentation` (5-7 项): 机构对外**自我表达**的核心主张/叙事关键词. 每项含 label (8-16 字关键词) / score (1-100, 该主张在语料中出现强度) / rationale (30-60 字简述哪些语料支撑).
2. `blindspots` (2-4 项): "机构**疑似想强调但语料里证据弱**"的潜在盲点. 每项含 label / rationale (30-60 字).
3. `consistency` (120-200 字): 机构对外讲述的一致性如何, 不同信源是否口径一致.
4. `media_coverage` (3-5 项): 媒体声音聚类. 每项 source (信源名) / tone (positive/neutral/negative) / summary (40-80 字).
5. `partners` (3-7 项): 出现频次较高的**合作方/捐赠方/项目伙伴**. 每项 name / type (foundation/corporate/government/media/academic 之一) / evidence (引自哪条语料).
6. `word_cloud` (恰好 {DEFAULT_WORD_CLOUD_TARGET} 项): 品牌词云. 每项 word (2-8 字关键词) / weight (1-100, 字号映射) / tone (positive/neutral/negative) / source_diversity (1-5, 出现在几类信源里).

## 硬约束

- 词云必须**恰好 50 项**, 不多不少.
- 所有 tone 字段只能是 positive/neutral/negative 三选一.
- 不要瞎编, 只用语料里出现过的事实和关键词.
- 如果证据不足填某字段, 给空数组/空字符串而不是编造.
- 用中文回答关键词和叙事内容; tone/type 用英文枚举值.

## 语料

{corpus_text}
{lh_text}"""


_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "self_presentation": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "score": {"type": "integer"},
                    "rationale": {"type": "string"},
                },
                "required": ["label", "score", "rationale"],
            },
        },
        "blindspots": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": ["label", "rationale"],
            },
        },
        "consistency": {"type": "string"},
        "media_coverage": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "tone": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["source", "tone", "summary"],
            },
        },
        "partners": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "required": ["name", "type", "evidence"],
            },
        },
        "word_cloud": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "word": {"type": "string"},
                    "weight": {"type": "integer"},
                    "tone": {"type": "string"},
                    "source_diversity": {"type": "integer"},
                },
                "required": ["word", "weight", "tone", "source_diversity"],
            },
        },
    },
    "required": [
        "self_presentation", "blindspots", "consistency",
        "media_coverage", "partners", "word_cloud",
    ],
}


def _coerce_payload(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        # 兜底剥 ```json ... ``` markdown 包裹
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
        return json.loads(text)
    raise ValueError(f"LLM 返回类型异常: {type(raw).__name__}")


def _sanitize_tone(value: Any) -> str:
    v = str(value or "neutral").strip().lower()
    return v if v in ("positive", "negative", "neutral") else "neutral"


def _sanitize_word_cloud(raw: list[Any]) -> list[dict[str, Any]]:
    cloud: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in raw or []:
        if not isinstance(entry, dict):
            continue
        word = str(entry.get("word") or "").strip()
        if not word or word in seen:
            continue
        seen.add(word)
        try:
            weight = max(1, min(100, int(entry.get("weight") or 50)))
        except (ValueError, TypeError):
            weight = 50
        try:
            diversity = max(1, min(5, int(entry.get("source_diversity") or 1)))
        except (ValueError, TypeError):
            diversity = 1
        cloud.append({
            "word": word,
            "weight": weight,
            "tone": _sanitize_tone(entry.get("tone")),
            "sourceDiversity": diversity,
        })
    return cloud


def run_brand_mirror_analysis(
    db: Database,
    ai_service: Any,
    *,
    client_id: str,
    client_name: str,
) -> BrandMirrorSnapshot:
    """同步跑一次画像 (约 30-90 秒) → 入库 → 返回快照."""
    if ai_service is None or not hasattr(ai_service, "_qwen_generate"):
        raise RuntimeError("AI 服务不可用, 无法生成品牌画像")

    items = _collect_corpus(db, client_id)
    if not items:
        raise ValueError(
            f"客户 {client_id} 没有 brand_official_corpus 语料, 请先跑 /brand-mirror/crawl"
        )
    total_chars = sum(len(item["excerpt"]) for item in items)

    # 关联最近一次 Lighthouse 评测 (有则带入)
    lh_cur = db.conn.execute(
        """
        SELECT id, performance, accessibility, best_practices, seo,
               mobile_friendly, downloadable_docs_count
        FROM website_audit_snapshots
        WHERE client_id = ?
        ORDER BY created_at DESC LIMIT 1
        """,
        (client_id,),
    )
    lh_row = lh_cur.fetchone()
    lighthouse_payload: dict[str, Any] | None = None
    website_audit_id: str | None = None
    if lh_row:
        website_audit_id = str(lh_row[0])
        lighthouse_payload = {
            "scores": {
                "performance": lh_row[1],
                "accessibility": lh_row[2],
                "bestPractices": lh_row[3],
                "seo": lh_row[4],
            },
            "mobileFriendly": bool(lh_row[5]),
            "downloadableDocsCount": lh_row[6],
        }

    prompt = _build_prompt(
        client_name=client_name,
        items=items,
        lighthouse=lighthouse_payload,
    )

    system_instruction = (
        "你是一位专业的公益机构品牌评估顾问, 擅长从官方语料里识别其品牌主张、"
        "媒体声音、合作生态. 严格基于语料给出 JSON, 不要瞎编. "
        "词云必须恰好 50 项. tone/type 字段只用规定的英文枚举值."
    )

    llm_model = ""
    error: str | None = None
    payload: dict[str, Any] = {}
    raw_text: Any = None
    try:
        raw_text = ai_service._qwen_generate(
            prompt=prompt,
            system_instruction=system_instruction,
            response_schema=_RESPONSE_SCHEMA,
            timeout_seconds=180.0,
            max_tokens=5500,
            temperature=0.3,
            top_p=0.85,
        )
        payload = _coerce_payload(raw_text)
        llm_model = "qwen3-vl:32b"  # 按 memory project_yiyu_model_reuse 强制复用
    except Exception as exc:  # noqa: BLE001
        error = f"llm_failed: {str(exc)[:400]}"
        logger.warning("[brand-mirror] LLM 调用失败 client=%s: %s", client_id, exc)

    self_presentation = payload.get("self_presentation") or []
    blindspots = payload.get("blindspots") or []
    consistency = str(payload.get("consistency") or "").strip()
    media_coverage = [
        {**entry, "tone": _sanitize_tone(entry.get("tone"))}
        for entry in (payload.get("media_coverage") or [])
        if isinstance(entry, dict)
    ]
    partners = [
        entry for entry in (payload.get("partners") or []) if isinstance(entry, dict)
    ]
    word_cloud = _sanitize_word_cloud(payload.get("word_cloud") or [])

    snapshot_id = _new_id()
    created_at = _now_iso()
    db.execute(
        """
        INSERT INTO brand_mirror_snapshots (
            id, client_id, corpus_doc_count, corpus_char_count, website_audit_id,
            self_presentation_json, blindspots_json, consistency_text,
            media_coverage_json, partners_json, word_cloud_json,
            llm_model, llm_raw_json, error, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot_id,
            client_id,
            len(items),
            total_chars,
            website_audit_id,
            json.dumps(self_presentation, ensure_ascii=False),
            json.dumps(blindspots, ensure_ascii=False),
            consistency,
            json.dumps(media_coverage, ensure_ascii=False),
            json.dumps(partners, ensure_ascii=False),
            json.dumps(word_cloud, ensure_ascii=False),
            llm_model,
            json.dumps(payload, ensure_ascii=False)[:200000],
            error,
            created_at,
        ),
    )
    db.conn.commit()

    return BrandMirrorSnapshot(
        snapshot_id=snapshot_id,
        client_id=client_id,
        corpus_doc_count=len(items),
        corpus_char_count=total_chars,
        website_audit_id=website_audit_id,
        self_presentation=self_presentation,
        blindspots=blindspots,
        consistency=consistency,
        media_coverage=media_coverage,
        partners=partners,
        word_cloud=word_cloud,
        llm_model=llm_model,
        error=error,
        created_at=created_at,
    )


def latest_brand_mirror_snapshot(
    db: Database, *, client_id: str
) -> dict[str, Any] | None:
    cur = db.conn.execute(
        """
        SELECT id, corpus_doc_count, corpus_char_count, website_audit_id,
               self_presentation_json, blindspots_json, consistency_text,
               media_coverage_json, partners_json, word_cloud_json,
               llm_model, error, created_at
        FROM brand_mirror_snapshots
        WHERE client_id = ?
        ORDER BY created_at DESC LIMIT 1
        """,
        (client_id,),
    )
    row = cur.fetchone()
    if not row:
        return None

    def _safe_json(text: str, fallback: Any) -> Any:
        try:
            return json.loads(text)
        except (ValueError, TypeError):
            return fallback

    return {
        "id": row[0],
        "corpusDocCount": row[1],
        "corpusCharCount": row[2],
        "websiteAuditId": row[3],
        "selfPresentation": _safe_json(row[4], []),
        "blindspots": _safe_json(row[5], []),
        "consistency": row[6],
        "mediaCoverage": _safe_json(row[7], []),
        "partners": _safe_json(row[8], []),
        "wordCloud": _safe_json(row[9], []),
        "llmModel": row[10],
        "error": row[11],
        "createdAt": row[12],
    }
