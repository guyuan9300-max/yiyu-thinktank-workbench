from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

WorkspaceFollowupScenario = Literal[
    "strategy_judgment",
    "organization_design",
    "business_project_design",
    "external_communication",
    "action_preparation",
    "research_upgrade",
    "risk_review",
    "file_search",
    "work_status",
    "general_consulting",
]

WorkspaceFollowupGenerationMode = Literal["consulting", "file_search", "fallback"]


@dataclass(frozen=True)
class WorkspaceFollowupResult:
    questions: list[str]
    scenario: WorkspaceFollowupScenario
    generation_mode: WorkspaceFollowupGenerationMode
    rejected_count: int = 0


@dataclass(frozen=True)
class WorkspaceFollowupNormalizeResult:
    questions: list[str]
    rejected_count: int = 0


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").lower())


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _clean_question(raw: str) -> str:
    text = str(raw or "").strip()
    text = re.sub(r"^[\-\*\d\.\)\(（）、\s]+", "", text).strip()
    text = text.strip("“”\"'`")
    if len(text) > 96:
        text = text[:96].rstrip("，,；;：:。.")
    if text and not text.endswith(("？", "?")):
        text = f"{text.rstrip('，,；;：:。.!！') or text}？"
    return text


def _is_overly_narrow_fact_question(question: str, scenario: WorkspaceFollowupScenario) -> bool:
    if scenario == "file_search":
        return False
    compact = _compact(question)
    narrow_tokens = (
        "哪份文件",
        "哪份原文",
        "哪份资料",
        "哪个文件",
        "哪个文档",
        "第几页",
        "出处在哪",
        "原文在哪",
        "来源是什么",
        "官方稿",
        "具体名单",
        "有哪些文件",
        "哪些文件",
        "哪些原文",
    )
    if _contains_any(compact, narrow_tokens):
        return True
    if "什么时候" in compact and _contains_any(compact, ("完成", "发布", "确定", "公开", "上线")):
        return True
    return False


def _is_low_value_generic_question(question: str) -> bool:
    compact = _compact(question)
    generic_questions = {
        _compact("下一步应该做什么？"),
        _compact("还需要补充什么资料？"),
        _compact("这个问题还有什么需要注意？"),
        _compact("可以继续问什么？"),
    }
    return compact in generic_questions


def classify_workspace_followup_scenario(
    *,
    prompt: str,
    answer_content: str = "",
    workspace_workflow: str = "",
    primary_sources: list[str] | None = None,
    missing_context: list[str] | None = None,
) -> WorkspaceFollowupScenario:
    prompt_text = _compact(prompt)
    answer_text = _compact(str(answer_content or "")[:900])
    combined = f"{prompt_text}{answer_text}"

    if workspace_workflow == "file_search":
        return "file_search"

    action_time_tokens = ("下周", "明天", "后天", "会前", "会后", "这次", "马上", "准备")
    action_tokens = ("见", "拜访", "路演", "汇报", "沟通", "开会", "写一份", "准备", "介绍材料")
    audience_tokens = ("资方", "投资人", "合作伙伴", "伙伴", "政府", "基金会", "董事会", "理事会")
    if (
        _contains_any(prompt_text, action_time_tokens)
        and _contains_any(prompt_text, action_tokens)
        and _contains_any(prompt_text, audience_tokens)
    ):
        return "action_preparation"

    work_tokens = ("上次会议", "会议共识", "行动项", "待办", "任务", "近期推进", "最近推进", "卡点")
    if workspace_workflow == "work_status" or _contains_any(prompt_text, work_tokens):
        return "work_status"

    external_tokens = ("资方", "投资人", "合作伙伴", "对外", "公众", "政府", "路演", "汇报", "宣传", "传播")
    if _contains_any(prompt_text, external_tokens):
        return "external_communication"

    research_tokens = ("行业", "独特性", "同业", "竞品", "深度研究", "更深度", "补什么资料", "补哪类资料", "补充什么资料")
    if _contains_any(prompt_text, research_tokens):
        return "research_upgrade"

    organization_tokens = ("组织", "架构", "团队", "分工", "职责", "岗位", "协作", "组织调整", "能力建设")
    if _contains_any(combined, organization_tokens):
        return "organization_design"

    risk_tokens = ("风险", "卡点", "阻力", "困境", "难点", "冲突", "失效", "失败")
    if _contains_any(combined, risk_tokens):
        return "risk_review"

    business_tokens = ("项目", "服务", "产品", "模式", "模块", "交付", "试点", "课程", "方案")
    if _contains_any(prompt_text, business_tokens):
        return "business_project_design"

    strategy_tokens = ("战略", "方向", "定位", "核心资产", "价值", "判断", "优势", "重点", "变化", "未来", "可能性")
    if _contains_any(combined, strategy_tokens):
        return "strategy_judgment"

    if missing_context:
        return "research_upgrade"
    if primary_sources and any(str(item) in {"meetings", "tasks", "event_lines"} for item in primary_sources):
        return "work_status"
    return "general_consulting"


