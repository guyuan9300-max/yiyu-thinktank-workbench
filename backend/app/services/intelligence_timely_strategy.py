from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from app.db import Database, from_json


TIMELY_STRATEGY_ROUTES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("政策监管", ("政策", "监管", "通知", "办法", "规范", "民政")),
    ("资助申报", ("资助", "申报", "公益创投", "征集", "扶持")),
    ("采购招标", ("采购", "招标", "政府购买服务", "比选", "中标")),
    ("合作方动态", ("合作方", "资助方", "伙伴", "联合", "动态")),
    ("同类机构动态", ("同类机构", "项目", "案例", "发布", "启动")),
    ("行业风险", ("风险", "合规", "公开募捐", "处罚", "整改", "审计")),
    ("项目/方法趋势", ("方法", "模式", "课程", "平台", "培训", "AI")),
    ("新闻舆情", ("新闻", "报道", "舆情", "争议", "回应")),
)

REGION_TERMS = (
    "全国", "广东", "广州", "深圳", "佛山", "东莞", "珠海", "北京", "上海", "江苏", "浙江",
    "四川", "湖南", "湖北", "福建", "山东", "广西", "海南", "香港", "澳门",
)
SERVICE_TARGET_TERMS = (
    "儿童心理健康", "儿童青少年心理健康", "困境儿童", "儿童", "青少年", "心理健康",
    "教师心理素养", "社区服务", "公益组织数字化", "公益组织", "社会组织", "基金会",
    "AI公益", "公益数字化", "组织工作台", "心理平台",
)
METHOD_TERMS = (
    "心灵魔法学院", "心盛计划", "课程", "培训", "平台", "工具", "工作台", "案例",
    "研究", "观点", "文章", "服务方案", "陪伴", "咨询", "组织发展", "数字化",
)
CONSTRAINT_TERMS = (
    "公开募捐", "合规", "监管", "登记", "信息公开", "年报", "审计", "资格", "备案",
)
DECISION_SIGNAL_TERMS = (
    "申报", "征集", "截止", "资助", "扶持", "招标", "采购", "中标", "比选",
    "监管", "合规", "公开募捐", "处罚", "风险", "整改", "规范", "政策", "通知",
    "合作", "联合", "伙伴", "发布", "启动", "试点", "培训", "课程", "平台",
)
TRANSFER_TERMS = (
    "影响", "适用", "面向", "针对", "要求", "资格", "条件", "对象", "地域", "材料",
    "合作", "申报", "参与", "纳入", "需要", "限制", "窗口", "机会", "风险", "约束",
)
LOW_VALUE_TIMELY_TERMS = (
    "招聘", "岗位", "职位", "薪资", "职友集", "BOSS直聘", "看准网", "猎聘", "智联招聘",
)
WINDOW_TERMS = (
    "截止", "报名", "申报", "征集", "有效期", "实施期", "执行期", "试点期", "自", "至",
    "仍在", "持续", "长期有效", "正在征集", "正在申报",
)


@dataclass
class TimelyResearchStrategy:
    scope_type: str
    scope_id: str
    client_id: str
    project_module_id: str | None
    object_name: str
    profile_ready: bool
    profile_score: int
    profile_gaps: list[str] = field(default_factory=list)
    identity_terms: list[str] = field(default_factory=list)
    focus_topics: list[str] = field(default_factory=list)
    service_targets: list[str] = field(default_factory=list)
    regions: list[str] = field(default_factory=list)
    project_terms: list[str] = field(default_factory=list)
    method_terms: list[str] = field(default_factory=list)
    partner_terms: list[str] = field(default_factory=list)
    constraint_terms: list[str] = field(default_factory=list)
    profile_tags: dict[str, list[str]] = field(default_factory=dict)
    tag_weights: dict[str, int] = field(default_factory=dict)
    search_atoms: list[str] = field(default_factory=list)
    routes: list[dict[str, object]] = field(default_factory=list)
    source_counts: dict[str, int] = field(default_factory=dict)

    def as_payload(self) -> dict[str, object]:
        return {
            "scopeType": self.scope_type,
            "scopeId": self.scope_id,
            "clientId": self.client_id,
            "projectModuleId": self.project_module_id,
            "objectName": self.object_name,
            "profileReady": self.profile_ready,
            "profileScore": self.profile_score,
            "profileGaps": self.profile_gaps,
            "identityTerms": self.identity_terms,
            "focusTopics": self.focus_topics,
            "serviceTargets": self.service_targets,
            "regions": self.regions,
            "projectTerms": self.project_terms,
            "methodTerms": self.method_terms,
            "partnerTerms": self.partner_terms,
            "constraintTerms": self.constraint_terms,
            "profileTags": self.profile_tags,
            "tagWeights": self.tag_weights,
            "searchAtoms": self.search_atoms,
            "routes": self.routes,
            "sourceCounts": self.source_counts,
        }


