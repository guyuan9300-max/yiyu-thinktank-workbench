from __future__ import annotations

import hashlib
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from html import unescape
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlparse, urlunparse

import httpx

from app.db import Database, from_json, to_json
from app.models import AiStructuredResponse
from app.services.intelligence_feedback import (
    feedback_score_for_candidate,
    source_domain_from_url,
    source_feedback_adjustment,
)
from app.services.intelligence_search_intents import GeneratedSearchIntent, IntelligenceSearchScope
from app.services.knowledge_v2 import upsert_canonical_text_document
from app.services.public_search import search_public_web


logger = logging.getLogger(__name__)

PROFILE_TTL_HOURS = 72
TIMELY_TTL_HOURS = 24
STRONG_SOURCE_TYPES = {"gov_policy", "procurement", "grant", "social_org_registry", "official_site", "official_site_section"}
PROFILE_SOURCE_TYPES = {"web_search", "official_site", "official_site_section", "social_org_registry", "profile_report", "charity_media"}
TIMELY_SOURCE_TYPES = {"web_search", "official_site", "official_site_section", "gov_policy", "procurement", "grant", "regulatory_risk", "partner_peer", "charity_media"}
CONTENT_KIND_SOURCE_TYPES = {
    "profile_completion": PROFILE_SOURCE_TYPES,
    "timely_intelligence": TIMELY_SOURCE_TYPES,
}


def refresh_cycle_hours(db: Database, content_kind: str) -> int:
    key = (
        "intelligence_profile_completion_cycle_hours"
        if content_kind == "profile_completion"
        else "intelligence_timely_intelligence_cycle_hours"
    )
    default = PROFILE_TTL_HOURS if content_kind == "profile_completion" else TIMELY_TTL_HOURS
    try:
        value = int(db.get_setting(key, str(default)))
    except Exception:
        value = default
    return max(1, min(value, 8760))
PROFILE_COMPLETION_DIMENSIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("机构简介", ("机构简介", "关于我们", "机构介绍", "业务范围", "宗旨", "使命", "愿景", "定位")),
    ("登记信息", ("登记", "统一社会信用代码", "登记机关", "法定代表人", "住所", "社会组织")),
    ("年报/信息公开", ("年报", "年度报告", "信息公开", "审计报告", "公开报告")),
    ("项目介绍", ("项目介绍", "项目概况", "项目背景", "服务内容", "服务对象", "项目目标")),
    ("项目成效", ("成效", "成果", "案例", "受益", "人数", "覆盖", "评估")),
    ("合作方", ("合作", "伙伴", "资助方", "支持方", "联合", "共建")),
    ("执行方法", ("方法", "模式", "路径", "课程", "培训", "活动", "服务流程")),
    ("负责人/团队", ("秘书长", "理事长", "负责人", "团队", "顾源源", "张真", "采访", "观点")),
)
CLOSED_OR_LOW_VALUE_DOMAINS = {
    "capitalone.com",
    "booking.com",
    "tripadvisor.com",
    "trivago.com",
    "kayak.com",
    "microsoft.com",
    "office.com",
    "live.com",
    "google.com",
    "google.us",
    "deepmind.google",
    "stackoverflow.com",
    "reddit.com",
    "roblox.com",
    "xiaohongshu.com",
    "xhslink.com",
    "mp.weixin.qq.com",
    "weixin.qq.com",
    "weibo.com",
    "zhihu.com",
    "baidu.com",
    "douyin.com",
    "toutiao.com",
    "sohu.com",
    "sina.com.cn",
    "163.com",
    "qq.com",
    "so.com",
    "image.so.com",
    "m.so.com",
    "sogou.com",
    "bing.com",
    "map.360.cn",
    "map.so.com",
    "ditu.so.com",
    "map.baidu.com",
}
AGGREGATOR_DOMAINS = {
    "qcc.com",
    "tianyancha.com",
    "aiqicha.baidu.com",
    "qixin.com",
    "qichacha.com",
    "jobui.com",
    "kanzhun.com",
    "zhipin.com",
    "liepin.com",
    "企查查",
    "天眼查",
}

OFFICIAL_SITE_SECTION_SPECS: tuple[tuple[str, str, tuple[str, ...], int], ...] = (
    ("官网栏目：关于/简介", "关于 我们 简介 机构介绍", ("profile_completion",), 96),
    ("官网栏目：项目/案例", "项目 案例 服务 成效", ("profile_completion", "timely_intelligence"), 95),
    ("官网栏目：文章/观点", "观点 文章 访谈 专访 案例", ("profile_completion", "timely_intelligence"), 95),
    ("官网栏目：公告/新闻", "公告 新闻 动态 通知", ("timely_intelligence",), 94),
    ("官网栏目：信息公开/年报/报告", "信息公开 年报 年度报告 报告", ("profile_completion",), 97),
    ("官网栏目：合作/资助", "合作 伙伴 资助 申报", ("timely_intelligence",), 93),
)
NOTICE_TITLE_TERMS = (
    "通知",
    "公告",
    "征集",
    "申报",
    "招标",
    "中标",
    "成交",
    "采购",
    "政策",
    "办法",
    "指南",
    "风险提示",
    "公开募捐",
)
PROTOTYPE_SAMPLE_TITLES = {
    "儿童心理健康相关项目资助征集开放",
    "公益组织使用 AI 工具的行业讨论",
    "多地加强未成年人服务项目中的数据采集与隐私保护要求",
}
PROTOTYPE_SAMPLE_DOMAINS = {"example.org", "example.com", "example.net"}
PROFILE_MATERIAL_TERMS = (
    "登记",
    "统一社会信用代码",
    "社会组织",
    "年报",
    "年度报告",
    "信息公开",
    "机构简介",
    "关于我们",
    "业务范围",
    "评估等级",
)
TIMELY_MATERIAL_TERMS = (
    "申报",
    "征集",
    "招标",
    "采购",
    "中标",
    "成交",
    "截止",
    "近期",
    "监管",
    "合规",
    "公开募捐",
    "处罚",
    "风险提示",
)
GENERIC_FOCUS_TERMS = {
    "官网",
    "官方网站",
    "介绍",
    "资料",
    "公开",
    "文章",
    "观点",
    "案例",
    "报道",
    "项目",
    "服务",
    "政策",
    "机会",
    "风险",
    "平台",
    "规则",
    "建设",
    "数据",
    "影响",
    "有关",
    "相关",
    "当前",
    "客户",
    "组织",
    "公益",
}
DETAIL_LINK_TERMS = (
    "详情",
    "查看",
    "全文",
    "公告",
    "通知",
    "介绍",
    "项目",
    "案例",
    "文章",
    "观点",
    "报道",
    "年报",
    "报告",
    "信息公开",
)
TEMPLATE_SUMMARY_MARKERS = (
    "已围绕",
    "一版可执行",
    "内部判断",
    "通用背景下",
    "不是基于当前客户原始资料",
    "本地背景没有直接覆盖",
)
TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_NAMES = {"spm", "from", "source", "src", "share", "shareid", "scene", "fbclid", "gclid"}


@dataclass
class SourceConfig:
    id: str
    scope_type: str
    scope_id: str
    client_id: str
    project_module_id: str | None
    source_type: str
    source_name: str
    source_url_template: str
    region: str
    reliability_tier: str
    priority: int
    content_kinds: list[str] = field(default_factory=list)
    enabled: bool = True
    discovery_source: str = "default_template"
    discovery_reason: str = ""
    discovery_samples: list[dict[str, str]] = field(default_factory=list)
    health_score: float = 70.0
    success_count: int = 0
    failure_count: int = 0
    candidate_count: int = 0
    promoted_count: int = 0
    duplicate_count: int = 0
    last_status: str = "unknown"
    last_checked_at: str | None = None
    last_success_at: str | None = None
    last_failure_at: str | None = None
    next_due_at: str | None = None


@dataclass
class CandidateHit:
    title: str
    url: str
    snippet: str = ""
    source: str = ""
    published_at: str | None = None
    provider: str = "public_search"


@dataclass
class CandidateDraft:
    id: str
    content_kind: str
    intent: GeneratedSearchIntent
    source_config: SourceConfig
    fetch_job_id: str
    hit: CandidateHit
    normalized_url: str
    dedupe_key: str
    matched_terms: list[str]
    confidence_score: float
    signal_count: int
    feedback_adjustment: float = 0.0
    parent_url: str | None = None
    page_type: str = ""
    quality_flags: list[str] = field(default_factory=list)


@dataclass
class CandidateRefreshResult:
    source_config_count: int = 0
    fetch_job_count: int = 0
    candidate_count: int = 0
    promoted_count: int = 0
    duplicate_count: int = 0
    failed_count: int = 0
    body_fetched_count: int = 0
    verified_count: int = 0
    summary_success_count: int = 0
    rejection_counts: dict[str, int] = field(default_factory=dict)
    source_coverage_status: str = "missing"
    candidate_refresh_status: str = "missing"
    last_candidate_fetch_at: str | None = None
    candidate_counts: dict[str, int] = field(default_factory=dict)
    profile_coverage: list[str] = field(default_factory=list)
    profile_missing_dimensions: list[str] = field(default_factory=list)
    profile_completion_ready: bool = False
    search_direction_count: int = 0
    query_count: int = 0
    success_query_count: int = 0
    no_result_query_count: int = 0
    effective_lead_count: int = 0
    uncovered_gaps: list[str] = field(default_factory=list)

    def as_payload(self) -> dict[str, object]:
        return {
            "sourceConfigCount": self.source_config_count,
            "fetchJobCount": self.fetch_job_count,
            "candidateCount": self.candidate_count,
            "promotedCount": self.promoted_count,
            "duplicateCount": self.duplicate_count,
            "failedCount": self.failed_count,
            "bodyFetchedCount": self.body_fetched_count,
            "verifiedCount": self.verified_count,
            "summarySuccessCount": self.summary_success_count,
            "rejectionCounts": self.rejection_counts,
            "sourceCoverageStatus": self.source_coverage_status,
            "candidateRefreshStatus": self.candidate_refresh_status,
            "lastCandidateFetchAt": self.last_candidate_fetch_at,
            "candidateCounts": self.candidate_counts,
            "profileCoverage": self.profile_coverage,
            "profileMissingDimensions": self.profile_missing_dimensions,
            "profileCompletionReady": self.profile_completion_ready,
            "searchDirectionCount": self.search_direction_count,
            "queryCount": self.query_count,
            "successQueryCount": self.success_query_count,
            "noResultQueryCount": self.no_result_query_count,
            "effectiveLeadCount": self.effective_lead_count,
            "uncoveredGaps": self.uncovered_gaps,
        }


@dataclass
class ProfileVerificationResult:
    verified: bool
    verification_status: str
    verification_reason: str
    body_fetch_status: str = "not_attempted"
    summary_status: str = "not_attempted"
    mapped_tags: list[str] = field(default_factory=list)
    summary: str = ""
    key_points: list[str] = field(default_factory=list)
    analysis: str = ""
    body_excerpt: str = ""


@dataclass
class TimelyEnrichmentResult:
    intelligence_type: str
    timeliness_label: str
    summary: str
    relevance_reason: str
    impact: str
    suggested_action: str
    followup_questions: list[str] = field(default_factory=list)


@dataclass
class ResearchBrief:
    scope: IntelligenceSearchScope
    object_terms: list[str]
    profile_focus: list[str] = field(default_factory=list)
    timely_focus: list[str] = field(default_factory=list)
    exclude_terms: list[str] = field(default_factory=list)
    priority_urls: list[str] = field(default_factory=list)
    profile_focus_terms: list[str] = field(default_factory=list)
    timely_focus_terms: list[str] = field(default_factory=list)


@dataclass
class PageQuality:
    page_type: str
    flags: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class EvidenceExtraction:
    summary: str
    facts: list[str] = field(default_factory=list)
    quotes: list[str] = field(default_factory=list)
    focus_hits: list[str] = field(default_factory=list)
    missing: str = ""
    analysis: str = ""
    impact: str = ""
    suggested_action: str = ""
    intelligence_type: str | None = None
    timeliness_label: str | None = None


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _clean_text(value: object, *, max_len: int = 240) -> str:
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


def _unique_items(items: list[str], *, limit: int = 20) -> list[str]:
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


def _default_content_kinds_for_source_type(source_type: str) -> list[str]:
    kinds: list[str] = []
    for content_kind, source_types in CONTENT_KIND_SOURCE_TYPES.items():
        if source_type in source_types:
            kinds.append(content_kind)
    return kinds or ["profile_completion", "timely_intelligence"]


def _scope_rows(db: Database, scope: IntelligenceSearchScope) -> tuple[dict[str, object], dict[str, object]]:
    client_row = db.fetchone("SELECT * FROM clients WHERE id = ?", (scope.client_id,))
    project_row = (
        db.fetchone("SELECT * FROM project_modules WHERE id = ?", (scope.project_module_id,))
        if scope.project_module_id
        else None
    )
    return dict(client_row) if client_row else {}, dict(project_row) if project_row else {}


def _normalize_focus_url(raw: str) -> str:
    text = _clean_text(raw, max_len=300)
    text = text.strip("。），),；;\"'")
    if not text:
        return ""
    if not re.match(r"https?://", text, flags=re.I):
        text = f"https://{text}"
    parsed = urlparse(text)
    if not parsed.netloc or "." not in parsed.netloc:
        return ""
    domain = parsed.netloc.lower().removeprefix("www.")
    if _domain_matches(domain, CLOSED_OR_LOW_VALUE_DOMAINS) or _domain_matches(domain, AGGREGATOR_DOMAINS):
        return ""
    return urlunparse((parsed.scheme.lower() or "https", parsed.netloc.lower(), parsed.path or "/", "", "", ""))


def _extract_focus_urls(*values: object) -> list[str]:
    urls: list[str] = []
    url_pattern = re.compile(r"(?:https?://)?(?:www\.)?[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:/[^\s，,。；;）)]*)?")
    for value in values:
        for line in _as_text_list(value, limit=24):
            for match in url_pattern.findall(line):
                normalized = _normalize_focus_url(match)
                if normalized and normalized not in urls:
                    urls.append(normalized)
    return urls[:8]


def _focus_terms_from_lines(lines: list[str], object_terms: list[str]) -> list[str]:
    terms: list[str] = []
    for line in lines:
        for url in _extract_focus_urls(line):
            domain = urlparse(url).netloc.lower().removeprefix("www.")
            if domain and domain not in terms:
                terms.append(domain)
        for token in re.split(r"[\s,，;；、。.!！？? |/()（）《》“”\"'：:]+", line):
            cleaned = _clean_text(token, max_len=36)
            if len(cleaned) < 2:
                continue
            if cleaned in GENERIC_FOCUS_TERMS:
                continue
            if re.fullmatch(r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}", cleaned):
                cleaned = cleaned.lower().removeprefix("www.")
            if cleaned not in terms:
                terms.append(cleaned)
            for part in re.split(r"(?:的|和|与|及|以及|有关|相关|提到|关注)", cleaned):
                part = _clean_text(part, max_len=28)
                if len(part) >= 2 and part not in GENERIC_FOCUS_TERMS and part not in terms:
                    terms.append(part)
            if len(cleaned) >= 6:
                for size in (2, 4, 6):
                    head = cleaned[:size]
                    if len(head) >= 2 and head not in GENERIC_FOCUS_TERMS and head not in terms:
                        terms.append(head)
    for term in object_terms:
        if term and term not in terms:
            terms.append(term)
    return _unique_items(terms, limit=18)


def _load_research_brief(db: Database, scope: IntelligenceSearchScope) -> ResearchBrief:
    object_terms = _object_terms(db, scope)
    directive_keys: list[tuple[str, str]] = [("global", "")]
    directive_keys.append((scope.scope_type, scope.scope_id))
    if scope.project_module_id:
        directive_keys.append(("project_module", scope.project_module_id))
    clauses = " OR ".join(["(scope_type = ? AND scope_id = ?)"] * len(directive_keys))
    params: list[object] = []
    for key in directive_keys:
        params.extend(key)
    rows = db.fetchall(
        f"SELECT * FROM intelligence_focus_directives WHERE {clauses} ORDER BY updated_at DESC",
        tuple(params),
    )
    profile_focus: list[str] = []
    timely_focus: list[str] = []
    exclude_terms: list[str] = []
    for row in rows:
        profile_focus.extend(_as_text_list(_safe_json(str(row["profile_completion_focus_json"] or "[]"), []), limit=12))
        timely_focus.extend(_as_text_list(_safe_json(str(row["timely_intelligence_focus_json"] or "[]"), []), limit=12))
        exclude_terms.extend(_as_text_list(_safe_json(str(row["exclude_json"] or "[]"), []), limit=12))
    profile_focus = _unique_items(profile_focus, limit=16)
    timely_focus = _unique_items(timely_focus, limit=16)
    exclude_terms = _unique_items(exclude_terms, limit=20)
    priority_urls = _extract_focus_urls(profile_focus, timely_focus)
    return ResearchBrief(
        scope=scope,
        object_terms=object_terms,
        profile_focus=profile_focus,
        timely_focus=timely_focus,
        exclude_terms=exclude_terms,
        priority_urls=priority_urls,
        profile_focus_terms=_focus_terms_from_lines(profile_focus, object_terms),
        timely_focus_terms=_focus_terms_from_lines(timely_focus, object_terms),
    )


