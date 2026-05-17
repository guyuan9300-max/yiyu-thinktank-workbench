from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("YIYU_WORKBENCH_DATA_DIR", tempfile.mkdtemp(prefix="yiyu-timely-strategy-tests-"))

from app.db import Database, to_json
from app.models import AiStructuredResponse
from app.services import intelligence_candidate_supply as supply
from app.services.data_center_ingest import ensure_data_center_ingest_schema
from app.services.intelligence_candidate_supply import CandidateHit, run_intelligence_candidate_refresh
from app.services.intelligence_search_intents import (
    GeneratedSearchIntent,
    IntelligenceSearchScope,
    generate_intelligence_search_intents,
)
from app.services.intelligence_timely_strategy import build_timely_research_strategy


def _seed_client(
    db: Database,
    *,
    client_id: str,
    name: str,
    domain: str = "儿童心理健康",
    intro: str = "关注儿童青少年心理健康服务、公益组织数字化和项目合作。",
) -> None:
    db.execute(
        """
        INSERT OR REPLACE INTO clients(id, name, alias, domain, type, intro, stage, color, created_at, updated_at)
        VALUES(?, ?, ?, ?, 'foundation', ?, 'active', '#5B7BFE',
            '2026-05-14T09:00:00', '2026-05-14T09:00:00')
        """,
        (client_id, name, name, domain, intro),
    )


def _scope(client_id: str, name: str) -> IntelligenceSearchScope:
    return IntelligenceSearchScope(
        scope_type="client",
        scope_id=client_id,
        client_id=client_id,
        project_module_id=None,
        display_name=name,
    )


def _intent(client_id: str, query: str, *, intent_id: str = "intent_timely_strategy") -> GeneratedSearchIntent:
    return GeneratedSearchIntent(
        id=intent_id,
        scope_type="client",
        scope_id=client_id,
        client_id=client_id,
        project_module_id=None,
        content_kind="timely_intelligence",
        query=query,
        exclude_terms=[],
        source_inputs=[f"client:{client_id}", "timely_strategy:test"],
        reason="时效策略层测试",
        priority=99,
        status="ready",
        input_hash=f"hash_{intent_id}",
        expires_at="2026-05-15T00:00:00",
    )


def _insert_intent(db: Database, intent: GeneratedSearchIntent) -> None:
    db.execute(
        """
        INSERT INTO intelligence_search_intents(
            id, scope_type, scope_id, client_id, project_module_id, content_kind, query,
            exclude_terms_json, source_inputs_json, reason, priority, status,
            input_hash, expires_at, generator_version, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ready', ?, ?, 'timely-strategy-test', ?, ?)
        """,
        (
            intent.id,
            intent.scope_type,
            intent.scope_id,
            intent.client_id,
            intent.project_module_id,
            intent.content_kind,
            intent.query,
            to_json(intent.exclude_terms),
            to_json(intent.source_inputs),
            intent.reason,
            intent.priority,
            intent.input_hash,
            intent.expires_at,
            "2026-05-14T10:00:00",
            "2026-05-14T10:00:00",
        ),
    )


def _insert_focus(db: Database, *, client_id: str, timely: list[str], profile: list[str] | None = None) -> None:
    db.execute(
        """
        INSERT OR REPLACE INTO intelligence_focus_directives(
            id, scope_type, scope_id, profile_completion_focus_json, timely_intelligence_focus_json,
            exclude_json, created_at, updated_at
        )
        VALUES(?, 'client', ?, ?, ?, '[]', '2026-05-14T10:00:00', '2026-05-14T10:00:00')
        """,
        (f"focus_{client_id}", client_id, to_json(profile or []), to_json(timely)),
    )


def _insert_profile_card(db: Database, *, client_id: str, title: str, summary: str, tags: list[str] | None = None) -> None:
    db.execute(
        """
        INSERT INTO intelligence_items(
            id, content_kind, scope_type, scope_id, client_id, project_module_id,
            title, summary, key_points_json, analysis, impact, tags_json,
            source, source_url, published_at, captured_at, verified_at,
            credibility_score, confidence_score, verification_status, verification_reason,
            user_status, created_at, updated_at
        )
        VALUES(?, 'profile_completion', 'client', ?, ?, NULL, ?, ?, ?, '', '', ?,
            '测试资料源', 'https://source.example.cn/profile', '2026-05-01',
            '2026-05-14T10:00:00', '2026-05-14T10:00:00',
            0.9, 0.9, 'verified', '测试资料卡', 'active',
            '2026-05-14T10:00:00', '2026-05-14T10:00:00')
        """,
        (
            f"profile_{client_id}_{abs(hash(title))}",
            client_id,
            client_id,
            title,
            summary,
            to_json([summary]),
            to_json(tags or ["已核验资料"]),
        ),
    )


