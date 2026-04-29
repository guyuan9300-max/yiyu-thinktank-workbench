from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

WorkspaceWorkflow = Literal["synthesis", "file_search", "work_status", "diagnostic"]
WorkspaceGenerationMode = Literal[
    "no_generation",
    "short_synthesis",
    "long_synthesis",
    "consultant_synthesis",
    "action_advisory",
    "prep_pack",
]

_EXPLICIT_FILE_SEARCH_PHRASES = (
    "找原文",
    "找出处",
    "找哪份资料",
    "找哪份文件",
    "哪份原文",
    "哪份资料",
    "哪份文件",
    "打开原文",
    "打开上次会议纪要",
    "会议纪要在哪",
    "原文在哪",
    "出处在哪",
)

_FILE_SEARCH_ACTION_TOKENS = (
    "找",
    "帮我找",
    "给我找",
    "找一下",
    "找出",
    "查一下",
    "查找",
    "打开",
    "定位",
    "查看",
)

_FILE_SEARCH_OBJECT_TOKENS = (
    "原文",
    "出处",
    "资料",
    "文件",
    "文档",
    "会议纪要",
    "纪要",
    "合同",
    "协议",
    "报价",
    "申请书",
    "标书",
    "0907",
)

_ANSWER_STYLE_GUARD_TOKENS = (
    "是什么",
    "包含哪些",
    "具体包含哪些",
    "怎么做",
    "有哪些内容",
    "核心是什么",
    "下一步是什么",
)

_OFFICIAL_TOKENS = ("系统里", "系统内", "已批准", "正式判断", "官方判断", "已登记")

# P2.13 FREEZE(restrictive-workspace-workflow): 这组词当前会把客户工作台问题先路由到 `work_status`。
# 当用户提示里同时出现“风险 / 最近 / 本周重点 / 下一步”等词时，哪怕主问题是在“介绍客户/机构”，
# 也可能被压到 `work_status + short_synthesis`。先冻结，避免继续漂移。
_WORK_STATUS_TOKENS = (
    "下一步",
    "接下来",
    "上次会议",
    "会议纪要",
    "共识",
    "行动项",
    "任务",
    "待办",
    "推进",
    "卡点",
    "风险",
    "最近",
    "本周",
    "重要的几件事",
)

_SYNTHESIS_TOKENS = (
    "介绍",
    "简介",
    "项目",
    "业务",
    "战略",
    "方向",
    "可能性",
    "判断",
    "核心资产",
    "价值",
    "定位",
    "怎么理解",
    "怎么看",
    "应该怎么讲",
)

_CONSULTANT_SYNTHESIS_TOKENS = (
    "介绍",
    "简介",
    "战略",
    "核心资产",
    "组织定位",
    "当前变化",
    "最新变化",
    "未来方向",
    "业务结构",
    "为什么重要",
    "怎么理解",
    "怎么讲",
    "应该怎么讲",
)

_ACTION_ADVISORY_TOKENS = (
    "下一步",
    "接下来",
    "最重要的事情",
    "最重要的事",
    "最核心的事情",
    "最核心的事",
    "应该先做什么",
    "先做什么",
    "怎么推进",
    "如何推进",
    "优先推进",
    "推进什么",
    "行动建议",
    "下一阶段",
)

# P2.13 FREEZE(restrictive-workspace-raw-evidence): 这组词当前会打开 `includeRawEvidence`，
# 并和 `work_status` 组合成偏谨慎的短回答路径。先冻结，后续统一做问题翻译层时再整体处理。
_RAW_EVIDENCE_TOKENS = ("根据原文", "根据资料", "出处", "原文", "引用", "哪份资料", "哪份文件")

_INTRO_PRIORITY_TOKENS = (
    "介绍",
    "简介",
    "概况",
    "概览",
    "机构",
    "组织",
    "它是什么样的机构",
    "它真正想解决的核心问题",
    "它是怎么做这件事的",
    "它有哪些主要业务线",
    "它正在往什么方向升级",
    "用一句话总结它最核心的优势",
)


class WorkspaceQueryRouteRecord(BaseModel):
    workflow: WorkspaceWorkflow = "synthesis"
    generationMode: WorkspaceGenerationMode = "long_synthesis"
    page: str = "workspace_chat"
    scopeType: str = "client"
    scopeId: str
    clientId: str
    intent: str = "general"
    dataSources: list[str] = Field(default_factory=list)
    includeRawEvidence: bool = True
    includeActionSuggestions: bool = True
    shouldReturnSearchResults: bool = False
    shouldGenerateAnswer: bool = True
    routeReason: str = ""
    confidence: float = 0.0


def _normalize_prompt(prompt: str) -> str:
    return "".join(str(prompt or "").lower().split())


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _is_explicit_file_search_prompt(normalized: str) -> bool:
    if _contains_any(normalized, _EXPLICIT_FILE_SEARCH_PHRASES):
        return True
    if "哪份" in normalized and _contains_any(normalized, ("原文", "资料", "文件", "文档", "纪要")):
        return True
    if _contains_any(normalized, _FILE_SEARCH_ACTION_TOKENS) and _contains_any(normalized, _FILE_SEARCH_OBJECT_TOKENS):
        return True
    return False


