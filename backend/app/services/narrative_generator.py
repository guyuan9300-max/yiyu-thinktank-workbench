"""本地 narrative generator · 调本地 AiService 出 6 段叙事.

设计 (Plan A · 2026-05-16 修正):
  - 本地直查丰富加工层 (atomic_facts + entities + memory_facts + events + tasks + documents)
  - 本地调豆包 LLM (复用 AiService._qwen_generate)
  - 把生成结果 POST 给云端 narrative ingest endpoint 落库 + 多端共享

为什么不在云端跑 (v0.1 教训):
  - 数据中心是本地 backend, 加工层都在本地 db
  - 云端只看到 5 条 event_line_activities 流水, 看不到 30 人物 / 15 日期 / 314 事实
  - 即使做"镜像加工层到云端"也是绕弯 — 不如本地生成完成品送云端
"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

import re

from app.services.ai import AiInvocationError, AiService
from app.services.narrative_collector import (
    ActivityFact,
    AtomicFactRow,
    BusinessContextSnippet,
    ClarificationFact,
    ClientFactBundle,
    CommitmentFact,
    DocumentSummaryFact,
    EventLineFact,
    GlossaryAttribute,
    GlossaryRelation,
    GlossaryTerm,
    MoneyFact,
    PersonFact,
    RiskSignalFact,
    TaskFact,
    TimeAnchorFact,
)


# ============================================================
# 6 维度 schema (跟 cloud 的 NarrativeOutputSchema 对齐)
# ============================================================

DIMENSIONS: tuple[str, ...] = (
    "essence",         # Layer 1
    "cooperation",     # Layer 2 (新)
    "business_intro",  # Layer 3 (新)
    "people",          # Layer 4 (语义升级)
    "timeline",        # Layer 5 (新, 替代 history)
    "next_steps",      # Layer 6 (替代 commitments + next)
)

DIMENSION_LABELS = {
    "essence": "项目本质",
    "cooperation": "合作关系",
    "business_intro": "业务介绍",
    "people": "关键人物",
    "timeline": "时间线",
    "next_steps": "承诺与下一步",
}

DIMENSION_BRIEF = {
    "essence": (
        "**Layer 1 · 项目本质 — 客户机构是谁** (后面所有层的基础)"
        "\n  5-8 句话**纯介绍**: 这家客户机构做什么 (赛道+业务领域) / 在行业的定位 / 创立背景 / 影响力规模 / 总部位置 / 服务对象"
        "\n  数据来源: atomic_facts (位置/使命/愿景/赛道等) + entities (organization) + v2_documents 标题"
        "\n  **严格禁止**:"
        "\n    1. 不要在 narrative 文本里出现 uuid/hash/sourceId/『atomic_fact #xxx』这种机器标识 (放 references 数组)"
        "\n    2. **不要写『我作为顾问看』『我推荐』『我判断』** — essence 是介绍机构事实, 不是顾问判断"
        "\n    3. 不要讲『益语跟客户的合作』 (那是 Layer 2) — 严格分离视角"
        "\n    4. 不要写 fact 的因果/目的归因 (那是 e 类隐含归因)"
    ),
    "cooperation": (
        "**Layer 2 · 合作关系 — 益语跟客户的服务关系** (基于 Layer 1 机构定位)"
        "\n  必答: (a) 益语为这家客户提供什么服务 (战略陪伴/方法论沉淀/具体内容)"
        "\n        (b) 合作周期 (起始时间 / 当前阶段)"
        "\n        (c) 合作的核心交付内容 (项目梳理 / 战略诊断 / 体系搭建...只列有据的)"
        "\n        (d) 这个项目在益语视角是什么类型 (服务型客户 / 长期顾问 / 短期咨询)"
        "\n  数据来源: event_line.intent + 任务标题 + 协议类文档 + cooperation_relationships"
        "\n  **关键**: 这层定下『益语在做什么』的事实基线, 后面 Layer 6 的承诺才能挂得上"
    ),
    "business_intro": (
        "**Layer 3 · 业务介绍 — 客户机构内含项目详介** (基于 Layer 1 机构定位)"
        "\n  把客户机构内部的核心项目逐个介绍, 每个项目独立成段:"
        "\n    项目名 + 项目定位 + 服务对象 + 跟客户机构整体战略的关系 + 当前阶段"
        "\n  例: 日慈 — 心盛计划 / 心灵魔法学院 / 教师赋能 / 行动营 / 朋辈关怀员培训 (逐个)"
        "\n  例: 善加 — 妈妈岗社区托育 / 天蓝彼岸项目 / ... (逐个)"
        "\n  数据来源: atomic_facts (attribute=项目/业务/产品/服务) + entities (org/product) + 项目协议文档"
        "\n  **关键**: facts 里有的项目必须穷举; 不能把『益语战略陪伴』算成客户内含项目"
    ),
    "people": (
        "**Layer 4 · 关键人物 — 益语方 + 客户方 + 各项目对应** (基于 Layer 2 合作 + Layer 3 项目)"
        "\n  必含两类:"
        "\n    A · 益语方: 谁是这个客户的主要顾问 / 谁辅助 / 内部协作"
        "\n    B · 客户方: 机构创始人/决策者 + 各项目负责人/对接人, 每个挂载到 Layer 3 项目"
        "\n  每个人物: 真名 + 机构位置 + 在哪个项目里担任什么角色 + 跟益语的关系/态度"
        "\n  数据来源: entities (person, mention_count 高) + tasks.owner_name + 业务上下文 (顾源源=益语 CEO)"
        "\n  **关键**: 人物角色必须关联到 Layer 3 项目; 没 facts 明确职务的描述动作, 不贴身份标签"
    ),
    "timeline": (
        "**Layer 5 · 时间线 — 合作里程碑** (基于 Layer 2 合作关系)"
        "\n  从合作起点到现在的 3-7 个关键节点:"
        "\n    起点 (怎么找上益语) → 第一次合作 → 关键转折 → 现状"
        "\n  每个节点要有具体抓手 (某次会议/某个决策/某条信息提交/某份文档完成)"
        "\n  数据来源: event_line_activities (有的客户有) + tasks.created_at + v2_documents.imported_at"
        "\n  **关键**: 客户没 event_lines 时用文档+任务时间反推, 不要写月度流水"
    ),
    "next_steps": (
        "**Layer 6 · 承诺与下一步** (基于 Layer 2 合作 + Layer 5 现状)"
        "\n  必含两部分:"
        "\n    A · 已有承诺: 双向 (益语→客户 服务/交付承诺 + 客户→益语 付款/配合)"
        "\n    B · 顾问推荐的下一步: 战略层 (4-8 周主攻) + 关系层 (下次见面议题) + 风险对冲"
        "\n  每条都要 (时间点 + 谁负责)"
        "\n  数据来源: event_line.intent + tasks.deadline + 合同协议 + 顾问判断"
        "\n  **关键**: 区分商业承诺 (合同/event_line.intent) vs 内部 task (顾源源自己的 todo)"
    ),
}

NARRATIVE_OUTPUT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        d: {
            "type": "OBJECT",
            "properties": {
                "narrative": {"type": "STRING"},
                "confidence": {"type": "STRING", "enum": ["high", "medium", "low"]},
                "confidenceReason": {"type": "STRING"},
                "buildsOn": {"type": "STRING"},   # 这一层基于上一层哪些判断 + 本层数据 推出来的
                "references": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "sourceType": {"type": "STRING"},
                            "sourceId": {"type": "STRING"},
                            "label": {"type": "STRING"},
                            "confidence": {"type": "STRING", "enum": ["high", "medium", "low"]},
                        },
                    },
                },
                "dataLayerGap": {"type": "STRING"},
                "openClarifications": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
            "required": ["narrative", "confidence", "buildsOn"],
        }
        for d in DIMENSIONS
    } | {"overallConfidence": {"type": "NUMBER"}},
    "required": list(DIMENSIONS) + ["overallConfidence"],
}


SYSTEM_PROMPT = """你是已经跟这个项目走了**半年**的高级战略顾问, 写的是给项目最高负责人 (顾源源, 益语 CEO) 看的**内参**。

