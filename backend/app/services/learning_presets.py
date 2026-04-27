from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class LearningPresetCard:
    id: str
    title: str
    category: str
    stage: str
    scenario: str
    why: str
    when_to_use: list[str]
    steps: list[str]
    checklist: list[str]
    anti_patterns: list[str]
    example_prompt: str
    output_template: str
    evidence_requirement: list[str]
    linked_module: str
    difficulty: Literal["入门", "进阶", "熟练"]
    estimated_minutes: int
    source_type: Literal["preset"] = "preset"


LEARNING_PRESET_CARDS: list[LearningPresetCard] = [
    LearningPresetCard(
        id="org_intro_three_part",
        title="机构介绍三段式",
        category="信息核对",
        stage="信息核对",
        scenario="需要介绍一家基金会、公益机构、客户组织时",
        why="先说清它是谁、正在做什么、为什么现在值得关注，可以避免介绍变成资料堆砌。",
        when_to_use=["介绍基金会", "介绍机构", "客户资料初读", "写组织简介"],
        steps=[
            "先从资料中找出机构定位、使命、服务对象。",
            "再列出正在推进的核心项目或业务线。",
            "最后说明它与当前合作、会议或战略陪伴的关系。",
        ],
        checklist=[
            "是否说清楚这家机构是谁？",
            "是否说清楚它主要服务谁？",
            "是否列出当前资料中能确认的项目？",
            "是否区分了事实、判断和待确认信息？",
            "是否引用了资料来源？",
        ],
        anti_patterns=[
            "只罗列文件名，不形成介绍。",
            "把候选判断当成事实。",
            "为了显得完整而编造机构背景。",
        ],
        example_prompt="请根据已上传资料，介绍这家基金会，要求简洁清晰并引用原文。",
        output_template="它是谁 / 它正在做什么 / 当前合作或关注点 / 缺失信息",
        evidence_requirement=["机构介绍资料", "项目资料", "会议纪要或战略资料"],
        linked_module="客户工作台",
        difficulty="入门",
        estimated_minutes=8,
    ),
    LearningPresetCard(
        id="project_intro_five_elements",
        title="项目介绍五要素",
        category="项目认知",
        stage="信息核对",
        scenario="需要介绍某个公益项目、客户项目或合作项目时",
        why="项目介绍不能只写名称，要把对象、问题、方法、成果和下一步串起来。",
        when_to_use=["介绍项目", "项目资料整理", "项目一页纸", "客户项目初读"],
        steps=[
            "确认项目服务对象。",
            "确认项目试图解决的问题。",
            "提炼项目的主要做法。",
            "查找已有成果或阶段进展。",
            "写出下一步仍需补充的信息。",
        ],
        checklist=[
            "服务对象是否明确？",
            "项目问题是否明确？",
            "做法是否来自资料而不是猜测？",
            "成果或进展是否有证据？",
            "是否列出下一步待确认项？",
        ],
        anti_patterns=[
            "只写项目名称。",
            "把项目愿景当成已发生成果。",
            "忽略项目当前阶段。",
        ],
        example_prompt="请介绍这个项目，包括服务对象、主要做法、当前进展和下一步。",
        output_template="服务对象 / 问题 / 方法 / 进展 / 下一步",
        evidence_requirement=["项目方案", "会议纪要", "项目进展材料"],
        linked_module="客户工作台",
        difficulty="入门",
        estimated_minutes=10,
    ),
    LearningPresetCard(
        id="fact_judgment_suggestion_split",
        title="事实、判断、建议分离卡",
        category="战略研判",
        stage="思考与研判",
        scenario="资料很多、判断很多，但不确定哪些能作为结论时",
        why="战略陪伴里最容易出错的是把观察、判断和建议混在一起。",
        when_to_use=["正式判断", "战略研判", "资料总结", "会议后分析"],
        steps=[
            "把资料中明确出现的信息放入事实栏。",
            "把基于事实形成的解释放入判断栏。",
            "把需要用户采取的动作放入建议栏。",
            "对每条判断标注证据是否足够。",
        ],
        checklist=[
            "事实是否能找到原文？",
            "判断是否有至少两条证据？",
            "建议是否说明了下一步动作？",
            "候选判断是否单独标注？",
        ],
        anti_patterns=[
            "用一句话同时写事实、判断和建议。",
            "证据不足却写成正式结论。",
            "没有引用来源。",
        ],
        example_prompt="请把这批资料拆成事实、判断和建议，不要把待确认内容当成结论。",
        output_template="事实 / 判断 / 建议 / 待确认",
        evidence_requirement=["原始资料", "会议纪要", "任务记录"],
        linked_module="战略陪伴",
        difficulty="进阶",
        estimated_minutes=12,
    ),
    LearningPresetCard(
        id="evidence_sufficiency_check",
        title="证据够不够检查卡",
        category="信息核对",
        stage="信息核对",
        scenario="准备生成正式回答、正式判断或客户介绍前",
        why="先判断证据够不够，可以避免系统给出看似完整但不可靠的回答。",
        when_to_use=["引用原文", "正式判断", "客户介绍", "项目介绍"],
        steps=[
            "列出当前问题需要回答的关键点。",
            "为每个关键点找对应证据。",
            "标注证据来自原文、会议、任务还是状态池。",
            "证据不足时生成追问或缺失资料清单。",
        ],
        checklist=[
            "是否每个关键点都有证据？",
            "证据是否来自原始资料？",
            "是否把状态池提醒和正式证据分开？",
            "是否列出缺口？",
        ],
        anti_patterns=[
            "只要有一个文件就开始长篇回答。",
            "把文件标题当作内容证据。",
            "不说明缺失信息。",
        ],
        example_prompt="请判断当前资料是否足够支撑这个回答，并列出缺失信息。",
        output_template="问题点 / 已有证据 / 证据缺口 / 下一步追问",
        evidence_requirement=["原始资料", "证据卡", "会议纪要"],
        linked_module="客户工作台",
        difficulty="进阶",
        estimated_minutes=8,
    ),
    LearningPresetCard(
        id="meeting_minutes_four_part",
        title="会议纪要四分法",
        category="会议与沟通",
        stage="内部对齐",
        scenario="需要提炼会议纪要、飞书妙记或客户沟通记录时",
        why="会议纪要要拆成事实、决定、行动和风险，才能服务后续推进。",
        when_to_use=["会议纪要", "飞书妙记", "沟通记录", "会后总结"],
        steps=[
            "先提取会议讨论的事实背景。",
            "再找出已经形成的决定。",
            "然后列出行动项、负责人和时间点。",
            "最后单独列出风险和未决问题。",
        ],
        checklist=[
            "是否区分讨论内容和最终决定？",
            "是否提取了行动项？",
            "是否有负责人或下一步？",
            "是否列出风险和未决问题？",
        ],
        anti_patterns=[
            "把整段纪要直接摘要成一段话。",
            "只写讨论，不写行动。",
            "把未决问题写成已决定事项。",
        ],
        example_prompt="请提炼最新会议纪要，按事实、决定、行动、风险输出。",
        output_template="事实 / 决定 / 行动项 / 风险与未决问题",
        evidence_requirement=["会议纪要", "会议行动项", "任务记录"],
        linked_module="客户工作台",
        difficulty="入门",
        estimated_minutes=10,
    ),
    LearningPresetCard(
        id="next_action_extraction",
        title="下一步行动提取卡",
        category="交付闭环",
        stage="沟通推进",
        scenario="用户问接下来做什么、下一步怎么推进时",
        why="下一步不能只来自模型判断，要综合任务、会议行动项、风险和未决问题。",
        when_to_use=["下一步", "接下来做什么", "本周推进", "行动项"],
        steps=[
            "先读取未完成任务。",
            "再读取最近会议行动项。",
            "再补充风险和未决问题。",
            "最后按已明确、待确认、需补资料三类输出。",
        ],
        checklist=[
            "是否有明确行动？",
            "是否有负责人？",
            "是否有时间点？",
            "哪些只是候选提醒？",
            "哪些需要先补证据？",
        ],
        anti_patterns=[
            "把风险当作行动。",
            "把候选判断当作任务。",
            "只给泛泛建议。",
        ],
        example_prompt="这个客户接下来要做什么？请按明确行动、待确认事项、风险提醒输出。",
        output_template="明确行动 / 待确认事项 / 风险提醒 / 需补资料",
        evidence_requirement=["任务", "会议行动项", "事件线", "风险记录"],
        linked_module="任务与日历",
        difficulty="进阶",
        estimated_minutes=10,
    ),
    LearningPresetCard(
        id="pre_meeting_three_questions",
        title="会前 3 个必须确认的问题",
        category="会议与沟通",
        stage="内部对齐",
        scenario="准备客户沟通、战略陪伴会议或内部评审前",
        why="会前只要把三个关键问题问清，就能显著降低会后返工。",
        when_to_use=["会前准备", "客户沟通", "战略陪伴会议", "内部对齐"],
        steps=[
            "确认本次会议必须形成什么结论。",
            "确认对方最关心的问题是什么。",
            "确认哪些资料或决定还缺口径。",
        ],
        checklist=[
            "会议目标是否清楚？",
            "要确认的问题是否不超过 3 个？",
            "是否准备了资料依据？",
            "是否知道会后要转成什么任务？",
        ],
        anti_patterns=[
            "带着一堆资料开会但没有问题。",
            "把会议开成信息同步。",
            "没有会后任务。",
        ],
        example_prompt="请帮我为这次客户会议准备 3 个必须确认的问题。",
        output_template="必须确认的问题 / 为什么要问 / 需要带的资料 / 会后动作",
        evidence_requirement=["会议背景", "客户资料", "任务上下文"],
        linked_module="战略陪伴",
        difficulty="入门",
        estimated_minutes=6,
    ),
    LearningPresetCard(
        id="candidate_to_official_judgment",
        title="候选判断转正式判断卡",
        category="战略研判",
        stage="思考与研判",
        scenario="系统已有待确认判断，但还没有正式判断时",
        why="正式判断必须有证据、边界和审批，不应由模型直接生成。",
        when_to_use=["待确认判断", "正式判断", "战略研判", "证据不足"],
        steps=[
            "选出一个候选判断。",
            "绑定至少两条证据。",
            "写清适用边界。",
            "列出反例或风险。",
            "提交人工确认。",
        ],
        checklist=[
            "是否有至少两条证据？",
            "是否写清判断边界？",
            "是否列出风险？",
            "是否经过人工确认？",
        ],
        anti_patterns=[
            "把 candidate 直接显示为正式判断。",
            "没有证据就批准。",
            "忽略相反证据。",
        ],
        example_prompt="请把这个候选判断整理成正式判断草案，并说明还缺哪些证据。",
        output_template="判断草案 / 证据 / 适用边界 / 风险 / 审批建议",
        evidence_requirement=["证据卡", "原始资料", "会议纪要"],
        linked_module="战略陪伴",
        difficulty="熟练",
        estimated_minutes=15,
    ),
    LearningPresetCard(
        id="one_page_brief",
        title="一页简介写作卡",
        category="方案产出",
        stage="方案产出",
        scenario="需要把客户、项目或合作机会写成一页简介时",
        why="一页简介要帮助别人快速理解，而不是复制资料。",
        when_to_use=["客户简介", "项目简介", "对内汇报", "合作说明"],
        steps=[
            "先写 100 字以内的执行摘要。",
            "再写背景、项目、当前进展。",
            "最后写风险、缺口和下一步。",
        ],
        checklist=[
            "开头是否能让人立刻知道对象是谁？",
            "是否列出核心项目？",
            "是否说明当前阶段？",
            "是否列出下一步？",
        ],
        anti_patterns=[
            "照搬材料。",
            "缺少当前阶段。",
            "没有下一步。",
        ],
        example_prompt="请根据资料写一页客户简介，适合内部快速阅读。",
        output_template="执行摘要 / 背景 / 项目 / 当前进展 / 下一步",
        evidence_requirement=["客户资料", "项目资料", "会议纪要"],
        linked_module="客户工作台",
        difficulty="入门",
        estimated_minutes=12,
    ),
    LearningPresetCard(
        id="project_risk_scan",
        title="项目风险扫描卡",
        category="项目认知",
        stage="沟通推进",
        scenario="项目推进中出现卡点、延迟、协作不清时",
        why="风险不是负面评价，而是提前识别会影响交付的条件。",
        when_to_use=["项目风险", "卡点", "推进受阻", "客户协作"],
        steps=[
            "识别资料风险。",
            "识别决策风险。",
            "识别协作风险。",
            "识别时间风险。",
            "给每个风险配一个下一步动作。",
        ],
        checklist=[
            "资料是否齐？",
            "谁有决策权？",
            "责任边界是否清楚？",
            "时间点是否明确？",
            "风险是否有处理动作？",
        ],
        anti_patterns=[
            "只说有风险，不说怎么处理。",
            "把不确定性写成事实。",
            "把责任全部推给客户。",
        ],
        example_prompt="请扫描这个项目当前风险，并给出下一步处理建议。",
        output_template="风险类型 / 具体表现 / 影响 / 下一步动作",
        evidence_requirement=["项目任务", "会议纪要", "风险记录"],
        linked_module="项目认知",
        difficulty="进阶",
        estimated_minutes=10,
    ),
    LearningPresetCard(
        id="method_card_writing",
        title="方法卡写作卡",
        category="复盘沉淀",
        stage="复盘沉淀",
        scenario="一次任务做完后，需要沉淀成团队可复用经验",
        why="复盘只有变成方法卡，才可能被下次任务自动推荐。",
        when_to_use=["复盘", "经验沉淀", "成长手册", "团队方法"],
        steps=[
            "写清这次解决了什么问题。",
            "写清有效动作是什么。",
            "写清适用边界。",
            "写清下次什么时候推荐。",
        ],
        checklist=[
            "是否有真实任务来源？",
            "是否有有效动作？",
            "是否有适用边界？",
            "是否有下次触发场景？",
        ],
        anti_patterns=[
            "只写心得，不写方法。",
            "没有适用边界。",
            "无法被下次复用。",
        ],
        example_prompt="请把这次任务复盘成一张团队可复用的方法卡。",
        output_template="问题 / 有效动作 / 适用场景 / 不适用场景 / 下次触发词",
        evidence_requirement=["任务记录", "交付物", "复盘说明"],
        linked_module="成长手册",
        difficulty="进阶",
        estimated_minutes=12,
    ),
    LearningPresetCard(
        id="missing_info_followup",
        title="缺失信息追问卡",
        category="信息核对",
        stage="需求接收",
        scenario="资料不足、问题无法稳定回答时",
        why="系统不能硬答时，应该生成清楚的追问和补资料清单。",
        when_to_use=["资料不足", "无法判断", "需要补充材料", "客户追问"],
        steps=[
            "先说明当前能确认什么。",
            "再说明不能确认什么。",
            "把缺口转成 3-5 个具体追问。",
            "标注每个追问的用途。",
        ],
        checklist=[
            "是否先说清已有信息？",
            "是否没有编造缺失内容？",
            "追问是否具体？",
            "是否说明为什么要补？",
        ],
        anti_patterns=[
            "直接说资料不足就结束。",
            "提出过于抽象的问题。",
            "追问和当前任务无关。",
        ],
        example_prompt="当前资料不足，请帮我列出需要向客户追问的问题。",
        output_template="已确认 / 未确认 / 追问 / 追问目的",
        evidence_requirement=["当前资料索引", "任务目标"],
        linked_module="客户工作台",
        difficulty="入门",
        estimated_minutes=6,
    ),
]