def _looks_answer_style_prompt(normalized: str) -> bool:
    return _contains_any(normalized, _ANSWER_STYLE_GUARD_TOKENS)


def _looks_intro_profile_prompt(normalized: str) -> bool:
    if not _contains_any(normalized, _INTRO_PRIORITY_TOKENS):
        return False
    if any(token in normalized for token in ("这条任务", "当前任务", "任务下一步", "任务背景")):
        return False
    return True


def _looks_consultant_synthesis_prompt(normalized: str) -> bool:
    if _contains_any(normalized, _CONSULTANT_SYNTHESIS_TOKENS):
        return True
    if "核心" in normalized and _contains_any(normalized, ("资产", "能力", "优势", "价值")):
        return True
    if "最值得关注" in normalized and _contains_any(normalized, ("变化", "趋势", "方向")):
        return True
    return False


def _looks_action_advisory_prompt(normalized: str) -> bool:
    if not _contains_any(normalized, _ACTION_ADVISORY_TOKENS):
        return False
    if _is_explicit_file_search_prompt(normalized):
        return False
    return True


def route_workspace_query(
    *,
    prompt: str,
    client_id: str,
    current_page: str = "workspace_chat",
    selected_scope_type: str = "client",
    selected_scope_id: str | None = None,
) -> WorkspaceQueryRouteRecord:
    normalized = _normalize_prompt(prompt)
    scope_id = str(selected_scope_id or client_id).strip() or client_id

    if _is_explicit_file_search_prompt(normalized):
        return WorkspaceQueryRouteRecord(
            workflow="file_search",
            generationMode="no_generation",
            page=current_page,
            scopeType=selected_scope_type,
            scopeId=scope_id,
            clientId=client_id,
            intent="file_search",
            dataSources=["raw_docs", "document_cards", "master_index", "vector_index"],
            includeRawEvidence=True,
            includeActionSuggestions=False,
            shouldReturnSearchResults=True,
            shouldGenerateAnswer=False,
            routeReason="workspace_rule_file_search_explicit",
            confidence=0.96,
        )

    if _contains_any(normalized, _OFFICIAL_TOKENS):
        return WorkspaceQueryRouteRecord(
            workflow="synthesis",
            generationMode="long_synthesis",
            page=current_page,
            scopeType=selected_scope_type,
            scopeId=scope_id,
            clientId=client_id,
            intent="official_judgment_registry",
            dataSources=["state_pool", "judgments"],
            includeRawEvidence=False,
            includeActionSuggestions=False,
            shouldReturnSearchResults=False,
            shouldGenerateAnswer=True,
            routeReason="workspace_rule_official_registry",
            confidence=0.96,
        )

    if _looks_action_advisory_prompt(normalized):
        return WorkspaceQueryRouteRecord(
            workflow="synthesis",
            generationMode="action_advisory",
            page=current_page,
            scopeType=selected_scope_type,
            scopeId=scope_id,
            clientId=client_id,
            intent="action_advisory",
            dataSources=[
                "meetings",
                "tasks",
                "event_lines",
                "state_pool",
                "open_questions",
                "conflicts",
                "client_dna",
                "judgments",
                "project_structure",
                "raw_docs",
                "document_cards",
            ],
            includeRawEvidence=True,
            includeActionSuggestions=True,
            shouldReturnSearchResults=False,
            shouldGenerateAnswer=True,
            routeReason="workspace_rule_action_advisory",
            confidence=0.9,
        )

    if _looks_consultant_synthesis_prompt(normalized):
        return WorkspaceQueryRouteRecord(
            workflow="synthesis",
            generationMode="consultant_synthesis",
            page=current_page,
            scopeType=selected_scope_type,
            scopeId=scope_id,
            clientId=client_id,
            intent="consultant_synthesis",
            dataSources=[
                "raw_docs",
                "document_cards",
                "client_dna",
                "judgments",
                "meetings",
                "tasks",
                "event_lines",
                "state_pool",
            ],
            includeRawEvidence=True,
            includeActionSuggestions=True,
            shouldReturnSearchResults=False,
            shouldGenerateAnswer=True,
            routeReason="workspace_rule_consultant_synthesis",
            confidence=0.82,
        )

    if _looks_answer_style_prompt(normalized):
        return WorkspaceQueryRouteRecord(
            workflow="synthesis",
            generationMode="long_synthesis",
            page=current_page,
            scopeType=selected_scope_type,
            scopeId=scope_id,
            clientId=client_id,
            intent="general",
            dataSources=["raw_docs", "document_cards"],
            includeRawEvidence=True,
            includeActionSuggestions=False,
            shouldReturnSearchResults=False,
            shouldGenerateAnswer=True,
            routeReason="workspace_rule_open_synthesis",
            confidence=0.7,
        )

    return WorkspaceQueryRouteRecord(
        workflow="synthesis",
        generationMode="long_synthesis",
        page=current_page,
        scopeType=selected_scope_type,
        scopeId=scope_id,
        clientId=client_id,
        intent="general",
        dataSources=["raw_docs", "document_cards"],
        includeRawEvidence=True,
        includeActionSuggestions=False,
        shouldReturnSearchResults=False,
        shouldGenerateAnswer=True,
        routeReason="workspace_rule_open_synthesis",
        confidence=0.62,
    )
