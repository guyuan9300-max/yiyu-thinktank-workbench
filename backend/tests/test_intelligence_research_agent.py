from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("YIYU_WORKBENCH_DATA_DIR", tempfile.mkdtemp(prefix="yiyu-research-agent-tests-"))

from app.db import Database, to_json
from app.models import AiStructuredResponse
from app.services import intelligence_candidate_supply as supply
from app.services.intelligence_candidate_supply import CandidateHit, run_intelligence_candidate_refresh
from app.services.intelligence_search_intents import GeneratedSearchIntent, IntelligenceSearchScope


def _seed_client(db: Database, *, client_id: str, name: str, domain: str = "儿童心理健康") -> None:
    db.execute(
        """
        INSERT OR REPLACE INTO clients(id, name, alias, domain, type, intro, stage, color, created_at, updated_at)
        VALUES(?, ?, ?, ?, 'foundation', '关注公益组织数字化和儿童心理健康服务', 'active', '#5B7BFE',
            '2026-05-14T09:00:00', '2026-05-14T09:00:00')
        """,
        (client_id, name, name, domain),
    )


def _scope(client_id: str, name: str) -> IntelligenceSearchScope:
    return IntelligenceSearchScope(
        scope_type="client",
        scope_id=client_id,
        client_id=client_id,
        project_module_id=None,
        display_name=name,
    )


