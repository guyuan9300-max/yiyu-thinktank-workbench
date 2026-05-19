"""舆情印象主题聚类（P5-A）。

目标：把一个客户/业务线的 30-100 条 sentiment items 聚成 3-7 个 brand impression themes，
让用户一眼看见"网上对他形成了什么印象"，而不是逐条 scroll。

实现策略（见方案讨论）：
  - 不引入 embedding 模型，单次 LLM 调用拍出主题。
  - qwen3-vl:32b 单次 32K 上下文够装 100 条 200 字摘要。
  - TTL=24h，每次 refresh_sentiment 抓完会自动重算。
  - 顺手把每条 item 的 tags_json 反写主题 label（补现在空着的 tags 字段）。
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db import Database, to_json

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# 配置
# ──────────────────────────────────────────────────────────────────────────

THEMES_TTL_HOURS = 24
MIN_ITEMS_FOR_CLUSTERING = 4   # 少于 4 条不聚类（聚出来也没意义）
MIN_ITEMS_PER_THEME = 2        # 簇至少 2 条 items 才算成簇
MAX_ITEMS_FED_TO_LLM = 80      # 喂 LLM 最多 80 条，超过截取最近的
MAX_SUMMARY_CHARS = 220


# ──────────────────────────────────────────────────────────────────────────
# 数据结构
# ──────────────────────────────────────────────────────────────────────────


@dataclass
class ThemeCluster:
    """单个印象主题簇。"""
    id: str
    theme_label: str
    theme_summary: str
    sentiment_tone: str  # 'negative' | 'neutral' | 'positive'
    item_count: int
    representative_quote: str
    representative_item_id: str | None
    item_ids: list[str]


# ──────────────────────────────────────────────────────────────────────────
# Prompt
# ──────────────────────────────────────────────────────────────────────────

CLUSTER_SYSTEM_INSTRUCTION = (
    "你是品牌舆情分析师。给你一批关于同一对象的网络声音摘要，"
    "请聚类出 3 到 7 个『印象主题』。每个主题代表网上大众对这个对象形成的一种印象。"
    "主题名要短（不超过 8 个字）、可被人记住，例如『信息不公开』『儿童活动专业』『营销过度商业化』。"
    "sentiment_tone 表示这个主题对该对象是负面/中性/正面。"
    "每个主题给出 1 句解释，并指出该主题下条目的索引（item_indices，从 0 开始）和最有代表性的那条索引（representative_index）。"
    "只把强信号聚出来——孤立的、和大众印象无关的条目不要硬塞进主题。"
    "严格只返回 JSON，不要 Markdown，不要解释。"
)

CLUSTER_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["themes"],
    "properties": {
        "themes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["label", "summary", "tone", "item_indices", "representative_index"],
                "properties": {
                    "label": {"type": "string"},
                    "summary": {"type": "string"},
                    "tone": {"type": "string", "enum": ["negative", "neutral", "positive"]},
                    "item_indices": {"type": "array", "items": {"type": "integer"}},
                    "representative_index": {"type": "integer"},
                },
            },
        },
    },
}


# ──────────────────────────────────────────────────────────────────────────
# 拉 items + 喂 LLM
# ──────────────────────────────────────────────────────────────────────────


def _fetch_items_for_clustering(
    db: Database,
    *,
    scope_type: str,
    scope_id: str,
    within_days: int = 30,
) -> list[dict[str, Any]]:
    """拉本客户/业务线最近 N 天的有效舆情 items（不含 dismissed/misclassified）。"""
    cutoff_iso = (
        datetime.now(timezone.utc) - timedelta(days=within_days)
    ).isoformat()

    if scope_type == "project_module":
        where = "project_module_id = ?"
    elif scope_type == "client":
        where = "client_id = ?"
    else:
        return []

    rows = db.fetchall(
        f"""
        SELECT id, title, summary, source, source_url, timeliness_label, captured_at
        FROM intelligence_items
        WHERE content_kind = 'public_opinion'
          AND {where}
          AND captured_at >= ?
          AND COALESCE(user_status, 'active') NOT IN ('dismissed', 'misclassified')
        ORDER BY captured_at DESC
        LIMIT ?
        """,
        (scope_id, cutoff_iso, MAX_ITEMS_FED_TO_LLM),
    )
    return [
        {
            "id": str(r["id"]),
            "title": str(r["title"] or ""),
            "summary": str(r["summary"] or "")[:MAX_SUMMARY_CHARS],
            "source": str(r["source"] or ""),
            "source_url": str(r["source_url"] or ""),
            "tone": _timeliness_to_tone(str(r["timeliness_label"] or "")),
        }
        for r in rows
    ]


def _timeliness_to_tone(label: str) -> str:
    if label == "negative_alert":
        return "negative"
    if label == "positive_signal":
        return "positive"
    return "neutral"


def _build_cluster_prompt(items: list[dict[str, Any]], target_name: str) -> str:
    lines = [f"target_name: {target_name}", "", "items（索引从 0 开始）："]
    for i, it in enumerate(items):
        lines.append(f"[{i}] ({it['tone']}/{it['source']}) {it['title']} | {it['summary']}")
    lines.append("")
    lines.append("请输出聚类结果。要求：")
    lines.append(f"- 主题数 3-7 个；每主题至少 {MIN_ITEMS_PER_THEME} 个 item")
    lines.append("- 主题名 ≤ 8 字，最好是名词短语")
    lines.append("- representative_index 必须在 item_indices 中")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────
# LLM 调用 + 解析
# ──────────────────────────────────────────────────────────────────────────


def _invoke_llm(
    ai_service: object,
    items: list[dict[str, Any]],
    target_name: str,
    timeout_seconds: float,
) -> list[dict[str, Any]] | None:
    """调一次 Qwen，返回 themes 列表。失败返回 None。"""
    try:
        raw = ai_service._qwen_generate(  # type: ignore[attr-defined]  # noqa: SLF001
            _build_cluster_prompt(items, target_name),
            CLUSTER_SYSTEM_INSTRUCTION,
            CLUSTER_RESPONSE_SCHEMA,
            timeout_seconds=timeout_seconds,
            max_tokens=2000,
            temperature=0.2,
            task_kind="default",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[theme-cluster] LLM call failed: %s", exc)
        return None

    if not isinstance(raw, dict):
        try:
            raw = json.loads(str(raw))
        except Exception:  # noqa: BLE001
            return None
    if not isinstance(raw, dict):
        return None
    themes = raw.get("themes")
    if not isinstance(themes, list):
        return None
    return [t for t in themes if isinstance(t, dict)]


def _normalize_themes(
    raw_themes: list[dict[str, Any]],
    items: list[dict[str, Any]],
) -> list[ThemeCluster]:
    """把 LLM 输出的索引引用转回 ThemeCluster（带 item id）。"""
    result: list[ThemeCluster] = []
    n = len(items)
    for t in raw_themes:
        label = str(t.get("label") or "").strip()
        if not label:
            continue
        tone = str(t.get("tone") or "neutral").strip().lower()
        if tone not in ("negative", "neutral", "positive"):
            tone = "neutral"
        indices = [
            int(i) for i in (t.get("item_indices") or [])
            if isinstance(i, int) or (isinstance(i, str) and i.isdigit())
        ]
        indices = [i for i in indices if 0 <= i < n]
        if len(indices) < MIN_ITEMS_PER_THEME:
            continue

        rep_idx = t.get("representative_index")
        try:
            rep_idx = int(rep_idx)
        except (TypeError, ValueError):
            rep_idx = indices[0]
        if rep_idx not in indices:
            rep_idx = indices[0]

        rep_item = items[rep_idx]
        item_ids = [items[i]["id"] for i in indices]

        # 代表原话：rep_item 的 summary（去掉 LLM 之前塞的【主题】前缀，干净一点）
        rep_summary = rep_item["summary"]
        if rep_summary.startswith("【主题】"):
            # 形如 "【主题】xxx\n真正的摘要" — 取真正的摘要
            parts = rep_summary.split("\n", 1)
            if len(parts) == 2:
                rep_summary = parts[1].strip()

        result.append(
            ThemeCluster(
                id=f"theme_{uuid.uuid4().hex[:12]}",
                theme_label=label[:32],
                theme_summary=str(t.get("summary") or "").strip()[:300],
                sentiment_tone=tone,
                item_count=len(indices),
                representative_quote=rep_summary[:300],
                representative_item_id=rep_item["id"],
                item_ids=item_ids,
            )
        )
    return result


# ──────────────────────────────────────────────────────────────────────────
# 落库 + 反写 tags
# ──────────────────────────────────────────────────────────────────────────


def _persist_themes(
    db: Database,
    *,
    scope_type: str,
    scope_id: str,
    themes: list[ThemeCluster],
) -> None:
    """覆盖式落库：清掉该 scope 下旧主题，再插新的。"""
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=THEMES_TTL_HOURS)
    now_iso = now.isoformat()
    expires_iso = expires.isoformat()

    db.execute(
        "DELETE FROM intelligence_sentiment_themes WHERE scope_type = ? AND scope_id = ?",
        (scope_type, scope_id),
    )
    for theme in themes:
        db.execute(
            """
            INSERT INTO intelligence_sentiment_themes (
                id, scope_type, scope_id, theme_label, theme_summary,
                sentiment_tone, item_count, representative_quote, representative_item_id,
                item_ids_json, computed_at, expires_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                theme.id,
                scope_type,
                scope_id,
                theme.theme_label,
                theme.theme_summary,
                theme.sentiment_tone,
                theme.item_count,
                theme.representative_quote,
                theme.representative_item_id,
                to_json(theme.item_ids),
                now_iso,
                expires_iso,
                now_iso,
                now_iso,
            ),
        )

    # 反向写 tags_json — 让每条 item 知道自己属于哪些主题
    item_to_labels: dict[str, list[str]] = {}
    for theme in themes:
        for item_id in theme.item_ids:
            item_to_labels.setdefault(item_id, []).append(theme.theme_label)
    for item_id, labels in item_to_labels.items():
        db.execute(
            "UPDATE intelligence_items SET tags_json = ?, updated_at = ? WHERE id = ?",
            (to_json(labels), now_iso, item_id),
        )