class _ReadyTimelyAi:
    def get_health(self):
        return type("Health", (), {"ready": True, "provider": "doubao"})()

    def generate_general_fallback(self, *_args, **_kwargs):
        return AiStructuredResponse(
            content="有资助方开放儿童青少年心理健康服务申报窗口，方向覆盖教师心理素养培训和心理平台建设。",
            judgment="这条机会与广东省日慈公益基金会关注的儿童心理健康服务相关，可能影响其合作机会、资源争取和项目材料准备。",
            analysis="如果日慈具备对应服务基础，可作为合作或申报窗口；若地域、资格或服务对象不匹配，则应纳入机会观察清单而非立即执行。",
            actions="先核验原公告的截止时间、申报资格、地域限制和服务对象，再判断是否转成申报准备或合作跟进任务。",
            timeline="仍处于有效申报窗口内，需要在窗口期完成研判。",
        )


def test_timely_strategy_reads_profile_cards_and_generates_strategy_queries(tmp_path: Path) -> None:
    db = Database(tmp_path / "timely_strategy_queries.sqlite")
    _seed_client(db, client_id="client_rici", name="广东省日慈公益基金会")
    _insert_focus(db, client_id="client_rici", timely=["儿童青少年心理健康、心灵魔法学院、心盛计划相关的资助、监管和合作动态。"])
    _insert_profile_card(
        db,
        client_id="client_rici",
        title="日慈心灵魔法学院资料卡",
        summary="日慈基金会通过心灵魔法学院和心盛计划服务儿童青少年心理健康，重点关注困境儿童、课程和平台建设。",
        tags=["项目介绍", "执行方法"],
    )

    strategy = build_timely_research_strategy(
        db,
        scope_type="client",
        scope_id="client_rici",
        client_id="client_rici",
        display_name="广东省日慈公益基金会",
    )
    assert strategy.profile_ready is True
    assert "心灵魔法学院" in "\n".join(strategy.search_atoms)
    assert len(strategy.routes) >= 8

    result = generate_intelligence_search_intents(
        db,
        ai_service=None,
        scope_type="client",
        scope_id="client_rici",
        content_kind="timely_intelligence",
        force=True,
    )
    text = "\n".join(f"{item.query} {' '.join(item.source_inputs)}" for item in result.intents)

    assert "timely_strategy:v1" in text
    assert "心灵魔法学院" in text or "心盛计划" in text
    for route in ("政策监管", "资助申报", "采购招标", "合作方动态", "同类机构动态", "行业风险", "项目/方法趋势", "新闻舆情"):
        assert f"timely_route:{route}" in text
    assert all(len(item.query) <= 88 for item in result.intents)


def test_external_intelligence_does_not_make_profile_ready(tmp_path: Path) -> None:
    db = Database(tmp_path / "timely_strategy_external_noise.sqlite")
    ensure_data_center_ingest_schema(db)
    _seed_client(db, client_id="client_empty", name="空资料客户", domain="", intro="")
    db.execute(
        """
        INSERT INTO data_center_ingest_events(
            id, source_type, source_id, content_hash, client_id, title,
            lifecycle_status, status, metadata_json, created_at, updated_at
        )
        VALUES('noise_1', 'external_intelligence', 'old_noise', 'hash_noise', 'client_empty',
            '旧情报噪音：资助机会', 'active', 'ready', ?, '2026-05-14T10:00:00', '2026-05-14T10:00:00')
        """,
        (to_json({"summary": "这是一条旧外部情报，不应反哺对象画像"}),),
    )

    strategy = build_timely_research_strategy(
        db,
        scope_type="client",
        scope_id="client_empty",
        client_id="client_empty",
        display_name="空资料客户",
    )

    assert strategy.source_counts["dataCenterItems"] == 0
    assert strategy.profile_ready is False
    assert "本地资料/已核验资料" in strategy.profile_gaps


def test_stale_source_with_future_effective_window_can_be_promoted(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "timely_strategy_future_window.sqlite")
    _seed_client(db, client_id="client_rici", name="广东省日慈公益基金会")
    _insert_focus(db, client_id="client_rici", timely=["儿童青少年心理健康服务资助计划。"])
    _insert_profile_card(
        db,
        client_id="client_rici",
        title="日慈儿童心理健康项目资料",
        summary="日慈基金会关注儿童青少年心理健康服务和心理平台建设。",
    )
    intent = _intent("client_rici", "儿童青少年心理健康 资助 申报", intent_id="intent_future_window")
    _insert_intent(db, intent)
    monkeypatch.setattr(
        supply,
        "_fetch_page_text",
        lambda _url: (
            "fetched",
            "发布时间：2023-01-10。某基金会发布儿童青少年心理健康服务资助申报通知，面向心理平台建设项目征集合作。"
            "本轮申报截止时间为2099年12月31日，仍在有效申报窗口内，相关公益组织需要核验服务对象、地域限制和申报资格。",
            "",
        ),
    )

    result = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=_ReadyTimelyAi(),
        scope=_scope("client_rici", "广东省日慈公益基金会"),
        intents=[intent],
        max_fetch_jobs=1,
        hit_fetcher=lambda _query, source_config: [
            CandidateHit(
                title="儿童青少年心理健康服务资助申报通知",
                url="https://grant.example.cn/future-window",
                snippet="申报截止时间为2099年12月31日，仍在征集。",
                source=source_config.source_name,
            )
        ],
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    assert result.promoted_count == 1
    assert result.timely_effective_window_exception_count == 1
    row = db.fetchone("SELECT verification_reason, evidence_json FROM intelligence_candidate_items WHERE content_kind='timely_intelligence'")
    assert row is not None
    assert "freshnessReason" in str(row["evidence_json"])


