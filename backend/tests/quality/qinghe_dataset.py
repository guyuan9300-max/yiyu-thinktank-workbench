"""V2.3 质量测试 · 青禾公益基金会 12 条数据集

顾源源 2026-05-23 钦定 12 条测试数据 (5 类来源):
    A 任务/日程 · 3 条
    B 客户文件   · 3 条
    C 外部情报   · 2 条
    D 用户口述   · 3 条
    E 成长方法卡 · 1 条

每条数据带:
  · sub_kind: 在该 path 内的细分
  · subject/attribute/value: 抽取后预期的 atomic_fact 三元组
  · expected_source_role: 预期 source_role (评 D1 用)
  · expected_content_role: 预期 content_role
  · expected_should_clarify: 该数据是否预期会触发澄清
  · narrative_raw: 原始文本 (用于真实抽取或 mock)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


PathKind = Literal[
    "task_review",
    "workbench_file",
    "internet_crawler",
    "mobile_ai_chat",
    "growth_method",
]


@dataclass(frozen=True)
class QinghDatum:
    """1 条测试数据 (跨 5 类来源同模型)."""
    id: str
    category: Literal["A", "B", "C", "D", "E"]
    title: str
    narrative_raw: str
    path: PathKind
    sub_kind: str
    expected_source_type: str
    expected_source_role: str
    expected_content_role: str
    happened_at: str  # ISO date
    actor_name: str  # 谁说的/谁记的
    expected_facts: list[dict] = field(default_factory=list)
    expected_should_clarify: bool = False
    expected_supersedes: str | None = None  # superseded 目标数据 id


# ─── A 类 · 任务与日程 ─────────────────────────────────


A_1_MEETING = QinghDatum(
    id="A1_meeting_5_6",
    category="A",
    title="5/6 与李明项目沟通会",
    narrative_raw=(
        "2026 年 5 月 6 日,与青禾公益基金会项目经理李明开会,讨论"
        "「乡村儿童阅读陪伴项目」是否进入试点。会议后,李明承诺 5 月 10 日"
        "前提供 3 所试点学校名单。"
    ),
    path="task_review",
    sub_kind="task",
    expected_source_type="collaboration_task",
    expected_source_role="yiyu_advisory",
    expected_content_role="plan",
    happened_at="2026-05-06",
    actor_name="顾源源",
    expected_facts=[
        {"subject": "乡村儿童阅读陪伴项目", "attribute": "首次沟通日期", "value": "2026-05-06"},
        {"subject": "李明", "attribute": "承诺", "value": "5/10 前提供 3 所试点学校名单"},
        {"subject": "李明", "attribute": "角色", "value": "青禾公益基金会项目经理"},
    ],
)


A_2_SEND_V1 = QinghDatum(
    id="A2_send_v1_5_11",
    category="A",
    title="5/11 我方发送第一版方案",
    narrative_raw=(
        "5 月 11 日,益语需要给青禾发送第一版试点方案,重点说明"
        "「为什么不建议一开始扩到 10 所学校」。"
    ),
    path="task_review",
    sub_kind="task",
    expected_source_type="collaboration_task",
    expected_source_role="yiyu_advisory",
    expected_content_role="plan",
    happened_at="2026-05-11",
    actor_name="顾源源",
    expected_facts=[
        {"subject": "我方", "attribute": "行动", "value": "5/11 发送第一版试点方案"},
        {"subject": "我方", "attribute": "核心判断", "value": "不建议一开始扩到 10 所学校"},
    ],
)


A_3_WEEKLY = QinghDatum(
    id="A3_weekly_review",
    category="A",
    title="本周复盘",
    narrative_raw=(
        "本周项目已完成首次需求沟通,但学校名单迟迟未确认;青禾内部对"
        "预算口径仍不统一,下周重点是确认试点范围和预算边界。"
    ),
    path="task_review",
    sub_kind="weekly_review",
    expected_source_type="collaboration_review",
    expected_source_role="yiyu_advisory",
    expected_content_role="lesson",
    happened_at="2026-05-22",
    actor_name="顾源源",
    expected_facts=[
        {"subject": "项目", "attribute": "卡点", "value": "学校名单未确认"},
        {"subject": "项目", "attribute": "卡点", "value": "预算口径不统一"},
        {"subject": "项目", "attribute": "下周重点", "value": "确认试点范围和预算边界"},
    ],
)


# ─── B 类 · 客户文件 ───────────────────────────────────


B_4_V1_DOC = QinghDatum(
    id="B4_v1_5_8",
    category="B",
    title="青禾阅读项目方案_v1_20260508.docx",
    narrative_raw=(
        "项目计划覆盖 10 所学校,总预算 500 万元,项目负责人为李明。"
    ),
    path="workbench_file",
    sub_kind="proposal",
    expected_source_type="client_internal_doc",
    expected_source_role="client_internal",
    expected_content_role="fact",
    happened_at="2026-05-08",
    actor_name="青禾公益基金会",
    expected_facts=[
        {"subject": "乡村儿童阅读陪伴项目", "attribute": "覆盖学校数(v1)", "value": "10 所"},
        {"subject": "乡村儿童阅读陪伴项目", "attribute": "总预算(v1)", "value": "500 万元"},
        {"subject": "乡村儿童阅读陪伴项目", "attribute": "负责人(v1)", "value": "李明"},
    ],
)


B_5_V2_DOC = QinghDatum(
    id="B5_v2_5_18",
    category="B",
    title="青禾阅读项目方案_v2_20260518.docx",
    narrative_raw=(
        "项目调整为先在 3 所学校试点,总预算 300 万元,李明负责执行推进,"
        "王华秘书长负责内部协调。"
    ),
    path="workbench_file",
    sub_kind="proposal",
    expected_source_type="client_internal_doc",
    expected_source_role="client_internal",
    expected_content_role="fact",
    happened_at="2026-05-18",
    actor_name="青禾公益基金会",
    expected_should_clarify=True,  # 与 v1 矛盾
    expected_supersedes="B4_v1_5_8",
    expected_facts=[
        {"subject": "乡村儿童阅读陪伴项目", "attribute": "试点学校数(v2)", "value": "3 所"},
        {"subject": "乡村儿童阅读陪伴项目", "attribute": "总预算(v2)", "value": "300 万元"},
        {"subject": "李明", "attribute": "新角色", "value": "执行推进"},
        {"subject": "王华", "attribute": "角色", "value": "秘书长 / 内部协调"},
    ],
)


B_6_OUR_FEEDBACK = QinghDatum(
    id="B6_our_feedback_5_20",
    category="B",
    title="益语关于青禾阅读项目的试点建议_20260520.docx",
    narrative_raw=(
        "建议项目第一阶段不要追求覆盖学校数量,而应先验证家长参与、"
        "学校配合、志愿者稳定性和阅读活动持续性。当前最大风险不是资源"
        "不足,而是点位扩张过快导致服务质量失控。"
    ),
    path="workbench_file",
    sub_kind="proposal",
    expected_source_type="client_internal_doc",
    expected_source_role="yiyu_advisory",
    expected_content_role="observation",
    happened_at="2026-05-20",
    actor_name="益语",
    expected_facts=[
        {"subject": "我方", "attribute": "判断", "value": "先验证机制再扩大点位"},
        {"subject": "项目", "attribute": "风险", "value": "扩张过快导致服务质量失控"},
        {"subject": "项目", "attribute": "验证维度", "value": "家长参与/学校配合/志愿者稳定性/活动持续性"},
    ],
)


# ─── C 类 · 外部情报 ───────────────────────────────────


C_7_OFFICIAL_SITE = QinghDatum(
    id="C7_official_site_5_3",
    category="C",
    title="青禾官网 5/3 启动会动态",
    narrative_raw=(
        "青禾公益基金会官网 2026 年 5 月 3 日发布动态:青禾启动乡村儿童"
        "阅读陪伴计划,秘书长王华出席启动会。"
    ),
    path="internet_crawler",
    sub_kind="official",
    expected_source_type="internet_official",
    expected_source_role="client_official",
    expected_content_role="fact",
    happened_at="2026-05-03",
    actor_name="青禾公益基金会官网",
    expected_facts=[
        {"subject": "乡村儿童阅读陪伴项目", "attribute": "对外公开日", "value": "2026-05-03"},
        {"subject": "王华", "attribute": "出席", "value": "5/3 启动会"},
    ],
)


C_8_MEDIA = QinghDatum(
    id="C8_media_5_9",
    category="C",
    title="某行业媒体 5/9 报道",
    narrative_raw=(
        "某行业媒体 2026 年 5 月 9 日报道:青禾计划在 10 所乡村学校"
        "推广阅读项目,预计投入 500 万元。"
    ),
    path="internet_crawler",
    sub_kind="media",
    expected_source_type="internet_media",
    expected_source_role="media_observation",
    expected_content_role="observation",
    happened_at="2026-05-09",
    actor_name="行业媒体",
    expected_should_clarify=True,  # 外部口径滞后于 v2
    expected_facts=[
        {"subject": "乡村儿童阅读陪伴项目", "attribute": "媒体口径学校数", "value": "10 所"},
        {"subject": "乡村儿童阅读陪伴项目", "attribute": "媒体口径预算", "value": "500 万元"},
    ],
)


# ─── D 类 · 用户口述 ───────────────────────────────────


D_9_BACKGROUND = QinghDatum(
    id="D9_background",
    category="D",
    title="项目背景口述",
    narrative_raw=(
        "青禾其实一开始想做一个比较大的阅读品牌项目,但我感觉他们内部"
        "还没有想清楚怎么长期运营。李明执行很积极,但他不是最终拍板的人。"
        "王华秘书长会影响方向,但真正最后拍板的是陈老师。"
    ),
    path="mobile_ai_chat",
    sub_kind="user_observation",
    expected_source_type="user_observation",
    expected_source_role="user_oral",
    expected_content_role="observation",
    happened_at="2026-05-22",
    actor_name="顾源源",
    expected_facts=[
        {"subject": "李明", "attribute": "用户判断", "value": "执行积极但非拍板人"},
        {"subject": "王华", "attribute": "用户判断", "value": "方向影响者"},
        {"subject": "陈老师", "attribute": "用户判断", "value": "最终拍板人 (待客户官方确认)"},
        {"subject": "青禾公益基金会", "attribute": "风险", "value": "内部尚未想清长期运营机制"},
    ],
)


D_10_HIDDEN_RISK = QinghDatum(
    id="D10_hidden_risk",
    category="D",
    title="隐性风险口述",
    narrative_raw=(
        "我不担心他们有没有钱,我担心的是他们把 3 所学校试点直接说成"
        "10 所学校推广,最后为了对外宣传牺牲项目质量。"
    ),
    path="mobile_ai_chat",
    sub_kind="user_observation",
    expected_source_type="user_observation",
    expected_source_role="user_oral",
    expected_content_role="risk",
    happened_at="2026-05-22",
    actor_name="顾源源",
    expected_facts=[
        {"subject": "项目", "attribute": "隐性风险", "value": "宣传压力 > 服务质量"},
        {"subject": "项目", "attribute": "用户担忧", "value": "3 校试点被对外说成 10 校推广"},
    ],
)


D_11_CORRECTION = QinghDatum(
    id="D11_correction",
    category="D",
    title="用户纠正预算",
    narrative_raw=(
        "刚才 AI 说预算是 500 万不对,500 万是旧版和媒体口径。"
        "现在内部最新版是 300 万,范围是 3 所学校。"
    ),
    path="mobile_ai_chat",
    sub_kind="user_verbal_fact",
    expected_source_type="user_verbal_fact",
    expected_source_role="user_oral",
    expected_content_role="fact",
    happened_at="2026-05-22",
    actor_name="顾源源",
    expected_supersedes="B4_v1_5_8",  # 用户纠正覆盖 v1
    expected_facts=[
        {"subject": "乡村儿童阅读陪伴项目", "attribute": "当前权威预算", "value": "300 万元"},
        {"subject": "乡村儿童阅读陪伴项目", "attribute": "当前权威范围", "value": "3 所学校"},
        {"subject": "乡村儿童阅读陪伴项目", "attribute": "500 万评价", "value": "旧版/外部滞后口径"},
    ],
)


# ─── E 类 · 成长方法卡 ─────────────────────────────────


E_12_METHOD = QinghDatum(
    id="E12_method_card",
    category="E",
    title="试点方法卡",
    narrative_raw=(
        "类似基金会试点项目,不要一开始追求覆盖规模,先用 2—3 个点位"
        "验证学校配合、家长参与、志愿者稳定性,再决定是否扩展。"
    ),
    path="growth_method",
    sub_kind="method_card",
    expected_source_type="system_derived",  # 方法卡走 system_derived (not client fact)
    expected_source_role="system_internal",
    expected_content_role="lesson",
    happened_at="2026-04-15",  # 沉淀日期早于本项目
    actor_name="顾源源",
    expected_facts=[
        {"subject": "试点项目方法", "attribute": "原则", "value": "2-3 个点位先验证再扩展"},
        {"subject": "试点项目方法", "attribute": "验证维度", "value": "学校配合/家长参与/志愿者稳定性"},
    ],
)


# ─── 集合 ─────────────────────────────────────────────


QINGHE_12_DATA: list[QinghDatum] = [
    A_1_MEETING, A_2_SEND_V1, A_3_WEEKLY,
    B_4_V1_DOC, B_5_V2_DOC, B_6_OUR_FEEDBACK,
    C_7_OFFICIAL_SITE, C_8_MEDIA,
    D_9_BACKGROUND, D_10_HIDDEN_RISK, D_11_CORRECTION,
    E_12_METHOD,
]


# ─── 测试主体常量 ─────────────────────────────────────


CLIENT_ID = "client_qinghe_v23test"
CLIENT_NAME = "青禾公益基金会"
PROJECT_ID = "project_reading_v23test"
PROJECT_NAME = "乡村儿童阅读陪伴项目"


# ─── 期望抽取的核心实体 (用于 D2 召回率打分) ───────


EXPECTED_ENTITIES = {
    "persons": ["李明", "王华", "陈老师"],
    "orgs": ["青禾公益基金会"],
    "projects": ["乡村儿童阅读陪伴项目"],
    "dates": ["2026-05-03", "2026-05-06", "2026-05-08", "2026-05-09",
              "2026-05-11", "2026-05-18", "2026-05-20", "2026-05-22"],
    "amounts": ["300 万", "500 万", "300 万元", "500 万元"],
    "ranges": ["3 所学校", "10 所学校", "3 所", "10 所"],
    "commitments": ["3 所试点学校名单"],
    "risks": ["扩张过快", "服务质量失控", "宣传压力"],
}


# ─── 预期核心冲突 (D3 评分) ────────────────────────────


EXPECTED_CORE_CONFLICTS = [
    {"name": "预算口径冲突", "v1": "500 万", "v2": "300 万", "authoritative": "300 万 (v2 + 用户纠正)"},
    {"name": "项目范围冲突", "v1": "10 所学校", "v2": "3 所学校", "authoritative": "3 所学校 (v2)"},
    {"name": "李明角色冲突", "v1": "负责人", "v2": "执行推进", "authoritative": "执行推进 (v2)"},
    {"name": "外部口径滞后", "external": "媒体 5/9 仍说 10 校/500 万", "internal": "v2 5/18 已改"},
    {"name": "陈老师拍板缺正式证据", "source": "仅用户口述", "issue": "无客户官方文件支持"},
]
