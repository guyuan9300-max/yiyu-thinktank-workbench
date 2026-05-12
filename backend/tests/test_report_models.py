"""报告生成器（report-gen）· R0.5 数据契约测试。

对应执行计划：docs/报告生成器-Claude-Code执行计划-2026-05-12.md

只验证 Pydantic 模型本身、字段约束、序列化/反序列化往返。
不测 LLM、不测 API、不测 DB（那些是 R1/R2/R3 的事）。
"""

from __future__ import annotations

import json

import pytest

from app.models import (
    ChartHint,
    CitationRef,
    DraftBlueprintRequest,
    DraftSectionsRequest,
    GeneratedChart,
    ReportArtifact,
    ReportBlueprint,
    ReportRunSummary,
    SectionContent,
    SectionPlan,
)


class TestChartHint:
    def test_minimal_construction(self) -> None:
        hint = ChartHint(
            kind="pie",
            title="commit 类型占比",
            data_source_hint="git log Q1 commit 类型计数",
        )
        assert hint.kind == "pie"
        assert hint.caption is None

    def test_kind_constraint(self) -> None:
        with pytest.raises(Exception):
            ChartHint(kind="invalid_kind", title="x", data_source_hint="y")  # type: ignore[arg-type]

    def test_all_5_chart_kinds_accepted(self) -> None:
        for kind in ("pie", "progress_bar_h", "timeline", "grouped_bar", "risk_bubble"):
            hint = ChartHint(kind=kind, title="t", data_source_hint="ds")  # type: ignore[arg-type]
            assert hint.kind == kind

    def test_special_kinds_no_chart(self) -> None:
        for kind in ("table_only", "callout_only"):
            hint = ChartHint(kind=kind, title="t", data_source_hint="ds")  # type: ignore[arg-type]
            assert hint.kind == kind


class TestSectionPlan:
    def test_minimal(self) -> None:
        plan = SectionPlan(title="本期摘要", goal="读者快速了解整期进展")
        assert plan.level == 1
        assert plan.citation_budget == 5
        assert plan.estimated_words == 300
        assert plan.chart_hints == []

    def test_level_constraint(self) -> None:
        SectionPlan(title="a", goal="b", level=1)
        SectionPlan(title="a", goal="b", level=2)
        with pytest.raises(Exception):
            SectionPlan(title="a", goal="b", level=3)
        with pytest.raises(Exception):
            SectionPlan(title="a", goal="b", level=0)

    def test_estimated_words_bounds(self) -> None:
        SectionPlan(title="a", goal="b", estimated_words=50)
        SectionPlan(title="a", goal="b", estimated_words=2000)
        with pytest.raises(Exception):
            SectionPlan(title="a", goal="b", estimated_words=49)
        with pytest.raises(Exception):
            SectionPlan(title="a", goal="b", estimated_words=2001)

    def test_with_charts(self) -> None:
        plan = SectionPlan(
            title="风险分析",
            goal="标出本期 5 大风险并评估应对",
            chart_hints=[
                ChartHint(kind="risk_bubble", title="风险矩阵", data_source_hint="open issues"),
            ],
            citation_budget=8,
            estimated_words=600,
        )
        assert len(plan.chart_hints) == 1
        assert plan.chart_hints[0].kind == "risk_bubble"


class TestReportBlueprint:
    def test_minimal(self) -> None:
        bp = ReportBlueprint(
            title="日慈 Q1 战略陪伴报告",
            report_kind="战略陪伴季报",
            audience="客户决策层",
            tone="专业冷静",
            period_start="2026-01-01",
            period_end="2026-03-31",
            inferred_theme="客户处于战略转折期，需要保持节奏与重点对齐",
            client_id="client_rici",
            generated_at="2026-05-12T16:00:00",
        )
        assert bp.confidence == 0.8
        assert bp.open_questions_for_human == []
        assert bp.sections == []

    def test_with_sections(self) -> None:
        bp = ReportBlueprint(
            title="x",
            report_kind="y",
            audience="z",
            tone="t",
            period_start="2026-01-01",
            period_end="2026-03-31",
            inferred_theme="θ",
            client_id="c",
            generated_at="2026-05-12T16:00:00",
            sections=[
                SectionPlan(title="s1", goal="g1"),
                SectionPlan(title="s2", goal="g2", level=2),
            ],
        )
        assert len(bp.sections) == 2

    def test_confidence_bounds(self) -> None:
        common_kwargs = {
            "title": "t",
            "report_kind": "k",
            "audience": "a",
            "tone": "to",
            "period_start": "2026-01-01",
            "period_end": "2026-03-31",
            "inferred_theme": "θ",
            "client_id": "c",
            "generated_at": "ts",
        }
        ReportBlueprint(**common_kwargs, confidence=0.0)  # type: ignore[arg-type]
        ReportBlueprint(**common_kwargs, confidence=1.0)  # type: ignore[arg-type]
        with pytest.raises(Exception):
            ReportBlueprint(**common_kwargs, confidence=1.1)  # type: ignore[arg-type]
        with pytest.raises(Exception):
            ReportBlueprint(**common_kwargs, confidence=-0.1)  # type: ignore[arg-type]

    def test_json_roundtrip(self) -> None:
        bp_original = ReportBlueprint(
            title="x",
            report_kind="y",
            audience="z",
            tone="t",
            period_start="2026-01-01",
            period_end="2026-03-31",
            inferred_theme="θ",
            client_id="c",
            generated_at="ts",
            sections=[
                SectionPlan(
                    title="s",
                    goal="g",
                    data_sources=["events", "tasks"],
                    chart_hints=[ChartHint(kind="pie", title="t", data_source_hint="ds")],
                ),
            ],
        )
        as_json = bp_original.model_dump_json()
        bp_restored = ReportBlueprint.model_validate_json(as_json)
        assert bp_restored == bp_original