def test_recruitment_and_generic_news_do_not_become_timely_cards(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "timely_strategy_reject_noise.sqlite")
    _seed_client(db, client_id="client_rici", name="广东省日慈公益基金会")
    _insert_focus(db, client_id="client_rici", timely=["儿童青少年心理健康服务资助计划。"])
    _insert_profile_card(
        db,
        client_id="client_rici",
        title="日慈儿童心理健康项目资料",
        summary="日慈基金会关注儿童青少年心理健康服务和心理平台建设。",
    )
    intent = _intent("client_rici", "儿童青少年心理健康 新闻 报道", intent_id="intent_generic_news")
    _insert_intent(db, intent)
    monkeypatch.setattr(
        supply,
        "_fetch_page_text",
        lambda _url: (
            "fetched",
            "发布时间：2026-05-01。公益行业举办高质量发展论坛，文章泛泛讨论公益行业新闻报道，没有申报、监管、合作、风险或项目方法变化。",
            "",
        ),
    )

    result = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=_ReadyTimelyAi(),
        scope=_scope("client_rici", "广东省日慈公益基金会"),
        intents=[intent],
        max_fetch_jobs=2,
        hit_fetcher=lambda _query, source_config: [
            CandidateHit(
                title="儿童发展项目部 项目官员/主管 招聘",
                url="https://www.jobui.com/company/jobs",
                snippet="岗位招聘、薪资待遇。",
                source=source_config.source_name,
            ),
            CandidateHit(
                title="公益行业高质量发展论坛新闻报道",
                url="https://news.example.cn/forum",
                snippet="公益行业新闻报道。",
                source=source_config.source_name,
            ),
        ],
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    assert result.promoted_count == 0
    assert result.candidate_count == 0
    assert db.scalar("SELECT COUNT(1) FROM intelligence_items WHERE content_kind='timely_intelligence'") == 0


def test_tag_profile_drives_timely_queries_without_requiring_object_name(tmp_path: Path) -> None:
    db = Database(tmp_path / "timely_strategy_tag_profile.sqlite")
    _seed_client(
        db,
        client_id="client_generic",
        name="春雨社区服务中心",
        domain="社区儿童服务",
        intro="服务社区困境儿童、青少年心理健康和家庭支持，关注政府购买服务与公益创投资源。",
    )
    _insert_focus(db, client_id="client_generic", timely=["困境儿童心理健康、政府购买服务、公益创投、家庭支持。"])
    _insert_profile_card(
        db,
        client_id="client_generic",
        title="社区儿童服务资料卡",
        summary="该机构提供社区困境儿童心理健康、家庭支持、课程和志愿服务，主要面向广东社区。",
        tags=["服务对象", "执行方法"],
    )

    strategy = build_timely_research_strategy(
        db,
        scope_type="client",
        scope_id="client_generic",
        client_id="client_generic",
        display_name="春雨社区服务中心",
    )
    payload = strategy.as_payload()
    assert "profileTags" in payload
    assert "tagWeights" in payload
    assert "困境儿童" in "\n".join(strategy.search_atoms) or "儿童心理健康" in "\n".join(strategy.search_atoms)

    result = generate_intelligence_search_intents(
        db,
        ai_service=None,
        scope_type="client",
        scope_id="client_generic",
        content_kind="timely_intelligence",
        force=True,
    )
    tag_queries = [item for item in result.intents if "tag_profile:v1" in item.source_inputs]
    assert tag_queries
    assert any("困境儿童" in item.query or "儿童心理健康" in item.query or "政府购买服务" in item.query for item in tag_queries)
    assert any("春雨社区服务中心" not in item.query for item in tag_queries)