def _clean_text(value: object, *, max_len: int = 240) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:max_len]


def _safe_json(value: object, default: object) -> object:
    try:
        return from_json(str(value or ""), default)
    except Exception:
        return default


def _row_dict(row: Any) -> dict[str, object]:
    if row is None:
        return {}
    try:
        return {key: row[key] for key in row.keys()}
    except Exception:
        return dict(row)


def _table_exists(db: Database, table_name: str) -> bool:
    try:
        return bool(
            db.fetchone(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table_name,),
            )
        )
    except Exception:
        return False


def _has_column(db: Database, table_name: str, column_name: str) -> bool:
    try:
        return db.has_column(table_name, column_name)
    except Exception:
        return False


def _as_text_list(value: object, *, limit: int = 12) -> list[str]:
    if value is None:
        raw_items: list[object] = []
    elif isinstance(value, str):
        raw_items = re.split(r"[\n,，;；、/|]+", value)
    elif isinstance(value, dict):
        raw_items = list(value.values())
    elif isinstance(value, (list, tuple, set)):
        raw_items = list(value)
    else:
        raw_items = [value]
    items: list[str] = []
    for item in raw_items:
        text = _clean_text(item, max_len=120)
        if text and text not in items:
            items.append(text)
        if len(items) >= limit:
            break
    return items


def _dedupe(items: list[str], *, limit: int = 20) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _clean_text(item, max_len=120)
        key = re.sub(r"\s+", "", text).lower()
        if not text or key in seen:
            continue
        seen.add(key)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def _hits(corpus: str, terms: tuple[str, ...] | list[str], *, limit: int = 10) -> list[str]:
    found: list[str] = []
    for term in terms:
        if term and term in corpus and term not in found:
            found.append(term)
        if len(found) >= limit:
            break
    return found


def _is_probable_url_term(term: str) -> bool:
    text = _clean_text(term, max_len=120).lower()
    if not text:
        return False
    return bool(re.search(r"https?://|www\.|[a-z0-9-]+\.[a-z]{2,}", text)) and not _contains_cjk(text)


def _add_weighted_terms(weights: dict[str, int], terms: list[str], weight: int) -> None:
    for term in terms:
        text = _clean_text(term, max_len=80)
        if not text or _is_probable_url_term(text):
            continue
        current = int(weights.get(text) or 0)
        weights[text] = max(current, weight)


def _contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def _focus_terms_from_directives(rows: list[dict[str, object]]) -> tuple[list[str], list[str], list[str]]:
    profile: list[str] = []
    timely: list[str] = []
    excludes: list[str] = []
    for row in rows:
        profile.extend(_as_text_list(_safe_json(row.get("profile_completion_focus_json"), []), limit=16))
        timely.extend(_as_text_list(_safe_json(row.get("timely_intelligence_focus_json"), []), limit=16))
        excludes.extend(_as_text_list(_safe_json(row.get("exclude_json"), []), limit=16))
    return _dedupe(profile, limit=18), _dedupe(timely, limit=18), _dedupe(excludes, limit=18)


