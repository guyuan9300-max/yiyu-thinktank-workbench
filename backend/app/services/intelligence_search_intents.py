from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Iterable

from app.db import Database, from_json, to_json
from app.services.intelligence_feedback import search_feedback_terms
from app.services.public_search import search_public_web


logger = logging.getLogger(__name__)

GENERATOR_VERSION = "p1a-rule-ai-v1"
CONTENT_KINDS = ("profile_completion", "timely_intelligence")
PROFILE_TTL_HOURS = 72
TIMELY_TTL_HOURS = 24
DEFAULT_EXCLUDE_TERMS = [
    "小红书",
    "微信公众号",
    "登录后可见",
    "无来源截图",
]


@dataclass(frozen=True)
class IntelligenceSearchScope:
    scope_type: str
    scope_id: str
    client_id: str
    project_module_id: str | None = None
    display_name: str = ""


@dataclass
class GeneratedSearchIntent:
    id: str
    scope_type: str
    scope_id: str
    client_id: str
    project_module_id: str | None
    content_kind: str
    query: str
    exclude_terms: list[str]
    source_inputs: list[str]
    reason: str
    priority: int
    status: str
    input_hash: str
    expires_at: str
    generator_version: str = GENERATOR_VERSION


@dataclass
class SearchIntentGenerationResult:
    scope: IntelligenceSearchScope
    intents: list[GeneratedSearchIntent] = field(default_factory=list)
    status: str = "ready"
    input_hash: str = ""
    errors: list[str] = field(default_factory=list)


@dataclass
class SearchDiagnosticResult:
    intent_id: str | None
    query: str
    content_kind: str
    status: str
    provider: str
    raw_count: int = 0
    deduped_count: int = 0
    sample_hits: list[dict[str, str]] = field(default_factory=list)
    failure_reason: str = ""
    duration_ms: int = 0


@dataclass
class EnrichmentSeedSelection:
    seed_queries: list[str]
    gaps: list[str]


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _clean_text(value: object, *, max_len: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:max_len]


def _safe_json(value: str | None, default: object) -> object:
    try:
        return from_json(value, default)
    except Exception:
        return default


def _as_text_list(value: object, *, limit: int = 12) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items: Iterable[object] = re.split(r"[\n,，;；、]+", value)
    elif isinstance(value, list):
        raw_items = value
    elif isinstance(value, tuple):
        raw_items = value
    elif isinstance(value, dict):
        raw_items = value.values()
    else:
        raw_items = [value]
    items: list[str] = []
    for item in raw_items:
        if isinstance(item, dict):
            text = " ".join(_clean_text(part, max_len=60) for part in item.values() if _clean_text(part, max_len=60))
        else:
            text = _clean_text(item, max_len=120)
        if text and text not in items:
            items.append(text)
        if len(items) >= limit:
            break
    return items


def _dedupe(items: Iterable[str], *, limit: int = 20) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _clean_text(item, max_len=140)
        if not text:
            continue
        key = re.sub(r"\s+", "", text).lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def _extract_terms(*values: object, limit: int = 8) -> list[str]:
    chunks: list[str] = []
    for value in values:
        chunks.extend(_as_text_list(value, limit=24))
    terms: list[str] = []
    for chunk in chunks:
        for token in re.split(r"[\s,，;；、/|]+", chunk):
            cleaned = _clean_text(token, max_len=24)
            if len(cleaned) < 2:
                continue
            if cleaned in {"项目", "客户", "公益", "服务", "推进中", "内部陪伴"}:
                continue
            if cleaned not in terms:
                terms.append(cleaned)
            if len(terms) >= limit:
                return terms
    return terms


def _row_dict(row) -> dict[str, object]:
    return dict(row) if row is not None else {}


def _normalize_scope_type(scope_type: str) -> str:
    value = str(scope_type or "client").strip()
    return "project_module" if value in {"project", "project_module", "module"} else "client"


