from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("YIYU_WORKBENCH_DATA_DIR", tempfile.mkdtemp(prefix="yiyu-profile-gap-tests-"))

from app.db import Database, to_json
from app.models import AiStructuredResponse
from app.services import intelligence_candidate_supply as supply
from app.services.intelligence_candidate_supply import CandidateHit, run_intelligence_candidate_refresh
from app.services.intelligence_search_intents import GeneratedSearchIntent, IntelligenceSearchScope, generate_intelligence_search_intents


def _seed_client(db: Database, *, client_id: str = "client_gap", name: str = "广州样本公益中心") -> None:
    db.execute(
        """
        INSERT OR REPLACE INTO clients(id, name, alias, domain, type, intro, stage, color, created_at, updated_at)
        VALUES(?, ?, ?, '儿童心理健康', 'foundation', '面向困境儿童提供心理健康服务', 'active', '#5B7BFE',
            '2026-05-15T09:00:00', '2026-05-15T09:00:00')
        """,
        (client_id, name, name),
    )


def _seed_focus(db: Database, *, client_id: str, profile: list[str]) -> None:
    db.execute(
        """
        INSERT OR REPLACE INTO intelligence_focus_directives(
            id, scope_type, scope_id, profile_completion_focus_json, timely_intelligence_focus_json,
            exclude_json, created_at, updated_at
        )
        VALUES(?, 'client', ?, ?, '[]', '[]', '2026-05-15T09:00:00', '2026-05-15T09:00:00')
        """,
        (f"focus_{client_id}", client_id, to_json(profile)),
    )


def _scope(client_id: str = "client_gap", name: str = "广州样本公益中心") -> IntelligenceSearchScope:
    return IntelligenceSearchScope(
        scope_type="client",
        scope_id=client_id,
        client_id=client_id,
        project_module_id=None,
        display_name=name,
    )


def _intent(client_id: str, query: str, *, intent_id: str = "intent_profile_gap") -> GeneratedSearchIntent:
    return GeneratedSearchIntent(
        id=intent_id,
        scope_type="client",
        scope_id=client_id,
        client_id=client_id,
        project_module_id=None,
        content_kind="profile_completion",
        query=query,
        exclude_terms=[],
        source_inputs=[f"client:{client_id}", "profile_gap:test"],
        reason="资料补全缺口图谱测试",
        priority=99,
        status="ready",
        input_hash=f"hash_{intent_id}",
        expires_at="2026-05-16T00:00:00",
    )