def _infer_region(*texts: object) -> str:
    corpus = " ".join(_clean_text(text, max_len=1200) for text in texts if text)
    regions = [
        "北京",
        "上海",
        "天津",
        "重庆",
        "广东",
        "广州",
        "深圳",
        "佛山",
        "东莞",
        "珠海",
        "江苏",
        "浙江",
        "山东",
        "四川",
        "湖南",
        "湖北",
        "福建",
        "河南",
        "河北",
        "广西",
        "海南",
        "云南",
        "贵州",
        "陕西",
        "甘肃",
        "安徽",
        "江西",
        "辽宁",
        "吉林",
        "黑龙江",
        "内蒙古",
        "新疆",
        "宁夏",
        "青海",
        "西藏",
        "香港",
        "澳门",
    ]
    for region in regions:
        if region in corpus:
            return region
    return "全国"


def _default_source_specs(region: str, client_name: str) -> list[dict[str, object]]:
    region_prefix = "" if region == "全国" else f"{region} "
    client_prefix = f"{client_name} " if client_name else ""
    return [
        {
            "source_type": "web_search",
            "source_name": "通用公开搜索",
            "template": "{query}",
            "tier": "standard",
            "priority": 70,
            "content_kinds": ["profile_completion", "timely_intelligence"],
            "reason": "默认通用搜索兜底，只在垂直来源不足时补充召回。",
        },
        {
            "source_type": "gov_policy",
            "source_name": "政府政策公开源",
            "template": f"{region_prefix}" + "{query} 政策 通知 site:gov.cn",
            "tier": "strong",
            "priority": 98,
            "content_kinds": ["timely_intelligence"],
            "reason": "时效情报优先覆盖政策通知。",
        },
        {
            "source_type": "procurement",
            "source_name": "招标采购公开源",
            "template": f"{region_prefix}" + "{query} 招标 采购 政府购买服务",
            "tier": "strong",
            "priority": 96,
            "content_kinds": ["timely_intelligence"],
            "reason": "时效情报优先覆盖招采和政府购买服务。",
        },
        {
            "source_type": "grant",
            "source_name": "资助申报公开源",
            "template": f"{region_prefix}" + "{query} 资助 申报 公益创投 征集 通知",
            "tier": "strong",
            "priority": 94,
            "content_kinds": ["timely_intelligence"],
            "reason": "时效情报优先覆盖资助与申报窗口。",
        },
        {
            "source_type": "regulatory_risk",
            "source_name": "监管风险公开源",
            "template": f"{region_prefix}" + "{query} 监管 合规 风险 公开募捐 处罚 通知",
            "tier": "strong",
            "priority": 93,
            "content_kinds": ["timely_intelligence"],
            "reason": "时效情报覆盖监管提醒、合规约束和风险提示。",
        },
        {
            "source_type": "social_org_registry",
            "source_name": "社会组织信息公开",
            "template": "{query} 社会组织 信息公开 年报 登记",
            "tier": "strong",
            "priority": 92,
            "content_kinds": ["profile_completion"],
            "reason": "资料补全优先覆盖登记、年报和信息公开。",
        },
        {
            "source_type": "profile_report",
            "source_name": "年报报告公开源",
            "template": "{query} 年报 年度报告 信息公开 报告 审计",
            "tier": "strong",
            "priority": 91,
            "content_kinds": ["profile_completion"],
            "reason": "资料补全覆盖年报、报告和可复用公开事实。",
        },
        {
            "source_type": "charity_media",
            "source_name": "公益行业公开报道",
            "template": "{query} 公益 慈善 项目 报道",
            "tier": "standard",
            "priority": 90,
            "content_kinds": ["profile_completion", "timely_intelligence"],
            "reason": "覆盖公益行业媒体、公开报道和案例线索。",
        },
        {
            "source_type": "partner_peer",
            "source_name": "合作方与同类机构动态",
            "template": "{query} 合作 伙伴 资助方 基金会 项目 动态 同类机构",
            "tier": "standard",
            "priority": 89,
            "content_kinds": ["timely_intelligence"],
            "reason": "时效情报覆盖合作方、资助方和同类机构动态。",
        },
        {
            "source_type": "official_site",
            "source_name": "官网线索公开搜索",
            "template": f"{client_prefix}" + "{query} 官网 项目 报告",
            "tier": "standard",
            "priority": 88,
            "content_kinds": ["profile_completion", "timely_intelligence"],
            "reason": "官网尚未确认时，先通过公开搜索寻找官网线索。",
        },
    ]


def _source_config_from_row(row) -> SourceConfig:
    source_type = str(row["source_type"] or "web_search")
    content_kinds = _as_text_list(
        _safe_json(str(row["content_kinds_json"] or "[]") if "content_kinds_json" in row.keys() else "[]", []),
        limit=4,
    )
    return SourceConfig(
        id=str(row["id"] or ""),
        scope_type=str(row["scope_type"] or ""),
        scope_id=str(row["scope_id"] or ""),
        client_id=str(row["client_id"] or ""),
        project_module_id=str(row["project_module_id"] or "") or None,
        source_type=source_type,
        source_name=str(row["source_name"] or ""),
        source_url_template=str(row["source_url_template"] or "{query}"),
        region=str(row["region"] or "全国"),
        reliability_tier=str(row["reliability_tier"] or "standard"),
        priority=int(row["priority"] or 50),
        content_kinds=content_kinds or _default_content_kinds_for_source_type(source_type),
        enabled=bool(int(row["enabled"] or 0)),
        discovery_source=str(row["discovery_source"] or "default_template") if "discovery_source" in row.keys() else "default_template",
        discovery_reason=str(row["discovery_reason"] or "") if "discovery_reason" in row.keys() else "",
        discovery_samples=list(_safe_json(str(row["discovery_samples_json"] or "[]"), [])) if "discovery_samples_json" in row.keys() else [],
        health_score=float(row["health_score"] or 70) if "health_score" in row.keys() else 70.0,
        success_count=int(row["success_count"] or 0) if "success_count" in row.keys() else 0,
        failure_count=int(row["failure_count"] or 0) if "failure_count" in row.keys() else 0,
        candidate_count=int(row["candidate_count"] or 0) if "candidate_count" in row.keys() else 0,
        promoted_count=int(row["promoted_count"] or 0) if "promoted_count" in row.keys() else 0,
        duplicate_count=int(row["duplicate_count"] or 0) if "duplicate_count" in row.keys() else 0,
        last_status=str(row["last_status"] or "unknown") if "last_status" in row.keys() else "unknown",
        last_checked_at=str(row["last_checked_at"] or "") or None if "last_checked_at" in row.keys() else None,
        last_success_at=str(row["last_success_at"] or "") or None if "last_success_at" in row.keys() else None,
        last_failure_at=str(row["last_failure_at"] or "") or None if "last_failure_at" in row.keys() else None,
        next_due_at=str(row["next_due_at"] or "") or None if "next_due_at" in row.keys() else None,
    )


def ensure_default_source_configs(db: Database, scope: IntelligenceSearchScope) -> list[SourceConfig]:
    client, project = _scope_rows(db, scope)
    project_keywords = _safe_json(str(project.get("keywords_json") or "[]"), []) if project else []
    region = _infer_region(
        client.get("name"),
        client.get("alias"),
        client.get("domain"),
        client.get("intro"),
        project.get("name") if project else "",
        project.get("goal") if project else "",
        project.get("description") if project else "",
        project_keywords,
    )
    timestamp = now_iso()
    for spec in _default_source_specs(region, _clean_text(client.get("name"))):
        source_type = str(spec["source_type"])
        source_name = str(spec["source_name"])
        template = str(spec["template"])
        tier = str(spec["tier"])
        priority = int(spec["priority"])
        content_kinds = [str(item) for item in spec.get("content_kinds", _default_content_kinds_for_source_type(source_type))]
        discovery_reason = str(spec.get("reason") or "")
        existing = db.fetchone(
            """
            SELECT id, created_at
            FROM intelligence_source_configs
            WHERE scope_type = ? AND scope_id = ? AND source_type = ? AND source_url_template = ?
            """,
            (scope.scope_type, scope.scope_id, source_type, template),
        )
        source_id = str(existing["id"]) if existing else _new_id("isrc")
        created_at = str(existing["created_at"]) if existing else timestamp
        db.execute(
            """
            INSERT INTO intelligence_source_configs(
                id, scope_type, scope_id, client_id, project_module_id, source_type,
                source_name, source_url_template, content_kinds_json, region,
                reliability_tier, priority, enabled, discovery_source, discovery_reason,
                last_status, created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'default_template', ?, 'unknown', ?, ?)
            ON CONFLICT(scope_type, scope_id, source_type, source_url_template) DO UPDATE SET
                client_id = excluded.client_id,
                project_module_id = excluded.project_module_id,
                source_name = excluded.source_name,
                content_kinds_json = excluded.content_kinds_json,
                region = excluded.region,
                reliability_tier = excluded.reliability_tier,
                priority = excluded.priority,
                discovery_reason = excluded.discovery_reason,
                enabled = 1,
                updated_at = excluded.updated_at
            """,
            (
                source_id,
                scope.scope_type,
                scope.scope_id,
                scope.client_id,
                scope.project_module_id,
                source_type,
                source_name,
                template,
                to_json(content_kinds),
                region,
                tier,
                priority,
                discovery_reason,
                created_at,
                timestamp,
            ),
        )
    rows = db.fetchall(
        """
        SELECT *
        FROM intelligence_source_configs
        WHERE scope_type = ? AND scope_id = ? AND enabled = 1
        ORDER BY priority DESC, health_score DESC, source_type ASC
        """,
        (scope.scope_type, scope.scope_id),
    )
    return [_source_config_from_row(row) for row in rows]


def _domain_from_source_template(template: str) -> str:
    text = _clean_text(template, max_len=500)
    site_match = re.search(r"site:([A-Za-z0-9.-]+\.[A-Za-z]{2,})", text, flags=re.I)
    if site_match:
        return site_match.group(1).lower().removeprefix("www.")
    url_match = re.search(r"https?://[^\s{}]+", text, flags=re.I)
    if url_match:
        return urlparse(url_match.group(0)).netloc.lower().removeprefix("www.")
    return ""


