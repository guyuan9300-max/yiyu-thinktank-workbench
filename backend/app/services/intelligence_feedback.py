from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from app.db import Database, from_json, to_json


POSITIVE_ACTIONS = {"follow", "task"}
NEGATIVE_ACTIONS = {"dismiss"}
NEUTRAL_ACTIONS = {"chat", "focus"}
TARGET_TYPES = {"theme", "tag", "source", "domain", "search_intent"}


@dataclass
class FeedbackContext:
    item_id: str | None = None
    candidate_id: str | None = None
    source_config_id: str | None = None
    intent_id: str | None = None
    scope_type: str = ""
    scope_id: str = ""
    client_id: str | None = None
    project_module_id: str | None = None
    content_kind: str = ""
    title: str = ""
    summary: str = ""
    source: str = ""
    source_url: str | None = None
    source_domain: str = ""
    tags: list[str] | None = None
    extracted_topics: list[str] | None = None


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _clean_text(value: object, *, max_len: int = 160) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:max_len]


def _safe_json(value: str | None, default: object) -> object:
    try:
        return from_json(value, default)
    except Exception:
        return default


def _as_text_list(value: object, *, limit: int = 12) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = re.split(r"[\n,，;；、/|]+", value)
    elif isinstance(value, (list, tuple)):
        raw_items = value
    elif isinstance(value, dict):
        raw_items = value.values()
    else:
        raw_items = [value]
    items: list[str] = []
    for item in raw_items:
        text = _clean_text(item, max_len=80)
        if text and text not in items:
            items.append(text)
        if len(items) >= limit:
            break
    return items


def _target_key(value: str) -> str:
    text = _clean_text(value, max_len=120).lower()
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def normalize_scope(scope_type: str | None, scope_id: str | None, client_id: str | None, project_module_id: str | None) -> tuple[str, str]:
    if project_module_id:
        return "project_module", str(project_module_id)
    if scope_type in {"project", "project_module", "module"} and scope_id:
        return "project_module", str(scope_id)
    if client_id:
        return "client", str(client_id)
    return ("client", str(scope_id or "")) if scope_id else ("", "")


def source_domain_from_url(url: str | None) -> str:
    if not url:
        return ""
    try:
        return urlparse(str(url)).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def extract_topics(*texts: object, tags: list[str] | None = None, limit: int = 8) -> list[str]:
    topics: list[str] = []
    for tag in tags or []:
        tag_text = _clean_text(tag, max_len=40)
        if tag_text and tag_text not in topics:
            topics.append(tag_text)
    corpus = " ".join(_clean_text(text, max_len=320) for text in texts if text)
    for token in re.split(r"[\s,，;；、/|：:（）()《》「」【】\\-]+", corpus):
        cleaned = _clean_text(token, max_len=32)
        if len(cleaned) < 2:
            continue
        if cleaned in {"项目", "客户", "公益", "服务", "来源", "情报", "资料", "公开", "自动候选"}:
            continue
        if cleaned not in topics:
            topics.append(cleaned)
        if len(topics) >= limit:
            break
    return topics[:limit]


