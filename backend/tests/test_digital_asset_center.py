from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.models import DigitalAssetMapNodeRecord, DigitalAssetMetricRecord
from app.services.digital_asset_center import (
    ASSET_MAP_NODES,
    AssetSource,
    _build_asset_map_node,
    _build_profile_score,
    _build_stage_summary,
    build_digital_asset_dashboard,
)


def _metric(key: str, value: int) -> DigitalAssetMetricRecord:
    return DigitalAssetMetricRecord(key=key, label=key, value=value)


def _insert_client(db: Database, client_id: str, name: str, alias: str, updated_at: str) -> None:
    db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, created_at, updated_at)
        VALUES(?, ?, ?, '公益', '战略陪伴', ?, '推进中', ?, ?)
        """,
        (client_id, name, alias, f"{name}简介", updated_at, updated_at),
    )


def _node(
    key: str,
    label: str,
    *,
    stage_index: int,
    maturity: int,
    coverage: int = 72,
    evidence_count: int = 8,
) -> DigitalAssetMapNodeRecord:
    return DigitalAssetMapNodeRecord(
        key=key,
        label=label,
        trackTitle="战略判断型" if key == "strategic_judgment" else "组织资产型",
        stageIndex=stage_index,
        coverageScore=coverage,
        maturityPercent=maturity,
        evidenceCount=evidence_count,
    )


def test_stage_progress_uses_maturity_not_next_stage_opportunity_gap() -> None:
    nodes = [
        _node("organization_identity", "组织身份", stage_index=2, maturity=61),
        _node("strategic_judgment", "战略判断", stage_index=2, maturity=59),
        _node("business_portfolio", "业务/项目组合", stage_index=2, maturity=57),
        _node("audience_profile", "服务对象画像", stage_index=2, maturity=55),
    ]
    metrics = [_metric("documents", 180), _metric("memoryFacts", 20), _metric("evidenceCards", 30)]

    summary = _build_stage_summary(nodes, metrics, understanding_score=78, empty_state=False)

    assert summary["assetStage"] == "结构计算期"
    assert 50 <= int(summary["stageProgress"]) <= 70


def test_digital_asset_dashboard_hides_internal_smoke_clients(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    _insert_client(db, "client_smoke_1", "安装态冒烟客户", "workspace-smoke", "2026-05-03T10:00:00")
    _insert_client(db, "client_smoke_2", "安装态冒烟客户", "workspace-smoke", "2026-05-03T11:00:00")
    _insert_client(db, "client_real", "A组织", "A组织", "2026-05-03T12:00:00")

    dashboard = build_digital_asset_dashboard(db)

    assert [client.name for client in dashboard.clients] == ["A组织"]


def test_digital_asset_dashboard_returns_pulse_and_alerts(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    now = datetime.now().replace(microsecond=0).isoformat()
    _insert_client(db, "client_smoke_1", "安装态冒烟客户", "workspace-smoke", "2026-05-03T10:00:00")
    _insert_client(db, "client_real", "研究项目", "research", now)
    for index in range(90):
        db.execute(
            """
            INSERT INTO documents(id, client_id, title, path, kind, source, excerpt, tags_json, created_at)
            VALUES(?, 'client_real', ?, ?, 'docx', 'upload', '项目 资料 介绍 活动', '[]', ?)
            """,
            (f"doc_{index}", f"项目资料_{index}", f"/tmp/doc_{index}.docx", now),
        )
    for index in range(3):
        db.execute(
            """
            INSERT INTO memory_facts(id, scope_type, scope_id, fact_key, fact_value, source_type, source_id, created_at, updated_at)
            VALUES(?, 'client', 'client_real', ?, '项目资料', 'document', ?, ?, ?)
            """,
            (f"fact_{index}", f"fact_{index}", f"doc_{index}", now, now),
        )

    dashboard = build_digital_asset_dashboard(db)

    assert dashboard.pulse.weeklyNewDocuments == 90
    assert dashboard.pulse.weeklyNewFacts == 3
    assert dashboard.pulse.activeOrganizations[0].name == "研究项目"
    assert all(item.name != "安装态冒烟客户" for item in dashboard.pulse.activeOrganizations)
    assert dashboard.pulse.assetAlerts
    assert dashboard.pulse.digestionFunnel[0].label == "资料归档"


def test_stage_progress_does_not_get_full_score_from_file_volume() -> None:
    nodes = [
        _node("organization_identity", "组织身份", stage_index=1, maturity=22, evidence_count=3),
        _node("business_portfolio", "业务/项目组合", stage_index=1, maturity=24, evidence_count=3),
    ]
    metrics = [_metric("documents", 120), _metric("memoryFacts", 0), _metric("evidenceCards", 0)]

    summary = _build_stage_summary(nodes, metrics, understanding_score=45, empty_state=False)

    assert summary["assetStage"] == "项目画像期"
    assert int(summary["stageProgress"]) < 50


def test_stage_progress_empty_client_stays_zero() -> None:
    summary = _build_stage_summary([], [], understanding_score=0, empty_state=True)

    assert summary["assetStage"] == "资料整理期"
    assert summary["stageProgress"] == 0


def test_node_maturity_rewards_evidence_chain_not_file_count_only() -> None:
    definition = next(node for node in ASSET_MAP_NODES if node.key == "strategic_judgment")
    thin_sources = [
        AssetSource(
            "document",
            "doc_1",
            "战略判断年度复盘表",
            "战略 命题 目标 判断 结论 依据 证据 时间 2026 年度 验证 结果 字段 表格",
        )
        for _ in range(24)
    ]
    rich_sources = [
        *thin_sources,
        *[
            AssetSource(
                "evidence",
                f"evidence_{index}",
                "战略判断证据卡",
                "战略 判断 依据 后续事实 验证 结果 复盘",
            )
            for index in range(6)
        ],
        AssetSource("theme", "theme_1", "战略主题簇", "战略 判断 版本 变化 复盘"),
        AssetSource("judgment", "judgment_1", "战略判断版本", "战略 判断 时间 依据 验证"),
    ]

    thin = _build_asset_map_node("测试组织", definition, thin_sources)
    rich = _build_asset_map_node("测试组织", definition, rich_sources)

    assert rich.maturityPercent >= thin.maturityPercent + 5
    assert rich.maturityPercent < 100


def test_typed_score_keeps_many_weak_files_below_structure_stage() -> None:
    sources = [
        AssetSource("document", f"doc_{index}", f"项目资料_{index}.docx", "项目 资料 介绍 活动")
        for index in range(80)
    ]
    metrics = [_metric("documents", 120), _metric("memoryFacts", 0), _metric("evidenceCards", 0)]

    result = _build_profile_score("测试组织", sources, metrics, [], empty_state=False)

    assert result.deposit_thickness >= 50
    assert result.maturity_score < 45
    assert result.asset_stage in {"资料整理期", "项目画像期"}


def test_typed_score_recognizes_platform_ecosystem_with_yearly_evaluations() -> None:
    sources = [
        AssetSource("document", "doc_2019", "2019年会评估报告", "论坛 年会 行业 机构 参与 反馈 评估 年度 2019 结果"),
        AssetSource("document", "doc_2020", "2020年会评估报告", "论坛 年会 行业 机构 参与 反馈 评估 年度 2020 结果"),
        AssetSource("document", "doc_2023", "2023年会评估报告", "论坛 年会 行业 机构 参与 反馈 评估 年度 2023 改进"),
        AssetSource("document", "doc_strategy", "平台战略规划", "平台 定位 行业 生态 服务 目标 战略 判断"),
        AssetSource("evidence", "e_1", "年会评估证据", "年会 反馈 结果 证据"),
        AssetSource("theme", "t_1", "行业生态主题", "行业 生态 机构 伙伴 变化"),
        AssetSource("judgment", "j_1", "平台战略判断", "战略 判断 依据 后续事实 验证"),
    ]
    metrics = [
        _metric("documents", 12),
        _metric("memoryFacts", 2),
        _metric("evidenceCards", 8),
        _metric("themeClusters", 2),
        _metric("openQuestions", 1),
        _metric("judgments", 2),
    ]

    result = _build_profile_score("测试平台", sources, metrics, [], empty_state=False)

    assert result.asset_profile_type == "平台/行业生态型"
    assert result.score_breakdown.timeContinuity >= 45
    assert result.score_breakdown.evidenceChain >= 45
    assert result.maturity_score >= 50


def test_typed_score_recognizes_field_research_but_caps_without_evidence_chain() -> None:
    sources = [
        AssetSource("document", "report", "云南儿童资助研究报告", "研究 报告 调研 儿童 社区 个案 样本 章节 需求 2024"),
        AssetSource("document", "case", "里布嘎社区儿童个案案例", "个案 案例 儿童 社区 服务 变化 反馈"),
        AssetSource("document", "signup", "工作坊报名表.xlsx", "报名 表格 xlsx 机构 参与 时间 反馈"),
    ]
    metrics = [_metric("documents", 260), _metric("memoryFacts", 18), _metric("evidenceCards", 0), _metric("themeClusters", 0), _metric("judgments", 0)]

    result = _build_profile_score("研究项目", sources, metrics, [], empty_state=False)

    assert result.asset_profile_type == "研究报告/田野型"
    assert result.deposit_thickness >= 60
    assert result.score_breakdown.evidenceChain < 45
    assert result.asset_stage == "项目画像期"


def test_typed_score_recognizes_content_asset_not_org_project() -> None:
    sources = [
        AssetSource("document", "a1", "B站视频资料.md", "视频 内容 发布 B站 观点 人口 研究 转写"),
        AssetSource("document", "a2", "真正拉开差距的不是更努力.docx", "文章 观点 内容 管理 职场 写作"),
        AssetSource("document", "a3", "西门庆真正没看明白的.docx", "文章 观点 内容 商业 战略 思考"),
    ]
    metrics = [_metric("documents", 23), _metric("evidenceCards", 0), _metric("themeClusters", 0), _metric("judgments", 0)]

    result = _build_profile_score("文章库", sources, metrics, [], empty_state=False)

    assert result.asset_profile_type == "内容/IP资产型"
    assert result.maturity_score < 35
    assert all("重点项目年度结果" not in row.missingSummary for row in result.material_rows)


def test_typed_score_rewards_tables_feedback_and_judgment_evidence() -> None:
    weak_sources = [
        AssetSource("document", "intro", "项目介绍", "公益项目 教师 学校 活动 介绍"),
    ]
    rich_sources = [
        *weak_sources,
        AssetSource("document", "signup", "项目报名反馈表.xlsx", "报名 表格 xlsx 教师 学校 参与 时间 反馈 满意度 结果 2024"),
        AssetSource("document", "outcome", "项目年度成效评估", "项目 年度 成效 评估 反馈 案例 结果 复盘 2025"),
        AssetSource("evidence", "evidence", "成效证据卡", "反馈 结果 证据 项目 成效"),
        AssetSource("theme", "theme", "项目反馈主题", "反馈 主题 需求 变化"),
        AssetSource("judgment", "judgment", "项目判断版本", "判断 依据 后续事实 验证 结果"),
    ]
    metrics_weak = [_metric("documents", 12), _metric("evidenceCards", 0), _metric("themeClusters", 0), _metric("judgments", 0)]
    metrics_rich = [_metric("documents", 12), _metric("evidenceCards", 6), _metric("themeClusters", 2), _metric("judgments", 2)]

    weak = _build_profile_score("公益项目", weak_sources, metrics_weak, [], empty_state=False)
    rich = _build_profile_score("公益项目", rich_sources, metrics_rich, [], empty_state=False)

    assert rich.score_breakdown.computable > weak.score_breakdown.computable
    assert rich.score_breakdown.evidenceChain > weak.score_breakdown.evidenceChain
    assert rich.maturity_score > weak.maturity_score


def test_typed_score_keeps_public_project_as_secondary_when_strategy_overrides_primary() -> None:
    sources = [
        AssetSource("document", "intro", "组织战略规划", "战略 使命 定位 判断 规划 目标 公益项目"),
        AssetSource("document", "project", "教师服务项目反馈表.xlsx", "项目 教师 学校 报名 参与 反馈 成效 年度 结果"),
        AssetSource("evidence", "evidence", "战略判断证据卡", "战略 判断 依据 验证 结果"),
        AssetSource("judgment", "judgment", "战略判断版本", "战略 判断 后续事实 复盘"),
    ]
    metrics = [_metric("documents", 30), _metric("evidenceCards", 6), _metric("themeClusters", 1), _metric("judgments", 2)]

    result = _build_profile_score("基金会", sources, metrics, [], empty_state=False)

    assert result.asset_profile_type == "组织战略陪伴型"
    assert "公益项目运营型" in result.secondary_profile_types