def _terms_from_focus(lines: list[str], *, limit: int = 16) -> list[str]:
    terms: list[str] = []
    for line in lines:
        for token in re.split(r"[\s,，;；、。.!！？? |/()（）《》“”\"'：:]+", line):
            text = _clean_text(token, max_len=36)
            if len(text) < 2:
                continue
            if text in {"官网", "资料", "关注", "相关", "有关", "方向", "案例", "信息", "动态"}:
                continue
            if _is_probable_url_term(text):
                continue
            terms.append(text.lower().removeprefix("www.") if "." in text else text)
        for match in re.findall(r"[“《]?([\u4e00-\u9fffA-Za-z0-9]{2,24}(?:计划|项目|学院|平台|课程|工作台|案例|观点|文章|服务方案))[”》]?", line):
            terms.append(match)
    return _dedupe(terms, limit=limit)


def _project_like_terms(corpus: str) -> list[str]:
    matches = re.findall(r"[“《]?([\u4e00-\u9fffA-Za-z0-9]{2,24}(?:计划|项目|学院|平台|课程|工作台|服务方案))[”》]?", corpus)
    return _dedupe(matches, limit=10)


def _load_directives(db: Database, *, scope_type: str, scope_id: str, client_id: str, project_module_id: str | None) -> list[dict[str, object]]:
    keys: list[tuple[str, str]] = [("global", ""), (scope_type, scope_id)]
    if client_id:
        keys.append(("client", client_id))
    if project_module_id:
        keys.append(("project_module", project_module_id))
    seen: set[tuple[str, str]] = set()
    keys = [key for key in keys if not (key in seen or seen.add(key))]
    clauses = " OR ".join(["(scope_type = ? AND scope_id = ?)"] * len(keys))
    params: list[object] = []
    for key in keys:
        params.extend(key)
    rows = db.fetchall(
        f"SELECT * FROM intelligence_focus_directives WHERE {clauses} ORDER BY updated_at DESC",
        tuple(params),
    )
    return [_row_dict(row) for row in rows]


