from __future__ import annotations

from types import SimpleNamespace

from app.services.workspace_data_center_adapter import build_dna_tool_context_from_workspace


def _module(module_key: str, title: str, text: str, *, source_kind: str = "manual") -> SimpleNamespace:
    return SimpleNamespace(
        clientId="client_rici",
        moduleKey=module_key,
        title=title,
        summary=text[:240],
        normalizedText=text,
        markdownContent=text,
        sourceKind=source_kind,
        updatedAt="2026-05-04T10:00:00",
        hasDocument=True,
    )


def test_strategy_dna_tool_reads_long_context_instead_of_short_background() -> None:
    stable = _module(
        "organization_intro",
        "组织介绍",
        "日慈基金会公开定位。官网公开口径。使命愿景。L2 内部文件。" * 80,
    )
    evolving = _module(
        "business_intro",
        "战略升级与第二曲线",
        "2026 战略 第二曲线 数据资产 场域 飞轮 待证据确认 自动升级 自动降级 边界。" * 160,
    )
    workspace = SimpleNamespace(dnaModules=[stable, evolving])

    context = build_dna_tool_context_from_workspace(
        workspace,
        prompt="日慈基金会的战略核心是什么？",
        max_chars=12000,
    )

    assert context.purpose == "strategy"
    assert context.context_chars > 2200
    assert "客户 DNA 工具调用" in context.context_text
    assert "evolving_dna" in context.selected_kinds
    assert "risk_dna" in context.selected_kinds
    assert context.selected_modules


def test_asset_gap_dna_tool_prefers_gap_and_marks_unverified_numbers() -> None:
    gap = _module(
        "market_intro",
        "资料缺口与补全",
        "缺口 补全 互联网补全 用户补充 优先级。关系资产覆盖80%以上，用户活跃度达到行业平均水平。"
        "需要补官网、年报、审计报告、项目运营数据。" * 80,
    )
    stable = _module("organization_intro", "组织介绍", "稳定身份 公开口径 官网 信息。" * 40)
    workspace = SimpleNamespace(dnaModules=[stable, gap])

    context = build_dna_tool_context_from_workspace(
        workspace,
        prompt="为了让系统更懂日慈基金会，下一轮应该补哪些资料？",
        max_chars=9000,
    )

    assert context.purpose == "asset_gap"
    assert "gap_dna" in context.selected_kinds
    assert "数字/成效口径需来源核验" in context.context_text
    assert "存在已降级的无来源数字/成效表述" in context.warnings


def test_public_material_dna_tool_keeps_public_and_risk_boundaries() -> None:
    public = _module(
        "organization_intro",
        "公开介绍",
        "官网 公开 对外 民政 年报 审计。内部战略口径不得直接用于对外公开回答。未成年人 隐私 合规 边界。" * 90,
    )
    evolving = _module("business_intro", "任务事件线", "任务 事件线 当前 下一步 战略陪伴。" * 90)
    workspace = SimpleNamespace(dnaModules=[evolving, public])

    context = build_dna_tool_context_from_workspace(
        workspace,
        prompt="生成一段对外合作材料",
        purpose="public_material",
        max_chars=9000,
    )

    assert context.purpose == "public_material"
    assert "public_dna" in context.selected_kinds
    assert "risk_dna" in context.selected_kinds
    assert "内部战略口径不得直接用于对外公开回答" in context.context_text