def resolve_intelligence_search_scope(db: Database, *, scope_type: str, scope_id: str) -> IntelligenceSearchScope:
    normalized_type = _normalize_scope_type(scope_type)
    normalized_id = str(scope_id or "").strip()
    if normalized_type == "project_module":
        project = db.fetchone("SELECT * FROM project_modules WHERE id = ?", (normalized_id,))
        if not project:
            raise ValueError("Project module not found")
        client_id = str(project["client_id"] or "")
        display_name = str(project["name"] or normalized_id)
        return IntelligenceSearchScope(
            scope_type="project_module",
            scope_id=normalized_id,
            client_id=client_id,
            project_module_id=normalized_id,
            display_name=display_name,
        )
    client = db.fetchone("SELECT * FROM clients WHERE id = ?", (normalized_id,))
    if not client:
        raise ValueError("Client not found")
    return IntelligenceSearchScope(
        scope_type="client",
        scope_id=normalized_id,
        client_id=normalized_id,
        project_module_id=None,
        display_name=str(client["name"] or normalized_id),
    )


def _collect_context(db: Database, scope: IntelligenceSearchScope) -> dict[str, object]:
    client = _row_dict(db.fetchone("SELECT * FROM clients WHERE id = ?", (scope.client_id,)))
    project = {}
    projects: list[dict[str, object]] = []
    flows: list[dict[str, object]] = []
    if scope.project_module_id:
        project = _row_dict(db.fetchone("SELECT * FROM project_modules WHERE id = ?", (scope.project_module_id,)))
        projects = [project] if project else []
        flow_rows = db.fetchall(
            "SELECT * FROM project_flows WHERE client_id = ? AND module_id = ? ORDER BY updated_at DESC LIMIT 8",
            (scope.client_id, scope.project_module_id),
        )
        flows = [_row_dict(row) for row in flow_rows]
    else:
        project_rows = db.fetchall(
            "SELECT * FROM project_modules WHERE client_id = ? ORDER BY updated_at DESC LIMIT 8",
            (scope.client_id,),
        )
        projects = [_row_dict(row) for row in project_rows]
        flow_rows = db.fetchall(
            "SELECT * FROM project_flows WHERE client_id = ? ORDER BY updated_at DESC LIMIT 12",
            (scope.client_id,),
        )
        flows = [_row_dict(row) for row in flow_rows]

    directive_keys: list[tuple[str, str]] = [("global", "")]
    directive_keys.append(("client", scope.client_id))
    if scope.project_module_id:
        directive_keys.append(("project_module", scope.project_module_id))
    clauses = " OR ".join(["(scope_type = ? AND scope_id = ?)"] * len(directive_keys))
    params: list[object] = []
    for key in directive_keys:
        params.extend(key)
    directive_rows = db.fetchall(
        f"SELECT * FROM intelligence_focus_directives WHERE {clauses} ORDER BY updated_at DESC",
        tuple(params),
    )
    directives = [_row_dict(row) for row in directive_rows]

    gap_rows = db.fetchall(
        """
        SELECT title, summary, content_markdown, confidence_score
        FROM organization_dna_v2_items
        WHERE module_kind = 'gap_dna'
          AND COALESCE(status, '') <> 'deprecated'
        ORDER BY updated_at DESC
        LIMIT 10
        """
    )
    gap_items = [_row_dict(row) for row in gap_rows]

    return {
        "client": client,
        "project": project,
        "projects": projects,
        "flows": flows,
        "directives": directives,
        "gapItems": gap_items,
        "feedbackTerms": {
            kind: search_feedback_terms(db, scope_type=scope.scope_type, scope_id=scope.scope_id, content_kind=kind)
            for kind in CONTENT_KINDS
        },
    }