class TestCitationRef:
    def test_all_types(self) -> None:
        for t in ("judgment", "event", "task", "document", "metric", "commit"):
            cr = CitationRef(type=t, id="x", label="L")  # type: ignore[arg-type]
            assert cr.type == t

    def test_excerpt_optional(self) -> None:
        cr = CitationRef(type="event", id="evt_1", label="2026-Q1 启动会")
        assert cr.excerpt is None


class TestSectionContent:
    def test_minimal(self) -> None:
        plan = SectionPlan(title="s", goal="g")
        content = SectionContent(plan=plan, markdown="## 第一段\n正文...")
        assert content.confidence == 0.7
        assert content.citations == []
        assert content.charts == []
        assert content.warnings == []
        assert content.data_source_annotation == ""

    def test_with_citations_and_charts(self) -> None:
        plan = SectionPlan(
            title="s",
            goal="g",
            chart_hints=[ChartHint(kind="pie", title="t", data_source_hint="ds")],
        )
        content = SectionContent(
            plan=plan,
            markdown="正文 [^evt_1]",
            citations=[CitationRef(type="event", id="evt_1", label="L1")],
            charts=[
                GeneratedChart(
                    hint=plan.chart_hints[0],
                    png_bytes_base64="iVBORw0KGgo=",  # 假数据
                ),
            ],
            data_source_annotation="数据来源：事件线 entry evt_1",
        )
        assert len(content.citations) == 1
        assert len(content.charts) == 1
        assert content.charts[0].width_cm == 14.5


class TestReportArtifact:
    def test_minimal(self) -> None:
        bp = ReportBlueprint(
            title="x",
            report_kind="y",
            audience="z",
            tone="t",
            period_start="2026-01-01",
            period_end="2026-03-31",
            inferred_theme="θ",
            client_id="c",
            generated_at="ts",
        )
        artifact = ReportArtifact(blueprint=bp, generated_at="ts2")
        assert artifact.sections == []
        assert artifact.output_files == {}
        assert artifact.total_llm_tokens == 0
        assert artifact.total_cost_usd == 0.0

    def test_with_outputs(self) -> None:
        bp = ReportBlueprint(
            title="x",
            report_kind="y",
            audience="z",
            tone="t",
            period_start="2026-01-01",
            period_end="2026-03-31",
            inferred_theme="θ",
            client_id="c",
            generated_at="ts",
        )
        artifact = ReportArtifact(
            blueprint=bp,
            generated_at="ts2",
            output_files={"docx": "/path/x.docx", "pdf": "/path/x.pdf"},
            total_llm_tokens=12345,
        )
        assert "docx" in artifact.output_files
        assert artifact.total_llm_tokens == 12345


class TestRequestModels:
    def test_draft_blueprint_request_minimal(self) -> None:
        # 全部字段都可选，最低限度可空构造
        req = DraftBlueprintRequest()
        assert req.event_line_id is None
        assert req.client_id is None

    def test_draft_blueprint_request_with_event_line(self) -> None:
        req = DraftBlueprintRequest(event_line_id="el_123", intent_hint="对外汇报")
        assert req.event_line_id == "el_123"
        assert req.intent_hint == "对外汇报"

    def test_draft_blueprint_request_with_period(self) -> None:
        req = DraftBlueprintRequest(
            client_id="c1",
            period_start="2026-01-01",
            period_end="2026-03-31",
        )
        assert req.client_id == "c1"

    def test_draft_sections_request_defaults(self) -> None:
        req = DraftSectionsRequest()
        assert req.section_indices is None  # 全部章节
        assert req.max_workers == 4

    def test_draft_sections_request_subset(self) -> None:
        req = DraftSectionsRequest(section_indices=[0, 2, 5], max_workers=2)
        assert req.section_indices == [0, 2, 5]
        assert req.max_workers == 2

    def test_max_workers_bounds(self) -> None:
        DraftSectionsRequest(max_workers=1)
        DraftSectionsRequest(max_workers=8)
        with pytest.raises(Exception):
            DraftSectionsRequest(max_workers=0)
        with pytest.raises(Exception):
            DraftSectionsRequest(max_workers=9)