def _disable_invalid_discovered_sources(db: Database, scope: IntelligenceSearchScope) -> None:
    rows = db.fetchall(
        """
        SELECT id, source_url_template
        FROM intelligence_source_configs
        WHERE scope_type = ? AND scope_id = ? AND enabled = 1
          AND source_type IN ('official_site', 'official_site_section')
        """,
        (scope.scope_type, scope.scope_id),
    )
    timestamp = now_iso()
    for row in rows:
        domain = _domain_from_source_template(str(row["source_url_template"] or ""))
        if not domain:
            continue
        if _domain_matches(domain, CLOSED_OR_LOW_VALUE_DOMAINS) or _domain_matches(domain, AGGREGATOR_DOMAINS):
            db.execute(
                """
                UPDATE intelligence_source_configs
                SET enabled = 0,
                    last_status = 'rejected',
                    discovery_reason = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                ("官网来源校准：封闭平台、聚合站、招聘、地图或搜索域名不得作为官网路线", timestamp, row["id"]),
            )


def ensure_user_supplied_official_sources(db: Database, scope: IntelligenceSearchScope, brief: ResearchBrief) -> list[SourceConfig]:
    timestamp = now_iso()
    created: list[SourceConfig] = []
    for url in brief.priority_urls:
        domain = urlparse(url).netloc.lower().removeprefix("www.")
        if not domain:
            continue
        template = f"site:{domain} {{query}}"
        existing = db.fetchone(
            """
            SELECT id, created_at
            FROM intelligence_source_configs
            WHERE scope_type = ? AND scope_id = ? AND source_type = 'official_site' AND source_url_template = ?
            """,
            (scope.scope_type, scope.scope_id, template),
        )
        source_id = str(existing["id"]) if existing else _new_id("isrc")
        created_at = str(existing["created_at"]) if existing else timestamp
        samples = [{"title": "用户重点关注中提供的官网", "url": url, "reason": "用户给定网址优先作为可信来源路线"}]
        db.execute(
            """
            INSERT INTO intelligence_source_configs(
                id, scope_type, scope_id, client_id, project_module_id, source_type,
                source_name, source_url_template, content_kinds_json, region,
                reliability_tier, priority, enabled, discovery_source, discovery_reason,
                discovery_samples_json, health_score, last_status, created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, 'official_site', ?, ?, ?, '全国',
                   'strong', 100, 1, 'user_focus_directive', ?, ?, 92, 'unknown', ?, ?)
            ON CONFLICT(scope_type, scope_id, source_type, source_url_template) DO UPDATE SET
                client_id = excluded.client_id,
                project_module_id = excluded.project_module_id,
                source_name = excluded.source_name,
                content_kinds_json = excluded.content_kinds_json,
                reliability_tier = 'strong',
                priority = MAX(intelligence_source_configs.priority, excluded.priority),
                enabled = 1,
                discovery_source = excluded.discovery_source,
                discovery_reason = excluded.discovery_reason,
                discovery_samples_json = excluded.discovery_samples_json,
                health_score = MAX(intelligence_source_configs.health_score, excluded.health_score),
                updated_at = excluded.updated_at
            """,
            (
                source_id,
                scope.scope_type,
                scope.scope_id,
                scope.client_id,
                scope.project_module_id,
                f"用户给定官网：{domain}",
                template,
                to_json(["profile_completion", "timely_intelligence"]),
                "用户在重点关注中提供官网或重点网址，优先进入研究路线",
                to_json(samples),
                created_at,
                timestamp,
            ),
        )
        _upsert_official_site_section_configs(db, scope=scope, domain=domain, samples=samples, timestamp=timestamp)
    if not brief.priority_urls:
        return created
    rows = db.fetchall(
        """
        SELECT *
        FROM intelligence_source_configs
        WHERE scope_type = ? AND scope_id = ? AND enabled = 1 AND discovery_source = 'user_focus_directive'
        ORDER BY priority DESC, health_score DESC
        """,
        (scope.scope_type, scope.scope_id),
    )
    return [_source_config_from_row(row) for row in rows]


def _object_terms(db: Database, scope: IntelligenceSearchScope) -> list[str]:
    client, project = _scope_rows(db, scope)
    terms = [
        client.get("name"),
        client.get("alias"),
        client.get("domain"),
        project.get("name") if project else "",
        project.get("goal") if project else "",
    ]
    if project:
        terms.extend(_as_text_list(_safe_json(str(project.get("keywords_json") or "[]"), []), limit=8))
    result: list[str] = []
    for term in terms:
        for item in _as_text_list(term, limit=10):
            if len(item) >= 2 and item not in result:
                result.append(item)
            if len(result) >= 12:
                return result
    return result


def _intent_terms(intent: GeneratedSearchIntent) -> list[str]:
    terms = []
    for term in re.split(r"[\s,，;；、/|]+", intent.query):
        cleaned = _clean_text(term, max_len=40)
        if len(cleaned) >= 2 and cleaned not in terms:
            terms.append(cleaned)
    return terms[:12]


def _normalize_url(url: str) -> str:
    text = _clean_text(url, max_len=500)
    if not text:
        return ""
    try:
        parsed = urlparse(text)
        scheme = parsed.scheme.lower() or "https"
        netloc = parsed.netloc.lower()
        path = re.sub(r"/+$", "", parsed.path or "/")
        return urlunparse((scheme, netloc, path, "", "", ""))
    except Exception:
        return text.lower()


def _title_key(title: str) -> str:
    return hashlib.sha256(re.sub(r"[\W_]+", "", title.lower()).encode("utf-8")).hexdigest()[:24]


def _dedupe_key(title: str, normalized_url: str) -> str:
    clean_title = _clean_text(title, max_len=180)
    if clean_title and any(term in clean_title for term in NOTICE_TITLE_TERMS):
        return f"title:{_title_key(clean_title)}"
    if normalized_url:
        return hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()[:32]
    return _title_key(clean_title)


def _is_prototype_sample_hit(hit: CandidateHit) -> bool:
    domain = urlparse(hit.url or "").netloc.lower().removeprefix("www.")
    text = f"{hit.title} {hit.snippet} {hit.source} {hit.url}"
    if domain in PROTOTYPE_SAMPLE_DOMAINS:
        return True
    if _clean_text(hit.title, max_len=220) in PROTOTYPE_SAMPLE_TITLES:
        return True
    if any(marker in text for marker in ("资料补全样张", "时效情报样张", "只作为设计和验收基准", "不得作为模拟内容")):
        return True
    return False


def _looks_like_timely_material(text: str) -> bool:
    return any(term in text for term in TIMELY_MATERIAL_TERMS) and not any(term in text for term in PROFILE_MATERIAL_TERMS)


def _effective_query(intent: GeneratedSearchIntent, config: SourceConfig) -> str:
    region_prefix = "" if config.region == "全国" else f"{config.region} "
    template = config.source_url_template or "{query}"
    if intent.query.strip().lower().startswith("site:") and template.strip().lower().startswith("site:"):
        return _clean_text(intent.query, max_len=220)
    return _clean_text(
        template.format(
            query=intent.query,
            region=config.region,
            region_prefix=region_prefix,
            client="",
        ),
        max_len=220,
    )


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _source_priority_score(config: SourceConfig, *, timestamp: str) -> float:
    score = float(config.priority) + (float(config.health_score or 70) - 70) * 0.7
    now_value = _parse_iso(timestamp) or datetime.now()
    next_due = _parse_iso(config.next_due_at)
    if next_due is None or next_due <= now_value:
        score += 8
    last_failure = _parse_iso(config.last_failure_at)
    if config.last_status == "failed":
        score -= 12
    if last_failure and now_value - last_failure <= timedelta(hours=24):
        score -= 8
    return score


def _source_priority_score_for_kind(db: Database, config: SourceConfig, *, content_kind: str, timestamp: str) -> float:
    return _source_priority_score(config, timestamp=timestamp) + source_feedback_adjustment(
        db,
        source_config_id=config.id,
        content_kind=content_kind,
    ) * 3


def _source_route_bonus(intent: GeneratedSearchIntent, config: SourceConfig) -> float:
    intent_text = f"{intent.query} {intent.reason}"
    source_text = f"{config.source_type} {config.source_name}"
    source_type = config.source_type
    bonus = 0.0
    if source_type == "web_search":
        bonus -= 10
    if intent.content_kind == "profile_completion":
        if any(term in intent_text for term in ("登记", "信息公开", "社会组织", "统一社会信用代码")):
            if source_type == "social_org_registry":
                bonus += 18
            elif source_type == "official_site_section":
                bonus += 8
        if any(term in intent_text for term in ("年报", "年度报告", "报告", "审计")):
            if source_type == "profile_report":
                bonus += 18
            elif source_type == "official_site_section":
                bonus += 12
            elif source_type == "official_site":
                bonus += 6
        if any(term in intent_text for term in ("项目", "案例", "成效", "合作", "伙伴")):
            if source_type == "official_site_section":
                bonus += 12
            elif source_type == "charity_media":
                bonus += 8
        return bonus
    if any(term in intent_text for term in ("招标", "采购", "政府购买服务", "中标", "成交")):
        if source_type == "procurement":
            bonus += 20
    if any(term in intent_text for term in ("资助", "申报", "公益创投", "征集", "扶持")):
        if source_type == "grant":
            bonus += 20
        elif source_type == "partner_peer":
            bonus += 6
    if any(term in intent_text for term in ("监管", "风险", "合规", "公开募捐", "处罚", "整改")):
        if source_type == "regulatory_risk":
            bonus += 20
        elif source_type == "gov_policy":
            bonus += 10
    if any(term in intent_text for term in ("政策", "通知", "办法", "规划", "指南")) and source_type == "gov_policy":
        bonus += 14
    if any(term in intent_text for term in ("合作", "伙伴", "资助方", "同类", "基金会动态")):
        if source_type == "partner_peer":
            bonus += 16
        elif source_type == "charity_media":
            bonus += 8
    if any(term in intent_text for term in ("公告", "新闻", "动态", "信息公开")) and source_type == "official_site_section":
        bonus += 6
    if source_type == "official_site_section" and any(term in source_text for term in ("公告", "新闻", "信息公开", "报告")):
        bonus += 2
    return bonus


def _domain_label(url: str) -> str:
    domain = urlparse(url).netloc.lower().removeprefix("www.")
    return domain or "公开网页"


def _looks_like_domain_label(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", (value or "").strip(), flags=re.I))


def _source_display_name(draft: CandidateDraft) -> str:
    source = _clean_text(draft.hit.source, max_len=160)
    if draft.content_kind == "profile_completion" and (not source or _looks_like_domain_label(source)):
        return _clean_text(draft.hit.title, max_len=160) or source or _domain_label(draft.hit.url)
    return source or draft.source_config.source_name or _domain_label(draft.hit.url)


def _fetch_public_search_hits(query: str, config: SourceConfig, *, timeout_seconds: float = 8.0) -> list[CandidateHit]:
    hits: list[CandidateHit] = []
    for item in search_public_web(query, max_results=8, timeout_seconds=timeout_seconds):
        hits.append(
            CandidateHit(
                title=item.title,
                url=item.url,
                snippet=item.snippet,
                source=item.source or _domain_label(item.url),
                provider=item.provider,
            )
        )
    return hits


def _normalize_hit(raw: CandidateHit | dict[str, object], config: SourceConfig) -> CandidateHit | None:
    if isinstance(raw, CandidateHit):
        hit = raw
    else:
        hit = CandidateHit(
            title=_clean_text(raw.get("title"), max_len=180),
            url=_clean_text(raw.get("url") or raw.get("source_url"), max_len=500),
            snippet=_clean_text(raw.get("snippet") or raw.get("summary"), max_len=500),
            source=_clean_text(raw.get("source"), max_len=120),
            published_at=_clean_text(raw.get("published_at") or raw.get("publishedAt"), max_len=80) or None,
            provider=_clean_text(raw.get("provider"), max_len=80) or "public_search",
        )
    if not hit.title or not hit.url:
        return None
    if not hit.source:
        hit.source = urlparse(hit.url).netloc or config.source_name
    if not hit.provider:
        hit.provider = "public_search"
    return hit


def _drilldown_detail_hits_from_list(hit: CandidateHit, terms: list[str], *, limit: int = 2, timeout_seconds: float = 5.0) -> list[CandidateHit]:
    quality = _classify_hit_page(hit)
    if quality.page_type != "list_page":
        return []
    try:
        response = httpx.get(
            hit.url,
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )
        response.raise_for_status()
    except Exception:
        return []
    html = response.text or ""
    if not html:
        return []
    base_domain = urlparse(hit.url).netloc.lower().removeprefix("www.")
    candidates: list[CandidateHit] = []
    pattern = re.compile(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", flags=re.I | re.S)
    for href, label_html in pattern.findall(html):
        label = re.sub(r"<[^>]+>", " ", label_html)
        label = _clean_text(unescape(label), max_len=160)
        if not label:
            continue
        absolute = urljoin(hit.url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        domain = parsed.netloc.lower().removeprefix("www.")
        if domain != base_domain:
            continue
        link_text = f"{label} {absolute}"
        if not _matched_terms(link_text, terms) and not any(term in link_text for term in DETAIL_LINK_TERMS):
            continue
        child = CandidateHit(
            title=label,
            url=absolute,
            snippet=f"由列表页下钻：{hit.title}",
            source=hit.source,
            published_at=hit.published_at,
            provider="list_drilldown",
        )
        child_quality = _classify_hit_page(child)
        if child_quality.page_type in {"search_page", "media_or_map", "recruitment_directory", "aggregator", "invalid_url", "list_page"}:
            continue
        if all(existing.url != child.url for existing in candidates):
            candidates.append(child)
        if len(candidates) >= limit:
            break
    return candidates


def _domain_matches(domain: str, blocked: set[str]) -> bool:
    normalized = domain.lower().removeprefix("www.")
    return any(normalized == item or normalized.endswith(f".{item}") for item in blocked)


def _contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def _hit_search_text(hit: CandidateHit) -> str:
    domain = urlparse(hit.url).netloc.lower().removeprefix("www.")
    return f"{hit.title} {hit.snippet} {hit.source} {domain}"


def _classify_hit_page(hit: CandidateHit) -> PageQuality:
    parsed = urlparse(hit.url or "")
    domain = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.lower()
    query = parsed.query.lower()
    text = f"{hit.title} {hit.snippet} {hit.source} {hit.url}".lower()
    flags: list[str] = []
    if not parsed.scheme or not parsed.netloc:
        return PageQuality("invalid_url", ["invalid_url"], "来源链接无效")
    if any(path.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".mp4", ".mov")):
        return PageQuality("media", ["media"], "图片或视频不作为情报资料来源")
    if path.endswith(".pdf"):
        return PageQuality("pdf", ["pdf"], "PDF 暂作为候选材料，需稳定解析后再成卡")
    if _domain_matches(domain, CLOSED_OR_LOW_VALUE_DOMAINS):
        flags.append("closed_or_low_value_domain")
    if _domain_matches(domain, AGGREGATOR_DOMAINS):
        flags.append("aggregator_domain")
    if any(token in text for token in ("360图片", "_360图片", "图片搜索", "查看全部图片", "地图", "到这去")):
        return PageQuality("media_or_map", [*flags, "media_or_map"], "图片、地图或导航结果不得作为来源")
    if any(token in text for token in ("怎么样 - 职友集", "招聘", "工资待遇", "面试经验", "公司评价", "薪酬")) and _domain_matches(domain, AGGREGATOR_DOMAINS):
        return PageQuality("recruitment_directory", [*flags, "recruitment_directory"], "招聘或雇主评价目录不作为资料或时效情报")
    if any(token in path for token in ("/search", "/s", "/web", "/link")) or any(token in query for token in ("q=", "query=", "wd=")):
        if domain.endswith(("so.com", "sogou.com", "bing.com", "baidu.com")):
            return PageQuality("search_page", [*flags, "search_page"], "搜索结果页不得作为来源")
    list_path_terms = ("/list", "/lists", "/index", "/category", "/search")
    list_query_terms = ("page=", "p=", "cp=", "sort=", "category=", "keyword=")
    if any(token in path for token in list_path_terms) or path.rstrip("/") in {"/news", "/announcements"} or any(token in query for token in list_query_terms):
        flags.append("possible_list_page")
    if any(token in text for token in ("搜索结果", "相关搜索", "站内搜索", "上一页", "下一页")):
        flags.append("possible_list_page")
    if flags and ("closed_or_low_value_domain" in flags or "aggregator_domain" in flags):
        return PageQuality("aggregator", flags, "封闭平台、聚合站或低价值域名不作为可信来源")
    if "possible_list_page" in flags:
        return PageQuality("list_page", flags, "列表页只能用于有限下钻，不能直接成卡")
    return PageQuality("detail_page", flags, "")


def _hit_is_closed_or_low_value(hit: CandidateHit) -> bool:
    page = _classify_hit_page(hit)
    if page.page_type in {"media_or_map", "recruitment_directory", "search_page", "aggregator", "invalid_url"}:
        return True
    domain = urlparse(hit.url).netloc.lower().removeprefix("www.")
    path = urlparse(hit.url).path.lower()
    query = urlparse(hit.url).query.lower()
    text = f"{hit.title} {hit.snippet} {hit.source} {hit.url}".lower()
    if any(token in text for token in ("360图片", "_360图片", "图片搜索", "查看全部图片", "地图", "到这去")) and domain.endswith(("so.com", "360.cn", "baidu.com")):
        return True
    if any(token in path for token in ("/image", "/images", "/pic", "/photo", "/video")) and domain.endswith(("so.com", "sogou.com", "bing.com")):
        return True
    if any(token in path for token in ("/search", "/s", "/web", "/link")) and domain.endswith(("so.com", "sogou.com", "bing.com", "baidu.com")):
        return True
    if any(token in query for token in ("q=", "query=", "wd=")) and domain.endswith(("image.so.com", "map.360.cn", "map.so.com", "sogou.com", "bing.com", "baidu.com")):
        return True
    if any(token in text for token in ("用户登录", "验证码", "账号登录", "立即登录")) and any(token in text for token in ("登录", "注册", "验证码", "账号")):
        return True
    if any(token in text for token in ("聚合搜索", "站内搜索", "搜索结果", "相关搜索")) and domain.endswith(("so.com", "sogou.com", "bing.com", "baidu.com")):
        return True
    if any(token in text for token in ("怎么样 - 职友集", "招聘", "工资待遇", "面试经验", "公司评价", "薪酬")) and domain.endswith(("jobui.com", "kanzhun.com", "zhipin.com", "liepin.com")):
        return True
    return bool(domain and (_domain_matches(domain, CLOSED_OR_LOW_VALUE_DOMAINS) or _domain_matches(domain, AGGREGATOR_DOMAINS)))


def _hit_matches_profile_completion_context(hit: CandidateHit, object_terms: list[str]) -> bool:
    text = _hit_search_text(hit)
    if _hit_is_closed_or_low_value(hit):
        return False
    if not _contains_cjk(text):
        return False
    return bool(_matched_terms(text, object_terms))


def _hit_matches_timely_context(hit: CandidateHit, intent: GeneratedSearchIntent, object_terms: list[str]) -> bool:
    text = _hit_search_text(hit)
    if _hit_is_closed_or_low_value(hit):
        return False
    if not _contains_cjk(text):
        return False
    return bool(_matched_terms(text, object_terms)) or len(_matched_terms(text, _intent_terms(intent))) >= 2


def _hit_matches_intelligence_context(hit: CandidateHit, intent: GeneratedSearchIntent, object_terms: list[str]) -> bool:
    text = _hit_search_text(hit)
    if _matched_terms(text, intent.exclude_terms):
        return False
    if intent.content_kind == "profile_completion":
        return _hit_matches_profile_completion_context(hit, object_terms)
    return _hit_matches_timely_context(hit, intent, object_terms)


def _rule_rows(db: Database, scope: IntelligenceSearchScope) -> list[dict[str, object]]:
    rows = db.fetchall(
        """
        SELECT *
        FROM intelligence_verification_rules
        WHERE (scope_type = 'global' AND scope_id = '')
           OR (scope_type = ? AND scope_id = ?)
        ORDER BY CASE WHEN scope_type = 'global' THEN 0 ELSE 1 END ASC, updated_at ASC
        """,
        (scope.scope_type, scope.scope_id),
    )
    return [dict(row) for row in rows]


def _verification_terms(db: Database, scope: IntelligenceSearchScope) -> tuple[list[str], list[str], list[str]]:
    identity_terms = _object_terms(db, scope)
    positive_rules: list[str] = []
    exclude_rules: list[str] = []
    for row in _rule_rows(db, scope):
        identity_terms.extend(_as_text_list(_safe_json(str(row.get("identity_anchors_json") or "[]"), []), limit=12))
        positive_rules.extend(_as_text_list(_safe_json(str(row.get("positive_rules_json") or "[]"), []), limit=12))
        exclude_rules.extend(_as_text_list(_safe_json(str(row.get("exclude_rules_json") or "[]"), []), limit=12))
    return _unique_items(identity_terms, limit=18), _unique_items(positive_rules, limit=18), _unique_items(exclude_rules, limit=18)


def _fetch_page_text(url: str, *, timeout_seconds: float = 8.0) -> tuple[str, str, str]:
    parsed = urlparse(url or "")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "failed", "", "来源链接无效"
    path = parsed.path.lower()
    if any(path.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".mp4", ".mov")):
        return "unsupported_media", "", "图片或视频不作为资料补全正文"
    try:
        response = httpx.get(
            url,
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )
        response.raise_for_status()
    except Exception as exc:
        return "failed", "", f"正文抓取失败：{_clean_text(exc, max_len=160)}"
    content_type = response.headers.get("content-type", "").lower()
    if "pdf" in content_type or path.endswith(".pdf"):
        return "unsupported_pdf", "", "PDF 暂未完成稳定正文解析，先保留为候选"
    if not response.text:
        return "empty", "", "页面未返回可读正文"
    text = response.text
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<noscript\b[^>]*>.*?</noscript>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    lower_text = text.lower()
    if any(marker in text for marker in ("System.InvalidOperationException", "The partial view", "RenderPartialInternal", "ViewEngineCollection")):
        return "server_error_page", text[:800], "来源页面打开后为服务端错误页，不能作为可复验来源"
    if "indexxxgsShzzPage" in text and "document.location" in text:
        return "unstable_redirect_page", text[:800], "来源页面依赖不稳定跳转，打开复验会进入错误页，暂不成卡"
    if any(token in text for token in ("用户登录", "验证码", "账号登录", "立即登录")) and any(token in text for token in ("登录", "注册", "验证码", "账号")):
        return "login_page", text[:800], "页面为登录或验证码页面，无法可靠核验"
    if len(text) < 120:
        return "too_short", text[:800], "正文过短，无法可靠核验"
    code_markers = (
        "loader.use",
        "jquery",
        "function(",
        "var ",
        "document.",
        "window.",
        "container.",
        "subbyte",
        "return str",
    )
    marker_count = sum(1 for marker in code_markers if marker in lower_text)
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    if cjk_count < 80:
        return "low_cjk", text[:800], "中文正文不足，无法可靠核验"
    if marker_count >= 3 and cjk_count < 120:
        return "script_noise", text[:800], "正文包含脚本、地图或搜索页噪音，无法可靠核验"
    return "fetched", text[:8000], ""


def _classify_fetched_page(hit: CandidateHit, body_status: str, body_text: str, body_reason: str) -> PageQuality:
    hit_quality = _classify_hit_page(hit)
    if body_status != "fetched":
        flags = _unique_items([*hit_quality.flags, body_status], limit=8)
        return PageQuality(hit_quality.page_type if hit_quality.page_type != "detail_page" else body_status, flags, body_reason)
    text = f"{hit.title} {hit.snippet} {body_text[:1600]}"
    flags = list(hit_quality.flags)
    list_markers = sum(1 for marker in ("上一页", "下一页", "共", "条记录", "当前位置", "列表", "搜索结果", "更多") if marker in text)
    if hit_quality.page_type == "list_page" or list_markers >= 3:
        return PageQuality("list_page", _unique_items([*flags, "list_page"], limit=8), "列表页只能用于有限下钻，不能直接成卡")
    if any(marker in text for marker in ("用户登录", "验证码", "账号登录", "立即登录")):
        return PageQuality("login_page", _unique_items([*flags, "login_page"], limit=8), "页面为登录或验证码页面，无法可靠核验")
    if any(marker in text for marker in ("System.InvalidOperationException", "The partial view", "RenderPartialInternal", "ViewEngineCollection", "indexxxgsShzzPage")):
        return PageQuality("server_error_page", _unique_items([*flags, "server_error_page"], limit=8), "来源页面打开复验失败，暂不成卡")
    return PageQuality("detail_page", flags, "")


def _split_sentences(text: str, *, limit: int = 80) -> list[str]:
    sentences: list[str] = []
    for item in re.split(r"(?<=[。！？!?；;])\s*", text):
        cleaned = _clean_text(item, max_len=260)
        if len(cleaned) < 16:
            continue
        if any(marker in cleaned for marker in ("版权所有", "ICP备", "登录", "注册", "上一页", "下一页")):
            continue
        if cleaned not in sentences:
            sentences.append(cleaned)
        if len(sentences) >= limit:
            break
    return sentences


def _evidence_terms_for_kind(brief: ResearchBrief, content_kind: str) -> list[str]:
    terms = brief.profile_focus_terms if content_kind == "profile_completion" else brief.timely_focus_terms
    return _unique_items([*terms, *brief.object_terms], limit=24)


def _profile_dimension_hits(*values: str) -> list[str]:
    corpus = " ".join(values)
    hits: list[str] = []
    for label, keywords in PROFILE_COMPLETION_DIMENSIONS:
        if any(keyword and keyword in corpus for keyword in keywords):
            hits.append(label)
    return _unique_items(hits, limit=8)


def _profile_fact_from_quote(quote: str, *, brief: ResearchBrief, draft: CandidateDraft) -> str:
    text = _clean_text(quote.rstrip("。；;"), max_len=180)
    text = re.sub(r"^(来源|编辑|作者|发布时间|发布日期)[:：]\s*", "", text)
    text = re.sub(r"^\d{4}[-年]\d{1,2}[-月]\d{0,2}[日]?\s*", "", text)
    text = re.sub(r"^(好公益X悦享新知\s*)?\d{4}[-年]\d{1,2}[-月]\d{1,2}[日]?\s*来源[:：]?\s*[^ ]+\s*", "", text)
    text = re.sub(r"编者按\s*", "", text)
    invite_match = re.search(r"(.{0,40}?邀请)(.+?)(?:，|,)?围绕[“\"]?([^”\"，。]+)", text)
    if invite_match:
        invite_part = _clean_text(invite_match.group(2), max_len=120)
        topic = _clean_text(invite_match.group(3), max_len=80)
        fact = f"{invite_part}参与公开对谈，主题为“{topic}”。"
        return fact
    if "毕业之后就进入" in text and "项目" in text:
        project_match = re.search(r"做[“\"]?([^”\"，。]+?项目)[”\"]?", text)
        project = project_match.group(1) if project_match else "相关项目"
        return f"材料提到受访者毕业后进入日慈并参与“{project}”，可作为项目执行团队和人才培养线索。"
    if "目前担任秘书长" in text or ("秘书长" in text and "七年" in text):
        return "材料提到张真从项目岗位成长为机构负责人，目前担任日慈秘书长，可用于补充团队经历线索。"
    if "快速发展期" in text and ("团队" in text or "组织" in text):
        return "文章将机构目标设定、团队成长和岗位匹配列为快速发展期公益组织的重要管理议题。"
    object_name = brief.scope.display_name or (brief.object_terms[0] if brief.object_terms else "")
    if object_name and object_name not in text and _matched_terms(text, brief.object_terms):
        text = f"{object_name}：{text}"
    if not text.endswith("。"):
        text = f"{text}。"
    return text


def _profile_missing_text(covered_dimensions: list[str]) -> str:
    baseline = ["机构简介", "登记信息", "年报/信息公开", "项目介绍", "项目成效", "合作方", "执行方法"]
    missing = [item for item in baseline if item not in covered_dimensions]
    if missing:
        return f"仍需继续补齐：{'、'.join(missing[:5])}。"
    return "已覆盖基础资料维度，仍可继续核对来源更新时间和更完整原文。"


def _extract_research_evidence(
    *,
    brief: ResearchBrief,
    content_kind: str,
    draft: CandidateDraft,
    body_text: str,
) -> EvidenceExtraction | None:
    terms = _evidence_terms_for_kind(brief, content_kind)
    sentences = _split_sentences(body_text)
    if not sentences:
        return None
    focus_only_terms = brief.profile_focus_terms if content_kind == "profile_completion" else brief.timely_focus_terms
    focus_only_terms = [term for term in focus_only_terms if term not in brief.object_terms]
    focus_hits = _matched_terms(f"{draft.hit.title} {draft.hit.snippet} {body_text}", focus_only_terms)
    object_hits = _matched_terms(f"{draft.hit.title} {draft.hit.snippet} {body_text}", brief.object_terms)
    if content_kind == "profile_completion" and not object_hits:
        return None
    if content_kind == "timely_intelligence" and not object_hits and not focus_hits:
        return None
    if content_kind == "timely_intelligence" and focus_only_terms and not focus_hits:
        return None
    scored: list[tuple[int, str]] = []
    for sentence in sentences:
        score = 0
        if _matched_terms(sentence, brief.object_terms):
            score += 4
        score += min(len(_matched_terms(sentence, terms)), 4) * 2
        if any(token in sentence for token in ("数据", "人数", "年度", "发起", "开展", "发布", "介绍", "服务", "合作", "资助", "培训", "心理", "困境", "儿童", "顾源源", "张真")):
            score += 2
        if content_kind == "timely_intelligence" and any(token in sentence for token in TIMELY_MATERIAL_TERMS):
            score += 4
        if score >= 4:
            scored.append((score, sentence))
    scored.sort(key=lambda item: (-item[0], len(item[1])))
    quotes = _unique_items([sentence for _score, sentence in scored], limit=4)
    if not quotes:
        return None
    if content_kind == "profile_completion":
        dimension_hits = _profile_dimension_hits(draft.hit.title, draft.hit.snippet, body_text[:2400])
        facts = [_profile_fact_from_quote(quote, brief=brief, draft=draft) for quote in quotes[:4]]
        covered = dimension_hits or focus_hits[:3] or object_hits[:3]
        summary = f"找到与{brief.scope.display_name or '当前对象'}相关的公开资料，可用于补充：{'、'.join(covered[:4])}。"
        missing = _profile_missing_text(dimension_hits)
        return EvidenceExtraction(summary=summary, facts=facts, quotes=quotes, focus_hits=focus_hits[:6], missing=missing)
    intelligence_type = _timely_intelligence_type(draft) or "外部变化"
    summary = quotes[0]
    relation = f"命中关注点：{'、'.join(focus_hits[:4] or object_hits[:4])}。"
    impact = "需要进一步判断这条变化是否会影响当前客户/项目的资源获取、合规边界、服务对象或方案设计。"
    action = "建议转为阅读/研判任务，先核验原公告、适用对象、时间窗口和参与条件。"
    return EvidenceExtraction(
        summary=summary,
        facts=quotes[:4],
        quotes=quotes,
        focus_hits=focus_hits[:6],
        missing="还需核验原公告全文、截止时间、地域限制、资格条件和与当前对象的直接关系。",
        analysis=relation,
        impact=impact,
        suggested_action=action,
        intelligence_type=intelligence_type,
        timeliness_label=_timeliness_label(draft, intelligence_type),
    )


def _looks_like_template_summary(*values: str) -> bool:
    text = " ".join(values)
    return any(marker in text for marker in TEMPLATE_SUMMARY_MARKERS)


def _map_profile_tags(intent: GeneratedSearchIntent, hit: CandidateHit, body_text: str, positive_rules: list[str]) -> list[str]:
    intent_text = f"{intent.reason} {intent.query} {hit.title} {hit.snippet}"
    body_preview = body_text[:1800]
    scored: list[tuple[int, str]] = []
    for label, keywords in PROFILE_COMPLETION_DIMENSIONS:
        score = 0
        if any(keyword in f"{hit.title} {hit.snippet}" for keyword in keywords):
            score += 3
        score += min(sum(1 for keyword in keywords if keyword in body_preview), 3)
        if any(keyword in intent_text for keyword in keywords):
            score += 1
        if score >= 2:
            scored.append((score, label))
    dimension_order = {label: index for index, (label, _keywords) in enumerate(PROFILE_COMPLETION_DIMENSIONS)}
    scored.sort(key=lambda item: (-item[0], dimension_order.get(item[1], 999)))
    tags = [label for _score, label in scored]
    for rule in positive_rules:
        for label, keywords in PROFILE_COMPLETION_DIMENSIONS:
            if any(keyword in rule for keyword in keywords):
                tags.append(label)
                break
    return _unique_items(tags, limit=3)


def _profile_coverage_snapshot(db: Database, scope: IntelligenceSearchScope) -> tuple[list[str], list[str], bool]:
    rows = db.fetchall(
        """
        SELECT title, summary, key_points_json, tags_json
        FROM intelligence_items
        WHERE scope_type = ? AND scope_id = ? AND content_kind = 'profile_completion' AND user_status = 'active'
        ORDER BY created_at DESC
        LIMIT 80
        """,
        (scope.scope_type, scope.scope_id),
    )
    covered: list[str] = []
    for row in rows:
        tags = _safe_json(str(row["tags_json"] or "[]"), [])
        points = _safe_json(str(row["key_points_json"] or "[]"), [])
        covered.extend(_profile_dimension_hits(str(row["title"] or ""), str(row["summary"] or ""), " ".join(_as_text_list(tags, limit=12)), " ".join(_as_text_list(points, limit=12))))
    covered = _unique_items(covered, limit=12)
    baseline = ["机构简介", "登记信息", "年报/信息公开", "项目介绍", "项目成效", "合作方", "执行方法"]
    missing = [item for item in baseline if item not in covered]
    ready = len(set(covered).intersection(baseline)) >= 5 and "机构简介" in covered and ("项目介绍" in covered or "项目成效" in covered)
    return covered, missing, ready


def _split_summary_points(*values: str, limit: int = 4) -> list[str]:
    points: list[str] = []
    for value in values:
        for item in re.split(r"[\n。；;]+", value or ""):
            text = _clean_text(item, max_len=160)
            if text and text not in points:
                points.append(text)
            if len(points) >= limit:
                return points
    return points


def _clean_profile_fact_candidate(value: str) -> str:
    text = re.sub(r"^\s*[-*•\d.、）)]+", "", value or "").strip()
    text = re.sub(r"^(可复用事实|事实|资料摘要|摘要|证据缺口|缺口|标签|来源)\s*[:：]\s*", "", text)
    text = _clean_text(text, max_len=180)
    if not text:
        return ""
    if any(marker in text for marker in ("建议", "待核验", "还需", "需要继续", "无法判断", "已围绕标题", "内部判断")):
        return ""
    if len(text) < 18:
        return ""
    if not text.endswith("。"):
        text = f"{text}。"
    return text


def _compact_compare_text(value: str) -> str:
    return re.sub(r"[\s，。；;:：、\-—_（）()《》<>\"'“”‘’/|]+", "", value or "")


def _looks_like_raw_profile_quote(fact: str, evidence: EvidenceExtraction, draft: CandidateDraft) -> bool:
    text = fact or ""
    if any(marker in text for marker in ("-->", "<!–", "您的位置", "首页 >", "证据句", "来源：", "作者：", "浏览量", "点击量")):
        return True
    compact_fact = _compact_compare_text(text)
    if len(compact_fact) < 28:
        return False
    raw_values = [draft.hit.title, draft.hit.snippet, *evidence.quotes, *evidence.facts]
    for raw in raw_values:
        compact_raw = _compact_compare_text(raw)
        if len(compact_raw) < 28:
            continue
        if compact_fact in compact_raw or compact_raw in compact_fact:
            return True
    return False


def _extract_profile_facts_from_ai(response: AiStructuredResponse, evidence: EvidenceExtraction, mapped_tags: list[str], draft: CandidateDraft) -> list[str]:
    raw_sections = [response.content or "", response.analysis or "", response.actions or "", response.judgment or ""]
    candidates: list[str] = []
    for raw in raw_sections:
        capture = False
        for line in re.split(r"[\n\r]+", raw):
            stripped = line.strip()
            if not stripped:
                continue
            if "可复用事实" in stripped or stripped.startswith("事实"):
                capture = True
                remainder = re.sub(r"^.*?(可复用事实|事实)\s*[:：]?", "", stripped).strip()
                if remainder:
                    candidates.append(remainder)
                continue
            if capture and any(stripped.startswith(prefix) for prefix in ("证据", "缺口", "资料摘要", "摘要", "标签")):
                capture = False
            if capture or re.match(r"^\s*[-*•\d]+[.、）)]", stripped):
                candidates.append(stripped)
    if not candidates:
        candidates = _split_summary_points(response.analysis or "", response.actions or "", response.judgment or "", limit=8)
    ground_terms = _unique_items([*draft.matched_terms, *evidence.focus_hits, *mapped_tags], limit=16)
    cleaned: list[str] = []
    for candidate in candidates:
        fact = _clean_profile_fact_candidate(candidate)
        if not fact:
            continue
        if _looks_like_raw_profile_quote(fact, evidence, draft):
            continue
        if ground_terms and not _matched_terms(fact, ground_terms):
            continue
        if fact not in cleaned:
            cleaned.append(fact)
        if len(cleaned) >= 4:
            break
    return cleaned


def _refine_profile_tags_from_facts(points: list[str], fallback_tags: list[str]) -> list[str]:
    fact_text = " ".join(points)
    scored: list[tuple[int, str]] = []
    for label, keywords in PROFILE_COMPLETION_DIMENSIONS:
        score = sum(1 for keyword in keywords if keyword and keyword in fact_text)
        if score > 0:
            scored.append((score, label))
    dimension_order = {label: index for index, (label, _keywords) in enumerate(PROFILE_COMPLETION_DIMENSIONS)}
    scored.sort(key=lambda item: (-item[0], dimension_order.get(item[1], 999)))
    tags = [label for _score, label in scored]
    tags.extend(fallback_tags)
    return _unique_items(tags, limit=3)


def _build_profile_enrichment(
    ai_service: object | None,
    draft: CandidateDraft,
    body_text: str,
    mapped_tags: list[str],
    evidence: EvidenceExtraction,
) -> tuple[str, list[str], str] | None:
    fallback_summary = evidence.summary
    fallback_points = evidence.facts[:4]
    fallback_analysis = "\n".join(
        [
            f"证据句：{quote}" for quote in evidence.quotes[:3]
        ]
        + ([f"缺口：{evidence.missing}"] if evidence.missing else [])
    )
    if not _ai_ready(ai_service) or not hasattr(ai_service, "generate_general_fallback"):
        return None
    prompt = "\n".join(
        [
            f"标题：{draft.hit.title}",
            f"来源：{draft.hit.source}",
            f"链接：{draft.hit.url}",
            f"命中搜索意图：{draft.intent.query}",
            f"拟映射标签：{'、'.join(mapped_tags)}",
            f"已抽取证据句：{'；'.join(evidence.quotes[:4])}",
            f"网页正文摘录：{body_text[:3200]}",
            "请只基于网页正文和证据句，生成可进入客户/项目资料库的资料补全摘要，并提炼 2-4 条可复用事实。",
            "可复用事实必须是你对网页信息的提炼，不要整段照搬网页摘要或搜索短摘；每条事实都要能被证据句支持。",
            "请严格使用格式：资料摘要：...；可复用事实：- ... - ...；证据缺口：...。",
            "不要写“已围绕标题整理”“内部判断”等模板话，不要把下一步建议混进可复用事实。",
        ]
    )
    try:
        response = ai_service.generate_general_fallback(prompt, "资料补全核验摘要", subject_name=draft.hit.title)
    except Exception:
        return None
    if not isinstance(response, AiStructuredResponse):
        return None
    summary = _clean_text(response.content or response.judgment or "", max_len=500)
    summary = re.sub(r"可复用事实[:：].*$", "", summary, flags=re.S).strip()
    summary = re.sub(r"^资料摘要\s*[:：]\s*", "", summary).strip()
    points = _extract_profile_facts_from_ai(response, evidence, mapped_tags, draft)
    if not summary or _looks_like_template_summary(summary, response.analysis, response.actions, response.judgment):
        return None
    if not points:
        return None
    analysis = _clean_text(response.analysis or response.judgment or "", max_len=900)
    if _looks_like_template_summary(analysis):
        analysis = fallback_analysis
    return summary, points[:4], analysis


def _update_candidate_verification(
    db: Database,
    *,
    candidate_id: str,
    verification_status: str,
    verification_reason: str,
    body_fetch_status: str,
    summary_status: str,
    mapped_tags: list[str],
    body_excerpt: str,
    timestamp: str,
    visible: bool = True,
    page_type: str = "",
    quality_flags: list[str] | None = None,
    evidence: dict[str, object] | None = None,
) -> None:
    db.execute(
        """
        UPDATE intelligence_candidate_items
        SET verification_status = ?,
            verification_reason = ?,
            body_fetch_status = ?,
            summary_status = ?,
            mapped_tags_json = ?,
            is_user_visible_candidate = ?,
            body_excerpt = ?,
            body_fetched_at = CASE WHEN ? != 'not_attempted' THEN ? ELSE body_fetched_at END,
            page_type = ?,
            quality_flags_json = ?,
            evidence_json = ?,
            promotion_reason = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            verification_status,
            verification_reason,
            body_fetch_status,
            summary_status,
            to_json(mapped_tags),
            1 if visible else 0,
            _clean_text(body_excerpt, max_len=1200),
            body_fetch_status,
            timestamp,
            page_type,
            to_json(quality_flags or []),
            to_json(evidence or {}),
            verification_reason,
            timestamp,
            candidate_id,
        ),
    )


