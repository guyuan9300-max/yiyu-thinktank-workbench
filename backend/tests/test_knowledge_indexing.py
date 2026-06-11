from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.knowledge_base import (
    build_catalog_search_text,
    build_coverage_terms,
    clean_title_for_search,
    finance_chunk_score_adjustment,
    finance_document_score_adjustment,
    is_finance_query,
    is_finance_statement_query,
    load_surrogate_retrieval_text,
)


def test_clean_title_for_search_strips_import_suffix_noise():
    assert clean_title_for_search("基业长青2022年财务报告_测试论坛A_20260211.pdf") == "基业长青2022年财务报告"
    assert clean_title_for_search("测试论坛A_项目价值分析表 2_测试论坛A_20260211.pdf") == "测试论坛A 项目价值分析表"


def test_build_catalog_search_text_prefers_summary_and_body_over_placeholder_noise():
    catalog = build_catalog_search_text(
        title="测试论坛A文件+机构和业务简介-CFF2025年会手册_测试论坛A_20260211.md",
        short_summary="测试论坛A 的核心业务包括行业网络、数据资产和知识服务。",
        summary="这份材料系统介绍了机构定位、核心业务、行业角色与未来能力版图。",
        raw_text="测试论坛A正在从传统信息平台转向公益慈善行业的可信基础设施，围绕网络、数据与知识形成三层底盘，并以行业服务、研究倡导、共创交付等方式形成长期复利。",
        keywords=["测试论坛A", "机构介绍", "核心业务"],
        entities=["测试论坛A", "测试论坛A"],
        primary_category="组织与战略",
        secondary_category="战略规划",
        document_role="机构介绍",
    )
    assert "可作为后续问答与证据引用来源" not in catalog
    assert "测试论坛A 的核心业务包括行业网络、数据资产和知识服务" in catalog
    assert "可信基础设施" in catalog


def test_load_surrogate_retrieval_text_excludes_query_hint_sections(tmp_path: Path):
    surrogate = tmp_path / "surrogate.md"
    surrogate.write_text(
        "\n".join(
            [
                "# 示例文档",
                "",
                "- source_type: document",
                "- folder_category: 组织与战略",
                "- document_role: 机构介绍",
                "",
                "## overview_summary",
                "这是机构介绍摘要。",
                "",
                "## source_outline",
                "这里有真正的正文骨架。",
                "",
                "## query_hints",
                "- 不该进入 surrogate 检索正文",
                "",
                "## core_questions",
                "- 这也不该进入 surrogate 检索正文",
            ]
        ),
        encoding="utf-8",
    )
    retrieval_text = load_surrogate_retrieval_text(surrogate)
    assert "真正的正文骨架" in retrieval_text
    assert "不该进入 surrogate 检索正文" not in retrieval_text


def test_build_coverage_terms_keeps_finance_anchor_tokens_for_chunk_matching():
    tokens = ["财务情况如何", "财务情况", "情况如何", "财务", "情况", "如何"]
    coverage_terms = build_coverage_terms("财务情况如何？", tokens, ["财务与筹款"])
    assert coverage_terms[0] == "财务"
    assert "财务" in coverage_terms
    assert len(coverage_terms) <= 8


def test_is_finance_query_detects_statement_style_questions():
    assert is_finance_query("分析测试论坛A的财务状况")
    assert is_finance_query("有没有资产负债和现金流信息")
    assert not is_finance_query("介绍测试论坛A的团队")


def test_is_finance_statement_query_detects_actual_statement_questions():
    assert is_finance_statement_query("分析测试论坛A的财务状况")
    assert is_finance_statement_query("有没有资产负债和现金流信息")
    assert not is_finance_statement_query("预算规划怎么做")


def test_finance_document_score_adjustment_prefers_finance_reports_over_generic_intro_docs():
    finance_score = finance_document_score_adjustment(
        title="基业长青2023年财务报告_测试论坛A_20260211.pdf",
        summary="包含资产总额、负债总额、收入总额与费用总额。",
        document_role="财务资料",
        folder_category="财务与筹款",
        path="/tmp/财务与筹款/基业长青2023年财务报告_测试论坛A_20260211.pdf",
        statement_mode=True,
    )
    generic_score = finance_document_score_adjustment(
        title="测试论坛A核心业务介绍 2_测试论坛A_20260211.pdf",
        summary="介绍五个主要项目与平台化方向。",
        document_role="会议与访谈",
        folder_category="项目与业务",
        path="/tmp/项目与业务/测试论坛A核心业务介绍_2_测试论坛A_20260211.pdf",
        statement_mode=True,
    )
    assert finance_score > generic_score


def test_finance_chunk_score_adjustment_prefers_numeric_finance_chunks():
    finance_chunk = finance_chunk_score_adjustment(
        title="3 基业长青2023年财务报告_测试论坛A_20260211.pdf",
        excerpt="截止 2023 年 12 月 31 日，中心资产总额 751.44 万元，负债总额 42.62 万元，收入总额 880.51 万元。",
        section_label="第 1 页",
        path="/tmp/财务与筹款/3 基业长青2023年财务报告_测试论坛A_20260211.pdf",
        statement_mode=True,
    )
    generic_chunk = finance_chunk_score_adjustment(
        title="测试论坛A核心业务介绍 2_测试论坛A_20260211.pdf",
        excerpt="介绍年会、峰会、图书馆、数据平台与平台化方向。",
        section_label="概览",
        path="/tmp/项目与业务/测试论坛A核心业务介绍_2_测试论坛A_20260211.pdf",
        statement_mode=True,
    )
    assert finance_chunk > generic_chunk
