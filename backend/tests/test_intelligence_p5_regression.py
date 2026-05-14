from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("YIYU_WORKBENCH_DATA_DIR", tempfile.mkdtemp(prefix="yiyu-p5-tests-"))

import app.main as app_main
from app.db import Database, to_json
from app.main import create_app
from app.models import AiStructuredResponse
from app.services import intelligence_candidate_supply as supply
from app.services.intelligence_candidate_supply import (
    CandidateHit,
    ensure_default_source_configs,
    run_intelligence_candidate_refresh,
)
from app.services.intelligence_search_intents import (
    GeneratedSearchIntent,
    IntelligenceSearchScope,
    SearchIntentGenerationResult,
)


def _seed_client(db: Database, *, client_id: str, name: str) -> None:
    db.execute(
        """
        INSERT OR REPLACE INTO clients(id, name, alias, domain, type, intro, stage, color, created_at, updated_at)
        VALUES(?, ?, ?, '儿童心理健康', 'foundation', '关注困境儿童和儿童心理健康服务', 'active', '#5B7BFE',
            '2026-05-14T09:00:00', '2026-05-14T09:00:00')
        """,
        (client_id, name, name),
    )


def _scope(client_id: str = "client_rici", name: str = "广东省日慈公益基金会") -> IntelligenceSearchScope:
    return IntelligenceSearchScope(
        scope_type="client",
        scope_id=client_id,
        client_id=client_id,
        project_module_id=None,
        display_name=name,
    )