def test_timely_focus_does_not_mix_profile_focus_or_official_url(tmp_path: Path) -> None:
    db = Database(tmp_path / "timely_focus_separation.sqlite")
    _seed_client(
        db,
        client_id="client_focus_split",
        name="益语智库",
        domain="公益组织数字化",
        intro="为公益组织提供数字化、AI 公益和组织工作台服务。",
    )
    _insert_focus(
        db,
        client_id="client_focus_split",
        profile=["官网 www.yiyu.love、顾源源文章、官网案例和服务方案。"],
        timely=["AI 公益、公益组织数字化、行业活动案例、资助合作动态。"],
    )
    _insert_profile_card(
        db,
        client_id="client_focus_split",
        title="益语智库服务资料",
        summary="益语智库关注公益组织数字化、AI 公益、服务方案和案例。",
        tags=["项目介绍", "执行方法"],
    )

    strategy = build_timely_research_strategy(
        db,
        scope_type="client",
        scope_id="client_focus_split",
        client_id="client_focus_split",
        display_name="益语智库",
    )
    assert "官网" not in "\n".join(strategy.focus_topics)
    assert "yiyu.love" not in "\n".join(strategy.search_atoms)
    assert "公益组织数字化" in "\n".join([*strategy.focus_topics, *strategy.service_targets])
    assert "AI" in "\n".join(strategy.search_atoms)

    result = generate_intelligence_search_intents(
        db,
        ai_service=None,
        scope_type="client",
        scope_id="client_focus_split",
        content_kind="timely_intelligence",
        force=True,
    )
    timely_queries = "\n".join(item.query for item in result.intents if item.content_kind == "timely_intelligence")
    timely_inputs = "\n".join("\n".join(item.source_inputs) for item in result.intents if item.content_kind == "timely_intelligence")
    assert "site:yiyu.love" not in timely_queries
    assert "官网" not in timely_queries
    assert "www.yiyu.love" not in timely_inputs


def test_timely_external_signal_filters_current_official_domain_and_promotes_inspiration(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "timely_external_signal_official_filter.sqlite")
    _seed_client(
        db,
        client_id="client_yiyu",
        name="益语智库",
        domain="公益组织数字化",
        intro="关注公益组织数字化、AI 公益、服务方案和行业案例。",
    )
    _insert_focus(
        db,
        client_id="client_yiyu",
        profile=["官网 www.yiyu.love、顾源源文章和案例。"],
        timely=["AI 公益、公益组织数字化、行业活动案例、资助合作动态。"],
    )
    _insert_profile_card(
        db,
        client_id="client_yiyu",
        title="益语智库资料",
        summary="益语智库服务公益组织数字化和 AI 公益，关注服务方案、行业案例和合作资源。",
        tags=["项目介绍", "执行方法"],
    )
    intent = _intent("client_yiyu", "公益组织数字化 AI公益 资助 合作", intent_id="intent_external_signal")
    _insert_intent(db, intent)
    monkeypatch.setattr(
        supply,
        "_fetch_page_text",
        lambda _url: (
            "fetched",
            "发布时间：2026-05-03。某公益创投发布公益组织数字化能力建设项目征集通知，支持社会组织应用 AI 工具、数字化工作台和服务方案案例建设。"
            "申报对象为社会组织和公益服务机构，截止时间为2026年06月30日，通知要求说明服务对象、应用场景、合作资源和项目材料。",
            "",
        ),
    )
    class _YiyuTimelyAi(_ReadyTimelyAi):
        def generate_general_fallback(self, *_args, **_kwargs):
            return AiStructuredResponse(
                content="公益创投开放公益组织数字化能力建设申报窗口，支持社会组织应用 AI 公益工具和数字化工作台。",
                judgment="这条外部机会虽未点名益语智库，但与其公益组织数字化、AI 公益和服务方案案例方向高度相关，可作为合作资源和方案启发。",
                analysis="外部资金窗口可能通过社会组织数字化能力建设需求传导到益语智库：客户需要应用场景、工具方案和案例材料，益语可研判是否作为合作方或服务支持方参与。",
                actions="先核验原公告截止时间、申报资格、服务对象和合作方角色，再评估是否转为合作研判或方案素材整理任务。",
                timeline="发布时间处于近 30 天窗口内，申报截止时间仍有效。",
            )

    result = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=_YiyuTimelyAi(),
        scope=_scope("client_yiyu", "益语智库"),
        intents=[intent],
        max_fetch_jobs=1,
        hit_fetcher=lambda _query, source_config: [
            CandidateHit(
                title="益语智库官网新闻",
                url="https://www.yiyu.love/news/ai-public-good",
                snippet="官网文章，介绍益语智库服务方案。",
                source=source_config.source_name,
                published_at="2026-05-02",
            ),
            CandidateHit(
                title="公益组织数字化能力建设项目征集通知",
                url="https://grant.example.cn/ngo-digital-ai-2026",
                snippet="支持社会组织应用 AI 工具和数字化工作台，截止时间为2026年06月30日。",
                source=source_config.source_name,
                published_at="2026-05-03",
            ),
        ],
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    assert result.own_official_filtered_count >= 1
    assert result.external_signal_candidate_count >= 1
    assert result.promoted_count == 1
    assert result.inspiration_card_count == 1
    item = db.fetchone("SELECT intelligence_type, source_url FROM intelligence_items WHERE content_kind='timely_intelligence'")
    assert item is not None
    assert item["intelligence_type"] == "启发型情报"
    assert "yiyu.love" not in str(item["source_url"])
    providers = [str(row["provider"]) for row in db.fetchall("SELECT provider FROM intelligence_fetch_jobs WHERE content_kind='timely_intelligence'")]
    assert "official_site" not in providers
    assert "official_site_section" not in providers


