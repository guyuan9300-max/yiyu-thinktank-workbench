"""R9：build_client_resource_index 单测 —— 客户全域资源索引（5 个域）。"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.workspace_data_center_adapter import build_client_resource_index


# ---- 测试用 stub objects -----------------------------------------------------


@dataclass
class _StubDoc:
    title: str
    kind: str = "pdf"
    importedAt: str = "2026-05-01T00:00:00"
    excerpt: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class _StubProject:
    name: str
    goal: str = ""
    description: str = ""
    createdAt: str = "2024-01-01"
    deliverables: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    ownerName: str = ""


@dataclass
class _StubJudgment:
    topic: str
    summary: str = ""
    status: str = "confirmed"
    authorityLevel: str = ""
    qualityTier: str = ""
    confidence: str = "high"
    riskLevel: str = ""
    evidenceIds: list[str] = field(default_factory=list)


@dataclass
class _StubMeeting:
    title: str
    stage: str = ""
    scheduledAt: str = "2026-04-15"
    updatedAt: str = ""


@dataclass
class _StubGoal:
    title: str
    quarter: str = ""
    progress: float = 0.0


@dataclass
class _StubSnapshot:
    documents: list[_StubDoc] = field(default_factory=list)
    projectModules: list[_StubProject] = field(default_factory=list)
    latestJudgments: list[_StubJudgment] = field(default_factory=list)
    meetings: list[_StubMeeting] = field(default_factory=list)
    goals: list[_StubGoal] = field(default_factory=list)


# ---- 基本行为 ----------------------------------------------------------------


def test_empty_snapshot_returns_empty() -> None:
    """5 个域全空时返回空字符串（不输出空 header）。"""
    snapshot = _StubSnapshot()
    assert build_client_resource_index(snapshot) == ""


def test_none_snapshot_returns_empty() -> None:
    assert build_client_resource_index(None) == ""


def test_only_documents_outputs_only_documents_section() -> None:
    snapshot = _StubSnapshot(documents=[
        _StubDoc(title="员工 A 合同.pdf"),
        _StubDoc(title="员工 B 合同.pdf"),
    ])
    result = build_client_resource_index(snapshot)
    assert "客户资源索引" in result
    assert "── 文档" in result
    assert "员工 A 合同.pdf" in result
    assert "员工 B 合同.pdf" in result
    # 其他域没数据 → 对应 section 不出现
    assert "── 项目模块" not in result
    assert "── 已采纳判断" not in result
    assert "── 会议" not in result
    assert "── 目标" not in result


def test_all_five_domains_present_when_populated() -> None:
    snapshot = _StubSnapshot(
        documents=[_StubDoc(title="X.pdf")],
        projectModules=[_StubProject(name="项目 Alpha", goal="测试", createdAt="2024-03-01")],
        latestJudgments=[_StubJudgment(topic="走差异化", status="confirmed")],
        meetings=[_StubMeeting(title="季度会议", scheduledAt="2026-04-15")],
        goals=[_StubGoal(title="覆盖 20 省", quarter="2026Q2", progress=40.0)],
    )
    result = build_client_resource_index(snapshot)
    assert "── 文档" in result
    assert "X.pdf" in result
    assert "── 项目模块" in result
    assert "项目 Alpha" in result
    assert "── 已采纳判断" in result
    assert "走差异化" in result
    assert "── 会议" in result
    assert "季度会议" in result
    assert "── 目标" in result
    assert "覆盖 20 省" in result


# ---- 文档域细节 -------------------------------------------------------------


def test_documents_sorted_by_imported_at_desc() -> None:
    snapshot = _StubSnapshot(documents=[
        _StubDoc(title="老文件.pdf", importedAt="2025-01-01"),
        _StubDoc(title="新文件.pdf", importedAt="2026-05-01"),
        _StubDoc(title="中间文件.pdf", importedAt="2025-12-01"),
    ])
    result = build_client_resource_index(snapshot)
    # 新文件应排在老文件前面
    new_pos = result.index("新文件.pdf")
    mid_pos = result.index("中间文件.pdf")
    old_pos = result.index("老文件.pdf")
    assert new_pos < mid_pos < old_pos


def test_documents_max_files_limit() -> None:
    """文档超过 max_files=80 时，剩余部分给出"另有 N 个文件未列出"。"""
    docs = [_StubDoc(title=f"file_{i}.pdf") for i in range(100)]
    snapshot = _StubSnapshot(documents=docs)
    result = build_client_resource_index(snapshot, documents_max_files=80)
    # 应有"另有 20 个文件未列出"提示
    assert "另有 20 个文件未列出" in result
    # 总计提示 100 份
    assert "共 100 份" in result


def test_documents_42_employee_contracts_all_listed() -> None:
    """复现用户场景：42 份员工合同 PDF 都被列出（验证不再丢失合同）。"""
    employees = [
        "安小青-副秘书长", "付雅馨-高级传播", "李思甜-采购", "彭启敏-出纳",
        "韩雯雯-运营", "詹瑶-秘书长", "杨先威-副秘书长", "张琴-财务",
        "黎园园-采购", "王欢-项目", "李玉林-项目", "黄爽-项目", "杨莹-新媒体",
        "徐敏-社工", "冯安凤-项目", "冷芸-社工", "刘学珉-项目", "向香草-社工",
        "吴和花-社工", "吴建林-理事长", "吴晓娟-社工", "周荣-项目", "安妮-社工",
        "庞慧琴-项目", "陈珊峰-主任", "淳学英-副主任", "谢静-行政", "李丹-社工",
        "李丽莎-项目", "李昌菊-社工", "李珍珠-社工", "杨园珍-社工",
        "潘四兰-社工", "王义-社工", "王圆月-社工", "王阳阳-社工", "田静慧-社工",
        "石艳琼-社工", "童容-项目", "颜金相-社工", "黄国锐-项目", "龙海丽-社工",
    ]
    docs = [_StubDoc(title=f"{e}-2024.1.1-2027.1.1.pdf") for e in employees]
    snapshot = _StubSnapshot(documents=docs)
    result = build_client_resource_index(snapshot)
    # 全部 42 份合同都应被列出
    for e in employees:
        assert e in result, f"员工 {e} 的合同应该在索引里"


# ---- 项目模块域 -------------------------------------------------------------


def test_projects_sorted_by_created_at_asc() -> None:
    """项目按创建时间升序（呈现演进时间线）。"""
    snapshot = _StubSnapshot(projectModules=[
        _StubProject(name="繁星计划", createdAt="2024-04-01"),
        _StubProject(name="心灵魔法学院", createdAt="2016-01-01"),
        _StubProject(name="青年支持计划", createdAt="2020-09-01"),
    ])
    result = build_client_resource_index(snapshot)
    pos_oldest = result.index("心灵魔法学院")
    pos_mid = result.index("青年支持计划")
    pos_newest = result.index("繁星计划")
    assert pos_oldest < pos_mid < pos_newest


# ---- 判断域 -----------------------------------------------------------------


def test_judgments_show_status() -> None:
    snapshot = _StubSnapshot(latestJudgments=[
        _StubJudgment(topic="第二曲线锁定青年", status="confirmed", confidence="high"),
        _StubJudgment(topic="待验证假设", status="draft", confidence="low"),
    ])
    result = build_client_resource_index(snapshot)
    assert "第二曲线锁定青年" in result
    assert "confirmed" in result
    assert "高" in result or "high" in result  # confidence 显示
    assert "待验证假设" in result
    assert "draft" in result


# ---- 会议域 -----------------------------------------------------------------


def test_meetings_sorted_by_scheduled_desc() -> None:
    snapshot = _StubSnapshot(meetings=[
        _StubMeeting(title="3 月会议", scheduledAt="2026-03-01"),
        _StubMeeting(title="5 月会议", scheduledAt="2026-05-15"),
        _StubMeeting(title="4 月会议", scheduledAt="2026-04-10"),
    ])
    result = build_client_resource_index(snapshot)
    # 最新会议在前
    pos_may = result.index("5 月会议")
    pos_apr = result.index("4 月会议")
    pos_mar = result.index("3 月会议")
    assert pos_may < pos_apr < pos_mar


# ---- 目标域 -----------------------------------------------------------------


def test_goals_with_progress_and_quarter() -> None:
    snapshot = _StubSnapshot(goals=[
        _StubGoal(title="县域覆盖 25 省", quarter="2026Q4", progress=40.0),
        _StubGoal(title="数字化平台上线", quarter="2026Q3", progress=60.0),
    ])
    result = build_client_resource_index(snapshot)
    assert "县域覆盖 25 省" in result
    assert "2026Q4" in result
    assert "40%" in result
    assert "数字化平台上线" in result
    assert "60%" in result


# ---- 总预算限制 -------------------------------------------------------------


def test_total_budget_truncates_when_exceeded() -> None:
    """总预算 max_chars 限制生效（防止 prompt 过长）。"""
    docs = [_StubDoc(title=f"很长很长的文件名 {'x' * 100} {i}.pdf") for i in range(50)]
    snapshot = _StubSnapshot(documents=docs)
    result = build_client_resource_index(snapshot, max_chars=2000)
    assert len(result) <= 2001  # 含末尾的 …


# ---- 头部说明 ---------------------------------------------------------------


def test_header_explains_purpose_and_guidance() -> None:
    """头部说明告诉 LLM 这是元数据索引（不是文件内容），可以直接引用。"""
    snapshot = _StubSnapshot(documents=[_StubDoc(title="X.pdf")])
    result = build_client_resource_index(snapshot)
    assert "客户资源索引" in result
    assert "全集元数据" in result
    # 提示 LLM 索引覆盖全集（不是检索命中）
    assert "全部资源" in result or "不只是检索命中的部分" in result
    # 提示可以直接引用
    assert "真实存在" in result or "可以直接引用" in result