def _intent(
    query: str,
    *,
    content_kind: str,
    intent_id: str = "intent_p5",
    client_id: str = "client_rici",
) -> GeneratedSearchIntent:
    return GeneratedSearchIntent(
        id=intent_id,
        scope_type="client",
        scope_id=client_id,
        client_id=client_id,
        project_module_id=None,
        content_kind=content_kind,
        query=query,
        exclude_terms=[],
        source_inputs=["client:广东省日慈公益基金会"],
        reason="P5 防退化测试",
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
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ready', ?, ?, 'p5-test', ?, ?)
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


class _ReadyAi:
    def get_health(self):
        return type("Health", (), {"ready": True, "provider": "doubao"})()

    def generate_general_fallback(self, *_args, **_kwargs):
        return AiStructuredResponse(
            content="广东省日慈公益基金会公开资料显示，该机构关注儿童心理健康与公益服务。",
            judgment="该内容与广东省日慈公益基金会当前客户画像相关。",
            analysis="可用于补充客户基础画像和项目方向判断。",
            actions="建议转成阅读/研判任务，核验原始来源后再行动。",
        )


def test_p5_prototype_samples_and_example_domains_never_promote_or_enter_documents(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "p5_sample.sqlite")
    _seed_client(db, client_id="client_rici", name="广东省日慈公益基金会")
    scope = _scope()
    intent = _intent("广东省日慈公益基金会 儿童心理健康 项目资助征集开放", content_kind="profile_completion")
    _insert_intent(db, intent)
    monkeypatch.setattr(
        supply,
        "_fetch_page_text",
        lambda _url: (
            "fetched",
            "广东省日慈公益基金会登记信息显示，该机构关注儿童心理健康、项目资助和公益服务，业务范围包含公益项目与社区服务。",
            "",
        ),
    )

    def sample_fetcher(_query: str, source_config) -> list[CandidateHit]:
        return [
            CandidateHit(
                title="儿童心理健康相关项目资助征集开放",
                url="https://example.org/grant",
                snippet="某资助方发布面向儿童心理健康项目的征集公告。",
                source=source_config.source_name,
            )
        ]

    result = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=_ReadyAi(),
        scope=scope,
        intents=[intent],
        max_fetch_jobs=1,
        hit_fetcher=sample_fetcher,
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    assert result.candidate_count == 1
    assert result.promoted_count == 0
    reason_row = db.fetchone("SELECT promotion_reason FROM intelligence_candidate_items WHERE scope_id='client_rici'")
    reason = reason_row["promotion_reason"] if reason_row else ""
    assert "样张" in str(reason)
    assert db.scalar("SELECT COUNT(1) FROM intelligence_items WHERE scope_id='client_rici'") == 0
    assert db.scalar("SELECT COUNT(1) FROM documents WHERE client_id='client_rici'") == 0
    assert db.scalar("SELECT COUNT(1) FROM v2_documents WHERE client_id='client_rici'") == 0


def test_p5_noisy_counterexamples_remain_backend_rejections(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "p5_noise.sqlite")
    _seed_client(db, client_id="client_rici", name="广东省日慈公益基金会")
    scope = _scope()
    intent = _intent("广东省日慈公益基金会 信息公开 年报", content_kind="profile_completion")
    _insert_intent(db, intent)
    monkeypatch.setattr(
        supply,
        "_fetch_page_text",
        lambda _url: ("login_page", "用户登录 账号登录 验证码 注册", "页面为登录或验证码页面，无法可靠核验"),
    )

    def noisy_fetcher(_query: str, source_config) -> list[CandidateHit]:
        return [
            CandidateHit(
                title="广东省日慈公益基金会_360图片",
                url="https://image.so.com/i?q=%E6%97%A5%E6%85%88",
                snippet="查看全部图片搜索结果。",
                source="360图片",
            ),
            CandidateHit(
                title="广东省日慈公益基金会 信息公开页面",
                url="https://reports.rici.org.cn/login",
                snippet="广东省日慈公益基金会信息公开和年报入口。",
                source=source_config.source_name,
            ),
        ]

    result = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=_ReadyAi(),
        scope=scope,
        intents=[intent],
        max_fetch_jobs=1,
        hit_fetcher=noisy_fetcher,
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    assert result.candidate_count == 1
    assert result.promoted_count == 0
    row = db.fetchone("SELECT title, body_fetch_status, promotion_reason FROM intelligence_candidate_items WHERE scope_id='client_rici'")
    assert row is not None
    assert "_360图片" not in str(row["title"])
    assert row["body_fetch_status"] == "login_page"
    assert "登录或验证码" in row["promotion_reason"]
    assert db.scalar("SELECT COUNT(1) FROM intelligence_items WHERE scope_id='client_rici'") == 0


def test_p5_recruitment_directory_page_never_becomes_timely_candidate(tmp_path: Path) -> None:
    db = Database(tmp_path / "p5_recruitment_directory.sqlite")
    _seed_client(db, client_id="client_rici", name="广东省日慈公益基金会")
    scope = _scope()
    intent = _intent("广东省日慈公益基金会 公益创投 申报 征集", content_kind="timely_intelligence", intent_id="intent_jobui")
    _insert_intent(db, intent)

    def directory_fetcher(_query: str, source_config) -> list[CandidateHit]:
        return [
            CandidateHit(
                title="广东省日慈公益基金会 怎么样 - 职友集",
                url="https://www.jobui.com/company/14417762/",
                snippet="广东省日慈公益基金会工资待遇、招聘要求、公司评价。",
                source=source_config.source_name,
            )
        ]

    result = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=_ReadyAi(),
        scope=scope,
        intents=[intent],
        max_fetch_jobs=1,
        hit_fetcher=directory_fetcher,
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    assert result.candidate_count == 0
    assert result.promoted_count == 0
    assert db.scalar("SELECT COUNT(1) FROM intelligence_candidate_items WHERE scope_id='client_rici'") == 0
    assert db.scalar("SELECT COUNT(1) FROM intelligence_items WHERE scope_id='client_rici'") == 0


def test_p5_profile_and_timely_streams_do_not_mix(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "p5_mix.sqlite")
    _seed_client(db, client_id="client_rici", name="广东省日慈公益基金会")
    scope = _scope()
    timely_intent = _intent("广东省日慈公益基金会 社会组织 登记信息 年报", content_kind="timely_intelligence", intent_id="intent_static")
    profile_intent = _intent("广东省日慈公益基金会 公益创投 申报 征集", content_kind="profile_completion", intent_id="intent_opportunity")
    _insert_intent(db, timely_intent)
    _insert_intent(db, profile_intent)
    monkeypatch.setattr(
        supply,
        "_fetch_page_text",
        lambda _url: (
            "fetched",
            "广东省日慈公益基金会近期公益创投申报征集通知，截止时间明确，需要判断是否符合申报资格。",
            "",
        ),
    )

    def static_fetcher(_query: str, source_config) -> list[CandidateHit]:
        return [
            CandidateHit(
                title="广东省日慈公益基金会社会组织登记信息",
                url="https://gdngo.gdnpo.gov.cn/org/rici",
                snippet="统一社会信用代码、业务范围、年报和登记机关等静态信息。",
                source=source_config.source_name,
            )
        ]

    def opportunity_fetcher(_query: str, source_config) -> list[CandidateHit]:
        return [
            CandidateHit(
                title="广东省日慈公益基金会公益创投申报征集通知",
                url="https://grant.rici.org.cn/notice",
                snippet="近期公益创投申报征集通知，含截止时间和申报条件。",
                source=source_config.source_name,
            )
        ]

    timely_result = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=_ReadyAi(),
        scope=scope,
        intents=[timely_intent],
        max_fetch_jobs=1,
        hit_fetcher=static_fetcher,
        official_site_hit_fetcher=lambda _query, _config: [],
    )
    profile_result = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=_ReadyAi(),
        scope=scope,
        intents=[profile_intent],
        max_fetch_jobs=1,
        hit_fetcher=opportunity_fetcher,
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    assert timely_result.promoted_count == 0
    assert profile_result.promoted_count == 0
    reasons = [str(row["promotion_reason"]) for row in db.fetchall("SELECT promotion_reason FROM intelligence_candidate_items")]
    assert any("静态登记" in reason for reason in reasons)
    assert any("不作为资料补全成卡" in reason for reason in reasons)