def list_learning_presets() -> list[LearningPresetCard]:
    return list(LEARNING_PRESET_CARDS)


def default_starter_learning_presets(mode: str = "global") -> list[LearningPresetCard]:
    if mode == "strategic":
        ids = [
            "org_intro_three_part",
            "meeting_minutes_four_part",
            "next_action_extraction",
            "fact_judgment_suggestion_split",
            "evidence_sufficiency_check",
            "method_card_writing",
        ]
    else:
        ids = [
            "missing_info_followup",
            "fact_judgment_suggestion_split",
            "method_card_writing",
        ]
    by_id = {card.id: card for card in LEARNING_PRESET_CARDS}
    return [by_id[item_id] for item_id in ids if item_id in by_id]


def match_learning_presets(
    *,
    task_title: str,
    task_desc: str = "",
    phase: str = "",
    client_name: str | None = None,
    current_blocker: str | None = None,
    evidence_count: int = 0,
    mode: str = "global",
) -> list[LearningPresetCard]:
    text = " ".join(
        part
        for part in [
            task_title,
            task_desc,
            phase,
            client_name or "",
            current_blocker or "",
        ]
        if part
    )
    scored: list[tuple[int, LearningPresetCard]] = []
    for card in LEARNING_PRESET_CARDS:
        score = 0
        for keyword in card.when_to_use:
            if keyword and keyword in text:
                score += 4
        if card.stage and card.stage == phase:
            score += 3
        if "介绍" in text and card.id in {
            "org_intro_three_part",
            "project_intro_five_elements",
            "one_page_brief",
            "fact_judgment_suggestion_split",
        }:
            score += 8
        if "介绍" in text and card.id == "fact_judgment_suggestion_split":
            score += 6
        if any(k in text for k in ["基金会", "机构", "组织", "客户"]):
            if card.id in {"org_intro_three_part", "one_page_brief", "evidence_sufficiency_check"}:
                score += 6
            if card.id == "fact_judgment_suggestion_split":
                score += 4
        if any(k in text for k in ["项目", "项目资料", "项目介绍"]):
            if card.id in {"project_intro_five_elements", "project_risk_scan"}:
                score += 6
        if any(k in text for k in ["会议", "纪要", "飞书", "沟通记录"]):
            if card.id in {
                "meeting_minutes_four_part",
                "pre_meeting_three_questions",
                "next_action_extraction",
            }:
                score += 8
        if any(k in text for k in ["下一步", "接下来", "待办", "行动项", "推进"]):
            if card.id in {"next_action_extraction", "project_risk_scan"}:
                score += 8
        if any(k in text for k in ["正式判断", "候选判断", "待确认判断", "研判"]):
            if card.id in {
                "candidate_to_official_judgment",
                "fact_judgment_suggestion_split",
                "evidence_sufficiency_check",
            }:
                score += 8
        if evidence_count <= 0 and card.id in {"missing_info_followup", "evidence_sufficiency_check"}:
            score += 5
        if score > 0:
            scored.append((score, card))
    scored.sort(key=lambda item: item[0], reverse=True)
    if not scored:
        return default_starter_learning_presets(mode=mode)
    return [card for _, card in scored[:4]]