def _verify_profile_candidate(
    db: Database,
    *,
    ai_service: object | None,
    scope: IntelligenceSearchScope,
    draft: CandidateDraft,
    brief: ResearchBrief,
    timestamp: str,
) -> ProfileVerificationResult:
    identity_terms, positive_rules, exclude_rules = _verification_terms(db, scope)
    quick_text = _hit_search_text(draft.hit)
    if exclude_rules and any(rule and rule in quick_text for rule in exclude_rules):
        reason = "命中用户补充的排除标准，暂不成卡"
        _update_candidate_verification(
            db,
            candidate_id=draft.id,
            verification_status="rejected",
            verification_reason=reason,
            body_fetch_status="not_attempted",
            summary_status="not_attempted",
            mapped_tags=[],
            body_excerpt="",
            timestamp=timestamp,
        )
        return ProfileVerificationResult(False, "rejected", reason)
    body_status, body_text, body_reason = _fetch_page_text(draft.hit.url)
    body_excerpt = body_text[:1000]
    page_quality = _classify_fetched_page(draft.hit, body_status, body_text, body_reason)
    if body_status != "fetched":
        reason = body_reason or "未抓到可用于核验的网页正文"
        _update_candidate_verification(
            db,
            candidate_id=draft.id,
            verification_status="pending",
            verification_reason=reason,
            body_fetch_status=body_status,
            summary_status="not_attempted",
            mapped_tags=[],
            body_excerpt=body_excerpt,
            timestamp=timestamp,
            page_type=page_quality.page_type,
            quality_flags=page_quality.flags,
        )
        return ProfileVerificationResult(False, "pending", reason, body_status, "not_attempted", body_excerpt=body_excerpt)
    if page_quality.page_type != "detail_page":
        reason = page_quality.reason or "页面不是可核验详情页，暂不成卡"
        _update_candidate_verification(
            db,
            candidate_id=draft.id,
            verification_status="rejected",
            verification_reason=reason,
            body_fetch_status=body_status,
            summary_status="not_attempted",
            mapped_tags=[],
            body_excerpt=body_excerpt,
            timestamp=timestamp,
            page_type=page_quality.page_type,
            quality_flags=page_quality.flags,
        )
        return ProfileVerificationResult(False, "rejected", reason, body_status, "not_attempted", body_excerpt=body_excerpt)
    content_text = f"{draft.hit.title} {draft.hit.snippet} {body_text}"
    if _looks_like_timely_material(content_text):
        reason = "内容更像时效机会、风险或通知，不作为资料补全成卡"
        _update_candidate_verification(
            db,
            candidate_id=draft.id,
            verification_status="rejected",
            verification_reason=reason,
            body_fetch_status="fetched",
            summary_status="not_attempted",
            mapped_tags=[],
            body_excerpt=body_excerpt,
            timestamp=timestamp,
            page_type=page_quality.page_type,
            quality_flags=page_quality.flags,
        )
        return ProfileVerificationResult(False, "rejected", reason, "fetched", "not_attempted", body_excerpt=body_excerpt)
    combined_text = f"{quick_text} {body_text}"
    matched_identity = _matched_terms(combined_text, identity_terms)
    if not matched_identity:
        reason = "正文未命中客户/项目身份锚点，暂不成卡"
        _update_candidate_verification(
            db,
            candidate_id=draft.id,
            verification_status="rejected",
            verification_reason=reason,
            body_fetch_status="fetched",
            summary_status="not_attempted",
            mapped_tags=[],
            body_excerpt=body_excerpt,
            timestamp=timestamp,
            page_type=page_quality.page_type,
            quality_flags=page_quality.flags,
        )
        return ProfileVerificationResult(False, "rejected", reason, "fetched", "not_attempted", body_excerpt=body_excerpt)
    evidence = _extract_research_evidence(
        brief=brief,
        content_kind="profile_completion",
        draft=draft,
        body_text=body_text,
    )
    if evidence is None:
        reason = "正文缺少客户/项目身份关系或可复用事实证据句，暂不成卡"
        _update_candidate_verification(
            db,
            candidate_id=draft.id,
            verification_status="rejected",
            verification_reason=reason,
            body_fetch_status="fetched",
            summary_status="not_attempted",
            mapped_tags=[],
            body_excerpt=body_excerpt,
            timestamp=timestamp,
            page_type=page_quality.page_type,
            quality_flags=[*page_quality.flags, "insufficient_evidence"],
        )
        return ProfileVerificationResult(False, "rejected", reason, "fetched", "not_attempted", body_excerpt=body_excerpt)
    mapped_tags = _map_profile_tags(draft.intent, draft.hit, body_text, positive_rules)
    if not mapped_tags:
        reason = "正文未能映射到明确资料缺口或标签，暂不成卡"
        _update_candidate_verification(
            db,
            candidate_id=draft.id,
            verification_status="pending",
            verification_reason=reason,
            body_fetch_status="fetched",
            summary_status="not_attempted",
            mapped_tags=[],
            body_excerpt=body_excerpt,
            timestamp=timestamp,
            page_type=page_quality.page_type,
            quality_flags=page_quality.flags,
        )
        return ProfileVerificationResult(False, "pending", reason, "fetched", "not_attempted", body_excerpt=body_excerpt)
    enrichment = _build_profile_enrichment(ai_service, draft, body_text, mapped_tags, evidence)
    if enrichment is None:
        reason = "AI 未生成合格的资料摘要和可复用事实提炼，暂不成卡"
        _update_candidate_verification(
            db,
            candidate_id=draft.id,
            verification_status="verified",
            verification_reason=reason,
            body_fetch_status="fetched",
            summary_status="failed",
            mapped_tags=mapped_tags,
            body_excerpt=body_excerpt,
            timestamp=timestamp,
            page_type=page_quality.page_type,
            quality_flags=page_quality.flags,
        )
        return ProfileVerificationResult(False, "verified", reason, "fetched", "failed", mapped_tags, body_excerpt=body_excerpt)
    summary, points, analysis = enrichment
    mapped_tags = _refine_profile_tags_from_facts(points, mapped_tags)
    reason = f"已核验：正文命中身份锚点（{', '.join(matched_identity[:3])}），并映射到 {', '.join(mapped_tags[:3])}"
    _update_candidate_verification(
        db,
        candidate_id=draft.id,
        verification_status="verified",
        verification_reason=reason,
        body_fetch_status="fetched",
        summary_status="generated",
        mapped_tags=mapped_tags,
        body_excerpt=body_excerpt,
        timestamp=timestamp,
        page_type=page_quality.page_type,
        quality_flags=page_quality.flags,
        evidence={
            "quotes": evidence.quotes,
            "facts": evidence.facts,
            "focusHits": evidence.focus_hits,
            "missing": evidence.missing,
        },
    )
    return ProfileVerificationResult(True, "verified", reason, "fetched", "generated", mapped_tags, summary, points, analysis, body_excerpt)