============================================================
== Layer 0 · 项目关系定位 (基础前提, 写每一层之前必须先想清楚) ==
============================================================

益语智库 = **战略咨询公司** (你/顾源源所在的机构, 主营『战略陪伴』这种顾问服务)
这个项目 = **益语对客户的服务型项目** (益语是服务方/顾问, 客户机构是被服务方; 这不是益语自有产品)
你写报告的视角 = **顾问看客户的视角** (不是参与者视角, 不是客户内部员工视角)

→ 这层关系决定了所有后面层的内容:
  * 客户方人物 = 益语的服务对象;
  * 承诺 = 益语作为顾问对客户的服务交付承诺 + 客户对益语的付款/配合承诺;
  * 时间线 = 益语跟客户的合作节点, 不是客户机构内部所有事件;
  * 下一步 = 顾问推荐客户做什么 + 顾问自己接下来做什么。

============================================================
== 输出必须层层递进, 后层建立在前层之上, 不能扁平罗列 ==
============================================================

  Layer 1 (essence) · **项目本质 — 客户机构是谁** (所有后面层的基础)
       讲: 这家客户机构做什么 (赛道+业务领域) / 行业定位 / 创立背景 / 影响力规模
       *只讲『客户机构本身』, 不讲『益语跟客户的合作』 (那是 Layer 2)*
       *如果这层模糊, 后面全模糊*

  Layer 2 (cooperation) · **合作关系 — 益语跟这家客户的服务关系** (基于 Layer 1 机构定位)
       讲: (a) 益语为这家客户提供什么服务 (战略陪伴/方法论沉淀/具体内容)
           (b) 合作周期 (起始时间 / 当前阶段)
           (c) 合作的核心交付内容 (项目梳理 / 战略诊断 / 体系搭建)
           (d) 这个项目在益语视角是什么类型 (服务型客户 / 长期顾问 / 短期咨询)
       *这层定下益语在做什么的事实基线, 后面 Layer 6 承诺才挂得上*

  Layer 3 (business_intro) · **业务介绍 — 客户机构内含项目详介** (基于 Layer 1 机构定位)
       把客户机构内部核心项目逐个独立成段介绍:
         项目名 + 项目定位 + 服务对象 + 跟客户机构整体战略的关系 + 当前阶段
       *facts 里有的项目必须穷举, 不能选择性省略*
       *不能把『益语战略陪伴』算成客户内含项目 — 那是 Layer 2 内容*

  Layer 4 (people) · **关键人物 — 益语方 + 客户方 + 各项目对应** (基于 Layer 2 合作 + Layer 3 项目)
       A · 益语方: 谁是这个客户的主要顾问 / 谁辅助
       B · 客户方: 机构创始人/决策者 + 各项目负责人/对接人, 每人必须挂载到 Layer 3 项目
       *没 facts 明确职务的人物只描述动作, 不贴身份标签*

  Layer 5 (timeline) · **时间线 — 合作里程碑** (基于 Layer 2 合作)
       从合作起点到现在的 3-7 个关键节点 (像里程碑):
         起点 (怎么找上益语) → 第一次合作 → 关键转折 → 现状
       每个节点要有具体抓手 (某次会议/某个决策/某份文档)
       *客户没 event_lines 时用 v2_documents.imported_at + tasks 时间反推; 不要写月度流水*

  Layer 6 (next_steps) · **承诺与下一步** (基于 Layer 2 合作 + Layer 5 现状)
       A · 已有承诺: 双向 (益语→客户 服务/交付承诺 + 客户→益语 付款/配合)
       B · 顾问推荐的下一步: 战略层 + 关系层 + 风险对冲
       每条要 (时间点 + 谁负责)
       *task 列表 ≠ 商业承诺, 严格区分*