def context_from_item_row(db: Database, item_row) -> FeedbackContext:
    tags = _as_text_list(_safe_json(str(item_row["tags_json"] or "[]"), []), limit=12)
    source_url = str(item_row["source_url"]) if item_row["source_url"] else None
    scope_type, scope_id = normalize_scope(
        str(item_row["scope_type"] or ""),
        str(item_row["scope_id"] or ""),
        str(item_row["client_id"] or "") or None,
        str(item_row["project_module_id"] or "") or None,
    )
    candidate = db.fetchone(
        """
        SELECT *
        FROM intelligence_candidate_items
        WHERE promoted_intelligence_item_id = ?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (str(item_row["id"]),),
    )
    source_config_id = str(candidate["source_config_id"]) if candidate and candidate["source_config_id"] else None
    intent_id = str(candidate["intent_id"]) if candidate and candidate["intent_id"] else None
    candidate_id = str(candidate["id"]) if candidate else None
    title = str(item_row["title"] or "")
    summary = str(item_row["summary"] or "")
    topics = extract_topics(title, summary, str(item_row["analysis"] or ""), tags=tags)
    return FeedbackContext(
        item_id=str(item_row["id"]),
        candidate_id=candidate_id,
        source_config_id=source_config_id,
        intent_id=intent_id,
        scope_type=scope_type,
        scope_id=scope_id,
        client_id=str(item_row["client_id"] or "") or None,
        project_module_id=str(item_row["project_module_id"] or "") or None,
        content_kind=str(item_row["content_kind"] or ""),
        title=title,
        summary=summary,
        source=str(item_row["source"] or ""),
        source_url=source_url,
        source_domain=source_domain_from_url(source_url),
        tags=tags,
        extracted_topics=topics,
    )


def score_delta_for_action(action_type: str, reason_code: str = "") -> float:
    action = str(action_type or "").strip()
    reason = str(reason_code or "").strip()
    if action == "task":
        return 2.0
    if action == "follow":
        return 1.0
    if action == "chat":
        return 0.25
    if action == "focus":
        return 0.4
    if action == "dismiss":
        if reason in {"duplicate", "outdated"}:
            return -0.6
        return -1.0
    return 0.0


def _summary_count_deltas(score_delta: float) -> tuple[int, int, int]:
    if score_delta > 0:
        return 1, 0, 0
    if score_delta < 0:
        return 0, 1, 0
    return 0, 0, 1


def _targets_for_context(context: FeedbackContext, *, action_type: str, note: str = "") -> list[tuple[str, str]]:
    topics = list(context.extracted_topics or [])
    topics.extend(extract_topics(note, limit=4))
    targets: list[tuple[str, str]] = []
    if action_type == "chat":
        for topic in topics[:5]:
            targets.append(("theme", topic))
        return targets
    for topic in topics[:6]:
        targets.append(("theme", topic))
    for tag in (context.tags or [])[:6]:
        targets.append(("tag", tag))
    if context.source:
        targets.append(("source", context.source))
    if context.source_domain:
        targets.append(("domain", context.source_domain))
    if context.intent_id:
        targets.append(("search_intent", context.intent_id))
    seen: set[tuple[str, str]] = set()
    result: list[tuple[str, str]] = []
    for target_type, label in targets:
        cleaned = _clean_text(label, max_len=120)
        key = (target_type, cleaned)
        if not cleaned or key in seen:
            continue
        seen.add(key)
        result.append(key)
    return result


def _upsert_summary(
    db: Database,
    *,
    context: FeedbackContext,
    target_type: str,
    target_label: str,
    score_delta: float,
    timestamp: str,
) -> None:
    if target_type not in TARGET_TYPES:
        return
    key = _target_key(f"{target_type}:{target_label}")
    if not key:
        return
    positive_delta, negative_delta, neutral_delta = _summary_count_deltas(score_delta)
    existing = db.fetchone(
        """
        SELECT id, created_at
        FROM intelligence_feedback_summaries
        WHERE scope_type = ? AND scope_id = ? AND content_kind = ?
          AND target_type = ? AND target_key = ?
        """,
        (context.scope_type, context.scope_id, context.content_kind, target_type, key),
    )
    summary_id = str(existing["id"]) if existing else _new_id("ifsum")
    created_at = str(existing["created_at"]) if existing else timestamp
    db.execute(
        """
        INSERT INTO intelligence_feedback_summaries(
            id, scope_type, scope_id, client_id, project_module_id, content_kind,
            target_type, target_key, target_label, positive_count, negative_count,
            neutral_count, score, last_event_at, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(scope_type, scope_id, content_kind, target_type, target_key) DO UPDATE SET
            client_id = excluded.client_id,
            project_module_id = excluded.project_module_id,
            target_label = excluded.target_label,
            positive_count = positive_count + excluded.positive_count,
            negative_count = negative_count + excluded.negative_count,
            neutral_count = neutral_count + excluded.neutral_count,
            score = MAX(-5, MIN(5, score + excluded.score)),
            last_event_at = excluded.last_event_at,
            updated_at = excluded.updated_at
        """,
        (
            summary_id,
            context.scope_type,
            context.scope_id,
            context.client_id,
            context.project_module_id,
            context.content_kind,
            target_type,
            key,
            target_label,
            positive_delta,
            negative_delta,
            neutral_delta,
            score_delta,
            timestamp,
            created_at,
            timestamp,
        ),
    )


def record_feedback_event(
    db: Database,
    *,
    context: FeedbackContext,
    action_type: str,
    reason_code: str = "",
    note: str = "",
    payload: dict[str, object] | None = None,
) -> str:
    timestamp = now_iso()
    score_delta = score_delta_for_action(action_type, reason_code)
    event_id = _new_id("ifevt")
    db.execute(
        """
        INSERT INTO intelligence_feedback_events(
            id, scope_type, scope_id, client_id, project_module_id, content_kind,
            item_id, candidate_id, source_config_id, intent_id, action_type, reason_code,
            note, extracted_topics_json, tags_json, source, source_domain, source_url,
            score_delta, payload_json, created_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            context.scope_type,
            context.scope_id,
            context.client_id,
            context.project_module_id,
            context.content_kind,
            context.item_id,
            context.candidate_id,
            context.source_config_id,
            context.intent_id,
            action_type,
            reason_code,
            _clean_text(note, max_len=500),
            to_json(context.extracted_topics or []),
            to_json(context.tags or []),
            context.source,
            context.source_domain,
            context.source_url,
            score_delta,
            to_json(payload or {}),
            timestamp,
        ),
    )
    for target_type, label in _targets_for_context(context, action_type=action_type, note=note):
        target_delta = score_delta
        if action_type == "chat" and target_type != "theme":
            continue
        _upsert_summary(
            db,
            context=context,
            target_type=target_type,
            target_label=label,
            score_delta=target_delta,
            timestamp=timestamp,
        )
    return event_id


def feedback_score_for_candidate(
    db: Database,
    *,
    scope_type: str,
    scope_id: str,
    content_kind: str,
    title: str,
    snippet: str = "",
    tags: list[str] | None = None,
    source: str = "",
    source_domain: str = "",
    intent_id: str | None = None,
) -> float:
    topics = extract_topics(title, snippet, tags=tags)
    target_labels: list[tuple[str, str]] = [(("theme", topic)) for topic in topics[:6]]
    target_labels.extend(("tag", tag) for tag in (tags or [])[:6])
    if source:
        target_labels.append(("source", source))
    if source_domain:
        target_labels.append(("domain", source_domain))
    if intent_id:
        target_labels.append(("search_intent", intent_id))
    total = 0.0
    seen: set[tuple[str, str]] = set()
    for target_type, label in target_labels:
        key_tuple = (target_type, label)
        if key_tuple in seen:
            continue
        seen.add(key_tuple)
        target_key = _target_key(f"{target_type}:{label}")
        row = db.fetchone(
            """
            SELECT score
            FROM intelligence_feedback_summaries
            WHERE scope_type = ? AND scope_id = ? AND content_kind = ?
              AND target_type = ? AND target_key = ?
            """,
            (scope_type, scope_id, content_kind, target_type, target_key),
        )
        if row:
            weight = 0.35 if target_type in {"theme", "tag"} else 0.5
            total += float(row["score"] or 0) * weight
    return max(-3.0, min(3.0, total))


def source_feedback_adjustment(db: Database, *, source_config_id: str, content_kind: str) -> float:
    row = db.fetchone("SELECT * FROM intelligence_source_configs WHERE id = ?", (source_config_id,))
    if not row:
        return 0.0
    scope_type = str(row["scope_type"] or "")
    scope_id = str(row["scope_id"] or "")
    source = str(row["source_name"] or "")
    domain = ""
    template = str(row["source_url_template"] or "")
    if template.startswith("site:"):
        domain = template.split(" ", 1)[0].replace("site:", "").strip()
    total = 0.0
    for target_type, label in (("source", source), ("domain", domain)):
        if not label:
            continue
        target_key = _target_key(f"{target_type}:{label}")
        summary = db.fetchone(
            """
            SELECT score
            FROM intelligence_feedback_summaries
            WHERE scope_type = ? AND scope_id = ? AND content_kind = ?
              AND target_type = ? AND target_key = ?
            """,
            (scope_type, scope_id, content_kind, target_type, target_key),
        )
        if summary:
            total += float(summary["score"] or 0)
    return max(-4.0, min(4.0, total))


def search_feedback_terms(db: Database, *, scope_type: str, scope_id: str, content_kind: str) -> dict[str, list[str]]:
    rows = db.fetchall(
        """
        SELECT target_type, target_label, score
        FROM intelligence_feedback_summaries
        WHERE scope_type = ? AND scope_id = ? AND content_kind = ?
          AND target_type IN ('theme', 'tag', 'source', 'domain')
        ORDER BY ABS(score) DESC, updated_at DESC
        LIMIT 24
        """,
        (scope_type, scope_id, content_kind),
    )
    positive: list[str] = []
    negative: list[str] = []
    for row in rows:
        label = _clean_text(row["target_label"], max_len=80)
        score = float(row["score"] or 0)
        if not label:
            continue
        if score >= 1 and label not in positive:
            positive.append(label)
        elif score <= -1 and label not in negative:
            negative.append(label)
    return {"positive": positive[:8], "negative": negative[:8]}


def feedback_diagnostics(db: Database, *, scope_type: str, scope_id: str, content_kind: str | None = None) -> dict[str, object]:
    normalized_type = "project_module" if scope_type in {"project", "project_module", "module"} else "client"
    params: list[object] = [normalized_type, scope_id]
    where = "scope_type = ? AND scope_id = ?"
    if content_kind:
        where += " AND content_kind = ?"
        params.append(content_kind)
    summary_rows = db.fetchall(
        f"""
        SELECT *
        FROM intelligence_feedback_summaries
        WHERE {where}
        ORDER BY ABS(score) DESC, updated_at DESC
        LIMIT 50
        """,
        tuple(params),
    )
    event_rows = db.fetchall(
        f"""
        SELECT *
        FROM intelligence_feedback_events
        WHERE {where}
        ORDER BY created_at DESC
        LIMIT 30
        """,
        tuple(params),
    )
    return {
        "scopeType": normalized_type,
        "scopeId": scope_id,
        "contentKind": content_kind,
        "summaries": [
            {
                "targetType": str(row["target_type"] or ""),
                "targetLabel": str(row["target_label"] or ""),
                "positiveCount": int(row["positive_count"] or 0),
                "negativeCount": int(row["negative_count"] or 0),
                "neutralCount": int(row["neutral_count"] or 0),
                "score": float(row["score"] or 0),
                "lastEventAt": str(row["last_event_at"] or "") or None,
            }
            for row in summary_rows
        ],
        "events": [
            {
                "id": str(row["id"]),
                "contentKind": str(row["content_kind"] or ""),
                "itemId": str(row["item_id"] or "") or None,
                "candidateId": str(row["candidate_id"] or "") or None,
                "actionType": str(row["action_type"] or ""),
                "reasonCode": str(row["reason_code"] or ""),
                "note": str(row["note"] or ""),
                "extractedTopics": _safe_json(str(row["extracted_topics_json"] or "[]"), []),
                "source": str(row["source"] or ""),
                "sourceDomain": str(row["source_domain"] or ""),
                "scoreDelta": float(row["score_delta"] or 0),
                "createdAt": str(row["created_at"] or ""),
            }
            for row in event_rows
        ],
    }