def _insert_intent(db: Database, intent: GeneratedSearchIntent) -> None:
    db.execute(
        """
        INSERT INTO intelligence_search_intents(
            id, scope_type, scope_id, client_id, project_module_id, content_kind, query,
            exclude_terms_json, source_inputs_json, reason, priority, status,
            input_hash, expires_at, generator_version, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ready', ?, ?, 'profile-gap-test', ?, ?)
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
            "2026-05-15T09:00:00",
            "2026-05-15T09:00:00",
        ),
    )


class _ProfileAi:
    def get_health(self):
        return type("Health", (), {"ready": True, "provider": "doubao"})()

    def generate_general_fallback(self, *_args, **_kwargs):
        return AiStructuredResponse(
            content="资料摘要：该官网页面同时提供机构定位、项目服务和团队信息，可拆分补齐多个资料维度。",
            analysis=(
                "可复用事实：\n"
                "- 广州样本公益中心官网介绍其宗旨和定位，可补充机构简介。\n"
                "- 广州样本公益中心的儿童心理服务项目面向困境儿童，可补充项目介绍和服务对象。\n"
                "- 广州样本公益中心网页列出负责人李明和项目团队，可补充负责人/团队。"
            ),
            judgment="证据缺口：仍需核验年报、登记信息和项目成效。",
            actions="",
            timeline="",
        )


def test_profile_gap_map_keeps_basic_gaps_and_splits_focus(tmp_path: Path) -> None:
    db = Database(tmp_path / "gap_map.sqlite")
    _seed_client(db)
    _seed_focus(db, client_id="client_gap", profile=["官网（www.sample-foundation.org）介绍、儿童心理服务项目、团队负责人。"])

    result = generate_intelligence_search_intents(
        db,
        ai_service=None,
        scope_type="client",
        scope_id="client_gap",
        content_kind="profile_completion",
        force=True,
    )
    text = "\n".join(f"{item.query} {item.reason} {' '.join(item.source_inputs)}" for item in result.intents)

    assert "登记信息" in text
    assert "年报/信息公开" in text
    assert "官网与栏目" in text
    assert "重点关注" in text
    assert any(item.query.startswith("site:sample-foundation.org") for item in result.intents)
    assert not any("官网（www.sample-foundation.org）介绍、儿童心理服务项目、团队负责人" in item.query for item in result.intents)


def test_profile_site_query_only_uses_official_sources(tmp_path: Path) -> None:
    db = Database(tmp_path / "site_routing.sqlite")
    _seed_client(db)
    scope = _scope()
    configs = supply.ensure_default_source_configs(db, scope)
    db.execute(
        """
        INSERT INTO intelligence_source_configs(
            id, scope_type, scope_id, client_id, project_module_id, source_type, source_name,
            source_url_template, content_kinds_json, region, reliability_tier, priority, enabled,
            discovery_source, discovery_reason, discovery_samples_json, health_score, last_status, created_at, updated_at
        )
        VALUES('isrc_official_test', 'client', 'client_gap', 'client_gap', NULL, 'official_site',
            '用户官网：sample-foundation.org', 'site:sample-foundation.org {query}', '["profile_completion"]',
            '全国', 'strong', 100, 1, 'test', '', '[]', 90, 'unknown', '2026-05-15T09:00:00', '2026-05-15T09:00:00')
        """
    )
    intent = _intent("client_gap", "site:sample-foundation.org 机构简介", intent_id="intent_site_only")

    tasks = supply._selected_fetch_tasks(db, [intent], configs + supply.ensure_default_source_configs(db, scope), max_fetch_jobs=20)

    assert tasks
    assert {config.source_type for _intent_item, config in tasks} <= {"official_site", "official_site_section"}


def test_profile_one_page_can_create_multiple_dimension_cards(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "multi_card.sqlite")
    _seed_client(db)
    scope = _scope()
    intent = _intent("client_gap", "广州样本公益中心 官网 项目 团队", intent_id="intent_multi")
    _insert_intent(db, intent)
    monkeypatch.setattr(
        supply,
        "_fetch_page_text",
        lambda _url: (
            "fetched",
            "广州样本公益中心官网介绍其宗旨和定位。广州样本公益中心儿童心理服务项目面向困境儿童，覆盖社区和学校。"
            "广州样本公益中心网页列出负责人李明和项目团队，并介绍课程、培训和活动方法。",
            "",
        ),
    )

    result = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=_ProfileAi(),
        scope=scope,
        intents=[intent],
        max_fetch_jobs=1,
        hit_fetcher=lambda _query, source_config: [
            CandidateHit(
                title="广州样本公益中心官网介绍",
                url="https://sample-foundation.org/about",
                snippet="广州样本公益中心官网公开机构、项目和团队介绍。",
                source=source_config.source_name,
            )
        ],
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    assert result.promoted_count == 1
    assert result.profile_fact_card_count >= 3
    rows = db.fetchall("SELECT source_url, tags_json, key_points_json FROM intelligence_items WHERE scope_id='client_gap' ORDER BY title")
    assert len(rows) >= 3
    assert {row["source_url"] for row in rows} == {"https://sample-foundation.org/about"}
    tag_text = "\n".join(str(row["tags_json"]) for row in rows)
    assert "机构简介" in tag_text
    assert "项目介绍" in tag_text
    assert "负责人/团队" in tag_text
    assert "已围绕标题" not in "\n".join(str(row["key_points_json"]) for row in rows)


def test_profile_same_page_same_fact_is_not_duplicated_on_second_run(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "duplicate_fact.sqlite")
    _seed_client(db)
    scope = _scope()
    intent = _intent("client_gap", "广州样本公益中心 官网 项目 团队", intent_id="intent_duplicate_fact")
    _insert_intent(db, intent)
    monkeypatch.setattr(
        supply,
        "_fetch_page_text",
        lambda _url: (
            "fetched",
            "广州样本公益中心官网介绍其宗旨和定位。广州样本公益中心儿童心理服务项目面向困境儿童。"
            "广州样本公益中心网页列出负责人李明和项目团队。",
            "",
        ),
    )
    fetcher = lambda _query, source_config: [
        CandidateHit(
            title="广州样本公益中心官网介绍",
            url="https://sample-foundation.org/about",
            snippet="广州样本公益中心官网公开机构、项目和团队介绍。",
            source=source_config.source_name,
        )
    ]

    first = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=_ProfileAi(),
        scope=scope,
        intents=[intent],
        max_fetch_jobs=1,
        hit_fetcher=fetcher,
        official_site_hit_fetcher=lambda _query, _config: [],
    )
    before = db.scalar("SELECT COUNT(1) FROM intelligence_items WHERE scope_id='client_gap'")
    second = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=_ProfileAi(),
        scope=scope,
        intents=[intent],
        max_fetch_jobs=1,
        hit_fetcher=fetcher,
        official_site_hit_fetcher=lambda _query, _config: [],
    )
    after = db.scalar("SELECT COUNT(1) FROM intelligence_items WHERE scope_id='client_gap'")

    assert first.profile_fact_card_count >= 3
    assert second.profile_fact_card_count == 0
    assert after == before