def test_p5_user_visible_items_api_does_not_leak_internal_scores_or_candidates(tmp_path: Path) -> None:
    app = create_app(tmp_path / "data")
    with TestClient(app) as client:
        db = client.app.state.app_state.db
        _seed_client(db, client_id="client_rici", name="广东省日慈公益基金会")
        db.execute(
            """
            INSERT INTO intelligence_items(
                id, content_kind, scope_type, scope_id, client_id, title, summary,
                key_points_json, analysis, impact, tags_json, source, source_url,
                captured_at, verified_at, credibility_score, confidence_score,
                verification_status, verification_reason, user_status, created_at, updated_at
            )
            VALUES('item_visible', 'timely_intelligence', 'client', 'client_rici', 'client_rici',
                '真实资助机会', '发生了什么', ?, '为什么有关', '可能影响', ?,
                '资助方官网公告', 'https://grant.rici.org.cn/notice',
                '2026-05-14T10:00:00', '2026-05-14T10:00:00', 0.93, 0.91,
                'verified', '内部核验理由', 'active', '2026-05-14T10:00:00', '2026-05-14T10:00:00')
            """,
            (to_json(["要点"]), to_json(["外部情报", "资助机会"])),
        )
        db.execute(
            """
            INSERT INTO intelligence_candidate_items(
                id, scope_type, scope_id, client_id, content_kind, title, url, snippet,
                source, source_tier, captured_at, confidence_score, classification_status,
                promotion_reason, created_at, updated_at
            )
            VALUES('cand_hidden', 'client', 'client_rici', 'client_rici', 'timely_intelligence',
                '候选短摘', 'https://candidate.rici.org.cn', '搜索短摘不能普通展示',
                '候选来源', 'strong', '2026-05-14T10:00:00', 95,
                'candidate', '内部成卡原因', '2026-05-14T10:00:00', '2026-05-14T10:00:00')
            """
        )

        response = client.get(
            "/api/v1/intelligence/items",
            params={"contentKind": "timely_intelligence", "scopeType": "client", "scopeId": "client_rici"},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["candidateSamples"] == []
        item = payload["items"][0]
        leaked_keys = {"healthScore", "sourceTier", "sourceType", "confidenceScore", "credibilityScore", "promotionReason", "snippet"}
        assert leaked_keys.isdisjoint(item.keys())
        assert item["title"] == "真实资助机会"
        assert item["source"] == "资助方官网公告"


def test_p5_fetch_budget_limits_jobs_and_duplicates_merge(tmp_path: Path) -> None:
    db = Database(tmp_path / "p5_budget.sqlite")
    _seed_client(db, client_id="client_rici", name="广东省日慈公益基金会")
    scope = _scope()
    intents = [
        _intent("广东省日慈公益基金会 公益创投 申报 征集", content_kind="timely_intelligence", intent_id="intent_a"),
        _intent("广东省日慈公益基金会 政府购买服务 招标 采购", content_kind="timely_intelligence", intent_id="intent_b"),
        _intent("广东省日慈公益基金会 公开募捐 监管 风险", content_kind="timely_intelligence", intent_id="intent_c"),
    ]
    for intent in intents:
        _insert_intent(db, intent)
    calls: list[str] = []

    def duplicate_fetcher(query: str, source_config) -> list[CandidateHit]:
        calls.append(query)
        return [
            CandidateHit(
                title="广东省日慈公益基金会公益创投项目征集公告",
                url=f"https://notice.rici.org.cn/a?source={source_config.source_type}",
                snippet="困境儿童心理服务公益创投申报窗口开启。",
                source=source_config.source_name,
            ),
            CandidateHit(
                title="广东省日慈公益基金会公益创投项目征集公告",
                url=f"https://mirror.rici.org.cn/b?source={source_config.source_type}",
                snippet="困境儿童心理服务公益创投申报窗口开启。",
                source=source_config.source_name,
            ),
        ]

    result = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=None,
        scope=scope,
        intents=intents,
        max_fetch_jobs=2,
        hit_fetcher=duplicate_fetcher,
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    assert result.fetch_job_count == 2
    assert len(calls) == 2
    assert result.duplicate_count >= 1
    assert db.scalar("SELECT COUNT(1) FROM intelligence_fetch_jobs WHERE scope_id='client_rici' AND content_kind='timely_intelligence'") == 2


def test_p5_batch_refresh_dispatches_all_clients_even_when_one_background_job_fails(tmp_path: Path, monkeypatch) -> None:
    app = create_app(tmp_path / "data")
    with TestClient(app) as client:
        db = client.app.state.app_state.db
        _seed_client(db, client_id="client_good", name="好客户")
        _seed_client(db, client_id="client_bad", name="坏客户")
        calls: list[str] = []

        def fake_generate(_db, _ai_service, *, scope_type: str, scope_id: str, content_kind: str | None = None, force: bool = False):
            intent = _intent(
                f"{scope_id} 公益创投 申报 征集",
                content_kind=content_kind or "timely_intelligence",
                intent_id=f"intent_{scope_id}",
                client_id=scope_id,
            )
            return SearchIntentGenerationResult(
                scope=IntelligenceSearchScope(
                    scope_type="client",
                    scope_id=scope_id,
                    client_id=scope_id,
                    project_module_id=None,
                    display_name=scope_id,
                ),
                intents=[intent],
                status="ready",
                input_hash=f"hash_{scope_id}",
            )

        def fake_refresh(_db, **kwargs):
            scope = kwargs["scope"]
            calls.append(scope.scope_id)
            if scope.scope_id == "client_bad":
                raise RuntimeError("single client failed")
            return supply.CandidateRefreshResult(fetch_job_count=1)

        monkeypatch.setattr(app_main, "generate_intelligence_search_intents", fake_generate)
        monkeypatch.setattr(app_main, "run_intelligence_candidate_refresh", fake_refresh)

        response = client.post(
            "/api/v1/intelligence/refresh",
            json={"scopeType": "all", "scopeId": None, "contentKind": "timely_intelligence", "force": True},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["totals"]["objectCount"] == 2
        assert set(calls) == {"client_good", "client_bad"}


def test_p5_legacy_intelligence_items_schema_migrates_public_optional_fields(tmp_path: Path) -> None:
    db_path = tmp_path / "p5_legacy_schema.sqlite"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE intelligence_items (
            id TEXT PRIMARY KEY,
            content_kind TEXT NOT NULL,
            scope_type TEXT,
            scope_id TEXT,
            client_id TEXT,
            project_module_id TEXT,
            title TEXT NOT NULL,
            summary TEXT NOT NULL DEFAULT '',
            key_points_json TEXT NOT NULL DEFAULT '[]',
            analysis TEXT NOT NULL DEFAULT '',
            impact TEXT NOT NULL DEFAULT '',
            tags_json TEXT NOT NULL DEFAULT '[]',
            source TEXT NOT NULL DEFAULT '',
            source_url TEXT,
            published_at TEXT,
            captured_at TEXT NOT NULL,
            verified_at TEXT,
            credibility_score REAL,
            confidence_score REAL,
            data_center_ingest_event_id TEXT,
            external_evidence_card_id TEXT,
            topic_candidate_id TEXT,
            converted_task_id TEXT,
            user_status TEXT NOT NULL DEFAULT 'active',
            user_feedback_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            verification_status TEXT NOT NULL DEFAULT 'verified',
            verification_reason TEXT NOT NULL DEFAULT ''
        );
        """
    )
    conn.close()

    db = Database(db_path)
    columns = {str(row["name"]) for row in db.fetchall("PRAGMA table_info(intelligence_items)")}

    assert {
        "intelligence_type",
        "timeliness_label",
        "relevance_reason",
        "suggested_action",
        "followup_questions_json",
    }.issubset(columns)