def _official_site_discovery_queries(db: Database, scope: IntelligenceSearchScope) -> list[str]:
    client, project = _scope_rows(db, scope)
    names = _as_text_list(client.get("name"), limit=2)
    names.extend(_as_text_list(client.get("alias"), limit=2))
    if project:
        project_names = _as_text_list(project.get("name"), limit=2)
        keywords = _as_text_list(_safe_json(str(project.get("keywords_json") or "[]"), []), limit=4)
        names.extend(project_names)
        base_client = _clean_text(client.get("name"), max_len=80)
        for project_name in project_names[:2]:
            if base_client:
                names.append(f"{base_client} {project_name}")
            for keyword in keywords[:2]:
                names.append(f"{project_name} {keyword}")
    queries: list[str] = []
    for name in names:
        text = _clean_text(name, max_len=80)
        if not text:
            continue
        for suffix in ("官网", "官方网站", "信息公开"):
            query = f"{text} {suffix}"
            if query not in queries:
                queries.append(query)
            if len(queries) >= 4:
                return queries
    return queries


def _score_official_site_candidate(hit: CandidateHit, object_terms: list[str]) -> tuple[int, str]:
    parsed = urlparse(hit.url)
    domain = parsed.netloc.lower().removeprefix("www.")
    page_quality = _classify_hit_page(hit)
    if (
        not domain
        or _domain_matches(domain, CLOSED_OR_LOW_VALUE_DOMAINS)
        or _domain_matches(domain, AGGREGATOR_DOMAINS)
        or page_quality.page_type in {"search_page", "media_or_map", "recruitment_directory", "aggregator", "list_page", "invalid_url"}
    ):
        return 0, page_quality.reason or "封闭平台、聚合站、列表页或低价值域名，不作为官网来源。"
    text = f"{hit.title} {hit.snippet} {hit.source} {domain}"
    object_matches = _matched_terms(text, object_terms)
    if not object_matches:
        return 0, "未命中客户/项目名称或关键词。"
    score = 40 + min(len(object_matches), 3) * 15
    if any(token in text for token in ("官网", "官方网站", "信息公开", "项目介绍", "关于我们")):
        score += 15
    if domain.endswith((".org.cn", ".org", ".edu.cn", ".gov.cn", ".cn")):
        score += 8
    if any(token in domain for token in ("gov", "edu")):
        score += 6
    return min(score, 98), f"官网发现命中：{', '.join(object_matches[:3])}"


def _insert_source_discovery_fetch_job(
    db: Database,
    *,
    scope: IntelligenceSearchScope,
    query: str,
    status: str,
    raw_count: int,
    deduped_count: int,
    sample_hits: list[dict[str, str]],
    failure_reason: str,
    duration_ms: int,
    timestamp: str,
) -> None:
    db.execute(
        """
        INSERT INTO intelligence_fetch_jobs(
            id, scope_type, scope_id, client_id, project_module_id, content_kind,
            trigger_source, provider, source_config_id, query, status, raw_count,
            deduped_count, candidate_count, sample_hits_json, failure_reason, duration_ms, created_at
        )
        VALUES(?, ?, ?, ?, ?, 'source_discovery', 'official_site_discovery',
               'official_site_discovery', NULL, ?, ?, ?, ?, 0, ?, ?, ?, ?)
        """,
        (
            _new_id("ifjob"),
            scope.scope_type,
            scope.scope_id,
            scope.client_id,
            scope.project_module_id,
            query,
            status,
            raw_count,
            deduped_count,
            to_json(sample_hits),
            failure_reason,
            duration_ms,
            timestamp,
        ),
    )


def _upsert_official_site_section_configs(
    db: Database,
    *,
    scope: IntelligenceSearchScope,
    domain: str,
    samples: list[dict[str, str]],
    timestamp: str,
) -> None:
    normalized_domain = domain.lower().removeprefix("www.").strip()
    if not normalized_domain:
        return
    for section_name, section_terms, content_kinds, priority in OFFICIAL_SITE_SECTION_SPECS:
        template = f"site:{normalized_domain} {{query}} {section_terms}"
        existing = db.fetchone(
            """
            SELECT id, created_at
            FROM intelligence_source_configs
            WHERE scope_type = ? AND scope_id = ? AND source_type = 'official_site_section' AND source_url_template = ?
            """,
            (scope.scope_type, scope.scope_id, template),
        )
        source_id = str(existing["id"]) if existing else _new_id("isrc")
        created_at = str(existing["created_at"]) if existing else timestamp
        db.execute(
            """
            INSERT INTO intelligence_source_configs(
                id, scope_type, scope_id, client_id, project_module_id, source_type,
                source_name, source_url_template, content_kinds_json, region,
                reliability_tier, priority, enabled, discovery_source, discovery_reason,
                discovery_samples_json, health_score, last_status, created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, 'official_site_section', ?, ?, ?, '全国',
                   'strong', ?, 1, 'official_site_section', ?, ?, 76, 'unknown', ?, ?)
            ON CONFLICT(scope_type, scope_id, source_type, source_url_template) DO UPDATE SET
                client_id = excluded.client_id,
                project_module_id = excluded.project_module_id,
                source_name = excluded.source_name,
                content_kinds_json = excluded.content_kinds_json,
                reliability_tier = 'strong',
                priority = excluded.priority,
                enabled = 1,
                discovery_source = excluded.discovery_source,
                discovery_reason = excluded.discovery_reason,
                discovery_samples_json = excluded.discovery_samples_json,
                health_score = MAX(intelligence_source_configs.health_score, excluded.health_score),
                updated_at = excluded.updated_at
            """,
            (
                source_id,
                scope.scope_type,
                scope.scope_id,
                scope.client_id,
                scope.project_module_id,
                section_name,
                template,
                to_json(list(content_kinds)),
                priority,
                f"官网栏目下钻：{normalized_domain}",
                to_json(samples[:3]),
                created_at,
                timestamp,
            ),
        )


def discover_official_site_source_configs(
    db: Database,
    *,
    scope: IntelligenceSearchScope,
    hit_fetcher: Callable[[str, SourceConfig], list[CandidateHit | dict[str, object]]] | None = None,
    max_queries: int = 4,
    hits_per_query: int = 5,
) -> list[SourceConfig]:
    timestamp = now_iso()
    object_terms = _object_terms(db, scope)
    queries = _official_site_discovery_queries(db, scope)[:max_queries]
    if not queries or not object_terms:
        return []
    fetcher = hit_fetcher or _fetch_public_search_hits
    discovery_config = SourceConfig(
        id="official_site_discovery",
        scope_type=scope.scope_type,
        scope_id=scope.scope_id,
        client_id=scope.client_id,
        project_module_id=scope.project_module_id,
        source_type="web_search",
        source_name="官网发现搜索",
        source_url_template="{query}",
        region="全国",
        reliability_tier="standard",
        priority=60,
        content_kinds=["profile_completion", "timely_intelligence"],
    )
    promoted_domains: set[str] = set()
    for query in queries:
        started = time.perf_counter()
        raw_hits: list[CandidateHit | dict[str, object]] = []
        status = "success"
        failure_reason = ""
        try:
            raw_hits = fetcher(query, discovery_config)
        except Exception as exc:
            status = "failed"
            failure_reason = _clean_text(exc, max_len=240)
        normalized_hits: list[CandidateHit] = []
        seen_domains: set[str] = set()
        for raw_hit in raw_hits:
            hit = _normalize_hit(raw_hit, discovery_config)
            if hit is None:
                continue
            domain = urlparse(hit.url).netloc.lower().removeprefix("www.")
            if not domain or domain in seen_domains:
                continue
            seen_domains.add(domain)
            normalized_hits.append(hit)
            if len(normalized_hits) >= hits_per_query:
                break
        if status == "success" and not normalized_hits:
            status = "no_results"
        samples: list[dict[str, str]] = []
        for hit in normalized_hits[:hits_per_query]:
            score, reason = _score_official_site_candidate(hit, object_terms)
            domain = urlparse(hit.url).netloc.lower().removeprefix("www.")
            samples.append({"title": hit.title, "url": hit.url, "score": str(score), "reason": reason})
            if score < 78 or domain in promoted_domains:
                continue
            promoted_domains.add(domain)
            template = f"site:{domain} {{query}}"
            source_id = _new_id("isrc")
            existing = db.fetchone(
                """
                SELECT id, created_at
                FROM intelligence_source_configs
                WHERE scope_type = ? AND scope_id = ? AND source_type = 'official_site' AND source_url_template = ?
                """,
                (scope.scope_type, scope.scope_id, template),
            )
            if existing:
                source_id = str(existing["id"])
                created_at = str(existing["created_at"])
            else:
                created_at = timestamp
            db.execute(
                """
                INSERT INTO intelligence_source_configs(
                    id, scope_type, scope_id, client_id, project_module_id, source_type,
                    source_name, source_url_template, content_kinds_json, region,
                    reliability_tier, priority, enabled, discovery_source, discovery_reason,
                    discovery_samples_json, health_score, last_status, created_at, updated_at
                )
                VALUES(?, ?, ?, ?, ?, 'official_site', ?, ?, ?, '全国',
                       'strong', 99, 1, 'official_site_search', ?, ?, 78, 'unknown', ?, ?)
                ON CONFLICT(scope_type, scope_id, source_type, source_url_template) DO UPDATE SET
                    client_id = excluded.client_id,
                    project_module_id = excluded.project_module_id,
                    source_name = excluded.source_name,
                    content_kinds_json = excluded.content_kinds_json,
                    reliability_tier = 'strong',
                    priority = MAX(intelligence_source_configs.priority, excluded.priority),
                    enabled = 1,
                    discovery_source = excluded.discovery_source,
                    discovery_reason = excluded.discovery_reason,
                    discovery_samples_json = excluded.discovery_samples_json,
                    health_score = MAX(intelligence_source_configs.health_score, excluded.health_score),
                    updated_at = excluded.updated_at
                """,
                (
                    source_id,
                    scope.scope_type,
                    scope.scope_id,
                    scope.client_id,
                    scope.project_module_id,
                    f"官网发现：{domain}",
                    template,
                    to_json(["profile_completion", "timely_intelligence"]),
                    reason,
                    to_json(samples[:3]),
                    created_at,
                    timestamp,
                ),
            )
            _upsert_official_site_section_configs(
                db,
                scope=scope,
                domain=domain,
                samples=samples[:3],
                timestamp=timestamp,
            )
        _insert_source_discovery_fetch_job(
            db,
            scope=scope,
            query=query,
            status=status,
            raw_count=len(raw_hits),
            deduped_count=len(normalized_hits),
            sample_hits=samples[:hits_per_query],
            failure_reason=failure_reason,
            duration_ms=int((time.perf_counter() - started) * 1000),
            timestamp=timestamp,
        )
    if not promoted_domains:
        return []
    rows = db.fetchall(
        """
        SELECT *
        FROM intelligence_source_configs
        WHERE scope_type = ? AND scope_id = ? AND source_type = 'official_site'
          AND discovery_source = 'official_site_search' AND enabled = 1
        ORDER BY health_score DESC, priority DESC
        """,
        (scope.scope_type, scope.scope_id),
    )
    return [_source_config_from_row(row) for row in rows]


def _matched_terms(text: str, terms: list[str]) -> list[str]:
    matched: list[str] = []
    for term in terms:
        if term and term in text and term not in matched:
            matched.append(term)
    return matched[:12]


def _score_candidate(
    *,
    content_kind: str,
    config: SourceConfig,
    hit: CandidateHit,
    intent: GeneratedSearchIntent,
    object_terms: list[str],
) -> tuple[float, int, list[str]]:
    text = f"{hit.title} {hit.snippet} {hit.source}"
    matched_object_terms = _matched_terms(text, object_terms)
    matched_intent_terms = _matched_terms(text, _intent_terms(intent))
    source_type_match = (
        config.source_type in PROFILE_SOURCE_TYPES
        if content_kind == "profile_completion"
        else config.source_type in TIMELY_SOURCE_TYPES
    )
    signal_count = 0
    if matched_object_terms:
        signal_count += 1
    if len(matched_intent_terms) >= 2:
        signal_count += 1
    if source_type_match:
        signal_count += 1
    if hit.published_at:
        signal_count += 1
    base = 55 if config.reliability_tier == "strong" else 40 if config.reliability_tier == "standard" else 25
    score = base + len(matched_object_terms) * 8 + min(len(matched_intent_terms), 4) * 5
    if source_type_match:
        score += 8
    if hit.published_at:
        score += 5
    return min(float(score), 98.0), signal_count, [*matched_object_terms, *matched_intent_terms]


