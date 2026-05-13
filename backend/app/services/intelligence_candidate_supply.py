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
from urllib.parse import urlparse, urlunparse

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
STRONG_SOURCE_TYPES = {"gov_policy", "procurement", "grant", "social_org_registry", "official_site"}
PROFILE_SOURCE_TYPES = {"web_search", "official_site", "social_org_registry", "charity_media"}
TIMELY_SOURCE_TYPES = {"web_search", "gov_policy", "procurement", "grant", "charity_media"}
CONTENT_KIND_SOURCE_TYPES = {
    "profile_completion": PROFILE_SOURCE_TYPES,
    "timely_intelligence": TIMELY_SOURCE_TYPES,
}
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
    "企查查",
    "天眼查",
}


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
            "priority": 100,
            "content_kinds": ["profile_completion", "timely_intelligence"],
            "reason": "默认通用搜索兜底。",
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
            "template": f"{region_prefix}" + "{query} 资助 申报 基金会 通知",
            "tier": "strong",
            "priority": 94,
            "content_kinds": ["timely_intelligence"],
            "reason": "时效情报优先覆盖资助与申报窗口。",
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
            "source_type": "charity_media",
            "source_name": "公益行业公开报道",
            "template": "{query} 公益 慈善 项目 报道",
            "tier": "standard",
            "priority": 90,
            "content_kinds": ["profile_completion", "timely_intelligence"],
            "reason": "覆盖公益行业媒体、公开报道和案例线索。",
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
    if normalized_url:
        return hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()[:32]
    return _title_key(title)


def _effective_query(intent: GeneratedSearchIntent, config: SourceConfig) -> str:
    region_prefix = "" if config.region == "全国" else f"{config.region} "
    template = config.source_url_template or "{query}"
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


def _domain_label(url: str) -> str:
    domain = urlparse(url).netloc.lower().removeprefix("www.")
    return domain or "公开网页"


def _fetch_public_search_hits(query: str, config: SourceConfig, *, timeout_seconds: float = 8.0) -> list[CandidateHit]:
    hits: list[CandidateHit] = []
    for item in search_public_web(query, max_results=5, timeout_seconds=timeout_seconds):
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


def _domain_matches(domain: str, blocked: set[str]) -> bool:
    normalized = domain.lower().removeprefix("www.")
    return any(normalized == item or normalized.endswith(f".{item}") for item in blocked)


def _contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def _hit_search_text(hit: CandidateHit) -> str:
    domain = urlparse(hit.url).netloc.lower().removeprefix("www.")
    return f"{hit.title} {hit.snippet} {hit.source} {domain}"


def _hit_is_closed_or_low_value(hit: CandidateHit) -> bool:
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
    marker_count = sum(1 for marker in code_markers if marker in text.lower())
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    if marker_count >= 3 and cjk_count < 120:
        return "script_noise", text[:800], "正文包含脚本、地图或搜索页噪音，无法可靠核验"
    return "fetched", text[:8000], ""


def _map_profile_tags(intent: GeneratedSearchIntent, hit: CandidateHit, body_text: str, positive_rules: list[str]) -> list[str]:
    corpus = f"{intent.reason} {intent.query} {hit.title} {hit.snippet} {body_text[:1200]}"
    candidates: list[tuple[str, tuple[str, ...]]] = [
        ("登记信息", ("登记", "注册", "统一社会信用代码", "社会组织")),
        ("年报/信息公开", ("年报", "信息公开", "年度报告")),
        ("服务对象规模", ("服务对象", "受益", "人数", "规模")),
        ("项目成效", ("成效", "成果", "影响", "案例")),
        ("合作方", ("合作", "伙伴", "资助方", "支持方")),
        ("执行方法", ("方法", "模式", "路径", "执行")),
        ("公开报告", ("报告", "白皮书", "研究")),
        ("机构简介", ("简介", "关于我们", "机构介绍")),
        ("项目介绍", ("项目介绍", "项目概况", "项目背景")),
    ]
    tags = [label for label, keywords in candidates if any(keyword in corpus for keyword in keywords)]
    tags.extend(positive_rules[:4])
    return _unique_items(tags, limit=6)


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


