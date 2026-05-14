from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("YIYU_WORKBENCH_DATA_DIR", tempfile.mkdtemp(prefix="yiyu-search-surface-tests-"))

from app.db import Database, to_json
from app.services.intelligence_candidate_supply import CandidateHit, run_intelligence_candidate_refresh
from app.services.intelligence_search_intents import (
    GeneratedSearchIntent,
    IntelligenceSearchScope,
    generate_intelligence_search_intents,
)


def _seed_client(db: Database, *, client_id: str, name: str, domain: str = "儿童心理健康") -> None:
    db.execute(
        """
        INSERT OR REPLACE INTO clients(id, name, alias, domain, type, intro, stage, color, created_at, updated_at)
        VALUES(?, ?, ?, ?, 'foundation', '关注公益组织数字化和儿童心理健康服务', 'active', '#5B7BFE',
            '2026-05-14T09:00:00', '2026-05-14T09:00:00')
        """,
        (client_id, name, name, domain),
    )


def _seed_focus(
    db: Database,
    *,
    client_id: str,
    profile: list[str] | None = None,
    timely: list[str] | None = None,
) -> None:
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


def _scope(client_id: str, name: str) -> IntelligenceSearchScope:
    return IntelligenceSearchScope(
        scope_type="client",
        scope_id=client_id,
        client_id=client_id,
        project_module_id=None,
        display_name=name,
    )


def _intent(client_id: str, query: str, *, content_kind: str, intent_id: str = "intent_search_surface") -> GeneratedSearchIntent:
    return GeneratedSearchIntent(
        id=intent_id,
        scope_type="client",
        scope_id=client_id,
        client_id=client_id,
        project_module_id=None,
        content_kind=content_kind,
        query=query,
        exclude_terms=[],
        source_inputs=[f"client:{client_id}", "search_surface:test"],
        reason="搜索面测试",
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
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ready', ?, ?, 'search-surface-test', ?, ?)
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


def test_long_focus_is_split_into_short_queries_and_site_queries(tmp_path: Path) -> None:
    db = Database(tmp_path / "search_surface_focus.sqlite")
    _seed_client(db, client_id="client_yiyu", name="益语智库", domain="公益组织数字化")
    long_focus = "益语智库/顾源源的观点、文章、案例，以及官网（www.yiyu.love）的益语介绍、公开服务对象和合作案例。"
    _seed_focus(db, client_id="client_yiyu", profile=[long_focus])

    result = generate_intelligence_search_intents(
        db,
        ai_service=None,
        scope_type="client",
        scope_id="client_yiyu",
        content_kind="profile_completion",
        force=True,
    )
    queries = [item.query for item in result.intents if item.content_kind == "profile_completion"]

    assert len(queries) > 12
    assert all(len(query) <= 88 for query in queries)
    assert not any(long_focus in query for query in queries)
    assert any("顾源源" in query and "观点" in query for query in queries)
    assert any(query.startswith("site:yiyu.love") for query in queries)


def test_basic_profile_gaps_are_searched_even_with_narrow_focus(tmp_path: Path) -> None:
    db = Database(tmp_path / "search_surface_gaps.sqlite")
    _seed_client(db, client_id="client_rici", name="广东省日慈公益基金会")
    _seed_focus(db, client_id="client_rici", profile=["心灵魔法学院、心盛计划、张真采访。"])

    result = generate_intelligence_search_intents(
        db,
        ai_service=None,
        scope_type="client",
        scope_id="client_rici",
        content_kind="profile_completion",
        force=True,
    )
    text = "\n".join(f"{item.query} {item.reason}" for item in result.intents)

    for expected in ("机构简介", "登记信息", "年报/信息公开", "项目介绍", "项目成效", "合作方", "执行方法", "负责人/团队"):
        assert expected in text
    assert "心灵魔法学院" in text
    assert "重点关注" in text


def test_profile_search_relaxes_after_many_no_results(tmp_path: Path) -> None:
    db = Database(tmp_path / "search_surface_relax.sqlite")
    _seed_client(db, client_id="client_rici", name="广东省日慈公益基金会")
    for index in range(9):
        db.execute(
            """
            INSERT INTO intelligence_fetch_jobs(
                id, scope_type, scope_id, client_id, project_module_id, content_kind, trigger_source,
                provider, source_config_id, query, status, raw_count, deduped_count, candidate_count,
                sample_hits_json, failure_reason, duration_ms, created_at
            )
            VALUES(?, 'client', 'client_rici', 'client_rici', NULL, 'profile_completion', 'manual',
                'public_search', NULL, ?, 'no_results', 0, 0, 0, '[]', '', 1, ?)
            """,
            (f"job_no_result_{index}", f"广东省日慈公益基金会 空搜 {index}", f"2026-05-14T10:0{index}:00"),
        )

    result = generate_intelligence_search_intents(
        db,
        ai_service=None,
        scope_type="client",
        scope_id="client_rici",
        content_kind="profile_completion",
        force=True,
    )

    assert any("search_surface:relaxed_after_no_results" in item.source_inputs for item in result.intents)
    assert any("空搜放宽" in item.reason for item in result.intents)


def test_timely_intelligence_uses_multiple_routes(tmp_path: Path) -> None:
    db = Database(tmp_path / "search_surface_timely.sqlite")
    _seed_client(db, client_id="client_rici", name="广东省日慈公益基金会")
    _seed_focus(db, client_id="client_rici", timely=["儿童青少年心理健康服务、心理平台建设、教师心理素养培训。"])

    result = generate_intelligence_search_intents(
        db,
        ai_service=None,
        scope_type="client",
        scope_id="client_rici",
        content_kind="timely_intelligence",
        force=True,
    )
    source_inputs = "\n".join(" ".join(item.source_inputs) for item in result.intents)

    for route in ("政策监管", "资助申报", "采购招标", "合作方动态", "同类机构动态", "新闻舆情"):
        assert f"timely_route:{route}" in source_inputs
    assert all(len(item.query) <= 88 for item in result.intents)


def test_candidate_refresh_reports_search_surface_diagnostics(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "search_surface_diagnostics.sqlite")
    _seed_client(db, client_id="client_rici", name="广东省日慈公益基金会")
    intent = _intent("client_rici", "广东省日慈公益基金会 心灵魔法学院", content_kind="profile_completion")
    _insert_intent(db, intent)
    monkeypatch.setattr(
        "app.services.intelligence_candidate_supply._fetch_page_text",
        lambda _url: (
            "fetched",
            "广东省日慈公益基金会官网材料提到心灵魔法学院项目，项目面向儿童青少年心理健康服务，提供课程和家庭支持。",
            "",
        ),
    )

    def fetcher(query: str, source_config) -> list[CandidateHit]:
        if "心灵魔法学院" not in query:
            return []
        return [
            CandidateHit(
                title="广东省日慈公益基金会心灵魔法学院项目介绍",
                url="https://www.rici.org.cn/projects/magic",
                snippet="广东省日慈公益基金会官网公开项目介绍。",
                source=source_config.source_name,
            )
        ]

    result = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=None,
        scope=_scope("client_rici", "广东省日慈公益基金会"),
        intents=[intent],
        max_fetch_jobs=2,
        hit_fetcher=fetcher,
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    assert result.query_count == result.fetch_job_count
    assert result.search_direction_count >= 1
    assert result.success_query_count >= 1
    assert result.effective_lead_count >= 1