def preset_card_to_generic_lesson(card: LearningPresetCard, *, task_title: str | None = None):
    from app.models import GrowthGenericLessonRecord

    return GrowthGenericLessonRecord(
        id=f"preset-{card.id}",
        title=card.title,
        judgment=card.why,
        applicableScene=card.scenario if not task_title else f"{card.scenario}；当前任务：{task_title}",
        whyItWorks=card.why,
        reuseHint=card.output_template,
        linkedContext=None,
    )


def preset_card_to_support_material(card: LearningPresetCard):
    from app.models import GrowthWorkbenchMaterialRecord

    return GrowthWorkbenchMaterialRecord(
        id=f"preset-material-{card.id}",
        title=card.title,
        type="模板工具",
        scenario=card.scenario,
        summary=" / ".join(card.steps[:3]),
        linkedContext=None,
    )


def build_actions_from_presets(cards: list[LearningPresetCard]):
    from app.models import GrowthWorkbenchActionRecord

    def first_step(index: int) -> str:
        card = cards[index] if index < len(cards) else None
        if card and card.steps:
            return card.steps[0]
        return "先选择一张方法卡开始。"

    actions_before = [
        GrowthWorkbenchActionRecord(
            id="preset-before-1",
            title="先确认资料和问题",
            output=first_step(0),
            scenario="开始前",
            actionLabel="查看方法卡",
            supportTitle="先确保对象和问题明确",
            kind="support",
        ),
        GrowthWorkbenchActionRecord(
            id="preset-before-2",
            title="先看证据够不够",
            output=first_step(1),
            scenario="开始前",
            actionLabel="做证据检查",
            supportTitle="先看证据再给判断",
            kind="support",
        ),
        GrowthWorkbenchActionRecord(
            id="preset-before-3",
            title="先列出会前关键问题",
            output=first_step(2),
            scenario="会前准备",
            actionLabel="生成会前问题",
            supportTitle="避免会后返工",
            kind="process",
        ),
    ]
    actions_during = [
        GrowthWorkbenchActionRecord(
            id="preset-during-1",
            title="按方法卡完成当前输出",
            output="把当前对象转成可执行输出，而不是泛泛建议。",
            scenario="执行中",
            actionLabel="打开练习",
            supportTitle="按步骤推进",
            kind="process",
        ),
        GrowthWorkbenchActionRecord(
            id="preset-during-2",
            title="用模板拆解事实 / 判断 / 建议",
            output="先保证事实可追溯，再形成判断与建议。",
            scenario="执行中",
            actionLabel="应用模板",
            supportTitle="避免事实与判断混写",
            kind="process",
        ),
        GrowthWorkbenchActionRecord(
            id="preset-during-3",
            title="用会议四分法提炼纪要",
            output="事实 / 决定 / 行动 / 风险四栏完整输出。",
            scenario="执行中",
            actionLabel="提炼纪要",
            supportTitle="把讨论转成行动",
            kind="process",
        ),
    ]
    actions_after = [
        GrowthWorkbenchActionRecord(
            id="preset-after-1",
            title="写回成长手册",
            output="记录问题、有效动作、适用边界和复用提示。",
            scenario="完成后",
            actionLabel="记录经验",
            supportTitle="沉淀为可复用资产",
            kind="compose",
        ),
        GrowthWorkbenchActionRecord(
            id="preset-after-2",
            title="转成任务继续推进",
            output="把学习动作拆成下一步任务和负责人。",
            scenario="完成后",
            actionLabel="转为任务",
            supportTitle="形成执行闭环",
            kind="task",
        ),
        GrowthWorkbenchActionRecord(
            id="preset-after-3",
            title="沉淀可复用方法卡",
            output="写清触发场景和不适用边界，方便下次推荐。",
            scenario="完成后",
            actionLabel="标记已复用",
            supportTitle="进入方法库",
            kind="compose",
        ),
    ]
    return actions_before, actions_during, actions_after
