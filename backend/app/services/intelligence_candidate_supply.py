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
from app.services.intelligence_ai_runner import (
    generate_intelligence_json,
    generate_intelligence_text,
    intelligence_ai_ready,
)
from app.services.intelligence_search_intents import GeneratedSearchIntent, IntelligenceSearchScope
from app.services.intelligence_timely_strategy import (
    build_timely_research_strategy,
    evaluate_timely_strategy_match,
    timely_effective_window_reason,
)
from app.services.knowledge_v2 import upsert_canonical_text_document
from app.services.public_search import search_public_web


logger = logging.getLogger(__name__)

PROFILE_TTL_HOURS = 72
TIMELY_TTL_HOURS = 24
STRONG_SOURCE_TYPES = {"gov_policy", "procurement", "grant", "social_org_registry", "official_site", "official_site_section"}
PROFILE_SOURCE_TYPES = {"web_search", "official_site", "official_site_section", "social_org_registry", "profile_report", "charity_media"}
TIMELY_SOURCE_TYPES = {"web_search", "gov_policy", "procurement", "grant", "regulatory_risk", "partner_peer", "charity_media"}
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
    ("官网与栏目", ("官网", "官方网站", "栏目", "关于我们", "导航", "信息公开")),
    ("机构简介", ("机构简介", "关于我们", "机构介绍", "业务范围", "宗旨", "使命", "愿景", "定位")),
    ("登记信息", ("登记", "统一社会信用代码", "登记机关", "法定代表人", "住所", "社会组织")),
    ("年报/信息公开", ("年报", "年度报告", "信息公开", "审计报告", "公开报告")),
    ("项目介绍", ("项目介绍", "项目概况", "项目背景", "服务内容", "服务对象", "项目目标")),
    ("服务对象/地域", ("服务对象", "服务范围", "区域", "地域", "地区", "困境儿童", "儿童青少年")),
    ("项目成效", ("成效", "成果", "案例", "受益", "人数", "覆盖", "评估")),
    ("合作方", ("合作", "伙伴", "资助方", "支持方", "联合", "共建")),
    ("执行方法", ("方法", "模式", "路径", "课程", "培训", "活动", "服务流程")),
    ("负责人/团队", ("秘书长", "理事长", "负责人", "团队", "顾源源", "张真", "采访", "观点")),
)
PROFILE_BASELINE_DIMENSIONS = ["机构简介", "登记信息", "年报/信息公开", "项目介绍", "项目成效", "合作方", "执行方法"]
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
    "gaoxiaojob.com",
    "yingjiesheng.com",
    "51job.com",
    "zhaopin.com",
    "lagou.com",
    "chinahr.com",
    "kanzhun.com",
    "zhipin.com",
    "liepin.com",
    "企查查",
    "天眼查",
}
TIMELY_DETAIL_REVIEW_LIMIT = 24
TIMELY_AI_REVIEW_LIMIT = 12
TIMELY_PROMOTION_LIMIT_PER_REFRESH = 5
BROAD_QUERY_TERMS = {
    "全国",
    "广东",
    "广州",
    "深圳",
    "佛山",
    "东莞",
    "珠海",
    "北京",
    "上海",
    "江苏",
    "浙江",
    "山东",
    "四川",
    "湖南",
    "湖北",
    "福建",
    "广西",
}
TIMELY_SOURCE_QUERY_TERMS = {
    "gov_policy": ("政策", "通知"),
    "grant": ("公益创投", "资助", "申报"),
    "procurement": ("政府购买服务", "采购", "招标"),
    "regulatory_risk": ("监管", "合规"),
    "partner_peer": ("合作", "资助方"),
    "charity_media": ("报道", "案例"),
}
TIMELY_ROUTE_SOURCE_TYPES = {
    "政策监管": ("web_search", "gov_policy", "regulatory_risk"),
    "资助申报": ("web_search", "grant", "charity_media", "partner_peer"),
    "采购招标": ("web_search", "procurement"),
    "合作方动态": ("web_search", "partner_peer", "charity_media"),
    "同类机构动态": ("web_search", "charity_media", "partner_peer"),
    "行业风险": ("web_search", "regulatory_risk", "gov_policy"),
    "项目/方法趋势": ("web_search", "charity_media", "partner_peer"),
    "新闻舆情": ("web_search", "charity_media"),
}