def _intent(client_id: str, query: str, *, content_kind: str, intent_id: str = "intent_research") -> GeneratedSearchIntent:
    return GeneratedSearchIntent(
        id=intent_id,
        scope_type="client",
        scope_id=client_id,
        client_id=client_id,
        project_module_id=None,
        content_kind=content_kind,
        query=query,
        exclude_terms=[],
        source_inputs=[f"client:{client_id}"],
        reason="研究员流程定向测试",
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
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ready', ?, ?, 'research-agent-test', ?, ?)
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


def _insert_focus(db: Database, *, client_id: str, profile: list[str] | None = None, timely: list[str] | None = None) -> None:
    db.execute(
        """
        INSERT OR REPLACE INTO intelligence_focus_directives(
            id, scope_type, scope_id, profile_completion_focus_json, timely_intelligence_focus_json,
            exclude_json, created_at, updated_at
        )
        VALUES(?, 'client', ?, ?, ?, '[]', '2026-05-14T10:00:00', '2026-05-14T10:00:00')
        """,
        (f"focus_{client_id}", client_id, to_json(profile or []), to_json(timely or [])),
    )


class _ReadyAi:
    def get_health(self):
        return type("Health", (), {"ready": True, "provider": "doubao"})()

    def generate_general_fallback(self, *_args, **_kwargs):
        return AiStructuredResponse(
            content="资料摘要：该网页提供了与客户/项目相关的公开资料，可用于补充项目介绍和团队线索。",
            judgment="证据缺口：仍需核验完整来源页和更新时间。",
            analysis="可复用事实：\n- 广东省日慈公益基金会公开材料提到心灵魔法学院项目，说明该项目面向儿童青少年心理健康服务。\n- 广东省日慈公益基金会材料提到心盛计划关注困境儿童心理健康，可作为项目方向线索。",
            actions="",
            timeline="",
        )


def test_research_profile_card_requires_focus_evidence_and_reuses_body_quotes(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "research_profile.sqlite")
    _seed_client(db, client_id="client_rici", name="广东省日慈公益基金会")
    _insert_focus(db, client_id="client_rici", profile=["日慈基金会官网介绍。心灵魔法学院、心盛计划两大项目的案例和数据。"])
    intent = _intent("client_rici", "广东省日慈公益基金会 心灵魔法学院 项目介绍", content_kind="profile_completion")
    _insert_intent(db, intent)
    monkeypatch.setattr(
        supply,
        "_fetch_page_text",
        lambda _url: (
            "fetched",
            "广东省日慈公益基金会官网介绍，心灵魔法学院项目面向儿童青少年心理健康服务，提供课程、活动和家庭支持。"
            "广东省日慈公益基金会在心盛计划中持续关注困境儿童心理健康，公开材料提到项目服务对象、执行方法和案例。",
            "",
        ),
    )

    def fetcher(_query: str, source_config) -> list[CandidateHit]:
        return [
            CandidateHit(
                title="广东省日慈公益基金会心灵魔法学院项目介绍",
                url="https://www.rici.org.cn/projects/magic",
                snippet="广东省日慈公益基金会官网公开心灵魔法学院项目介绍。",
                source=source_config.source_name,
            )
        ]

    result = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=_ReadyAi(),
        scope=_scope("client_rici", "广东省日慈公益基金会"),
        intents=[intent],
        max_fetch_jobs=1,
        hit_fetcher=fetcher,
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    assert result.promoted_count == 1
    item = db.fetchone("SELECT summary, key_points_json FROM intelligence_items WHERE scope_id='client_rici'")
    assert item is not None
    assert "已围绕标题" not in str(item["summary"])
    assert "心灵魔法学院" in str(item["key_points_json"])


def test_research_profile_focus_is_priority_not_hard_gate_for_basic_gaps(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "research_profile_reject.sqlite")
    _seed_client(db, client_id="client_rici", name="广东省日慈公益基金会")
    _insert_focus(db, client_id="client_rici", profile=["心灵魔法学院、心盛计划两大项目的案例和数据。"])
    intent = _intent("client_rici", "广东省日慈公益基金会 登记信息", content_kind="profile_completion")
    _insert_intent(db, intent)
    monkeypatch.setattr(
        supply,
        "_fetch_page_text",
        lambda _url: (
            "fetched",
            "广东省日慈公益基金会登记信息显示，该机构属于社会组织，页面包含统一社会信用代码、登记机关和业务范围。",
            "",
        ),
    )

    result = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=_ReadyAi(),
        scope=_scope("client_rici", "广东省日慈公益基金会"),
        intents=[intent],
        max_fetch_jobs=1,
        hit_fetcher=lambda _query, source_config: [
            CandidateHit(
                title="广东省日慈公益基金会社会组织登记信息",
                url="https://gdnpo.gov.cn/org/rici",
                snippet="广东省日慈公益基金会登记信息。",
                source=source_config.source_name,
            )
        ],
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    assert result.promoted_count == 1
    row = db.fetchone("SELECT summary, tags_json FROM intelligence_items WHERE scope_id='client_rici'")
    assert row is not None
    assert "登记信息" in str(row["summary"]) or "登记信息" in str(row["tags_json"])
    assert result.profile_completion_ready is False
    assert "年报/信息公开" in result.profile_missing_dimensions


def test_research_user_supplied_url_becomes_trusted_official_source(tmp_path: Path) -> None:
    db = Database(tmp_path / "research_url.sqlite")
    _seed_client(db, client_id="client_yiyu", name="益语智库", domain="公益组织数字化")
    _insert_focus(db, client_id="client_yiyu", profile=["益语智库/顾源源的观点、文章、案例。官网（www.yiyu.love）的益语介绍。"])
    intent = _intent("client_yiyu", "益语智库 顾源源 观点 文章", content_kind="profile_completion", intent_id="intent_yiyu")

    run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=None,
        scope=_scope("client_yiyu", "益语智库"),
        intents=[intent],
        max_fetch_jobs=1,
        hit_fetcher=lambda _query, _config: [],
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    rows = db.fetchall(
        "SELECT source_type, source_name, source_url_template, discovery_source FROM intelligence_source_configs WHERE scope_id='client_yiyu'"
    )
    assert any(row["source_type"] == "official_site" and "site:yiyu.love" in row["source_url_template"] and row["discovery_source"] == "user_focus_directive" for row in rows)
    assert any(row["source_type"] == "official_site_section" and "site:yiyu.love" in row["source_url_template"] for row in rows)


def test_research_list_page_drills_down_but_never_promotes_list_itself(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "research_list.sqlite")
    _seed_client(db, client_id="client_rici", name="广东省日慈公益基金会")
    _insert_focus(db, client_id="client_rici", profile=["张真接受采访的报道。"])
    intent = _intent("client_rici", "广东省日慈公益基金会 张真 采访 报道", content_kind="profile_completion")
    _insert_intent(db, intent)
    monkeypatch.setattr(
        supply,
        "_drilldown_detail_hits_from_list",
        lambda _hit, _terms, **_kwargs: [
            CandidateHit(
                title="广东省日慈公益基金会秘书长张真接受采访",
                url="https://www.rici.org.cn/news/zhangzhen",
                snippet="由列表页下钻得到的采访详情页。",
                source="日慈官网",
                provider="list_drilldown",
            )
        ],
    )
    monkeypatch.setattr(
        supply,
        "_fetch_page_text",
        lambda _url: (
            "fetched",
            "广东省日慈公益基金会秘书长张真接受采访时介绍，基金会关注儿童心理健康服务，并结合项目案例推动困境儿童支持。",
            "",
        ),
    )

    result = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=_ReadyAi(),
        scope=_scope("client_rici", "广东省日慈公益基金会"),
        intents=[intent],
        max_fetch_jobs=1,
        hit_fetcher=lambda _query, source_config: [
            CandidateHit(
                title="广东省日慈公益基金会新闻列表",
                url="https://www.rici.org.cn/news?page=1",
                snippet="新闻列表，含张真采访报道。",
                source=source_config.source_name,
            )
        ],
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    assert result.promoted_count == 1
    rows = db.fetchall("SELECT title, page_type, source_page_url FROM intelligence_candidate_items WHERE scope_id='client_rici'")
    assert len(rows) == 1
    assert "新闻列表" not in str(rows[0]["title"])
    assert rows[0]["page_type"] == "detail_page"


def test_research_timely_card_requires_body_change_and_impact_evidence(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "research_timely.sqlite")
    _seed_client(db, client_id="client_rici", name="广东省日慈公益基金会")
    _insert_focus(db, client_id="client_rici", timely=["与儿童青少年心理健康服务、心理平台建设、教师心理素养培训有关的资助计划、合作机会、政策导向。"])
    intent = _intent("client_rici", "儿童青少年心理健康 教师心理素养培训 资助 申报", content_kind="timely_intelligence")
    _insert_intent(db, intent)
    monkeypatch.setattr(
        supply,
        "_fetch_page_text",
        lambda _url: (
            "fetched",
            "某基金会发布儿童青少年心理健康服务资助申报通知，面向教师心理素养培训和心理平台建设项目征集合作。"
            "通知明确近期申报窗口和材料要求，相关公益组织需要核验服务对象、地域限制和申报资格。",
            "",
        ),
    )

    result = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=_ReadyAi(),
        scope=_scope("client_rici", "广东省日慈公益基金会"),
        intents=[intent],
        max_fetch_jobs=1,
        hit_fetcher=lambda _query, source_config: [
            CandidateHit(
                title="儿童青少年心理健康服务资助申报通知",
                url="https://grant.example.cn/mental-health-notice",
                snippet="近期申报窗口，面向教师心理素养培训和心理平台建设。",
                source=source_config.source_name,
            )
        ],
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    assert result.promoted_count == 1
    item = db.fetchone("SELECT summary, relevance_reason, impact, suggested_action FROM intelligence_items WHERE content_kind='timely_intelligence'")
    assert item is not None
    assert "心理" in str(item["summary"])
    assert str(item["relevance_reason"])
    assert str(item["impact"])
    assert str(item["suggested_action"])