def build_timely_research_strategy(
    db: Database,
    *,
    scope_type: str,
    scope_id: str,
    client_id: str,
    project_module_id: str | None = None,
    display_name: str = "",
) -> TimelyResearchStrategy:
    client = _row_dict(db.fetchone("SELECT * FROM clients WHERE id = ?", (client_id,))) if client_id else {}
    project = (
        _row_dict(db.fetchone("SELECT * FROM project_modules WHERE id = ?", (project_module_id,)))
        if project_module_id and _table_exists(db, "project_modules")
        else {}
    )
    project_rows = (
        [project]
        if project
        else [
            _row_dict(row)
            for row in db.fetchall(
                "SELECT * FROM project_modules WHERE client_id = ? ORDER BY updated_at DESC LIMIT 10",
                (client_id,),
            )
        ]
        if _table_exists(db, "project_modules")
        else []
    )
    flow_rows = (
        [
            _row_dict(row)
            for row in db.fetchall(
                "SELECT * FROM project_flows WHERE client_id = ? ORDER BY updated_at DESC LIMIT 12",
                (client_id,),
            )
        ]
        if _table_exists(db, "project_flows")
        else []
    )
    profile_rows = [
        _row_dict(row)
        for row in db.fetchall(
            """
            SELECT title, summary, key_points_json, analysis, impact, tags_json, source, published_at
            FROM intelligence_items
            WHERE scope_type = ? AND scope_id = ?
              AND content_kind = 'profile_completion'
              AND user_status = 'active'
            ORDER BY captured_at DESC
            LIMIT 40
            """,
            (scope_type, scope_id),
        )
    ]
    data_rows: list[Any] = []
    if _table_exists(db, "data_center_ingest_events"):
        if project_module_id and _has_column(db, "data_center_ingest_events", "project_module_id"):
            data_rows = db.fetchall(
                """
                SELECT title, source_type, content_domain, metadata_json, updated_at
                FROM data_center_ingest_events
                WHERE lifecycle_status = 'active'
                  AND COALESCE(source_type, '') <> 'external_intelligence'
                  AND (client_id = ? OR project_module_id = ?)
                ORDER BY updated_at DESC
                LIMIT 24
                """,
                (client_id, project_module_id),
            )
        else:
            data_rows = db.fetchall(
                """
                SELECT title, source_type, content_domain, metadata_json, updated_at
                FROM data_center_ingest_events
                WHERE lifecycle_status = 'active'
                  AND COALESCE(source_type, '') <> 'external_intelligence'
                  AND client_id = ?
                ORDER BY updated_at DESC
                LIMIT 24
                """,
                (client_id,),
            )
    data_items = [_row_dict(row) for row in data_rows]
    knowledge_items = (
        [
            _row_dict(row)
            for row in db.fetchall(
                """
                SELECT title, overview_summary, retrieval_summary, document_role, query_hints_json,
                       distinct_findings_json, entities_json, time_markers_json
                FROM knowledge_surrogates
                WHERE client_id = ?
                ORDER BY updated_at DESC
                LIMIT 12
                """,
                (client_id,),
            )
        ]
        if _table_exists(db, "knowledge_surrogates")
        else []
    )
    strategic_profile = (
        _row_dict(db.fetchone("SELECT * FROM client_strategic_profiles WHERE client_id = ?", (client_id,)))
        if _table_exists(db, "client_strategic_profiles")
        else {}
    )
    directives = _load_directives(db, scope_type=scope_type, scope_id=scope_id, client_id=client_id, project_module_id=project_module_id)
    profile_focus, timely_focus, _excludes = _focus_terms_from_directives(directives)
    object_name = _clean_text(project.get("name") or client.get("name") or display_name or scope_id, max_len=80)
    identity_terms = _dedupe(
        [
            object_name,
            _clean_text(client.get("alias"), max_len=80),
            _clean_text(client.get("domain"), max_len=80),
            _clean_text(project.get("name"), max_len=80),
        ],
        limit=8,
    )
    corpus_parts: list[str] = [
        _clean_text(client.get("name"), max_len=200),
        _clean_text(client.get("alias"), max_len=200),
        _clean_text(client.get("domain"), max_len=200),
        _clean_text(client.get("intro"), max_len=1200),
        _clean_text(client.get("stage"), max_len=120),
        _clean_text(strategic_profile.get("industry"), max_len=500),
        _clean_text(strategic_profile.get("current_needs"), max_len=500),
        _clean_text(strategic_profile.get("pain_points"), max_len=500),
    ]
    for row in project_rows[:10]:
        corpus_parts.extend(
            [
                _clean_text(row.get("name"), max_len=160),
                _clean_text(row.get("goal"), max_len=600),
                _clean_text(row.get("description"), max_len=800),
                " ".join(_as_text_list(_safe_json(row.get("keywords_json"), []), limit=10)),
            ]
        )
    for row in flow_rows[:8]:
        corpus_parts.extend([_clean_text(row.get("name"), max_len=120), _clean_text(row.get("risk_points_json"), max_len=500)])
    for row in profile_rows[:24]:
        corpus_parts.extend(
            [
                _clean_text(row.get("title"), max_len=180),
                _clean_text(row.get("summary"), max_len=800),
                " ".join(_as_text_list(_safe_json(row.get("key_points_json"), []), limit=8)),
                " ".join(_as_text_list(_safe_json(row.get("tags_json"), []), limit=8)),
            ]
        )
    for row in data_items[:20]:
        metadata = _safe_json(row.get("metadata_json"), {})
        corpus_parts.extend([_clean_text(row.get("title"), max_len=180), _clean_text(metadata, max_len=800)])
    for row in knowledge_items[:12]:
        corpus_parts.extend(
            [
                _clean_text(row.get("title"), max_len=160),
                _clean_text(row.get("overview_summary"), max_len=600),
                _clean_text(row.get("retrieval_summary"), max_len=600),
                " ".join(_as_text_list(_safe_json(row.get("query_hints_json"), []), limit=8)),
                " ".join(_as_text_list(_safe_json(row.get("distinct_findings_json"), []), limit=8)),
            ]
        )
    # Keep the two user instruction channels separate. Profile-completion focus
    # is for filling static materials; timely strategy should use verified
    # object materials plus timely-specific focus, not profile-only instructions
    # such as "官网/栏目".
    corpus_parts.extend(timely_focus)
    corpus = " ".join(part for part in corpus_parts if part)

    focus_topics = _dedupe(_terms_from_focus(timely_focus, limit=14), limit=18)
    service_targets = _hits(corpus, SERVICE_TARGET_TERMS, limit=10)
    regions = _hits(corpus, REGION_TERMS, limit=6)
    project_terms = _dedupe(
        [
            *[_clean_text(row.get("name"), max_len=60) for row in project_rows],
            *_project_like_terms(corpus),
            *[term for term in focus_topics if any(marker in term for marker in ("计划", "项目", "学院", "平台", "工作台"))],
        ],
        limit=12,
    )
    method_terms = _dedupe([*_hits(corpus, METHOD_TERMS, limit=12), *[term for term in focus_topics if term not in project_terms]], limit=12)
    partner_terms = _dedupe(re.findall(r"([\u4e00-\u9fffA-Za-z0-9]{2,24}(?:基金会|公益|资助方|合作方|伙伴))", corpus), limit=8)
    constraint_terms = _hits(corpus, CONSTRAINT_TERMS, limit=8)
    resource_terms = _hits(corpus, ["资助", "申报", "政府购买服务", "采购", "招标", "合作", "资源", "资金", "项目支持", "能力建设"], limit=8)
    domain_terms = _dedupe([_clean_text(client.get("domain"), max_len=80), _clean_text(strategic_profile.get("industry"), max_len=80)], limit=5)
    profile_tags: dict[str, list[str]] = {
        "identity": identity_terms,
        "domain": domain_terms,
        "serviceTargets": service_targets,
        "regions": regions,
        "projects": project_terms,
        "methods": method_terms,
        "resourceNeeds": resource_terms,
        "partners": partner_terms,
        "constraints": constraint_terms,
        "focus": focus_topics,
        "exclude": _excludes,
    }
    tag_weights: dict[str, int] = {}
    _add_weighted_terms(tag_weights, focus_topics, 100)
    _add_weighted_terms(tag_weights, service_targets, 82 if profile_rows else 72)
    _add_weighted_terms(tag_weights, project_terms, 80 if profile_rows else 68)
    _add_weighted_terms(tag_weights, method_terms, 76 if profile_rows else 66)
    _add_weighted_terms(tag_weights, resource_terms, 72)
    _add_weighted_terms(tag_weights, constraint_terms, 70)
    _add_weighted_terms(tag_weights, partner_terms, 66)
    _add_weighted_terms(tag_weights, regions, 58)
    _add_weighted_terms(tag_weights, domain_terms, 56)
    _add_weighted_terms(tag_weights, identity_terms, 35)
    weighted_atoms = sorted(tag_weights.items(), key=lambda item: (-item[1], len(item[0]), item[0]))
    search_atoms = _dedupe(
        [
            term
            for term, weight in weighted_atoms
            if weight >= 56 and term not in identity_terms
        ],
        limit=24,
    )
    if not search_atoms:
        search_atoms = _dedupe([*service_targets, *method_terms, *domain_terms, "公益"], limit=4)

    score = 0
    if object_name and (_clean_text(client.get("domain")) or _clean_text(client.get("intro")) or project_terms):
        score += 20
    if profile_rows:
        score += 25
    elif data_items or knowledge_items:
        score += 15
    if service_targets:
        score += 18
    if project_terms or method_terms:
        score += 18
    if focus_topics:
        score += 16
    if regions or partner_terms or constraint_terms:
        score += 8
    score = min(score, 100)
    profile_gaps: list[str] = []
    if not object_name or not (_clean_text(client.get("domain")) or _clean_text(client.get("intro"))):
        profile_gaps.append("客户身份/基础介绍")
    if not service_targets:
        profile_gaps.append("服务对象/业务方向")
    if not project_terms and not method_terms:
        profile_gaps.append("项目/方法")
    if not profile_rows and not data_items and not knowledge_items:
        profile_gaps.append("本地资料/已核验资料")
    if not focus_topics:
        profile_gaps.append("重点关注")
    profile_ready = score >= 50 and len(profile_gaps) <= 3

    routes: list[dict[str, object]] = []
    for label, keywords in TIMELY_STRATEGY_ROUTES:
        if label == "资助申报":
            route_atoms = [*focus_topics, *service_targets, *project_terms]
        elif label == "采购招标":
            route_atoms = [*focus_topics, *regions, *service_targets, *project_terms, *method_terms]
        elif label == "政策监管":
            route_atoms = [*focus_topics, *regions, *service_targets, *constraint_terms]
        elif label == "行业风险":
            route_atoms = [*focus_topics, *constraint_terms, *service_targets]
        elif label == "项目/方法趋势":
            route_atoms = [*focus_topics, *method_terms, *project_terms, *service_targets]
        elif label == "合作方动态":
            route_atoms = [*focus_topics, *partner_terms, *project_terms, *service_targets]
        elif label == "同类机构动态":
            route_atoms = [*focus_topics, *service_targets, *method_terms, *project_terms]
        else:
            route_atoms = [*focus_topics, *service_targets, *project_terms]
        routes.append(
            {
                "label": label,
                "keywords": list(keywords),
                "atoms": _dedupe(route_atoms or search_atoms, limit=8),
                "decisionSignals": [term for term in keywords if term in DECISION_SIGNAL_TERMS][:6],
            }
        )

    return TimelyResearchStrategy(
        scope_type=scope_type,
        scope_id=scope_id,
        client_id=client_id,
        project_module_id=project_module_id,
        object_name=object_name,
        profile_ready=profile_ready,
        profile_score=score,
        profile_gaps=_dedupe(profile_gaps, limit=8),
        identity_terms=identity_terms,
        focus_topics=focus_topics,
        service_targets=service_targets,
        regions=regions,
        project_terms=project_terms,
        method_terms=method_terms,
        partner_terms=partner_terms,
        constraint_terms=constraint_terms,
        profile_tags=profile_tags,
        tag_weights=tag_weights,
        search_atoms=search_atoms,
        routes=routes,
        source_counts={
            "profileItems": len(profile_rows),
            "dataCenterItems": len(data_items),
            "knowledgeSurrogates": len(knowledge_items),
            "projects": len(project_rows),
            "flows": len(flow_rows),
            "focusDirectives": len(directives),
        },
    )