def fallback_workspace_followup_questions(
    scenario: WorkspaceFollowupScenario,
    *,
    client_name: str = "",
) -> list[str]:
    client_label = str(client_name or "这个客户").strip() or "这个客户"
    by_scenario: dict[str, list[str]] = {
        "strategy_judgment": [
            f"{client_label}这个方向落地时，最可能卡在哪个组织能力或资源条件上？",
            "这个判断是在放大既有优势，还是进入一个新的能力区？",
            "如果这个判断未来失效，最可能是哪个关键前提没有成立？",
        ],
        "organization_design": [
            "按当前业务架构，组织分工最需要调整的地方是什么？",
            "哪些工作还依赖关键个人，而没有沉淀成组织能力？",
            "当前团队最应该先补战略判断、项目交付，还是数据化运营能力？",
        ],
        "business_project_design": [
            "这个项目最难规模化的是服务模式、交付角色，还是成效证明？",
            "它应该成为核心产品、入口项目，还是支撑型服务？",
            "如果要让项目更可复制，最需要先标准化哪一环？",
        ],
        "external_communication": [
            "面向资方或合作伙伴时，最该强调组织使命、项目成效，还是方法论资产？",
            "哪种表达会显得过于泛公益，反而削弱这个组织的独特性？",
            "对方听完后，最应该留下哪一个清晰判断？",
        ],
        "action_preparation": [
            "这次见面前，最需要判断对方真正关心资金、影响力，还是合作抓手？",
            "会上最应该争取对方给出什么明确反馈？",
            "会后要把这次沟通转成任务、资料补充，还是下一轮合作方案？",
        ],
        "research_upgrade": [
            "如果要判断这个项目在行业里的独特性，最需要补哪类同业参照？",
            "如果要让分析更客观，最需要补服务对象、成效数据，还是合作网络资料？",
            "哪些资料一旦补齐，可以把当前判断从经验判断提升为研究判断？",
        ],
        "risk_review": [
            "当前最容易被低估的推进阻力是什么？",
            "哪个风险如果不提前处理，会影响后续战略落地？",
            "现在看起来顺利的部分，背后可能隐藏什么结构性问题？",
        ],
        "file_search": [
            "是否要基于这几份原文生成一版综合回答？",
            "还需要继续缩小到某个项目、会议或时间段查找吗？",
            "这些资料里，哪一份最接近你要核对的判断依据？",
        ],
        "work_status": [
            "最近推进里，哪些事项最需要先变成明确责任和时间节点？",
            "上次会议留下的共识里，哪一条最容易在执行中被误解？",
            "如果只推进一件事，哪件事最能降低当前卡点？",
        ],
        "general_consulting": [
            "如果继续深挖这个判断，最需要先验证哪个关键假设？",
            "哪些资料一旦补齐，能让这个判断更具体、更客观？",
            "这件事下一步最值得讨论的分歧点是什么？",
        ],
    }
    return by_scenario.get(scenario, by_scenario["general_consulting"])