def test_tag_relevant_recent_opportunity_can_promote_without_object_name(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "timely_strategy_tag_relevant.sqlite")
    _seed_client(
        db,
        client_id="client_generic",
        name="春雨社区服务中心",
        domain="社区儿童服务",
        intro="服务社区困境儿童、青少年心理健康和家庭支持。",
    )
    _insert_focus(db, client_id="client_generic", timely=["困境儿童心理健康服务、公益创投、政府购买服务。"])
    _insert_profile_card(
        db,
        client_id="client_generic",
        title="社区儿童心理服务资料",
        summary="机构服务困境儿童和青少年心理健康，具备课程、家庭支持和社区服务基础。",
        tags=["服务对象", "项目介绍"],
    )
    intent = _intent("client_generic", "困境儿童 心理健康 公益创投 申报", intent_id="intent_tag_opportunity")
    _insert_intent(db, intent)
    monkeypatch.setattr(
        supply,
        "_fetch_page_text",
        lambda _url: (
            "fetched",
            "发布时间：2026-05-01。南山区发布公益创投项目征集通知，重点支持困境儿童心理健康服务、家庭支持和社区服务平台建设。"
            "申报对象为社会组织，申报截止时间为2026年06月30日，项目需说明服务对象、地域覆盖、资源需求和执行方案。",
            "",
        ),
    )

    result = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=_ReadyTimelyAi(),
        scope=_scope("client_generic", "春雨社区服务中心"),
        intents=[intent],
        max_fetch_jobs=1,
        hit_fetcher=lambda _query, source_config: [
            CandidateHit(
                title="南山区公益创投项目征集通知",
                url="https://grant.example.cn/children-mental-health-2026",
                snippet="支持困境儿童心理健康服务，申报截止时间为2026年06月30日。",
                source=source_config.source_name,
                published_at="2026-05-01",
            )
        ],
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    assert result.promoted_count == 1
    assert result.scout_candidate_count == 1
    assert result.review_candidate_count == 1
    item = db.fetchone("SELECT title, relevance_reason FROM intelligence_items WHERE content_kind='timely_intelligence'")
    assert item is not None
    assert "春雨社区服务中心" not in str(item["title"])
    assert "相关" in str(item["relevance_reason"]) or "影响" in str(item["relevance_reason"])


def test_business_only_policy_without_public_service_anchor_does_not_promote(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "timely_strategy_business_only.sqlite")
    _seed_client(
        db,
        client_id="client_rici",
        name="广东省日慈公益基金会",
        domain="儿童心理健康",
        intro="关注儿童青少年心理健康、公益创投、政府购买服务和社会组织合作。",
    )
    _insert_focus(db, client_id="client_rici", timely=["儿童青少年心理健康服务、公益创投、政府购买服务。"])
    _insert_profile_card(
        db,
        client_id="client_rici",
        title="儿童心理健康服务资料",
        summary="机构关注儿童青少年心理健康、社会组织合作和公益创投机会。",
        tags=["服务对象", "项目介绍"],
    )
    intent = _intent("client_rici", "儿童青少年心理健康 合作 资源", intent_id="intent_business_only")
    _insert_intent(db, intent)
    monkeypatch.setattr(
        supply,
        "_fetch_page_text",
        lambda _url: (
            "fetched",
            "发布时间：2026-03-27。贵州省外事办印发《关于支持企业对外合作的措施》，"
            "为企业提供政策解读、涉外业务培训、经贸资源对接和境外团组访黔对接支持。",
            "",
        ),
    )

    result = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=_ReadyTimelyAi(),
        scope=_scope("client_rici", "广东省日慈公益基金会"),
        intents=[intent],
        max_fetch_jobs=1,
        hit_fetcher=lambda _query, source_config: [
            CandidateHit(
                title="贵州省外事办公印发《关于支持企业对外合作的措施》",
                url="https://example.gov.cn/business-policy",
                snippet="为企业提供政策解读、涉外业务培训、经贸资源对接和境外团组访黔对接支持。",
                source=source_config.source_name,
                published_at="2026-03-27",
            )
        ],
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    assert result.promoted_count == 0
    assert result.ai_reviewed_count == 0
    assert db.scalar("SELECT COUNT(1) FROM intelligence_items WHERE content_kind='timely_intelligence'") == 0