def _context_hash(context: dict[str, object], content_kinds: list[str]) -> str:
    payload = {
        "version": GENERATOR_VERSION,
        "contentKinds": content_kinds,
        "client": context.get("client"),
        "project": context.get("project"),
        "projects": context.get("projects"),
        "flows": context.get("flows"),
        "directives": context.get("directives"),
        "gapItems": context.get("gapItems"),
        "feedbackTerms": context.get("feedbackTerms"),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _directive_lines(context: dict[str, object], key: str) -> list[str]:
    lines: list[str] = []
    for directive in context.get("directives", []) or []:
        if not isinstance(directive, dict):
            continue
        lines.extend(_as_text_list(_safe_json(str(directive.get(key) or "[]"), []), limit=12))
    return _dedupe(lines, limit=16)


def _exclude_terms(context: dict[str, object]) -> list[str]:
    excludes = list(DEFAULT_EXCLUDE_TERMS)
    for directive in context.get("directives", []) or []:
        if isinstance(directive, dict):
            excludes.extend(_as_text_list(_safe_json(str(directive.get("exclude_json") or "[]"), []), limit=12))
    feedback_terms = context.get("feedbackTerms") if isinstance(context.get("feedbackTerms"), dict) else {}
    for value in feedback_terms.values():
        if isinstance(value, dict):
            excludes.extend(_as_text_list(value.get("negative"), limit=8))
    return _dedupe(excludes, limit=20)


def _profile_gap_phrases(context: dict[str, object]) -> list[str]:
    gaps = [
        "登记信息 信息公开",
        "年报 信息公开",
        "服务对象 规模",
        "项目成效 报告",
        "合作方 执行方法",
        "公开报告 filetype:pdf",
    ]
    client = context.get("client") if isinstance(context.get("client"), dict) else {}
    projects = [item for item in context.get("projects", []) or [] if isinstance(item, dict)]
    if not str(client.get("intro") or "").strip():
        gaps.append("机构简介 官网")
    if projects:
        gaps.extend(["项目介绍", "项目时间线 案例"])
    for item in context.get("gapItems", []) or []:
        if isinstance(item, dict):
            gaps.extend(_as_text_list([item.get("title"), item.get("summary")], limit=3))
    gaps.extend(_directive_lines(context, "profile_completion_focus_json"))
    feedback_terms = context.get("feedbackTerms") if isinstance(context.get("feedbackTerms"), dict) else {}
    profile_feedback = feedback_terms.get("profile_completion") if isinstance(feedback_terms.get("profile_completion"), dict) else {}
    gaps.extend(_as_text_list(profile_feedback.get("positive"), limit=8))
    return _dedupe(gaps, limit=14)


def _profile_gap_description(gap: str) -> str:
    normalized = _clean_text(gap, max_len=120)
    descriptions = [
        (("登记", "信息公开"), "查找可确认主体身份、登记机关、统一社会信用代码、法定代表人、住所、业务范围等固定资料的可靠公开页面。"),
        (("年报", "信息公开"), "查找年度报告、信息公开页面或公开披露文件，用于补足组织年度运营、项目、财务或治理资料。"),
        (("服务对象", "规模"), "查找服务对象、覆盖区域、受益人数、服务规模等可复用事实，避免只采纳泛泛介绍。"),
        (("项目成效", "报告"), "查找项目成果、评估、案例或公开报告，用于补足项目成效和证据材料。"),
        (("合作方", "执行方法"), "查找合作机构、资助方、执行路径、服务方法等可复用事实。"),
        (("公开报告",), "查找 PDF、报告、白皮书、案例材料等正文可清洗的公开文件。"),
        (("机构简介", "官网"), "优先查找客户/项目官网或权威公开介绍，用于补足机构定位和公开服务描述。"),
        (("项目介绍",), "查找项目概况、目标、服务内容、执行周期、服务对象和成效资料。"),
    ]
    for keywords, description in descriptions:
        if all(keyword in normalized for keyword in keywords):
            return f"资料补全缺口：{normalized}。详细需求：{description}"
    return f"资料补全缺口：{normalized}。详细需求：查找能确认属于当前客户/项目、可补足资料缺口、并能提炼为可复用事实的中文公开资料。"


def _source_inputs(context: dict[str, object]) -> list[str]:
    client = context.get("client") if isinstance(context.get("client"), dict) else {}
    project = context.get("project") if isinstance(context.get("project"), dict) else {}
    inputs = [
        f"client:{client.get('name', '')}",
        f"client_domain:{client.get('domain', '')}",
        f"client_stage:{client.get('stage', '')}",
    ]
    if project:
        inputs.append(f"project:{project.get('name', '')}")
    inputs.extend(f"focus:{line}" for line in _directive_lines(context, "profile_completion_focus_json")[:4])
    inputs.extend(f"focus:{line}" for line in _directive_lines(context, "timely_intelligence_focus_json")[:4])
    feedback_terms = context.get("feedbackTerms") if isinstance(context.get("feedbackTerms"), dict) else {}
    for kind, value in feedback_terms.items():
        if isinstance(value, dict):
            inputs.extend(f"feedback:{kind}:positive:{line}" for line in _as_text_list(value.get("positive"), limit=3))
            inputs.extend(f"feedback:{kind}:negative:{line}" for line in _as_text_list(value.get("negative"), limit=3))
    return _dedupe(inputs, limit=16)


def _make_intent(
    *,
    scope: IntelligenceSearchScope,
    content_kind: str,
    query: str,
    reason: str,
    priority: int,
    exclude_terms: list[str],
    source_inputs: list[str],
    input_hash: str,
    expires_at: str,
) -> GeneratedSearchIntent:
    return GeneratedSearchIntent(
        id=_new_id("isint"),
        scope_type=scope.scope_type,
        scope_id=scope.scope_id,
        client_id=scope.client_id,
        project_module_id=scope.project_module_id,
        content_kind=content_kind,
        query=_clean_text(query, max_len=140),
        exclude_terms=exclude_terms,
        source_inputs=source_inputs,
        reason=_clean_text(reason, max_len=240),
        priority=max(1, min(int(priority), 100)),
        status="ready",
        input_hash=input_hash,
        expires_at=expires_at,
    )


def _build_rule_intents(
    *,
    scope: IntelligenceSearchScope,
    context: dict[str, object],
    content_kinds: list[str],
    input_hash: str,
    timestamp: str,
) -> list[GeneratedSearchIntent]:
    client = context.get("client") if isinstance(context.get("client"), dict) else {}
    project = context.get("project") if isinstance(context.get("project"), dict) else {}
    projects = [item for item in context.get("projects", []) or [] if isinstance(item, dict)]
    flows = [item for item in context.get("flows", []) or [] if isinstance(item, dict)]
    client_name = _clean_text(client.get("name") or scope.display_name)
    domain = _clean_text(client.get("domain") or "")
    stage = _clean_text(client.get("stage") or "")
    project_name = _clean_text(project.get("name") or "")
    project_terms = _extract_terms(
        project.get("name"),
        project.get("goal"),
        project.get("description"),
        _safe_json(str(project.get("keywords_json") or "[]"), []),
        *[_safe_json(str(item.get("keywords_json") or "[]"), []) for item in projects[:4]],
        *[item.get("risk_points_json") for item in flows[:3]],
        limit=8,
    )
    base_object = " ".join(_dedupe([client_name, project_name], limit=2)).strip()
    object_with_domain = " ".join(_dedupe([base_object, domain], limit=4)).strip()
    excludes = _exclude_terms(context)
    inputs = _source_inputs(context)
    intents: list[GeneratedSearchIntent] = []
    if "profile_completion" in content_kinds:
        profile_expires = (datetime.fromisoformat(timestamp) + timedelta(hours=PROFILE_TTL_HOURS)).isoformat()
        for index, gap in enumerate(_profile_gap_phrases(context), start=1):
            query = f"{base_object or client_name} {gap}".strip()
            intents.append(
                _make_intent(
                    scope=scope,
                    content_kind="profile_completion",
                    query=query,
                    reason=_profile_gap_description(gap),
                    priority=96 - index,
                    exclude_terms=excludes,
                    source_inputs=inputs,
                    input_hash=input_hash,
                    expires_at=profile_expires,
                )
            )
        if project_terms:
            intents.append(
                _make_intent(
                    scope=scope,
                    content_kind="profile_completion",
                    query=f"{base_object or client_name} {' '.join(project_terms[:3])} 公开资料",
                    reason="由项目关键词生成的公开资料补全意图",
                    priority=86,
                    exclude_terms=excludes,
                    source_inputs=inputs,
                    input_hash=input_hash,
                    expires_at=profile_expires,
                )
            )
    if "timely_intelligence" in content_kinds:
        timely_expires = (datetime.fromisoformat(timestamp) + timedelta(hours=TIMELY_TTL_HOURS)).isoformat()
        timely_templates = [
            ("政策窗口", f"{object_with_domain or client_name} 政策 通知"),
            ("政府购买服务与采购", f"{object_with_domain or client_name} 政府购买服务 招标 采购"),
            ("资助申报", f"{object_with_domain or client_name} 资助 申报 通知"),
            ("监管变化", f"{object_with_domain or client_name} 监管 规范 通知"),
            ("客户动态与舆情", f"{client_name} 新闻 动态 舆情"),
            ("同类机构动作", f"{domain or client_name} 同类机构 项目 动态"),
        ]
        if project_terms:
            timely_templates.append(("项目短期机会", f"{object_with_domain or client_name} {' '.join(project_terms[:3])} 机会"))
        for line in _directive_lines(context, "timely_intelligence_focus_json"):
            timely_templates.append((f"用户关注：{line}", f"{object_with_domain or client_name} {line}"))
        feedback_terms = context.get("feedbackTerms") if isinstance(context.get("feedbackTerms"), dict) else {}
        timely_feedback = feedback_terms.get("timely_intelligence") if isinstance(feedback_terms.get("timely_intelligence"), dict) else {}
        for line in _as_text_list(timely_feedback.get("positive"), limit=6):
            timely_templates.append((f"用户反馈强化：{line}", f"{object_with_domain or client_name} {line}"))
        for index, (reason, query) in enumerate(timely_templates, start=1):
            intents.append(
                _make_intent(
                    scope=scope,
                    content_kind="timely_intelligence",
                    query=query,
                    reason=reason,
                    priority=96 - index,
                    exclude_terms=excludes,
                    source_inputs=inputs,
                    input_hash=input_hash,
                    expires_at=timely_expires,
                )
            )
    return intents


def _build_ai_prompt(context: dict[str, object], content_kind: str) -> tuple[str, str]:
    client = context.get("client") if isinstance(context.get("client"), dict) else {}
    project = context.get("project") if isinstance(context.get("project"), dict) else {}
    projects = [item for item in context.get("projects", []) or [] if isinstance(item, dict)]
    flows = [item for item in context.get("flows", []) or [] if isinstance(item, dict)]
    object_name = _clean_text(project.get("name") or client.get("name") or "工作对象")
    prompt_lines = [
        f"客户：{_clean_text(client.get('name'))}",
        f"领域：{_clean_text(client.get('domain'))}",
        f"阶段：{_clean_text(client.get('stage'))}",
        f"简介：{_clean_text(client.get('intro'), max_len=160)}",
    ]
    if project:
        prompt_lines.append(f"项目：{_clean_text(project.get('name'))}")
        prompt_lines.append(f"项目目标：{_clean_text(project.get('goal'), max_len=160)}")
        prompt_lines.append(f"项目描述：{_clean_text(project.get('description'), max_len=160)}")
        prompt_lines.append(f"项目关键词：{'、'.join(_as_text_list(_safe_json(str(project.get('keywords_json') or '[]'), []), limit=8))}")
    elif projects:
        prompt_lines.append("相关项目：" + "、".join(_clean_text(item.get("name"), max_len=40) for item in projects[:5]))
    if flows:
        prompt_lines.append("流程风险：" + "、".join(_clean_text(item.get("risk_points_json"), max_len=80) for item in flows[:3] if item.get("risk_points_json")))
    focus_key = "profile_completion_focus_json" if content_kind == "profile_completion" else "timely_intelligence_focus_json"
    focus_lines = _directive_lines(context, focus_key)
    if focus_lines:
        prompt_lines.append("用户关注：" + "、".join(focus_lines[:6]))
    feedback_terms = context.get("feedbackTerms") if isinstance(context.get("feedbackTerms"), dict) else {}
    feedback = feedback_terms.get(content_kind) if isinstance(feedback_terms.get(content_kind), dict) else {}
    positive_feedback = _as_text_list(feedback.get("positive"), limit=6)
    negative_feedback = _as_text_list(feedback.get("negative"), limit=6)
    if positive_feedback:
        prompt_lines.append("对象内正反馈主题：" + "、".join(positive_feedback))
    if negative_feedback:
        prompt_lines.append("对象内负反馈/少看：" + "、".join(negative_feedback))
    gap_lines = []
    for item in context.get("gapItems", []) or []:
        if isinstance(item, dict):
            gap_lines.extend(_as_text_list([item.get("title"), item.get("summary")], limit=2))
    if gap_lines:
        prompt_lines.append("组织缺口：" + "、".join(_dedupe(gap_lines, limit=6)))
    if content_kind == "profile_completion":
        prompt_lines.append("目标：生成用于补齐客户/项目固定资料的中文公开源查询词，优先官网、信息公开、年报、项目报告、合作方、服务对象规模、成效资料。")
    else:
        prompt_lines.append("目标：生成用于发现时效情报的中文公开源查询词，优先政策、采购招标、资助申报、监管、舆情、合作方动态、同类机构动作。")
    return object_name, "\n".join(line for line in prompt_lines if line.strip())


def _build_ai_intents(
    *,
    ai_service: object | None,
    scope: IntelligenceSearchScope,
    context: dict[str, object],
    content_kinds: list[str],
    input_hash: str,
    timestamp: str,
) -> tuple[list[GeneratedSearchIntent], list[str]]:
    if ai_service is None:
        return [], []
    intents: list[GeneratedSearchIntent] = []
    errors: list[str] = []
    excludes = _exclude_terms(context)
    inputs = [*_source_inputs(context), "ai_expansion"]
    for content_kind in content_kinds:
        title, prompt = _build_ai_prompt(context, content_kind)
        expires_at = (
            datetime.fromisoformat(timestamp)
            + timedelta(hours=PROFILE_TTL_HOURS if content_kind == "profile_completion" else TIMELY_TTL_HOURS)
        ).isoformat()
        try:
            suggest = getattr(ai_service, "suggest_topic_search_queries")
            queries = suggest(title=title, prompt=prompt, time_range="30_days")
        except Exception as exc:
            errors.append(f"{content_kind}:{exc}")
            continue
        for index, query in enumerate(_dedupe([str(item) for item in queries], limit=4), start=1):
            intents.append(
                _make_intent(
                    scope=scope,
                    content_kind=content_kind,
                    query=query,
                    reason="AI 补强：扩展对象语境、用户关注和公开源搜索表达",
                    priority=82 - index,
                    exclude_terms=excludes,
                    source_inputs=inputs,
                    input_hash=input_hash,
                    expires_at=expires_at,
                )
            )
    return intents, errors


def _cap_intents(intents: list[GeneratedSearchIntent]) -> list[GeneratedSearchIntent]:
    capped: list[GeneratedSearchIntent] = []
    for content_kind in CONTENT_KINDS:
        kind_items = [item for item in intents if item.content_kind == content_kind and item.query]
        kind_items.sort(key=lambda item: (-item.priority, len(item.query), item.query))
        seen: set[str] = set()
        for item in kind_items:
            key = re.sub(r"\s+", "", item.query).lower()
            if key in seen:
                continue
            seen.add(key)
            capped.append(item)
            if sum(1 for existing in capped if existing.content_kind == content_kind) >= 12:
                break
    return capped


def _persist_intents(db: Database, intents: list[GeneratedSearchIntent], *, scope: IntelligenceSearchScope, content_kinds: list[str], input_hash: str) -> list[GeneratedSearchIntent]:
    timestamp = now_iso()
    saved: list[GeneratedSearchIntent] = []
    for item in intents:
        existing = db.fetchone(
            """
            SELECT id, created_at
            FROM intelligence_search_intents
            WHERE scope_type = ? AND scope_id = ? AND content_kind = ? AND query = ?
            """,
            (item.scope_type, item.scope_id, item.content_kind, item.query),
        )
        intent_id = str(existing["id"]) if existing else item.id
        created_at = str(existing["created_at"]) if existing else timestamp
        db.execute(
            """
            INSERT INTO intelligence_search_intents(
                id, scope_type, scope_id, client_id, project_module_id, content_kind,
                query, exclude_terms_json, source_inputs_json, reason, priority,
                status, input_hash, expires_at, generator_version, created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(scope_type, scope_id, content_kind, query) DO UPDATE SET
                client_id = excluded.client_id,
                project_module_id = excluded.project_module_id,
                exclude_terms_json = excluded.exclude_terms_json,
                source_inputs_json = excluded.source_inputs_json,
                reason = excluded.reason,
                priority = excluded.priority,
                status = excluded.status,
                input_hash = excluded.input_hash,
                expires_at = excluded.expires_at,
                generator_version = excluded.generator_version,
                updated_at = excluded.updated_at
            """,
            (
                intent_id,
                item.scope_type,
                item.scope_id,
                item.client_id,
                item.project_module_id,
                item.content_kind,
                item.query,
                to_json(item.exclude_terms),
                to_json(item.source_inputs),
                item.reason,
                item.priority,
                item.status,
                item.input_hash,
                item.expires_at,
                item.generator_version,
                created_at,
                timestamp,
            ),
        )
        item.id = intent_id
        saved.append(item)

    for content_kind in content_kinds:
        active_queries = [item.query for item in saved if item.content_kind == content_kind]
        if not active_queries:
            continue
        placeholders = ",".join(["?"] * len(active_queries))
        db.execute(
            f"""
            UPDATE intelligence_search_intents
            SET status = 'stale', updated_at = ?
            WHERE scope_type = ?
              AND scope_id = ?
              AND content_kind = ?
              AND input_hash <> ?
              AND query NOT IN ({placeholders})
            """,
            (timestamp, scope.scope_type, scope.scope_id, content_kind, input_hash, *active_queries),
        )
    return saved


def generate_intelligence_search_intents(
    db: Database,
    ai_service: object | None,
    *,
    scope_type: str,
    scope_id: str,
    content_kind: str | None = None,
    force: bool = False,
) -> SearchIntentGenerationResult:
    scope = resolve_intelligence_search_scope(db, scope_type=scope_type, scope_id=scope_id)
    content_kinds = [content_kind] if content_kind in CONTENT_KINDS else list(CONTENT_KINDS)
    context = _collect_context(db, scope)
    input_hash = _context_hash(context, content_kinds)
    timestamp = now_iso()
    if not force:
        existing_rows = db.fetchall(
            """
            SELECT *
            FROM intelligence_search_intents
            WHERE scope_type = ?
              AND scope_id = ?
              AND content_kind IN ({})
              AND input_hash = ?
              AND status = 'ready'
              AND (expires_at IS NULL OR expires_at > ?)
            ORDER BY content_kind ASC, priority DESC, updated_at DESC
            """.format(",".join(["?"] * len(content_kinds))),
            (scope.scope_type, scope.scope_id, *content_kinds, input_hash, timestamp),
        )
        counts = {kind: 0 for kind in content_kinds}
        for row in existing_rows:
            counts[str(row["content_kind"] or "")] = counts.get(str(row["content_kind"] or ""), 0) + 1
        if existing_rows and all(counts.get(kind, 0) >= 4 for kind in content_kinds):
            return SearchIntentGenerationResult(
                scope=scope,
                intents=[_intent_from_row(row) for row in existing_rows],
                status="ready",
                input_hash=input_hash,
                errors=[],
            )

    rule_intents = _build_rule_intents(
        scope=scope,
        context=context,
        content_kinds=content_kinds,
        input_hash=input_hash,
        timestamp=timestamp,
    )
    ai_intents, errors = _build_ai_intents(
        ai_service=ai_service,
        scope=scope,
        context=context,
        content_kinds=content_kinds,
        input_hash=input_hash,
        timestamp=timestamp,
    )
    saved = _persist_intents(
        db,
        _cap_intents([*rule_intents, *ai_intents]),
        scope=scope,
        content_kinds=content_kinds,
        input_hash=input_hash,
    )
    return SearchIntentGenerationResult(
        scope=scope,
        intents=saved,
        status="ready" if saved else "failed",
        input_hash=input_hash,
        errors=errors,
    )


def _intent_from_row(row) -> GeneratedSearchIntent:
    return GeneratedSearchIntent(
        id=str(row["id"] or ""),
        scope_type=str(row["scope_type"] or ""),
        scope_id=str(row["scope_id"] or ""),
        client_id=str(row["client_id"] or ""),
        project_module_id=str(row["project_module_id"] or "") or None,
        content_kind=str(row["content_kind"] or ""),
        query=str(row["query"] or ""),
        exclude_terms=_as_text_list(_safe_json(str(row["exclude_terms_json"] or "[]"), []), limit=20),
        source_inputs=_as_text_list(_safe_json(str(row["source_inputs_json"] or "[]"), []), limit=20),
        reason=str(row["reason"] or ""),
        priority=int(row["priority"] or 0),
        status=str(row["status"] or "ready"),
        input_hash=str(row["input_hash"] or ""),
        expires_at=str(row["expires_at"] or ""),
        generator_version=str(row["generator_version"] or GENERATOR_VERSION),
    )


def _fetch_public_search_samples(query: str, *, timeout_seconds: float = 8.0) -> list[dict[str, str]]:
    return [
        {"title": item.title, "url": item.url}
        for item in search_public_web(query, max_results=5, timeout_seconds=timeout_seconds)
    ]


def run_intelligence_search_diagnostic(
    db: Database,
    *,
    scope: IntelligenceSearchScope,
    intents: list[GeneratedSearchIntent],
    trigger_source: str = "manual",
    providers: list[str] | None = None,
    max_intents: int = 6,
    sample_fetcher: Callable[[str], list[dict[str, str]]] | None = None,
) -> list[SearchDiagnosticResult]:
    selected_providers = providers or ["public_search_cn"]
    fetcher = sample_fetcher or _fetch_public_search_samples
    selected = sorted(intents, key=lambda item: (-item.priority, item.content_kind, item.query))[:max_intents]
    results: list[SearchDiagnosticResult] = []
    timestamp = now_iso()
    for intent in selected:
        for provider in selected_providers:
            started = time.perf_counter()
            raw_samples: list[dict[str, str]] = []
            status = "success"
            failure_reason = ""
            try:
                raw_samples = fetcher(intent.query)
            except Exception as exc:
                status = "failed"
                failure_reason = _clean_text(exc, max_len=240)
            deduped: list[dict[str, str]] = []
            seen_urls: set[str] = set()
            for hit in raw_samples:
                title = _clean_text(hit.get("title"), max_len=180)
                url = _clean_text(hit.get("url"), max_len=320)
                if not title or not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                deduped.append({"title": title, "url": url})
                if len(deduped) >= 3:
                    break
            if status == "success" and not deduped:
                status = "no_results"
            duration_ms = int((time.perf_counter() - started) * 1000)
            result = SearchDiagnosticResult(
                intent_id=intent.id,
                query=intent.query,
                content_kind=intent.content_kind,
                status=status,
                provider=provider,
                raw_count=len(raw_samples),
                deduped_count=len(seen_urls),
                sample_hits=deduped,
                failure_reason=failure_reason,
                duration_ms=duration_ms,
            )
            db.execute(
                """
                INSERT INTO intelligence_search_diagnostics(
                    id, scope_type, scope_id, client_id, project_module_id, content_kind,
                    intent_id, query, trigger_source, provider, status, raw_count,
                    deduped_count, sample_hits_json, failure_reason, duration_ms, created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _new_id("isdiag"),
                    scope.scope_type,
                    scope.scope_id,
                    scope.client_id,
                    scope.project_module_id,
                    intent.content_kind,
                    intent.id,
                    intent.query,
                    trigger_source,
                    provider,
                    status,
                    len(raw_samples),
                    len(seen_urls),
                    to_json(deduped),
                    failure_reason,
                    duration_ms,
                    timestamp,
                ),
            )
            results.append(result)
    return results


def select_enrichment_seed_queries(
    scope: IntelligenceSearchScope,
    intents: list[GeneratedSearchIntent],
    diagnostics: list[SearchDiagnosticResult] | None = None,
    *,
    limit: int = 8,
) -> EnrichmentSeedSelection:
    success_by_query = {
        result.query: result
        for result in diagnostics or []
        if result.status in {"success", "no_results"} or result.deduped_count > 0
    }
    ordered = sorted(intents, key=lambda item: (-item.priority, item.content_kind, item.query))
    selected: list[str] = []
    for item in ordered:
        if diagnostics and item.query not in success_by_query and item.priority < 90:
            continue
        if item.query not in selected:
            selected.append(item.query)
        if len(selected) >= limit:
            break
    if len(selected) < min(limit, 4):
        for item in ordered:
            if item.query not in selected:
                selected.append(item.query)
            if len(selected) >= limit:
                break
    gaps = _dedupe(
        [
            item.reason
            for item in ordered
            if item.content_kind == "profile_completion"
            and item.reason
            and not item.reason.startswith("AI 补强")
        ],
        limit=8,
    )
    if not gaps:
        gaps = [
            "登记信息、信息公开、年报或官网资料",
            "项目介绍、服务对象规模、执行方法和合作方",
            "项目成效、公开报告和仍需用户补充的信息",
        ]
    return EnrichmentSeedSelection(seed_queries=selected, gaps=gaps)


def get_search_intent_status_for_scope(
    db: Database,
    *,
    scope_type: str,
    scope_id: str,
) -> tuple[str, str | None]:
    normalized_type = _normalize_scope_type(scope_type)
    normalized_id = str(scope_id or "").strip()
    rows = db.fetchall(
        """
        SELECT status, expires_at, updated_at
        FROM intelligence_search_intents
        WHERE scope_type = ? AND scope_id = ?
        ORDER BY updated_at DESC
        """,
        (normalized_type, normalized_id),
    )
    if not rows:
        return "missing", "搜索意图尚未生成，下一次补全互联网资料时会先生成关键词/搜索意图。"
    statuses = {str(row["status"] or "ready") for row in rows}
    if "running" in statuses:
        return "running", "搜索意图正在刷新，列表内容可能短暂落后。"
    if "failed" in statuses:
        return "failed", "搜索意图生成或诊断失败，当前会退回规则关键词。"
    current = now_iso()
    if "stale" in statuses or any(str(row["expires_at"] or "") and str(row["expires_at"]) <= current for row in rows):
        return "stale", "搜索意图已过期或底层资料已变化，建议刷新互联网资料补全。"
    return "ready", None