def build_workspace_followup_instruction(scenario: WorkspaceFollowupScenario) -> str:
    scenario_directions = {
        "strategy_judgment": "追问战略假设、落地条件、组织能力约束和判断失效风险。",
        "organization_design": "追问组织分工、协作机制、关键个人依赖和能力沉淀。",
        "business_project_design": "追问服务模式、项目定位、交付角色、规模化和成效证明。",
        "external_communication": "追问对外表达对象、价值主张、独特性和误读风险。",
        "action_preparation": "追问会前判断、沟通目标、对方关注点和会后转化动作。",
        "research_upgrade": "追问需要补哪类资料、同业参照、成效数据和研究边界。",
        "risk_review": "追问被低估的阻力、前置条件、潜在冲突和结构性风险。",
        "file_search": "追问是否继续核对原文、缩小查找范围或基于原文生成回答。",
        "work_status": "追问会议共识、责任节点、行动优先级、卡点和未决问题。",
        "general_consulting": "追问关键假设、资料缺口、讨论分歧和下一步判断。",
    }
    return (
        "你不是在继续检索资料，而是在帮助用户把问题问深、问清楚。\n"
        "严格输出 3 个中文问题，每行 1 个问题，不要编号，不要解释，不要加标题，不要输出答案。\n"
        "追问必须贴合刚才的问题和回答，帮助创始人、负责人或项目决策者发现盲区、深化判断、推动讨论或行动。\n"
        "不要问过窄事实，例如官方稿什么时候完成、具体有哪些文件、哪份原文第几页，除非当前场景是 file_search。\n"
        "如果资料不足，追问应指向补哪类资料能支撑更深判断，而不是问一个必然答不出的具体事实。\n"
        f"当前追问场景：{scenario}。\n"
        f"本场景追问方向：{scenario_directions.get(scenario, scenario_directions['general_consulting'])}\n"
    )


def build_workspace_followup_context(
    *,
    prompt: str,
    answer_content: str,
    workspace_workflow: str,
    scenario: WorkspaceFollowupScenario,
    client_name: str,
    primary_sources: list[str],
    missing_context: list[str],
) -> str:
    return "\n".join(
        part
        for part in (
            f"客户：{client_name}" if client_name else "",
            f"当前问题：{prompt}",
            f"当前回答：\n{str(answer_content or '').strip()[:2200]}",
            f"工作流：{workspace_workflow}",
            f"追问场景：{scenario}",
            f"主要来源：{'、'.join(primary_sources[:6])}" if primary_sources else "",
            f"资料缺口：{'；'.join(missing_context[:4])}" if missing_context else "",
        )
        if part
    )


def normalize_workspace_followup_questions(
    raw_items: list[str],
    *,
    scenario: WorkspaceFollowupScenario,
    workspace_workflow: str = "",
) -> WorkspaceFollowupNormalizeResult:
    normalized: list[str] = []
    seen: set[str] = set()
    rejected_count = 0
    for raw in raw_items:
        text = _clean_question(str(raw or ""))
        if not text:
            continue
        compact = _compact(text)
        if len(compact) < 6 or compact in seen:
            continue
        if _is_overly_narrow_fact_question(text, scenario) or _is_low_value_generic_question(text):
            rejected_count += 1
            continue
        seen.add(compact)
        normalized.append(text)
        if len(normalized) >= 3:
            break
    return WorkspaceFollowupNormalizeResult(questions=normalized, rejected_count=rejected_count)


def build_workspace_followup_result_from_candidates(
    raw_items: list[str],
    *,
    scenario: WorkspaceFollowupScenario,
    generation_mode: WorkspaceFollowupGenerationMode,
    client_name: str = "",
    workspace_workflow: str = "",
) -> WorkspaceFollowupResult:
    normalized = normalize_workspace_followup_questions(
        raw_items,
        scenario=scenario,
        workspace_workflow=workspace_workflow,
    )
    questions = list(normalized.questions)
    seen = {_compact(item) for item in questions}
    for fallback in fallback_workspace_followup_questions(scenario, client_name=client_name):
        cleaned = _clean_question(fallback)
        compact = _compact(cleaned)
        if compact and compact not in seen and not _is_overly_narrow_fact_question(cleaned, scenario):
            questions.append(cleaned)
            seen.add(compact)
        if len(questions) >= 3:
            break
    return WorkspaceFollowupResult(
        questions=questions[:3],
        scenario=scenario,
        generation_mode=generation_mode,
        rejected_count=normalized.rejected_count,
    )