class TestReportRunSummary:
    def test_minimal(self) -> None:
        summary = ReportRunSummary(
            id="run_001",
            client_id="c1",
            event_line_id=None,
            period_start=None,
            period_end=None,
            intent_hint=None,
            status="blueprint_pending",
            blueprint=None,
            created_at="2026-05-12T16:00:00",
            updated_at="2026-05-12T16:00:00",
        )
        assert summary.sections_status == []
        assert summary.output_files == {}
        assert summary.total_llm_tokens == 0

    def test_with_full_state(self) -> None:
        bp = ReportBlueprint(
            title="x",
            report_kind="y",
            audience="z",
            tone="t",
            period_start="2026-01-01",
            period_end="2026-03-31",
            inferred_theme="θ",
            client_id="c",
            generated_at="ts",
        )
        summary = ReportRunSummary(
            id="run_001",
            client_id="c1",
            event_line_id="el_1",
            period_start="2026-01-01",
            period_end="2026-03-31",
            intent_hint="对外汇报",
            status="drafting",
            blueprint=bp,
            sections_status=["done", "drafting", "pending"],
            output_files={"docx": "/path/x.docx"},
            total_llm_tokens=8000,
            created_at="2026-05-12T16:00:00",
            updated_at="2026-05-12T16:00:10",
        )
        assert summary.status == "drafting"
        assert summary.sections_status == ["done", "drafting", "pending"]


class TestEndToEndJsonRoundtrip:
    """完整流程序列化/反序列化往返：保证 API 传输不丢字段。"""

    def test_blueprint_to_artifact_roundtrip(self) -> None:
        bp = ReportBlueprint(
            title="日慈 Q1 战略陪伴报告",
            subtitle="2026 年首个季度的关键判断与下一步建议",
            report_kind="战略陪伴季报",
            audience="客户决策层",
            tone="专业冷静",
            period_start="2026-01-01",
            period_end="2026-03-31",
            inferred_theme="客户处于战略转折期",
            confidence=0.85,
            open_questions_for_human=["客户方是否希望本期重点 vs 上期对比？"],
            event_line_id="el_rici_q1",
            client_id="client_rici",
            generated_at="2026-05-12T16:00:00",
            sections=[
                SectionPlan(
                    level=1,
                    title="本期摘要",
                    goal="一页读完整期进展",
                    data_sources=["confirmedJudgments", "events"],
                    citation_budget=3,
                    estimated_words=200,
                ),
                SectionPlan(
                    level=1,
                    title="战略目标进展",
                    goal="逐目标说明完成度",
                    data_sources=["tasks", "events"],
                    chart_hints=[
                        ChartHint(
                            kind="progress_bar_h",
                            title="目标完成度",
                            data_source_hint="目标 tasks 完成数 / 总数",
                        ),
                    ],
                    citation_budget=5,
                    estimated_words=500,
                ),
            ],
        )

        content_1 = SectionContent(
            plan=bp.sections[0],
            markdown="## 概览\n本期完成 X 项关键判断 [^j_1]，...",
            citations=[CitationRef(type="judgment", id="j_1", label="判断 #1")],
            data_source_annotation="数据来源：confirmedJudgments[j_1], events 2026-01-01~03-31",
        )
        content_2 = SectionContent(
            plan=bp.sections[1],
            markdown="## 目标 1\n完成度 70% [CHART:0]...",
            citations=[CitationRef(type="task", id="task_42", label="任务 #42")],
            charts=[
                GeneratedChart(
                    hint=bp.sections[1].chart_hints[0],
                    png_bytes_base64="iVBORw0KGgo=",
                ),
            ],
            data_source_annotation="数据来源：tasks status 统计",
        )

        artifact = ReportArtifact(
            blueprint=bp,
            sections=[content_1, content_2],
            output_files={"docx": "/path/q1.docx"},
            generated_at="2026-05-12T16:05:00",
            total_llm_tokens=15800,
            total_cost_usd=0.45,
        )

        # JSON 往返
        as_json = artifact.model_dump_json()
        restored = ReportArtifact.model_validate_json(as_json)
        assert restored == artifact

        # JSON 字段健全检查
        parsed = json.loads(as_json)
        assert parsed["blueprint"]["confidence"] == 0.85
        assert len(parsed["sections"]) == 2
        assert parsed["sections"][1]["charts"][0]["png_bytes_base64"] == "iVBORw0KGgo="