def _build_profile_enrichment(ai_service: object | None, draft: CandidateDraft, body_text: str, mapped_tags: list[str]) -> tuple[str, list[str], str] | None:
    if not _ai_ready(ai_service) or not hasattr(ai_service, "generate_general_fallback"):
        return None
    prompt = "\n".join(
        [
            f"标题：{draft.hit.title}",
            f"来源：{draft.hit.source}",
            f"链接：{draft.hit.url}",
            f"命中搜索意图：{draft.intent.query}",
            f"拟映射标签：{'、'.join(mapped_tags)}",
            f"网页正文摘录：{body_text[:3600]}",
            "请只基于网页正文，生成可进入客户/项目资料库的资料补全摘要，并提炼 2-4 条可复用事实。不要复述搜索短摘，不要夸大核验范围。",
        ]
    )
    try:
        response = ai_service.generate_general_fallback(prompt, "资料补全核验摘要", subject_name=draft.hit.title)
    except Exception:
        return None
    if not isinstance(response, AiStructuredResponse):
        return None
    summary = _clean_text(response.content or response.judgment or "", max_len=500)
    points = _split_summary_points(response.analysis or "", response.actions or "", response.judgment or "", limit=4)
    if not summary:
        return None
    if not points:
        points = _split_summary_points(body_text[:900], limit=3)
    analysis = _clean_text(response.analysis or response.judgment or "", max_len=900)
    return summary, points, analysis


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
        )
        return ProfileVerificationResult(False, "pending", reason, body_status, "not_attempted", body_excerpt=body_excerpt)
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
        )
        return ProfileVerificationResult(False, "pending", reason, "fetched", "not_attempted", body_excerpt=body_excerpt)
    enrichment = _build_profile_enrichment(ai_service, draft, body_text, mapped_tags)
    if enrichment is None:
        reason = "AI 摘要不可用，暂未成卡"
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
        )
        return ProfileVerificationResult(False, "verified", reason, "fetched", "failed", mapped_tags, body_excerpt=body_excerpt)
    summary, points, analysis = enrichment
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
    if not domain or _domain_matches(domain, CLOSED_OR_LOW_VALUE_DOMAINS) or _domain_matches(domain, AGGREGATOR_DOMAINS):
        return 0, "封闭平台、聚合站或低价值域名，不作为官网来源。"
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
) -> float:
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
        intent_id=intent.id,
    )
    return max(1.0, min(98.0, base_score + adjustment * 4))


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
    per_kind_limit = max(1, min(12, (max_fetch_jobs + max(1, len(active_kinds)) - 1) // max(1, len(active_kinds))))
    for content_kind in active_kinds:
        source_types = CONTENT_KIND_SOURCE_TYPES[content_kind]
        kind_intents = sorted(
            [item for item in intents if item.content_kind == content_kind],
            key=lambda item: (-item.priority, item.query),
        )[:4]
        kind_configs = [
            item
            for item in configs
            if item.source_type in source_types and (not item.content_kinds or content_kind in item.content_kinds)
        ]
        kind_configs.sort(key=lambda item: (-_source_priority_score_for_kind(db, item, content_kind=content_kind, timestamp=timestamp), item.source_type))
        kind_task_count = 0
        for intent in kind_intents:
            for config in kind_configs[:4]:
                tasks.append((intent, config))
                kind_task_count += 1
                if len(tasks) >= max_fetch_jobs:
                    return tasks
                if kind_task_count >= per_kind_limit:
                    break
            if kind_task_count >= per_kind_limit:
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
    due_hours = PROFILE_TTL_HOURS if content_kind == "profile_completion" else TIMELY_TTL_HOURS
    success_delta = 1 if status in {"success", "no_results"} else 0
    failure_delta = 1 if status == "failed" else 0
    last_success_at = timestamp if status in {"success", "no_results"} else None
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
            classification_status, promotion_reason, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?)
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


def _timely_intelligence_type(draft: CandidateDraft) -> str | None:
    text = f"{draft.intent.query} {draft.intent.reason} {draft.hit.title} {draft.hit.snippet} {draft.source_config.source_type}"
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


def _is_static_profile_material(draft: CandidateDraft) -> bool:
    text = f"{draft.hit.title} {draft.hit.snippet} {draft.intent.query} {draft.intent.reason}"
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


def _timely_candidate_gate(draft: CandidateDraft) -> tuple[bool, str, str | None]:
    if _is_static_profile_material(draft):
        return False, "静态登记、官网介绍或年报资料应进入资料补全，不进入时效情报", None
    intelligence_type = _timely_intelligence_type(draft)
    if not intelligence_type:
        return False, "未识别出明确情报类型，暂不成卡", None
    text = f"{draft.hit.title} {draft.hit.snippet} {draft.intent.query} {draft.intent.reason}"
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
    if len(draft.hit.snippet or draft.hit.title) < 12:
        return False, "公开信息过短，无法判断发生了什么", None
    return True, "已识别近期外部变化，并具备对象或行业相关信号", intelligence_type


def _build_timely_enrichment(ai_service: object | None, draft: CandidateDraft) -> TimelyEnrichmentResult | None:
    passed, reason, intelligence_type = _timely_candidate_gate(draft)
    if not passed or not intelligence_type:
        draft.hit.snippet = draft.hit.snippet or reason
        return None
    if not _ai_ready(ai_service) or not hasattr(ai_service, "generate_general_fallback"):
        return None
    followups = _timely_followup_questions(draft, intelligence_type)
    prompt = "\n".join(
        [
            f"标题：{draft.hit.title}",
            f"来源：{draft.hit.source}",
            f"摘要：{draft.hit.snippet}",
            f"命中搜索意图：{draft.intent.query}",
            f"情报类型：{intelligence_type}",
            "请只基于标题、短摘和搜索意图，整理为时效情报卡。",
            "必须输出：发生了什么、为什么和当前客户/项目有关、可能影响、建议动作、证据不足点。",
            "建议动作可以是阅读/研判任务，不要强行写成执行任务；不要使用“先确认负责人、再补材料”这类模板空话。",
        ]
    )
    try:
        response = ai_service.generate_general_fallback(prompt, "情报候选自动分流", subject_name=draft.hit.title)
    except Exception:
        return None
    if not isinstance(response, AiStructuredResponse):
        return None
    summary = _clean_text(response.content or draft.hit.snippet or draft.hit.title, max_len=500)
    relevance = _clean_text(response.judgment or response.analysis or "", max_len=700)
    impact = _clean_text(response.analysis or response.timeline or "", max_len=700)
    suggested_action = _clean_text(response.actions or "", max_len=500)
    if not summary or not relevance or not impact or not suggested_action:
        return None
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
            f"- 来源：{draft.hit.source or draft.hit.url}",
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
    draft: CandidateDraft,
    timestamp: str,
) -> bool:
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
        WHERE content_kind = ? AND source_url = ? AND COALESCE(client_id, '') = COALESCE(?, '')
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
        passed, gate_reason, _intelligence_type = _timely_candidate_gate(draft)
        if not passed:
            db.execute(
                "UPDATE intelligence_candidate_items SET promotion_reason = ?, updated_at = ? WHERE id = ?",
                (gate_reason, timestamp, draft.id),
            )
            return False
        if not _ai_ready(ai_service):
            db.execute(
                "UPDATE intelligence_candidate_items SET promotion_reason = ?, updated_at = ? WHERE id = ?",
                ("AI 不可用，时效情报候选暂不自动成卡", timestamp, draft.id),
            )
            return False
        enrichment = _build_timely_enrichment(ai_service, draft)
        if enrichment is None:
            db.execute(
                "UPDATE intelligence_candidate_items SET promotion_reason = ?, updated_at = ? WHERE id = ?",
                ("AI 研判未生成完整结构，暂不自动成卡", timestamp, draft.id),
            )
            return False
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
            draft.hit.source or draft.source_config.source_name,
            draft.hit.url,
            draft.hit.published_at,
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
    max_fetch_jobs: int = 20,
    hit_fetcher: Callable[[str, SourceConfig], list[CandidateHit | dict[str, object]]] | None = None,
    official_site_hit_fetcher: Callable[[str, SourceConfig], list[CandidateHit | dict[str, object]]] | None = None,
) -> CandidateRefreshResult:
    timestamp = now_iso()
    configs = ensure_default_source_configs(db, scope)
    discover_official_site_source_configs(
        db,
        scope=scope,
        hit_fetcher=official_site_hit_fetcher or hit_fetcher,
    )
    configs = ensure_default_source_configs(db, scope)
    object_terms = _object_terms(db, scope)
    fetcher = hit_fetcher or _fetch_public_search_hits
    drafts: list[CandidateDraft] = []
    failed_count = 0
    fetch_job_count = 0
    tasks = _selected_fetch_tasks(db, intents, configs, max_fetch_jobs=max_fetch_jobs)
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
        seen_keys: set[str] = set()
        for raw_hit in raw_hits:
            hit = _normalize_hit(raw_hit, config)
            if hit is None:
                continue
            if not _hit_matches_intelligence_context(hit, intent, object_terms):
                continue
            normalized_url = _normalize_url(hit.url)
            dedupe_key = _dedupe_key(hit.title, normalized_url)
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            normalized_hits.append(hit)
        if status == "success" and not normalized_hits:
            status = "no_results"
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
            score = _apply_feedback_to_candidate_score(
                db,
                scope=scope,
                content_kind=intent.content_kind,
                config=config,
                hit=hit,
                intent=intent,
                base_score=score,
            )
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