def test_generic_policy_query_terms_do_not_self_validate_timely_candidate(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "timely_strategy_generic_policy.sqlite")
    _seed_client(
        db,
        client_id="client_rici",
        name="广东省日慈公益基金会",
        domain="儿童心理健康",
        intro="关注儿童青少年心理健康、公益创投、政府购买服务和社会组织合作。",
    )
    _insert_focus(db, client_id="client_rici", timely=["儿童青少年心理健康服务、公益创投、政府购买服务。"])
    _insert_profile_card(
        db,
        client_id="client_rici",
        title="儿童心理健康服务资料",
        summary="机构关注儿童青少年心理健康、社会组织合作和公益创投机会。",
        tags=["服务对象", "项目介绍"],
    )
    intent = _intent("client_rici", "儿童青少年心理健康 政策 通知", intent_id="intent_generic_policy")
    _insert_intent(db, intent)
    monkeypatch.setattr(
        supply,
        "_fetch_page_text",
        lambda _url: (
            "fetched",
            "发布时间：2026-04-02。铜陵市住房公积金中心发布政策调整通知，调整个人住房贷款额度、缴存认定和还款规则。",
            "",
        ),
    )

    result = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=_ReadyTimelyAi(),
        scope=_scope("client_rici", "广东省日慈公益基金会"),
        intents=[intent],
        max_fetch_jobs=1,
        hit_fetcher=lambda _query, source_config: [
            CandidateHit(
                title="铜陵公积金发布政策调整通知",
                url="https://paper.example.cn/housing-fund-policy",
                snippet="调整个人住房贷款额度、缴存认定和还款规则。",
                source=source_config.source_name,
                published_at="2026-04-02",
            )
        ],
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    assert result.promoted_count == 0
    assert result.ai_reviewed_count == 0
    assert db.scalar("SELECT COUNT(1) FROM intelligence_items WHERE content_kind='timely_intelligence'") == 0


def test_object_name_only_static_material_does_not_promote(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "timely_strategy_name_only.sqlite")
    _seed_client(db, client_id="client_name_only", name="春雨社区服务中心", domain="社区儿童服务")
    _insert_profile_card(
        db,
        client_id="client_name_only",
        title="社区服务基础资料",
        summary="机构服务社区儿童和家庭支持。",
    )
    intent = _intent("client_name_only", "春雨社区服务中心 新闻", intent_id="intent_name_only")
    _insert_intent(db, intent)
    monkeypatch.setattr(
        supply,
        "_fetch_page_text",
        lambda _url: (
            "fetched",
            "发布时间：2026-05-02。春雨社区服务中心机构介绍，主要展示机构简介、使命、愿景、项目介绍和团队情况，没有新的政策、资助、采购、合作或风险变化。",
            "",
        ),
    )

    result = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=_ReadyTimelyAi(),
        scope=_scope("client_name_only", "春雨社区服务中心"),
        intents=[intent],
        max_fetch_jobs=1,
        hit_fetcher=lambda _query, source_config: [
            CandidateHit(
                title="春雨社区服务中心机构介绍",
                url="https://org.example.cn/about",
                snippet="机构简介、项目介绍和团队情况。",
                source=source_config.source_name,
                published_at="2026-05-02",
            )
        ],
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    assert result.promoted_count == 0
    assert result.static_profile_filtered_count >= 1
    assert db.scalar("SELECT COUNT(1) FROM intelligence_items WHERE content_kind='timely_intelligence'") == 0


def test_timely_window_31_to_90_days_requires_review_but_can_promote(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "timely_strategy_extended_window.sqlite")
    _seed_client(db, client_id="client_extended", name="春雨社区服务中心", domain="社区儿童服务")
    _insert_focus(db, client_id="client_extended", timely=["困境儿童心理健康服务资助计划。"])
    _insert_profile_card(
        db,
        client_id="client_extended",
        title="社区儿童心理服务资料",
        summary="机构服务困境儿童心理健康和家庭支持。",
    )
    intent = _intent("client_extended", "困境儿童 心理健康 资助 申报", intent_id="intent_extended")
    _insert_intent(db, intent)
    monkeypatch.setattr(
        supply,
        "_fetch_page_text",
        lambda _url: (
            "fetched",
            "发布时间：2026-03-20。省级公益创投发布困境儿童心理健康服务资助申报通知，支持社会组织提供社区心理服务、家庭支持和平台建设。"
            "通知要求说明服务对象、地域、资格条件和项目材料，申报截止时间为2026年06月20日。",
            "",
        ),
    )

    result = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=_ReadyTimelyAi(),
        scope=_scope("client_extended", "春雨社区服务中心"),
        intents=[intent],
        max_fetch_jobs=1,
        hit_fetcher=lambda _query, source_config: [
            CandidateHit(
                title="困境儿童心理健康服务资助申报通知",
                url="https://grant.example.cn/extended-window",
                snippet="支持困境儿童心理健康服务，申报截止时间为2026年06月20日。",
                source=source_config.source_name,
                published_at="2026-03-20",
            )
        ],
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    assert result.promoted_count == 1
    assert result.extended_window_count == 1