def strategy_source_inputs(strategy: TimelyResearchStrategy | dict[str, object]) -> list[str]:
    payload = strategy.as_payload() if isinstance(strategy, TimelyResearchStrategy) else strategy
    return [
        "timely_strategy:v1",
        f"timely_profile_ready:{1 if payload.get('profileReady') else 0}",
        f"timely_profile_score:{int(payload.get('profileScore') or 0)}",
        f"timely_strategy_routes:{len(payload.get('routes') or [])}",
    ]


def _payload_list(payload: dict[str, object], key: str, *, limit: int = 20) -> list[str]:
    return _dedupe(_as_text_list(payload.get(key), limit=limit), limit=limit)


def _profile_tag_terms(payload: dict[str, object], *, limit: int = 32) -> list[str]:
    tags = payload.get("profileTags")
    if not isinstance(tags, dict):
        return []
    items: list[str] = []
    for key in ("focus", "serviceTargets", "projects", "methods", "resourceNeeds", "constraints", "regions", "domain"):
        items.extend(_as_text_list(tags.get(key), limit=12))
    return _dedupe(items, limit=limit)


def evaluate_timely_strategy_match(text: str, strategy: TimelyResearchStrategy | dict[str, object] | None) -> dict[str, object]:
    payload = strategy.as_payload() if isinstance(strategy, TimelyResearchStrategy) else (strategy or {})
    corpus = _clean_text(text, max_len=6000)
    if not corpus:
        return {"ok": False, "reason": "正文为空，无法进行情报策略复核"}
    if any(term in corpus for term in LOW_VALUE_TIMELY_TERMS):
        return {"ok": False, "reason": "招聘、岗位或低价值站点信息不属于当前时效情报监测范围"}
    focus_terms = _dedupe(
        [
            *_payload_list(payload, "searchAtoms", limit=24),
            *_payload_list(payload, "focusTopics", limit=18),
            *_payload_list(payload, "serviceTargets", limit=12),
            *_payload_list(payload, "projectTerms", limit=12),
            *_payload_list(payload, "methodTerms", limit=12),
            *_profile_tag_terms(payload, limit=32),
        ],
        limit=40,
    )
    route_hits: list[str] = []
    for route in payload.get("routes") or []:
        if not isinstance(route, dict):
            continue
        label = _clean_text(route.get("label"), max_len=40)
        keywords = _as_text_list(route.get("keywords"), limit=8)
        if label and (label in corpus or any(keyword in corpus for keyword in keywords)):
            route_hits.append(label)
    focus_hits = _hits(corpus, focus_terms, limit=10)
    decision_hits = _hits(corpus, DECISION_SIGNAL_TERMS, limit=10)
    transfer_hits = _hits(corpus, TRANSFER_TERMS, limit=10)
    object_hits = _hits(corpus, _payload_list(payload, "identityTerms", limit=10), limit=6)
    if not route_hits:
        return {"ok": False, "reason": "未命中任何情报监测路线，暂不成卡", "focusHits": focus_hits}
    if not focus_hits and not object_hits:
        return {"ok": False, "reason": "未回应当前对象画像或重点关注，暂不成卡", "routeHits": route_hits}
    if not decision_hits:
        return {"ok": False, "reason": "缺少机会、风险、约束、合作或趋势等决策相关信号", "routeHits": route_hits, "focusHits": focus_hits}
    if not transfer_hits:
        return {"ok": False, "reason": "缺少适用对象、条件、窗口或影响链条证据", "routeHits": route_hits, "focusHits": focus_hits}
    return {
        "ok": True,
        "reason": "候选内容命中对象画像、监测路线和决策相关信号",
        "routeHits": _dedupe(route_hits, limit=6),
        "focusHits": focus_hits,
        "decisionSignals": decision_hits,
        "transferSignals": transfer_hits,
        "objectHits": object_hits,
    }


def _parse_date(value: str) -> datetime | None:
    match = re.search(r"(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})", value)
    if not match:
        return None
    try:
        return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def timely_effective_window_reason(text: str, *, timestamp: str) -> str | None:
    corpus = _clean_text(text, max_len=6000)
    if not corpus or not any(term in corpus for term in WINDOW_TERMS):
        return None
    try:
        now_dt = datetime.fromisoformat(timestamp[:19])
    except Exception:
        now_dt = datetime.now()
    for match in re.finditer(r"(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})", corpus):
        dt = _parse_date(match.group(0))
        if not dt:
            continue
        window_text = corpus[max(0, match.start() - 30): match.end() + 30]
        if dt >= now_dt - timedelta(days=1) and any(term in window_text for term in WINDOW_TERMS):
            return f"正文显示仍处有效窗口：{dt.date().isoformat()}"
    current_or_future_year = str(now_dt.year) in corpus or str(now_dt.year + 1) in corpus
    if current_or_future_year and any(term in corpus for term in ("长期有效", "持续征集", "正在征集", "仍在申报", "有效期")):
        return "正文显示该事项仍在征集、申报或有效期内"
    return None