# ──────────────────────────────────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────────────────────────────────


def recompute_themes(
    db: Database,
    ai_service: object | None,
    *,
    scope_type: str,
    scope_id: str,
    target_name: str,
    within_days: int = 30,
    timeout_seconds: float = 60.0,
) -> dict[str, Any]:
    """重算指定 scope 的印象主题。返回 {ok, themes, reason?}。"""
    if scope_type not in ("client", "project_module"):
        return {"ok": False, "reason": "invalid_scope_type", "themes": []}
    if not scope_id or not target_name:
        return {"ok": False, "reason": "missing_scope_id_or_target", "themes": []}
    if ai_service is None:
        return {"ok": False, "reason": "ai_service_unavailable", "themes": []}
    try:
        health = ai_service.get_health()  # type: ignore[attr-defined]
        if not getattr(health, "ready", False):
            return {"ok": False, "reason": f"ai_not_ready: {getattr(health, 'detail', '')}", "themes": []}
    except Exception:  # noqa: BLE001
        return {"ok": False, "reason": "ai_health_failed", "themes": []}

    items = _fetch_items_for_clustering(
        db, scope_type=scope_type, scope_id=scope_id, within_days=within_days,
    )
    if len(items) < MIN_ITEMS_FOR_CLUSTERING:
        # 少于阈值时清掉旧主题，避免回显错的 cluster
        db.execute(
            "DELETE FROM intelligence_sentiment_themes WHERE scope_type = ? AND scope_id = ?",
            (scope_type, scope_id),
        )
        return {
            "ok": False,
            "reason": f"too_few_items: {len(items)} < {MIN_ITEMS_FOR_CLUSTERING}",
            "themes": [],
        }

    raw_themes = _invoke_llm(ai_service, items, target_name, timeout_seconds)
    if not raw_themes:
        return {"ok": False, "reason": "llm_failed_or_empty", "themes": []}

    themes = _normalize_themes(raw_themes, items)
    if not themes:
        return {"ok": False, "reason": "no_themes_after_filter", "themes": []}

    _persist_themes(db, scope_type=scope_type, scope_id=scope_id, themes=themes)
    return {
        "ok": True,
        "themes": [_theme_to_dict(t) for t in themes],
    }


