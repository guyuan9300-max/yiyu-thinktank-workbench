from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("YIYU_WORKBENCH_DATA_DIR", tempfile.mkdtemp(prefix="yiyu-p4-tests-"))

from app.db import Database, to_json
from app.main import create_app
from app.services import intelligence_candidate_supply as supply
from app.services.intelligence_candidate_supply import (
    CandidateHit,
    OFFICIAL_SITE_SECTION_SPECS,
    discover_official_site_source_configs,
    ensure_default_source_configs,
    run_intelligence_candidate_refresh,
)
from app.services.intelligence_search_intents import GeneratedSearchIntent, IntelligenceSearchScope


def _seed_client(db: Database, *, client_id: str = "client_rici", name: str = "广东省日慈公益基金会") -> None:
    db.execute(
        """
        INSERT OR REPLACE INTO clients(id, name, alias, domain, type, intro, stage, color, created_at, updated_at)
        VALUES(?, ?, ?, '儿童心理健康', 'foundation', '关注困境儿童和儿童心理健康服务', 'active', '#5B7BFE',
            '2026-05-14T09:00:00', '2026-05-14T09:00:00')
        """,
        (client_id, name, name),
    )


def _scope(client_id: str = "client_rici") -> IntelligenceSearchScope:
    return IntelligenceSearchScope(
        scope_type="client",
        scope_id=client_id,
        client_id=client_id,
        project_module_id=None,
        display_name="广东省日慈公益基金会",
    )