def test_over_90_days_without_effective_window_is_rejected(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "timely_strategy_stale_window.sqlite")
    _seed_client(db, client_id="client_stale", name="春雨社区服务中心", domain="社区儿童服务")
    _insert_focus(db, client_id="client_stale", timely=["困境儿童心理健康服务资助计划。"])
    _insert_profile_card(
        db,
        client_id="client_stale",
        title="社区儿童心理服务资料",
        summary="机构服务困境儿童心理健康和家庭支持。",
    )
    intent = _intent("client_stale", "困境儿童 心理健康 资助 申报", intent_id="intent_stale")
    _insert_intent(db, intent)
    monkeypatch.setattr(
        supply,
        "_fetch_page_text",
        lambda _url: (
            "fetched",
            "发布时间：2025-12-01。某地公益创投曾支持困境儿童心理健康服务，文章回顾申报要求、服务对象、地域限制和项目材料。",
            "",
        ),
    )

    result = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=_ReadyTimelyAi(),
        scope=_scope("client_stale", "春雨社区服务中心"),
        intents=[intent],
        max_fetch_jobs=1,
        hit_fetcher=lambda _query, source_config: [
            CandidateHit(
                title="困境儿童心理健康服务资助回顾",
                url="https://grant.example.cn/stale-window",
                snippet="回顾困境儿童心理健康服务申报要求。",
                source=source_config.source_name,
                published_at="2025-12-01",
            )
        ],
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    assert result.promoted_count == 0
    row = db.fetchone("SELECT verification_reason FROM intelligence_candidate_items WHERE content_kind='timely_intelligence'")
    assert row is not None
    assert "90 天" in str(row["verification_reason"])


def test_low_quality_recruitment_domain_does_not_enter_detail_budget(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "timely_strategy_low_quality_domain.sqlite")
    _seed_client(db, client_id="client_low_quality", name="春雨社区服务中心", domain="社区儿童服务")
    _insert_profile_card(
        db,
        client_id="client_low_quality",
        title="社区儿童心理服务资料",
        summary="机构服务困境儿童心理健康和家庭支持。",
    )
    intent = _intent("client_low_quality", "困境儿童 心理健康 招聘", intent_id="intent_low_quality")
    _insert_intent(db, intent)
    monkeypatch.setattr(
        supply,
        "_fetch_page_text",
        lambda _url: (_ for _ in ()).throw(AssertionError("low quality recruitment page should not be fetched")),
    )

    result = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=_ReadyTimelyAi(),
        scope=_scope("client_low_quality", "春雨社区服务中心"),
        intents=[intent],
        max_fetch_jobs=1,
        hit_fetcher=lambda _query, source_config: [
            CandidateHit(
                title="儿童心理健康项目主管招聘",
                url="https://www.gaoxiaojob.com/announce/detail/123",
                snippet="岗位招聘、薪资待遇、人才网公告。",
                source=source_config.source_name,
                published_at="2026-05-01",
            )
        ],
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    assert result.candidate_count == 0
    assert result.detail_fetched_count == 0


def test_timely_scout_uses_web_search_and_compact_queries(tmp_path: Path) -> None:
    db = Database(tmp_path / "timely_strategy_web_scout.sqlite")
    _seed_client(db, client_id="client_rici", name="广东省日慈公益基金会")
    _insert_focus(db, client_id="client_rici", timely=["儿童青少年心理健康服务、公益创投、政府购买服务。"])
    _insert_profile_card(
        db,
        client_id="client_rici",
        title="儿童心理健康服务资料",
        summary="日慈基金会关注儿童青少年心理健康服务、心理平台建设和教师心理素养培训。",
    )
    intent = _intent("client_rici", "广东 儿童青少年心理健康 公益创投 申报 通知", intent_id="intent_web_scout")
    _insert_intent(db, intent)
    seen: list[tuple[str, str]] = []

    def fake_fetch(query: str, source_config):
        seen.append((source_config.source_type, query))
        return []

    result = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=_ReadyTimelyAi(),
        scope=_scope("client_rici", "广东省日慈公益基金会"),
        intents=[intent],
        max_fetch_jobs=3,
        hit_fetcher=fake_fetch,
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    assert result.query_count == 3
    assert seen[0][0] == "web_search"
    assert "广东 广东" not in "\n".join(query for _source, query in seen)
    assert not any("监管 资助 申报 公益创投 征集 通知" in query for _source, query in seen)