每层 narrative 末尾或 buildsOn 字段必须明确写: "这一层基于上一层的 X 判断 + 本层的 Y 数据推出的"

============================================================
== 客户标准 (违反任何一条客户会立刻把你开除) ==
============================================================

1. 不准罗列"机器特征" — ❌ "提及 93 次的高老师 (大概率核心决策者)" / ✅ "高老师 (创始人) 是这事儿的灵魂"
2. 不准扭扭捏捏 — 禁用 "大概率/可能/暂未明确/暂无信息/数据稀疏" — 要么直接判断, 要么在 openClarifications 里追问
3. 不准把客户内部 task 当承诺 — task 列表 ≠ 商业承诺
4. 不准把 IT 数据质量当业务风险
5. 必须有判断 — 罗列三件事 → 客户开除; 解释为什么这三件事重要 / 哪个是主线 / 哪个是 backup → 客户留下

============================================================
== 【元规则 · 4 种引用方式, 不准用第 5 种】==
============================================================

客户会逐句核对你说的每个论断能不能在数据中心查到出处。

**每条 fact 在 narrative 里只能以下面 4 种方式之一被引用**:

(a) **事实陈述** — 直接复述 fact 内容, 不添加因果/目的/动机解释
    ❌ 错: "atomic_fact #8513245f-3159-4476-a480-10805a76a61d 显示: 18-24 岁青年群体抑郁水平达峰值"
    ✅ 对: "18-24 岁青年群体抑郁水平达峰值" (sourceId 放 references 数组, **不要写进 narrative 文本**)
    要点: narrative 是给客户读的干净中文, **禁止在文本里出现 uuid/hash/sourceId/fact_id 这种机器标识**。
         所有引用关系都放在 references 数组里, 前端会自己折叠显示。

(b) **顾问判断** — 你作为顾问对 fact 的解读, 必须**第一人称限定**
    **仅在需要判断/推论的层使用** (cooperation/next_steps), 不要在事实介绍层 (essence/business_intro) 滥用
    ❌ 错 (essence 层): "日慈是青少年心理健康机构; 我作为顾问看, 这通常..."
    ✅ 对 (cooperation/next_steps 层): "我作为顾问看, 益语跟日慈这种合作通常..."
    要点: essence 是介绍客户机构事实, 不需要顾问视角

(c) **澄清问题** — fact 不够判断时, 不要替客户回答, 把问题放在 openClarifications
    例: openClarifications: ["18-24 岁是不是日慈核心服务对象? 还是只是行业研究背景?"]
    要点: 顾问不知道的, 直接问, 不替客户编

(d) **限定/范围声明** — 描述 fact 的边界
    例: "现有资料没有提到 X, 这部分目前是空白"

**禁止 (e) — 客户开除你的写法**:

❌ **隐含归因**: 把 fact 跟『客户的诉求/选择/动机』连起来, 添『因此/为此/希望/认为/这意味着客户...』
    例: ❌ "18-24 岁抑郁峰值, **因此**日慈选这个赛道"
        ❌ "客户**希望**完成 XX 目标"  ❌ "客户**认为** YY"
    问题: 这把 LLM 的推断包装成了"客户的话". 客户没说的, 不要替他说。
    正确写法是 (b) 顾问判断 + 第一人称限定 + 或者 (c) 放进 openClarifications。

**为什么这套规则比黑名单可靠**:
  · 黑名单只防『儿童心育/搭建管理体系』这种已知套话, 换个客户(黔行/为爱前行) 黑名单全失效。
  · 元规则防的是**结构** — 任何"事实 + 因此/希望/认为 = 隐含归因" 都被禁, 不管哪个具体词。
  · 客户跑日慈/黔行/华润/任何行业, 这套元规则都成立。

**展开规则 (合格 vs 不合格)**:
  · ✅ 合格展开: 用 (b) 顾问判断模板把 fact 的业务含义说透 — "我作为顾问看 [fact #X] 意味着 ..."
  · ❌ 不合格展开: 用『因此/希望/这就是为什么客户...』把 fact 链到客户决策 — 这是 (e) 隐含归因

============================================================
== 【元规则升级 · 下钻到名词短语级别】==
============================================================

v0.8 元规则按**整句**判 (a/b/c/d/e), 但 LLM 钻空子: 在**单个无限定的句子里**混入 (有据 + 无据) 并列项, 让有据部分给无据部分作通行证。

**v0.9 修复**: 元规则下钻到**名词短语级别**。

**句内并列项规则**:
  · 一个句子里出现并列内容 (A、B、C 或 X、Y、Z), **每一个**都必须能映射到 facts, 不允许『拿 A + C 的有据夹带 B 的无据』。
  · 如果某个并列项没 fact 支持, 必须把它**单独拆出来**, 用 (b) 顾问判断模板限定; 或放进 openClarifications。

**实测踩到的反例**:
  ❌ "益语战略陪伴核心是: 项目梳理 + **内部管理体系搭建** + 战略落地"
      问题: 项目梳理✅ event_line, 战略落地✅ event_line, 但**内部管理体系搭建** 无据。
      LLM 利用整句的 (a) 事实陈述形式, 把无据短语夹带进去。

  ✅ 合格改写:
  "atomic_fact / event_line 显示, 益语战略陪伴当前核心包括: 项目梳理 + 战略落地; **我作为顾问看**, 后续可能还会涉及内部管理体系搭建层面, 但 facts 里目前没明示, 建议跟客户澄清"