def list_themes(
    db: Database,
    *,
    scope_type: str,
    scope_id: str,
) -> list[dict[str, Any]]:
    """读已聚出的主题（不管 TTL，由 endpoint 决定要不要触发 recompute）。"""
    rows = db.fetchall(
        """
        SELECT id, theme_label, theme_summary, sentiment_tone, item_count,
               representative_quote, representative_item_id, item_ids_json,
               computed_at, expires_at
        FROM intelligence_sentiment_themes
        WHERE scope_type = ? AND scope_id = ?
        ORDER BY
            CASE sentiment_tone WHEN 'negative' THEN 0 WHEN 'neutral' THEN 1 ELSE 2 END,
            item_count DESC
        """,
        (scope_type, scope_id),
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        try:
            item_ids = json.loads(r["item_ids_json"]) if r["item_ids_json"] else []
        except Exception:  # noqa: BLE001
            item_ids = []
        out.append({
            "id": str(r["id"]),
            "themeLabel": str(r["theme_label"]),
            "themeSummary": str(r["theme_summary"] or ""),
            "sentimentTone": str(r["sentiment_tone"]),
            "itemCount": int(r["item_count"] or 0),
            "representativeQuote": str(r["representative_quote"] or ""),
            "representativeItemId": str(r["representative_item_id"] or "") or None,
            "itemIds": [str(x) for x in item_ids],
            "computedAt": str(r["computed_at"]),
            "expiresAt": str(r["expires_at"]),
        })
    return out


def fetch_theme_items(
    db: Database,
    *,
    theme_id: str,
    limit: int = 10,
) -> dict[str, Any]:
    """点主题看原话（#4 溯源）。返回主题元信息 + 该簇下的前 N 条 items。"""
    theme_row = db.fetchone(
        "SELECT * FROM intelligence_sentiment_themes WHERE id = ?",
        (theme_id,),
    )
    if not theme_row:
        return {"ok": False, "reason": "theme_not_found", "items": []}

    try:
        item_ids = json.loads(theme_row["item_ids_json"]) if theme_row["item_ids_json"] else []
    except Exception:  # noqa: BLE001
        item_ids = []
    item_ids = [str(x) for x in item_ids][:limit]
    if not item_ids:
        return {
            "ok": True,
            "theme": _theme_row_to_dict(theme_row),
            "items": [],
        }

    placeholders = ",".join("?" * len(item_ids))
    rows = db.fetchall(
        f"""
        SELECT id, title, summary, source, source_url, captured_at,
               timeliness_label, relevance_reason
        FROM intelligence_items
        WHERE id IN ({placeholders})
        ORDER BY captured_at DESC
        """,
        tuple(item_ids),
    )
    return {
        "ok": True,
        "theme": _theme_row_to_dict(theme_row),
        "items": [
            {
                "id": str(r["id"]),
                "title": str(r["title"] or ""),
                "summary": str(r["summary"] or ""),
                "source": str(r["source"] or ""),
                "sourceUrl": str(r["source_url"] or ""),
                "capturedAt": str(r["captured_at"] or ""),
                "sentimentLabel": _timeliness_to_short(str(r["timeliness_label"] or "")),
                "sentimentReason": str(r["relevance_reason"] or ""),
            }
            for r in rows
        ],
    }


def themes_cache_is_fresh(
    db: Database,
    *,
    scope_type: str,
    scope_id: str,
) -> bool:
    """看缓存是否未过期。endpoint 决定该不该触发重算。"""
    row = db.fetchone(
        """
        SELECT MIN(expires_at) AS min_expires
        FROM intelligence_sentiment_themes
        WHERE scope_type = ? AND scope_id = ?
        """,
        (scope_type, scope_id),
    )
    if not row or not row["min_expires"]:
        return False
    try:
        expires = datetime.fromisoformat(str(row["min_expires"]))
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
    except Exception:  # noqa: BLE001
        return False
    return expires > datetime.now(timezone.utc)


# ──────────────────────────────────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────────────────────────────────


def _theme_to_dict(theme: ThemeCluster) -> dict[str, Any]:
    return {
        "id": theme.id,
        "themeLabel": theme.theme_label,
        "themeSummary": theme.theme_summary,
        "sentimentTone": theme.sentiment_tone,
        "itemCount": theme.item_count,
        "representativeQuote": theme.representative_quote,
        "representativeItemId": theme.representative_item_id,
        "itemIds": theme.item_ids,
    }


def _theme_row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "themeLabel": str(row["theme_label"]),
        "themeSummary": str(row["theme_summary"] or ""),
        "sentimentTone": str(row["sentiment_tone"]),
        "itemCount": int(row["item_count"] or 0),
        "representativeQuote": str(row["representative_quote"] or ""),
        "representativeItemId": str(row["representative_item_id"] or "") or None,
        "computedAt": str(row["computed_at"]),
        "expiresAt": str(row["expires_at"]),
    }


def _timeliness_to_short(timeliness: str) -> str:
    if timeliness == "negative_alert":
        return "negative"
    if timeliness == "positive_signal":
        return "positive"
    return "neutral"