def _intent(query: str, *, content_kind: str = "timely_intelligence", intent_id: str = "intent_p4") -> GeneratedSearchIntent:
    return GeneratedSearchIntent(
        id=intent_id,
        scope_type="client",
        scope_id="client_rici",
        client_id="client_rici",
        project_module_id=None,
        content_kind=content_kind,
        query=query,
        exclude_terms=[],
        source_inputs=["client:广东省日慈公益基金会"],
        reason="P4 定向测试",
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
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ready', ?, ?, 'p4-test', ?, ?)
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


def test_p4_default_sources_are_typed_and_web_search_is_fallback(tmp_path: Path) -> None:
    db = Database(tmp_path / "p4_sources.sqlite")
    _seed_client(db)
    configs = ensure_default_source_configs(db, _scope())
    by_type = {config.source_type: config for config in configs}

    assert {"profile_report", "regulatory_risk", "partner_peer", "web_search"} <= set(by_type)
    assert by_type["web_search"].priority < by_type["grant"].priority
    assert by_type["web_search"].priority < by_type["social_org_registry"].priority
    assert by_type["profile_report"].content_kinds == ["profile_completion"]
    assert by_type["regulatory_risk"].content_kinds == ["timely_intelligence"]
    assert by_type["partner_peer"].content_kinds == ["timely_intelligence"]


def test_p4_official_site_discovery_creates_fixed_section_sources_and_filters_bad_domains(tmp_path: Path) -> None:
    db = Database(tmp_path / "p4_official.sqlite")
    _seed_client(db)
    scope = _scope()

    def fake_fetcher(_query: str, _config) -> list[CandidateHit]:
        return [
            CandidateHit(
                title="广东省日慈公益基金会 官网 信息公开",
                url="https://www.rici.org.cn/about",
                snippet="广东省日慈公益基金会官方网站，公开项目介绍和信息公开。",
                source="广东省日慈公益基金会",
            ),
            CandidateHit(
                title="广东省日慈公益基金会_360图片",
                url="https://image.so.com/i?q=%E6%97%A5%E6%85%88",
                snippet="查看全部图片搜索结果。",
                source="360图片",
            ),
        ]

    promoted = discover_official_site_source_configs(db, scope=scope, hit_fetcher=fake_fetcher)

    assert len(promoted) == 1
    official_count = db.scalar(
        "SELECT COUNT(1) FROM intelligence_source_configs WHERE source_type='official_site' AND scope_id='client_rici'"
    )
    section_rows = db.fetchall(
        "SELECT source_url_template, content_kinds_json FROM intelligence_source_configs WHERE source_type='official_site_section' AND scope_id='client_rici'"
    )
    assert official_count == 1
    assert len(section_rows) == len(OFFICIAL_SITE_SECTION_SPECS)
    assert all("site:rici.org.cn" in row["source_url_template"] for row in section_rows)
    assert not db.fetchone("SELECT 1 FROM intelligence_source_configs WHERE source_url_template LIKE '%image.so.com%'")


def test_p4_route_matching_prefers_specific_sources_over_web_search(tmp_path: Path) -> None:
    db = Database(tmp_path / "p4_routes.sqlite")
    _seed_client(db)
    configs = ensure_default_source_configs(db, _scope())

    grant_task = supply._selected_fetch_tasks(
        db,
        [_intent("广东省日慈公益基金会 公益创投 申报 征集", intent_id="intent_grant")],
        configs,
        max_fetch_jobs=1,
    )[0]
    procurement_task = supply._selected_fetch_tasks(
        db,
        [_intent("广东省日慈公益基金会 政府购买服务 招标 采购", intent_id="intent_procurement")],
        configs,
        max_fetch_jobs=1,
    )[0]
    risk_task = supply._selected_fetch_tasks(
        db,
        [_intent("广东省日慈公益基金会 公开募捐 监管 风险提示", intent_id="intent_risk")],
        configs,
        max_fetch_jobs=1,
    )[0]

    assert grant_task[1].source_type == "grant"
    assert procurement_task[1].source_type == "procurement"
    assert risk_task[1].source_type == "regulatory_risk"


def test_p4_body_quality_rejection_is_recorded_before_profile_card(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "p4_quality.sqlite")
    _seed_client(db)
    scope = _scope()
    intent = _intent("广东省日慈公益基金会 信息公开 年报", content_kind="profile_completion", intent_id="intent_profile")
    _insert_intent(db, intent)

    monkeypatch.setattr(
        supply,
        "_fetch_page_text",
        lambda _url: ("low_cjk", "Only a short English shell.", "中文正文不足，无法可靠核验"),
    )

    def fake_fetcher(_query: str, source_config) -> list[CandidateHit]:
        return [
            CandidateHit(
                title="广东省日慈公益基金会 信息公开 年报",
                url="https://www.rici.org.cn/report",
                snippet="广东省日慈公益基金会信息公开和年度报告。",
                source=source_config.source_name,
            )
        ]

    result = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=None,
        scope=scope,
        intents=[intent],
        max_fetch_jobs=1,
        hit_fetcher=fake_fetcher,
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    assert result.candidate_count == 1
    assert result.promoted_count == 0
    row = db.fetchone("SELECT body_fetch_status, promotion_reason FROM intelligence_candidate_items WHERE scope_id='client_rici'")
    assert row is not None
    assert row["body_fetch_status"] == "low_cjk"
    assert "中文正文不足" in row["promotion_reason"]
    assert db.scalar("SELECT COUNT(1) FROM intelligence_items WHERE content_kind='profile_completion'") == 0


def test_p4_source_health_retry_and_notice_duplicate_merge(tmp_path: Path) -> None:
    db = Database(tmp_path / "p4_health.sqlite")
    _seed_client(db)
    scope = _scope()
    intent = _intent("广东省日慈公益基金会 公益创投 申报 征集", intent_id="intent_duplicate")
    _insert_intent(db, intent)

    def duplicate_fetcher(_query: str, source_config) -> list[CandidateHit]:
        return [
            CandidateHit(
                title="广东省日慈公益基金会公益创投项目征集公告",
                url="https://news.example.org/a?id=1&utm_source=search",
                snippet="困境儿童心理服务公益创投申报窗口开启。",
                source=source_config.source_name,
            ),
            CandidateHit(
                title="广东省日慈公益基金会公益创投项目征集公告",
                url="https://mirror.example.org/repost?id=2",
                snippet="困境儿童心理服务公益创投申报窗口开启。",
                source=source_config.source_name,
            ),
        ]

    result = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=None,
        scope=scope,
        intents=[intent],
        max_fetch_jobs=1,
        hit_fetcher=duplicate_fetcher,
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    assert result.candidate_count == 2
    assert result.duplicate_count == 1
    duplicate_source = db.fetchone(
        """
        SELECT duplicate_count, candidate_count, last_status
        FROM intelligence_source_configs
        WHERE id = (SELECT source_config_id FROM intelligence_candidate_items WHERE classification_status='duplicate' LIMIT 1)
        """
    )
    assert duplicate_source is not None
    assert int(duplicate_source["duplicate_count"]) >= 1
    assert int(duplicate_source["candidate_count"]) >= 2
    assert duplicate_source["last_status"] == "success"

    failing_intent = _intent("广东省日慈公益基金会 公开募捐 监管 风险提示", intent_id="intent_fail")
    _insert_intent(db, failing_intent)

    def failing_fetcher(_query: str, _source_config) -> list[CandidateHit]:
        raise RuntimeError("provider down")

    failed = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=None,
        scope=scope,
        intents=[failing_intent],
        max_fetch_jobs=1,
        hit_fetcher=failing_fetcher,
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    assert failed.failed_count == 1
    failed_source = db.fetchone("SELECT failure_count, success_count, last_status, last_failure_at, next_due_at FROM intelligence_source_configs WHERE last_status='failed' ORDER BY updated_at DESC LIMIT 1")
    assert failed_source is not None
    assert int(failed_source["failure_count"]) >= 1
    assert int(failed_source["success_count"]) == 0
    assert failed_source["last_failure_at"]
    assert datetime.fromisoformat(str(failed_source["next_due_at"])) <= datetime.now().replace(microsecond=0) + timedelta(hours=2, minutes=5)


def test_p4_source_diagnostics_endpoint_returns_backend_records(tmp_path: Path) -> None:
    app = create_app(tmp_path / "data")
    with TestClient(app) as client:
        db = client.app.state.app_state.db
        _seed_client(db)
        ensure_default_source_configs(db, _scope())

        response = client.get(
            "/api/v1/intelligence/source-diagnostics",
            params={"scopeType": "client", "scopeId": "client_rici", "contentKind": "timely_intelligence"},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["scopeType"] == "client"
        assert payload["scopeId"] == "client_rici"
        assert payload["sources"]
        assert "recentFetchJobs" in payload
        assert any(source["sourceType"] == "regulatory_risk" for source in payload["sources"])
