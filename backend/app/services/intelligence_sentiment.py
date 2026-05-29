"""资讯情报站 · 舆情监控 service (P2-a)

定位：
  - 抓取公开渠道（媒体 / 论坛 / 搜索引擎）对客户的提及
  - 用词表+AI 做情感分析（负面 / 中性 / 积极）
  - 重点保留 source_url，让用户能直接跳原文
  - 支持按客户级别 / 业务线级别（project_module_id）过滤

跟资料补全 / 时效情报的关系：
  - 三者共用 intelligence_items 表，靠 content_kind 区分
  - 舆情 items 的 content_kind = 'public_opinion'
  - 30 天滚动保留，超期归档
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from app.db import Database, from_json, to_json
from app.services.public_search import search_public_web

# ──────────────────────────────────────────────────────────────────────────
# 情感词表 — 公益领域专用，AI 介入前的快速判别
# ──────────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────────
# 负面词分两级：硬负面（独立出现就算）+ 软负面（要看上下文）
# ──────────────────────────────────────────────────────────────────────────

# 硬负面词：单独出现就基本能确认是负面舆情
HARD_NEGATIVE_TERMS: tuple[str, ...] = (
    # 重大违法 / 财务问题
    "造假", "虚假", "诈骗", "骗捐", "贪污", "挪用", "侵吞", "截留",
    "丑闻", "黑幕", "腐败", "失联", "跑路", "失信",
    # 信任 / 透明度
    "不透明", "信息不公开", "财务不清", "账目不清",
    # 重大处罚
    "撤销登记", "通报批评", "处罚", "罚款", "立案",
    "失实", "误导",
    # 服务质量负面
    "推诿", "敷衍", "无作为", "效果差", "白搭", "失望",
    # 情绪化负面
    "愤怒", "气愤", "恶心", "失望透顶", "再也不", "再不会",
    # 与 客户名 共现的"被举报/被质疑"也是硬负面（在 analyze_sentiment 里判）
    "被举报", "被质疑", "被处罚", "被罚款", "被起诉", "被立案",
    "款项不知去向", "钱不知道去哪",
)

# 软负面词：在网站页脚里非常常见（"侵权举报""投诉举报"等），单独出现要降级
# 必须配合"硬负面词"或"客户名近邻"共现才算真负面
SOFT_NEGATIVE_TERMS: tuple[str, ...] = (
    "举报", "投诉", "违规", "违法",
    "质疑", "争议", "曝光", "维权", "整改",
)

# 噪声短语：把"举报/投诉/违规"包在网站功能词里，先从文本剔除再分析
# 顺序：长的在前（避免短的先匹配吃掉长的）
NOISE_FOOTER_PHRASES: tuple[str, ...] = (
    # 网站标配 footer
    "违规内容投诉", "不良信息举报", "侵权投诉举报",
    "侵权举报", "投诉举报", "舞弊举报", "举报投诉",
    "举报邮箱", "举报电话", "举报方式", "信息举报",
    # 平台标配
    "微博客服", "微博招聘", "新浪网导航", "网站导航",
    "微信客服", "客户服务", "网站客服",
    # 协议 / 反馈类
    "服务协议", "用户协议", "购前协议", "免责声明",
    "意见反馈", "联系方式", "关于我们", "网站地图",
    # 投诉作为页面分类
    "投诉机构", "举报机构", "投诉中心",
)


# 兼容旧引用：NEGATIVE_TERMS = 硬负面 + 软负面（保持原 import 不破坏）
NEGATIVE_TERMS: tuple[str, ...] = tuple(HARD_NEGATIVE_TERMS) + tuple(SOFT_NEGATIVE_TERMS)

POSITIVE_TERMS: tuple[str, ...] = (
    "点赞", "感谢", "敬佩", "敬意", "敬礼", "辛苦", "厉害",
    "靠谱", "专业", "用心", "公开透明", "高效",
    "推荐", "推广", "支持", "认可", "赞助", "捐赠增长",
    "获奖", "表彰", "嘉奖", "标杆", "示范",
)

NEUTRAL_REPORT_TERMS: tuple[str, ...] = (
    "成立", "发布", "举办", "出席", "签署", "发起",
    "完成", "推进", "实施", "落地", "宣布",
)

# AI 假信号过滤（搜索引擎广告、SEO 垃圾页）
SEO_NOISE_TERMS: tuple[str, ...] = (
    "百度推广", "搜狗推广", "信息流广告", "广告位",
)


# ──────────────────────────────────────────────────────────────────────────
# 数据结构
# ──────────────────────────────────────────────────────────────────────────


@dataclass
class SentimentAnalysisResult:
    """单条 hit 的情感分析结果。"""
    label: str           # 'negative' / 'neutral' / 'positive'
    score: float         # -1.0 ~ 1.0，越负越坏
    confidence: float    # 0.0 ~ 1.0，词表命中越多置信度越高
    matched_terms: list[str]
    reason: str          # 给用户看的"为什么这条被这么判"


@dataclass
class SentimentItemDraft:
    """准备入 intelligence_items 表的舆情条目。"""
    title: str
    summary: str
    source: str          # 来源域名（豆瓣 / 微博 / 公益时报 等）
    source_url: str      # 关键 — 用户能直接点
    sentiment: SentimentAnalysisResult
    captured_at: str
    client_id: str | None = None
    project_module_id: str | None = None
    scope_type: str | None = None
    scope_id: str | None = None


# ──────────────────────────────────────────────────────────────────────────
# 情感分析（词表快判，AI 升级在 P3）
# ──────────────────────────────────────────────────────────────────────────


def _strip_noise_phrases(text: str) -> str:
    """从文本里挖掉"侵权举报""违规内容投诉"等网站标配 footer 短语。

    避免软负面词被这些噪声带跑（例：A组织儿童活动报告页脚有"侵权举报"，
    不应该把这条报告判成负面）。

    按 NOISE_FOOTER_PHRASES 长度倒序剔除，避免短的吃掉长的。
    """
    cleaned = text or ""
    for phrase in sorted(NOISE_FOOTER_PHRASES, key=len, reverse=True):
        cleaned = cleaned.replace(phrase, " ")
    return cleaned


def analyze_sentiment(text: str, *, target_name: str | None = None) -> SentimentAnalysisResult:
    """词表分级 + 噪声剔除的情感分析。

    判定逻辑（2026-05-18 升级，解决A组织案例 4 条全误判为负面的 bug）：
      1. 先剔除 footer 噪声短语（"侵权举报""违规内容投诉"等）
      2. 命中"硬负面词"（造假/挪用/被举报/...） → 直接负面
      3. 只命中"软负面词"（投诉/举报/违规）+ 0 个硬负面 → 降级中性
         理由：这些词在网站 footer 里几乎是标配，单独出现不代表客户真的被负评
      4. 命中积极词且 ≥ 负面词 → 积极
      5. 其他 → 中性

    target_name（客户名）传进来时还会做"客户名 + 负面词近距离共现"判定：
    "韩红 + 被举报" 距离 < 20 字 → 强负面信号
    """
    raw_text = (text or "").strip()
    if not raw_text:
        return SentimentAnalysisResult(
            label="neutral", score=0.0, confidence=0.0,
            matched_terms=[], reason="空文本",
        )

    # 关键步骤：剔除网站 footer 噪声短语后再做词表匹配
    clean_text = _strip_noise_phrases(raw_text)

    hard_neg = [term for term in HARD_NEGATIVE_TERMS if term in clean_text]
    soft_neg = [term for term in SOFT_NEGATIVE_TERMS if term in clean_text]
    pos_hits = [term for term in POSITIVE_TERMS if term in clean_text]

    # 客户名 + 负面词近邻判定（不到 20 字以内出现"X + 软负面词"也算硬负面）
    proximity_neg: list[str] = []
    if target_name:
        target = target_name.strip()
        for term in soft_neg:
            # 找到 target 跟 term 在 clean_text 里所有位置，最小距离 < 25 → 计为强信号
            t_positions = [m.start() for m in re.finditer(re.escape(target), clean_text)]
            term_positions = [m.start() for m in re.finditer(re.escape(term), clean_text)]
            if not t_positions or not term_positions:
                continue
            min_dist = min(abs(tp - kp) for tp in t_positions for kp in term_positions)
            if min_dist < 25:
                proximity_neg.append(f"{target}~{term}")

    # 计分
    hard_neg_count = len(hard_neg)
    soft_neg_count = len(soft_neg)
    proximity_neg_count = len(proximity_neg)
    effective_neg_count = hard_neg_count + proximity_neg_count  # 软负面单独出现不计入"有效负面"
    pos_count = len(pos_hits)

    # 0 信号：中性兜底
    if effective_neg_count == 0 and soft_neg_count == 0 and pos_count == 0:
        return SentimentAnalysisResult(
            label="neutral", score=0.0, confidence=0.3,
            matched_terms=[], reason="未命中情感词（footer 噪声已剔除），默认中性",
        )

    # 只命中软负面，没命中硬负面也不在客户名附近 → 强降级中性
    if effective_neg_count == 0 and soft_neg_count > 0 and pos_count == 0:
        return SentimentAnalysisResult(
            label="neutral", score=-0.1, confidence=0.5,
            matched_terms=soft_neg[:4],
            reason=f"只命中页面通用词「{'、'.join(soft_neg[:3])}」，未与监控对象近距离共现，可能是网站 footer，降为中性",
        )

    # 有效负面 vs 积极
    if effective_neg_count > pos_count:
        score = -min(1.0, 0.4 + effective_neg_count * 0.25)
        matched_for_reason = (hard_neg + proximity_neg)[:3]
        if proximity_neg:
            reason = f"硬负面词 {hard_neg_count} 个 + 监控对象与「{'、'.join(soft_neg[:2])}」近距离共现：{'、'.join(matched_for_reason)}"
        else:
            reason = f"命中 {hard_neg_count} 个硬负面词：{'、'.join(matched_for_reason)}"
        confidence = min(0.95, 0.5 + effective_neg_count * 0.15)
        return SentimentAnalysisResult(
            label="negative", score=score, confidence=confidence,
            matched_terms=(hard_neg + soft_neg)[:8], reason=reason,
        )

    if pos_count > effective_neg_count:
        score = min(1.0, 0.3 + pos_count * 0.2)
        confidence = min(0.9, 0.4 + pos_count * 0.15)
        return SentimentAnalysisResult(
            label="positive", score=score, confidence=confidence,
            matched_terms=pos_hits[:8],
            reason=f"命中 {pos_count} 个积极词：{'、'.join(pos_hits[:3])}",
        )

    # 平局 → 中性
    return SentimentAnalysisResult(
        label="neutral", score=0.0, confidence=0.4,
        matched_terms=(hard_neg + pos_hits)[:6],
        reason=f"负面 {effective_neg_count} 积极 {pos_count}，相互抵消",
    )


# ──────────────────────────────────────────────────────────────────────────
# 抓取流程
# ──────────────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────────────
# 从数据中心拉客户的扩展上下文（别名 / 业务域 / 项目模块）
# ──────────────────────────────────────────────────────────────────────────


def _collect_target_aliases(
    db: Database,
    *,
    client_id: str | None = None,
    project_module_id: str | None = None,
) -> dict[str, Any]:
    """从 clients / project_modules 拉客户的扩展信息，用于扩 query。

    返回示例：
      {
        "primary_name": "A组织",
        "aliases": ["A组织"],          # clients.alias，不同于 name 才计入
        "domain": "儿童心理",          # clients.domain
        "project_modules": ["心灵魔法学院", "..."],  # 客户名下激活的模块名
      }

    NOTE：刻意没拉 entities 表的 person，因为 entity 抽取目前质量太差
    （"施工"被识别成 person，"高老师"是内部员工而非创始人）。
    关键人物等高敏感扩展词应该让用户在 focus_directives UI 手动配。
    """
    result: dict[str, Any] = {
        "primary_name": "",
        "aliases": [],
        "domain": "",
        "project_modules": [],
    }
    if not client_id and not project_module_id:
        return result

    # 1) clients
    if client_id:
        client_row = db.fetchone(
            "SELECT name, alias, domain FROM clients WHERE id = ?",
            (client_id,),
        )
        if client_row:
            name = str(client_row["name"] or "").strip()
            alias = str(client_row["alias"] or "").strip()
            domain = str(client_row["domain"] or "").strip()
            result["primary_name"] = name
            if alias and alias != name and len(alias) >= 2:
                result["aliases"].append(alias)
            if domain and len(domain) >= 2:
                result["domain"] = domain

    # 2) project_modules（只取该客户的激活模块名）
    if client_id:
        try:
            pm_rows = db.fetchall(
                """
                SELECT name FROM project_modules
                WHERE client_id = ?
                ORDER BY updated_at DESC
                LIMIT 5
                """,
                (client_id,),
            )
            result["project_modules"] = [
                str(r["name"]) for r in pm_rows if r["name"] and len(str(r["name"]).strip()) >= 2
            ]
        except Exception:  # noqa: BLE001
            pass  # 表不存在 / 字段不存在时不阻塞

    return result


def build_search_queries(
    target_name: str,
    *,
    business_line: str | None = None,
    aliases: list[str] | None = None,
    domain: str | None = None,
    project_modules: list[str] | None = None,
    include_social_sites: bool = True,
) -> list[str]:
    """生成舆情专用搜索 query 矩阵。

    扩展维度：
      1. 主名 + 评价 / 怎么样 / 报道 / 投诉
      2. 别名 + 评价 / 怎么样     （客户 alias 跑一遍）
      3. 业务域辅助           （如 "A组织 儿童心理"）
      4. site: 限定 UGC 平台   （微博/知乎/豆瓣/小红书 各一组）
      5. 业务线 / 项目模块共现 （如 "A组织 心灵魔法学院 评价"）
    """
    if not target_name or not target_name.strip():
        return []
    target = target_name.strip()
    queries: list[str] = []
    seen: set[str] = set()

    def _add(q: str) -> None:
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            queries.append(q)

    # 1) 主名基础 query
    _add(f"{target} 评价")
    _add(f"{target} 怎么样")
    _add(f"{target} 报道")
    _add(f"{target} 投诉 OR 质疑 OR 曝光")

    # 2) 别名（不同于主名的）跑一遍 — 但只跑高价值的"评价/怎么样"
    for alias in (aliases or []):
        alias = (alias or "").strip()
        if not alias or alias == target:
            continue
        _add(f"{alias} 评价")
        _add(f"{alias} 怎么样")

    # 3) 业务域辅助（让搜索引擎理解客户所在领域）
    if domain and domain.strip():
        _add(f"{target} {domain.strip()}")

    # 4) UGC 平台 site 限定 — 通过搜索引擎曲线召回小红书/微博/知乎/豆瓣公开内容
    #    （直接抓 UGC 平台要破反爬，先用搜索引擎已索引的公开页面做兜底）
    if include_social_sites:
        for site in ("xiaohongshu.com", "weibo.com", "zhihu.com", "douban.com"):
            _add(f"{target} site:{site}")

    # 5) 业务线 / 项目模块共现
    if business_line and business_line.strip():
        _add(f"{target} {business_line.strip()}")
    for module_name in (project_modules or [])[:3]:  # 防止 query 矩阵爆炸，最多 3 个模块
        module_name = (module_name or "").strip()
        if module_name and module_name != target:
            _add(f"{target} {module_name}")

    return queries


def _build_target_tokens(target_name: str, aliases: list[str] | None) -> list[str]:
    """生成目标判定 token：完整名 + 别名 + 主名的去常见后缀版本。

    例：target_name = "A组织"，aliases=["A组织"]
        → ["A组织", "A组织"]  （"A组织" 来自 alias，主名去掉"基金会"后等于 alias，去重）

    例：target_name = "益语智库"，aliases=[]
        → ["益语智库", "益语"]    （去掉"智库"得到的短名作为兜底）

    最少要求：每个 token 长度 >= 2，避免单字误匹配。
    """
    out: list[str] = []
    seen: set[str] = set()

    def _add(s: str) -> None:
        s = (s or "").strip()
        if not s or len(s) < 2:
            return
        if s in seen:
            return
        seen.add(s)
        out.append(s)

    target = (target_name or "").strip()
    _add(target)

    for alias in aliases or []:
        _add(alias)

    # 主名截尾：A组织 → A组织；益语智库 → 益语
    # 慎用：如果剪完只剩 1 字就放弃
    SUFFIXES = ("基金会", "公益基金会", "公益", "智库", "实验室", "中心", "研究院", "集团", "公司")
    for suffix in SUFFIXES:
        if target.endswith(suffix) and len(target) > len(suffix) + 1:
            _add(target[: -len(suffix)])
            break

    return out


def _is_low_value_hit(title: str, snippet: str, url: str) -> bool:
    """跳过明显无用的搜索结果（SEO 垃圾、自家官网首页等）。"""
    text = f"{title} {snippet}"
    if any(term in text for term in SEO_NOISE_TERMS):
        return True
    if not url:
        return True
    return False


def fetch_sentiment_candidates(
    target_name: str,
    *,
    business_line: str | None = None,
    aliases: list[str] | None = None,
    domain: str | None = None,
    project_modules: list[str] | None = None,
    max_per_query: int = 5,
    timeout_seconds: float = 8.0,
    include_social_sites: bool = True,
    ai_service: object | None = None,
    deep_judge_budget: int = 8,
    # P7-2 新增：智能 query 策略（上层 endpoint 用 strategy engine 生成后传进来）
    query_plans: list[dict[str, Any]] | None = None,
) -> list[SentimentItemDraft]:
    """对一个监控对象跑舆情抓取，返回带情感打标的 drafts。

    Args（关键）:
      - query_plans: 智能 strategy 生成的 query 矩阵（含 intent/priority/source_priority）。
        如果提供则**主路径**，硬编码模板只在 plan 缺失时兜底。
      - aliases/domain/project_modules: 数据中心信号备份，传统硬编码 query 矩阵也会用。
    """
    # 主路径：智能 query plan 优先
    if query_plans:
        # query_plans 已按 priority 排好（strategy 出口排过），直接拿 query_text
        queries = [str(q.get("queryText") or "").strip() for q in query_plans if q.get("queryText")]
        queries = [q for q in queries if q]
    else:
        # 降级兜底：硬编码模板
        queries = build_search_queries(
            target_name,
            business_line=business_line,
            aliases=aliases,
            domain=domain,
            project_modules=project_modules,
            include_social_sites=include_social_sites,
        )
    if not queries:
        return []

    drafts: list[SentimentItemDraft] = []
    seen_urls: set[str] = set()
    captured_at = datetime.now(timezone.utc).isoformat()

    # 目标出现校验：title+snippet 必须含 target_name 或某个 alias，否则丢弃。
    # 出问题的场景：搜「A组织 投诉 OR 质疑」时引擎把「韩红基金会被举报」也返回了，
    # 那条 hit 全文一个「A组织」字都没有 — 必须挡掉，否则负面预警就是错的。
    name_tokens = _build_target_tokens(target_name, aliases)

    def _hit_mentions_target(title: str, snippet: str) -> bool:
        if not name_tokens:
            return True  # 没目标可比对就别拦
        text = f"{title}\n{snippet}"
        return any(tok in text for tok in name_tokens)

    def _ingest_hit(hit: Any) -> None:
        url = (getattr(hit, "url", "") or "").strip()
        if not url or url in seen_urls:
            return
        title = (getattr(hit, "title", "") or "").strip()
        snippet = (getattr(hit, "snippet", "") or "").strip()
        if _is_low_value_hit(title, snippet, url):
            return
        # P0 修复：跨主体污染拦截
        if not _hit_mentions_target(title, snippet):
            return
        seen_urls.add(url)
        text = f"{title}\n{snippet}"
        sentiment = analyze_sentiment(text, target_name=target_name)
        drafts.append(SentimentItemDraft(
            title=title or "(无标题)",
            summary=snippet[:300] or title,
            source=_domain_label(url),
            source_url=url,
            sentiment=sentiment,
            captured_at=captured_at,
        ))

    # 1) 三大搜索引擎冗余抓取
    for query in queries:
        try:
            results = search_public_web(
                query,
                max_results=max_per_query,
                timeout_seconds=timeout_seconds,
            )
        except Exception:  # noqa: BLE001  网络故障不阻塞流程
            continue
        for hit in results:
            _ingest_hit(hit)

    # 2) 多平台搜索 — 搜狗微信 + B 站 API（verified work）+ 其他 stub
    if include_social_sites:
        # 2a) 搜狗微信：每条 query 顺手过一遍，拿公众号长文
        try:
            from app.services.multi_platform_search import search_wechat, search_bilibili
            top_queries_for_social = queries[:8]
            for q in top_queries_for_social:
                # 搜狗微信
                try:
                    wx_hits = search_wechat(q, max_results=max_per_query, timeout_seconds=10.0)
                    for hit in wx_hits:
                        _ingest_hit(hit)
                except Exception:  # noqa: BLE001
                    pass
                # B 站 API（实测 verified work，每 query 命中 5-20 条）
                try:
                    bili_hits = search_bilibili(q, max_results=max_per_query, timeout_seconds=10.0)
                    for hit in bili_hits:
                        _ingest_hit(hit)
                except Exception:  # noqa: BLE001
                    pass
        except Exception:  # noqa: BLE001
            pass

        # 2b) 社交平台直抓 stub（微博/小红书/抖音/知乎/B 站）
        # — 当前都被反爬挡住返回 []，保留接口等后续接 Playwright
        try:
            from app.services.social_search import search_weibo, search_xiaohongshu, search_douyin
        except Exception:  # noqa: BLE001
            search_weibo = search_xiaohongshu = search_douyin = None  # type: ignore[assignment]

        base_social_query = target_name.strip()
        for fn in (search_weibo, search_xiaohongshu, search_douyin):
            if fn is None:
                continue
            try:
                social_hits = fn(
                    base_social_query,
                    max_results=max_per_query,
                    timeout_seconds=timeout_seconds,
                )
            except Exception:  # noqa: BLE001
                continue
            for hit in social_hits:
                _ingest_hit(hit)

    # 3) 全文增强 — B 站走 yt-dlp+SenseVoice / 公众号走 HTML 解析
    # 复用系统已有的 link_material_import 通道，把 200 字 snippet 升级为千字级正文
    # 注：耗时大，限 top 3 顺序跑，单条 timeout 180s
    if drafts:
        try:
            from app.services.intelligence_transcript_enrich import enrich_drafts_with_transcripts
            drafts, transcript_stats = enrich_drafts_with_transcripts(
                drafts, max_transcripts=3, per_item_timeout_seconds=180.0,
            )
            if transcript_stats["succeeded"]:
                import logging
                logging.getLogger(__name__).info(
                    "[transcript-enrich] %d 条 hit 全文化成功（B站/公众号）",
                    transcript_stats["succeeded"],
                )
        except Exception:  # noqa: BLE001
            pass  # 全文增强失败不阻塞情感分析

    # 4) Insight Agent — 对边界情况跑 Qwen 二次判定（在全文之后跑，判断更准）
    if ai_service is not None and drafts:
        try:
            from app.services.intelligence_insight_agent import deep_judge_drafts
            drafts, _stats = deep_judge_drafts(
                ai_service,
                drafts,
                target_name=target_name,
                max_invocations=deep_judge_budget,
                timeout_seconds=25.0,
            )
        except Exception:  # noqa: BLE001
            pass  # LLM 故障不阻塞抓取主流程

    return drafts


def _domain_label(url: str) -> str:
    """从 URL 提取友好域名标签，对社交平台/公众号显式分类。

    用户视角的「公众入口」必须显形，不能被搜索引擎中转 URL 隐藏。
    """
    try:
        host = (urlparse(url).hostname or "").lower()
        # ── 社交平台 / 公众号显式分类（优先级最高）──
        if "weixin.sogou.com" in host or "mp.weixin.qq.com" in host:
            return "微信公众号"
        if "weibo.com" in host or "weibo.cn" in host:
            return "微博"
        if "xiaohongshu.com" in host or "xhscdn" in host:
            return "小红书"
        if "douyin.com" in host or "iesdouyin.com" in host:
            return "抖音"
        if "kuaishou.com" in host:
            return "快手"
        if "zhihu.com" in host or "zhihu.cn" in host:
            return "知乎"
        if "bilibili.com" in host:
            return "B站"
        if "douban.com" in host:
            return "豆瓣"
        if "toutiao.com" in host:
            return "今日头条"
        if "baijiahao.baidu.com" in host:
            return "百家号"
        # ── 权威源 ──
        if "gov.cn" in host:
            return "政府.gov.cn"
        if "tianyancha.com" in host:
            return "天眼查"
        if "qichacha.com" in host or "qcc.com" in host:
            return "企查查"
        # ── fallback：通用域名 ──
        parts = host.split(".")
        if len(parts) >= 2:
            return ".".join(parts[-2:])
        return host
    except Exception:  # noqa: BLE001
        return ""


# ──────────────────────────────────────────────────────────────────────────
# 入库
# ──────────────────────────────────────────────────────────────────────────


def persist_sentiment_drafts(
    db: Database,
    *,
    drafts: list[SentimentItemDraft],
    client_id: str | None = None,
    project_module_id: str | None = None,
) -> int:
    """把 drafts 写入 intelligence_items 表，content_kind='public_opinion'。

    每条带上 client_id / project_module_id（业务线级别舆情聚合用）。
    返回实际写入条数（去重后）。
    """
    inserted = 0
    timestamp = datetime.now(timezone.utc).isoformat()
    scope_type = "project_module" if project_module_id else ("client" if client_id else None)
    scope_id = project_module_id or client_id

    for draft in drafts:
        # 简单去重：同 source_url 24 小时内已入库则跳过
        existing = db.fetchone(
            """
            SELECT id FROM intelligence_items
            WHERE content_kind = 'public_opinion'
              AND source_url = ?
              AND captured_at > datetime(?, '-1 day')
            LIMIT 1
            """,
            (draft.source_url, timestamp),
        )
        if existing:
            continue

        item_id = f"iitem_{uuid.uuid4().hex[:12]}"
        # tags_json 存情感标签 + 命中词，前端不用解析也能展示
        tags = [draft.sentiment.label] + draft.sentiment.matched_terms[:4]
        user_feedback = {
            "sentiment": {
                "label": draft.sentiment.label,
                "score": draft.sentiment.score,
                "confidence": draft.sentiment.confidence,
                "reason": draft.sentiment.reason,
            },
        }
        db.execute(
            """
            INSERT INTO intelligence_items (
                id, content_kind, scope_type, scope_id, client_id, project_module_id,
                title, summary, key_points_json, analysis, impact,
                intelligence_type, timeliness_label, relevance_reason, suggested_action,
                followup_questions_json, tags_json,
                source, source_url, published_at,
                captured_at, user_status, user_feedback_json,
                created_at, updated_at
            ) VALUES (
                ?, 'public_opinion', ?, ?, ?, ?,
                ?, ?, '[]', '', '',
                '舆情', ?, ?, '',
                '[]', ?,
                ?, ?, ?,
                ?, 'active', ?,
                ?, ?
            )
            """,
            (
                item_id, scope_type, scope_id, client_id, project_module_id,
                draft.title, draft.summary,
                _label_to_timeliness(draft.sentiment.label),
                draft.sentiment.reason,
                to_json(tags),
                draft.source, draft.source_url, draft.captured_at,
                draft.captured_at, to_json(user_feedback),
                timestamp, timestamp,
            ),
        )
        inserted += 1

        # P7-2 双写：同一条 hit 也送进数据中心 ingest，复用其多源对比/澄清流程
        try:
            from app.services.data_center_ingest import ingest_external_observation
            ingest_external_observation(
                db,
                source_type="external_sentiment",
                source_url=draft.source_url,
                title=draft.title,
                body_text=draft.summary,
                client_id=client_id,
                project_module_id=project_module_id,
                captured_at=draft.captured_at,
                sentiment_label=draft.sentiment.label,
                intent_kind="evaluation",
                metadata_extra={
                    "intelligenceItemId": item_id,
                    "sentimentScore": draft.sentiment.score,
                    "sentimentConfidence": draft.sentiment.confidence,
                    "sentimentReason": draft.sentiment.reason,
                    "sourceLabel": draft.source,
                },
            )
        except Exception:  # noqa: BLE001
            # 数据中心写失败不阻塞主流程，由 logger 记录
            import logging
            logging.getLogger(__name__).warning(
                "[sentiment] data center ingest failed for %s", draft.source_url, exc_info=True,
            )
    return inserted


def _label_to_timeliness(label: str) -> str:
    """情感 label 复用 timeliness_label 字段（避免改 schema）。"""
    if label == "negative":
        return "negative_alert"
    if label == "positive":
        return "positive_signal"
    return "neutral_mention"


# ──────────────────────────────────────────────────────────────────────────
# 查询：公众画像聚合（按业务线维度）
# ──────────────────────────────────────────────────────────────────────────


def compute_sentiment_profile(
    db: Database,
    *,
    client_id: str | None = None,
    project_module_id: str | None = None,
    within_days: int = 30,
) -> dict[str, Any]:
    """聚合 N 天内的舆情数据，输出公众画像。

    数据：
      - 整体情感分（0-100）
      - 提及量
      - 三色分布（负面/中性/积极）
      - 高频词（tags 聚合）
      - 注意点（负面集中 source 域名）
    """
    cutoff = datetime.now(timezone.utc).timestamp() - within_days * 86400
    cutoff_iso = datetime.fromtimestamp(cutoff, timezone.utc).isoformat()

    where = [
        "content_kind = 'public_opinion'",
        "captured_at >= ?",
        # 排除用户已确认误判 / 已处理的条目，避免画像被脏数据拖垮
        "COALESCE(user_status, 'active') NOT IN ('dismissed', 'misclassified')",
    ]
    params: list[Any] = [cutoff_iso]
    if project_module_id:
        where.append("project_module_id = ?")
        params.append(project_module_id)
    elif client_id:
        where.append("client_id = ?")
        params.append(client_id)
    where_sql = " AND ".join(where)

    rows = db.fetchall(
        f"SELECT timeliness_label, source, tags_json FROM intelligence_items WHERE {where_sql}",
        tuple(params),
    )

    negative_count = 0
    positive_count = 0
    neutral_count = 0
    source_counter: dict[str, int] = {}
    neg_source_counter: dict[str, int] = {}

    for row in rows:
        label_field = str(row["timeliness_label"] or "")
        if label_field == "negative_alert":
            negative_count += 1
            src = str(row["source"] or "")
            if src:
                neg_source_counter[src] = neg_source_counter.get(src, 0) + 1
        elif label_field == "positive_signal":
            positive_count += 1
        else:
            neutral_count += 1
        src = str(row["source"] or "")
        if src:
            source_counter[src] = source_counter.get(src, 0) + 1

    total = negative_count + positive_count + neutral_count
    # 情感分：100 - (负面占比 * 80)，简单兜底算法
    if total > 0:
        sentiment_score = max(0, int(100 - (negative_count / total) * 80))
    else:
        sentiment_score = 0

    top_neg_sources = sorted(
        neg_source_counter.items(), key=lambda kv: kv[1], reverse=True,
    )[:3]
    return {
        "withinDays": within_days,
        "totalMentions": total,
        "sentimentScore": sentiment_score,
        "negativeCount": negative_count,
        "neutralCount": neutral_count,
        "positiveCount": positive_count,
        "topNegativeSources": [
            {"source": s, "count": c} for s, c in top_neg_sources
        ],
        "topSources": sorted(
            [{"source": s, "count": c} for s, c in source_counter.items()],
            key=lambda x: x["count"], reverse=True,
        )[:5],
    }


def list_sentiment_items(
    db: Database,
    *,
    client_id: str | None = None,
    project_module_id: str | None = None,
    within_days: int = 30,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """读最近 N 天的舆情条目，按情感 label 排序（负面优先 → 中性 → 积极）。"""
    cutoff_iso = datetime.fromtimestamp(
        datetime.now(timezone.utc).timestamp() - within_days * 86400,
        timezone.utc,
    ).isoformat()

    where = [
        "content_kind = 'public_opinion'",
        "captured_at >= ?",
        # 同 compute_sentiment_profile：用户处置过的不再回显
        "COALESCE(user_status, 'active') NOT IN ('dismissed', 'misclassified')",
    ]
    params: list[Any] = [cutoff_iso]
    if project_module_id:
        where.append("project_module_id = ?")
        params.append(project_module_id)
    elif client_id:
        where.append("client_id = ?")
        params.append(client_id)
    where_sql = " AND ".join(where)

    rows = db.fetchall(
        f"""
        SELECT id, title, summary, source, source_url, captured_at,
               timeliness_label, relevance_reason, tags_json, user_status
        FROM intelligence_items
        WHERE {where_sql}
        ORDER BY
            CASE timeliness_label
                WHEN 'negative_alert' THEN 0
                WHEN 'neutral_mention' THEN 1
                WHEN 'positive_signal' THEN 2
                ELSE 3
            END,
            captured_at DESC
        LIMIT ?
        """,
        (*params, limit),
    )
    return [
        {
            "id": str(row["id"]),
            "title": str(row["title"] or ""),
            "summary": str(row["summary"] or ""),
            "source": str(row["source"] or ""),
            "sourceUrl": str(row["source_url"] or ""),
            "capturedAt": str(row["captured_at"] or ""),
            "sentimentLabel": _label_to_short(str(row["timeliness_label"] or "")),
            "sentimentReason": str(row["relevance_reason"] or ""),
            "tags": _parse_tags(row["tags_json"]),
            "userStatus": str(row["user_status"] or "active"),
        }
        for row in rows
    ]


def _label_to_short(timeliness: str) -> str:
    if timeliness == "negative_alert":
        return "negative"
    if timeliness == "positive_signal":
        return "positive"
    return "neutral"


def _parse_tags(raw: Any) -> list[str]:
    if not raw:
        return []
    try:
        import json
        return [str(item) for item in json.loads(raw) if item]
    except Exception:  # noqa: BLE001
        return []