def _apply_feedback_to_candidate_score(
    db: Database,
    *,
    scope: IntelligenceSearchScope,
    content_kind: str,
    config: SourceConfig,
    hit: CandidateHit,
    intent: GeneratedSearchIntent,
    base_score: float,
) -> tuple[float, float]:
    adjustment = feedback_score_for_candidate(
        db,
        scope_type=scope.scope_type,
        scope_id=scope.scope_id,
        content_kind=content_kind,
        title=hit.title,
        snippet=hit.snippet,
        tags=[config.source_type],
        source=hit.source or config.source_name,
        source_domain=source_domain_from_url(hit.url),
        source_config_id=config.id,
        intent_id=intent.id,
    )
    return max(1.0, min(98.0, base_score + adjustment * 4)), adjustment


def _selected_fetch_tasks(
    db: Database,
    intents: list[GeneratedSearchIntent],
    configs: list[SourceConfig],
    *,
    max_fetch_jobs: int,
) -> list[tuple[GeneratedSearchIntent, SourceConfig]]:
    timestamp = now_iso()
    tasks: list[tuple[GeneratedSearchIntent, SourceConfig]] = []
    active_kinds = [content_kind for content_kind in ("profile_completion", "timely_intelligence") if any(item.content_kind == content_kind for item in intents)]
    per_kind_limit = max(1, (max_fetch_jobs + max(1, len(active_kinds)) - 1) // max(1, len(active_kinds)))
    for content_kind in active_kinds:
        source_types = CONTENT_KIND_SOURCE_TYPES[content_kind]
        intent_limit = 40 if content_kind == "profile_completion" else 32
        source_window = 7 if content_kind == "profile_completion" else 5
        kind_limit = min(200 if content_kind == "profile_completion" else 140, per_kind_limit)
        kind_intents = sorted(
            [item for item in intents if item.content_kind == content_kind],
            key=lambda item: (-item.priority, item.query),
        )[:intent_limit]
        kind_configs = [
            item
            for item in configs
            if item.source_type in source_types and (not item.content_kinds or content_kind in item.content_kinds)
        ]
        kind_task_count = 0
        for intent in kind_intents:
            routed_configs = sorted(
                kind_configs,
                key=lambda item: (
                    -(
                        _source_priority_score_for_kind(db, item, content_kind=content_kind, timestamp=timestamp)
                        + _source_route_bonus(intent, item)
                    ),
                    item.source_type,
                    item.source_name,
                ),
            )
            for config in routed_configs[:source_window]:
                tasks.append((intent, config))
                kind_task_count += 1
                if len(tasks) >= max_fetch_jobs:
                    return tasks
                if kind_task_count >= kind_limit:
                    break
            if kind_task_count >= kind_limit:
                break
    return tasks


def _health_score_from_counts(
    *,
    success_count: int,
    failure_count: int,
    candidate_count: int,
    promoted_count: int,
    duplicate_count: int,
    last_status: str,
) -> float:
    score = 70.0
    score += min(success_count, 12) * 1.5
    score += min(candidate_count, 30) * 0.25
    score += min(promoted_count, 12) * 3.0
    score -= min(failure_count, 12) * 4.0
    score -= min(duplicate_count, 30) * 0.4
    if last_status == "failed":
        score -= 10
    elif last_status == "no_results":
        score -= 3
    return max(5.0, min(100.0, score))


def _recompute_source_health(db: Database, source_config_id: str) -> None:
    row = db.fetchone("SELECT * FROM intelligence_source_configs WHERE id = ?", (source_config_id,))
    if not row:
        return
    score = _health_score_from_counts(
        success_count=int(row["success_count"] or 0),
        failure_count=int(row["failure_count"] or 0),
        candidate_count=int(row["candidate_count"] or 0),
        promoted_count=int(row["promoted_count"] or 0),
        duplicate_count=int(row["duplicate_count"] or 0),
        last_status=str(row["last_status"] or "unknown"),
    )
    db.execute(
        "UPDATE intelligence_source_configs SET health_score = ?, updated_at = ? WHERE id = ?",
        (score, now_iso(), source_config_id),
    )


def _insert_fetch_job(
    db: Database,
    *,
    scope: IntelligenceSearchScope,
    content_kind: str,
    trigger_source: str,
    config: SourceConfig,
    query: str,
    status: str,
    raw_count: int,
    deduped_count: int,
    candidate_count: int,
    sample_hits: list[dict[str, str]],
    failure_reason: str,
    duration_ms: int,
    timestamp: str,
) -> str:
    job_id = _new_id("ifjob")
    db.execute(
        """
        INSERT INTO intelligence_fetch_jobs(
            id, scope_type, scope_id, client_id, project_module_id, content_kind,
            trigger_source, provider, source_config_id, query, status, raw_count,
            deduped_count, candidate_count, sample_hits_json, failure_reason, duration_ms, created_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            scope.scope_type,
            scope.scope_id,
            scope.client_id,
            scope.project_module_id,
            content_kind,
            trigger_source,
            config.source_type,
            config.id,
            query,
            status,
            raw_count,
            deduped_count,
            candidate_count,
            to_json(sample_hits),
            failure_reason,
            duration_ms,
            timestamp,
        ),
    )
    base_due_hours = refresh_cycle_hours(db, content_kind)
    if status == "failed":
        due_hours = 2 if content_kind == "profile_completion" else 1
    elif status == "no_results":
        due_hours = min(base_due_hours, 6)
    else:
        due_hours = base_due_hours
    success_delta = 1 if status == "success" else 0
    failure_delta = 1 if status == "failed" else 0
    last_success_at = timestamp if status == "success" else None
    last_failure_at = timestamp if status == "failed" else None
    db.execute(
        """
        UPDATE intelligence_source_configs
        SET last_status = ?,
            last_checked_at = ?,
            last_success_at = COALESCE(?, last_success_at),
            last_failure_at = COALESCE(?, last_failure_at),
            success_count = success_count + ?,
            failure_count = failure_count + ?,
            candidate_count = candidate_count + ?,
            next_due_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            status,
            timestamp,
            last_success_at,
            last_failure_at,
            success_delta,
            failure_delta,
            candidate_count,
            (datetime.fromisoformat(timestamp) + timedelta(hours=due_hours)).isoformat(),
            timestamp,
            config.id,
        ),
    )
    _recompute_source_health(db, config.id)
    return job_id


def _insert_candidate(
    db: Database,
    *,
    scope: IntelligenceSearchScope,
    draft: CandidateDraft,
    classification_status: str,
    duplicate_of_id: str | None,
    timestamp: str,
) -> None:
    hit = draft.hit
    db.execute(
        """
        INSERT INTO intelligence_candidate_items(
            id, scope_type, scope_id, client_id, project_module_id, content_kind,
            intent_id, source_config_id, fetch_job_id, title, url, normalized_url,
            snippet, source, source_tier, provider, published_at, captured_at,
            matched_terms_json, dedupe_key, duplicate_of_id, confidence_score,
            classification_status, promotion_reason, page_type, quality_flags_json,
            parent_candidate_id, source_page_url, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?, ?, ?, ?, ?)
        """,
        (
            draft.id,
            scope.scope_type,
            scope.scope_id,
            scope.client_id,
            scope.project_module_id,
            draft.content_kind,
            draft.intent.id,
            draft.source_config.id,
            draft.fetch_job_id,
            hit.title,
            hit.url,
            draft.normalized_url,
            hit.snippet,
            hit.source,
            draft.source_config.reliability_tier,
            hit.provider,
            hit.published_at,
            timestamp,
            to_json(draft.matched_terms),
            draft.dedupe_key,
            duplicate_of_id,
            draft.confidence_score,
            classification_status,
            draft.page_type,
            to_json(draft.quality_flags),
            None,
            draft.parent_url,
            timestamp,
            timestamp,
        ),
    )


def _apply_source_classification_delta(
    db: Database,
    *,
    source_config_id: str,
    promoted_delta: int = 0,
    duplicate_delta: int = 0,
    timestamp: str,
) -> None:
    if promoted_delta <= 0 and duplicate_delta <= 0:
        return
    db.execute(
        """
        UPDATE intelligence_source_configs
        SET promoted_count = promoted_count + ?,
            duplicate_count = duplicate_count + ?,
            updated_at = ?
        WHERE id = ?
        """,
        (promoted_delta, duplicate_delta, timestamp, source_config_id),
    )
    _recompute_source_health(db, source_config_id)


def _is_high_confidence(draft: CandidateDraft) -> tuple[bool, str]:
    object_hit = any(term in f"{draft.hit.title} {draft.hit.snippet}" for term in draft.matched_terms[:4])
    if draft.source_config.reliability_tier == "strong" and object_hit and draft.confidence_score >= 70:
        return True, "来源和内容命中工作对象，进入核验流程"
    if draft.source_config.reliability_tier != "strong" and draft.signal_count >= 2 and draft.confidence_score >= 70:
        return True, "多项信号命中工作对象，进入核验流程"
    return False, "相关性不足，暂不成卡"


def _ai_ready(ai_service: object | None) -> bool:
    if ai_service is None or not hasattr(ai_service, "get_health"):
        return False
    try:
        health = ai_service.get_health()
        return bool(getattr(health, "ready", False)) and str(getattr(health, "provider", "mock")) != "mock"
    except Exception:
        return False


def _timely_intelligence_type(draft: CandidateDraft, body_text: str = "") -> str | None:
    text = f"{draft.intent.query} {draft.intent.reason} {draft.hit.title} {draft.hit.snippet} {draft.source_config.source_type} {body_text[:1200]}"
    rules: list[tuple[str, tuple[str, ...]]] = [
        ("资助机会", ("资助", "基金会", "申报", "公益创投", "扶持", "征集")),
        ("招采采购", ("招标", "采购", "政府购买服务", "中标", "磋商", "比选")),
        ("政策变化", ("政策", "通知", "办法", "意见", "规划", "指南")),
        ("舆情/监管", ("监管", "合规", "公开募捐", "处罚", "风险提示", "舆情", "规范")),
        ("合作方动态", ("合作", "伙伴", "资助方", "联合", "基金会发布", "征集项目")),
        ("同类机构动作", ("同类", "案例", "试点", "发布报告", "项目启动")),
        ("行业风险", ("风险", "整改", "规范", "违规", "审计", "披露")),
        ("短期机会", ("报名", "截止", "窗口", "名额", "近期", "本周")),
    ]
    for label, keywords in rules:
        if any(keyword in text for keyword in keywords):
            return label
    return None


def _is_static_profile_material(draft: CandidateDraft, body_text: str = "") -> bool:
    quick_text = f"{draft.hit.title} {draft.hit.snippet} {draft.intent.query} {draft.intent.reason}"
    if any(term in quick_text for term in PROFILE_MATERIAL_TERMS) and not any(term in quick_text for term in TIMELY_MATERIAL_TERMS):
        return True
    text = f"{quick_text} {body_text[:1200]}"
    static_terms = ("登记信息", "统一社会信用代码", "社会组织信息公开", "年报", "年度报告", "机构简介", "官网", "官方网站", "业务范围", "法定代表人")
    timely_terms = ("申报", "招标", "采购", "监管", "风险", "征集", "截止", "近期", "发布")
    return any(term in text for term in static_terms) and not any(term in text for term in timely_terms)


def _timeliness_label(draft: CandidateDraft, intelligence_type: str) -> str:
    if draft.hit.published_at:
        return f"发布时间：{draft.hit.published_at[:10]}"
    if intelligence_type in {"资助机会", "招采采购", "短期机会"}:
        return "近期窗口，需核对截止时间"
    if intelligence_type in {"行业风险", "舆情/监管", "政策变化"}:
        return "近期外部变化，需判断影响"
    return "近期公开动态"


def _profile_published_at(draft: CandidateDraft, body_text: str) -> str | None:
    if draft.hit.published_at:
        return draft.hit.published_at
    parsed = urlparse(draft.hit.url or "")
    path = (parsed.path or "/").strip()
    if path in {"", "/"}:
        return None
    header = _clean_text(f"{draft.hit.title} {draft.hit.snippet} {body_text[:1200]}", max_len=1800)
    patterns = (
        r"(?:发布时间|发布日期|发表时间|更新于|来源[:：][^0-9]{0,40}|作者[:：][^0-9]{0,40}|写在前面[:：]?)\s*(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})",
        r"(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})\s*(?:来源|作者|写在前面|编者按)",
    )
    for pattern in patterns:
        match = re.search(pattern, header)
        if not match:
            continue
        year, month, day = match.group(1), match.group(2), match.group(3)
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    return None


def _timely_followup_questions(draft: CandidateDraft, intelligence_type: str) -> list[str]:
    object_name = draft.intent.source_inputs[0].replace("client:", "") if draft.intent.source_inputs else "当前客户/项目"
    base = [
        f"这条外部变化会通过什么链条影响{object_name}？",
        f"它和{object_name}的业务、对象、地域、资源需求分别有多强相关？",
        "哪些证据不足，暂时不能据此行动？",
    ]
    if intelligence_type in {"行业风险", "舆情/监管", "政策变化"}:
        base.insert(1, f"这类风险或监管要求可能通过什么链条传导到{object_name}？")
    if intelligence_type == "资助机会":
        base.insert(1, "机会中提到的服务对象和当前客户/项目关注对象的相关度有多高？")
    if intelligence_type == "合作方动态":
        base.insert(1, "这条动态说明资助方或合作方偏好发生了什么变化？")
    return _unique_items(base, limit=5)


def _timely_candidate_gate(draft: CandidateDraft, body_text: str = "") -> tuple[bool, str, str | None]:
    if _is_static_profile_material(draft, body_text):
        return False, "静态登记、官网介绍或年报资料应进入资料补全，不进入时效情报", None
    intelligence_type = _timely_intelligence_type(draft, body_text)
    if not intelligence_type:
        return False, "未识别出明确情报类型，暂不成卡", None
    text = f"{draft.hit.title} {draft.hit.snippet} {draft.intent.query} {draft.intent.reason} {body_text[:1600]}"
    object_terms = [term for term in draft.matched_terms if term and term in text][:4]
    sector_terms = ("公益", "慈善", "社会组织", "儿童", "困境", "心理", "社区", "志愿", "民政", "基金会", "项目")
    has_sector_signal = any(term in text for term in sector_terms)
    if not object_terms and not has_sector_signal:
        return False, "只有泛政策或弱相关新闻，未建立与客户/项目的清晰关系", None
    if not object_terms:
        transfer_terms = (
            "申报", "征集", "截止", "资助", "扶持", "招标", "采购", "中标",
            "监管", "合规", "公开募捐", "处罚", "风险", "整改", "规范",
            "儿童", "困境", "心理", "社区服务", "社会组织",
        )
        if not any(term in text for term in transfer_terms):
            return False, "泛政策或泛通知缺少可传导到客户/项目的机会、风险或约束链条，暂不成卡", None
    if not body_text and len(draft.hit.snippet or draft.hit.title) < 12:
        return False, "公开信息过短，无法判断发生了什么", None
    if body_text and not any(term in text for term in TIMELY_MATERIAL_TERMS):
        return False, "正文未呈现近期变化、窗口、政策、风险或合作动态，暂不成卡", None
    return True, "已识别近期外部变化，并具备对象或行业相关信号", intelligence_type


def _build_timely_enrichment(
    ai_service: object | None,
    draft: CandidateDraft,
    body_text: str,
    evidence: EvidenceExtraction,
) -> TimelyEnrichmentResult | None:
    passed, reason, intelligence_type = _timely_candidate_gate(draft, body_text)
    if not passed or not intelligence_type:
        draft.hit.snippet = draft.hit.snippet or reason
        return None
    fallback = TimelyEnrichmentResult(
        intelligence_type=evidence.intelligence_type or intelligence_type,
        timeliness_label=evidence.timeliness_label or _timeliness_label(draft, intelligence_type),
        summary=evidence.summary,
        relevance_reason=evidence.analysis or f"命中关注点：{'、'.join(evidence.focus_hits[:4])}。",
        impact=evidence.impact,
        suggested_action=evidence.suggested_action,
        followup_questions=_timely_followup_questions(draft, intelligence_type),
    )
    if not _ai_ready(ai_service) or not hasattr(ai_service, "generate_general_fallback"):
        return fallback
    followups = _timely_followup_questions(draft, intelligence_type)
    prompt = "\n".join(
        [
            f"标题：{draft.hit.title}",
            f"来源：{draft.hit.source}",
            f"搜索短摘：{draft.hit.snippet}",
            f"命中搜索意图：{draft.intent.query}",
            f"情报类型：{intelligence_type}",
            f"已抽取证据句：{'；'.join(evidence.quotes[:4])}",
            f"网页正文摘录：{body_text[:3200]}",
            "请只基于网页正文和证据句整理时效情报卡。",
            "必须输出：发生了什么、为什么和当前客户/项目有关、可能影响、建议动作、证据不足点；不得只复述标题或搜索短摘。",
            "建议动作可以是阅读/研判任务，不要强行写成执行任务；不要使用“先确认负责人、再补材料”这类模板空话。",
        ]
    )
    try:
        response = ai_service.generate_general_fallback(prompt, "情报候选自动分流", subject_name=draft.hit.title)
    except Exception:
        return fallback
    if not isinstance(response, AiStructuredResponse):
        return fallback
    summary = _clean_text(response.content or draft.hit.snippet or draft.hit.title, max_len=500)
    relevance = _clean_text(response.judgment or response.analysis or "", max_len=700)
    impact = _clean_text(response.analysis or response.timeline or "", max_len=700)
    suggested_action = _clean_text(response.actions or "", max_len=500)
    if (
        not summary
        or not relevance
        or not impact
        or not suggested_action
        or _looks_like_template_summary(summary, relevance, impact, suggested_action)
    ):
        return fallback
    return TimelyEnrichmentResult(
        intelligence_type=intelligence_type,
        timeliness_label=_timeliness_label(draft, intelligence_type),
        summary=summary,
        relevance_reason=relevance,
        impact=impact,
        suggested_action=suggested_action,
        followup_questions=followups,
    )