def test_timely_can_promote_at_most_five_cards_per_refresh(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "timely_strategy_card_cap.sqlite")
    _seed_client(db, client_id="client_cap", name="春雨社区服务中心", domain="社区儿童服务")
    _insert_focus(db, client_id="client_cap", timely=["困境儿童心理健康、公益创投、政府购买服务。"])
    _insert_profile_card(
        db,
        client_id="client_cap",
        title="社区儿童心理服务资料",
        summary="机构服务困境儿童、青少年心理健康和家庭支持。",
    )
    intent = _intent("client_cap", "困境儿童 心理健康 公益创投 申报", intent_id="intent_cap")
    _insert_intent(db, intent)

    def fake_page_text(url: str):
        index = url.rsplit("/", 1)[-1]
        return (
            "fetched",
            f"发布时间：2026-05-01。第{index}号公益创投项目征集通知，重点支持困境儿童心理健康服务、家庭支持和社区服务平台建设。"
            "申报对象为社会组织，申报截止时间为2026年06月30日，需要说明服务对象、地域覆盖、资源需求和执行方案。",
            "",
        )

    monkeypatch.setattr(supply, "_fetch_page_text", fake_page_text)
    hits = [
        CandidateHit(
            title=f"困境儿童心理健康公益创投征集通知 {index}",
            url=f"https://grant.example.cn/opportunity/{index}",
            snippet="支持困境儿童心理健康服务，仍在申报窗口内。",
            source="公益创投公开源",
            published_at="2026-05-01",
        )
        for index in range(7)
    ]

    result = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=_ReadyTimelyAi(),
        scope=_scope("client_cap", "春雨社区服务中心"),
        intents=[intent],
        max_fetch_jobs=1,
        hit_fetcher=lambda _query, _source_config: hits,
        official_site_hit_fetcher=lambda _query, _config: [],
        timely_promote_limit=5,
    )

    assert result.scout_candidate_count == 7
    assert result.promoted_count == 5
    assert db.scalar("SELECT COUNT(1) FROM intelligence_items WHERE content_kind='timely_intelligence'") == 5
    overflow = db.scalar(
        "SELECT COUNT(1) FROM intelligence_candidate_items WHERE promotion_reason LIKE '%5 条上限%'"
    )
    assert overflow == 2


def test_continue_existing_fetched_timely_candidates_runs_ai_back_half(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "timely_continue_back_half.sqlite")
    _seed_client(db, client_id="client_continue", name="春雨社区服务中心", domain="社区儿童服务")
    _insert_focus(db, client_id="client_continue", timely=["困境儿童心理健康服务、公益创投、政府购买服务。"])
    _insert_profile_card(
        db,
        client_id="client_continue",
        title="社区儿童心理服务资料",
        summary="机构服务困境儿童和青少年心理健康，具备课程、家庭支持和社区服务基础。",
        tags=["服务对象", "项目介绍"],
    )
    intent = _intent("client_continue", "困境儿童 心理健康 公益创投 申报", intent_id="intent_continue")
    _insert_intent(db, intent)

    monkeypatch.setattr(
        supply,
        "_fetch_page_text",
        lambda _url: (
            "fetched",
            "发布时间：2026-05-01。南山区发布公益创投项目征集通知，重点支持困境儿童心理健康服务、家庭支持和社区服务平台建设。"
            "申报对象为社会组织，申报截止时间为2026年06月30日，项目需说明服务对象、地域覆盖、资源需求和执行方案。",
            "",
        ),
    )

    first = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=None,
        scope=_scope("client_continue", "春雨社区服务中心"),
        intents=[intent],
        max_fetch_jobs=1,
        hit_fetcher=lambda _query, source_config: [
            CandidateHit(
                title="南山区公益创投项目征集通知",
                url="https://grant.example.cn/continue-children-mental-health",
                snippet="支持困境儿童心理健康服务，申报截止时间为2026年06月30日。",
                source=source_config.source_name,
                published_at="2026-05-01",
            )
        ],
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    assert first.promoted_count == 0
    assert first.body_fetched_count == 1
    assert "AI 不可用" in str(
        db.scalar("SELECT COUNT(1) FROM intelligence_candidate_items WHERE promotion_reason LIKE '%AI 不可用%'")
    ) or db.scalar("SELECT COUNT(1) FROM intelligence_candidate_items WHERE summary_status = 'not_attempted'") >= 1

    continued = supply.continue_timely_candidate_review(
        db,
        data_dir=tmp_path,
        ai_service=_ReadyTimelyAi(),
        scope=_scope("client_continue", "春雨社区服务中心"),
        since="2026-01-01T00:00:00",
    )

    assert continued.candidate_count == 1
    assert continued.ai_reviewed_count == 1
    assert continued.promoted_count == 1
    assert db.scalar("SELECT COUNT(1) FROM intelligence_items WHERE content_kind='timely_intelligence'") == 1