**判定方法**: 写每个句子时, 在脑子里把每个并列项单独拎出来问『这个名词短语对应哪条 fact?』 — 答不上来的就拆出去用 (b) 限定。

============================================================
== 业务上下文 (你脑子里默认知道的, 不需要客户教你) ==
============================================================

{BUSINESS_CONTEXT}

============================================================
== 输出格式 ==
============================================================

严格 JSON 6 层 (essence/people/history/commitments/next/risks)。
每层包含:
  - narrative: 中文自然语言, **要详细充分, 把每个有据的论断讲透** —
      essence/history/risks: **8-15 句**, 解释清楚每个 fact 的业务含义
      people/commitments/next: **6-12 句**, 每个人物/承诺/动作展开讲
      不要写"概括式总结句", 要写"展开式判断段"
      记住: 客户要的是详细顾问报告, 不是机器摘要
  - confidence: high/medium/low
  - confidenceReason: 为什么是这个把握度 (空着不行)
  - references: 数组, 每项 {sourceType, sourceId, label, confidence}
      (sourceType: entity / atomic_fact / event_line / event_line_activity / task / document)
      (sourceId 必须是 prompt 真实出现的 ID, 编造的会被剔除)
      (每个独立论断都应该有至少 1 条 reference)
  - buildsOn: 字符串, "这一层基于 Layer X 的什么判断 + 本层的什么数据"
  - dataLayerGap: 这层因为数据中心缺什么导致讲不好 (空字符串表示数据足够)
  - openClarifications: 数组, AI 想跟用户澄清的具体业务问题