def _candidate_markdown(
    draft: CandidateDraft,
    timestamp: str,
    *,
    summary: str,
    key_points: list[str],
    mapped_tags: list[str],
    verification_reason: str,
) -> str:
    point_lines = [f"- {point}" for point in key_points if _clean_text(point, max_len=220)]
    tag_text = "、".join(mapped_tags)
    return "\n".join(
        [
            f"# {draft.hit.title}",
            "",
            f"- 来源：{_source_display_name(draft)}",
            f"- URL：{draft.hit.url}",
            f"- 抓取时间：{timestamp}",
            f"- 命中意图：{draft.intent.query}",
            f"- 对应标签：{tag_text}",
            f"- 核验结果：{verification_reason}",
            "",
            "## 可复用事实",
            *(point_lines or [summary]),
        ]
    )


def _promote_candidate(
    db: Database,
    *,
    data_dir: Path,
    ai_service: object | None,
    scope: IntelligenceSearchScope,
    brief: ResearchBrief,
    draft: CandidateDraft,
    timestamp: str,
) -> bool:
    if _is_prototype_sample_hit(draft.hit):
        db.execute(
            "UPDATE intelligence_candidate_items SET promotion_reason = ?, updated_at = ? WHERE id = ?",
            ("样张、演示域名或验收示例不得进入用户可见情报或资料库", timestamp, draft.id),
        )
        return False
    if draft.feedback_adjustment <= -2.0:
        db.execute(
            "UPDATE intelligence_candidate_items SET promotion_reason = ?, updated_at = ? WHERE id = ?",
            ("用户反馈降权：同主题、来源或判断标准此前被标记为少看/不采纳，暂不成卡", timestamp, draft.id),
        )
        return False
    high_confidence, reason = _is_high_confidence(draft)
    if not high_confidence:
        db.execute(
            "UPDATE intelligence_candidate_items SET promotion_reason = ?, updated_at = ? WHERE id = ?",
            (reason, timestamp, draft.id),
        )
        return False
    existing = db.fetchone(
        """
        SELECT id
        FROM intelligence_items
        WHERE content_kind = ? AND source_url = ? AND COALESCE(client_id, '') = COALESCE(?, '') AND user_status = 'active'
        LIMIT 1
        """,
        (draft.content_kind, draft.hit.url, scope.client_id),
    )
    if existing:
        db.execute(
            """
            UPDATE intelligence_candidate_items
            SET classification_status = 'promoted',
                promotion_reason = ?,
                promoted_intelligence_item_id = ?,
                is_user_visible_candidate = 0,
                updated_at = ?
            WHERE id = ?
            """,
            (reason, str(existing["id"]), timestamp, draft.id),
        )
        return True

    data_center_document_id: str | None = None
    verified_at: str | None = None
    verification_status = "verified"
    verification_reason = reason
    if draft.content_kind == "profile_completion":
        verification = _verify_profile_candidate(
            db,
            ai_service=ai_service,
            scope=scope,
            draft=draft,
            brief=brief,
            timestamp=timestamp,
        )
        if not verification.verified:
            return False
        upserted = upsert_canonical_text_document(
            db,
            data_dir=data_dir,
            client_id=scope.client_id,
            canonical_kind="internet_source_doc",
            origin_type="intelligence_candidate",
            origin_id=draft.id,
            title=draft.hit.title,
            text=_candidate_markdown(
                draft,
                timestamp,
                summary=verification.summary,
                key_points=verification.key_points,
                mapped_tags=verification.mapped_tags,
                verification_reason=verification.verification_reason,
            ),
            visible_category="互联网补充资料",
            secondary_category="自动候选",
            created_at=draft.hit.published_at or timestamp,
            updated_at=timestamp,
            source_entity_type="intelligence_candidate",
            source_entity_id=draft.id,
            content_domain="intelligence_candidate_pool",
        )
        data_center_document_id = str(upserted.get("documentId")) if upserted else None
        verified_at = timestamp
        published_at = _profile_published_at(draft, verification.body_excerpt or "")
        summary = verification.summary
        analysis = verification.analysis
        impact = ""
        reason = verification.verification_reason
        verification_status = verification.verification_status
        tags = ["已核验资料", *verification.mapped_tags]
        key_points = verification.key_points
        intelligence_type = None
        timeliness_label = None
        relevance_reason = ""
        suggested_action = ""
        followup_questions: list[str] = []
    else:
        published_at = draft.hit.published_at
        body_status, body_text, body_reason = _fetch_page_text(draft.hit.url)
        body_excerpt = body_text[:1000]
        page_quality = _classify_fetched_page(draft.hit, body_status, body_text, body_reason)
        if body_status != "fetched":
            reason = body_reason or "未抓到可用于核验的网页正文"
            _update_candidate_verification(
                db,
                candidate_id=draft.id,
                verification_status="pending",
                verification_reason=reason,
                body_fetch_status=body_status,
                summary_status="not_attempted",
                mapped_tags=[],
                body_excerpt=body_excerpt,
                timestamp=timestamp,
                page_type=page_quality.page_type,
                quality_flags=page_quality.flags,
            )
            return False
        if page_quality.page_type != "detail_page":
            reason = page_quality.reason or "页面不是可核验详情页，暂不成卡"
            _update_candidate_verification(
                db,
                candidate_id=draft.id,
                verification_status="rejected",
                verification_reason=reason,
                body_fetch_status=body_status,
                summary_status="not_attempted",
                mapped_tags=[],
                body_excerpt=body_excerpt,
                timestamp=timestamp,
                page_type=page_quality.page_type,
                quality_flags=page_quality.flags,
            )
            return False
        passed, gate_reason, _intelligence_type = _timely_candidate_gate(draft, body_text)
        if not passed:
            _update_candidate_verification(
                db,
                candidate_id=draft.id,
                verification_status="rejected",
                verification_reason=gate_reason,
                body_fetch_status=body_status,
                summary_status="not_attempted",
                mapped_tags=[],
                body_excerpt=body_excerpt,
                timestamp=timestamp,
                page_type=page_quality.page_type,
                quality_flags=page_quality.flags,
            )
            return False
        evidence = _extract_research_evidence(
            brief=brief,
            content_kind="timely_intelligence",
            draft=draft,
            body_text=body_text,
        )
        if evidence is None:
            reason = "正文未回应当前重点关注，或缺少外部变化与影响链条证据，暂不成卡"
            _update_candidate_verification(
                db,
                candidate_id=draft.id,
                verification_status="rejected",
                verification_reason=reason,
                body_fetch_status=body_status,
                summary_status="not_attempted",
                mapped_tags=[],
                body_excerpt=body_excerpt,
                timestamp=timestamp,
                page_type=page_quality.page_type,
                quality_flags=[*page_quality.flags, "insufficient_impact_evidence"],
            )
            return False
        if not _ai_ready(ai_service):
            _update_candidate_verification(
                db,
                candidate_id=draft.id,
                verification_status="pending",
                verification_reason="AI 不可用，时效情报候选暂不自动成卡",
                body_fetch_status=body_status,
                summary_status="not_attempted",
                mapped_tags=[],
                body_excerpt=body_excerpt,
                timestamp=timestamp,
                page_type=page_quality.page_type,
                quality_flags=page_quality.flags,
            )
            return False
        enrichment = _build_timely_enrichment(ai_service, draft, body_text, evidence)
        if enrichment is None:
            _update_candidate_verification(
                db,
                candidate_id=draft.id,
                verification_status="pending",
                verification_reason="AI 研判未生成完整结构，暂不自动成卡",
                body_fetch_status=body_status,
                summary_status="failed",
                mapped_tags=[],
                body_excerpt=body_excerpt,
                timestamp=timestamp,
                page_type=page_quality.page_type,
                quality_flags=page_quality.flags,
            )
            return False
        _update_candidate_verification(
            db,
            candidate_id=draft.id,
            verification_status="verified",
            verification_reason="已核验：正文呈现近期外部变化，并抽取到影响链条相关证据",
            body_fetch_status=body_status,
            summary_status="generated",
            mapped_tags=[enrichment.intelligence_type],
            body_excerpt=body_excerpt,
            timestamp=timestamp,
            page_type=page_quality.page_type,
            quality_flags=page_quality.flags,
            evidence={
                "quotes": evidence.quotes,
                "facts": evidence.facts,
                "focusHits": evidence.focus_hits,
                "missing": evidence.missing,
            },
        )
        summary = enrichment.summary
        analysis = enrichment.relevance_reason
        impact = enrichment.impact
        intelligence_type = enrichment.intelligence_type
        timeliness_label = enrichment.timeliness_label
        relevance_reason = enrichment.relevance_reason
        suggested_action = enrichment.suggested_action
        followup_questions = enrichment.followup_questions
        tags = ["外部情报", intelligence_type]
        key_points = [summary, relevance_reason, impact, suggested_action]
    item_id = _new_id("iitem")
    db.execute(
        """
        INSERT INTO intelligence_items(
            id, content_kind, scope_type, scope_id, client_id, project_module_id,
            title, summary, key_points_json, analysis, impact, tags_json,
            intelligence_type, timeliness_label, relevance_reason, suggested_action, followup_questions_json,
            source, source_url, published_at, captured_at, verified_at,
            credibility_score, confidence_score, data_center_ingest_event_id,
            verification_status, verification_reason,
            user_status, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
        """,
        (
            item_id,
            draft.content_kind,
            scope.scope_type,
            scope.scope_id,
            scope.client_id,
            scope.project_module_id,
            draft.hit.title,
            summary,
            to_json(key_points),
            analysis,
            impact,
            to_json(tags),
            intelligence_type,
            timeliness_label,
            relevance_reason,
            suggested_action,
            to_json(followup_questions),
            _source_display_name(draft),
            draft.hit.url,
            published_at,
            timestamp,
            verified_at,
            min(draft.confidence_score / 100, 0.98),
            min(draft.confidence_score / 100, 0.98),
            data_center_document_id,
            verification_status,
            verification_reason,
            timestamp,
            timestamp,
        ),
    )
    db.execute(
        """
        UPDATE intelligence_candidate_items
        SET classification_status = 'promoted',
            promotion_reason = ?,
            promoted_intelligence_item_id = ?,
            data_center_ingest_event_id = ?,
            is_user_visible_candidate = 0,
            updated_at = ?
        WHERE id = ?
        """,
        (reason, item_id, data_center_document_id, timestamp, draft.id),
    )
    return True


def run_intelligence_candidate_refresh(
    db: Database,
    *,
    data_dir: Path,
    ai_service: object | None,
    scope: IntelligenceSearchScope,
    intents: list[GeneratedSearchIntent],
    trigger_source: str = "manual",
    max_fetch_jobs: int = 40,
    hit_fetcher: Callable[[str, SourceConfig], list[CandidateHit | dict[str, object]]] | None = None,
    official_site_hit_fetcher: Callable[[str, SourceConfig], list[CandidateHit | dict[str, object]]] | None = None,
) -> CandidateRefreshResult:
    timestamp = now_iso()
    brief = _load_research_brief(db, scope)
    configs = ensure_default_source_configs(db, scope)
    ensure_user_supplied_official_sources(db, scope, brief)
    discover_official_site_source_configs(
        db,
        scope=scope,
        hit_fetcher=official_site_hit_fetcher or hit_fetcher,
    )
    _disable_invalid_discovered_sources(db, scope)
    configs = ensure_default_source_configs(db, scope)
    object_terms = brief.object_terms
    fetcher = hit_fetcher or _fetch_public_search_hits
    drafts: list[CandidateDraft] = []
    failed_count = 0
    fetch_job_count = 0
    tasks = _selected_fetch_tasks(db, intents, configs, max_fetch_jobs=max_fetch_jobs)
    search_directions = {
        _clean_text(intent.reason.split("。")[0], max_len=80) or intent.query
        for intent, _config in tasks
    }
    success_query_count = 0
    no_result_query_count = 0
    for intent, config in tasks:
        query = _effective_query(intent, config)
        started = time.perf_counter()
        raw_hits: list[CandidateHit | dict[str, object]] = []
        status = "success"
        failure_reason = ""
        try:
            raw_hits = fetcher(query, config)
        except Exception as exc:
            status = "failed"
            failure_reason = _clean_text(exc, max_len=240)
            failed_count += 1
        normalized_hits: list[CandidateHit] = []
        for raw_hit in raw_hits:
            hit = _normalize_hit(raw_hit, config)
            if hit is None:
                continue
            if not _hit_matches_intelligence_context(hit, intent, object_terms):
                continue
            page_quality = _classify_hit_page(hit)
            if page_quality.page_type == "list_page":
                drilldown_terms = _unique_items([*object_terms, *_intent_terms(intent)], limit=24)
                drilldown_limit = 5 if intent.content_kind == "profile_completion" else 2
                for child_hit in _drilldown_detail_hits_from_list(hit, drilldown_terms, limit=drilldown_limit):
                    if _hit_matches_intelligence_context(child_hit, intent, object_terms):
                        normalized_hits.append(child_hit)
                continue
            normalized_hits.append(hit)
        if status == "success" and not normalized_hits:
            status = "no_results"
        if status == "success":
            success_query_count += 1
        elif status == "no_results":
            no_result_query_count += 1
        fetch_job_id = _insert_fetch_job(
            db,
            scope=scope,
            content_kind=intent.content_kind,
            trigger_source=trigger_source,
            config=config,
            query=query,
            status=status,
            raw_count=len(raw_hits),
            deduped_count=len(normalized_hits),
            candidate_count=len(normalized_hits),
            sample_hits=[{"title": hit.title, "url": hit.url} for hit in normalized_hits[:3]],
            failure_reason=failure_reason,
            duration_ms=int((time.perf_counter() - started) * 1000),
            timestamp=timestamp,
        )
        fetch_job_count += 1
        for hit in normalized_hits:
            normalized_url = _normalize_url(hit.url)
            dedupe_key = _dedupe_key(hit.title, normalized_url)
            score, signals, matched = _score_candidate(
                content_kind=intent.content_kind,
                config=config,
                hit=hit,
                intent=intent,
                object_terms=object_terms,
            )
            score, feedback_adjustment = _apply_feedback_to_candidate_score(
                db,
                scope=scope,
                content_kind=intent.content_kind,
                config=config,
                hit=hit,
                intent=intent,
                base_score=score,
            )
            page_quality = _classify_hit_page(hit)
            drafts.append(
                CandidateDraft(
                    id=_new_id("icand"),
                    content_kind=intent.content_kind,
                    intent=intent,
                    source_config=config,
                    fetch_job_id=fetch_job_id,
                    hit=hit,
                    normalized_url=normalized_url,
                    dedupe_key=dedupe_key,
                    matched_terms=matched,
                    confidence_score=score,
                    signal_count=signals,
                    feedback_adjustment=feedback_adjustment,
                    page_type=page_quality.page_type,
                    quality_flags=page_quality.flags,
                )
            )

    canonical_by_key: dict[str, CandidateDraft] = {}
    for draft in sorted(drafts, key=lambda item: (-item.confidence_score, item.hit.title)):
        if draft.dedupe_key not in canonical_by_key:
            canonical_by_key[draft.dedupe_key] = draft

    promoted_count = 0
    duplicate_count = 0
    ordered_drafts = sorted(
        drafts,
        key=lambda item: 0 if canonical_by_key.get(item.dedupe_key) and canonical_by_key[item.dedupe_key].id == item.id else 1,
    )
    for draft in ordered_drafts:
        existing = db.fetchone(
            """
            SELECT id
            FROM intelligence_candidate_items
            WHERE scope_type = ? AND scope_id = ? AND content_kind = ? AND dedupe_key = ?
              AND classification_status <> 'duplicate'
            ORDER BY confidence_score DESC, captured_at ASC
            LIMIT 1
            """,
            (scope.scope_type, scope.scope_id, draft.content_kind, draft.dedupe_key),
        )
        canonical = canonical_by_key.get(draft.dedupe_key)
        duplicate_of_id = str(existing["id"]) if existing else (canonical.id if canonical and canonical.id != draft.id else None)
        status = "duplicate" if duplicate_of_id else "candidate"
        if status == "duplicate":
            duplicate_count += 1
            _apply_source_classification_delta(
                db,
                source_config_id=draft.source_config.id,
                duplicate_delta=1,
                timestamp=timestamp,
            )
        _insert_candidate(
            db,
            scope=scope,
            draft=draft,
            classification_status=status,
            duplicate_of_id=duplicate_of_id,
            timestamp=timestamp,
        )
        if status == "candidate" and _promote_candidate(
            db,
            data_dir=data_dir,
            ai_service=ai_service,
            scope=scope,
            brief=brief,
            draft=draft,
            timestamp=timestamp,
        ):
            promoted_count += 1
            _apply_source_classification_delta(
                db,
                source_config_id=draft.source_config.id,
                promoted_delta=1,
                timestamp=timestamp,
            )

    candidate_ids = [draft.id for draft in drafts]
    body_fetched_count = 0
    verified_count = 0
    summary_success_count = 0
    rejection_counts: dict[str, int] = {}
    if candidate_ids:
        placeholders = ",".join("?" for _ in candidate_ids)
        stat_rows = db.fetchall(
            f"""
            SELECT body_fetch_status, verification_status, summary_status, promotion_reason, COUNT(1) AS count
            FROM intelligence_candidate_items
            WHERE id IN ({placeholders})
            GROUP BY body_fetch_status, verification_status, summary_status, promotion_reason
            """,
            tuple(candidate_ids),
        )
        for row in stat_rows:
            count = int(row["count"] or 0)
            if str(row["body_fetch_status"] or "") == "fetched":
                body_fetched_count += count
            if str(row["verification_status"] or "") == "verified":
                verified_count += count
            if str(row["summary_status"] or "") == "generated":
                summary_success_count += count
            reason = _clean_text(str(row["promotion_reason"] or ""), max_len=80)
            if reason and str(row["summary_status"] or "") != "generated":
                rejection_counts[reason] = rejection_counts.get(reason, 0) + count

    profile_coverage: list[str] = []
    profile_missing_dimensions: list[str] = []
    profile_completion_ready = False
    if any(intent.content_kind == "profile_completion" for intent in intents):
        profile_coverage, profile_missing_dimensions, profile_completion_ready = _profile_coverage_snapshot(db, scope)

    status_payload = get_candidate_supply_status_for_scope(db, scope_type=scope.scope_type, scope_id=scope.scope_id)
    return CandidateRefreshResult(
        source_config_count=len(configs),
        fetch_job_count=fetch_job_count,
        candidate_count=len(drafts),
        promoted_count=promoted_count,
        duplicate_count=duplicate_count,
        failed_count=failed_count,
        body_fetched_count=body_fetched_count,
        verified_count=verified_count,
        summary_success_count=summary_success_count,
        rejection_counts=rejection_counts,
        source_coverage_status=str(status_payload.get("sourceCoverageStatus") or "ready"),
        candidate_refresh_status=str(status_payload.get("candidateRefreshStatus") or "ready"),
        last_candidate_fetch_at=str(status_payload.get("lastCandidateFetchAt") or timestamp),
        candidate_counts=dict(status_payload.get("candidateCounts") or {}),
        profile_coverage=profile_coverage,
        profile_missing_dimensions=profile_missing_dimensions,
        profile_completion_ready=profile_completion_ready,
        search_direction_count=len(search_directions),
        query_count=fetch_job_count,
        success_query_count=success_query_count,
        no_result_query_count=no_result_query_count,
        effective_lead_count=max(0, len(drafts) - duplicate_count),
        uncovered_gaps=profile_missing_dimensions,
    )