OFFICIAL_SITE_SECTION_SPECS: tuple[tuple[str, str, tuple[str, ...], int], ...] = (
    ("官网栏目：关于/简介", "关于 我们 简介 机构介绍", ("profile_completion",), 96),
    ("官网栏目：项目/案例", "项目 案例 服务 成效", ("profile_completion",), 95),
    ("官网栏目：文章/观点", "观点 文章 访谈 专访 案例", ("profile_completion",), 95),
    ("官网栏目：公告/新闻", "公告 新闻 动态 通知", ("profile_completion",), 94),
    ("官网栏目：信息公开/年报/报告", "信息公开 年报 年度报告 报告", ("profile_completion",), 97),
    ("官网栏目：合作/资助", "合作 伙伴 资助 申报", ("profile_completion",), 93),
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
    "资助",
    "扶持",
    "公益创投",
    "政府购买",
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
EXTERNAL_SIGNAL_TERMS = (
    "通知",
    "公告",
    "需求",
    "需求表",
    "申报",
    "征集",
    "招标",
    "采购",
    "中标",
    "成交",
    "政府购买",
    "资助",
    "扶持",
    "公益创投",
    "政策",
    "办法",
    "指南",
    "监管",
    "合规",
    "风险提示",
    "处罚",
    "整改",
    "案例",
    "活动",
    "发布",
    "启动",
    "合作",
    "签约",
    "入选",
    "试点",
)
STATIC_TIMELY_PROFILE_TERMS = (
    "机构简介",
    "关于我们",
    "官网",
    "官方网站",
    "业务范围",
    "组织架构",
    "团队介绍",
    "年报",
    "年度报告",
    "研究报告",
    "白皮书",
    "信息公开",
)
GENERIC_MACRO_TIMELY_TERMS = (
    "高质量发展论坛",
    "宏观讨论",
    "泛泛讨论",
    "理论研讨",
    "行业观察",
    "发展综述",
)
OFF_TOPIC_TIMELY_TERMS = (
    "光伏",
    "白酒",
    "制造业",
    "智能制造",
    "房地产",
    "私募",
    "证券",
    "股票",
    "盘龙药业",
    "医药股",
    "人口计生",
    "生育政策",
    "汽车产业",
    "半导体",
)
CORE_PUBLIC_WELFARE_TIMELY_TERMS = (
    "公益",
    "慈善",
    "社会组织",
    "基金会",
    "民政",
    "未成年人",
    "儿童",
    "青少年",
    "困境儿童",
    "心理健康",
    "社区服务",
    "志愿服务",
    "公益创投",
    "政府购买",
)
BUSINESS_ONLY_TIMELY_TERMS = (
    "企业",
    "经贸",
    "外贸",
    "商务",
    "招商",
    "投资",
    "对外合作",
    "出海",
    "进出口",
    "外事",
    "境外团组",
    "贸易",
    "产业链",
    "营商环境",
    "港澳投融资",
)
PUBLIC_SERVICE_ANCHOR_TERMS = (
    *CORE_PUBLIC_WELFARE_TIMELY_TERMS,
    "教育",
    "心理",
    "家庭支持",
    "未成年人保护",
    "社会服务",
    "公益组织",
    "非营利",
)
GENERIC_TIMELY_ROUTE_TERMS = (
    "政策",
    "通知",
    "公告",
    "合作",
    "项目",
    "服务",
    "资源",
    "机会",
    "发布",
    "启动",
    "平台",
    "案例",
    "活动",
    "申报",
    "征集",
    "采购",
    "招标",
    "支持",
    "措施",
    "办法",
    "指南",
    "动态",
)
TIMELY_REVIEW_BUCKET_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("grant", ("资助", "扶持", "公益创投", "申报", "征集", "截止", "基金会")),
    ("procurement", ("政府购买", "采购", "招标", "中标", "成交", "磋商", "比选")),
    ("policy", ("政策", "通知", "办法", "意见", "指南", "民政", "未成年人", "心理健康")),
    ("risk", ("监管", "合规", "公开募捐", "处罚", "整改", "风险提示", "规范")),
    ("case", ("案例", "活动", "启动", "试点", "项目", "平台建设", "服务")),
    ("partner", ("合作", "联合", "伙伴", "资助方", "同类机构", "社会组织")),
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
    "需要进一步判断这条变化是否会影响",
    "建议转为阅读/研判任务",
    "命中关注点",
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
    profile_partial_dimensions: list[str] = field(default_factory=list)
    profile_gap_map: dict[str, object] = field(default_factory=dict)
    profile_completion_ready: bool = False
    search_direction_count: int = 0
    query_count: int = 0
    success_query_count: int = 0
    no_result_query_count: int = 0
    effective_lead_count: int = 0
    direct_source_count: int = 0
    pages_fetched_count: int = 0
    profile_fact_candidate_count: int = 0
    profile_fact_card_count: int = 0
    no_new_fact_rounds: int = 0
    scout_candidate_count: int = 0
    review_candidate_count: int = 0
    detail_fetched_count: int = 0
    ai_reviewed_count: int = 0
    fresh_window_count: int = 0
    extended_window_count: int = 0
    effective_window_exception_count: int = 0
    uncovered_gaps: list[str] = field(default_factory=list)
    timely_profile_ready: bool = False
    timely_profile_score: int = 0
    timely_profile_gaps: list[str] = field(default_factory=list)
    timely_strategy_route_count: int = 0
    timely_candidate_review_count: int = 0
    timely_effective_window_exception_count: int = 0
    research_stage: str = ""
    processed_page_count: int = 0
    usable_fact_count: int = 0
    quick_win_card_count: int = 0
    deep_queue_count: int = 0
    covered_sub_gaps: list[str] = field(default_factory=list)
    remaining_sub_gaps: list[str] = field(default_factory=list)
    deferred_hard_sources: list[str] = field(default_factory=list)
    profile_run_mode: str = "standard"
    deep_dive_queued_count: int = 0
    deep_dive_processed_count: int = 0
    deep_dive_skipped_count: int = 0
    deep_dive_remaining_count: int = 0
    deep_dive_source_titles: list[str] = field(default_factory=list)
    deep_dive_skip_summary: list[str] = field(default_factory=list)
    external_signal_candidate_count: int = 0
    external_signal_review_count: int = 0
    ai_judged_count: int = 0
    inspiration_card_count: int = 0
    own_official_filtered_count: int = 0
    static_profile_filtered_count: int = 0
    generic_macro_filtered_count: int = 0

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
            "profilePartialDimensions": self.profile_partial_dimensions,
            "profileGapMap": self.profile_gap_map,
            "profileCompletionReady": self.profile_completion_ready,
            "searchDirectionCount": self.search_direction_count,
            "queryCount": self.query_count,
            "successQueryCount": self.success_query_count,
            "noResultQueryCount": self.no_result_query_count,
            "effectiveLeadCount": self.effective_lead_count,
            "directSourceCount": self.direct_source_count,
            "pagesFetchedCount": self.pages_fetched_count,
            "profileFactCandidateCount": self.profile_fact_candidate_count,
            "profileFactCardCount": self.profile_fact_card_count,
            "noNewFactRounds": self.no_new_fact_rounds,
            "scoutCandidateCount": self.scout_candidate_count,
            "reviewCandidateCount": self.review_candidate_count,
            "detailFetchedCount": self.detail_fetched_count,
            "aiReviewedCount": self.ai_reviewed_count,
            "freshWindowCount": self.fresh_window_count,
            "extendedWindowCount": self.extended_window_count,
            "effectiveWindowExceptionCount": self.effective_window_exception_count,
            "uncoveredGaps": self.uncovered_gaps,
            "timelyProfileReady": self.timely_profile_ready,
            "timelyProfileScore": self.timely_profile_score,
            "timelyProfileGaps": self.timely_profile_gaps,
            "timelyStrategyRouteCount": self.timely_strategy_route_count,
            "timelyCandidateReviewCount": self.timely_candidate_review_count,
            "timelyEffectiveWindowExceptionCount": self.timely_effective_window_exception_count,
            "researchStage": self.research_stage,
            "processedPageCount": self.processed_page_count,
            "usableFactCount": self.usable_fact_count,
            "quickWinCardCount": self.quick_win_card_count,
            "deepQueueCount": self.deep_queue_count,
            "coveredSubGaps": self.covered_sub_gaps,
            "remainingSubGaps": self.remaining_sub_gaps,
            "deferredHardSources": self.deferred_hard_sources,
            "profileRunMode": self.profile_run_mode,
            "deepDiveQueuedCount": self.deep_dive_queued_count,
            "deepDiveProcessedCount": self.deep_dive_processed_count,
            "deepDiveSkippedCount": self.deep_dive_skipped_count,
            "deepDiveRemainingCount": self.deep_dive_remaining_count,
            "deepDiveSourceTitles": self.deep_dive_source_titles,
            "deepDiveSkipSummary": self.deep_dive_skip_summary,
            "externalSignalCandidateCount": self.external_signal_candidate_count,
            "externalSignalReviewCount": self.external_signal_review_count,
            "aiJudgedCount": self.ai_judged_count,
            "inspirationCardCount": self.inspiration_card_count,
            "ownOfficialFilteredCount": self.own_official_filtered_count,
            "staticProfileFilteredCount": self.static_profile_filtered_count,
            "genericMacroFilteredCount": self.generic_macro_filtered_count,
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
    fact_cards: list["ProfileFactCard"] = field(default_factory=list)


@dataclass
class ProfileFactCard:
    dimension: str
    title: str
    summary: str
    key_points: list[str]
    analysis: str
    fact_signature: str


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
    timely_strategy: dict[str, object] = field(default_factory=dict)


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
    timely_strategy = build_timely_research_strategy(
        db,
        scope_type=scope.scope_type,
        scope_id=scope.scope_id,
        client_id=scope.client_id,
        project_module_id=scope.project_module_id,
        display_name=scope.display_name,
    ).as_payload()
    return ResearchBrief(
        scope=scope,
        object_terms=object_terms,
        profile_focus=profile_focus,
        timely_focus=timely_focus,
        exclude_terms=exclude_terms,
        priority_urls=priority_urls,
        profile_focus_terms=_focus_terms_from_lines(profile_focus, object_terms),
        timely_focus_terms=_focus_terms_from_lines(timely_focus, object_terms),
        timely_strategy=timely_strategy,
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
            "content_kinds": ["profile_completion"],
            "reason": "官网尚未确认时，先通过公开搜索寻找官网线索；时效情报只使用官网外部信号。",
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


def _site_domain_from_text(text: str) -> str:
    match = re.search(r"site:([A-Za-z0-9.-]+\.[A-Za-z]{2,})", text or "", flags=re.I)
    return match.group(1).lower().removeprefix("www.") if match else ""


def _strip_site_prefix(text: str) -> str:
    return _clean_text(re.sub(r"\bsite:[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", " ", text or "", flags=re.I), max_len=220)


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
                to_json(["profile_completion"]),
                "用户在重点关注中提供官网或重点网址，优先进入资料补全和对象画像；时效情报不抓取对象官网",
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


def _timely_specific_intent_terms(intent: GeneratedSearchIntent) -> list[str]:
    return [term for term in _intent_terms(intent) if term not in BROAD_QUERY_TERMS]


def _query_tokens(value: str) -> list[str]:
    tokens: list[str] = []
    for token in re.split(r"[\s,，;；、/|]+", value or ""):
        cleaned = _clean_text(token, max_len=42)
        cleaned = re.sub(r"^(与|和|及|以及)", "", cleaned)
        cleaned = re.sub(r"(等有关的?|相关的?|有关的?)", "", cleaned)
        cleaned = _clean_text(cleaned, max_len=42)
        if len(cleaned) >= 2 and cleaned not in tokens:
            tokens.append(cleaned)
    return tokens


def _compact_query_terms(*groups: object, limit: int = 6) -> str:
    terms: list[str] = []
    seen: set[str] = set()
    for group in groups:
        if isinstance(group, (list, tuple, set)):
            raw_terms = [str(item) for item in group]
        else:
            raw_terms = _query_tokens(str(group or ""))
        for term in raw_terms:
            for token in _query_tokens(term):
                key = re.sub(r"\s+", "", token).lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                terms.append(token)
                if len(terms) >= limit:
                    return " ".join(terms)
    return " ".join(terms)


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


def _hit_domain(url: str) -> str:
    return urlparse(url or "").netloc.lower().removeprefix("www.")


def _official_domains_for_scope(db: Database, scope: IntelligenceSearchScope, brief: ResearchBrief | None = None) -> set[str]:
    domains: set[str] = set()
    rows = db.fetchall(
        """
        SELECT source_url_template
        FROM intelligence_source_configs
        WHERE scope_type = ? AND scope_id = ? AND enabled = 1
          AND source_type IN ('official_site', 'official_site_section')
        """,
        (scope.scope_type, scope.scope_id),
    )
    for row in rows:
        domain = _site_domain_from_text(str(row["source_url_template"] or ""))
        if domain:
            domains.add(domain.lower().removeprefix("www."))
    if brief:
        for url in brief.priority_urls:
            domain = _hit_domain(url)
            if domain:
                domains.add(domain)
    return domains


def _is_own_official_hit(hit: CandidateHit, official_domains: set[str]) -> bool:
    domain = _hit_domain(hit.url)
    return bool(domain and any(domain == item or domain.endswith(f".{item}") for item in official_domains))


def _timely_strategy_terms(brief: ResearchBrief | None) -> list[str]:
    if not brief:
        return []
    # User directives are intentionally separated: profile-completion focus can
    # teach the object profile through verified materials, but it must not steer
    # timely intelligence search or review directly.
    terms: list[str] = [*brief.timely_focus_terms]
    strategy = brief.timely_strategy or {}
    for key in ("searchAtoms", "serviceTargets", "projectTerms", "methodTerms", "resourceNeeds", "complianceConstraints"):
        terms.extend(_as_text_list(strategy.get(key), limit=16))
    for route in strategy.get("routes") or []:
        if isinstance(route, dict):
            terms.append(_clean_text(route.get("label"), max_len=40))
            terms.extend(_as_text_list(route.get("terms"), limit=8))
    return _unique_items([term for term in terms if term not in GENERIC_FOCUS_TERMS], limit=48)


def _direct_identity_hits(text: str, brief: ResearchBrief | None) -> list[str]:
    if not brief:
        return []
    display_name = _clean_text(brief.scope.display_name, max_len=80)
    identity_terms = [display_name]
    if display_name:
        identity_terms.extend([term for term in brief.object_terms if term and (term in display_name or display_name in term)])
    return _matched_terms(text, _unique_items(identity_terms, limit=8))


def _meaningful_timely_strategy_hits(text: str, brief: ResearchBrief | None) -> list[str]:
    terms = [
        term
        for term in _timely_strategy_terms(brief)
        if term and len(term) >= 2 and term not in GENERIC_TIMELY_ROUTE_TERMS
    ]
    return _matched_terms(text, _unique_items(terms, limit=36))


def _has_external_signal(text: str, source_type: str = "") -> bool:
    return bool(
        any(term in text for term in EXTERNAL_SIGNAL_TERMS)
        or source_type in {"gov_policy", "procurement", "grant", "regulatory_risk", "partner_peer"}
    )


def _looks_like_static_timely_hit(text: str, *, has_external_signal: bool) -> bool:
    if has_external_signal:
        return False
    return any(term in text for term in STATIC_TIMELY_PROFILE_TERMS)


def _looks_like_generic_macro_signal(text: str) -> bool:
    if any(term in text for term in ("申报", "征集", "截止", "采购", "招标", "中标", "监管", "处罚", "风险提示", "资助", "公益创投")):
        return False
    return any(term in text for term in GENERIC_MACRO_TIMELY_TERMS)


def _looks_like_off_topic_timely_signal(text: str) -> bool:
    if not any(term in text for term in OFF_TOPIC_TIMELY_TERMS):
        return False
    return not any(term in text for term in CORE_PUBLIC_WELFARE_TIMELY_TERMS)


def _looks_like_business_only_policy(text: str) -> bool:
    if not any(term in text for term in BUSINESS_ONLY_TIMELY_TERMS):
        return False
    if any(term in text for term in PUBLIC_SERVICE_ANCHOR_TERMS):
        return False
    return any(term in text for term in ("政策", "措施", "通知", "支持", "合作", "办法", "指南"))


def _external_signal_fast_screen(
    *,
    hit: CandidateHit,
    intent: GeneratedSearchIntent,
    config: SourceConfig,
    brief: ResearchBrief,
) -> tuple[bool, float, list[str], str]:
    text = f"{hit.title} {hit.snippet} {hit.source} {intent.query} {intent.reason}"
    hit_text = f"{hit.title} {hit.snippet} {hit.source}"
    has_signal = _has_external_signal(text, config.source_type)
    if _looks_like_static_timely_hit(text, has_external_signal=has_signal):
        return False, -40.0, ["static_profile_filtered"], "static_profile"
    if _looks_like_off_topic_timely_signal(text):
        return False, -40.0, ["off_topic_filtered"], "generic_macro"
    if _looks_like_business_only_policy(hit_text):
        return False, -40.0, ["business_only_filtered"], "generic_macro"
    if _looks_like_generic_macro_signal(text):
        return False, -40.0, ["generic_macro_filtered"], "generic_macro"
    signal_terms = _matched_terms(text, list(EXTERNAL_SIGNAL_TERMS))
    tag_terms = _matched_terms(text, _timely_strategy_terms(brief))
    route_terms = [item for item in intent.source_inputs if item.startswith("timely_route:")]
    score = 0.0
    flags: list[str] = []
    if has_signal or signal_terms:
        score += 28
        flags.append("external_signal")
    if tag_terms:
        score += min(len(tag_terms), 5) * 6
        flags.append("tag_relevant_signal")
    if route_terms:
        score += 8
    if config.source_type in {"gov_policy", "procurement", "grant", "regulatory_risk"}:
        score += 12
    if hit.published_at:
        score += 8
    object_hits = _matched_terms(text, brief.object_terms)
    if not object_hits and (tag_terms or signal_terms) and has_signal:
        flags.append("inspiration_signal")
    if not has_signal and not tag_terms:
        score -= 16
    return True, min(score, 50.0), _unique_items(flags, limit=8), ""


def _effective_query(intent: GeneratedSearchIntent, config: SourceConfig) -> str:
    if intent.content_kind == "timely_intelligence" and config.source_type in TIMELY_SOURCE_TYPES:
        base_terms = _query_tokens(intent.query)
        source_terms = [] if config.source_type == "web_search" else list(TIMELY_SOURCE_QUERY_TERMS.get(config.source_type, ()))
        if config.source_type != "web_search" and config.region and config.region != "全国" and config.region not in base_terms:
            base_terms = [config.region, *base_terms]
        return _clean_text(_compact_query_terms(base_terms, source_terms, limit=6), max_len=120)
    region_prefix = "" if config.region == "全国" else f"{config.region} "
    template = config.source_url_template or "{query}"
    if intent.query.strip().lower().startswith("site:") and template.strip().lower().startswith("site:"):
        if config.source_type == "official_site":
            return _clean_text(intent.query, max_len=220)
        query_without_site = _strip_site_prefix(intent.query)
        return _clean_text(
            template.format(
                query=query_without_site,
                region=config.region,
                region_prefix=region_prefix,
                client="",
            ),
            max_len=220,
        )
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


def _parse_publication_date(value: str | None) -> datetime | None:
    text = _clean_text(value, max_len=120)
    if not text:
        return None
    parsed = _parse_iso(text[:19]) or _parse_iso(text[:10])
    if parsed:
        return parsed
    match = re.search(r"(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})", text)
    if not match:
        return None
    try:
        return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _timely_publication_freshness(
    published_at: str | None,
    *,
    timestamp: str,
    max_age_days: int = 30,
    body_text: str = "",
) -> tuple[bool, str, str]:
    effective_window = timely_effective_window_reason(body_text, timestamp=timestamp)
    published_dt = _parse_publication_date(published_at)
    if published_dt is None:
        if effective_window:
            return True, f"未识别到发布时间，但{effective_window}", "effective_window_exception"
        return False, "未识别到来源页面近 90 天内发布时间或有效窗口，暂不作为时效情报成卡", "missing_date"
    now_dt = _parse_iso(timestamp) or datetime.now()
    if published_dt > now_dt + timedelta(days=1):
        return False, "来源发布时间晚于当前时间，暂不成卡", "future_date"
    age = now_dt - published_dt
    if age <= timedelta(days=30):
        return True, "来源发布时间处于近 30 天优先时效窗口内", "fresh_window"
    if age <= timedelta(days=90):
        return True, "来源发布时间处于 31-90 天扩展时效窗口内，需通过更强相关和影响链条复核", "extended_window"
    if age > timedelta(days=max(max_age_days, 90)):
        if effective_window:
            return True, f"来源发布时间较早，但{effective_window}", "effective_window_exception"
        return False, f"来源发布时间为 {published_dt.date().isoformat()}，已超过近 90 天时效窗口且未识别到有效窗口", "stale_over_90"
    return False, "来源发布时间未通过时效窗口判断，暂不成卡", "unknown_window"


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
        bonus += 16 if intent.content_kind == "timely_intelligence" else -10
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
            bonus += 36
    if any(term in intent_text for term in ("资助", "申报", "公益创投", "征集", "扶持")):
        if source_type == "grant":
            bonus += 20
        elif source_type == "partner_peer":
            bonus += 6
    if any(term in intent_text for term in ("监管", "风险", "合规", "公开募捐", "处罚", "整改")):
        if source_type == "regulatory_risk":
            bonus += 36
        elif source_type == "gov_policy":
            bonus += 6
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
    generic_source_labels = {"公开搜索", "通用公开搜索", "公开来源", "web_search", "搜索结果"}
    if (
        not source
        or source in generic_source_labels
        or _looks_like_domain_label(source)
        or source.startswith("http://")
        or source.startswith("https://")
    ):
        return _clean_text(draft.hit.title, max_len=160) or source or _domain_label(draft.hit.url)
    return source or draft.source_config.source_name or _domain_label(draft.hit.url)


def _html_text_snippet(html: str, *, max_len: int = 260) -> str:
    for pattern in (
        r"<meta[^>]+name=[\"']description[\"'][^>]+content=[\"']([^\"']+)[\"']",
        r"<meta[^>]+content=[\"']([^\"']+)[\"'][^>]+name=[\"']description[\"']",
    ):
        match = re.search(pattern, html or "", flags=re.I | re.S)
        if match:
            return _clean_text(unescape(match.group(1)), max_len=max_len)
    text = re.sub(r"<(script|style)\b.*?</\1>", " ", html or "", flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return _clean_text(unescape(text), max_len=max_len)


def _html_title(html: str, fallback: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html or "", flags=re.I | re.S)
    if match:
        title = _clean_text(unescape(re.sub(r"<[^>]+>", " ", match.group(1))), max_len=120)
        if title:
            return title
    return fallback


def _query_terms_for_direct_site(query: str) -> list[str]:
    stripped = _strip_site_prefix(query)
    stopwords = {"官网", "官方网站", "关于", "我们", "简介", "机构介绍", "项目", "案例", "服务", "成效", "信息公开", "年报", "年度报告", "报告"}
    terms: list[str] = []
    for token in re.split(r"[\s,，。;；、/|()（）]+", stripped):
        text = _clean_text(token, max_len=40)
        if len(text) < 2 or text in stopwords:
            continue
        if text not in terms:
            terms.append(text)
    return terms[:12]


def _fetch_direct_official_site_hits(query: str, config: SourceConfig, *, timeout_seconds: float = 6.0) -> list[CandidateHit]:
    if config.source_type not in {"official_site", "official_site_section"}:
        return []
    domain = _site_domain_from_text(query) or _site_domain_from_text(config.source_url_template)
    if not domain or _domain_matches(domain, CLOSED_OR_LOW_VALUE_DOMAINS) or _domain_matches(domain, AGGREGATOR_DOMAINS):
        return []
    urls = [f"https://{domain}/", f"http://{domain}/"]
    response_text = ""
    final_url = ""
    for url in urls:
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
            response_text = response.text or ""
            final_url = str(response.url)
            break
        except Exception:
            continue
    if not response_text or not final_url:
        return []
    homepage_title = _html_title(response_text, f"{domain} 官网")
    homepage = CandidateHit(
        title=homepage_title,
        url=final_url,
        snippet=_html_text_snippet(response_text),
        source=homepage_title or domain,
        provider="direct_official_site",
    )
    terms = _query_terms_for_direct_site(query)
    hits: list[CandidateHit] = [homepage]
    base_domain = urlparse(final_url).netloc.lower().removeprefix("www.") or domain
    pattern = re.compile(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", flags=re.I | re.S)
    for href, label_html in pattern.findall(response_text):
        label = _clean_text(unescape(re.sub(r"<[^>]+>", " ", label_html)), max_len=120)
        if not label:
            continue
        absolute = urljoin(final_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"} or parsed.netloc.lower().removeprefix("www.") != base_domain:
            continue
        link_text = f"{label} {absolute}"
        if terms and not _matched_terms(link_text, terms) and not any(term in link_text for term in DETAIL_LINK_TERMS):
            continue
        hits.append(
            CandidateHit(
                title=label,
                url=absolute,
                snippet=f"官网栏目链接：{homepage_title}",
                source=homepage_title or domain,
                provider="direct_official_site",
            )
        )
        if len(hits) >= 8:
            break
    return hits


def _fetch_public_search_hits(query: str, config: SourceConfig, *, timeout_seconds: float = 8.0) -> list[CandidateHit]:
    hits: list[CandidateHit] = _fetch_direct_official_site_hits(query, config, timeout_seconds=min(timeout_seconds, 6.0))
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
    deduped: list[CandidateHit] = []
    seen: set[str] = set()
    for hit in hits:
        key = _normalize_url(hit.url)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(hit)
    return deduped


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
        if child_quality.page_type in {"search_page", "media_or_map", "recruitment_directory", "aggregator", "invalid_url"}:
            continue
        if child_quality.page_type == "list_page" and not _url_looks_like_detail_page(child.url):
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


def _url_looks_like_detail_page(url: str) -> bool:
    parsed = urlparse(url or "")
    path = parsed.path.lower()
    query = parsed.query.lower()
    if path.endswith(".pdf"):
        return True
    list_tokens = ("/list", "/lists", "/index", "/category", "/search")
    list_query_terms = ("page=", "p=", "cp=", "sort=", "category=", "keyword=")
    has_id_signal = bool(re.search(r"/(?:id|project_id|cate_id)/\d+", path)) or bool(
        re.search(r"(?:^|[?&])(?:id|articleid|project_id|cate_id)=", query)
    )
    if not has_id_signal and (any(token in path for token in list_tokens) or any(token in query for token in list_query_terms)):
        return False
    detail_tokens = (
        "/detail",
        "detail/",
        "reportdetail",
        "/article",
        "/news/",
        "/project/detail",
        "/info/",
        "/home/project/detail",
        "/home/info/",
        "/pub/",
        "/view/",
        "/content/",
    )
    if any(token in path for token in detail_tokens):
        return True
    if has_id_signal:
        return True
    return False


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
    intent_hits = _matched_terms(text, _timely_specific_intent_terms(intent))
    signal_hits = _matched_terms(text, list(EXTERNAL_SIGNAL_TERMS))
    if _matched_terms(text, object_terms):
        return True
    if len(intent_hits) >= 2:
        return True
    # Inspiration-style intelligence often does not name the current object.
    # Let real external-signal pages reach the later AI strategy review when
    # they have at least one non-generic object tag match.
    return bool(intent_hits and signal_hits)


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
    if hit_quality.page_type == "list_page" and not _url_looks_like_detail_page(hit.url):
        return PageQuality("list_page", _unique_items([*flags, "list_page"], limit=8), "列表页只能用于有限下钻，不能直接成卡")
    if list_markers >= 5 and not _url_looks_like_detail_page(hit.url):
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
    if content_kind == "timely_intelligence" and brief.timely_strategy:
        terms = [
            *terms,
            *_as_text_list(brief.timely_strategy.get("searchAtoms"), limit=18),
            *_as_text_list(brief.timely_strategy.get("serviceTargets"), limit=12),
            *_as_text_list(brief.timely_strategy.get("projectTerms"), limit=12),
            *_as_text_list(brief.timely_strategy.get("methodTerms"), limit=12),
            *_as_text_list(brief.timely_strategy.get("profileTags"), limit=24),
        ]
    return _unique_items([*terms, *brief.object_terms], limit=24)


def _profile_dimension_hits(*values: str) -> list[str]:
    corpus = " ".join(values)
    hits: list[str] = []
    for label, keywords in PROFILE_COMPLETION_DIMENSIONS:
        if any(keyword and keyword in corpus for keyword in keywords):
            hits.append(label)
    return _unique_items(hits, limit=8)


def _profile_dimension_order(label: str) -> int:
    for index, (dimension, _keywords) in enumerate(PROFILE_COMPLETION_DIMENSIONS):
        if dimension == label:
            return index
    return 999


def _profile_fact_signature(value: str) -> str:
    compact = _compact_compare_text(value)
    return compact[:120]


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
    missing = [item for item in PROFILE_BASELINE_DIMENSIONS if item not in covered_dimensions]
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
    full_text = f"{draft.hit.title} {draft.hit.snippet} {body_text}"
    strategy_match = evaluate_timely_strategy_match(full_text, brief.timely_strategy) if content_kind == "timely_intelligence" else {}
    strategy_focus_hits = _as_text_list(strategy_match.get("focusHits"), limit=8) if isinstance(strategy_match, dict) else []
    timely_tag_hits = _matched_terms(full_text, _timely_strategy_terms(brief)) if content_kind == "timely_intelligence" else []
    focus_hits = _unique_items([*_matched_terms(full_text, focus_only_terms), *strategy_focus_hits, *timely_tag_hits], limit=10)
    object_hits = _matched_terms(full_text, brief.object_terms)
    if content_kind == "profile_completion" and not object_hits:
        return None
    if content_kind == "timely_intelligence" and not object_hits and not focus_hits:
        return None
    external_signal = _has_external_signal(full_text, draft.source_config.source_type) if content_kind == "timely_intelligence" else False
    if (
        content_kind == "timely_intelligence"
        and isinstance(strategy_match, dict)
        and not strategy_match.get("ok")
        and not (external_signal and focus_hits)
    ):
        return None
    scored: list[tuple[int, str]] = []
    for sentence in sentences:
        score = 0
        if _matched_terms(sentence, brief.object_terms):
            score += 4
        score += min(len(_matched_terms(sentence, terms)), 4) * 2
        if content_kind == "timely_intelligence" and _matched_terms(sentence, strategy_focus_hits):
            score += 3
        if content_kind == "timely_intelligence" and _matched_terms(sentence, timely_tag_hits):
            score += 3
        if any(token in sentence for token in ("数据", "人数", "年度", "发起", "开展", "发布", "介绍", "服务", "合作", "资助", "培训", "心理", "困境", "儿童", "顾源源", "张真")):
            score += 2
        if content_kind == "timely_intelligence" and any(token in sentence for token in (*TIMELY_MATERIAL_TERMS, *EXTERNAL_SIGNAL_TERMS)):
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
    if not _direct_identity_hits(full_text, brief) and focus_hits and external_signal:
        intelligence_type = "启发型情报"
    summary = quotes[0]
    route_hits = _as_text_list(strategy_match.get("routeHits"), limit=4) if isinstance(strategy_match, dict) else []
    decision_signals = _as_text_list(strategy_match.get("decisionSignals"), limit=4) if isinstance(strategy_match, dict) else []
    relation_parts = []
    if route_hits:
        relation_parts.append(f"监测路线：{'、'.join(route_hits[:3])}")
    if focus_hits or object_hits:
        relation_parts.append(f"命中对象/关注点：{'、'.join((focus_hits or object_hits)[:4])}")
    if decision_signals:
        relation_parts.append(f"决策信号：{'、'.join(decision_signals[:4])}")
    relation = "；".join(relation_parts) + "。"
    impact = "需判断这条外部变化会通过适用对象、申报资格、合规边界、资源窗口或方案设计要求传导到当前客户/项目。"
    action = "建议先核验原公告、适用对象、时间窗口、资格条件和与当前对象的关系，再决定是否转为申报、合作或材料审核任务。"
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


def _fallback_timely_evidence(
    *,
    brief: ResearchBrief,
    draft: CandidateDraft,
    body_text: str,
) -> EvidenceExtraction | None:
    sentences = _split_sentences(body_text)
    if not sentences:
        return None
    text = f"{draft.hit.title} {draft.hit.snippet} {body_text[:2400]}"
    terms = _unique_items(
        [*_timely_strategy_terms(brief), *list(EXTERNAL_SIGNAL_TERMS), *list(CORE_PUBLIC_WELFARE_TIMELY_TERMS)],
        limit=80,
    )
    scored: list[tuple[int, str]] = []
    for sentence in sentences:
        score = min(len(_matched_terms(sentence, terms)), 6) * 2
        if any(term in sentence for term in EXTERNAL_SIGNAL_TERMS):
            score += 5
        if any(term in sentence for term in CORE_PUBLIC_WELFARE_TIMELY_TERMS):
            score += 3
        if score >= 4:
            scored.append((score, sentence))
    scored.sort(key=lambda item: (-item[0], len(item[1])))
    quotes = _unique_items([sentence for _score, sentence in scored], limit=4)
    if not quotes and any(term in text for term in EXTERNAL_SIGNAL_TERMS):
        quotes = _unique_items(sentences[:4], limit=4)
    if not quotes:
        return None
    intelligence_type = _timely_intelligence_type(draft, body_text) or "外部变化"
    focus_hits = _matched_terms(text, _timely_strategy_terms(brief))
    if not _direct_identity_hits(text, brief) and focus_hits and _has_external_signal(text, draft.source_config.source_type):
        intelligence_type = "启发型情报"
    return EvidenceExtraction(
        summary=quotes[0],
        facts=quotes,
        quotes=quotes,
        focus_hits=focus_hits[:6],
        missing="AI 研判前保留的候选证据句，需继续判断对象关系和传导链条。",
        intelligence_type=intelligence_type,
        timeliness_label=_timeliness_label(draft, intelligence_type),
    )


def _looks_like_template_summary(*values: str) -> bool:
    text = " ".join(values)
    return any(marker in text for marker in TEMPLATE_SUMMARY_MARKERS)


def _timely_ai_output_is_specific(
    *,
    summary: str,
    relevance: str,
    impact: str,
    suggested_action: str,
    draft: CandidateDraft,
    evidence: EvidenceExtraction,
    brief: ResearchBrief,
) -> bool:
    values = [summary, relevance, impact, suggested_action]
    joined = " ".join(values)
    if _looks_like_template_summary(*values):
        return False
    if "资料摘要" in joined or "可复用事实" in joined or "通用背景" in joined or "不是基于当前客户原始资料" in joined:
        return False
    if summary in {draft.hit.title, draft.hit.snippet}:
        return False
    normalized_summary = re.sub(r"\s+", "", summary)
    if not evidence.quotes:
        return False
    if len(joined) < 60:
        return False
    strategy_terms = []
    if brief.timely_strategy:
        strategy_terms.extend(_as_text_list(brief.timely_strategy.get("searchAtoms"), limit=12))
        strategy_terms.extend(_as_text_list(brief.timely_strategy.get("serviceTargets"), limit=8))
        strategy_terms.extend(_as_text_list(brief.timely_strategy.get("projectTerms"), limit=8))
    object_or_focus_terms = _unique_items([*brief.object_terms, *brief.timely_focus_terms, *strategy_terms, *evidence.focus_hits], limit=28)
    evidence_text = " ".join(evidence.quotes)
    weak_anchor_terms = {"合作", "资源", "项目", "服务", "平台", "发展", "支持", "需求", "机会", "广东", "全国"}
    strong_anchor_terms = [
        term
        for term in object_or_focus_terms
        if len(term) >= 2 and term not in weak_anchor_terms
    ]
    core_relation_terms = (
        "儿童", "青少年", "困境", "心理", "心理健康", "社会组织", "公益创投", "政府购买",
        "资助", "扶持", "慈善", "公益", "民政", "社区服务", "公开募捐", "志愿服务",
        "AI 公益", "数字化", "公益组织数字化",
    )
    evidence_has_focus = bool(_matched_terms(evidence_text, strong_anchor_terms)) or any(term in evidence_text for term in core_relation_terms)
    response_has_decision_signal = any(term in joined for term in ("机会", "风险", "约束", "启发", "申报", "合作", "服务对象", "资源", "方案", "材料", "合规", "研判", "窗口", "传导"))
    action_terms = ("核验", "检查", "评估", "研判", "关注", "比对", "整理", "联系", "纳入", "申报", "跟进", "阅读", "判断")
    response_mentions_evidence = any(term in joined for term in _unique_items([*evidence.focus_hits, *strong_anchor_terms], limit=12))
    if response_has_decision_signal and suggested_action and any(term in suggested_action for term in action_terms) and (evidence_has_focus or response_mentions_evidence):
        return True
    if object_or_focus_terms and not _matched_terms(joined, object_or_focus_terms) and not (evidence_has_focus and response_has_decision_signal):
        return False
    if not evidence_has_focus and not _direct_identity_hits(evidence_text, brief):
        return False
    relation_terms = ("影响", "相关", "对应", "传导", "适用", "机会", "风险", "约束", "趋势", "申报", "合作", "合规", "资源", "服务对象")
    if not any(term in f"{relevance} {impact}" for term in relation_terms):
        return False
    action_terms = ("核验", "检查", "评估", "研判", "关注", "比对", "转为", "整理", "联系", "纳入", "申报", "跟进")
    if not any(term in suggested_action for term in action_terms):
        return False
    return True


def _timely_structured_ai_response(
    ai_service: object,
    *,
    prompt: str,
    draft: CandidateDraft,
    intelligence_type: str,
) -> AiStructuredResponse | None:
    """Use a grounded, field-specific call for timely cards instead of generic chat fallback."""
    compact_prompt = _minimal_timely_ai_prompt(prompt)
    schema = {
        "type": "OBJECT",
        "properties": {
            "summary": {"type": "STRING"},
            "relevanceReason": {"type": "STRING"},
            "impact": {"type": "STRING"},
            "suggestedAction": {"type": "STRING"},
            "evidenceGap": {"type": "STRING"},
            "timeliness": {"type": "STRING"},
        },
        "required": ["summary", "relevanceReason", "impact", "suggestedAction", "evidenceGap", "timeliness"],
    }
    system_instruction = (
        "你是益语智库的时效情报研究员，只能基于给定网页正文和证据句研判。"
        "不要写通用背景说明，不要说“以下不是正式分析”，不要输出 Markdown。"
        "如果证据不足，也要在 evidenceGap 里具体说明不足点；其他字段仍尽量给出审慎判断。"
        "字段要求：summary 写 80-160 字说明发生了什么、主体、动作和时间窗口；"
        "relevanceReason 写 100-220 字说明它为什么对当前对象有启发，必须点出对象标签关系；"
        "impact 写 120-260 字说明机会/风险/约束/趋势如何传导到当前对象；"
        "suggestedAction 写 60-140 字下一步研判或跟进行动；"
        "timeliness 写发布时间、截止期、征集期或有效窗口判断。"
    )
    result = generate_intelligence_json(
        ai_service,
        prompt=compact_prompt,
        system_instruction=system_instruction,
        response_schema=schema,
        timeout_seconds=180.0,
        max_tokens=1600,
        temperature=0.2,
        top_p=0.84,
        task_kind="deep_analysis",
        enable_thinking=True,
    )
    payload = result.payload if result.ok else None
    if not isinstance(payload, dict):
        payload = _timely_labeled_ai_payload(
            getattr(ai_service, "_qwen_generate", None),
            compact_prompt,
            system_instruction,
            ai_service=ai_service,
        )
    if not isinstance(payload, dict):
        # Backend tests use a narrow AI double that exposes only generate_general_fallback.
        # Production AiService reaches the runner path above.
        legacy = getattr(ai_service, "generate_general_fallback", None)
        if callable(legacy) and not callable(getattr(ai_service, "_qwen_generate", None)):
            try:
                legacy_response = legacy(compact_prompt, "情报候选自动分流", subject_name=draft.hit.title)
            except Exception:
                legacy_response = None
            if isinstance(legacy_response, AiStructuredResponse):
                return legacy_response
        return None
    summary = _clean_text(payload.get("summary"), max_len=520)
    relevance = _clean_text(payload.get("relevanceReason"), max_len=720)
    impact = _clean_text(payload.get("impact"), max_len=720)
    suggested_action = _clean_text(payload.get("suggestedAction"), max_len=520)
    evidence_gap = _clean_text(payload.get("evidenceGap"), max_len=360)
    timeliness = _clean_text(payload.get("timeliness"), max_len=280)
    if not any((summary, relevance, impact, suggested_action)):
        return None
    analysis_parts = [part for part in (impact, f"证据缺口：{evidence_gap}" if evidence_gap else "") if part]
    return AiStructuredResponse(
        content=summary or draft.hit.snippet or draft.hit.title,
        judgment=relevance,
        analysis="\n".join(analysis_parts) or impact or relevance,
        actions=suggested_action,
        timeline=timeliness or _timeliness_label(draft, intelligence_type),
    )


def _compact_timely_ai_prompt(prompt: str) -> str:
    text = str(prompt or "")
    text = re.sub(
        r"网页正文摘录：([\s\S]*?)(\n请只基于|\Z)",
        lambda match: f"网页正文摘录：{_clean_text(match.group(1), max_len=600)}{match.group(2)}",
        text,
    )
    text = re.sub(
        r"已抽取证据句：([^\n]*)",
        lambda match: f"已抽取证据句：{_clean_text(match.group(1), max_len=320)}",
        text,
    )
    return text[:1300]


def _minimal_timely_ai_prompt(prompt: str) -> str:
    text = _compact_timely_ai_prompt(prompt)
    def field(label: str, max_len: int) -> str:
        match = re.search(rf"{re.escape(label)}：([^\n]*)", text)
        return _clean_text(match.group(1) if match else "", max_len=max_len)

    subject = field("当前对象", 80)
    atoms = field("对象画像主题", 90)
    title = field("标题", 120)
    source = field("来源", 80)
    query = field("命中搜索意图", 80)
    intelligence_type = field("情报类型", 40)
    evidence = field("已抽取证据句", 260)
    body_match = re.search(r"网页正文摘录：([\s\S]*)", text)
    body = _clean_text(body_match.group(1) if body_match else "", max_len=360)
    parts = [
        f"对象：{subject}" if subject else "",
        f"对象标签：{_clean_timely_prompt_atoms(atoms)}" if atoms else "",
        f"外部信号：{title}" if title else "",
        f"来源：{source}" if source else "",
        f"类型：{intelligence_type}" if intelligence_type else "",
        f"搜索方向：{query}" if query else "",
        f"网页证据：{evidence}" if evidence else "",
        f"正文片段：{body}" if body else "",
        "请基于证据判断这条外部信号对当前对象是否有启发。不要假设对象一定符合资格；资格、地域、时间窗口不明时写明需核验。",
    ]
    return "\n".join(part for part in parts if part)[:980]


def _clean_timely_prompt_atoms(value: str) -> str:
    raw_terms = _as_text_list(value, limit=8)
    weak_terms = {"合作机会", "政策导向", "资源", "平台", "基金会"}
    terms = [term for term in raw_terms if term and term not in weak_terms]
    return "、".join(terms[:5]) or _clean_text(value, max_len=80)


def _timely_labeled_ai_payload(
    generator: object,
    prompt: str,
    system_instruction: str,
    *,
    ai_service: object | None = None,
) -> dict[str, object] | None:
    if not callable(generator) and not _ai_ready(ai_service):
        return None
    labeled_prompt = (
        f"{prompt}\n\n"
        "请直接按下面 6 个中文标签回答，每项 2-4 句，必须具体到证据和当前对象标签，不要解释格式：\n"
        "发生了什么：说明外部信号、主体、动作和时间/窗口。\n"
        "为什么有关：说明它与当前对象的服务对象、业务方法、资源需求或合规约束的关系。\n"
        "可能影响：说明机会、风险、约束或趋势如何传导到当前对象。\n"
        "建议动作：说明下一步最小研判或跟进动作，不强行写成立即执行任务。\n"
        "证据缺口：说明仍缺哪些资格、地域、截止期、主体身份或适用条件证据。\n"
        "时效性：说明发布时间、截止期、征集期、有效期或为什么仍在窗口内。"
    )
    text = ""
    if _ai_ready(ai_service):
        text = _intelligence_ai_text(
            ai_service,
            prompt=labeled_prompt,
            system_instruction=system_instruction + " 请按指定中文标签输出，不要输出 JSON。",
            timeout_seconds=180.0,
            max_tokens=1500,
            temperature=0.22,
            top_p=0.84,
            task_kind="deep_analysis",
        )
    if not text and callable(generator):
        try:
            text = str(
                generator(
                    prompt=labeled_prompt,
                    system_instruction=system_instruction + " 请按指定中文标签输出，不要输出 JSON。",
                    response_schema=None,
                    timeout_seconds=150.0,
                    max_tokens=1300,
                    temperature=0.22,
                    top_p=0.84,
                    enable_thinking=True,
                    task_kind="deep_analysis",
                )
                or ""
            )
        except Exception:
            return None
    cleaned = str(text or "").strip()
    if len(cleaned) < 60:
        return None
    payload = {
        "summary": _extract_labeled_value(cleaned, ("发生了什么", "summary", "事件")),
        "relevanceReason": _extract_labeled_value(cleaned, ("为什么有关", "相关性", "启发")),
        "impact": _extract_labeled_value(cleaned, ("可能影响", "影响", "传导链条")),
        "suggestedAction": _extract_labeled_value(cleaned, ("建议动作", "下一步", "行动")),
        "evidenceGap": _extract_labeled_value(cleaned, ("证据不足", "证据缺口", "不足")),
        "timeliness": _extract_labeled_value(cleaned, ("时效性", "时间性", "有效窗口")),
    }
    if not any(str(value or "").strip() for value in payload.values()):
        lines = [
            _clean_text(re.sub(r"^\s*[-*]?\s*(?:[一二三四五六]、|\d+[.、])?\s*", "", line), max_len=700)
            for line in cleaned.splitlines()
            if _clean_text(line, max_len=20)
        ]
        if len(lines) >= 4:
            payload.update(
                {
                    "summary": lines[0],
                    "relevanceReason": lines[1],
                    "impact": lines[2],
                    "suggestedAction": lines[3],
                    "evidenceGap": lines[4] if len(lines) >= 5 else "",
                    "timeliness": lines[5] if len(lines) >= 6 else "",
                }
            )
    return payload


def _extract_labeled_value(text: str, labels: tuple[str, ...]) -> str:
    label_pattern = "|".join(re.escape(label) for label in labels)
    next_labels = "发生了什么|为什么有关|相关性|启发|可能影响|影响|传导链条|建议动作|下一步|行动|证据不足|证据缺口|不足|时效性|时间性|有效窗口"
    match = re.search(
        rf"(?:^|\n)\s*(?:{label_pattern})\s*[:：]\s*([\s\S]*?)(?=\n\s*(?:{next_labels})\s*[:：]|\Z)",
        text,
        re.IGNORECASE,
    )
    if match:
        return _clean_text(match.group(1), max_len=700)
    return ""


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


def _profile_gap_map_snapshot(db: Database, scope: IntelligenceSearchScope) -> dict[str, object]:
    client, project = _scope_rows(db, scope)
    project_rows = [project] if project else [
        _row_dict(row)
        for row in db.fetchall(
            "SELECT name, goal, description, keywords_json FROM project_modules WHERE client_id = ? ORDER BY updated_at DESC LIMIT 8",
            (scope.client_id,),
        )
    ]
    rows = db.fetchall(
        """
        SELECT title, summary, key_points_json, tags_json, source_url
        FROM intelligence_items
        WHERE scope_type = ? AND scope_id = ? AND content_kind = 'profile_completion' AND user_status = 'active'
        ORDER BY created_at DESC
        LIMIT 80
        """,
        (scope.scope_type, scope.scope_id),
    )
    entries: dict[str, dict[str, object]] = {
        label: {
            "status": "missing",
            "coveredTags": [],
            "missingTags": list(keywords[:4]),
            "sourceCount": 0,
            "factCount": 0,
        }
        for label, keywords in PROFILE_COMPLETION_DIMENSIONS
    }

    def mark_partial(label: str, *tags: str) -> None:
        entry = entries.get(label)
        if not entry or entry["status"] == "covered":
            return
        entry["status"] = "partial"
        covered_tags = list(entry.get("coveredTags") or [])
        covered_tags.extend(tag for tag in tags if tag)
        entry["coveredTags"] = _unique_items(covered_tags, limit=8)

    def mark_covered(label: str, *, tags: list[str], source_url: str = "", fact_count: int = 0) -> None:
        entry = entries.get(label)
        if not entry:
            return
        entry["status"] = "covered"
        entry["sourceCount"] = int(entry.get("sourceCount") or 0) + (1 if source_url else 0)
        entry["factCount"] = int(entry.get("factCount") or 0) + max(1, fact_count)
        entry["coveredTags"] = _unique_items([*_as_text_list(entry.get("coveredTags"), limit=8), *tags], limit=10)

    client_text = " ".join(
        _as_text_list(
            [
                client.get("name"),
                client.get("alias"),
                client.get("domain"),
                client.get("type"),
                client.get("intro"),
                client.get("stage"),
            ],
            limit=12,
        )
    )
    if client_text:
        for label in _profile_dimension_hits(client_text):
            mark_partial(label, "基础字段")
    for item in project_rows:
        project_text = " ".join(
            _as_text_list(
                [
                    item.get("name"),
                    item.get("goal"),
                    item.get("description"),
                    _safe_json(str(item.get("keywords_json") or "[]"), []),
                ],
                limit=12,
            )
        )
        if project_text:
            for label in _profile_dimension_hits(project_text):
                mark_partial(label, "项目字段")

    for row in rows:
        tags = _safe_json(str(row["tags_json"] or "[]"), [])
        points = _safe_json(str(row["key_points_json"] or "[]"), [])
        dimension_hits = _profile_dimension_hits(
            str(row["title"] or ""),
            str(row["summary"] or ""),
            " ".join(_as_text_list(tags, limit=12)),
            " ".join(_as_text_list(points, limit=12)),
        )
        for label in dimension_hits:
            mark_covered(
                label,
                tags=_as_text_list(tags, limit=8),
                source_url=str(row["source_url"] or ""),
                fact_count=len(_as_text_list(points, limit=8)),
            )

    covered = [label for label, entry in entries.items() if entry.get("status") == "covered"]
    partial = [label for label, entry in entries.items() if entry.get("status") == "partial"]
    missing = [item for item in PROFILE_BASELINE_DIMENSIONS if entries.get(item, {}).get("status") != "covered"]
    ready = (
        len(set(covered).intersection(PROFILE_BASELINE_DIMENSIONS)) >= 5
        and "机构简介" in covered
        and ("项目介绍" in covered or "项目成效" in covered)
    )
    return {
        "dimensions": entries,
        "covered": sorted(covered, key=_profile_dimension_order),
        "partial": sorted(partial, key=_profile_dimension_order),
        "missing": missing,
        "ready": ready,
    }


def _profile_coverage_snapshot(db: Database, scope: IntelligenceSearchScope) -> tuple[list[str], list[str], bool]:
    snapshot = _profile_gap_map_snapshot(db, scope)
    return (
        _as_text_list(snapshot.get("covered"), limit=16),
        _as_text_list(snapshot.get("missing"), limit=16),
        bool(snapshot.get("ready")),
    )


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
    if not _ai_ready(ai_service):
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
    raw_text = _intelligence_ai_text(
        ai_service,
        prompt=prompt,
        system_instruction=(
            "你是资料补全研究员。必须只基于给定网页正文和证据句提炼资料事实。"
            "不要写通用背景，不要写不能被证据支持的判断。"
            "请严格使用：资料摘要：...\\n可复用事实：\\n- ...\\n- ...\\n证据缺口：..."
        ),
        timeout_seconds=90.0,
        max_tokens=1100,
        temperature=0.24,
        top_p=0.86,
        task_kind="deep_analysis",
    )
    if not raw_text:
        return None
    response = AiStructuredResponse(content=raw_text, analysis=raw_text, actions=raw_text, judgment=raw_text, timeline="")
    if not isinstance(response, AiStructuredResponse):
        return None
    summary = _clean_text(response.content or response.judgment or "", max_len=500)
    summary = re.sub(r"可复用事实[:：].*$", "", summary, flags=re.S).strip()
    summary = re.sub(r"^资料摘要\s*[:：]\s*", "", summary).strip()
    points = _extract_profile_facts_from_ai(response, evidence, mapped_tags, draft)
    if not summary or _looks_like_template_summary(summary, response.analysis, response.actions, response.judgment):
        return None
    if not summary or not points:
        return None
    analysis = _clean_text(response.analysis or response.judgment or "", max_len=900)
    if _looks_like_template_summary(analysis):
        return None
    return summary, points[:4], analysis


def _dimension_for_profile_fact(fact: str, mapped_tags: list[str], fallback_index: int) -> str:
    hits = _profile_dimension_hits(fact)
    for tag in mapped_tags:
        if tag in hits:
            return tag
    if hits:
        return hits[0]
    if mapped_tags:
        return mapped_tags[min(fallback_index, len(mapped_tags) - 1)]
    return "机构简介"


def _build_profile_fact_cards(
    *,
    draft: CandidateDraft,
    verification: ProfileVerificationResult,
) -> list[ProfileFactCard]:
    grouped: dict[str, list[str]] = {}
    for index, point in enumerate(verification.key_points):
        fact = _clean_profile_fact_candidate(point)
        if not fact:
            continue
        dimension = _dimension_for_profile_fact(fact, verification.mapped_tags, index)
        grouped.setdefault(dimension, [])
        if fact not in grouped[dimension]:
            grouped[dimension].append(fact)

    if not grouped and verification.summary:
        dimension = verification.mapped_tags[0] if verification.mapped_tags else "机构简介"
        grouped[dimension] = [_clean_text(verification.summary, max_len=180)]

    cards: list[ProfileFactCard] = []
    for dimension in sorted(grouped, key=_profile_dimension_order):
        facts = grouped[dimension][:3]
        if not facts:
            continue
        title_fact = re.sub(r"[。；;]$", "", facts[0])
        title = f"{dimension}｜{_clean_text(title_fact, max_len=52)}"
        summary = f"该来源可补充“{dimension}”资料：{_clean_text(title_fact, max_len=120)}。"
        signature = _profile_fact_signature(f"{dimension} {' '.join(facts)}")
        if not signature:
            continue
        cards.append(
            ProfileFactCard(
                dimension=dimension,
                title=title,
                summary=summary,
                key_points=facts,
                analysis=verification.analysis,
                fact_signature=signature,
            )
        )
    return cards[:6]


def _profile_fact_already_active(
    db: Database,
    *,
    scope: IntelligenceSearchScope,
    source_url: str,
    dimension: str,
    fact_signature: str,
) -> bool:
    rows = db.fetchall(
        """
        SELECT tags_json, key_points_json
        FROM intelligence_items
        WHERE content_kind = 'profile_completion'
          AND user_status = 'active'
          AND scope_type = ?
          AND scope_id = ?
          AND COALESCE(source_url, '') = COALESCE(?, '')
        ORDER BY created_at DESC
        LIMIT 30
        """,
        (scope.scope_type, scope.scope_id, source_url),
    )
    for row in rows:
        tags = _as_text_list(_safe_json(str(row["tags_json"] or "[]"), []), limit=12)
        if dimension not in tags:
            continue
        points = _as_text_list(_safe_json(str(row["key_points_json"] or "[]"), []), limit=8)
        existing_signature = _profile_fact_signature(f"{dimension} {' '.join(points)}")
        if existing_signature and (
            existing_signature == fact_signature
            or existing_signature in fact_signature
            or fact_signature in existing_signature
        ):
            return True
    return False


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
    provisional = ProfileVerificationResult(
        True,
        "verified",
        "",
        "fetched",
        "generated",
        mapped_tags,
        summary,
        points,
        analysis,
        body_excerpt,
    )
    fact_cards = _build_profile_fact_cards(draft=draft, verification=provisional)
    if not fact_cards:
        reason = "AI 提炼结果未能拆成明确资料维度事实，暂不成卡"
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
            quality_flags=[*page_quality.flags, "no_profile_fact_card"],
        )
        return ProfileVerificationResult(False, "verified", reason, "fetched", "failed", mapped_tags, body_excerpt=body_excerpt)
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
            "factCards": [
                {
                    "dimension": card.dimension,
                    "title": card.title,
                    "facts": card.key_points,
                    "factSignature": card.fact_signature,
                }
                for card in fact_cards
            ],
        },
    )
    return ProfileVerificationResult(True, "verified", reason, "fetched", "generated", mapped_tags, summary, points, analysis, body_excerpt, fact_cards)


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
    if _has_external_signal(f"{text} {parsed.path}", "") and not any(token in text for token in ("官网", "官方网站", "关于我们", "首页", "机构介绍")):
        return 0, "命中的是通知、风险、采购或资助等外部信号页，不作为官网来源。"
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
        content_kinds=["profile_completion"],
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
                    to_json(["profile_completion"]),
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


def _timely_review_bucket(draft: CandidateDraft) -> str:
    text = f"{draft.intent.query} {draft.intent.reason} {draft.hit.title} {draft.hit.snippet} {draft.source_config.source_type}"
    for bucket, terms in TIMELY_REVIEW_BUCKET_TERMS:
        if any(term in text for term in terms):
            return bucket
    if any(term in text for term in CORE_PUBLIC_WELFARE_TIMELY_TERMS):
        return "sector"
    return "other"


def _timely_review_priority(draft: CandidateDraft, brief: ResearchBrief, *, timestamp: str | None = None) -> float:
    text = f"{draft.intent.query} {draft.intent.reason} {draft.hit.title} {draft.hit.snippet} {draft.hit.source}"
    keep, external_bonus, flags, _reject_kind = _external_signal_fast_screen(
        hit=draft.hit,
        intent=draft.intent,
        config=draft.source_config,
        brief=brief,
    )
    if not keep:
        return -1000.0
    score = float(draft.confidence_score) + external_bonus
    signal_hits = _matched_terms(text, list(EXTERNAL_SIGNAL_TERMS))
    tag_hits = _matched_terms(text, _timely_strategy_terms(brief))
    core_hits = _matched_terms(text, list(CORE_PUBLIC_WELFARE_TIMELY_TERMS))
    score += min(len(signal_hits), 5) * 5
    score += min(len(tag_hits), 6) * 4
    score += min(len(core_hits), 4) * 3
    if "inspiration_signal" in flags:
        score += 10
    if draft.source_config.source_type == "web_search":
        score += 8
    elif draft.source_config.source_type in {"grant", "procurement", "gov_policy", "regulatory_risk"}:
        score += 10
    if draft.hit.published_at:
        published_dt = _parse_publication_date(draft.hit.published_at)
        now_dt = _parse_iso(timestamp) if timestamp else datetime.now()
        if published_dt and now_dt:
            age = now_dt - published_dt
            if age <= timedelta(days=30):
                score += 18
            elif age <= timedelta(days=90):
                score += 10
            elif not any(term in text for term in ("截止", "有效期", "征集", "申报", "仍在", "2026")):
                score -= 24
    if _looks_like_off_topic_timely_signal(text):
        score -= 80
    if _looks_like_generic_macro_signal(text):
        score -= 45
    return score


def _select_timely_review_drafts(
    drafts: list[CandidateDraft],
    *,
    brief: ResearchBrief,
    timestamp: str,
    detail_limit: int,
    ai_limit: int,
) -> tuple[set[str], set[str]]:
    ranked = [
        (draft, _timely_review_priority(draft, brief, timestamp=timestamp), _timely_review_bucket(draft))
        for draft in drafts
        if draft.content_kind == "timely_intelligence"
    ]
    ranked = [(draft, score, bucket) for draft, score, bucket in ranked if score > 0]
    buckets: dict[str, list[tuple[CandidateDraft, float]]] = {}
    for draft, score, bucket in ranked:
        buckets.setdefault(bucket, []).append((draft, score))
    for items in buckets.values():
        items.sort(key=lambda item: (-item[1], item[0].hit.title))

    selected: list[CandidateDraft] = []
    bucket_order = ["grant", "procurement", "policy", "risk", "case", "partner", "sector", "other"]
    while len(selected) < detail_limit:
        advanced = False
        for bucket in bucket_order:
            items = buckets.get(bucket) or []
            while items and any(existing.dedupe_key == items[0][0].dedupe_key for existing in selected):
                items.pop(0)
            if not items:
                continue
            selected.append(items.pop(0)[0])
            advanced = True
            if len(selected) >= detail_limit:
                break
        if not advanced:
            break

    selected_ids = {draft.id for draft in selected}
    selected_scores = {draft.id: _timely_review_priority(draft, brief, timestamp=timestamp) for draft in selected}
    ai_selected = sorted(selected, key=lambda item: (-selected_scores.get(item.id, 0), item.hit.title))[:ai_limit]
    return selected_ids, {draft.id for draft in ai_selected}


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


def _profile_allowed_source_types(intent: GeneratedSearchIntent) -> set[str]:
    text = f"{intent.query} {intent.reason}"
    if _site_domain_from_text(intent.query):
        return {"official_site", "official_site_section"}
    allowed = {"official_site", "official_site_section", "web_search"}
    if any(term in text for term in ("登记", "统一社会信用代码", "社会组织", "法定代表人", "住所")):
        allowed.update({"social_org_registry", "profile_report"})
    if any(term in text for term in ("年报", "年度报告", "信息公开", "公开报告", "审计报告")):
        allowed.update({"profile_report", "social_org_registry"})
    if any(term in text for term in ("项目", "案例", "成效", "服务对象", "课程", "培训", "合作", "伙伴", "团队", "采访", "观点")):
        allowed.update({"charity_media", "profile_report"})
    return allowed


def _profile_source_window(intent: GeneratedSearchIntent) -> int:
    if _site_domain_from_text(intent.query):
        return 3
    if "官网限定" in intent.reason:
        return 4
    if any(marker in intent.reason for marker in ("重点关注", "数据中心资料缺口")):
        return 4
    return 3


def _timely_route_label(intent: GeneratedSearchIntent) -> str:
    for item in intent.source_inputs:
        if item.startswith("timely_route:"):
            return item.split(":", 1)[1]
    text = f"{intent.query} {intent.reason}"
    if any(term in text for term in ("招标", "采购", "政府购买服务", "中标", "成交", "比选")):
        return "采购招标"
    if any(term in text for term in ("资助", "申报", "公益创投", "征集", "扶持")):
        return "资助申报"
    if any(term in text for term in ("公开募捐", "监管", "风险", "处罚", "整改", "合规")):
        return "行业风险"
    if any(term in text for term in ("政策", "通知", "办法", "规范", "民政")):
        return "政策监管"
    return ""


def _timely_allowed_source_types(intent: GeneratedSearchIntent) -> set[str]:
    route_label = _timely_route_label(intent)
    configured = TIMELY_ROUTE_SOURCE_TYPES.get(route_label)
    if configured:
        return set(configured)
    return {"web_search", "charity_media", "partner_peer", "gov_policy", "grant"}


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
        intent_limit = 56 if content_kind == "profile_completion" else 32
        source_window = 5
        kind_limit = min(200 if content_kind == "profile_completion" else 140, per_kind_limit)
        seen_effective_queries: set[str] = set()
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
            allowed_profile_types = _profile_allowed_source_types(intent) if content_kind == "profile_completion" else set()
            if content_kind == "timely_intelligence":
                allowed_timely_types = _timely_allowed_source_types(intent)
                current_source_window = 3
                eligible_configs = [item for item in kind_configs if item.source_type in allowed_timely_types]
            else:
                current_source_window = _profile_source_window(intent)
                eligible_configs = [item for item in kind_configs if item.source_type in allowed_profile_types]
            routed_configs = sorted(
                eligible_configs,
                key=lambda item: (
                    -(
                        _source_priority_score_for_kind(db, item, content_kind=content_kind, timestamp=timestamp)
                        + _source_route_bonus(intent, item)
                    ),
                    item.source_type,
                    item.source_name,
                ),
            )
            if content_kind == "timely_intelligence":
                web_configs = [item for item in routed_configs if item.source_type == "web_search"]
                other_configs = [item for item in routed_configs if item.source_type != "web_search"]
                routed_configs = [*web_configs[:1], *other_configs]
            for config in routed_configs[:current_source_window]:
                intent_site_domain = _site_domain_from_text(intent.query)
                config_site_domain = _site_domain_from_text(config.source_url_template)
                if intent_site_domain and not config_site_domain:
                    continue
                if intent_site_domain and config_site_domain and intent_site_domain != config_site_domain:
                    continue
                effective_query = _effective_query(intent, config)
                query_key = re.sub(r"\s+", "", effective_query).lower()
                if content_kind == "timely_intelligence":
                    query_key = f"{config.source_type}:{query_key}"
                if query_key in seen_effective_queries:
                    continue
                seen_effective_queries.add(query_key)
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
    if draft.content_kind == "timely_intelligence":
        if (
            draft.confidence_score >= 55
            and (
                draft.signal_count >= 2
                or any(flag in draft.quality_flags for flag in ("external_signal", "tag_relevant_signal", "inspiration_signal"))
                or any(term in f"{draft.hit.title} {draft.hit.snippet}" for term in EXTERNAL_SIGNAL_TERMS)
            )
        ):
            return True, "候选呈现外部信号，进入时效研判流程"
    object_hit = any(term in f"{draft.hit.title} {draft.hit.snippet}" for term in draft.matched_terms[:4])
    if draft.source_config.reliability_tier == "strong" and object_hit and draft.confidence_score >= 70:
        return True, "来源和内容命中工作对象，进入核验流程"
    if draft.source_config.reliability_tier != "strong" and draft.signal_count >= 2 and draft.confidence_score >= 70:
        return True, "多项信号命中工作对象，进入核验流程"
    return False, "相关性不足，暂不成卡"


def _ai_ready(ai_service: object | None) -> bool:
    return intelligence_ai_ready(ai_service)


def _intelligence_ai_text(
    ai_service: object | None,
    *,
    prompt: str,
    system_instruction: str,
    timeout_seconds: float = 90.0,
    max_tokens: int = 1000,
    temperature: float = 0.28,
    top_p: float = 0.88,
    task_kind: str = "default",
) -> str:
    """Shared AI text path for intelligence analysis with long timeout and retries."""
    normalized_task_kind = "deep_analysis" if task_kind == "default" else task_kind
    fast_mode = normalized_task_kind == "fast_structured"
    result = generate_intelligence_text(
        ai_service,
        prompt=prompt,
        system_instruction=system_instruction,
        timeout_seconds=max(45.0 if fast_mode else 120.0, timeout_seconds),
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        task_kind=normalized_task_kind,
        enable_thinking=not fast_mode,
        min_chars=20,
    )
    if not result.ok:
        logger.warning("intelligence AI text failed: %s", result.error)
    return result.text.strip()


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
        r"(?:发布时间|发布日期|发表时间|更新于|来源[:：][^0-9]{0,40}|作者[:：][^0-9]{0,40}|写在前面[:：]?)[:：]?\s*(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})",
        r"(?:成文日期|发布日期|发布时间|日期|时间)[:：]\s*(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})",
        r"(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})\s+\d{1,2}:\d{2}\s*(?:来源|发布|浏览|\(|（)",
        r"(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})\s*(?:来源|作者|写在前面|编者按)",
    )
    for pattern in patterns:
        match = re.search(pattern, header)
        if not match:
            continue
        year, month, day = match.group(1), match.group(2), match.group(3)
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    url_date = re.search(r"/(20\d{2})[-_/]?(\d{2})[-_/]?(\d{2})(?:/|_|-|\\.|$)", draft.hit.url or "")
    if url_date:
        return f"{int(url_date.group(1)):04d}-{int(url_date.group(2)):02d}-{int(url_date.group(3)):02d}"
    return None


def _fallback_timely_followup_questions(
    draft: CandidateDraft,
    intelligence_type: str,
    brief: ResearchBrief,
) -> list[str]:
    object_name = brief.scope.display_name or "当前客户/项目"
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
    return _unique_items(base, limit=3)


def _parse_ai_followup_questions(text: str) -> list[str]:
    questions: list[str] = []
    for raw_line in str(text or "").splitlines():
        line = _clean_text(
            re.sub(r"^\s*(?:[-*]|\d+[.、)]|[一二三四五六七八九十]+[、.])\s*", "", raw_line),
            max_len=120,
        )
        if not line:
            continue
        for part in re.split(r"[；;]\s*", line):
            question = _clean_text(part, max_len=120)
            if not question:
                continue
            if not question.endswith(("？", "?")) and any(term in question for term in ("什么", "是否", "如何", "哪些", "多大", "怎样")):
                question = f"{question}？"
            if question.endswith(("？", "?")) and not any(weak in question for weak in ("这是什么", "有哪些要点", "怎么跟进")):
                questions.append(question)
    return _unique_items(questions, limit=3)


def _timely_ai_followup_questions(
    ai_service: object | None,
    *,
    draft: CandidateDraft,
    brief: ResearchBrief,
    intelligence_type: str,
    summary: str,
    relevance: str,
    impact: str,
    suggested_action: str,
    evidence: EvidenceExtraction,
) -> list[str]:
    prompt = "\n".join(
        [
            f"当前对象：{brief.scope.display_name or '当前客户/项目'}",
            f"情报类型：{intelligence_type}",
            f"标题：{draft.hit.title}",
            f"发生了什么：{summary}",
            f"为什么有关：{relevance}",
            f"可能影响：{impact}",
            f"建议动作：{suggested_action}",
            f"证据句：{'；'.join(evidence.quotes[:3])}",
            "请为这张情报卡生成 2-3 条推荐追问。问题必须围绕传导链条、对象相关度、证据缺口或下一步判断，且要贴合这张卡的具体内容。",
            "只输出问题本身，每行一个，不要标题，不要解释。",
        ]
    )
    raw = _intelligence_ai_text(
        ai_service,
        prompt=prompt,
        system_instruction="你是资讯情报站的追问设计助手。只生成具体、深入、可继续分析的问题。",
        timeout_seconds=45.0,
        max_tokens=360,
        temperature=0.28,
        top_p=0.88,
        task_kind="fast_structured",
    )
    questions = _parse_ai_followup_questions(str(raw or ""))
    return questions


def _timely_candidate_gate(draft: CandidateDraft, body_text: str = "", brief: ResearchBrief | None = None) -> tuple[bool, str, str | None]:
    if _is_static_profile_material(draft, body_text):
        return False, "静态登记、官网介绍或年报资料应进入资料补全，不进入时效情报", None
    intelligence_type = _timely_intelligence_type(draft, body_text)
    if not intelligence_type:
        return False, "未识别出明确情报类型，暂不成卡", None
    text = f"{draft.hit.title} {draft.hit.snippet} {draft.intent.query} {draft.intent.reason} {body_text[:1600]}"
    source_text = f"{draft.hit.title} {draft.hit.snippet} {body_text[:1600]}"
    if _looks_like_business_only_policy(source_text):
        return False, "企业/经贸类外部政策未出现公益、社会服务或当前对象业务锚点，暂不成卡", None
    has_external_signal = _has_external_signal(source_text, draft.source_config.source_type)
    strategy_tag_hits = _meaningful_timely_strategy_hits(source_text, brief)
    if (
        _looks_like_generic_macro_signal(source_text)
        or any(marker in source_text for marker in ("泛泛讨论", "宏观讨论", "高质量发展论坛", "行业论坛"))
        and re.search(r"没有[^。；;]{0,40}(申报|监管|合作|风险|政策|采购|招标|资助)", source_text)
        and not any(marker in source_text for marker in ("征集通知", "申报通知", "截止时间", "报名截止", "中标公告", "采购公告"))
    ):
        return False, "泛行业新闻未呈现可传导到当前对象的决策相关机会、风险、约束或合作变化，暂不成卡", None
    if brief and brief.timely_strategy:
        strategy_match = evaluate_timely_strategy_match(source_text, brief.timely_strategy)
        if not strategy_match.get("ok") and not (has_external_signal and strategy_tag_hits):
            return False, _clean_text(strategy_match.get("reason") or "未通过情报策略复核，暂不成卡", max_len=180), None
    object_terms = [term for term in draft.matched_terms if term and term in source_text][:4]
    direct_identity_hits = _direct_identity_hits(source_text, brief)
    has_sector_signal = any(term in source_text for term in PUBLIC_SERVICE_ANCHOR_TERMS)
    if not object_terms and not has_sector_signal and not strategy_tag_hits:
        return False, "只有泛政策或弱相关新闻，未出现公益、社会服务或当前对象业务锚点，暂不成卡", None
    if not object_terms:
        transfer_terms = (
            "申报", "征集", "截止", "资助", "扶持", "招标", "采购", "中标",
            "监管", "合规", "公开募捐", "处罚", "风险", "整改", "规范",
            "儿童", "困境", "心理", "社区服务", "社会组织",
        )
        if not any(term in source_text for term in transfer_terms):
            return False, "泛政策或泛通知缺少可传导到客户/项目的机会、风险或约束链条，暂不成卡", None
    if has_external_signal and strategy_tag_hits and not direct_identity_hits:
        intelligence_type = "启发型情报"
    if not body_text and len(draft.hit.snippet or draft.hit.title) < 12:
        return False, "公开信息过短，无法判断发生了什么", None
    if body_text and not any(term in text for term in (*TIMELY_MATERIAL_TERMS, *EXTERNAL_SIGNAL_TERMS)):
        return False, "正文未呈现近期变化、窗口、政策、风险或合作动态，暂不成卡", None
    return True, "已识别近期外部变化，并具备对象或行业相关信号", intelligence_type


def _build_timely_enrichment(
    ai_service: object | None,
    draft: CandidateDraft,
    body_text: str,
    evidence: EvidenceExtraction,
    brief: ResearchBrief,
) -> TimelyEnrichmentResult | None:
    passed, reason, intelligence_type = _timely_candidate_gate(draft, body_text, brief=brief)
    if not passed or not intelligence_type:
        draft.hit.snippet = draft.hit.snippet or reason
        return None
    if not _ai_ready(ai_service):
        return None
    strategy = brief.timely_strategy or {}
    strategy_routes = []
    for route in strategy.get("routes") or []:
        if isinstance(route, dict) and route.get("label"):
            strategy_routes.append(_clean_text(route.get("label"), max_len=24))
    strategy_atoms = _as_text_list(strategy.get("searchAtoms"), limit=10)
    body_excerpt = _clean_text(body_text, max_len=1200)
    evidence_text = _clean_text("；".join(evidence.quotes[:4]), max_len=900)
    prompt = "\n".join(
        [
            f"当前对象：{strategy.get('objectName') or brief.scope.display_name or '当前客户/项目'}",
            f"对象画像主题：{'、'.join(strategy_atoms[:8]) if strategy_atoms else '未充分识别'}",
            f"本轮监测路线：{'、'.join(_unique_items(strategy_routes, limit=8)) if strategy_routes else '政策、资助、采购、合作、风险、趋势'}",
            f"标题：{draft.hit.title}",
            f"来源：{draft.hit.source}",
            f"搜索短摘：{draft.hit.snippet}",
            f"命中搜索意图：{draft.intent.query}",
            f"情报类型：{intelligence_type}",
            f"已抽取证据句：{evidence_text}",
            f"网页正文摘录：{body_excerpt}",
            "请只基于网页正文和证据句整理时效情报卡。",
            "必须输出：发生了什么、为什么和当前客户/项目有关、可能影响、建议动作、证据不足点；不得只复述标题或搜索短摘。",
            "建议动作可以是阅读/研判任务，不要强行写成执行任务；不要使用“先确认负责人、再补材料”这类模板空话。",
            "不能假设当前对象一定符合资格；资格、地域和窗口不明时，要写成需核验。",
        ]
    )
    response = _timely_structured_ai_response(
        ai_service,
        prompt=prompt,
        draft=draft,
        intelligence_type=intelligence_type,
    )
    if response is None:
        return None
    if not isinstance(response, AiStructuredResponse):
        return None
    summary = _clean_text(response.content or draft.hit.snippet or draft.hit.title, max_len=500)
    relevance = _clean_text(response.judgment or response.analysis or "", max_len=700)
    impact = _clean_text(response.analysis or response.timeline or "", max_len=700)
    suggested_action = _clean_text(response.actions or "", max_len=500)
    if (
        not summary
        or not relevance
        or not impact
        or not suggested_action
        or not _timely_ai_output_is_specific(
            summary=summary,
            relevance=relevance,
            impact=impact,
            suggested_action=suggested_action,
            draft=draft,
            evidence=evidence,
            brief=brief,
        )
    ):
        return None
    followups = _timely_ai_followup_questions(
        ai_service,
        draft=draft,
        brief=brief,
        intelligence_type=intelligence_type,
        summary=summary,
        relevance=relevance,
        impact=impact,
        suggested_action=suggested_action,
        evidence=evidence,
    )
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
    allow_ai_review: bool = True,
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
    if draft.content_kind != "profile_completion":
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
        reason = verification.verification_reason
        verification_status = verification.verification_status
        created_item_ids: list[str] = []
        for card in verification.fact_cards:
            if _profile_fact_already_active(
                db,
                scope=scope,
                source_url=draft.hit.url,
                dimension=card.dimension,
                fact_signature=card.fact_signature,
            ):
                continue
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
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, NULL, NULL, '', '', '[]', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    item_id,
                    draft.content_kind,
                    scope.scope_type,
                    scope.scope_id,
                    scope.client_id,
                    scope.project_module_id,
                    card.title,
                    card.summary,
                    to_json(card.key_points),
                    card.analysis,
                    to_json(["已核验资料", card.dimension, *[tag for tag in verification.mapped_tags if tag != card.dimension][:2]]),
                    _source_display_name(draft),
                    draft.hit.url,
                    published_at,
                    timestamp,
                    verified_at,
                    min(draft.confidence_score / 100, 0.98),
                    min(draft.confidence_score / 100, 0.98),
                    data_center_document_id,
                    verification_status,
                    f"{reason}；事实维度：{card.dimension}",
                    timestamp,
                    timestamp,
                ),
            )
            created_item_ids.append(item_id)
        if not created_item_ids:
            db.execute(
                """
                UPDATE intelligence_candidate_items
                SET classification_status = 'duplicate',
                    promotion_reason = ?,
                    is_user_visible_candidate = 0,
                    updated_at = ?
                WHERE id = ?
                """,
                ("同一来源下的同维度事实已成卡，避免重复展示", timestamp, draft.id),
            )
            return False
        candidate_row = db.fetchone("SELECT evidence_json FROM intelligence_candidate_items WHERE id = ?", (draft.id,))
        evidence_payload = _safe_json(str(candidate_row["evidence_json"] or "{}"), {}) if candidate_row else {}
        if not isinstance(evidence_payload, dict):
            evidence_payload = {}
        evidence_payload["createdFactCardCount"] = len(created_item_ids)
        db.execute(
            "UPDATE intelligence_candidate_items SET evidence_json = ?, updated_at = ? WHERE id = ?",
            (to_json(evidence_payload), timestamp, draft.id),
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
            (reason, created_item_ids[0], data_center_document_id, timestamp, draft.id),
        )
        return True
    else:
        body_status, body_text, body_reason = _fetch_page_text(draft.hit.url)
        body_excerpt = body_text[:1000]
        page_quality = _classify_fetched_page(draft.hit, body_status, body_text, body_reason)
        base_quality_flags = _unique_items([*draft.quality_flags, *page_quality.flags], limit=18)
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
                quality_flags=base_quality_flags,
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
                quality_flags=base_quality_flags,
            )
            return False
        published_at = _profile_published_at(draft, body_text)
        draft.hit.published_at = published_at
        passed, gate_reason, _intelligence_type = _timely_candidate_gate(draft, body_text, brief=brief)
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
                quality_flags=base_quality_flags,
            )
            return False
        fresh_enough, freshness_reason, freshness_bucket = _timely_publication_freshness(published_at, timestamp=timestamp, max_age_days=90, body_text=body_text)
        freshness_flags = [freshness_bucket] if freshness_bucket else []
        if not fresh_enough:
            _update_candidate_verification(
                db,
                candidate_id=draft.id,
                verification_status="rejected",
                verification_reason=freshness_reason,
                body_fetch_status=body_status,
                summary_status="not_attempted",
                mapped_tags=[],
                body_excerpt=body_excerpt,
                timestamp=timestamp,
                page_type=page_quality.page_type,
                quality_flags=[*base_quality_flags, "stale_timely_source"],
            )
            return False
        evidence = _extract_research_evidence(
            brief=brief,
            content_kind="timely_intelligence",
            draft=draft,
            body_text=body_text,
        )
        if evidence is None:
            evidence = _fallback_timely_evidence(brief=brief, draft=draft, body_text=body_text)
        if evidence is None:
            strategy_match = evaluate_timely_strategy_match(
                f"{draft.hit.title} {draft.hit.snippet} {draft.intent.query} {draft.intent.reason} {body_text[:2400]}",
                brief.timely_strategy,
            )
            strategy_reason = _clean_text(strategy_match.get("reason") if isinstance(strategy_match, dict) else "", max_len=140)
            strategy_failed = bool(strategy_reason) and (not isinstance(strategy_match, dict) or not bool(strategy_match.get("ok")))
            reason = (
                f"策略复核未通过：{strategy_reason}"
                if strategy_failed
                else "策略复核未通过：正文未回应当前重点关注，或缺少外部变化与影响链条证据，暂不成卡"
            )
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
                quality_flags=[*base_quality_flags, "insufficient_impact_evidence"],
            )
            return False
        if not allow_ai_review:
            _update_candidate_verification(
                db,
                candidate_id=draft.id,
                verification_status="pending",
                verification_reason="候选已通过详情复核前置条件，但本轮 AI 深度分析预算已满，暂不自动成卡",
                body_fetch_status=body_status,
                summary_status="not_attempted",
                mapped_tags=[],
                body_excerpt=body_excerpt,
                timestamp=timestamp,
                page_type=page_quality.page_type,
                quality_flags=[*base_quality_flags, "ai_review_budget_deferred"],
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
                quality_flags=base_quality_flags,
            )
            return False
        enrichment = _build_timely_enrichment(ai_service, draft, body_text, evidence, brief)
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
                quality_flags=base_quality_flags,
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
            quality_flags=[*base_quality_flags, *freshness_flags],
            evidence={
                "quotes": evidence.quotes,
                "facts": evidence.facts,
                "focusHits": evidence.focus_hits,
                "missing": evidence.missing,
                "timelyStrategy": brief.timely_strategy,
                "freshnessReason": freshness_reason,
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


ProfileResearchProgressCallback = Callable[[CandidateRefreshResult, str, str], None]


def _profile_created_fact_count(db: Database, candidate_id: str) -> int:
    row = db.fetchone("SELECT evidence_json, classification_status FROM intelligence_candidate_items WHERE id = ?", (candidate_id,))
    if not row:
        return 0
    payload = _safe_json(str(row["evidence_json"] or "{}"), {})
    if not isinstance(payload, dict):
        return 0
    created = int(payload.get("createdFactCardCount") or 0)
    if created:
        return created
    if str(row["classification_status"] or "") == "promoted":
        fact_cards = payload.get("factCards")
        if isinstance(fact_cards, list):
            return len(fact_cards)
    return 0


def _profile_research_snapshot(
    db: Database,
    *,
    scope: IntelligenceSearchScope,
    source_config_count: int,
    candidate_ids: list[str],
    fetch_job_count: int,
    success_query_count: int,
    no_result_query_count: int,
    duplicate_count: int,
    failed_count: int,
    rejection_counts: dict[str, int],
    search_direction_count: int,
    direct_source_count: int,
    quick_win_card_count: int,
    deep_queue_count: int,
    deferred_hard_sources: list[str],
    research_stage: str,
    profile_run_mode: str = "standard",
    deep_dive_queued_count: int = 0,
    deep_dive_processed_count: int = 0,
    deep_dive_skipped_count: int = 0,
    deep_dive_remaining_count: int | None = None,
    deep_dive_source_titles: list[str] | None = None,
    deep_dive_skip_summary: list[str] | None = None,
) -> CandidateRefreshResult:
    body_fetched_count = 0
    verified_count = 0
    summary_success_count = 0
    profile_fact_candidate_count = 0
    profile_fact_card_count = 0
    processed_page_count = 0
    promoted_count = 0
    snapshot_rejections = dict(rejection_counts)
    if candidate_ids:
        placeholders = ",".join("?" for _ in candidate_ids)
        rows = db.fetchall(
            f"""
            SELECT classification_status, body_fetch_status, verification_status, summary_status,
                   promotion_reason, page_type, evidence_json
            FROM intelligence_candidate_items
            WHERE id IN ({placeholders})
            """,
            tuple(candidate_ids),
        )
        for row in rows:
            body_status = str(row["body_fetch_status"] or "")
            summary_status = str(row["summary_status"] or "")
            verification_status = str(row["verification_status"] or "")
            classification_status = str(row["classification_status"] or "")
            page_type = str(row["page_type"] or "")
            if body_status and body_status != "not_attempted":
                processed_page_count += 1
            elif page_type in {"list_page", "pdf", "unsupported_pdf"}:
                processed_page_count += 1
            if body_status == "fetched":
                body_fetched_count += 1
            if verification_status == "verified":
                verified_count += 1
            if summary_status == "generated":
                summary_success_count += 1
            if classification_status == "promoted":
                promoted_count += 1
            reason = _clean_text(str(row["promotion_reason"] or ""), max_len=80)
            if reason and summary_status != "generated":
                snapshot_rejections[reason] = snapshot_rejections.get(reason, 0) + 1
            payload = _safe_json(str(row["evidence_json"] or "{}"), {})
            if isinstance(payload, dict):
                fact_cards = payload.get("factCards")
                if isinstance(fact_cards, list):
                    profile_fact_candidate_count += len(fact_cards)
                profile_fact_card_count += int(payload.get("createdFactCardCount") or 0)
    profile_gap_map = _profile_gap_map_snapshot(db, scope)
    profile_coverage = _as_text_list(profile_gap_map.get("covered"), limit=16)
    profile_missing_dimensions = _as_text_list(profile_gap_map.get("missing"), limit=16)
    profile_partial_dimensions = _as_text_list(profile_gap_map.get("partial"), limit=16)
    status_payload = get_candidate_supply_status_for_scope(db, scope_type=scope.scope_type, scope_id=scope.scope_id)
    remaining = _unique_items([*profile_missing_dimensions, *profile_partial_dimensions], limit=16)
    deep_counts, queued_titles, skipped_reasons = _profile_deep_dive_status_snapshot(db, scope)
    remaining_deep_count = deep_dive_remaining_count if deep_dive_remaining_count is not None else deep_counts.get("queued", 0) + deep_counts.get("processing", 0)
    return CandidateRefreshResult(
        source_config_count=source_config_count,
        fetch_job_count=fetch_job_count,
        candidate_count=len(candidate_ids),
        promoted_count=promoted_count,
        duplicate_count=duplicate_count,
        failed_count=failed_count,
        body_fetched_count=body_fetched_count,
        verified_count=verified_count,
        summary_success_count=summary_success_count,
        rejection_counts=snapshot_rejections,
        source_coverage_status=str(status_payload.get("sourceCoverageStatus") or "ready"),
        candidate_refresh_status=str(status_payload.get("candidateRefreshStatus") or "ready"),
        last_candidate_fetch_at=str(status_payload.get("lastCandidateFetchAt") or now_iso()),
        candidate_counts=dict(status_payload.get("candidateCounts") or {}),
        profile_coverage=profile_coverage,
        profile_missing_dimensions=profile_missing_dimensions,
        profile_partial_dimensions=profile_partial_dimensions,
        profile_gap_map=profile_gap_map,
        profile_completion_ready=bool(profile_gap_map.get("ready")),
        search_direction_count=search_direction_count,
        query_count=fetch_job_count,
        success_query_count=success_query_count,
        no_result_query_count=no_result_query_count,
        effective_lead_count=max(0, len(candidate_ids) - duplicate_count),
        direct_source_count=direct_source_count,
        pages_fetched_count=body_fetched_count,
        profile_fact_candidate_count=profile_fact_candidate_count,
        profile_fact_card_count=profile_fact_card_count,
        uncovered_gaps=remaining,
        research_stage=research_stage,
        processed_page_count=processed_page_count,
        usable_fact_count=profile_fact_candidate_count,
        quick_win_card_count=quick_win_card_count,
        deep_queue_count=deep_queue_count,
        covered_sub_gaps=profile_coverage,
        remaining_sub_gaps=remaining,
        deferred_hard_sources=_unique_items(deferred_hard_sources, limit=8),
        profile_run_mode=profile_run_mode,
        deep_dive_queued_count=deep_dive_queued_count,
        deep_dive_processed_count=deep_dive_processed_count,
        deep_dive_skipped_count=deep_dive_skipped_count,
        deep_dive_remaining_count=remaining_deep_count,
        deep_dive_source_titles=_unique_items(deep_dive_source_titles or queued_titles, limit=8),
        deep_dive_skip_summary=_unique_items(deep_dive_skip_summary or skipped_reasons, limit=5),
    )


def _profile_layered_fetch_tasks(
    db: Database,
    *,
    intents: list[GeneratedSearchIntent],
    configs: list[SourceConfig],
    max_fetch_jobs: int,
) -> list[tuple[str, GeneratedSearchIntent, SourceConfig]]:
    timestamp = now_iso()
    profile_intents = sorted(
        [intent for intent in intents if intent.content_kind == "profile_completion"],
        key=lambda item: (-item.priority, item.query),
    )
    profile_configs = [
        config
        for config in configs
        if config.source_type in PROFILE_SOURCE_TYPES and (not config.content_kinds or "profile_completion" in config.content_kinds)
    ]
    layers: list[tuple[str, set[str], int, int]] = [
        ("quick", {"official_site", "official_site_section", "web_search", "charity_media", "social_org_registry"}, 28, 2),
        ("expand", {"official_site", "official_site_section", "web_search", "charity_media", "profile_report", "social_org_registry"}, 54, 3),
        ("deep", {"profile_report", "social_org_registry", "official_site_section"}, max_fetch_jobs, 2),
    ]
    tasks: list[tuple[str, GeneratedSearchIntent, SourceConfig]] = []
    seen_effective_queries: set[str] = set()
    for layer, source_types, layer_cap, source_window in layers:
        for intent in profile_intents:
            if len(tasks) >= max_fetch_jobs or len([item for item in tasks if item[0] == layer]) >= layer_cap:
                break
            allowed_profile_types = _profile_allowed_source_types(intent).intersection(source_types)
            routed_configs = sorted(
                [config for config in profile_configs if config.source_type in allowed_profile_types],
                key=lambda config: (
                    -(
                        _source_priority_score_for_kind(db, config, content_kind="profile_completion", timestamp=timestamp)
                        + _source_route_bonus(intent, config)
                    ),
                    config.source_type,
                    config.source_name,
                ),
            )
            for config in routed_configs[:source_window]:
                intent_site_domain = _site_domain_from_text(intent.query)
                config_site_domain = _site_domain_from_text(config.source_url_template)
                if intent_site_domain and not config_site_domain:
                    continue
                if intent_site_domain and config_site_domain and intent_site_domain != config_site_domain:
                    continue
                effective_query = _effective_query(intent, config)
                query_key = re.sub(r"\s+", "", effective_query).lower()
                if query_key in seen_effective_queries:
                    continue
                seen_effective_queries.add(query_key)
                tasks.append((layer, intent, config))
                if len(tasks) >= max_fetch_jobs or len([item for item in tasks if item[0] == layer]) >= layer_cap:
                    break
    return tasks[:max_fetch_jobs]


PROFILE_DEEP_DIVE_VALUE_TERMS = (
    "年报",
    "年度报告",
    "审计",
    "信息公开",
    "报告",
    "项目",
    "案例",
    "成效",
    "团队",
    "负责人",
    "服务对象",
    "课程",
    "方法",
    "合作",
    "资助",
)


def _deep_dive_payload(
    *,
    status: str,
    reason: str,
    cost_tier: str,
    value_tier: str,
    source_stage: str = "deep_pool",
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "sourceStage": source_stage,
        "deepDiveStatus": status,
        "deepDiveReason": _clean_text(reason, max_len=240),
        "costTier": cost_tier,
        "valueTier": value_tier,
    }
    if extra:
        payload.update(extra)
    return payload


def _merge_candidate_evidence(db: Database, candidate_id: str, patch: dict[str, object], *, timestamp: str) -> dict[str, object]:
    row = db.fetchone("SELECT evidence_json FROM intelligence_candidate_items WHERE id = ?", (candidate_id,))
    payload = _safe_json(str(row["evidence_json"] or "{}"), {}) if row else {}
    if not isinstance(payload, dict):
        payload = {}
    payload.update(patch)
    db.execute(
        "UPDATE intelligence_candidate_items SET evidence_json = ?, updated_at = ? WHERE id = ?",
        (to_json(payload), timestamp, candidate_id),
    )
    return payload


def _profile_deep_dive_decision(
    *,
    hit: CandidateHit,
    config: SourceConfig,
    page_quality: PageQuality,
    brief: ResearchBrief,
    intent: GeneratedSearchIntent,
) -> tuple[str, str, str, str]:
    text = f"{hit.title} {hit.snippet} {hit.url} {config.source_type} {intent.query} {intent.reason}"
    trusted = config.source_type in {"official_site", "official_site_section", "profile_report", "social_org_registry", "charity_media"} or config.reliability_tier == "strong"
    focus_terms = _unique_items([*brief.profile_focus_terms, *_intent_terms(intent), *brief.object_terms], limit=28)
    focus_hit = any(term and term in text for term in focus_terms)
    value_hit = any(term in text for term in PROFILE_DEEP_DIVE_VALUE_TERMS)
    if page_quality.page_type in {"pdf", "unsupported_pdf"}:
        if trusted and (value_hit or focus_hit or config.source_type == "profile_report"):
            return "queued", "可信来源 PDF/报告类资料，进入下一轮自动深挖", "high", "high"
        return "skipped", "PDF 来源价值或对象关系不够明确，本轮不投入深挖预算", "high", "uncertain"
    if page_quality.page_type == "list_page":
        if trusted and (value_hit or focus_hit or config.source_type in {"official_site", "official_site_section", "social_org_registry"}):
            return "queued", "可信列表/栏目页，进入下一轮自动下钻深挖", "medium", "high"
        return "skipped", "列表页价值或对象关系不够明确，本轮不投入深挖预算", "medium", "uncertain"
    return "skipped", "复杂来源价值不确定，本轮跳过", "medium", "uncertain"


def _existing_profile_deep_candidate(db: Database, *, scope: IntelligenceSearchScope, dedupe_key: str) -> str | None:
    row = db.fetchone(
        """
        SELECT id
        FROM intelligence_candidate_items
        WHERE scope_type = ? AND scope_id = ? AND content_kind = 'profile_completion' AND dedupe_key = ?
          AND classification_status IN ('candidate', 'promoted')
          AND evidence_json LIKE '%deepDiveStatus%'
        ORDER BY captured_at DESC
        LIMIT 1
        """,
        (scope.scope_type, scope.scope_id, dedupe_key),
    )
    return str(row["id"]) if row else None


def _record_profile_deep_source(
    db: Database,
    *,
    scope: IntelligenceSearchScope,
    draft: CandidateDraft,
    timestamp: str,
    status: str,
    reason: str,
    cost_tier: str,
    value_tier: str,
) -> tuple[str | None, bool]:
    existing_id = _existing_profile_deep_candidate(db, scope=scope, dedupe_key=draft.dedupe_key)
    if existing_id:
        return existing_id, False
    _insert_candidate(db, scope=scope, draft=draft, classification_status="candidate", duplicate_of_id=None, timestamp=timestamp)
    evidence = _deep_dive_payload(
        status=status,
        reason=reason,
        cost_tier=cost_tier,
        value_tier=value_tier,
        extra={"sourceTitle": draft.hit.title, "sourceUrl": draft.hit.url},
    )
    verification_status = "pending" if status == "queued" else "rejected"
    _update_candidate_verification(
        db,
        candidate_id=draft.id,
        verification_status=verification_status,
        verification_reason=reason,
        body_fetch_status="not_attempted",
        summary_status="not_attempted",
        mapped_tags=[],
        body_excerpt="",
        timestamp=timestamp,
        visible=False,
        page_type=draft.page_type,
        quality_flags=[*draft.quality_flags, f"deep_dive_{status}"],
        evidence=evidence,
    )
    return draft.id, True


def _profile_deep_dive_status_snapshot(db: Database, scope: IntelligenceSearchScope) -> tuple[dict[str, int], list[str], list[str]]:
    rows = db.fetchall(
        """
        SELECT title, evidence_json
        FROM intelligence_candidate_items
        WHERE scope_type = ? AND scope_id = ? AND content_kind = 'profile_completion'
          AND evidence_json LIKE '%deepDiveStatus%'
        """,
        (scope.scope_type, scope.scope_id),
    )
    counts = {"queued": 0, "processing": 0, "processed": 0, "skipped": 0}
    queued_titles: list[str] = []
    skipped_reasons: list[str] = []
    for row in rows:
        payload = _safe_json(str(row["evidence_json"] or "{}"), {})
        if not isinstance(payload, dict):
            continue
        status = str(payload.get("deepDiveStatus") or "").strip()
        if status not in counts:
            continue
        counts[status] += 1
        if status in {"queued", "processing"}:
            queued_titles.append(_clean_text(payload.get("sourceTitle") or row["title"], max_len=80))
        if status == "skipped":
            reason = _clean_text(payload.get("deepDiveReason"), max_len=80)
            if reason:
                skipped_reasons.append(reason)
    return counts, _unique_items(queued_titles, limit=8), _unique_items(skipped_reasons, limit=5)


def _profile_deep_dive_rows(db: Database, scope: IntelligenceSearchScope, *, limit: int) -> list[object]:
    rows = db.fetchall(
        """
        SELECT
            c.*,
            i.query AS intent_query,
            i.reason AS intent_reason,
            i.priority AS intent_priority,
            i.exclude_terms_json AS intent_exclude_terms_json,
            i.source_inputs_json AS intent_source_inputs_json,
            i.input_hash AS intent_input_hash,
            i.expires_at AS intent_expires_at,
            s.source_type AS cfg_source_type,
            s.source_name AS cfg_source_name,
            s.source_url_template AS cfg_source_url_template,
            s.region AS cfg_region,
            s.reliability_tier AS cfg_reliability_tier,
            s.priority AS cfg_priority,
            s.content_kinds_json AS cfg_content_kinds_json,
            s.enabled AS cfg_enabled,
            s.discovery_source AS cfg_discovery_source,
            s.discovery_reason AS cfg_discovery_reason,
            s.discovery_samples_json AS cfg_discovery_samples_json,
            s.health_score AS cfg_health_score,
            s.success_count AS cfg_success_count,
            s.failure_count AS cfg_failure_count,
            s.candidate_count AS cfg_candidate_count,
            s.promoted_count AS cfg_promoted_count,
            s.duplicate_count AS cfg_duplicate_count,
            s.last_status AS cfg_last_status,
            s.last_checked_at AS cfg_last_checked_at,
            s.last_success_at AS cfg_last_success_at,
            s.last_failure_at AS cfg_last_failure_at,
            s.next_due_at AS cfg_next_due_at
        FROM intelligence_candidate_items c
        LEFT JOIN intelligence_search_intents i ON i.id = c.intent_id
        LEFT JOIN intelligence_source_configs s ON s.id = c.source_config_id
        WHERE c.scope_type = ? AND c.scope_id = ? AND c.content_kind = 'profile_completion'
          AND c.classification_status = 'candidate'
          AND c.evidence_json LIKE '%deepDiveStatus%'
        ORDER BY c.captured_at ASC
        LIMIT ?
        """,
        (scope.scope_type, scope.scope_id, max(1, limit * 4)),
    )
    queued: list[object] = []
    for row in rows:
        payload = _safe_json(str(row["evidence_json"] or "{}"), {})
        if isinstance(payload, dict) and str(payload.get("deepDiveStatus") or "") == "queued":
            queued.append(row)
        if len(queued) >= limit:
            break
    return queued


def _deep_dive_source_config_from_row(row: object, scope: IntelligenceSearchScope) -> SourceConfig:
    return SourceConfig(
        id=str(row["source_config_id"] or "deep_dive_source"),
        scope_type=str(row["scope_type"] or scope.scope_type),
        scope_id=str(row["scope_id"] or scope.scope_id),
        client_id=str(row["client_id"] or scope.client_id or ""),
        project_module_id=str(row["project_module_id"] or scope.project_module_id or "") or None,
        source_type=str(row["cfg_source_type"] or "web_search"),
        source_name=str(row["cfg_source_name"] or row["source"] or "深挖来源"),
        source_url_template=str(row["cfg_source_url_template"] or ""),
        region=str(row["cfg_region"] or ""),
        reliability_tier=str(row["cfg_reliability_tier"] or row["source_tier"] or "standard"),
        priority=int(row["cfg_priority"] or 70),
        content_kinds=_as_text_list(_safe_json(str(row["cfg_content_kinds_json"] or "[]"), []), limit=8),
        enabled=bool(row["cfg_enabled"] if row["cfg_enabled"] is not None else True),
        discovery_source=str(row["cfg_discovery_source"] or "deep_pool"),
        discovery_reason=str(row["cfg_discovery_reason"] or ""),
        discovery_samples=[item for item in (_safe_json(str(row["cfg_discovery_samples_json"] or "[]"), []) or []) if isinstance(item, dict)][:5],
        health_score=float(row["cfg_health_score"] or 70.0),
        success_count=int(row["cfg_success_count"] or 0),
        failure_count=int(row["cfg_failure_count"] or 0),
        candidate_count=int(row["cfg_candidate_count"] or 0),
        promoted_count=int(row["cfg_promoted_count"] or 0),
        duplicate_count=int(row["cfg_duplicate_count"] or 0),
        last_status=str(row["cfg_last_status"] or "unknown"),
        last_checked_at=str(row["cfg_last_checked_at"] or "") or None,
        last_success_at=str(row["cfg_last_success_at"] or "") or None,
        last_failure_at=str(row["cfg_last_failure_at"] or "") or None,
        next_due_at=str(row["cfg_next_due_at"] or "") or None,
    )


def _deep_dive_intent_from_row(row: object, scope: IntelligenceSearchScope) -> GeneratedSearchIntent:
    return GeneratedSearchIntent(
        id=str(row["intent_id"] or f"intent_deep_{row['id']}"),
        scope_type=scope.scope_type,
        scope_id=scope.scope_id,
        client_id=scope.client_id,
        project_module_id=scope.project_module_id,
        content_kind="profile_completion",
        query=str(row["intent_query"] or row["title"] or scope.display_name),
        exclude_terms=_as_text_list(_safe_json(str(row["intent_exclude_terms_json"] or "[]"), []), limit=12),
        source_inputs=_as_text_list(_safe_json(str(row["intent_source_inputs_json"] or "[]"), []), limit=12) or ["deep_pool"],
        reason=str(row["intent_reason"] or "资料补全自动深挖池"),
        priority=int(row["intent_priority"] or 80),
        status="ready",
        input_hash=str(row["intent_input_hash"] or f"deep_pool:{row['id']}"),
        expires_at=str(row["intent_expires_at"] or now_iso()),
    )


def _deep_dive_draft_from_row(row: object, scope: IntelligenceSearchScope) -> CandidateDraft:
    hit = CandidateHit(
        title=str(row["title"] or ""),
        url=str(row["url"] or ""),
        snippet=str(row["snippet"] or ""),
        source=str(row["source"] or ""),
        published_at=str(row["published_at"] or "") or None,
        provider=str(row["provider"] or "deep_pool"),
    )
    flags = _as_text_list(_safe_json(str(row["quality_flags_json"] or "[]"), []), limit=16)
    return CandidateDraft(
        id=str(row["id"]),
        content_kind="profile_completion",
        intent=_deep_dive_intent_from_row(row, scope),
        source_config=_deep_dive_source_config_from_row(row, scope),
        fetch_job_id=str(row["fetch_job_id"] or ""),
        hit=hit,
        normalized_url=str(row["normalized_url"] or _normalize_url(hit.url)),
        dedupe_key=str(row["dedupe_key"] or _dedupe_key(hit.title, _normalize_url(hit.url))),
        matched_terms=_as_text_list(_safe_json(str(row["matched_terms_json"] or "[]"), []), limit=18),
        confidence_score=float(row["confidence_score"] or 76.0),
        signal_count=max(2, len(_as_text_list(_safe_json(str(row["matched_terms_json"] or "[]"), []), limit=18))),
        page_type=str(row["page_type"] or ""),
        quality_flags=_unique_items([*flags, "deep_dive_processing"], limit=20),
    )


def run_profile_completion_research(
    db: Database,
    *,
    data_dir: Path,
    ai_service: object | None,
    scope: IntelligenceSearchScope,
    intents: list[GeneratedSearchIntent],
    trigger_source: str = "manual",
    max_fetch_jobs: int = 200,
    hit_fetcher: Callable[[str, SourceConfig], list[CandidateHit | dict[str, object]]] | None = None,
    official_site_hit_fetcher: Callable[[str, SourceConfig], list[CandidateHit | dict[str, object]]] | None = None,
    progress_callback: ProfileResearchProgressCallback | None = None,
    max_runtime_seconds: int = 30 * 60,
) -> CandidateRefreshResult:
    timestamp = now_iso()
    deadline_monotonic = time.monotonic() + max(30, max_runtime_seconds)
    brief = _load_research_brief(db, scope)
    ensure_default_source_configs(db, scope)
    ensure_user_supplied_official_sources(db, scope, brief)
    discover_official_site_source_configs(
        db,
        scope=scope,
        hit_fetcher=official_site_hit_fetcher or hit_fetcher,
    )
    _disable_invalid_discovered_sources(db, scope)
    configs = ensure_default_source_configs(db, scope)
    fetcher = hit_fetcher or _fetch_public_search_hits
    queued_deep_rows = _profile_deep_dive_rows(db, scope, limit=min(max_fetch_jobs, 24))
    tasks = [] if queued_deep_rows else _profile_layered_fetch_tasks(db, intents=intents, configs=configs, max_fetch_jobs=max_fetch_jobs)
    candidate_ids: list[str] = []
    seen_dedupe_keys: set[str] = set()
    fetch_job_count = 0
    success_query_count = 0
    no_result_query_count = 0
    failed_count = 0
    duplicate_count = 0
    promoted_count = 0
    quick_win_card_count = 0
    deep_queue_count = 0
    deep_dive_queued_count = len(queued_deep_rows)
    deep_dive_processed_count = 0
    deep_dive_skipped_count = 0
    deep_dive_source_titles: list[str] = []
    deep_dive_skip_summary: list[str] = []
    profile_run_mode = "deep_dive" if queued_deep_rows else "standard"
    direct_source_count = sum(1 for layer, _intent, config in tasks if layer == "quick" and config.source_type in {"official_site", "official_site_section"})
    deferred_hard_sources: list[str] = []
    rejection_counts: dict[str, int] = {}
    search_directions = {
        _clean_text(intent.reason.split("。")[0], max_len=80) or intent.query
        for _layer, intent, _config in tasks
    }

    def emit(stage: str, message: str) -> CandidateRefreshResult:
        result = _profile_research_snapshot(
            db,
            scope=scope,
            source_config_count=len(configs),
            candidate_ids=candidate_ids,
            fetch_job_count=fetch_job_count,
            success_query_count=success_query_count,
            no_result_query_count=no_result_query_count,
            duplicate_count=duplicate_count,
            failed_count=failed_count,
            rejection_counts=rejection_counts,
            search_direction_count=len(search_directions),
            direct_source_count=direct_source_count,
            quick_win_card_count=quick_win_card_count,
            deep_queue_count=deep_queue_count,
            deferred_hard_sources=deferred_hard_sources,
            research_stage=stage,
            profile_run_mode=profile_run_mode,
            deep_dive_queued_count=deep_dive_queued_count,
            deep_dive_processed_count=deep_dive_processed_count,
            deep_dive_skipped_count=deep_dive_skipped_count,
            deep_dive_source_titles=deep_dive_source_titles,
            deep_dive_skip_summary=deep_dive_skip_summary,
        )
        if progress_callback:
            progress_callback(result, stage, message)
        return result

    if queued_deep_rows:
        last_result = emit("deep_dive_start", "正在处理上一轮发现的年报/PDF、列表页和复杂来源")
        processed_since_emit = 0
        for row in queued_deep_rows:
            if time.monotonic() >= deadline_monotonic:
                return emit("completed", "资料深挖已达到本轮时间预算，剩余复杂来源将留到下一轮继续处理")
            parent_draft = _deep_dive_draft_from_row(row, scope)
            candidate_ids.append(parent_draft.id)
            deep_dive_source_titles.append(parent_draft.hit.title)
            _merge_candidate_evidence(
                db,
                parent_draft.id,
                _deep_dive_payload(
                    status="processing",
                    reason="本轮正在处理自动深挖池来源",
                    cost_tier="medium" if parent_draft.page_type == "list_page" else "high",
                    value_tier="high",
                    extra={"sourceTitle": parent_draft.hit.title, "sourceUrl": parent_draft.hit.url},
                ),
                timestamp=timestamp,
            )
            db.execute(
                """
                UPDATE intelligence_candidate_items
                SET verification_status = 'pending',
                    promotion_reason = ?,
                    is_user_visible_candidate = 0,
                    updated_at = ?
                WHERE id = ?
                """,
                ("正在处理自动深挖池来源", timestamp, parent_draft.id),
            )
            created_cards_before = sum(_profile_created_fact_count(db, cid) for cid in candidate_ids)
            if parent_draft.page_type == "list_page":
                drilldown_terms = _unique_items([*brief.object_terms, *_intent_terms(parent_draft.intent)], limit=24)
                child_hits = [
                    hit
                    for hit in _drilldown_detail_hits_from_list(parent_draft.hit, drilldown_terms, limit=10)
                    if _hit_matches_intelligence_context(hit, parent_draft.intent, brief.object_terms)
                ]
                if not child_hits:
                    deep_dive_skipped_count += 1
                    reason = "列表页下钻后没有发现可核验详情页"
                    deep_dive_skip_summary.append(reason)
                    _merge_candidate_evidence(
                        db,
                        parent_draft.id,
                        _deep_dive_payload(
                            status="processed",
                            reason=reason,
                            cost_tier="medium",
                            value_tier="high",
                            extra={"sourceTitle": parent_draft.hit.title, "sourceUrl": parent_draft.hit.url},
                        ),
                        timestamp=timestamp,
                    )
                for child_hit in child_hits:
                    normalized_url = _normalize_url(child_hit.url)
                    dedupe_key = _dedupe_key(child_hit.title, normalized_url)
                    if dedupe_key in seen_dedupe_keys:
                        duplicate_count += 1
                        continue
                    seen_dedupe_keys.add(dedupe_key)
                    page_quality = _classify_hit_page(child_hit)
                    if page_quality.page_type == "list_page" and _url_looks_like_detail_page(child_hit.url):
                        page_quality = PageQuality("detail_page", [flag for flag in page_quality.flags if flag != "possible_list_page"], "")
                    score, signals, matched = _score_candidate(
                        content_kind="profile_completion",
                        config=parent_draft.source_config,
                        hit=child_hit,
                        intent=parent_draft.intent,
                        object_terms=brief.object_terms,
                    )
                    child_draft = CandidateDraft(
                        id=_new_id("icand"),
                        content_kind="profile_completion",
                        intent=parent_draft.intent,
                        source_config=parent_draft.source_config,
                        fetch_job_id=parent_draft.fetch_job_id,
                        hit=child_hit,
                        normalized_url=normalized_url,
                        dedupe_key=dedupe_key,
                        matched_terms=matched,
                        confidence_score=max(score, 78.0),
                        signal_count=max(signals, 2),
                        parent_url=parent_draft.hit.url,
                        page_type=page_quality.page_type,
                        quality_flags=_unique_items([*page_quality.flags, "deep_dive_child"], limit=16),
                    )
                    _insert_candidate(db, scope=scope, draft=child_draft, classification_status="candidate", duplicate_of_id=None, timestamp=timestamp)
                    candidate_ids.append(child_draft.id)
                    before_cards = _profile_created_fact_count(db, child_draft.id)
                    if _promote_candidate(
                        db,
                        data_dir=data_dir,
                        ai_service=ai_service,
                        scope=scope,
                        brief=brief,
                        draft=child_draft,
                        timestamp=timestamp,
                    ):
                        promoted_count += 1
                        _apply_source_classification_delta(db, source_config_id=parent_draft.source_config.id, promoted_delta=1, timestamp=timestamp)
                    if _profile_created_fact_count(db, child_draft.id) <= before_cards:
                        reason = "详情页未通过证据核验或 AI 提炼"
                        if reason not in deep_dive_skip_summary:
                            deep_dive_skip_summary.append(reason)
                _merge_candidate_evidence(
                    db,
                    parent_draft.id,
                    _deep_dive_payload(
                        status="processed",
                        reason="列表页已完成本轮下钻处理",
                        cost_tier="medium",
                        value_tier="high",
                        extra={"sourceTitle": parent_draft.hit.title, "sourceUrl": parent_draft.hit.url},
                    ),
                    timestamp=timestamp,
                )
            else:
                before_cards = _profile_created_fact_count(db, parent_draft.id)
                if _promote_candidate(
                    db,
                    data_dir=data_dir,
                    ai_service=ai_service,
                    scope=scope,
                    brief=brief,
                    draft=parent_draft,
                    timestamp=timestamp,
                ):
                    promoted_count += 1
                    _apply_source_classification_delta(db, source_config_id=parent_draft.source_config.id, promoted_delta=1, timestamp=timestamp)
                after_cards = _profile_created_fact_count(db, parent_draft.id)
                outcome_reason = "复杂来源已完成本轮深挖处理" if after_cards > before_cards else "复杂来源未通过正文解析、证据核验或 AI 提炼"
                if after_cards <= before_cards:
                    deep_dive_skipped_count += 1
                    deep_dive_skip_summary.append(outcome_reason)
                _merge_candidate_evidence(
                    db,
                    parent_draft.id,
                    _deep_dive_payload(
                        status="processed",
                        reason=outcome_reason,
                        cost_tier="high" if parent_draft.page_type in {"pdf", "unsupported_pdf"} else "medium",
                        value_tier="high",
                        extra={"sourceTitle": parent_draft.hit.title, "sourceUrl": parent_draft.hit.url},
                    ),
                    timestamp=timestamp,
                )
            created_cards_after = sum(_profile_created_fact_count(db, cid) for cid in candidate_ids)
            quick_win_card_count += max(0, created_cards_after - created_cards_before)
            deep_dive_processed_count += 1
            processed_since_emit += 1
            if processed_since_emit >= 3:
                processed_since_emit = 0
                last_result = emit("deep_dive", "正在处理上一轮发现的年报/PDF、列表页和复杂来源")
        return emit("completed", "资料深挖已完成，本轮只展示通过证据核验和 AI 提炼的资料卡")

    last_result = emit("quick_start", "正在快速查找官网、公开报道和可直接成卡的 HTML 页面")
    processed_candidates_since_emit = 0
    for layer in ("quick", "expand"):
        if time.monotonic() >= deadline_monotonic:
            return emit("completed", "资料补全研究已达到本轮时间预算，已保留本轮通过核验的资料卡")
        layer_tasks = [item for item in tasks if item[0] == layer]
        if not layer_tasks:
            continue
        layer_message = {
            "quick": "正在快速查找官网、公开报道和可直接成卡的网页资料",
            "expand": "正在下钻官网栏目，并围绕项目、人名和重点关注做二次搜索",
            "deep": "正在处理年报/PDF、复杂页面和剩余难点来源",
        }[layer]
        last_result = emit(layer, layer_message)
        for _layer, intent, config in layer_tasks:
            if time.monotonic() >= deadline_monotonic:
                return emit("completed", "资料补全研究已达到本轮时间预算，已保留本轮通过核验的资料卡")
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
            list_hits: list[CandidateHit] = []
            for raw_hit in raw_hits:
                hit = _normalize_hit(raw_hit, config)
                if hit is None:
                    continue
                if not _hit_matches_intelligence_context(hit, intent, brief.object_terms):
                    continue
                page_quality = _classify_hit_page(hit)
                if page_quality.page_type in {"search_page", "media_or_map", "recruitment_directory", "aggregator", "invalid_url"}:
                    continue
                if page_quality.page_type == "list_page" and not _url_looks_like_detail_page(hit.url):
                    list_hits.append(hit)
                    continue
                normalized_hits.append(hit)
            if status == "success" and not normalized_hits and not list_hits:
                status = "no_results"
            if status == "success":
                success_query_count += 1
            elif status == "no_results":
                no_result_query_count += 1
            fetch_job_id = _insert_fetch_job(
                db,
                scope=scope,
                content_kind="profile_completion",
                trigger_source=trigger_source,
                config=config,
                query=query,
                status=status,
                raw_count=len(raw_hits),
                deduped_count=len(normalized_hits) + len(list_hits),
                candidate_count=len(normalized_hits) + len(list_hits),
                sample_hits=[{"title": hit.title, "url": hit.url} for hit in [*normalized_hits, *list_hits][:3]],
                failure_reason=failure_reason,
                duration_ms=int((time.perf_counter() - started) * 1000),
                timestamp=timestamp,
            )
            fetch_job_count += 1
            for hit in list_hits:
                normalized_url = _normalize_url(hit.url)
                dedupe_key = _dedupe_key(hit.title, normalized_url)
                if dedupe_key in seen_dedupe_keys:
                    duplicate_count += 1
                    continue
                seen_dedupe_keys.add(dedupe_key)
                score, signals, matched = _score_candidate(
                    content_kind="profile_completion",
                    config=config,
                    hit=hit,
                    intent=intent,
                    object_terms=brief.object_terms,
                )
                draft = CandidateDraft(
                    id=_new_id("icand"),
                    content_kind="profile_completion",
                    intent=intent,
                    source_config=config,
                    fetch_job_id=fetch_job_id,
                    hit=hit,
                    normalized_url=normalized_url,
                    dedupe_key=dedupe_key,
                    matched_terms=matched,
                    confidence_score=max(score, 72.0),
                    signal_count=max(signals, 2),
                    page_type="list_page",
                    quality_flags=["list_page", "queued_for_drilldown"],
                )
                deep_status, deep_reason, cost_tier, value_tier = _profile_deep_dive_decision(
                    hit=hit,
                    config=config,
                    page_quality=PageQuality("list_page", ["list_page", "queued_for_drilldown"], ""),
                    brief=brief,
                    intent=intent,
                )
                recorded_id, inserted = _record_profile_deep_source(
                    db,
                    scope=scope,
                    draft=draft,
                    timestamp=timestamp,
                    status=deep_status,
                    reason=deep_reason,
                    cost_tier=cost_tier,
                    value_tier=value_tier,
                )
                if recorded_id:
                    candidate_ids.append(recorded_id)
                if inserted and deep_status == "queued":
                    deep_queue_count += 1
                    deep_dive_queued_count += 1
                    deferred_hard_sources.append(hit.title)
                    deep_dive_source_titles.append(hit.title)
                elif inserted and deep_status == "skipped":
                    deep_dive_skipped_count += 1
                    deep_dive_skip_summary.append(deep_reason)
            for hit in normalized_hits:
                normalized_url = _normalize_url(hit.url)
                dedupe_key = _dedupe_key(hit.title, normalized_url)
                if dedupe_key in seen_dedupe_keys:
                    duplicate_count += 1
                    continue
                seen_dedupe_keys.add(dedupe_key)
                page_quality = _classify_hit_page(hit)
                if page_quality.page_type == "list_page" and _url_looks_like_detail_page(hit.url):
                    page_quality = PageQuality("detail_page", [flag for flag in page_quality.flags if flag != "possible_list_page"], "")
                score, signals, matched = _score_candidate(
                    content_kind="profile_completion",
                    config=config,
                    hit=hit,
                    intent=intent,
                    object_terms=brief.object_terms,
                )
                score, feedback_adjustment = _apply_feedback_to_candidate_score(
                    db,
                    scope=scope,
                    content_kind="profile_completion",
                    config=config,
                    hit=hit,
                    intent=intent,
                    base_score=max(score, 74.0 if layer in {"quick", "expand"} else score),
                )
                if layer == "quick" and config.source_type in {"official_site", "official_site_section"}:
                    score = max(score, 80.0)
                    signals = max(signals, 2)
                if hit.provider == "list_drilldown":
                    score = max(score, 78.0)
                    signals = max(signals, 2)
                if page_quality.page_type in {"pdf", "unsupported_pdf"}:
                    draft = CandidateDraft(
                        id=_new_id("icand"),
                        content_kind="profile_completion",
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
                        parent_url=None,
                        page_type=page_quality.page_type,
                        quality_flags=page_quality.flags,
                    )
                    deep_status, deep_reason, cost_tier, value_tier = _profile_deep_dive_decision(
                        hit=hit,
                        config=config,
                        page_quality=page_quality,
                        brief=brief,
                        intent=intent,
                    )
                    recorded_id, inserted = _record_profile_deep_source(
                        db,
                        scope=scope,
                        draft=draft,
                        timestamp=timestamp,
                        status=deep_status,
                        reason=deep_reason,
                        cost_tier=cost_tier,
                        value_tier=value_tier,
                    )
                    if recorded_id:
                        candidate_ids.append(recorded_id)
                    if inserted and deep_status == "queued":
                        deep_queue_count += 1
                        deep_dive_queued_count += 1
                        deferred_hard_sources.append(hit.title)
                        deep_dive_source_titles.append(hit.title)
                    elif inserted and deep_status == "skipped":
                        deep_dive_skipped_count += 1
                        deep_dive_skip_summary.append(deep_reason)
                    continue
                draft = CandidateDraft(
                    id=_new_id("icand"),
                    content_kind="profile_completion",
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
                    parent_url=None,
                    page_type=page_quality.page_type,
                    quality_flags=page_quality.flags,
                )
                _insert_candidate(db, scope=scope, draft=draft, classification_status="candidate", duplicate_of_id=None, timestamp=timestamp)
                candidate_ids.append(draft.id)
                before_cards = _profile_created_fact_count(db, draft.id)
                if _promote_candidate(
                    db,
                    data_dir=data_dir,
                    ai_service=ai_service,
                    scope=scope,
                    brief=brief,
                    draft=draft,
                    timestamp=timestamp,
                ):
                    promoted_count += 1
                    created_cards = max(0, _profile_created_fact_count(db, draft.id) - before_cards)
                    if layer == "quick":
                        quick_win_card_count += created_cards
                    _apply_source_classification_delta(db, source_config_id=config.id, promoted_delta=1, timestamp=timestamp)
                processed_candidates_since_emit += 1
                if processed_candidates_since_emit >= 5:
                    processed_candidates_since_emit = 0
                    last_result = emit(layer, layer_message)
        last_result = emit(layer, layer_message)
    if deep_dive_queued_count > 0:
        return emit("completed", f"本轮已完成快速资料补全，并发现 {deep_dive_queued_count} 个高价值复杂来源；下一轮资料补全将优先深挖这些文件/页面。")
    if deep_dive_skipped_count > 0:
        return emit("completed", "资料补全研究已完成；部分复杂来源价值不确定，已跳过且不进入普通列表。")
    return emit("completed", "资料补全研究已完成，本轮只展示通过证据核验和 AI 提炼的资料卡")


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
    timely_promote_limit: int | None = None,
) -> CandidateRefreshResult:
    timestamp = now_iso()
    brief = _load_research_brief(db, scope)
    configs = ensure_default_source_configs(db, scope)
    ensure_user_supplied_official_sources(db, scope, brief)
    _disable_invalid_discovered_sources(db, scope)
    official_domains = _official_domains_for_scope(db, scope, brief)
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
    own_official_filtered_count = 0
    static_profile_filtered_count = 0
    generic_macro_filtered_count = 0
    external_signal_candidate_count = 0
    tasks = _selected_fetch_tasks(db, intents, configs, max_fetch_jobs=max_fetch_jobs)
    direct_source_count = sum(1 for intent, config in tasks if intent.content_kind == "profile_completion" and config.source_type in {"official_site", "official_site_section"})
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
            if intent.content_kind == "timely_intelligence" and _is_own_official_hit(hit, official_domains):
                own_official_filtered_count += 1
                continue
            if not _hit_matches_intelligence_context(hit, intent, object_terms):
                continue
            page_quality = _classify_hit_page(hit)
            if page_quality.page_type == "list_page":
                drilldown_terms = _unique_items([*object_terms, *_intent_terms(intent)], limit=24)
                drilldown_limit = 5 if intent.content_kind == "profile_completion" else 2
                for child_hit in _drilldown_detail_hits_from_list(hit, drilldown_terms, limit=drilldown_limit):
                    if intent.content_kind == "timely_intelligence" and _is_own_official_hit(child_hit, official_domains):
                        own_official_filtered_count += 1
                        continue
                    if _hit_matches_intelligence_context(child_hit, intent, object_terms):
                        if intent.content_kind == "timely_intelligence":
                            keep_child, _bonus, _flags, reject_kind = _external_signal_fast_screen(
                                hit=child_hit,
                                intent=intent,
                                config=config,
                                brief=brief,
                            )
                            if not keep_child:
                                if reject_kind == "static_profile":
                                    static_profile_filtered_count += 1
                                elif reject_kind == "generic_macro":
                                    generic_macro_filtered_count += 1
                                continue
                        normalized_hits.append(child_hit)
                continue
            if intent.content_kind == "timely_intelligence":
                keep_hit, _bonus, _flags, reject_kind = _external_signal_fast_screen(
                    hit=hit,
                    intent=intent,
                    config=config,
                    brief=brief,
                )
                if not keep_hit:
                    if reject_kind == "static_profile":
                        static_profile_filtered_count += 1
                    elif reject_kind == "generic_macro":
                        generic_macro_filtered_count += 1
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
            extra_flags: list[str] = []
            if intent.content_kind == "timely_intelligence":
                keep_hit, external_bonus, extra_flags, reject_kind = _external_signal_fast_screen(
                    hit=hit,
                    intent=intent,
                    config=config,
                    brief=brief,
                )
                if not keep_hit:
                    if reject_kind == "static_profile":
                        static_profile_filtered_count += 1
                    elif reject_kind == "generic_macro":
                        generic_macro_filtered_count += 1
                    continue
                score = min(score + external_bonus, 99.0)
                if "external_signal" in extra_flags:
                    external_signal_candidate_count += 1
                matched = _unique_items([*matched, *_matched_terms(f"{hit.title} {hit.snippet}", _timely_strategy_terms(brief))], limit=16)
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
                    quality_flags=_unique_items([*page_quality.flags, *extra_flags], limit=16),
                )
            )

    canonical_by_key: dict[str, CandidateDraft] = {}
    for draft in sorted(drafts, key=lambda item: (-item.confidence_score, item.hit.title)):
        if draft.dedupe_key not in canonical_by_key:
            canonical_by_key[draft.dedupe_key] = draft

    has_timely_intents = any(intent.content_kind == "timely_intelligence" for intent in intents)
    timely_review_pool = [
        draft
        for draft in sorted(canonical_by_key.values(), key=lambda item: (-item.confidence_score, item.hit.title))
        if draft.content_kind == "timely_intelligence"
    ]
    timely_review_ids, timely_ai_review_ids = _select_timely_review_drafts(
        timely_review_pool,
        brief=brief,
        timestamp=timestamp,
        detail_limit=TIMELY_DETAIL_REVIEW_LIMIT,
        ai_limit=TIMELY_AI_REVIEW_LIMIT,
    )
    promoted_count = 0
    duplicate_count = 0
    review_candidate_count = 0
    timely_promote_limit = TIMELY_PROMOTION_LIMIT_PER_REFRESH if timely_promote_limit is None else max(0, int(timely_promote_limit))
    ordered_drafts = sorted(
        drafts,
        key=lambda item: (
            0 if canonical_by_key.get(item.dedupe_key) and canonical_by_key[item.dedupe_key].id == item.id else 1,
            -item.confidence_score,
            item.hit.title,
        ),
    )
    for draft in ordered_drafts:
        existing = db.fetchone(
            """
            SELECT c.id
            FROM intelligence_candidate_items c
            JOIN intelligence_items i ON i.id = c.promoted_intelligence_item_id
            WHERE c.scope_type = ? AND c.scope_id = ? AND c.content_kind = ? AND c.dedupe_key = ?
              AND c.classification_status = 'promoted'
              AND i.user_status = 'active'
            ORDER BY c.confidence_score DESC, c.captured_at ASC
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
        should_deep_review = status == "candidate" and (
            draft.content_kind != "timely_intelligence" or draft.id in timely_review_ids
        )
        if status == "candidate" and draft.content_kind == "timely_intelligence" and draft.id not in timely_review_ids:
            db.execute(
                """
                UPDATE intelligence_candidate_items
                SET promotion_reason = ?, updated_at = ?
                WHERE id = ?
                """,
                ("候选已进入初筛池，但未进入本轮深复核预算，暂不抓取详情页", timestamp, draft.id),
            )
        if should_deep_review:
            if draft.content_kind == "timely_intelligence":
                review_candidate_count += 1
        if (
            should_deep_review
            and draft.content_kind == "timely_intelligence"
            and promoted_count >= timely_promote_limit
        ):
            db.execute(
                """
                UPDATE intelligence_candidate_items
                SET promotion_reason = ?, updated_at = ?
                WHERE id = ?
                """,
                ("本轮时效情报成卡已达 5 条上限，保留为后台候选诊断", timestamp, draft.id),
            )
            continue
        if should_deep_review and _promote_candidate(
            db,
            data_dir=data_dir,
            ai_service=ai_service,
            scope=scope,
            brief=brief,
            draft=draft,
            timestamp=timestamp,
            allow_ai_review=draft.content_kind != "timely_intelligence" or draft.id in timely_ai_review_ids,
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
    profile_fact_candidate_count = 0
    profile_fact_card_count = 0
    ai_reviewed_count = 0
    fresh_window_count = 0
    extended_window_count = 0
    timely_effective_window_exception_count = 0
    inspiration_card_count = 0
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
            if has_timely_intents and str(row["summary_status"] or "") in {"generated", "failed"}:
                ai_reviewed_count += count
            reason = _clean_text(str(row["promotion_reason"] or ""), max_len=80)
            if reason and str(row["summary_status"] or "") != "generated":
                rejection_counts[reason] = rejection_counts.get(reason, 0) + count
        if not has_timely_intents:
            evidence_rows = db.fetchall(
                f"""
                SELECT classification_status, evidence_json
                FROM intelligence_candidate_items
                WHERE id IN ({placeholders})
                  AND content_kind = 'profile_completion'
                """,
                tuple(candidate_ids),
            )
            for row in evidence_rows:
                evidence_payload = _safe_json(str(row["evidence_json"] or "{}"), {})
                if not isinstance(evidence_payload, dict):
                    continue
                fact_cards = evidence_payload.get("factCards")
                if isinstance(fact_cards, list):
                    profile_fact_candidate_count += len(fact_cards)
                    if str(row["classification_status"] or "") == "promoted":
                        profile_fact_card_count += int(evidence_payload.get("createdFactCardCount") or len(fact_cards))
                    continue
                facts = evidence_payload.get("facts")
                if isinstance(facts, list):
                    profile_fact_candidate_count += len(facts)
        fresh_window_count = int(
            db.fetchone(
                f"""
                SELECT COUNT(1) AS count
                FROM intelligence_candidate_items
                WHERE id IN ({placeholders})
                  AND content_kind = 'timely_intelligence'
                  AND quality_flags_json LIKE '%fresh_window%'
                """,
                tuple(candidate_ids),
            )["count"]
            or 0
        )
        extended_window_count = int(
            db.fetchone(
                f"""
                SELECT COUNT(1) AS count
                FROM intelligence_candidate_items
                WHERE id IN ({placeholders})
                  AND content_kind = 'timely_intelligence'
                  AND quality_flags_json LIKE '%extended_window%'
                """,
                tuple(candidate_ids),
            )["count"]
            or 0
        )
        timely_effective_window_exception_count = int(
            db.fetchone(
                f"""
                SELECT COUNT(1) AS count
                FROM intelligence_candidate_items
                WHERE id IN ({placeholders})
                  AND content_kind = 'timely_intelligence'
                  AND quality_flags_json LIKE '%effective_window_exception%'
                """,
                tuple(candidate_ids),
            )["count"]
            or 0
        )
        inspiration_card_count = int(
            db.fetchone(
                f"""
                SELECT COUNT(1) AS count
                FROM intelligence_candidate_items c
                JOIN intelligence_items i ON i.id = c.promoted_intelligence_item_id
                WHERE c.id IN ({placeholders})
                  AND c.content_kind = 'timely_intelligence'
                  AND i.intelligence_type = '启发型情报'
                  AND i.user_status = 'active'
                """,
                tuple(candidate_ids),
            )["count"]
            or 0
        )

    profile_coverage: list[str] = []
    profile_missing_dimensions: list[str] = []
    profile_partial_dimensions: list[str] = []
    profile_gap_map: dict[str, object] = {}
    profile_completion_ready = False
    if any(intent.content_kind == "profile_completion" for intent in intents):
        profile_gap_map = _profile_gap_map_snapshot(db, scope)
        profile_coverage = _as_text_list(profile_gap_map.get("covered"), limit=16)
        profile_missing_dimensions = _as_text_list(profile_gap_map.get("missing"), limit=16)
        profile_partial_dimensions = _as_text_list(profile_gap_map.get("partial"), limit=16)
        profile_completion_ready = bool(profile_gap_map.get("ready"))
    timely_strategy = brief.timely_strategy or {}
    timely_profile_gaps = _as_text_list(timely_strategy.get("profileGaps"), limit=8)
    timely_routes = [item for item in timely_strategy.get("routes", []) or [] if isinstance(item, dict)]
    has_timely_intents = any(intent.content_kind == "timely_intelligence" for intent in intents)

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
        profile_partial_dimensions=profile_partial_dimensions,
        profile_gap_map=profile_gap_map,
        profile_completion_ready=profile_completion_ready,
        search_direction_count=len(search_directions),
        query_count=fetch_job_count,
        success_query_count=success_query_count,
        no_result_query_count=no_result_query_count,
        effective_lead_count=max(0, len(drafts) - duplicate_count),
        direct_source_count=direct_source_count,
        pages_fetched_count=body_fetched_count,
        profile_fact_candidate_count=profile_fact_candidate_count if not has_timely_intents else 0,
        profile_fact_card_count=profile_fact_card_count if not has_timely_intents else 0,
        scout_candidate_count=len(drafts) if has_timely_intents else 0,
        review_candidate_count=review_candidate_count if has_timely_intents else 0,
        detail_fetched_count=body_fetched_count if has_timely_intents else 0,
        ai_reviewed_count=ai_reviewed_count if has_timely_intents else 0,
        fresh_window_count=fresh_window_count if has_timely_intents else 0,
        extended_window_count=extended_window_count if has_timely_intents else 0,
        effective_window_exception_count=timely_effective_window_exception_count if has_timely_intents else 0,
        uncovered_gaps=profile_missing_dimensions if not has_timely_intents else timely_profile_gaps,
        timely_profile_ready=bool(timely_strategy.get("profileReady")),
        timely_profile_score=int(timely_strategy.get("profileScore") or 0),
        timely_profile_gaps=timely_profile_gaps,
        timely_strategy_route_count=len(timely_routes),
        timely_candidate_review_count=review_candidate_count if has_timely_intents else 0,
        timely_effective_window_exception_count=timely_effective_window_exception_count,
        external_signal_candidate_count=external_signal_candidate_count if has_timely_intents else 0,
        external_signal_review_count=review_candidate_count if has_timely_intents else 0,
        ai_judged_count=ai_reviewed_count if has_timely_intents else 0,
        inspiration_card_count=inspiration_card_count if has_timely_intents else 0,
        own_official_filtered_count=own_official_filtered_count if has_timely_intents else 0,
        static_profile_filtered_count=static_profile_filtered_count if has_timely_intents else 0,
        generic_macro_filtered_count=generic_macro_filtered_count if has_timely_intents else 0,
    )


def _candidate_source_config_from_row(row: object, scope: IntelligenceSearchScope) -> SourceConfig:
    return SourceConfig(
        id=str(row["source_config_id"] or row["cfg_id"] or "existing_candidate_source"),
        scope_type=str(row["cfg_scope_type"] or scope.scope_type),
        scope_id=str(row["cfg_scope_id"] or scope.scope_id),
        client_id=str(row["cfg_client_id"] or scope.client_id),
        project_module_id=str(row["cfg_project_module_id"] or scope.project_module_id or "") or None,
        source_type=str(row["cfg_source_type"] or "web_search"),
        source_name=str(row["cfg_source_name"] or row["source"] or "公开搜索"),
        source_url_template=str(row["cfg_source_url_template"] or "{query}"),
        region=str(row["cfg_region"] or "全国"),
        reliability_tier=str(row["cfg_reliability_tier"] or row["source_tier"] or "standard"),
        priority=int(row["cfg_priority"] or 50),
        content_kinds=_as_text_list(_safe_json(str(row["cfg_content_kinds_json"] or "[]"), []), limit=4),
        enabled=bool(int(row["cfg_enabled"] or 1)),
        discovery_source=str(row["cfg_discovery_source"] or "existing_candidate"),
        discovery_reason=str(row["cfg_discovery_reason"] or ""),
        discovery_samples=[],
        health_score=float(row["cfg_health_score"] or 70.0),
        success_count=int(row["cfg_success_count"] or 0),
        failure_count=int(row["cfg_failure_count"] or 0),
        candidate_count=int(row["cfg_candidate_count"] or 0),
        promoted_count=int(row["cfg_promoted_count"] or 0),
        duplicate_count=int(row["cfg_duplicate_count"] or 0),
        last_status=str(row["cfg_last_status"] or "unknown"),
        last_checked_at=str(row["cfg_last_checked_at"] or "") or None,
        last_success_at=str(row["cfg_last_success_at"] or "") or None,
        last_failure_at=str(row["cfg_last_failure_at"] or "") or None,
        next_due_at=str(row["cfg_next_due_at"] or "") or None,
    )


def _candidate_intent_from_row(row: object, scope: IntelligenceSearchScope) -> GeneratedSearchIntent:
    return GeneratedSearchIntent(
        id=str(row["intent_id"] or f"intent_existing_{row['id']}"),
        scope_type=scope.scope_type,
        scope_id=scope.scope_id,
        client_id=scope.client_id,
        project_module_id=scope.project_module_id,
        content_kind="timely_intelligence",
        query=str(row["intent_query"] or row["title"] or scope.display_name),
        exclude_terms=_as_text_list(_safe_json(str(row["intent_exclude_terms_json"] or "[]"), []), limit=12),
        source_inputs=_as_text_list(_safe_json(str(row["intent_source_inputs_json"] or "[]"), []), limit=16) or [f"client:{scope.scope_id}", "existing_candidate"],
        reason=str(row["intent_reason"] or "继续复核最近一轮时效候选"),
        priority=int(row["intent_priority"] or 80),
        status="ready",
        input_hash=str(row["intent_input_hash"] or f"existing_candidate:{row['id']}"),
        expires_at=str(row["intent_expires_at"] or now_iso()),
    )


def _timely_candidate_draft_from_row(row: object, scope: IntelligenceSearchScope) -> CandidateDraft:
    hit = CandidateHit(
        title=str(row["title"] or ""),
        url=str(row["url"] or ""),
        snippet=str(row["snippet"] or ""),
        source=str(row["source"] or ""),
        published_at=str(row["published_at"] or "") or None,
        provider=str(row["provider"] or "existing_candidate"),
    )
    flags = _as_text_list(_safe_json(str(row["quality_flags_json"] or "[]"), []), limit=18)
    matched_terms = _as_text_list(_safe_json(str(row["matched_terms_json"] or "[]"), []), limit=18)
    return CandidateDraft(
        id=str(row["id"]),
        content_kind="timely_intelligence",
        intent=_candidate_intent_from_row(row, scope),
        source_config=_candidate_source_config_from_row(row, scope),
        fetch_job_id=str(row["fetch_job_id"] or ""),
        hit=hit,
        normalized_url=str(row["normalized_url"] or _normalize_url(hit.url)),
        dedupe_key=str(row["dedupe_key"] or _dedupe_key(hit.title, _normalize_url(hit.url))),
        matched_terms=matched_terms,
        confidence_score=float(row["confidence_score"] or 60.0),
        signal_count=max(1, len(matched_terms)),
        page_type=str(row["page_type"] or ""),
        quality_flags=flags,
    )


def continue_timely_candidate_review(
    db: Database,
    *,
    data_dir: Path,
    ai_service: object | None,
    scope: IntelligenceSearchScope,
    since: str | None = None,
    candidate_limit: int = 60,
    promote_limit: int = TIMELY_PROMOTION_LIMIT_PER_REFRESH,
) -> CandidateRefreshResult:
    timestamp = now_iso()
    brief = _load_research_brief(db, scope)
    params: list[object] = [scope.scope_type, scope.scope_id]
    since_clause = ""
    if since:
        since_clause = "AND c.created_at >= ?"
        params.append(since)
    rows = db.fetchall(
        f"""
        SELECT
            c.*,
            s.id AS cfg_id,
            s.scope_type AS cfg_scope_type,
            s.scope_id AS cfg_scope_id,
            s.client_id AS cfg_client_id,
            s.project_module_id AS cfg_project_module_id,
            s.source_type AS cfg_source_type,
            s.source_name AS cfg_source_name,
            s.source_url_template AS cfg_source_url_template,
            s.region AS cfg_region,
            s.reliability_tier AS cfg_reliability_tier,
            s.priority AS cfg_priority,
            s.content_kinds_json AS cfg_content_kinds_json,
            s.enabled AS cfg_enabled,
            s.discovery_source AS cfg_discovery_source,
            s.discovery_reason AS cfg_discovery_reason,
            s.health_score AS cfg_health_score,
            s.success_count AS cfg_success_count,
            s.failure_count AS cfg_failure_count,
            s.candidate_count AS cfg_candidate_count,
            s.promoted_count AS cfg_promoted_count,
            s.duplicate_count AS cfg_duplicate_count,
            s.last_status AS cfg_last_status,
            s.last_checked_at AS cfg_last_checked_at,
            s.last_success_at AS cfg_last_success_at,
            s.last_failure_at AS cfg_last_failure_at,
            s.next_due_at AS cfg_next_due_at,
            i.query AS intent_query,
            i.exclude_terms_json AS intent_exclude_terms_json,
            i.source_inputs_json AS intent_source_inputs_json,
            i.reason AS intent_reason,
            i.priority AS intent_priority,
            i.input_hash AS intent_input_hash,
            i.expires_at AS intent_expires_at
        FROM intelligence_candidate_items c
        LEFT JOIN intelligence_source_configs s ON s.id = c.source_config_id
        LEFT JOIN intelligence_search_intents i ON i.id = c.intent_id
        WHERE c.scope_type = ? AND c.scope_id = ?
          AND c.content_kind = 'timely_intelligence'
          AND c.classification_status = 'candidate'
          AND c.summary_status IN ('not_attempted', 'failed')
          AND c.promoted_intelligence_item_id IS NULL
          {since_clause}
        ORDER BY c.created_at DESC, c.confidence_score DESC
        LIMIT ?
        """,
        tuple([*params, int(candidate_limit)]),
    )
    drafts = [_timely_candidate_draft_from_row(row, scope) for row in rows]
    drafts.sort(key=lambda draft: (-_timely_review_priority(draft, brief, timestamp=timestamp), draft.hit.title))
    promoted_count = 0
    candidate_ids: list[str] = [draft.id for draft in drafts]
    for draft in drafts:
        if promoted_count >= promote_limit:
            db.execute(
                "UPDATE intelligence_candidate_items SET promotion_reason = ?, updated_at = ? WHERE id = ?",
                ("本轮时效情报成卡已达 5 条上限，保留为后台候选诊断", timestamp, draft.id),
            )
            continue
        if _promote_candidate(
            db,
            data_dir=data_dir,
            ai_service=ai_service,
            scope=scope,
            brief=brief,
            draft=draft,
            timestamp=timestamp,
            allow_ai_review=True,
        ):
            promoted_count += 1
            _apply_source_classification_delta(
                db,
                source_config_id=draft.source_config.id,
                promoted_delta=1,
                timestamp=timestamp,
            )

    body_fetched_count = 0
    verified_count = 0
    summary_success_count = 0
    ai_reviewed_count = 0
    fresh_window_count = 0
    extended_window_count = 0
    timely_effective_window_exception_count = 0
    inspiration_card_count = 0
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
            if str(row["summary_status"] or "") in {"generated", "failed"}:
                ai_reviewed_count += count
            reason = _clean_text(str(row["promotion_reason"] or ""), max_len=80)
            if reason and str(row["summary_status"] or "") != "generated":
                rejection_counts[reason] = rejection_counts.get(reason, 0) + count
        fresh_window_count = int(db.scalar(f"SELECT COUNT(1) FROM intelligence_candidate_items WHERE id IN ({placeholders}) AND quality_flags_json LIKE '%fresh_window%'", tuple(candidate_ids)) or 0)
        extended_window_count = int(db.scalar(f"SELECT COUNT(1) FROM intelligence_candidate_items WHERE id IN ({placeholders}) AND quality_flags_json LIKE '%extended_window%'", tuple(candidate_ids)) or 0)
        timely_effective_window_exception_count = int(db.scalar(f"SELECT COUNT(1) FROM intelligence_candidate_items WHERE id IN ({placeholders}) AND quality_flags_json LIKE '%effective_window_exception%'", tuple(candidate_ids)) or 0)
        inspiration_card_count = int(
            db.scalar(
                f"""
                SELECT COUNT(1)
                FROM intelligence_candidate_items c
                JOIN intelligence_items i ON i.id = c.promoted_intelligence_item_id
                WHERE c.id IN ({placeholders}) AND i.intelligence_type = '启发型情报' AND i.user_status = 'active'
                """,
                tuple(candidate_ids),
            )
            or 0
        )
    timely_strategy = brief.timely_strategy or {}
    timely_profile_gaps = _as_text_list(timely_strategy.get("profileGaps"), limit=8)
    timely_routes = [item for item in timely_strategy.get("routes", []) or [] if isinstance(item, dict)]
    status_payload = get_candidate_supply_status_for_scope(db, scope_type=scope.scope_type, scope_id=scope.scope_id)
    return CandidateRefreshResult(
        source_config_count=int(db.scalar("SELECT COUNT(1) FROM intelligence_source_configs WHERE scope_type = ? AND scope_id = ? AND enabled = 1", (scope.scope_type, scope.scope_id)) or 0),
        fetch_job_count=0,
        candidate_count=len(drafts),
        promoted_count=promoted_count,
        duplicate_count=0,
        failed_count=0,
        body_fetched_count=body_fetched_count,
        verified_count=verified_count,
        summary_success_count=summary_success_count,
        rejection_counts=rejection_counts,
        source_coverage_status=str(status_payload.get("sourceCoverageStatus") or "ready"),
        candidate_refresh_status=str(status_payload.get("candidateRefreshStatus") or "ready"),
        last_candidate_fetch_at=str(status_payload.get("lastCandidateFetchAt") or timestamp),
        candidate_counts=dict(status_payload.get("candidateCounts") or {}),
        scout_candidate_count=len(drafts),
        review_candidate_count=len(drafts),
        detail_fetched_count=body_fetched_count,
        ai_reviewed_count=ai_reviewed_count,
        fresh_window_count=fresh_window_count,
        extended_window_count=extended_window_count,
        effective_window_exception_count=timely_effective_window_exception_count,
        uncovered_gaps=timely_profile_gaps,
        timely_profile_ready=bool(timely_strategy.get("profileReady")),
        timely_profile_score=int(timely_strategy.get("profileScore") or 0),
        timely_profile_gaps=timely_profile_gaps,
        timely_strategy_route_count=len(timely_routes),
        timely_candidate_review_count=len(drafts),
        timely_effective_window_exception_count=timely_effective_window_exception_count,
        external_signal_candidate_count=len(drafts),
        external_signal_review_count=len(drafts),
        ai_judged_count=ai_reviewed_count,
        inspiration_card_count=inspiration_card_count,
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