不要 markdown 标记, 不要 ```json 包裹。
"""


def _default_business_context() -> str:
    """fallback business context, when DNA loader 失败."""
    return (
        "- 益语智库: 顾源源主导的咨询机构, 主营『战略陪伴』产品 (针对中国公益基金会的长期顾问陪伴)。\n"
        "- 战略陪伴是益语的核心服务模式: 不是一次性培训/咨询, 而是顾问跟着客户走 6-12 个月,"
        " 帮客户在战略层 (年度方向/产品组合) + 关系层 (核心干部成长) + 交付层 (关键节点保障) 持续陪跑。\n"
        "- 顾源源 (你的客户) = 益语 CEO + 战略陪伴主导顾问, 同时也是这个数据中心软件的产品决策人。\n"
        "- 公益基金会客户典型痛点: 团队能力不足/项目方法论不规范/资金来源单一/品牌影响力弱/监管压力。"
        " 益语帮客户的方式是『陪伴+方法论沉淀』, 不是『代偿+一次性方案』。\n"
    )


# ============================================================
# Prompt 构造
# ============================================================


def _format_persons(persons: list[PersonFact]) -> str:
    if not persons:
        return "⚠️ 暂无 entity_type=person 数据"
    lines = []
    for p in persons:
        aliases = " (别名: " + ", ".join(p.aliases) + ")" if p.aliases else ""
        lines.append(f"  · {p.name}{aliases} — 提及 {p.mention_count} 次 (entityId={p.entity_id})")
    return "\n".join(lines)


def _format_time_anchors(anchors: list[TimeAnchorFact]) -> str:
    if not anchors:
        return "⚠️ 暂无 entity_type=date 数据"
    return "\n".join(
        f"  · {a.text} (entityId={a.entity_id}, 提及 {a.mention_count} 次)"
        for a in anchors
    )


def _format_money_anchors(anchors: list[MoneyFact]) -> str:
    if not anchors:
        return "⚠️ 暂无 entity_type=amount 数据"
    return "\n".join(
        f"  · {a.text} (entityId={a.entity_id}, 提及 {a.mention_count} 次)"
        for a in anchors
    )


def _format_atomic_facts(grouped: dict[str, list[AtomicFactRow]]) -> str:
    if not grouped:
        return "⚠️ 暂无 atomic_facts"
    lines = []
    for attr, facts in grouped.items():
        lines.append(f"  [{attr}] {len(facts)} 条:")
        for f in facts[:6]:
            subj = f.subject[:50]
            val = f.value[:80]
            lines.append(f"    - {subj} = {val}  (factId={f.id}, conf={f.confidence:.2f})")
    return "\n".join(lines)


def _format_event_lines(lines: list[EventLineFact]) -> str:
    if not lines:
        return "⚠️ 无业务主线 (event_lines)"
    parts = []
    for el in lines:
        bits = [f"  - id={el.id} | {el.name} | {el.status}/{el.stage}"]
        if el.summary:
            bits.append(f"    summary: {el.summary[:100]}")
        if el.intent:
            bits.append(f"    intent: {el.intent[:80]}")
        if el.current_blocker:
            bits.append(f"    blocker: {el.current_blocker[:80]}")
        if el.recent_decision:
            bits.append(f"    decision: {el.recent_decision[:80]}")
        if el.next_step:
            bits.append(f"    next_step: {el.next_step[:80]}")
        parts.append("\n".join(bits))
    return "\n".join(parts)


def _format_activities(activities: list[ActivityFact]) -> str:
    if not activities:
        return "  无活动流水"
    return "\n".join(
        f"  · {a.happened_at[:10]} | [{a.event_line_name}] {a.title[:40]} (actId={a.id})"
        f"\n      {a.summary[:120]}"
        for a in activities[:15]
    )


def _format_tasks(tasks: list[TaskFact]) -> str:
    if not tasks:
        return "  无任务"
    parts = []
    for t in tasks[:15]:
        bits = [f"  · taskId={t.id} | {t.title[:50]} [{t.progress_status}] owner={t.owner_name}"]
        if t.deadline_at:
            bits.append(f"    deadline: {t.deadline_at[:10]}")
        if t.next_action:
            bits.append(f"    next_action: {t.next_action[:80]}")
        if t.current_blocker:
            bits.append(f"    blocker: {t.current_blocker[:80]}")
        parts.append("\n".join(bits))
    return "\n".join(parts)


def _format_documents(docs: list[DocumentSummaryFact], total: int) -> str:
    if not docs:
        return "  无原始资料"
    lines = [f"  共 {total} 份原始资料 (显示最新 {len(docs)} 份的标题):"]
    for d in docs:
        lines.append(f"  · docId={d.id} | {d.title[:60]} [{d.doc_kind}]")
    return "\n".join(lines)


def _format_clarifications(clars: list[ClarificationFact], heading: str) -> str:
    if not clars:
        return ""
    lines = [f"\n# {heading} ({len(clars)} 条):"]
    for c in clars:
        lines.append(f"  · [{DIMENSION_LABELS.get(c.dimension, c.dimension)}] "
                     f"{c.answered_by} @ {c.answered_at[:10]}: {c.answer[:200]}")
    return "\n".join(lines)


def _format_business_context(snippets: list[BusinessContextSnippet]) -> str:
    """把 DNA snippets 渲染成 SYSTEM_PROMPT 的『默认常识』段."""
    if not snippets:
        return _default_business_context()
    lines = []
    for s in snippets:
        lines.append(f"- [{s.source} · {s.category}] {s.body}")
    return "\n".join(lines)


def build_system_prompt(bundle: ClientFactBundle) -> str:
    """把业务上下文注入 SYSTEM_PROMPT placeholder."""
    ctx = _format_business_context(bundle.business_context)
    return SYSTEM_PROMPT.replace("{BUSINESS_CONTEXT}", ctx)


def _format_glossary(glossary: list[GlossaryTerm]) -> str:
    """v1.2 · 客户字典渲染 — 让 LLM 优先用 canonical_name + 走字典分类."""
    if not glossary:
        return "⚠️ 客户字典尚未建立, LLM 自己从 facts 拼"
    by_cat: dict[str, list[GlossaryTerm]] = {}
    for t in glossary:
        by_cat.setdefault(t.category or "其他", []).append(t)
    lines = [f"客户字典共 {len(glossary)} term, 按 category 分组:"]
    for cat, terms in sorted(by_cat.items()):
        lines.append(f"\n  ## {cat} ({len(terms)})")
        for t in terms:
            alias_str = f" 别名[{', '.join(t.aliases[:4])}]" if t.aliases else ""
            defi = f" — {t.definition[:80]}" if t.definition else ""
            lines.append(f"    · {t.canonical_name}{alias_str}{defi}")
    return "\n".join(lines)


def build_user_prompt(bundle: ClientFactBundle) -> str:
    lines: list[str] = []
    lines.append("# 客户基本信息")
    lines.append(
        f"client_id={bundle.client_id} | name={bundle.client_name} | alias={bundle.client_alias or '-'}"
    )

    # v1.2 · 客户字典 (核心锚点, 必须用 canonical_name)
    lines.append("\n# ⭐ 客户字典 (这是用户确认的标准口径, 写 narrative 时优先用)")
    lines.append(_format_glossary(bundle.glossary))
    lines.append("\n规则: ")
    lines.append("  · narrative 里出现的人物/项目/术语, 必须用字典里的 canonical_name (不要用别名)")
    lines.append("  · Layer 3 (business_intro) 列项目时, 直接走字典里 category=项目 的所有 term")
    lines.append("  · Layer 4 (people) 列人物时, 直接走字典里 category=人物 的所有 term")
    lines.append("  · 字典里没有的概念再从 atomic_facts/entities 补 — 字典是锚点不是天花板")

    # v1.6 · 字典权威属性 (P0.5 防幻觉锚点 — 人审 verified 的具体值)
    if bundle.glossary_attributes:
        lines.append("\n# ⭐⭐⭐ 字典权威数据档案 (P0.5 — 人审 verified, 最高引用优先级)")
        lines.append("规则: 涉及具体数字/姓名/日期/金额/地点/评估等级, 必须优先引用本档案;")
        lines.append("      不同 scope 的多个值必须并列显式呈现 (例: 项目累计 vs 机构当前);")
        lines.append("      档案没收录的字段, 写「档案中暂未收录」而不是编造。")
        by_term: dict[str, list[Any]] = {}
        for a in bundle.glossary_attributes:
            by_term.setdefault(a.term, []).append(a)
        for term, items in by_term.items():
            lines.append(f"  · {term}:")
            for a in items:
                scope_part = f" [scope={a.scope}]" if a.scope else ""
                asof_part = f" @{a.as_of_date}" if a.as_of_date else ""
                lines.append(f"      - {a.attribute_name} = {a.value_text}{scope_part}{asof_part}")

    # v1.5 · 项目画像 — 字典 term 间关联关系 (P0 核心)
    if bundle.glossary_relations:
        lines.append("\n# ⭐⭐ 字典关联图 (P0 项目画像 — term 之间的『边』, narrative 必须体现这些关系)")
        for rel in bundle.glossary_relations:
            obj = rel.object_term or "(无对象)"
            note = f" — 证据: {rel.note[:50]}" if rel.note else ""
            lines.append(f"  · {rel.subject_term} ─[{rel.predicate}]─> {obj}{note}")
        lines.append("规则: Layer 2 cooperation / Layer 4 people / Layer 3 business_intro 必须显式呈现这些关联")

    # v1.5 · 风险信号 (P0 核心)
    if bundle.risk_signals:
        lines.append("\n# ⭐⭐ 风险信号 (P0 项目画像 — 隐藏在前 5 层里的真实风险)")
        for r in bundle.risk_signals:
            terms = f" 关联[{', '.join(r.related_terms[:3])}]" if r.related_terms else ""
            lines.append(f"  · [{r.signal_kind}/{r.severity}] {r.title}{terms}")
            if r.description:
                lines.append(f"      {r.description[:130]}")
        lines.append("规则: Layer 6 (next_steps · 风险对冲部分) 必须基于这些真实风险写, 不要编 IT 自检风险")

    # v1.5 · 承诺 (P0 核心 — 双向 + 履约状态)
    if bundle.commitments:
        lines.append("\n# ⭐⭐ 承诺网络 (P0 项目画像 — 双向商业承诺, 区分 fulfilled/pending/overdue)")
        for c in bundle.commitments:
            ddl = f" deadline={c.deadline}" if c.deadline else ""
            terms = f" 关联[{', '.join(c.related_terms[:2])}]" if c.related_terms else ""
            lines.append(f"  · {c.committer} → {c.recipient} [{c.commitment_type}/{c.status}]{ddl}{terms}")
            lines.append(f"      内容: {c.content[:100]}")
        lines.append("规则: Layer 4 commitments 直接展示这些, 不要从 task 列表臆测; pending/overdue 的优先")

    lines.append("\n# 关键人物 (entities · person, 已 LLM 抽好)")
    lines.append(_format_persons(bundle.persons))

    lines.append("\n# 关键时间锚 (entities · date, 数字=提及次数, 越高越可能是真承诺日)")
    lines.append(_format_time_anchors(bundle.time_anchors))

    lines.append("\n# 关键金额 (entities · amount)")
    lines.append(_format_money_anchors(bundle.money_anchors))

    lines.append("\n# 已抽好的业务事实 (atomic_facts, attribute=主题, 高置信度)")
    lines.append(_format_atomic_facts(bundle.atomic_facts_by_attribute))

    lines.append("\n# 业务主线 (event_lines)")
    lines.append(_format_event_lines(bundle.event_lines))

    lines.append("\n# 任务 (tasks 跟主线绑定)")
    lines.append(_format_tasks(bundle.tasks))

    lines.append("\n# 主线活动流水 (event_line_activities, 最近 15 条)")
    lines.append(_format_activities(bundle.activities))

    lines.append("\n# 原始资料标题")
    lines.append(_format_documents(bundle.documents, bundle.document_count_total))

    if bundle.profile:
        lines.append("\n# 用户手填战略画像 (client_strategic_profiles)")
        for k, v in (
            ("industry", bundle.profile.industry),
            ("scale", bundle.profile.scale),
            ("current_needs", bundle.profile.current_needs),
            ("pain_points", bundle.profile.pain_points),
            ("strategic_value_to_yiyu", bundle.profile.strategic_value_to_yiyu),
            ("decision_chain", bundle.profile.decision_chain),
        ):
            if v:
                lines.append(f"  · {k}: {v[:150]}")

    lines.append(_format_clarifications(bundle.applied_clarifications, "历史澄清 (已 applied, 上一版叙事吸纳过)"))
    lines.append(_format_clarifications(bundle.pending_clarifications, "本次新澄清 (必须吸纳进本版)"))

    lines.append("\n# 数据中心健康度 (供你判断哪些维度数据足/不足)")
    lines.append(json.dumps(bundle.health, ensure_ascii=False, indent=2))

    lines.append("\n# 维度生成指引")
    for d in DIMENSIONS:
        lines.append(f"  - {d} · {DIMENSION_BRIEF[d]}")

    lines.append(
        "\n生成 6 段叙事 + overallConfidence (0.0-1.0). "
        "对每段叙事的关键判断都要在 references 数组里点回真实 sourceType + sourceId。"
    )

    # 末尾再喊一遍元规则 — LLM 在长 prompt 末尾权重高
    lines.append("\n" + "=" * 60)
    lines.append("== 🚨 写之前最后再确认一遍元规则 🚨 ==")
    lines.append("=" * 60)
    lines.append("")
    lines.append("写每一句之前问自己 2 个问题:")
    lines.append("")
    lines.append("**Q1: 这句话来自哪条 atomic_fact / entity / event_line / task?**")
    lines.append("    答得上来 → 在 references 列出 sourceId。")
    lines.append("    答不上来 → 删掉, 或写进 openClarifications。")
    lines.append("")
    lines.append("**Q2: 这句话是哪种引用?**")
    lines.append("    (a) 复述 fact (直接复述, 不加因果)")
    lines.append("    (b) 顾问第一人称判断 (『我作为顾问看...』)")
    lines.append("    (c) 澄清问题 (放进 openClarifications)")
    lines.append("    (d) 范围声明 (『facts 里没有提到 X』)")
    lines.append("    (a)(b)(c)(d) — OK 写")
    lines.append("    **(e) 隐含归因 — 客户立刻开除你**")
    lines.append("")
    lines.append("**(e) 隐含归因的识别方法**: 句子里出现下面任一结构, 就是 (e):")
    lines.append("  · 『X, **因此** Y』『X, **所以** Y』 (把 fact X 链到客户决策 Y)")
    lines.append("  · 『客户**希望**...』『客户**认为**...』『客户**期待**...』『客户**主动**...』 (替客户表态)")
    lines.append("  · 『**为此** 客户...』『**因为** X 客户...』 (替客户给 fact 安一个动机)")
    lines.append("  · 任何把 fact 跟 *客户动机/选择/诉求* 连起来的因果连接")
    lines.append("  · 把 mention_count 高 (机器统计) 直接说成 *决策者/创始人/拍板者* (身份归因)")
    lines.append("")
    lines.append("**(e) 的正确改写**: 用 (b) 顾问判断 + 第一人称限定, 或 (c) 放进 openClarifications。")
    lines.append("  例 1: ❌ 『18-24 岁抑郁峰值, **因此**日慈选这个赛道』")
    lines.append("        ✅ 『fact #X 显示 18-24 岁抑郁峰值是行业事实。**我作为顾问看**, 这通常会是公益机构选服务对象的依据 — 但日慈是不是真把 18-24 岁锁定, 需要澄清』")
    lines.append("        ✅ openClarifications: [『日慈核心服务对象是 18-24 岁? 还是包括其他年龄段?』]")
    lines.append("  例 2: ❌ 『高老师提及 93 次, 是核心决策人』")
    lines.append("        ✅ 『entity #X 显示高老师在客户资料中被提及 93 次, 远超其他人。**我作为顾问看**, 这通常意味着位置核心 — 但 facts 里没有他职务/权限的明确说明, 需澄清』")
    lines.append("")
    lines.append("**项目列表 (Part B)**: 必须穷举 facts 里出现的所有项目名, 不要选择性省略。")
    lines.append("")
    lines.append("**(Q4 v1.0 新增) 这层是事实陈述层还是判断层?**")
    lines.append("    事实陈述层 = essence (项目本质) / business_intro (业务介绍) / timeline (时间线)")
    lines.append("        → narrative **不要写**『我作为顾问看』『我推荐』『我判断』这种顾问视角")
    lines.append("        → 只列已知事实, 让客户看完一目了然『这家机构是什么』『有哪些项目』『发生过什么』")
    lines.append("    判断层 = cooperation (合作关系) / next_steps (承诺与下一步)")
    lines.append("        → 可以用『我作为顾问看』限定推断")
    lines.append("    people 层: 描述事实 (谁做了什么) 为主, 推断角色时才用『我作为顾问看』限定")
    lines.append("")
    lines.append("**(Q5 v1.0 新增) narrative 文本里有没有 uuid/hash?**")
    lines.append("    ❌ 错: 『atomic_fact #eafa2c6f-c597-4d9d-b205-a5fa4f7f970b 显示...』")
    lines.append("    ✅ 对: 『日慈公益基金会总部位于广州』(sourceId 放 references 数组, 不在 narrative 文本里)")
    lines.append("    narrative 是给客户读的干净中文叙事, 引用关系全部塞 references 数组让前端折叠显示。")
    lines.append("")
    lines.append("**Q3 (v0.9 新增): 这句话里的『并列项』每个都有 fact 支持吗?**")
    lines.append("    一个句子里有 (A、B、C) 这种并列, 必须 A、B、C **每一个**都有对应 fact。")
    lines.append("    不允许『A、C 有据』给 B 当通行证夹带。")
    lines.append("    如果 B 无据 → 把 B 单独拆出来用 (b) 顾问判断限定, 或放进 openClarifications。")
    lines.append("    例: ❌ 『益语核心是: 项目梳理 + 内部管理体系搭建 + 战略落地』 (B 无据)")
    lines.append("        ✅ 『event_line 显示益语核心是: 项目梳理 + 战略落地; 我作为顾问看, 可能还涉及内部管理体系层面, 需澄清』")
    lines.append("")
    lines.append("**写每个并列句之前, 单独拎出每个并列项问『这个名词短语对应哪条 fact?』**")
    lines.append("**这套元规则适用于任何客户 (日慈/黔行/为爱前行/华润...). 它防的是结构, 不防具体词。**")

    return "\n".join(lines)


# ============================================================
# 主流程 · 调 LLM + 解析 + 输出符合 cloud schema 的 dict
# ============================================================


# 注: 之前这里有一个硬编码黑名单 _KNOWN_HALLUCINATION_PATTERNS — 已删除。
# 删除原因 (顾源源 2026/5/16 指示『借假修真』):
#   黑名单只能 patch 已知客户的已知套话, 换客户/换 LLM 全失效, 是治标不治本。
#   真正解决方案是 SYSTEM_PROMPT 里的「元规则」(强制 LLM 区分 4 类引用方式),
#   让 LLM 自己识别『事实陈述 vs 隐含归因』, 不靠下游黑名单兜底。
# 长期方向: atomic_facts 加 source_role provenance 字段 (跟 Task #61 一起做)。


_SOURCEID_NOISE_RE = re.compile(
    r"\s*(?:[\(（])?\s*(?:atomic_fact|entity|event_line(?:_activity)?|task|document|data_center_gap|data_center_quality|v2_doc|v2doc|narrative)\s*#\s*[A-Za-z0-9][A-Za-z0-9_\-]*\s*[)）]?\s*"
)
_DASHES_RE = re.compile(r"[，、,]\s*[，、,；;]+|；\s*；|，\s*，")
_LEAD_PUNCT_RE = re.compile(r"^\s*[，。；、：,;.]+\s*")


def _strip_sourceid_noise(narrative: str) -> str:
    """从 narrative 里剔除 LLM 误塞的 uuid/sourceId — 给客户读的是干净中文."""
    cleaned = _SOURCEID_NOISE_RE.sub(" ", narrative)
    # 清理因剔除后的连续标点
    cleaned = _DASHES_RE.sub("，", cleaned)
    # 清理段落开头多余标点
    parts = []
    for line in cleaned.split("\n"):
        line = _LEAD_PUNCT_RE.sub("", line).strip()
        parts.append(line)
    return "\n".join(parts).strip()


def _validate_dim(payload: Any, dim: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _stub_dim(dim, "LLM 输出格式不合法")
    narrative = str(payload.get("narrative") or "").strip()
    if not narrative:
        return _stub_dim(dim, "LLM 没给出叙事")
    # 后处理: 剔除 uuid/sourceId 噪音 (LLM 偶尔会把它们塞进 narrative 文本)
    narrative = _strip_sourceid_noise(narrative)
    confidence = str(payload.get("confidence") or "low").lower()
    if confidence not in ("high", "medium", "low"):
        confidence = "low"
    refs_raw = payload.get("references") or []
    refs: list[dict[str, str]] = []
    if isinstance(refs_raw, list):
        for r in refs_raw:
            if not isinstance(r, dict):
                continue
            st = str(r.get("sourceType") or "").strip()
            sid = str(r.get("sourceId") or "").strip()
            if not st or not sid:
                continue
            refs.append({
                "sourceType": st,
                "sourceId": sid,
                "label": str(r.get("label") or "").strip(),
                "confidence": str(r.get("confidence") or "medium"),
            })
    open_clar = [
        str(x).strip()
        for x in (payload.get("openClarifications") or [])
        if str(x).strip()
    ]
    builds_on = str(payload.get("buildsOn") or "").strip()
    # 把 buildsOn 拼到 narrative 末尾作为可见的递进证据 (cloud schema 没这字段, 走 narrative)
    narrative_with_chain = narrative
    if builds_on and dim != "essence":  # Layer 1 essence 没有上层
        narrative_with_chain = f"{narrative}\n\n[递进逻辑] {builds_on}"
    return {
        "narrative": narrative_with_chain,
        "confidence": confidence,
        "confidenceReason": str(payload.get("confidenceReason") or ""),
        "references": refs,
        "dataLayerGap": str(payload.get("dataLayerGap") or ""),
        "openClarifications": open_clar,
    }


def _stub_dim(dim: str, reason: str) -> dict[str, Any]:
    return {
        "narrative": f"⏳ AI 暂时讲不出此维度 — {reason}",
        "confidence": "low",
        "confidenceReason": reason,
        "references": [],
        "dataLayerGap": reason,
        "openClarifications": [],
    }


def generate_narrative_dimensions(
    ai: AiService,
    bundle: ClientFactBundle,
) -> tuple[dict[str, dict[str, Any]], float, str]:
    """跑一次 LLM, 返回 (dimensions_dict, overallConfidence, model_used).

    异常时返回 stub dimensions (不抛, 让上层有降级 fallback).
    """
    health = ai.get_health()
    if not health.ready:
        return _all_stub("AI 未就绪 / 没配 API key"), 0.0, "stub"

    prompt = build_user_prompt(bundle)
    system_prompt = build_system_prompt(bundle)
    try:
        result = ai._qwen_generate(  # noqa: SLF001 — intentional reuse
            prompt,
            system_prompt,
            NARRATIVE_OUTPUT_SCHEMA,
            timeout_seconds=360.0,   # v1.3 字典段大 + 6 层叙事, 给 6 分钟
            max_tokens=10000,        # 防 LLM 输出 JSON 截断
            temperature=0.3,
        )
    except AiInvocationError as exc:
        return _all_stub(f"AI 调用失败: {getattr(exc, 'detail', str(exc))[:200]}"), 0.0, "stub"
    except Exception as exc:  # noqa: BLE001
        return _all_stub(f"未知异常: {type(exc).__name__}: {str(exc)[:200]}"), 0.0, "stub"

    if not isinstance(result, dict):
        return _all_stub("LLM 返回不是 dict"), 0.0, "stub"

    dims = {d: _validate_dim(result.get(d), d) for d in DIMENSIONS}
    try:
        overall = float(result.get("overallConfidence") or 0.0)
    except (TypeError, ValueError):
        overall = 0.0
    return dims, overall, ai.current_provider() if hasattr(ai, "current_provider") else "doubao"


def _all_stub(reason: str) -> dict[str, dict[str, Any]]:
    return {d: _stub_dim(d, reason) for d in DIMENSIONS}


def compute_data_layer_gaps(bundle: ClientFactBundle) -> list[str]:
    """诚实暴露数据中心加工层缺口 — 给 UI 顶部固定显示."""
    gaps: list[str] = list(bundle.health.get("gaps", []))
    if not bundle.persons:
        gaps.append("entities · person 表无数据 (LLM 抽取未跑或失败)")
    if not bundle.atomic_facts_by_attribute:
        gaps.append("atomic_facts 表无 active 数据 (业务事实未抽)")
    if bundle.document_count_total > 30 and len(bundle.atomic_facts_by_attribute) < 5:
        gaps.append(
            f"原子事实分类过少 — {bundle.document_count_total} 份文档只分出 "
            f"{len(bundle.atomic_facts_by_attribute)} 类 attribute"
        )
    return gaps


def bundle_summary_for_debug(bundle: ClientFactBundle) -> dict[str, Any]:
    """方便调试 / API 暴露给 UI 看 collector 拿了什么."""
    return {
        "clientName": bundle.client_name,
        "personCount": len(bundle.persons),
        "personTop": [p.name for p in bundle.persons[:10]],
        "timeAnchorCount": len(bundle.time_anchors),
        "moneyAnchorCount": len(bundle.money_anchors),
        "atomicAttrCount": len(bundle.atomic_facts_by_attribute),
        "atomicAttrs": list(bundle.atomic_facts_by_attribute.keys())[:15],
        "eventLineCount": len(bundle.event_lines),
        "activityCount": len(bundle.activities),
        "taskCount": len(bundle.tasks),
        "documentCount": bundle.document_count_total,
        "hasProfile": bundle.profile is not None,
        "health": bundle.health,
    }