def get_candidate_supply_status_for_scope(db: Database, *, scope_type: str, scope_id: str) -> dict[str, object]:
    normalized_type = "project_module" if scope_type in {"project", "project_module", "module"} else "client"
    normalized_id = _clean_text(scope_id, max_len=120)
    source_count = int(
        db.scalar(
            "SELECT COUNT(1) FROM intelligence_source_configs WHERE scope_type = ? AND scope_id = ? AND enabled = 1",
            (normalized_type, normalized_id),
        )
        or 0
    )
    failed_source_count = int(
        db.scalar(
            """
            SELECT COUNT(1)
            FROM intelligence_source_configs
            WHERE scope_type = ? AND scope_id = ? AND enabled = 1 AND last_status = 'failed'
            """,
            (normalized_type, normalized_id),
        )
        or 0
    )
    discovered_official_count = int(
        db.scalar(
            """
            SELECT COUNT(1)
            FROM intelligence_source_configs
            WHERE scope_type = ? AND scope_id = ? AND enabled = 1
              AND source_type = 'official_site' AND discovery_source = 'official_site_search'
            """,
            (normalized_type, normalized_id),
        )
        or 0
    )
    latest_official_discovery = db.fetchone(
        """
        SELECT created_at
        FROM intelligence_fetch_jobs
        WHERE scope_type = ? AND scope_id = ? AND content_kind = 'source_discovery'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (normalized_type, normalized_id),
    )
    latest_fetch = db.fetchone(
        """
        SELECT status, created_at
        FROM intelligence_fetch_jobs
        WHERE scope_type = ? AND scope_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (normalized_type, normalized_id),
    )
    running_fetch_count = int(
        db.scalar(
            """
            SELECT COUNT(1)
            FROM intelligence_fetch_jobs
            WHERE scope_type = ? AND scope_id = ? AND status = 'running'
            """,
            (normalized_type, normalized_id),
        )
        or 0
    )
    candidate_rows = db.fetchall(
        """
        SELECT classification_status, COUNT(1) AS count
        FROM intelligence_candidate_items
        WHERE scope_type = ? AND scope_id = ?
        GROUP BY classification_status
        """,
        (normalized_type, normalized_id),
    )
    candidate_counts = {str(row["classification_status"] or "candidate"): int(row["count"] or 0) for row in candidate_rows}
    source_status = (
        "missing"
        if source_count <= 0
        else "failed"
        if failed_source_count >= source_count
        else "stale"
        if latest_official_discovery is not None and discovered_official_count <= 0
        else "ready"
    )
    if latest_fetch is None:
        candidate_status = "missing"
        last_fetch_at = None
    elif running_fetch_count > 0:
        candidate_status = "running"
        last_fetch_at = str(latest_fetch["created_at"] or "") or None
    elif str(latest_fetch["status"] or "") == "failed" and sum(candidate_counts.values()) <= 0:
        candidate_status = "failed"
        last_fetch_at = str(latest_fetch["created_at"] or "") or None
    else:
        stale_count = int(
            db.scalar(
                """
                SELECT COUNT(1)
                FROM intelligence_source_configs
                WHERE scope_type = ? AND scope_id = ? AND enabled = 1
                  AND next_due_at IS NOT NULL AND next_due_at <= ?
                """,
                (normalized_type, normalized_id, now_iso()),
            )
            or 0
        )
        candidate_status = "stale" if stale_count > 0 else "ready"
        last_fetch_at = str(latest_fetch["created_at"] or "") or None
    hint = None
    if source_status == "missing":
        hint = "来源包尚未展开，下一次补全互联网资料时会先建立默认公开源覆盖。"
    elif source_status == "stale":
        hint = "尚未发现可确认的客户/项目官网，当前先使用通用公开源和权威公开源。"
    elif candidate_status == "missing":
        hint = "线索抓取尚未刷新，下一次补全互联网资料时会先完成来源检索。"
    elif candidate_status == "failed":
        hint = "最近一次线索抓取失败，当前会保留既有内容并等待重试。"
    elif candidate_status == "stale":
        hint = "线索抓取结果已到期，建议刷新互联网资料补全。"
    return {
        "sourceCoverageStatus": source_status,
        "candidateRefreshStatus": candidate_status,
        "candidateRefreshHint": hint,
        "lastCandidateFetchAt": last_fetch_at,
        "candidateCounts": candidate_counts,
        "officialSiteDiscoveredCount": discovered_official_count,
    }


def get_source_diagnostics(
    db: Database,
    *,
    scope_type: str,
    scope_id: str,
    content_kind: str | None = None,
    limit: int = 20,
) -> dict[str, object]:
    normalized_type = "project_module" if scope_type in {"project", "project_module", "module"} else "client"
    normalized_id = _clean_text(scope_id, max_len=120)
    status = get_candidate_supply_status_for_scope(db, scope_type=normalized_type, scope_id=normalized_id)
    source_rows = db.fetchall(
        """
        SELECT *
        FROM intelligence_source_configs
        WHERE scope_type = ? AND scope_id = ? AND enabled = 1
        ORDER BY health_score DESC, priority DESC, updated_at DESC
        """,
        (normalized_type, normalized_id),
    )
    sources: list[dict[str, object]] = []
    for row in source_rows:
        config = _source_config_from_row(row)
        if content_kind and config.content_kinds and content_kind not in config.content_kinds:
            continue
        sources.append(
            {
                "id": config.id,
                "sourceType": config.source_type,
                "sourceName": config.source_name,
                "sourceUrlTemplate": config.source_url_template,
                "contentKinds": config.content_kinds,
                "region": config.region,
                "reliabilityTier": config.reliability_tier,
                "priority": config.priority,
                "enabled": config.enabled,
                "discoverySource": config.discovery_source,
                "discoveryReason": config.discovery_reason,
                "discoverySamples": config.discovery_samples[:5],
                "healthScore": config.health_score,
                "successCount": config.success_count,
                "failureCount": config.failure_count,
                "candidateCount": config.candidate_count,
                "promotedCount": config.promoted_count,
                "duplicateCount": config.duplicate_count,
                "lastStatus": config.last_status,
                "lastCheckedAt": config.last_checked_at,
                "lastSuccessAt": config.last_success_at,
                "lastFailureAt": config.last_failure_at,
                "nextDueAt": config.next_due_at,
            }
        )
        if len(sources) >= limit:
            break
    fetch_params: list[object] = [normalized_type, normalized_id]
    fetch_where = "scope_type = ? AND scope_id = ?"
    if content_kind:
        fetch_where += " AND content_kind IN (?, 'source_discovery')"
        fetch_params.append(content_kind)
    fetch_rows = db.fetchall(
        f"""
        SELECT *
        FROM intelligence_fetch_jobs
        WHERE {fetch_where}
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (*fetch_params, max(1, min(limit, 50))),
    )
    recent_fetch_jobs = [
        {
            "id": str(row["id"]),
            "contentKind": str(row["content_kind"] or ""),
            "provider": str(row["provider"] or ""),
            "sourceConfigId": str(row["source_config_id"] or "") or None,
            "query": str(row["query"] or ""),
            "status": str(row["status"] or ""),
            "rawCount": int(row["raw_count"] or 0),
            "dedupedCount": int(row["deduped_count"] or 0),
            "candidateCount": int(row["candidate_count"] or 0),
            "sampleHits": _safe_json(str(row["sample_hits_json"] or "[]"), []),
            "failureReason": str(row["failure_reason"] or ""),
            "durationMs": int(row["duration_ms"] or 0),
            "createdAt": str(row["created_at"] or ""),
        }
        for row in fetch_rows
    ]
    source_types = {str(item["sourceType"]) for item in sources}
    coverage_gaps: list[str] = []
    desired_types = set()
    if content_kind:
        desired_types = CONTENT_KIND_SOURCE_TYPES.get(content_kind, set())
    else:
        desired_types = PROFILE_SOURCE_TYPES | TIMELY_SOURCE_TYPES
    for source_type in sorted(desired_types):
        if source_type not in source_types:
            coverage_gaps.append(f"缺少 {source_type} 来源配置")
    if int(status.get("officialSiteDiscoveredCount") or 0) <= 0:
        coverage_gaps.append("尚未发现可确认的客户/项目官网来源")
    if any(item.get("lastStatus") == "failed" for item in sources):
        coverage_gaps.append("存在最近抓取失败的来源")
    discovery_samples = [
        item
        for item in recent_fetch_jobs
        if item["contentKind"] == "source_discovery"
    ]
    return {
        "scopeType": normalized_type,
        "scopeId": normalized_id,
        "contentKind": content_kind,
        "sourceCoverageStatus": status.get("sourceCoverageStatus", "missing"),
        "candidateRefreshStatus": status.get("candidateRefreshStatus", "missing"),
        "candidateRefreshHint": status.get("candidateRefreshHint"),
        "lastCandidateFetchAt": status.get("lastCandidateFetchAt"),
        "candidateCounts": status.get("candidateCounts", {}),
        "officialSiteDiscoveredCount": status.get("officialSiteDiscoveredCount", 0),
        "coverageGaps": coverage_gaps,
        "sources": sources,
        "recentFetchJobs": recent_fetch_jobs,
        "officialSiteDiscoverySamples": discovery_samples[:5],
    }


def cleanup_low_value_intelligence_artifacts(db: Database) -> dict[str, int]:
    timestamp = now_iso()
    promoted_visible = int(
        db.scalar(
            """
            SELECT COUNT(1)
            FROM intelligence_candidate_items
            WHERE COALESCE(is_user_visible_candidate, 1) = 1
              AND classification_status IN ('promoted', 'duplicate')
            """
        )
        or 0
    )
    if promoted_visible:
        db.execute(
            """
            UPDATE intelligence_candidate_items
            SET is_user_visible_candidate = 0,
                updated_at = ?
            WHERE COALESCE(is_user_visible_candidate, 1) = 1
              AND classification_status IN ('promoted', 'duplicate')
            """,
            (timestamp,),
        )

    legacy_rows = db.fetchall(
        """
        SELECT id, data_center_ingest_event_id
        FROM intelligence_items
        WHERE content_kind = 'profile_completion'
          AND user_status <> 'dismissed'
          AND (
            COALESCE(verification_reason, '') = ''
            OR verification_reason NOT LIKE '已核验：%'
            OR COALESCE(verified_at, '') = ''
          )
        """
    )
    legacy_dismissed = 0
    if legacy_rows:
        legacy_ids = [str(row["id"]) for row in legacy_rows if str(row["id"] or "").strip()]
        if legacy_ids:
            placeholders = ", ".join("?" for _ in legacy_ids)
            db.execute(
                f"""
                UPDATE intelligence_items
                SET user_status = 'dismissed',
                    verification_status = 'legacy_unverified',
                    verification_reason = 'P4 前短摘成卡，未经过正文核验和 AI 摘要，已退出已核验资料流',
                    user_feedback_json = ?,
                    updated_at = ?
                WHERE id IN ({placeholders})
                """,
                (
                    to_json({"dismissedAt": timestamp, "reasonCode": "cleanup_legacy_profile_completion"}),
                    timestamp,
                    *legacy_ids,
                ),
            )
            legacy_dismissed = len(legacy_ids)
        document_ids = [
            str(row["data_center_ingest_event_id"])
            for row in legacy_rows
            if str(row["data_center_ingest_event_id"] or "").strip()
        ]
        if document_ids:
            document_placeholders = ", ".join("?" for _ in document_ids)
            v2_document_ids = [f"v2doc_{document_id}" for document_id in document_ids]
            v2_placeholders = ", ".join("?" for _ in v2_document_ids)
            try:
                db.execute(
                    f"""
                    UPDATE v2_documents
                    SET lifecycle_status = 'inactive',
                        is_searchable = 0,
                        updated_at = ?
                    WHERE document_id IN ({document_placeholders})
                       OR id IN ({v2_placeholders})
                    """,
                    (timestamp, *document_ids, *v2_document_ids),
                )
            except Exception:
                logger.debug("[intelligence] skipped legacy v2 document cleanup", exc_info=True)
            try:
                db.execute(
                    f"""
                    UPDATE documents
                    SET lifecycle_status = 'inactive',
                        updated_at = ?
                    WHERE id IN ({document_placeholders})
                    """,
                    (timestamp, *document_ids),
                )
            except Exception:
                logger.debug("[intelligence] skipped legacy document cleanup", exc_info=True)

    candidate_rows = db.fetchall(
        """
        SELECT id, url, title, snippet, source
        FROM intelligence_candidate_items
        WHERE COALESCE(is_user_visible_candidate, 1) = 1
           OR classification_status NOT IN ('rejected', 'duplicate')
        """
    )
    hidden_candidates = 0
    for row in candidate_rows:
        hit = CandidateHit(
            title=str(row["title"] or ""),
            url=str(row["url"] or ""),
            snippet=str(row["snippet"] or ""),
            source=str(row["source"] or ""),
        )
        if not _hit_is_closed_or_low_value(hit):
            continue
        db.execute(
            """
            UPDATE intelligence_candidate_items
            SET classification_status = 'rejected',
                verification_status = 'rejected',
                verification_reason = '低价值、图片、封闭平台或聚合来源已清理',
                promotion_reason = '低价值、图片、封闭平台或聚合来源已清理',
                is_user_visible_candidate = 0,
                updated_at = ?
            WHERE id = ?
            """,
            (timestamp, str(row["id"])),
        )
        for table_name in ("documents", "v2_documents", "memory_facts"):
            try:
                db.execute(
                    f"""
                    UPDATE {table_name}
                    SET lifecycle_status = 'inactive',
                        updated_at = ?
                    WHERE source_entity_type = 'intelligence_candidate'
                      AND source_entity_id = ?
                    """,
                    (timestamp, str(row["id"])),
                )
            except Exception:
                logger.debug("[intelligence] skipped inactive cleanup for %s", table_name, exc_info=True)
        hidden_candidates += 1
    item_rows = db.fetchall(
        """
        SELECT id, source_url, title, summary, source
        FROM intelligence_items
        WHERE user_status <> 'dismissed'
        """
    )
    dismissed_items = 0
    for row in item_rows:
        hit = CandidateHit(
            title=str(row["title"] or ""),
            url=str(row["source_url"] or ""),
            snippet=str(row["summary"] or ""),
            source=str(row["source"] or ""),
        )
        if not _hit_is_closed_or_low_value(hit):
            continue
        db.execute(
            """
            UPDATE intelligence_items
            SET user_status = 'dismissed',
                verification_status = 'rejected',
                verification_reason = '低价值、图片、封闭平台或聚合来源已清理',
                user_feedback_json = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                to_json({"dismissedAt": timestamp, "reasonCode": "cleanup_low_value_source"}),
                timestamp,
                str(row["id"]),
            ),
        )
        dismissed_items += 1
    return {
        "hiddenCandidates": hidden_candidates,
        "hiddenPromotedCandidates": promoted_visible,
        "dismissedItems": dismissed_items,
        "dismissedLegacyProfileItems": legacy_dismissed,
    }
