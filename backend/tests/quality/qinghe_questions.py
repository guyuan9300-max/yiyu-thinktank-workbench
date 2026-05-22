"""V2.3 质量测试 · 50 个测试问题

顾源源 5/23 钦定: 至少 50 个, 不同类型, 不同长短.

10 大类 × 5 变种 = 50 问. 每变种维度:
  v1 简短直接 / v2 中长情境 / v3 历史对比 / v4 外部视角 / v5 未来与责任

每题字段:
  qid:                Q01 ~ Q50
  category:           1-10 (10 大类)
  variant:            1-5
  length_kind:        short / medium / long
  type_kind:          factual / comparative / historical / external / forward
  prompt:             问题原文
  must_contain:       答案必须包含的关键词/数字 (评分)
  must_not_contain:   不能说的错答 (失分点)
  must_label_evidence: 该题答案是否必须带证据 (true/false)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


LengthKind = Literal["short", "medium", "long"]
TypeKind = Literal["factual", "comparative", "historical", "external", "forward", "open"]


@dataclass(frozen=True)
class QinghQuestion:
    qid: str
    category: int                    # 1-10
    variant: int                     # 1-5
    length_kind: LengthKind
    type_kind: TypeKind
    prompt: str
    must_contain: list[str] = field(default_factory=list)
    must_not_contain: list[str] = field(default_factory=list)
    must_label_evidence: bool = True
    weight: float = 1.0


# ─── 大类 1 · 项目来源 ────────────────────────────────


Q01 = QinghQuestion(
    qid="Q01", category=1, variant=1, length_kind="short", type_kind="factual",
    prompt="这个项目最早是怎么来的?",
    must_contain=["阅读", "青禾", "5 月 6 日"],
    must_not_contain=["发起人为顾源源"],  # 不能编造
)
Q02 = QinghQuestion(
    qid="Q02", category=1, variant=2, length_kind="medium", type_kind="historical",
    prompt="请回顾一下项目从最早动议到现在的关键节点。",
    must_contain=["5 月 6 日", "首次", "5 月 18 日", "v2"],
)
Q03 = QinghQuestion(
    qid="Q03", category=1, variant=3, length_kind="long", type_kind="comparative",
    prompt=(
        "青禾这个阅读陪伴项目最初的设想是什么?后来跟初版相比"
        "有什么调整?能不能把这条变化路径讲清楚。"
    ),
    must_contain=["10 所", "3 所", "调整", "试点"],
)
Q04 = QinghQuestion(
    qid="Q04", category=1, variant=4, length_kind="short", type_kind="external",
    prompt="外部媒体是怎么报道这个项目的?",
    must_contain=["10 所", "500 万", "媒体"],
)
Q05 = QinghQuestion(
    qid="Q05", category=1, variant=5, length_kind="medium", type_kind="forward",
    prompt="这个项目接下来的演进方向是什么?",
    must_contain=["试点", "验证"],
)


# ─── 大类 2 · 预算 ──────────────────────────────────────


Q06 = QinghQuestion(
    qid="Q06", category=2, variant=1, length_kind="short", type_kind="factual",
    prompt="这个项目现在确认的预算是多少?",
    must_contain=["300"],
    must_not_contain=["500 万是当前", "500 万是最新"],
)
Q07 = QinghQuestion(
    qid="Q07", category=2, variant=2, length_kind="medium", type_kind="historical",
    prompt="为什么资料里出现过 500 万这个数字?这个数字现在还作数吗?",
    must_contain=["500", "v1", "旧版", "300"],
)
Q08 = QinghQuestion(
    qid="Q08", category=2, variant=3, length_kind="long", type_kind="comparative",
    prompt=(
        "请把项目从最初到现在的预算口径梳理一遍,说明哪个是"
        "客户官方最新版,哪个是媒体口径,哪个是用户纠正,以及为什么"
        "现在权威值是 300 万。"
    ),
    must_contain=["v1", "v2", "媒体", "用户纠正", "300"],
)
Q09 = QinghQuestion(
    qid="Q09", category=2, variant=4, length_kind="short", type_kind="external",
    prompt="外部公开信息里项目的预算是多少?跟内部最新一致吗?",
    must_contain=["500", "10 所", "滞后"],
)
Q10 = QinghQuestion(
    qid="Q10", category=2, variant=5, length_kind="medium", type_kind="forward",
    prompt="如果对外发宣传稿引用预算,我应该用哪个数字?",
    must_contain=["300", "需要确认", "外部"],
)


# ─── 大类 3 · 项目范围 ──────────────────────────────────


Q11 = QinghQuestion(
    qid="Q11", category=3, variant=1, length_kind="short", type_kind="factual",
    prompt="项目范围现在是 3 所学校还是 10 所学校?",
    must_contain=["3 所"],
    must_not_contain=["10 所是最新"],
)
Q12 = QinghQuestion(
    qid="Q12", category=3, variant=2, length_kind="medium", type_kind="historical",
    prompt="项目范围有没有过调整?为什么会调整?",
    must_contain=["10 所", "3 所", "试点", "调整"],
)
Q13 = QinghQuestion(
    qid="Q13", category=3, variant=3, length_kind="long", type_kind="comparative",
    prompt=(
        "请对比 v1 方案、v2 方案、外部媒体口径在项目范围上的差异,"
        "说明哪个是当前权威值。"
    ),
    must_contain=["v1", "v2", "媒体", "3 所", "10 所"],
)
Q14 = QinghQuestion(
    qid="Q14", category=3, variant=4, length_kind="short", type_kind="external",
    prompt="如果外部已经看到 10 所学校的口径,我们要做什么?",
    must_contain=["确认", "外部口径", "更新"],
)
Q15 = QinghQuestion(
    qid="Q15", category=3, variant=5, length_kind="medium", type_kind="forward",
    prompt="3 所试点跑通后会扩展吗?判断标准是什么?",
    must_contain=["验证", "扩展"],
)


# ─── 大类 4 · 人物角色 ──────────────────────────────────


Q16 = QinghQuestion(
    qid="Q16", category=4, variant=1, length_kind="short", type_kind="factual",
    prompt="谁是项目执行推进人?",
    must_contain=["李明"],
)
Q17 = QinghQuestion(
    qid="Q17", category=4, variant=2, length_kind="short", type_kind="factual",
    prompt="谁是最终拍板人?",
    must_contain=["陈老师", "待确认"],
    must_not_contain=["客户官方确认陈老师"],
)
Q18 = QinghQuestion(
    qid="Q18", category=4, variant=3, length_kind="medium", type_kind="comparative",
    prompt="李明、王华、陈老师三个人在项目里分别是什么角色?",
    must_contain=["李明", "执行", "王华", "协调", "陈老师", "拍板"],
)
Q19 = QinghQuestion(
    qid="Q19", category=4, variant=4, length_kind="long", type_kind="historical",
    prompt=(
        "李明在 v1 方案和 v2 方案里的角色一样吗?如果不一样,"
        "请说清楚变化在哪里,以及王华是从什么时候出现的。"
    ),
    must_contain=["负责人", "执行推进", "王华", "v2"],
)
Q20 = QinghQuestion(
    qid="Q20", category=4, variant=5, length_kind="medium", type_kind="external",
    prompt="哪些人物在客户官方文件里出现过?哪些只在用户口述里?",
    must_contain=["李明", "王华", "陈老师", "口述"],
)


# ─── 大类 5 · 风险 ──────────────────────────────────────


Q21 = QinghQuestion(
    qid="Q21", category=5, variant=1, length_kind="short", type_kind="factual",
    prompt="这个项目最大的风险是什么?",
    must_contain=["扩张", "服务质量"],
    must_not_contain=["资金不足"],
)
Q22 = QinghQuestion(
    qid="Q22", category=5, variant=2, length_kind="medium", type_kind="factual",
    prompt="除了已记录的明显风险,有没有用户口述里的隐性风险?",
    must_contain=["宣传", "10 所"],
)
Q23 = QinghQuestion(
    qid="Q23", category=5, variant=3, length_kind="long", type_kind="comparative",
    prompt=(
        "客户官方文件提到的风险,我方判断提到的风险,用户口述里"
        "提到的风险,分别是什么?哪些重叠,哪些只有一边有?"
    ),
    must_contain=["扩张", "宣传", "服务质量", "用户"],
)
Q24 = QinghQuestion(
    qid="Q24", category=5, variant=4, length_kind="short", type_kind="forward",
    prompt="按严重度排,我现在最该缓解哪个风险?",
    must_contain=["服务质量", "扩张", "宣传"],
)
Q25 = QinghQuestion(
    qid="Q25", category=5, variant=5, length_kind="medium", type_kind="forward",
    prompt="如果客户硬要扩到 10 所,我们应该如何应对?",
    must_contain=["试点", "验证", "建议"],
)


# ─── 大类 6 · 承诺 ──────────────────────────────────────


Q26 = QinghQuestion(
    qid="Q26", category=6, variant=1, length_kind="short", type_kind="factual",
    prompt="目前有哪些承诺还没完成?",
    must_contain=["3 所", "学校名单", "5/10"],
)
Q27 = QinghQuestion(
    qid="Q27", category=6, variant=2, length_kind="medium", type_kind="factual",
    prompt="李明在 5/6 那次会议上承诺了什么?现在兑现了吗?",
    must_contain=["5/10", "3 所", "未确认"],
)
Q28 = QinghQuestion(
    qid="Q28", category=6, variant=3, length_kind="long", type_kind="comparative",
    prompt=(
        "请把目前已知所有承诺都列出来,包括承诺人、承诺内容、"
        "约定时间和当前状态,哪些已延期。"
    ),
    must_contain=["李明", "5/10", "延期"],
)
Q29 = QinghQuestion(
    qid="Q29", category=6, variant=4, length_kind="short", type_kind="forward",
    prompt="哪些承诺如果再延期会触发风险?",
    must_contain=["学校名单"],
)
Q30 = QinghQuestion(
    qid="Q30", category=6, variant=5, length_kind="medium", type_kind="forward",
    prompt="李明的承诺到期没兑现,下一步怎么追?",
    must_contain=["李明", "学校名单"],
)


# ─── 大类 7 · 冲突识别 ──────────────────────────────────


Q31 = QinghQuestion(
    qid="Q31", category=7, variant=1, length_kind="short", type_kind="factual",
    prompt="这批资料里有哪些地方互相矛盾?",
    must_contain=["500", "300", "10 所", "3 所"],
)
Q32 = QinghQuestion(
    qid="Q32", category=7, variant=2, length_kind="medium", type_kind="factual",
    prompt="预算和范围的冲突分别来自哪些来源?",
    must_contain=["v1", "v2", "媒体"],
)
Q33 = QinghQuestion(
    qid="Q33", category=7, variant=3, length_kind="long", type_kind="comparative",
    prompt=(
        "把所有冲突按严重度排序,说明每个冲突来源,当前权威值是哪个,"
        "为什么权威值是它而不是另一个。"
    ),
    must_contain=["预算", "范围", "李明", "权威"],
)
Q34 = QinghQuestion(
    qid="Q34", category=7, variant=4, length_kind="short", type_kind="external",
    prompt="外部口径和内部口径有差异吗?",
    must_contain=["媒体", "10 所", "500"],
)
Q35 = QinghQuestion(
    qid="Q35", category=7, variant=5, length_kind="medium", type_kind="forward",
    prompt="哪些冲突需要找客户确认,哪些可以系统自己定?",
    must_contain=["陈老师", "确认", "李明"],
)


# ─── 大类 8 · 时间线 ────────────────────────────────────


Q36 = QinghQuestion(
    qid="Q36", category=8, variant=1, length_kind="short", type_kind="factual",
    prompt="请按时间线复述项目到目前为止的来龙去脉。",
    must_contain=["5 月 3 日", "5 月 6 日", "5 月 18 日", "5 月 20 日"],
)
Q37 = QinghQuestion(
    qid="Q37", category=8, variant=2, length_kind="short", type_kind="factual",
    prompt="5 月 6 日发生了什么?",
    must_contain=["李明", "项目沟通", "承诺"],
)
Q38 = QinghQuestion(
    qid="Q38", category=8, variant=3, length_kind="medium", type_kind="comparative",
    prompt="项目在 5 月 8 日到 5 月 20 日之间发生了哪些关键变化?",
    must_contain=["v1", "v2", "媒体", "益语反馈"],
)
Q39 = QinghQuestion(
    qid="Q39", category=8, variant=4, length_kind="medium", type_kind="historical",
    prompt="哪几天有外部信息进入?哪几天有客户文件进入?",
    must_contain=["5 月 3 日", "5 月 8 日", "5 月 9 日", "5 月 18 日"],
)
Q40 = QinghQuestion(
    qid="Q40", category=8, variant=5, length_kind="long", type_kind="forward",
    prompt=(
        "未来一周(5/23—5/29)按现有信息推断,会发生哪些可能事件?"
        "比如哪个承诺会到期,哪个矛盾该被澄清。"
    ),
    must_contain=["学校名单", "确认", "预算"],
)


# ─── 大类 9 · 信息分类 ──────────────────────────────────


Q41 = QinghQuestion(
    qid="Q41", category=9, variant=1, length_kind="short", type_kind="factual",
    prompt="哪些信息是客户官方确认的?",
    must_contain=["v2", "3 所", "300", "李明", "王华"],
)
Q42 = QinghQuestion(
    qid="Q42", category=9, variant=2, length_kind="short", type_kind="factual",
    prompt="哪些信息只是我方判断,不是客户事实?",
    must_contain=["扩张", "服务质量"],
)
Q43 = QinghQuestion(
    qid="Q43", category=9, variant=3, length_kind="medium", type_kind="factual",
    prompt="哪些信息只来自用户口述,客户官方没确认?",
    must_contain=["陈老师", "宣传"],
)
Q44 = QinghQuestion(
    qid="Q44", category=9, variant=4, length_kind="medium", type_kind="external",
    prompt="哪些信息是外部公开的?可信度怎样?",
    must_contain=["官网", "媒体", "5/3", "5/9"],
)
Q45 = QinghQuestion(
    qid="Q45", category=9, variant=5, length_kind="long", type_kind="comparative",
    prompt=(
        "请把全部信息按客户官方/我方判断/外部公开/用户口述/方法卡"
        "5 类各举 2 个例子。"
    ),
    must_contain=["v2", "扩张", "媒体", "陈老师", "方法"],
)


# ─── 大类 10 · 下一步 ───────────────────────────────────


Q46 = QinghQuestion(
    qid="Q46", category=10, variant=1, length_kind="short", type_kind="factual",
    prompt="下一步最应该问客户确认哪 3 个问题?",
    must_contain=["外部口径", "陈老师", "学校名单"],
)
Q47 = QinghQuestion(
    qid="Q47", category=10, variant=2, length_kind="medium", type_kind="forward",
    prompt="下一步该补哪些材料?",
    must_contain=["学校名单", "外部"],
)
Q48 = QinghQuestion(
    qid="Q48", category=10, variant=3, length_kind="short", type_kind="forward",
    prompt="哪件事最紧急?",
    must_contain=["学校名单", "确认"],
)
Q49 = QinghQuestion(
    qid="Q49", category=10, variant=4, length_kind="short", type_kind="forward",
    prompt="下一步事项分别由谁负责?",
    must_contain=["李明", "我方"],
)
Q50 = QinghQuestion(
    qid="Q50", category=10, variant=5, length_kind="long", type_kind="forward",
    prompt=(
        "请生成一份下一周的行动计划,包含 3 件最重要的事,每件事写"
        "为什么要做、由谁做、什么时候做、衡量标准是什么。"
    ),
    must_contain=["学校名单", "外部口径", "确认"],
)


QINGHE_50_QUESTIONS: list[QinghQuestion] = [
    Q01, Q02, Q03, Q04, Q05,
    Q06, Q07, Q08, Q09, Q10,
    Q11, Q12, Q13, Q14, Q15,
    Q16, Q17, Q18, Q19, Q20,
    Q21, Q22, Q23, Q24, Q25,
    Q26, Q27, Q28, Q29, Q30,
    Q31, Q32, Q33, Q34, Q35,
    Q36, Q37, Q38, Q39, Q40,
    Q41, Q42, Q43, Q44, Q45,
    Q46, Q47, Q48, Q49, Q50,
]


assert len(QINGHE_50_QUESTIONS) == 50, "must have exactly 50 questions"
