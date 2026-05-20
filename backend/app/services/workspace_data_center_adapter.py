from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from app.models import (
    ChatRetrievalDecisionReason,
    ClientWorkspaceResponse,
    DataCenterKernelResultRecord,
    DataCenterRequestRecord,
    DataCenterScopeRecord,
    PageContextPackRecord,
    WorkspaceAnswerIntent,
)
from app.services.evidence_quality import classify_evidence_quality_fields
from app.services.answer_layer import (
    should_include_answer_action_cards,
    should_include_answer_boundary,
    should_include_answer_next_actions,
    should_include_operational_context_points,
)
from app.services.workspace_query_router import WorkspaceQueryRouteRecord

WORKSPACE_SCOPE_MAPPING: dict[str, dict[str, str]] = {
    "client_workspace": {"page": "client_workspace", "scopeType": "client"},
    "workspace_chat": {"page": "workspace_chat", "scopeType": "client"},
    "meeting_detail": {"page": "meeting_detail", "scopeType": "meeting"},
    "task_detail": {"page": "task_detail", "scopeType": "task"},
    "event_line_detail": {"page": "event_line_detail", "scopeType": "event_line"},
    "project_module_detail": {"page": "project_module_detail", "scopeType": "project_module"},
    "project_flow_detail": {"page": "project_flow_detail", "scopeType": "project_flow"},
    "strategic_cockpit": {"page": "strategic_cockpit", "scopeType": "strategic_cockpit"},
}


def build_workspace_data_center_request(
    *,
    client_id: str,
    prompt: str,
    include_action_suggestions: bool = True,
    include_raw_evidence: bool = True,
    shadow: bool = True,
    persist_drafts: bool = False,
) -> DataCenterRequestRecord:
    return DataCenterRequestRecord(
        scope=DataCenterScopeRecord(
            page="workspace_chat",
            scopeType="client",
            scopeId=client_id,
            clientId=client_id,
        ),
        prompt=prompt,
        mode="answer",
        includeRawEvidence=include_raw_evidence,
        includeActionSuggestions=include_action_suggestions,
        shadow=shadow,
        persistDrafts=persist_drafts,
    )


def build_workspace_data_center_request_from_route(
    *,
    route: WorkspaceQueryRouteRecord,
    prompt: str,
    shadow: bool = True,
    persist_drafts: bool = False,
    working_document_ids: list[str] | None = None,
) -> DataCenterRequestRecord:
    if route.workflow == "file_search":
        mode = "search"
    elif route.workflow == "work_status" and route.generationMode == "prep_pack":
        mode = "prep"
    else:
        mode = "answer"
    effective_shadow = False if route.generationMode == "consultant_synthesis" else shadow
    return DataCenterRequestRecord(
        scope=build_workspace_scope(
            page=route.page,
            client_id=route.clientId,
            scope_id=route.scopeId,
        ),
        prompt=prompt,
        mode=mode,  # type: ignore[arg-type]
        includeRawEvidence=route.includeRawEvidence,
        includeActionSuggestions=route.includeActionSuggestions,
        shadow=effective_shadow,
        persistDrafts=persist_drafts,
        workingDocumentIds=[str(item).strip() for item in (working_document_ids or []) if str(item).strip()],
    )


def build_workspace_scope(
    *,
    page: str,
    client_id: str | None = None,
    scope_id: str | None = None,
    task_id: str | None = None,
    meeting_id: str | None = None,
    event_line_id: str | None = None,
    project_module_id: str | None = None,
    project_flow_id: str | None = None,
) -> DataCenterScopeRecord:
    mapping = WORKSPACE_SCOPE_MAPPING.get(page)
    if mapping is None:
        raise ValueError(f"unsupported workspace page for scope mapping: {page}")
    mapped_page = mapping["page"]
    scope_type = mapping["scopeType"]
    resolved_client_id = str(client_id or "").strip() or None
    resolved_scope_id = str(scope_id or "").strip()

    if scope_type == "client":
        resolved_scope_id = resolved_scope_id or str(resolved_client_id or "").strip()
    elif scope_type == "task":
        resolved_scope_id = resolved_scope_id or str(task_id or "").strip()
    elif scope_type == "meeting":
        resolved_scope_id = resolved_scope_id or str(meeting_id or "").strip()
    elif scope_type == "event_line":
        resolved_scope_id = resolved_scope_id or str(event_line_id or "").strip()
    elif scope_type == "project_module":
        resolved_scope_id = resolved_scope_id or str(project_module_id or "").strip()
    elif scope_type == "project_flow":
        resolved_scope_id = resolved_scope_id or str(project_flow_id or "").strip()
    elif scope_type == "strategic_cockpit":
        resolved_scope_id = resolved_scope_id or str(resolved_client_id or "").strip()

    if not resolved_scope_id:
        raise ValueError(f"missing scope id for page={page} scopeType={scope_type}")

    payload: dict[str, object] = {
        "page": mapped_page,
        "scopeType": scope_type,
        "scopeId": resolved_scope_id,
        "clientId": resolved_client_id,
    }
    if task_id:
        payload["taskId"] = task_id
    if meeting_id:
        payload["meetingId"] = meeting_id
    if event_line_id:
        payload["eventLineId"] = event_line_id
    if project_module_id:
        payload["projectModuleId"] = project_module_id
    if project_flow_id:
        payload["projectFlowId"] = project_flow_id
    return DataCenterScopeRecord.model_validate(payload)


def build_workspace_page_context_request(
    *,
    client_id: str,
    page: str = "client_workspace",
    prompt: str = "",
    include_raw_evidence: bool = True,
    include_action_suggestions: bool = False,
    mode: str = "page_context",
) -> DataCenterRequestRecord:
    return DataCenterRequestRecord(
        scope=build_workspace_scope(page=page, client_id=client_id, scope_id=client_id),
        prompt=prompt,
        mode=mode,  # type: ignore[arg-type]
        includeRawEvidence=include_raw_evidence,
        includeActionSuggestions=include_action_suggestions,
        shadow=True,
        persistDrafts=False,
    )


def build_workspace_task_data_center_request(
    *,
    client_id: str,
    task_id: str,
    prompt: str = "",
    mode: str = "page_context",
) -> DataCenterRequestRecord:
    return DataCenterRequestRecord(
        scope=build_workspace_scope(
            page="task_detail",
            client_id=client_id,
            scope_id=task_id,
            task_id=task_id,
        ),
        prompt=prompt,
        mode=mode,  # type: ignore[arg-type]
        includeRawEvidence=True,
        includeActionSuggestions=True,
        shadow=True,
    )


def build_workspace_meeting_data_center_request(
    *,
    client_id: str,
    meeting_id: str,
    prompt: str = "",
    mode: str = "page_context",
) -> DataCenterRequestRecord:
    return DataCenterRequestRecord(
        scope=build_workspace_scope(
            page="meeting_detail",
            client_id=client_id,
            scope_id=meeting_id,
            meeting_id=meeting_id,
        ),
        prompt=prompt,
        mode=mode,  # type: ignore[arg-type]
        includeRawEvidence=True,
        includeActionSuggestions=True,
        shadow=True,
    )


def build_workspace_event_line_data_center_request(
    *,
    client_id: str,
    event_line_id: str,
    prompt: str = "",
    mode: str = "page_context",
) -> DataCenterRequestRecord:
    return DataCenterRequestRecord(
        scope=build_workspace_scope(
            page="event_line_detail",
            client_id=client_id,
            scope_id=event_line_id,
            event_line_id=event_line_id,
        ),
        prompt=prompt,
        mode=mode,  # type: ignore[arg-type]
        includeRawEvidence=True,
        includeActionSuggestions=True,
        shadow=True,
    )


def build_workspace_project_module_data_center_request(
    *,
    client_id: str,
    module_id: str,
    prompt: str = "",
    mode: str = "page_context",
) -> DataCenterRequestRecord:
    return DataCenterRequestRecord(
        scope=build_workspace_scope(
            page="project_module_detail",
            client_id=client_id,
            scope_id=module_id,
            project_module_id=module_id,
        ),
        prompt=prompt,
        mode=mode,  # type: ignore[arg-type]
        includeRawEvidence=True,
        includeActionSuggestions=True,
        shadow=True,
    )


def build_workspace_project_flow_data_center_request(
    *,
    client_id: str,
    flow_id: str,
    prompt: str = "",
    mode: str = "page_context",
) -> DataCenterRequestRecord:
    return DataCenterRequestRecord(
        scope=build_workspace_scope(
            page="project_flow_detail",
            client_id=client_id,
            scope_id=flow_id,
            project_flow_id=flow_id,
        ),
        prompt=prompt,
        mode=mode,  # type: ignore[arg-type]
        includeRawEvidence=True,
        includeActionSuggestions=True,
        shadow=True,
    )


def _clean_text(value: object, *, limit: int = 200) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text if len(text) <= limit else f"{text[:limit]}…"


def _field_value(item: object, field: str) -> object:
    if isinstance(item, dict):
        return item.get(field)
    value = getattr(item, field, None)
    if value is not None:
        return value
    model_dump = getattr(item, "model_dump", None)
    if callable(model_dump):
        try:
            payload = model_dump(mode="json")
        except TypeError:
            payload = model_dump()
        if isinstance(payload, dict):
            return payload.get(field)
    return None


def _list_value(value: object) -> list[object]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    return []


def _json_object(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items()}
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            payload = model_dump(mode="json")
        except TypeError:
            payload = model_dump()
        if isinstance(payload, dict):
            return {str(key): item for key, item in payload.items()}
    return {}


def _collect_item_lines(items: list[object], *, fields: tuple[str, ...], limit: int) -> list[str]:
    lines: list[str] = []
    for item in items[:limit]:
        if isinstance(item, str):
            text_line = _clean_text(item)
            if text_line:
                lines.append(text_line)
            continue
        line = ""
        for field in fields:
            value = _clean_text(_field_value(item, field))
            if value:
                line = value
                break
        if line:
            lines.append(line)
    return lines


@dataclass(frozen=True)
class ConsultantSynthesisMaterialPack:
    content: str
    profile: str = "consultant_synthesis_v1"
    source_counts: dict[str, int] = field(default_factory=dict)
    excluded_noise_count: int = 0
    boundary_notes: list[str] = field(default_factory=list)
    context_chars: int = 0


@dataclass(frozen=True)
class ActionAdvisoryMaterialPack:
    content: str
    profile: str = "action_advisory_v1"
    source_counts: dict[str, int] = field(default_factory=dict)
    boundary_notes: list[str] = field(default_factory=list)
    context_chars: int = 0


@dataclass(frozen=True)
class DnaToolContextRecord:
    purpose: str
    selected_modules: list[str] = field(default_factory=list)
    selected_kinds: list[str] = field(default_factory=list)
    context_text: str = ""
    source_level_summary: str = ""
    time_scope_summary: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def context_chars(self) -> int:
        return len(self.context_text)


_CONSULTANT_NOISE_TOKENS = (
    "prog_test",
    "test_attachment",
    "smoke",
    "冒烟",
    "安装态冒烟",
    "报销",
    "飞书按钮联调",
    "飞书会议按钮",
    "按钮联调",
    "重复件已移至废纸篓",
    "整理说明",
    "说明.txt",
    "运行态",
    "source-integrity",
    "buildversion",
    "install-smoke",
    "install-receipt",
    "软件启动",
    "启动门禁",
)

_CONSULTANT_ATTACHMENT_NOISE_TOKENS = (
    "已作为任务附件",
    "附件已进入项目资料库",
    "任务附件已进入项目资料库",
    "上传附件",
)

_CONSULTANT_HIGH_SIGNAL_TOKENS = (
    "战略",
    "规划",
    "定位",
    "使命",
    "愿景",
    "价值",
    "核心",
    "业务",
    "项目",
    "服务",
    "产品",
    "方案",
    "会议",
    "纪要",
    "访谈",
    "沟通",
    "复盘",
    "调研",
    "资方",
    "合作",
    "品牌",
    "心灵魔法",
    "心盛",
    "教师赋能",
    "繁星",
    "陪伴",
)


def _first_text_field(item: object, fields: tuple[str, ...], *, limit: int = 800) -> str:
    if isinstance(item, str):
        return _clean_text(item, limit=limit)
    for field_name in fields:
        value = _clean_text(_field_value(item, field_name), limit=limit)
        if value:
            return value
    return ""


def _full_text_field(item: object, fields: tuple[str, ...]) -> str:
    if isinstance(item, str):
        return item.strip()
    for field_name in fields:
        value = str(_field_value(item, field_name) or "").strip()
        if value:
            return value
    return ""


def infer_dna_tool_purpose(prompt: str, fallback: str = "intro") -> str:
    normalized = re.sub(r"\s+", "", str(prompt or "").lower())
    if any(token in normalized for token in ("缺什么", "缺哪些", "补哪些", "补充哪些", "资料缺口", "补全", "数字资产", "还缺")):
        return "asset_gap"
    if any(token in normalized for token in ("下一步", "未来两周", "任务", "日程", "推进", "怎么做", "行动", "会议", "跟进")):
        return "task_next_action"
    if any(token in normalized for token in ("战略", "核心", "定位", "第二曲线", "增长飞轮", "方向", "路径", "判断")):
        return "strategy"
    if any(token in normalized for token in ("对外", "公开", "合作方", "宣传", "材料", "介绍稿", "官网")):
        return "public_material"
    if any(token in normalized for token in ("风险", "合规", "边界", "不能说", "未成年人", "隐私", "公开口径")):
        return "risk_check"
    if any(token in normalized for token in ("介绍", "简介", "是谁", "画像", "项目特点")):
        return "intro"
    return fallback


def _dna_module_kinds(module: object) -> list[str]:
    module_key = _clean_text(_field_value(module, "moduleKey"), limit=80)
    title = _clean_text(_field_value(module, "title"), limit=120)
    text = " ".join(
        part
        for part in [
            _full_text_field(module, ("summary",)),
            _full_text_field(module, ("normalizedText",)),
            _full_text_field(module, ("markdownContent",)),
            _full_text_field(module, ("text", "content")),
        ]
        if part
    )
    normalized = f"{module_key} {title} {text[:6000]}".lower()
    kinds: list[str] = []
    if module_key in {"organization_intro", "business_intro", "team_intro", "market_intro"}:
        kinds.append("stable_dna")
    if any(token in normalized for token in ("官网", "公开", "对外", "民政", "慈善中国", "年报", "审计", "报告", "披露")):
        kinds.append("public_dna")
    if any(token in normalized for token in ("战略", "第二曲线", "任务", "事件线", "会议", "当前", "下一步", "待证据确认", "自动升级", "自动降级", "飞轮")):
        kinds.append("evolving_dna")
    if any(token in normalized for token in ("缺口", "补全", "待补", "资料", "互联网", "用户补", "自动补", "优先级")):
        kinds.append("gap_dna")
    if any(token in normalized for token in ("风险", "合规", "边界", "不能", "不得", "公开口径", "内部口径", "未成年人", "隐私", "治疗", "正式事实", "高置信")):
        kinds.append("risk_dna")
    return list(dict.fromkeys(kinds or ["stable_dna"]))


def _preferred_dna_kinds_for_purpose(purpose: str) -> list[str]:
    return {
        "intro": ["stable_dna", "public_dna"],
        "strategy": ["stable_dna", "evolving_dna", "risk_dna"],
        "task_next_action": ["evolving_dna", "gap_dna", "risk_dna", "stable_dna"],
        "asset_gap": ["gap_dna", "evolving_dna", "risk_dna", "stable_dna"],
        "public_material": ["public_dna", "stable_dna", "risk_dna"],
        "risk_check": ["risk_dna", "public_dna", "stable_dna"],
    }.get(purpose, ["stable_dna", "evolving_dna", "gap_dna", "risk_dna"])


def _mark_unverified_dna_numbers(text: str) -> str:
    pieces = re.split(r"([。；;\n])", text)
    rebuilt: list[str] = []
    for idx in range(0, len(pieces), 2):
        sentence = pieces[idx]
        delimiter = pieces[idx + 1] if idx + 1 < len(pieces) else ""
        has_strong_number = bool(
            re.search(r"\d+(?:\.\d+)?%|\d+(?:\.\d+)?倍|(?:提升|降低|增长|减少|节省|替代)[^。；;\n]{0,18}\d", sentence)
        )
        has_source_marker = bool(re.search(r"S\d{3}|来源|L1|L2|官网|年报|审计|截至20\d{2}", sentence))
        if has_strong_number and not has_source_marker and "数字/成效口径需来源核验" not in sentence:
            sentence = sentence.rstrip() + "（数字/成效口径需来源核验，不能直接写成正式事实）"
        rebuilt.append(sentence + delimiter)
    return "".join(rebuilt)


def _filter_dna_text_for_purpose(text: str, purpose: str) -> str:
    if purpose not in {"intro", "public_material"}:
        return text
    noisy_tokens = (
        "待证据确认",
        "自动升级",
        "自动降级",
        "事件线",
        "未来两周",
        "下一阶段任务",
        "任务1",
        "任务2",
        "资料缺口",
        "补全优先级",
        "系统自动补",
        "用户补充",
        "互联网补全",
    )
    paragraphs = re.split(r"\n{2,}|(?<=。)", text)
    kept: list[str] = []
    for paragraph in paragraphs:
        cleaned = paragraph.strip()
        if not cleaned:
            continue
        if any(token in cleaned for token in noisy_tokens):
            continue
        kept.append(cleaned)
    return "\n".join(kept) or text


def _short_label(value: object, *, limit: int = 200) -> str:
    """Collapse whitespace + truncate to a short single-line label."""
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip()
    if not cleaned:
        return ""
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(1, limit - 1)].rstrip() + "…"


def build_workspace_background_pack(
    workspace_snapshot: ClientWorkspaceResponse | None,
    *,
    max_chars: int = 9000,
    judgment_limit: int = 6,
    meeting_limit: int = 3,
    task_limit: int = 5,
    project_module_limit: int = 4,
    goal_limit: int = 4,
    open_question_limit: int = 3,
    conflict_limit: int = 3,
) -> str:
    """构造"客户画像 + 核心判断 + 当前推进 + 矛盾"的固定背景包。

    这个块在所有 workflow 的主回答 system context 里都注入，作为不变的画像底色 ——
    让模型永远知道"当前对话锁定的这家组织 / 项目目前状态是什么"，
    避免它只盯着零散资料、忘记全局。

    与 ``build_dna_tool_context_from_workspace`` 互补：DNA 是"工具调用"，
    可以承载更丰富的业务/组织/品牌细节；这里是"客户当前状态"，必须紧凑。

    返回 markdown 字符串；客户什么都没有时返回空字符串（不注入空块）。
    """
    if workspace_snapshot is None:
        return ""

    blocks: list[str] = ["【客户背景包 · 永远在场】"]

    # 1) 客户档案
    client = workspace_snapshot.client
    if client is not None:
        archive_lines = [f"客户：{client.name}".strip()]
        if client.alias and client.alias != client.name:
            archive_lines.append(f"别名：{client.alias}")
        if client.type:
            archive_lines.append(f"类型：{client.type}")
        if client.stage:
            archive_lines.append(f"阶段：{client.stage}")
        intro = _short_label(client.intro, limit=260)
        if intro:
            archive_lines.append(f"简介：{intro}")
        if client.lastActivityAt:
            archive_lines.append(f"最后活跃：{client.lastActivityAt}")
        blocks.append("\n".join(archive_lines))

    # 2) 已确认核心判断（优先选 confirmed / approved）
    judgments = list(workspace_snapshot.latestJudgments or [])
    confirmed_judgments = [
        j for j in judgments
        if str(getattr(j, "status", "") or "").lower() in {"confirmed", "approved"}
        or str(getattr(j, "authorityLevel", "") or "").lower() == "approved"
    ]
    judgment_pool = confirmed_judgments if confirmed_judgments else judgments
    if judgment_pool:
        lines = ["─── 已确认核心判断"]
        for judgment in judgment_pool[:judgment_limit]:
            topic = _short_label(getattr(judgment, "topic", ""), limit=80) or "判断"
            summary = _short_label(getattr(judgment, "summary", ""), limit=260)
            if not summary:
                continue
            meta_parts: list[str] = []
            confidence = str(getattr(judgment, "confidence", "") or "").strip()
            if confidence:
                meta_parts.append(f"信心={confidence}")
            risk = str(getattr(judgment, "riskLevel", "") or "").strip()
            if risk:
                meta_parts.append(f"风险={risk}")
            meta_str = f"（{'，'.join(meta_parts)}）" if meta_parts else ""
            lines.append(f"- [{topic}] {summary}{meta_str}")
        if len(lines) > 1:
            blocks.append("\n".join(lines))

    # 3) 当前推进重点：项目模块 / 会议 / 活跃任务 / 目标
    drive_sections: list[str] = []

    modules = list(workspace_snapshot.projectModules or [])
    if modules:
        module_lines = ["活跃项目模块："]
        for module in modules[:project_module_limit]:
            name = _short_label(getattr(module, "name", ""), limit=80) or "项目模块"
            goal = _short_label(getattr(module, "goal", ""), limit=220)
            description = _short_label(getattr(module, "description", ""), limit=320)
            owner = _short_label(getattr(module, "ownerName", ""), limit=40)
            deliverables_raw = getattr(module, "deliverables", []) or []
            deliverables_str = "、".join(
                _short_label(item, limit=60) for item in deliverables_raw[:5] if _short_label(item, limit=60)
            )
            keywords_raw = getattr(module, "keywords", []) or []
            keywords_str = "、".join(
                _short_label(item, limit=30) for item in keywords_raw[:6] if _short_label(item, limit=30)
            )
            module_lines.append(f"- {name}")
            if goal:
                module_lines.append(f"    目标：{goal}")
            if description:
                module_lines.append(f"    说明：{description}")
            if deliverables_str:
                module_lines.append(f"    交付物：{deliverables_str}")
            if keywords_str:
                module_lines.append(f"    关键词：{keywords_str}")
            if owner:
                module_lines.append(f"    负责人：{owner}")
        drive_sections.append("\n".join(module_lines))

    meetings = list(workspace_snapshot.meetings or [])
    if meetings:
        sorted_meetings = sorted(
            meetings,
            key=lambda m: str(getattr(m, "scheduledAt", "") or getattr(m, "updatedAt", "") or ""),
            reverse=True,
        )
        meet_lines = ["近期会议："]
        for meeting in sorted_meetings[:meeting_limit]:
            title = _short_label(getattr(meeting, "title", ""), limit=120) or "会议"
            stage = str(getattr(meeting, "stage", "") or "").strip()
            scheduled = str(getattr(meeting, "scheduledAt", "") or "").strip()
            updated = str(getattr(meeting, "updatedAt", "") or "").strip()
            date_label = scheduled or updated
            meet_lines.append(
                f"- {title}"
                + (f"（{stage}）" if stage else "")
                + (f" · {date_label}" if date_label else "")
            )
        drive_sections.append("\n".join(meet_lines))

    tasks = list(workspace_snapshot.relatedTasks or [])
    active_tasks = [
        t for t in tasks
        if str(getattr(t, "status", "") or "").lower() not in {"done", "archived", "completed", "cancelled"}
    ]
    if active_tasks:
        task_lines = ["活跃任务："]
        for task in active_tasks[:task_limit]:
            title = _short_label(getattr(task, "title", ""), limit=120) or "任务"
            status = str(getattr(task, "status", "") or "").strip()
            due = (
                str(getattr(task, "dueDate", "") or "").strip()
                or str(getattr(task, "deadlineAt", "") or "").strip()
                or str(getattr(task, "ddl", "") or "").strip()
            )
            owner = _short_label(getattr(task, "ownerName", ""), limit=40)
            desc = _short_label(getattr(task, "desc", ""), limit=240)
            event_line = _short_label(getattr(task, "eventLineName", ""), limit=60)
            project_module = _short_label(getattr(task, "projectModuleName", ""), limit=60)
            head = f"- {title}"
            if status:
                head += f" [{status}]"
            if due:
                head += f" / 截止 {due}"
            if owner:
                head += f" / {owner}"
            task_lines.append(head)
            if desc:
                task_lines.append(f"    描述：{desc}")
            link_parts = []
            if event_line:
                link_parts.append(f"事件线={event_line}")
            if project_module:
                link_parts.append(f"项目模块={project_module}")
            if link_parts:
                task_lines.append(f"    关联：{'；'.join(link_parts)}")
        drive_sections.append("\n".join(task_lines))

    goals = list(workspace_snapshot.goals or [])
    if goals:
        goal_lines = ["目标："]
        for goal in goals[:goal_limit]:
            title = _short_label(getattr(goal, "title", ""), limit=120) or "目标"
            quarter = str(getattr(goal, "quarter", "") or "").strip()
            progress_val = getattr(goal, "progress", 0)
            try:
                progress = int(progress_val)
            except (TypeError, ValueError):
                progress = 0
            tail = "，".join(p for p in (quarter, f"进度 {progress}%") if p)
            goal_lines.append(f"- {title}" + (f"（{tail}）" if tail else ""))
        drive_sections.append("\n".join(goal_lines))

    if drive_sections:
        blocks.append("─── 当前推进重点\n" + "\n\n".join(drive_sections))

    # 4) 矛盾 / 待澄清问题
    flag_sections: list[str] = []
    conflicts = list(workspace_snapshot.latestConflicts or [])
    if conflicts:
        conflict_lines = ["矛盾："]
        for conflict in conflicts[:conflict_limit]:
            title = _short_label(getattr(conflict, "title", ""), limit=80)
            summary = _short_label(getattr(conflict, "summary", ""), limit=200)
            severity = str(getattr(conflict, "severity", "") or "").strip()
            body = summary or title
            if not body:
                continue
            conflict_lines.append(
                f"- {title}：{summary}" if (title and summary and title != summary)
                else f"- {body}"
                + (f"（{severity}）" if severity else "")
            )
        if len(conflict_lines) > 1:
            flag_sections.append("\n".join(conflict_lines))

    open_questions = list(workspace_snapshot.latestOpenQuestions or [])
    if open_questions:
        question_lines = ["待澄清问题："]
        for question in open_questions[:open_question_limit]:
            text = _short_label(getattr(question, "question", ""), limit=200)
            blocker = str(getattr(question, "blockerLevel", "") or "").strip()
            reason = _short_label(getattr(question, "reason", ""), limit=120)
            if not text:
                continue
            question_lines.append(
                f"- {text}"
                + (f"（阻塞={blocker}）" if blocker else "")
                + (f" — {reason}" if reason else "")
            )
        if len(question_lines) > 1:
            flag_sections.append("\n".join(question_lines))

    if flag_sections:
        blocks.append("─── 当前矛盾与待澄清\n" + "\n\n".join(flag_sections))

    if len(blocks) <= 1:
        # 标题外什么都没装上 → 客户为空白，干脆不注入
        return ""

    content = "\n\n".join(block for block in blocks if block).strip()
    if len(content) > max_chars:
        content = content[: max(1, max_chars - 1)].rstrip() + "…"
    return content


def build_client_resource_index(
    workspace_snapshot: ClientWorkspaceResponse | None,
    *,
    prompt: str = "",
    max_chars: int = 8000,
    documents_budget: int = 4000,
    projects_budget: int = 1200,
    judgments_budget: int = 1500,
    meetings_budget: int = 600,
    goals_budget: int = 600,
    documents_max_files: int = 80,
    projects_max_count: int = 30,
    judgments_max_count: int = 30,
    meetings_max_count: int = 20,
    goals_max_count: int = 20,
) -> str:
    """R9：客户全域资源索引（5 个域元数据视图）。

    给「任务型 + 穷举型」请求用的元数据全集视图：让 LLM 看到客户全部资源
    （documents / projectModules / latestJudgments / meetings / goals），
    不需要依赖检索 top-K 命中。

    每个域内部只列最重要字段（1 行/条），空域自动跳过。
    总预算 ~8000 字，足以覆盖大型客户的全部元数据。
    """
    if workspace_snapshot is None:
        return ""

    sections: list[str] = []

    # 域 1: documents
    docs_block = _resource_documents_block(
        workspace_snapshot, budget=documents_budget, max_files=documents_max_files
    )
    if docs_block:
        sections.append(docs_block)

    # 域 2: projectModules
    projects_block = _resource_projects_block(
        workspace_snapshot, budget=projects_budget, max_count=projects_max_count
    )
    if projects_block:
        sections.append(projects_block)

    # 域 3: latestJudgments
    judgments_block = _resource_judgments_block(
        workspace_snapshot, budget=judgments_budget, max_count=judgments_max_count
    )
    if judgments_block:
        sections.append(judgments_block)

    # 域 4: meetings
    meetings_block = _resource_meetings_block(
        workspace_snapshot, budget=meetings_budget, max_count=meetings_max_count
    )
    if meetings_block:
        sections.append(meetings_block)

    # 域 5: goals
    goals_block = _resource_goals_block(
        workspace_snapshot, budget=goals_budget, max_count=goals_max_count
    )
    if goals_block:
        sections.append(goals_block)

    if not sections:
        return ""

    header = (
        "【客户资源索引 · 全集元数据视图】\n"
        "下面是该客户在系统里**全部资源的索引**（不只是检索命中的部分）。\n"
        "用于回答「列出所有 X」「做一张包含全部 Y 的表」「客户有几个 Z」等穷举/枚举类任务。\n"
        "**索引里的每一条都是真实存在的资源，可以直接引用**。\n"
        "—— 文档：可从文件名解析姓名/岗位/日期等结构化字段\n"
        "—— 项目/判断/会议/目标：标题级元数据，需要内容时仍依赖检索命中片段\n"
    )
    pack = header + "\n" + "\n\n".join(sections)
    if len(pack) > max_chars:
        pack = pack[: max(1, max_chars - 1)].rstrip() + "…"
    return pack


def _resource_documents_block(
    workspace_snapshot: ClientWorkspaceResponse,
    *,
    budget: int,
    max_files: int,
) -> str:
    documents = list(getattr(workspace_snapshot, "documents", []) or [])
    if not documents:
        return ""
    ordered = sorted(
        documents,
        key=lambda d: str(getattr(d, "importedAt", "") or ""),
        reverse=True,
    )
    total = len(ordered)
    lines: list[str] = [f"── 文档（documents · 共 {total} 份，最多列 {max_files} 条）──"]
    used = sum(len(line) for line in lines)
    listed = 0
    for doc in ordered:
        if listed >= max_files:
            break
        title = _clean_text(getattr(doc, "title", ""), limit=180) or "未命名"
        kind = _clean_text(getattr(doc, "kind", ""), limit=24)
        line = f"- {title}"
        if kind:
            line += f"（{kind}）"
        if used + len(line) + 1 > budget:
            break
        lines.append(line)
        used += len(line) + 1
        listed += 1
    omitted = total - listed
    if omitted > 0:
        lines.append(f"（另有 {omitted} 个文件未列出）")
    return "\n".join(lines) if listed > 0 else ""


def _resource_projects_block(
    workspace_snapshot: ClientWorkspaceResponse,
    *,
    budget: int,
    max_count: int,
) -> str:
    modules = list(getattr(workspace_snapshot, "projectModules", []) or [])
    if not modules:
        return ""
    # 按 createdAt 升序，呈现演进时间线
    ordered = sorted(modules, key=lambda m: str(getattr(m, "createdAt", "") or ""))
    total = len(ordered)
    lines: list[str] = [f"── 项目模块（projectModules · 共 {total} 个，按创建时间）──"]
    used = sum(len(line) for line in lines)
    listed = 0
    for module in ordered:
        if listed >= max_count:
            break
        name = _clean_text(getattr(module, "name", ""), limit=80) or "未命名项目"
        created_at = str(getattr(module, "createdAt", "") or "")[:7]
        goal = _short_label(getattr(module, "goal", ""), limit=80)
        parts = [f"- [{created_at or '?'}] {name}"]
        if goal:
            parts.append(f"goal: {goal}")
        line = "；".join(parts)
        if used + len(line) + 1 > budget:
            break
        lines.append(line)
        used += len(line) + 1
        listed += 1
    omitted = total - listed
    if omitted > 0:
        lines.append(f"（另有 {omitted} 个项目模块未列出）")
    return "\n".join(lines) if listed > 0 else ""


def _resource_judgments_block(
    workspace_snapshot: ClientWorkspaceResponse,
    *,
    budget: int,
    max_count: int,
) -> str:
    judgments = list(getattr(workspace_snapshot, "latestJudgments", []) or [])
    if not judgments:
        return ""
    total = len(judgments)
    lines: list[str] = [f"── 已采纳判断（latestJudgments · 共 {total} 条）──"]
    used = sum(len(line) for line in lines)
    listed = 0
    for judgment in judgments:
        if listed >= max_count:
            break
        topic = _clean_text(getattr(judgment, "topic", ""), limit=80) or "判断"
        status = str(getattr(judgment, "status", "") or "draft").lower()
        confidence = str(getattr(judgment, "confidence", "") or "").strip()
        meta_parts: list[str] = [status]
        if confidence:
            meta_parts.append(f"信心={confidence}")
        line = f"- [{'/'.join(meta_parts)}] {topic}"
        if used + len(line) + 1 > budget:
            break
        lines.append(line)
        used += len(line) + 1
        listed += 1
    omitted = total - listed
    if omitted > 0:
        lines.append(f"（另有 {omitted} 条判断未列出）")
    return "\n".join(lines) if listed > 0 else ""


def _resource_meetings_block(
    workspace_snapshot: ClientWorkspaceResponse,
    *,
    budget: int,
    max_count: int,
) -> str:
    meetings = list(getattr(workspace_snapshot, "meetings", []) or [])
    if not meetings:
        return ""
    # 按 scheduledAt 倒序
    ordered = sorted(
        meetings,
        key=lambda m: str(getattr(m, "scheduledAt", "") or ""),
        reverse=True,
    )
    total = len(ordered)
    lines: list[str] = [f"── 会议（meetings · 共 {total} 场，按时间倒序）──"]
    used = sum(len(line) for line in lines)
    listed = 0
    for meeting in ordered:
        if listed >= max_count:
            break
        title = _clean_text(getattr(meeting, "title", ""), limit=80) or "未命名会议"
        scheduled_at = str(getattr(meeting, "scheduledAt", "") or "")[:10]
        stage = _clean_text(getattr(meeting, "stage", ""), limit=20)
        parts = [f"- [{scheduled_at or '?'}] {title}"]
        if stage:
            parts.append(f"阶段: {stage}")
        line = "；".join(parts)
        if used + len(line) + 1 > budget:
            break
        lines.append(line)
        used += len(line) + 1
        listed += 1
    omitted = total - listed
    if omitted > 0:
        lines.append(f"（另有 {omitted} 场会议未列出）")
    return "\n".join(lines) if listed > 0 else ""


def _resource_goals_block(
    workspace_snapshot: ClientWorkspaceResponse,
    *,
    budget: int,
    max_count: int,
) -> str:
    goals = list(getattr(workspace_snapshot, "goals", []) or [])
    if not goals:
        return ""
    total = len(goals)
    lines: list[str] = [f"── 目标（goals · 共 {total} 个）──"]
    used = sum(len(line) for line in lines)
    listed = 0
    for goal in goals:
        if listed >= max_count:
            break
        title = _clean_text(getattr(goal, "title", ""), limit=80) or "未命名目标"
        quarter = _clean_text(getattr(goal, "quarter", ""), limit=20)
        progress = getattr(goal, "progress", None)
        parts = [f"- {title}"]
        if quarter:
            parts.append(quarter)
        if progress is not None:
            try:
                parts.append(f"进度 {int(progress)}%")
            except (TypeError, ValueError):
                pass
        line = "；".join(parts)
        if used + len(line) + 1 > budget:
            break
        lines.append(line)
        used += len(line) + 1
        listed += 1
    omitted = total - listed
    if omitted > 0:
        lines.append(f"（另有 {omitted} 个目标未列出）")
    return "\n".join(lines) if listed > 0 else ""


def build_client_file_catalog(
    workspace_snapshot: ClientWorkspaceResponse | None,
    *,
    prompt: str = "",
    max_files: int = 100,
    max_chars: int = 4500,
) -> str:
    """R8.15：任务型请求专用的「客户全文件目录」。

    与 build_strategic_pack 互补：不喂 DNA / judgments / chat history 等长内容（避免 prompt 超时），
    只列 documents 表里所有文件的 title + kind + tags。

    用途：用户要做表/提取/列出全部 X 时，LLM 至少能从**文件名**直接解析结构化信息
    （如「姓名-岗位-日期.pdf」可以直接读出姓名/岗位/入职日期，不需要等检索命中文件内容）。
    """
    if workspace_snapshot is None:
        return ""
    documents = list(getattr(workspace_snapshot, "documents", []) or [])
    if not documents:
        return ""

    # 按 importedAt 倒序，最近上传的先
    ordered = sorted(
        documents,
        key=lambda d: str(getattr(d, "importedAt", "") or ""),
        reverse=True,
    )

    lines: list[str] = [
        "【客户已上传的全部资料目录（仅文件名 + 类型，无文件正文）】",
        "下面列出的是该客户**已上传到系统**的所有文件。这些文件名都是**真实存在的**，",
        "**可以直接引用**——比如「姓名-岗位-起始日期-终止日期.pdf」格式的文件名，",
        "你可以直接从文件名解析出姓名、岗位、入职日期，**不需要等检索命中文件内容**。",
        "",
    ]
    used = sum(len(line) for line in lines)
    listed = 0
    for doc in ordered:
        if listed >= max_files:
            break
        title = _clean_text(getattr(doc, "title", ""), limit=180) or "未命名"
        kind = _clean_text(getattr(doc, "kind", ""), limit=24)
        line = f"- {title}"
        if kind:
            line += f"（{kind}）"
        if used + len(line) + 1 > max_chars:
            break
        lines.append(line)
        used += len(line) + 1
        listed += 1

    omitted = len(ordered) - listed
    if omitted > 0:
        lines.append(f"\n（另有 {omitted} 个文件因预算或排序未列出）")

    if listed == 0:
        return ""
    return "\n".join(lines)


def _brand_strategy_block(
    brand_strategy: dict[str, object] | None,
    *,
    budget: int,
) -> str:
    """段 7: 客户战略主张+方法学+应然相关方 (来自 brand_strategy_extractor 抽取).

    数据来源是用户上传的 strategy.md / methodology.md → brand_strategy_extractor LLM
    抽出来的结构化"战略骨架". 给 chat 主答案 prompt 一个明确的"客户战略锚点", 让 LLM
    在回答里基于真战略 (心智素养 / 县域复制 / 应然相关方) 推导, 不是凭空编造方向.
    """
    if not isinstance(brand_strategy, dict):
        return ""
    so = _clean_text(brand_strategy.get("strategicObjective") or "", limit=400)
    methodology = _clean_text(brand_strategy.get("methodology") or "", limit=400)
    stakeholders_raw = brand_strategy.get("stakeholders") or []
    stakeholder_names: list[str] = []
    for s in stakeholders_raw[:10]:
        if isinstance(s, dict):
            name = _clean_text(s.get("name") or "", limit=24)
            if name:
                stakeholder_names.append(name)

    if not so and not methodology and not stakeholder_names:
        return ""

    lines: list[str] = ["【客户战略骨架（用户已上传 strategy.md + methodology.md 的结构化抽取）】"]
    used = len(lines[0])
    if so:
        line = f"\n战略主张：{so}"
        if used + len(line) <= budget:
            lines.append(line)
            used += len(line)
    if methodology:
        line = f"\n方法学：{methodology}"
        if used + len(line) <= budget:
            lines.append(line)
            used += len(line)
    if stakeholder_names:
        line = f"\n应然关注相关方：{'、'.join(stakeholder_names[:8])}"
        if used + len(line) <= budget:
            lines.append(line)
    return "\n".join(lines)


def build_strategic_pack(
    workspace_snapshot: ClientWorkspaceResponse | None,
    *,
    prompt: str = "",
    max_chars: int = 13000,
    dna_budget: int = 4500,
    judgment_budget: int = 2400,
    project_timeline_budget: int = 1400,
    chat_insight_budget: int = 2400,
    documents_budget: int = 1500,
    notebook_budget: int = 900,
    brand_strategy: dict[str, object] | None = None,
    brand_strategy_budget: int = 1200,
) -> str:
    """构造"战略素材包"：组织 DNA + 已采纳判断推导 + 项目演进时间线 + 历史 chat 沉淀 + 文档目录 + 组织记忆。

    与 :func:`build_workspace_background_pack` 互补：
    - background_pack 是"客户当前状态"（项目清单 + 任务 + 会议 + 矛盾），扁平且时效性强
    - strategic_pack 是"组织级战略素材"，承载差异化定位、赛道边界、判断推导链、项目演进、历史观点

    Pass 1（出大纲）需要后者才能跳出"项目进展"层面、形成战略层判断角度。
    每个段独立有预算，缺失的段自动跳过（不留空标题）。返回空字符串表示客户没有任何战略素材。

    禁用硬编码框架 —— 本函数只拼资料，不写"按 SWOT/三飞轮 组织"之类的指引。
    """
    if workspace_snapshot is None:
        return ""

    sections: list[str] = []

    # 段 0: 客户战略骨架 (来自用户上传的 strategy.md/methodology.md, 经 brand_strategy_extractor 抽取).
    # 放在最前面是因为这是 chat 答案的"战略锚点", 后面所有素材都应该围绕这个锚点解读.
    brand_strategy_block_text = _brand_strategy_block(brand_strategy, budget=brand_strategy_budget)
    if brand_strategy_block_text:
        sections.append(brand_strategy_block_text)

    # 段 1：组织 DNA（差异化定位 / 赛道边界 / 核心论点）
    dna_block = _strategic_dna_block(workspace_snapshot, prompt=prompt, budget=dna_budget)
    if dna_block:
        sections.append(dna_block)

    # 段 2：组织记忆笔记（业务模块、关键产品、挑战、目标、近期事实）
    notebook_block = _strategic_notebook_block(workspace_snapshot, budget=notebook_budget)
    if notebook_block:
        sections.append(notebook_block)

    # 段 3：已采纳判断的推导链
    judgment_block = _strategic_judgment_block(workspace_snapshot, budget=judgment_budget)
    if judgment_block:
        sections.append(judgment_block)

    # 段 4：项目演进时间线
    timeline_block = _strategic_project_timeline_block(workspace_snapshot, budget=project_timeline_budget)
    if timeline_block:
        sections.append(timeline_block)

    # 段 5：客户文档目录（让 LLM 知道客户上传过哪些资料 —— 项目名/方案/会议常常藏在文件名里）
    documents_block = _strategic_documents_block(workspace_snapshot, budget=documents_budget)
    if documents_block:
        sections.append(documents_block)

    # 段 6：历史 chat 中沉淀的关键观点
    chat_block = _strategic_chat_insight_block(workspace_snapshot, budget=chat_insight_budget)
    if chat_block:
        sections.append(chat_block)

    if not sections:
        return ""

    pack = "【战略素材包 · 组织级定位/判断/演进/历史观点】\n\n" + "\n\n".join(sections)
    if len(pack) > max_chars:
        pack = pack[: max(1, max_chars - 1)].rstrip() + "…"
    return pack


def _strategic_dna_block(
    workspace_snapshot: ClientWorkspaceResponse,
    *,
    prompt: str,
    budget: int,
) -> str:
    """从 dnaModules 里挑最相关的，扁平拼出 DNA 摘要段。"""
    modules = [
        module
        for module in list(getattr(workspace_snapshot, "dnaModules", []) or [])
        if bool(_field_value(module, "hasDocument"))
        and _full_text_field(module, ("markdownContent", "normalizedText", "summary", "text", "content"))
    ]
    if not modules:
        return ""

    prompt_tokens = [
        token for token in re.findall(r"[一-鿿]{2,}|[A-Za-z0-9_]+", str(prompt or "").lower())
        if len(token) >= 2
    ]

    def relevance_score(module: object) -> tuple[int, int, str]:
        title = _clean_text(_field_value(module, "title"), limit=120)
        text = _full_text_field(module, ("markdownContent", "summary", "normalizedText", "text", "content"))
        haystack = f"{title} {text[:4000]}".lower()
        token_score = sum(2 for token in prompt_tokens if token and token in haystack)
        source_score = 5 if str(_field_value(module, "sourceKind") or "manual") == "manual" else 1
        return (token_score + source_score, len(text), str(_field_value(module, "updatedAt") or ""))

    ordered = sorted(modules, key=relevance_score, reverse=True)
    lines: list[str] = ["─── 组织 DNA（差异化定位 / 赛道边界 / 核心论点）"]
    used = 0
    # 加权分配：最相关的 module 拿更多 budget（含深度市场调研、赛道判断这种长篇资料）。
    # 排名 1: budget * 0.45（最相关，通常含深度长篇）
    # 排名 2: budget * 0.27
    # 排名 3+: 共享剩余 budget * 0.28
    take_modules = ordered[:5]
    if len(take_modules) >= 1:
        weights = [0.45, 0.27, 0.14, 0.09, 0.05][: len(take_modules)]
        # 归一化（防止 modules<5 时浪费 budget）
        total_w = sum(weights) or 1.0
        weights = [w / total_w for w in weights]
    else:
        weights = []
    for index, module in enumerate(take_modules):
        title = _clean_text(_field_value(module, "title"), limit=120) or "DNA 模块"
        module_key = _clean_text(_field_value(module, "moduleKey"), limit=80)
        updated_at = _clean_text(_field_value(module, "updatedAt"), limit=80)
        raw_text = _full_text_field(module, ("markdownContent", "summary", "normalizedText", "text", "content"))
        text = re.sub(r"\s+", " ", raw_text).strip()
        remaining = budget - used
        if remaining <= 400:
            break
        # 给当前 module 分配权重 * 总预算，但至少 500 字（短 module 不浪费），且不超过 remaining
        module_budget = max(500, int(budget * weights[index]))
        take = min(module_budget, remaining)
        snippet = text[:take].rstrip()
        if len(text) > take:
            snippet += "…"
        header = f"[DNA · {title}]"
        if module_key:
            header += f"（{module_key}）"
        if updated_at:
            header += f" · 更新于 {updated_at[:10]}"
        lines.append(header)
        lines.append(snippet)
        used += len(snippet) + len(header)
    if len(lines) <= 1:
        return ""
    return "\n".join(lines)


def _strategic_notebook_block(
    workspace_snapshot: ClientWorkspaceResponse,
    *,
    budget: int,
) -> str:
    """组织笔记快照：业务模块 / 关键产品 / 挑战 / 协作目标 / 近期事实 / 信息缺口。

    这是 organization_notebook 持续积累的组织级摘要，常含项目命名、阶段、挑战等
    战略性表达。喂入能直接给 Pass 1"组织全景图"。
    """
    notebook = getattr(workspace_snapshot, "notebookSummary", None)
    if notebook is None:
        return ""

    lines: list[str] = ["─── 组织记忆笔记（业务模块 / 关键产品 / 挑战 / 协作目标 / 近期事实）"]
    used = 0

    def _append(label: str, value: str | list[str] | None) -> None:
        nonlocal used
        if not value:
            return
        remaining = budget - used
        if remaining <= 80:
            return
        if isinstance(value, list):
            cleaned_items = [re.sub(r"\s+", " ", str(item or "")).strip() for item in value if str(item or "").strip()]
            if not cleaned_items:
                return
            content = "；".join(cleaned_items)
        else:
            content = re.sub(r"\s+", " ", str(value or "")).strip()
            if not content:
                return
        take = min(len(content), remaining - len(label) - 4)
        if take <= 30:
            return
        snippet = content[:take]
        if len(content) > take:
            snippet += "…"
        line = f"- {label}：{snippet}"
        lines.append(line)
        used += len(line)

    _append("组织简介", getattr(notebook, "organizationIntro", ""))
    _append("当前阶段", getattr(notebook, "currentStage", ""))
    _append("协作关系", getattr(notebook, "collaborationRelationship", ""))
    _append("业务模块", getattr(notebook, "businessModules", []))
    _append("关键产品", getattr(notebook, "keyProducts", []))
    _append("关键人物", getattr(notebook, "keyPeople", []))
    _append("当前挑战", getattr(notebook, "currentChallenges", []))
    _append("协作目标", getattr(notebook, "collaborationGoals", []))
    _append("近期事实", getattr(notebook, "recentFacts", []))
    _append("信息缺口", getattr(notebook, "informationGaps", []))

    if len(lines) <= 1:
        return ""
    return "\n".join(lines)


def _strategic_documents_block(
    workspace_snapshot: ClientWorkspaceResponse,
    *,
    budget: int,
) -> str:
    """客户文档目录：按 importedAt 倒序列出文件标题。

    很多客户的项目名、方案、会议纪要藏在文件名里（如「心灵魔法学院 2024 项目报告.pdf」、
    「教师赋能体系建设方案.docx」），但 projectModules 表可能是空的。
    单独列文档目录能让 Pass 1 识别"客户都在做哪些事"，弥补 projectModules 缺失。
    不读文件内容，只列标题 + tags + kind。
    """
    documents = list(getattr(workspace_snapshot, "documents", []) or [])
    if not documents:
        return ""

    def sort_key(doc: object) -> str:
        return str(getattr(doc, "importedAt", "") or "")

    ordered = sorted(documents, key=sort_key, reverse=True)
    lines: list[str] = ["─── 客户已上传的资料目录（标题 + 类型 + 标签，最新 → 较早）"]
    used = 0
    max_lines = 30  # 最多列 30 条，避免单纯标题刷屏
    for doc in ordered[:max_lines]:
        title = _clean_text(getattr(doc, "title", ""), limit=120) or "未命名文档"
        kind = _clean_text(getattr(doc, "kind", ""), limit=30)
        imported_at = str(getattr(doc, "importedAt", "") or "")[:10]
        tags = list(getattr(doc, "tags", []) or [])
        meta_parts: list[str] = []
        if imported_at:
            meta_parts.append(imported_at)
        if kind:
            meta_parts.append(kind)
        if tags:
            meta_parts.append("#" + " #".join(tag for tag in tags[:3] if tag))
        meta_str = f"（{'，'.join(meta_parts)}）" if meta_parts else ""
        line = f"- {title}{meta_str}"
        remaining = budget - used
        if remaining <= 60:
            break
        if len(line) > remaining:
            line = line[: remaining - 1] + "…"
        lines.append(line)
        used += len(line)
    if len(lines) <= 1:
        return ""
    return "\n".join(lines)


def _strategic_judgment_block(
    workspace_snapshot: ClientWorkspaceResponse,
    *,
    budget: int,
) -> str:
    """已采纳/批准过的核心判断，带 summary 完整推导。"""
    judgments = list(getattr(workspace_snapshot, "latestJudgments", []) or [])
    approved = [
        j for j in judgments
        if str(getattr(j, "status", "") or "").lower() in {"confirmed", "approved"}
        or str(getattr(j, "authorityLevel", "") or "").lower() == "approved"
    ]
    pool = approved if approved else judgments
    if not pool:
        return ""

    lines: list[str] = ["─── 已采纳的核心判断（推导链 / 信心 / 风险）"]
    used = 0
    for judgment in pool[:8]:
        topic = _clean_text(getattr(judgment, "topic", ""), limit=80) or "判断"
        summary = re.sub(r"\s+", " ", str(getattr(judgment, "summary", "") or "")).strip()
        if not summary:
            continue
        meta_parts: list[str] = []
        confidence = str(getattr(judgment, "confidence", "") or "").strip()
        if confidence:
            meta_parts.append(f"信心={confidence}")
        risk = str(getattr(judgment, "riskLevel", "") or "").strip()
        if risk:
            meta_parts.append(f"风险={risk}")
        authority = str(getattr(judgment, "authorityLevel", "") or "").strip()
        if authority:
            meta_parts.append(f"authority={authority}")
        quality = str(getattr(judgment, "qualityTier", "") or "").strip()
        if quality and quality != "legacy":
            meta_parts.append(f"quality={quality}")
        evidence_ids = list(getattr(judgment, "evidenceIds", []) or [])
        if evidence_ids:
            meta_parts.append(f"证据={len(evidence_ids)} 条")
        meta_str = f"（{'，'.join(meta_parts)}）" if meta_parts else ""
        header = f"【{topic}】{meta_str}"
        remaining = budget - used
        if remaining <= 250:
            break
        # judgment summary 是推导链精华，尽量不截
        per_summary = min(640, remaining - len(header) - 10)
        if per_summary <= 80:
            break
        body = summary[:per_summary]
        if len(summary) > per_summary:
            body += "…"
        lines.append(header)
        lines.append(body)
        used += len(header) + len(body)
    if len(lines) <= 1:
        return ""
    return "\n".join(lines)


def _strategic_project_timeline_block(
    workspace_snapshot: ClientWorkspaceResponse,
    *,
    budget: int,
) -> str:
    """项目演进时间线：按 createdAt 排序，让 LLM 看到"第二曲线 / 多线布局"信号。"""
    modules = list(getattr(workspace_snapshot, "projectModules", []) or [])
    if not modules:
        return ""

    def sort_key(module: object) -> str:
        return str(getattr(module, "createdAt", "") or "")

    ordered = sorted(modules, key=sort_key)
    lines: list[str] = ["─── 项目演进时间线（最早 → 最新，看演进/分阶段/第二曲线）"]
    used = 0
    for module in ordered:
        name = _clean_text(getattr(module, "name", ""), limit=80) or "项目"
        created_at = str(getattr(module, "createdAt", "") or "")
        year_label = created_at[:7] if created_at else "?"
        goal = _short_label(getattr(module, "goal", ""), limit=140)
        description = _short_label(getattr(module, "description", ""), limit=200)
        owner = _clean_text(getattr(module, "ownerName", ""), limit=40)
        deliverables = list(getattr(module, "deliverables", []) or [])
        keywords = list(getattr(module, "keywords", []) or [])
        parts: list[str] = [f"- [{year_label}] {name}"]
        if owner:
            parts.append(f"负责人={owner}")
        if goal:
            parts.append(f"目标：{goal}")
        elif description:
            parts.append(f"描述：{description}")
        if deliverables:
            parts.append(f"交付物={'、'.join(deliverables[:4])}")
        if keywords:
            parts.append(f"关键词={'、'.join(keywords[:4])}")
        line = "；".join(parts)
        remaining = budget - used
        if remaining <= 80:
            break
        if len(line) > remaining:
            line = line[: remaining - 1] + "…"
        lines.append(line)
        used += len(line)
    if len(lines) <= 1:
        return ""
    return "\n".join(lines)


def _strategic_chat_insight_block(
    workspace_snapshot: ClientWorkspaceResponse,
    *,
    budget: int,
) -> str:
    """历史 chat 中沉淀的关键观点：从 assistant 消息的 structuredData.judgment/analysis 里挑。

    优先取 grounded_answer + sufficient/partial 证据 + 含 judgment 的消息，按时间倒序。
    这是用户和系统已经一起验证过的视角性观点，对新一轮答题非常有用。
    """
    messages = list(getattr(workspace_snapshot, "recentMessages", []) or [])
    assistant_messages = [
        m for m in messages
        if str(getattr(m, "role", "") or "").lower() == "assistant"
        and getattr(m, "structuredData", None) is not None
    ]
    if not assistant_messages:
        return ""

    def score(message: object) -> tuple[int, str]:
        structured = getattr(message, "structuredData", None)
        judgment_text = str(getattr(structured, "judgment", "") or "").strip() if structured else ""
        answer_mode = str(getattr(message, "answerMode", "") or "").lower()
        evidence_status = str(getattr(message, "evidenceStatus", "") or "").lower()
        rank = 0
        if judgment_text:
            rank += 4
        if answer_mode == "grounded_answer":
            rank += 3
        elif answer_mode == "grounded_fallback":
            rank += 1
        if evidence_status == "sufficient":
            rank += 2
        elif evidence_status == "partial":
            rank += 1
        return (rank, str(getattr(message, "createdAt", "") or ""))

    ranked = sorted(assistant_messages, key=score, reverse=True)
    lines: list[str] = ["─── 历史对话中已沉淀的关键观点（用户和系统已一起验证过的视角）"]
    used = 0
    for message in ranked[:10]:
        structured = getattr(message, "structuredData", None)
        if not structured:
            continue
        judgment_text = re.sub(r"\s+", " ", str(getattr(structured, "judgment", "") or "")).strip()
        analysis_text = re.sub(r"\s+", " ", str(getattr(structured, "analysis", "") or "")).strip()
        if not (judgment_text or analysis_text):
            continue
        created_at = str(getattr(message, "createdAt", "") or "")[:10]
        prefix = f"[{created_at}]" if created_at else "[chat]"
        remaining = budget - used
        if remaining <= 200:
            break
        body_parts: list[str] = []
        if judgment_text:
            body_parts.append(f"判断：{judgment_text[:240]}")
        if analysis_text:
            available = remaining - sum(len(p) for p in body_parts) - len(prefix) - 30
            take = min(360, max(80, available))
            if take >= 80:
                analysis_snippet = analysis_text[:take]
                if len(analysis_text) > take:
                    analysis_snippet += "…"
                body_parts.append(f"分析：{analysis_snippet}")
        if not body_parts:
            continue
        line = f"{prefix} " + " / ".join(body_parts)
        lines.append(line)
        used += len(line)
    if len(lines) <= 1:
        return ""
    return "\n".join(lines)


def build_dna_tool_context_from_workspace(
    workspace_snapshot: ClientWorkspaceResponse | None,
    *,
    prompt: str,
    purpose: str | None = None,
    max_chars: int = 18000,
) -> DnaToolContextRecord:
    modules = [
        module
        for module in list(getattr(workspace_snapshot, "dnaModules", []) or [])
        if bool(_field_value(module, "hasDocument")) and _full_text_field(module, ("normalizedText", "markdownContent", "summary", "text", "content"))
    ]
    resolved_purpose = purpose or infer_dna_tool_purpose(prompt)
    if not modules:
        return DnaToolContextRecord(purpose=resolved_purpose)

    preferred_kinds = _preferred_dna_kinds_for_purpose(resolved_purpose)
    prompt_tokens = [token for token in re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_]+", str(prompt or "").lower()) if len(token) >= 2]

    def module_rank(module: object) -> tuple[int, int, str, str]:
        title = _clean_text(_field_value(module, "title"), limit=120)
        module_key = _clean_text(_field_value(module, "moduleKey"), limit=80)
        text = _full_text_field(module, ("summary", "normalizedText", "markdownContent", "text", "content"))
        kinds = _dna_module_kinds(module)
        kind_score = sum((len(preferred_kinds) - index) * 20 for index, kind in enumerate(preferred_kinds) if kind in kinds)
        token_score = sum(1 for token in prompt_tokens if token and token in f"{title} {text[:6000]}".lower())
        source_kind_score = 8 if str(_field_value(module, "sourceKind") or "manual") == "manual" else 2
        return (kind_score + token_score * 6 + source_kind_score, len(text), str(_field_value(module, "updatedAt") or ""), module_key)

    ordered_modules = sorted(modules, key=module_rank, reverse=True)
    selected_modules: list[str] = []
    selected_kinds: list[str] = []
    blocks: list[str] = [
        "【客户 DNA 工具调用】",
        f"purpose={resolved_purpose}",
        "使用规则：DNA 是客户理解、战略判断和行动建议工具；不能单独作为正式事实来源。",
        "证据边界：没有 L1/L2 支撑的内容只能作为高置信判断或待证据确认；内部战略口径不能直接用于对外公开回答。",
        "数字边界：比例、倍数、规模、成效、时间节点必须有来源；无来源数字只能作为待核验线索。",
    ]
    content_budget = max(1800, max_chars - sum(len(line) for line in blocks) - 80)
    module_budget = max(1800, content_budget // max(1, min(len(ordered_modules), 4)))
    used_chars = 0
    for module in ordered_modules:
        title = _clean_text(_field_value(module, "title"), limit=120) or "客户 DNA"
        module_key = _clean_text(_field_value(module, "moduleKey"), limit=80)
        source_kind = _clean_text(_field_value(module, "sourceKind"), limit=80) or "manual"
        updated_at = _clean_text(_field_value(module, "updatedAt"), limit=80)
        kinds = _dna_module_kinds(module)
        raw_text = _full_text_field(module, ("normalizedText", "markdownContent", "summary", "text", "content"))
        raw_text = _filter_dna_text_for_purpose(raw_text, resolved_purpose)
        guarded_text = _mark_unverified_dna_numbers(re.sub(r"\s+", " ", raw_text).strip())
        remaining = content_budget - used_chars
        if remaining <= 600:
            break
        take = min(module_budget, remaining)
        snippet = guarded_text[:take].rstrip()
        if len(guarded_text) > take:
            snippet += "…"
        blocks.append(
            "\n".join(
                [
                    f"[DNA 模块] {title}",
                    f"moduleKey={module_key or '-'}；kinds={','.join(kinds)}；sourceKind={source_kind}；updatedAt={updated_at or '-'}",
                    snippet,
                ]
            )
        )
        used_chars += len(snippet)
        selected_modules.append(title)
        selected_kinds.extend(kinds)
        if len(selected_modules) >= 6:
            break

    selected_kinds = list(dict.fromkeys(selected_kinds))
    context_text = "\n\n".join(blocks).strip()
    if len(context_text) > max_chars:
        context_text = context_text[: max_chars - 1].rstrip() + "…"
    source_level_summary = "；".join(
        f"{level}={context_text.count(level)}"
        for level in ("L1", "L2", "L3", "L4")
        if context_text.count(level)
    ) or "未检测到明确 L1/L2/L3/L4 标注"
    dates = sorted(set(re.findall(r"20\d{2}(?:[-/.年]\d{1,2})?(?:[-/.月]\d{1,2})?", context_text)))
    time_scope_summary = "、".join(dates[-6:]) if dates else "未检测到明确时间戳"
    warnings = [
        "DNA 不能单独作为正式事实来源",
        "内部战略口径不得直接用于对外公开回答",
    ]
    if "数字/成效口径需来源核验" in context_text:
        warnings.append("存在已降级的无来源数字/成效表述")
    return DnaToolContextRecord(
        purpose=resolved_purpose,
        selected_modules=selected_modules,
        selected_kinds=selected_kinds,
        context_text=context_text,
        source_level_summary=source_level_summary,
        time_scope_summary=time_scope_summary,
        warnings=warnings,
    )


def _consultant_noise_text(title: str = "", body: str = "", path: str = "", source_type: str = "") -> bool:
    normalized = _clean_text(f"{title} {body} {path} {source_type}", limit=5000).lower()
    if not normalized:
        return False
    if any(token in normalized for token in _CONSULTANT_NOISE_TOKENS):
        return True
    if any(ext in normalized for ext in (".jpg", ".jpeg", ".png", ".heic", ".gif")) and any(
        token in normalized for token in _CONSULTANT_ATTACHMENT_NOISE_TOKENS
    ):
        return True
    quality = classify_evidence_quality_fields(
        title=title,
        excerpt=body,
        source_type=source_type,
        section_label="",
        path=path,
        retrieval_stage="raw_chunk",
    )
    return bool(quality.isNoise and quality.sourceKind in {"ppt_visual", "ppt_master", "template_page", "short_excerpt"})


def _is_high_signal_consultant_material(title: str = "", body: str = "", tags: object = None) -> bool:
    normalized = _clean_text(f"{title} {body} {' '.join(str(item) for item in _list_value(tags))}", limit=4000).lower()
    if not normalized:
        return False
    return any(token in normalized for token in _CONSULTANT_HIGH_SIGNAL_TOKENS)


def _format_consultant_item(
    item: object,
    *,
    title_fields: tuple[str, ...] = ("title", "name", "label", "fileName"),
    body_fields: tuple[str, ...] = ("summary", "excerpt", "content", "text", "description", "rationale", "statement"),
    body_limit: int = 900,
) -> tuple[str, bool]:
    title = _first_text_field(item, title_fields, limit=180)
    body = _first_text_field(item, body_fields, limit=body_limit)
    path = _first_text_field(item, ("path", "filePath", "sourcePath", "originalPath"), limit=360)
    source_type = _first_text_field(item, ("sourceType", "kind", "type", "retrievalStage"), limit=80)
    if _consultant_noise_text(title=title, body=body, path=path, source_type=source_type):
        return "", True
    if title and body and title not in body:
        return f"- {title}：{body}", False
    if body:
        return f"- {body}", False
    if title:
        return f"- {title}", False
    return "", False


def build_consultant_synthesis_material_pack(
    *,
    prompt: str,
    kernel_result: DataCenterKernelResultRecord,
    workspace_snapshot: ClientWorkspaceResponse | None,
    max_chars: int = 36000,
) -> ConsultantSynthesisMaterialPack:
    page_context = kernel_result.pageContext
    answer_material = kernel_result.answerMaterial
    source_counts: dict[str, int] = {}
    excluded_noise_count = 0
    sections: list[str] = []

    def add_section(title: str, lines: list[str], source_key: str) -> None:
        cleaned_lines = [line for line in lines if str(line).strip()]
        if not cleaned_lines:
            return
        source_counts[source_key] = source_counts.get(source_key, 0) + len(cleaned_lines)
        sections.append(f"【{title}】\n" + "\n".join(cleaned_lines))

    def collect_items(
        items: list[object],
        *,
        source_key: str,
        title_fields: tuple[str, ...] = ("title", "name", "label", "fileName"),
        body_fields: tuple[str, ...] = ("summary", "excerpt", "content", "text", "description", "rationale", "statement"),
        limit: int = 10,
        body_limit: int = 900,
        high_signal_only: bool = False,
    ) -> list[str]:
        nonlocal excluded_noise_count
        lines: list[str] = []
        for item in items:
            title = _first_text_field(item, title_fields, limit=220)
            body = _first_text_field(item, body_fields, limit=body_limit)
            if high_signal_only and not _is_high_signal_consultant_material(
                title=title,
                body=body,
                tags=_field_value(item, "tags"),
            ):
                continue
            line, is_noise = _format_consultant_item(
                item,
                title_fields=title_fields,
                body_fields=body_fields,
                body_limit=body_limit,
            )
            if is_noise:
                excluded_noise_count += 1
                continue
            if line and line not in lines:
                lines.append(line)
            if len(lines) >= limit:
                break
        return lines

    client_lines: list[str] = []
    if workspace_snapshot is not None and workspace_snapshot.client is not None:
        client = workspace_snapshot.client
        client_lines.append(f"- 客户名称：{_clean_text(getattr(client, 'name', ''), limit=120) or '当前客户'}")
        client_stage = _clean_text(getattr(client, "stage", ""), limit=120)
        client_summary = _clean_text(getattr(client, "summary", ""), limit=700)
        if client_stage:
            client_lines.append(f"- 当前阶段：{client_stage}")
        if client_summary:
            client_lines.append(f"- 客户摘要：{client_summary}")
    if not client_lines and page_context is not None:
        client_lines.append(f"- 客户 ID：{_clean_text(page_context.clientId, limit=120) or '当前客户'}")

    sections.append(
        "\n".join(
            [
                "【用户问题】",
                _clean_text(prompt, limit=1000),
                "",
                "【材料包使用原则】",
                "以下材料用于生成开放、深入、可解释的顾问式综合回答；不要在正文中列资料清单，不要暴露系统过程。",
            ]
        ).strip()
    )
    add_section("客户基础信息", client_lines, "clientBasics")
    # P0 背景包：consultant_synthesis 后续会单独列正式判断/相关会议/任务，
    # 这里只放一个紧凑的"画像总览"作为开头底色（不重复后面的 section）。
    consultant_background = build_workspace_background_pack(
        workspace_snapshot,
        max_chars=6500,
        judgment_limit=4,
        meeting_limit=2,
        task_limit=4,
        project_module_limit=4,
        goal_limit=3,
        open_question_limit=2,
        conflict_limit=2,
    )
    if consultant_background:
        sections.append(consultant_background)
        source_counts["backgroundPack"] = 1
    dna_tool_context = build_dna_tool_context_from_workspace(
        workspace_snapshot,
        prompt=prompt,
        purpose="strategy" if "战略" in prompt or "核心" in prompt else None,
        max_chars=14000,
    )
    if dna_tool_context.context_text:
        source_counts["clientDnaTool"] = max(1, len(dna_tool_context.selected_modules))
        sections.append(dna_tool_context.context_text)

    boundary_notes: list[str] = []
    if page_context is not None:
        boundary_notes = [
            _clean_text(item, limit=260)
            for item in list(page_context.boundaryNotes or [])[:8]
            if _clean_text(item, limit=260)
        ]
        missing_context = [
            _clean_text(item, limit=260)
            for item in list(page_context.missingContext or [])[:8]
            if _clean_text(item, limit=260)
        ]
        add_section("正式判断", collect_items(list(page_context.officialJudgments or []), source_key="officialJudgments", limit=10), "officialJudgments")
        add_section("候选判断与待确认洞察", collect_items(list(page_context.candidateJudgments or []), source_key="candidateJudgments", limit=12), "candidateJudgments")
        add_section("证据卡与分析卡", collect_items(list(page_context.evidenceCards or []), source_key="evidenceCards", limit=12), "evidenceCards")
        add_section("原文证据摘录", collect_items(list(page_context.rawEvidence or []), source_key="rawEvidence", limit=16, body_limit=1200), "rawEvidence")
        add_section("相关会议", collect_items(list(page_context.relatedMeetings or []), source_key="relatedMeetings", limit=8), "relatedMeetings")
        add_section("相关任务与近期工作", collect_items(list(page_context.relatedTasks or []), source_key="relatedTasks", limit=8), "relatedTasks")
        add_section("相关文档", collect_items(list(page_context.relatedDocuments or []), source_key="relatedDocuments", limit=10, high_signal_only=True), "relatedDocuments")
        add_section("开放问题", [f"- {item}" for item in missing_context[:5]], "missingContext")
        add_section("边界说明", [f"- {item}" for item in boundary_notes[:5]], "boundaryNotes")
        add_section("统一记忆", [f"- {_clean_text(item, limit=500)}" for item in list(page_context.memoryFacts or [])[:10] if _clean_text(item, limit=500)], "memoryFacts")

    if answer_material is not None:
        add_section("关键事实", [f"- {_clean_text(item, limit=700)}" for item in list(answer_material.keyFacts or [])[:12] if _clean_text(item, limit=700)], "keyFacts")
        add_section("结构化线索", [f"- {_clean_text(item, limit=700)}" for item in list(answer_material.structuredPoints or [])[:12] if _clean_text(item, limit=700)], "structuredPoints")
        add_section("精选原文与证据片段", collect_items(list(answer_material.evidenceHighlights or []), source_key="evidenceHighlights", limit=24, body_limit=1600), "evidenceHighlights")
        add_section("下一步线索", [f"- {_clean_text(item, limit=500)}" for item in list(answer_material.nextActions or [])[:8] if _clean_text(item, limit=500)], "nextActions")

    if workspace_snapshot is not None:
        add_section(
            "客户工作台高信号文档",
            collect_items(
                list(workspace_snapshot.documents or []),
                source_key="workspaceDocuments",
                title_fields=("title", "fileName", "path"),
                body_fields=("excerpt", "summary", "markdownContent"),
                limit=14,
                body_limit=1200,
                high_signal_only=True,
            ),
            "workspaceDocuments",
        )
        add_section(
            "项目结构与业务线",
            collect_items(
                list(workspace_snapshot.projectModules or []) + list(workspace_snapshot.projectFlows or []),
                source_key="projectStructure",
                title_fields=("title", "name", "label"),
                body_fields=("summary", "description", "content", "status"),
                limit=12,
                body_limit=900,
            ),
            "projectStructure",
        )
        add_section(
            "工作台近期任务",
            collect_items(
                list(workspace_snapshot.relatedTasks or []),
                source_key="workspaceTasks",
                title_fields=("title", "name"),
                body_fields=("summary", "description", "status", "notes"),
                limit=8,
                body_limit=800,
            ),
            "workspaceTasks",
        )

    content = "\n\n".join(section for section in sections if section.strip()).strip()
    if len(content) > max_chars:
        content = content[: max_chars - 1].rstrip() + "…"
    return ConsultantSynthesisMaterialPack(
        content=content,
        source_counts=source_counts,
        excluded_noise_count=excluded_noise_count,
        boundary_notes=boundary_notes,
        context_chars=len(content),
    )


def build_action_advisory_material_pack(
    *,
    prompt: str,
    kernel_result: DataCenterKernelResultRecord,
    workspace_snapshot: ClientWorkspaceResponse | None,
    answer_perspective: str,
    perspective_source: str,
    max_chars: int = 26000,
) -> ActionAdvisoryMaterialPack:
    page_context = kernel_result.pageContext
    answer_material = kernel_result.answerMaterial
    source_counts: dict[str, int] = {}
    sections: list[str] = []

    def add_section(title: str, lines: list[str], source_key: str) -> None:
        cleaned = [line for line in lines if str(line).strip()]
        if not cleaned:
            return
        source_counts[source_key] = source_counts.get(source_key, 0) + len(cleaned)
        sections.append(f"【{title}】\n" + "\n".join(cleaned))

    def collect_items(
        items: list[object],
        *,
        source_key: str,
        title_fields: tuple[str, ...] = ("title", "name", "label", "fileName"),
        body_fields: tuple[str, ...] = ("summary", "excerpt", "content", "text", "description", "rationale", "statement", "nextAction", "status"),
        limit: int = 8,
        body_limit: int = 800,
    ) -> list[str]:
        lines: list[str] = []
        for item in items:
            line, is_noise = _format_consultant_item(
                item,
                title_fields=title_fields,
                body_fields=body_fields,
                body_limit=body_limit,
            )
            if is_noise:
                continue
            if line and line not in lines:
                lines.append(line)
            if len(lines) >= limit:
                break
        return lines

    perspective_guidance = {
        "individual": "默认按用户本人下一步如何推进来组织回答，聚焦用户可以推动的沟通、资料补齐、判断确认和下一步动作。",
        "team": "默认按团队或部门负责人视角组织回答，聚焦团队分工、协作节奏、责任节点、能力补齐和推进优先级。",
        "organization": "默认按机构负责人视角组织回答，聚焦组织级取舍、战略落地、业务结构、资源配置、风险和关键决策。",
        "project": "默认按项目负责人视角组织回答，聚焦项目路径、交付闭环、试点、资料补齐、关键责任和风险。",
        "meeting_followup": "默认按会后跟进视角组织回答，聚焦会议共识、责任人、时间节点、待澄清问题和下一轮沟通。",
    }.get(str(answer_perspective or ""), "默认按用户本人下一步如何推进来组织回答。")

    sections.append(
        "\n".join(
            [
                "【用户问题】",
                _clean_text(prompt, limit=1000),
                "",
                "【行动回答视角】",
                f"- answerPerspective：{answer_perspective or 'individual'}",
                f"- perspectiveSource：{perspective_source or 'fallback_default'}",
                f"- 生成要求：{perspective_guidance}",
                "- 正文不要解释回答视角，不要列出个人/部门/机构分类，直接给出自然的下一步判断。",
            ]
        ).strip()
    )

    client_lines: list[str] = []
    if workspace_snapshot is not None and workspace_snapshot.client is not None:
        client = workspace_snapshot.client
        client_lines.append(f"- 客户名称：{_clean_text(getattr(client, 'name', ''), limit=120) or '当前客户'}")
        client_stage = _clean_text(getattr(client, "stage", ""), limit=120)
        client_summary = _clean_text(getattr(client, "summary", ""), limit=700)
        if client_stage:
            client_lines.append(f"- 当前阶段：{client_stage}")
        if client_summary:
            client_lines.append(f"- 客户摘要：{client_summary}")
    add_section("客户基础信息", client_lines, "clientBasics")
    dna_tool_context = build_dna_tool_context_from_workspace(
        workspace_snapshot,
        prompt=prompt,
        purpose="task_next_action",
        max_chars=12000,
    )
    if dna_tool_context.context_text:
        source_counts["clientDnaTool"] = max(1, len(dna_tool_context.selected_modules))
        sections.append(dna_tool_context.context_text)

    boundary_notes: list[str] = []
    if page_context is not None:
        boundary_notes = [
            _clean_text(item, limit=260)
            for item in list(page_context.boundaryNotes or [])[:8]
            if _clean_text(item, limit=260)
        ]
        missing_context = [
            _clean_text(item, limit=260)
            for item in list(page_context.missingContext or [])[:8]
            if _clean_text(item, limit=260)
        ]
        add_section("最近会议与共识", collect_items(list(page_context.relatedMeetings or []), source_key="relatedMeetings", limit=8), "relatedMeetings")
        add_section("当前任务与责任线索", collect_items(list(page_context.relatedTasks or []), source_key="relatedTasks", limit=10), "relatedTasks")
        add_section("开放问题", [f"- {item}" for item in missing_context[:6]], "missingContext")
        add_section("风险与边界", [f"- {item}" for item in boundary_notes[:6]], "boundaryNotes")
        add_section("候选判断与待确认洞察", collect_items(list(page_context.candidateJudgments or []), source_key="candidateJudgments", limit=8), "candidateJudgments")
        add_section("正式判断", collect_items(list(page_context.officialJudgments or []), source_key="officialJudgments", limit=8), "officialJudgments")
        add_section("统一记忆", [f"- {_clean_text(item, limit=500)}" for item in list(page_context.memoryFacts or [])[:10] if _clean_text(item, limit=500)], "memoryFacts")
        add_section("战略与原文支撑", collect_items(list(page_context.rawEvidence or []), source_key="rawEvidence", limit=12, body_limit=1100), "rawEvidence")

    if answer_material is not None:
        add_section("下一步线索", [f"- {_clean_text(item, limit=500)}" for item in list(answer_material.nextActions or [])[:10] if _clean_text(item, limit=500)], "nextActions")
        add_section("关键事实", [f"- {_clean_text(item, limit=650)}" for item in list(answer_material.keyFacts or [])[:10] if _clean_text(item, limit=650)], "keyFacts")
        add_section("结构化线索", [f"- {_clean_text(item, limit=650)}" for item in list(answer_material.structuredPoints or [])[:10] if _clean_text(item, limit=650)], "structuredPoints")
        add_section("精选证据片段", collect_items(list(answer_material.evidenceHighlights or []), source_key="evidenceHighlights", limit=14, body_limit=1200), "evidenceHighlights")

    if workspace_snapshot is not None:
        add_section(
            "项目结构与业务线",
            collect_items(
                list(workspace_snapshot.projectModules or []) + list(workspace_snapshot.projectFlows or []),
                source_key="projectStructure",
                title_fields=("title", "name", "label"),
                body_fields=("summary", "description", "content", "status", "nextAction"),
                limit=10,
            ),
            "projectStructure",
        )
        add_section(
            "工作台近期任务",
            collect_items(
                list(workspace_snapshot.relatedTasks or []),
                source_key="workspaceTasks",
                title_fields=("title", "name"),
                body_fields=("summary", "description", "status", "notes", "nextAction"),
                limit=10,
            ),
            "workspaceTasks",
        )

    content = "\n\n".join(section for section in sections if section.strip()).strip()
    if len(content) > max_chars:
        content = content[: max_chars - 1].rstrip() + "…"
    return ActionAdvisoryMaterialPack(
        content=content,
        source_counts=source_counts,
        boundary_notes=boundary_notes,
        context_chars=len(content),
    )


def build_workspace_context_quality_summary(
    page_context: PageContextPackRecord | None,
    quality: Any | None,
) -> dict[str, object]:
    resolved_quality = quality or (page_context.quality if page_context is not None else None)
    official_count = len(page_context.officialJudgments) if page_context is not None else 0
    candidate_count = len(page_context.candidateJudgments) if page_context is not None else 0
    open_question_count = len(page_context.openQuestions) if page_context is not None else 0
    conflict_count = len(page_context.conflicts) if page_context is not None else 0
    task_count = len(page_context.relatedTasks) if page_context is not None else 0
    meeting_count = len(page_context.relatedMeetings) if page_context is not None else 0
    related_document_count = len(page_context.relatedDocuments) if page_context is not None else 0
    missing_context_count = len(page_context.missingContext) if page_context is not None else 0
    context_quality = str(getattr(resolved_quality, "contextQuality", "none") or "none")
    return {
        "contextQuality": context_quality,
        "officialJudgmentCount": int(getattr(resolved_quality, "approvedJudgmentCount", official_count) or official_count),
        "candidateJudgmentCount": int(getattr(resolved_quality, "candidateJudgmentCount", candidate_count) or candidate_count),
        "openQuestionCount": int(getattr(resolved_quality, "openQuestionCount", open_question_count) or open_question_count),
        "conflictCount": conflict_count,
        "relatedTaskCount": int(getattr(resolved_quality, "taskCount", task_count) or task_count),
        "relatedMeetingCount": int(getattr(resolved_quality, "meetingCount", meeting_count) or meeting_count),
        "relatedDocumentCount": related_document_count,
        "missingContextCount": missing_context_count,
    }


def build_open_workspace_answer_context(
    *,
    prompt: str,
    kernel_result: DataCenterKernelResultRecord,
    workspace_snapshot: ClientWorkspaceResponse | None,
    max_chars: int = 100000,
    question_focus_frame: dict[str, object] | None = None,
    profile_draft: str | None = None,
    dna_tool_context: DnaToolContextRecord | None = None,
) -> str:
    page_context = kernel_result.pageContext
    answer_material = kernel_result.answerMaterial
    client_name = ""
    if workspace_snapshot is not None and workspace_snapshot.client is not None:
        client_name = str(workspace_snapshot.client.name or "").strip()
    if not client_name and page_context is not None and page_context.clientId:
        client_name = str(page_context.clientId)
    client_label = client_name or "当前客户"

    def _is_noise_doc(*, title: str, excerpt: str, path: str, source_type: str, section_label: str) -> bool:
        quality = classify_evidence_quality_fields(
            title=title,
            excerpt=excerpt,
            source_type=source_type,
            section_label=section_label,
            path=path,
            retrieval_stage="raw_chunk",
        )
        normalized = _clean_text(f"{title} {path} {excerpt}", limit=2400).lower()
        if any(token in normalized for token in ("说明.txt", "整理说明", "重复件已移至废纸篓")):
            return True
        if quality.isNoise and quality.sourceKind in {"ppt_visual", "ppt_master", "template_page", "short_excerpt"}:
            return True
        return False

    document_sections: list[str] = []
    if answer_material is not None:
        evidence_highlights = _list_value(_field_value(answer_material, "evidenceHighlights"))
        grouped: dict[str, dict[str, object]] = {}
        # P2.14 FREEZE(answer-shaping-document-pack-window): 旧 raw_document_pack 的窗口限制已冻结。
        # P2.15 V2(answer-reading-pack-window): workspace/chat 主链已切到 family-first 的 raw_reading_pack_v2。
        for item in evidence_highlights:
            title = _clean_text(_field_value(item, "title"), limit=200) or "资料"
            excerpt = _clean_text(_field_value(item, "excerpt"), limit=2400)
            path = _clean_text(_field_value(item, "path"), limit=360)
            section_label = _clean_text(_field_value(item, "sectionLabel"), limit=120)
            source_type = _clean_text(_field_value(item, "sourceType"), limit=60)
            document_id = _clean_text(_field_value(item, "documentId"), limit=120)
            document_family_id = _clean_text(_field_value(item, "documentFamilyId"), limit=160)
            canonical_kind = _clean_text(_field_value(item, "canonicalKind"), limit=60) or "raw_file"
            if not excerpt:
                continue
            if _is_noise_doc(
                title=title,
                excerpt=excerpt,
                path=path,
                source_type=source_type,
                section_label=section_label,
            ):
                continue
            group_key = document_family_id or document_id or path or title
            if not group_key:
                continue
            bucket = grouped.setdefault(
                group_key,
                {
                    "title": title,
                    "path": path,
                    "sourceType": source_type,
                    "canonicalKind": canonical_kind,
                    "documentFamilyId": document_family_id,
                    "segments": [],
                },
            )
            segments = bucket["segments"]
            if not isinstance(segments, list):
                continue
            segment_text = f"{section_label}：{excerpt}" if section_label else excerpt
            if segment_text in segments:
                continue
            if len(segments) >= 3:
                continue
            segments.append(segment_text)

        total_segments = 0
        for index, bucket in enumerate(list(grouped.values())[:12], start=1):
            segments = bucket.get("segments") if isinstance(bucket, dict) else None
            if not isinstance(segments, list) or not segments:
                continue
            if total_segments >= 24:
                break
            segments_for_doc = segments[: max(0, min(3, 24 - total_segments))]
            if not segments_for_doc:
                continue
            lines = [f"[文档 {index}]", f"标题：{str(bucket.get('title') or '资料').strip()}"]
            canonical_kind = str(bucket.get("canonicalKind") or "").strip()
            document_family_id = str(bucket.get("documentFamilyId") or "").strip()
            source_type = str(bucket.get("sourceType") or "").strip()
            path = str(bucket.get("path") or "").strip()
            if canonical_kind:
                lines.append(f"文档类型：{canonical_kind}")
            if document_family_id:
                lines.append(f"文档家族：{document_family_id}")
            if source_type:
                lines.append(f"类型：{source_type}")
            if path:
                lines.append(f"路径：{path}")
            for seg_index, segment in enumerate(segments_for_doc, start=1):
                lines.append(f"片段 {seg_index}：{str(segment).strip()}")
            total_segments += len(segments_for_doc)
            document_sections.append("\n".join(lines).strip())

    resolved_dna_tool_context = dna_tool_context or build_dna_tool_context_from_workspace(
        workspace_snapshot,
        prompt=prompt,
        max_chars=22000,
    )
    # P0 背景包：所有 workflow 主回答的固定画像底色（客户档案 + 核心判断 + 当前推进 + 矛盾）。
    # 区别于 build_dna_tool_context（工具调用 / 业务-组织-品牌细节），背景包是"当前状态"。
    background_pack = build_workspace_background_pack(workspace_snapshot)
    sections: list[str] = [
        "\n".join(
            [
                "【用户问题】",
                prompt.strip(),
                "",
                "【回答原则】",
                "你是这家组织的资深陪伴顾问。下面的「背景包」是你已经知道的事实清单——客户档案、已确认判断、活跃项目模块、近期会议、活跃任务、目标、矛盾、待澄清问题。不需要再从资料里确认这些。",
                "把背景包当作组织画像的地图，但回答的具体性必须从「原始阅读资料包」里挖出来：具体的项目名、合作方、活动名、数字、时间节点、决议、人物角色，这些是背景包没列出来的，需要你深入文档片段去找。",
                "不要满足于在画像层面做抽象总结。一份合格的答案要能让读者看到具体在做什么、跟谁做、什么时候做、做到什么程度——这些细节都在资料里。",
                '给出有判断的结论而非中立陈述；明确标示三种信息来源：「资料明示的」「背景包已有判断」「基于全局推断的」，让读者知道每个论断的来历。',
                "不要编造资料和背景包之外的硬事实。可以自由组织结构和长度；不要暴露系统过程或检索细节。",
            ]
        ).strip(),
        f"【客户】\n{client_label}",
    ]
    if background_pack:
        sections.append(background_pack)
    if resolved_dna_tool_context.context_text:
        sections.append(resolved_dna_tool_context.context_text)
    sections.append("【原始阅读资料包 v2】\n" + "\n\n".join(document_sections or ["当前没有可用的文档原文片段。"]))

    content = "\n\n".join(section for section in sections if section.strip()).strip()
    # P2.14 FREEZE(answer-shaping-context-max-chars): 单包上下文仍然受 max_chars 截断。
    # 这是旧塑形半层的最后一道硬边界，先冻结为待拆层。
    if len(content) <= max_chars:
        return content
    return content[: max_chars - 1].rstrip() + "…"


def _resolve_open_workspace_answer_intent(kernel_result: DataCenterKernelResultRecord) -> str | None:
    answer_plan = getattr(kernel_result, "answerPlan", None)
    if answer_plan is not None:
        intent = str(getattr(answer_plan, "intent", "") or "").strip()
        if intent and intent != "general":
            return intent
    route_decision = getattr(kernel_result, "routeDecision", None)
    if route_decision is not None:
        intent = str(getattr(route_decision, "intent", "") or "").strip()
        if intent and intent != "general":
            return intent
    page_context = getattr(kernel_result, "pageContext", None)
    if page_context is not None:
        intent = str(getattr(page_context, "intent", "") or "").strip()
        if intent and intent != "general":
            return intent
    return None


def build_workspace_dc_response_meta(
    *,
    kernel_result: DataCenterKernelResultRecord,
    answer_intent: WorkspaceAnswerIntent,
    retrieval_decision_reason: ChatRetrievalDecisionReason,
    data_center_primary_enabled: bool,
    legacy_intent: WorkspaceAnswerIntent,
    legacy_retrieval_reason: ChatRetrievalDecisionReason,
    llm_attempt_count: int,
    compact_retry_attempted: bool,
    fallback_template_used: bool,
    final_failure_stage: str | None,
    route_decision_source: str,
    answer_mode: str,
    evidence_status: str,
    failure_reason: str | None,
    fallback_presentation_mode: str,
    should_run_retrieval: bool,
    state_confidence: str,
    state_sources: list[str],
    state_answer_sections: dict[str, Any],
    state_source_summary: dict[str, int],
    total_elapsed_ms: float,
    retrieval_elapsed_ms: float,
    llm_elapsed_ms: float,
    answer_quality: dict[str, object],
    quality_gate_warned: bool,
    generation_policy: dict[str, object],
    llm_error_kind: str | None = None,
    generation_profile: str | None = None,
    partial_generation_preserved: bool = False,
    source_integrity_match: bool | None = None,
    workspace_workflow: str | None = None,
    workspace_generation_mode: str | None = None,
    workspace_route: dict[str, object] | None = None,
    primary_sources: list[str] | None = None,
    preview_summary: str | None = None,
    work_trace: dict[str, Any] | None = None,
    master_hit_count: int = 0,
    surrogate_hit_count: int = 0,
    raw_chunk_hit_count: int = 0,
    material_access_mode: str | None = None,
    suggested_followups: list[str] | None = None,
    followup_scenario: str | None = None,
    followup_generation_mode: str | None = None,
    followup_rejected_count: int = 0,
    material_pack_profile: str | None = None,
    material_pack_source_counts: dict[str, int] | None = None,
    excluded_noise_count: int = 0,
    consultant_context_chars: int = 0,
    consultant_boundary_notes: list[str] | None = None,
    answer_perspective: str | None = None,
    perspective_source: str | None = None,
    action_advisory_source_counts: dict[str, int] | None = None,
) -> dict[str, object]:
    normalized_material_access_mode = str(material_access_mode or "").strip()
    if normalized_material_access_mode == "raw_document_pack":
        raise ValueError("raw_document_pack has been removed from workspace/chat main answers; use raw_reading_pack_v2")
    page_context = kernel_result.pageContext
    quality_summary = build_workspace_context_quality_summary(page_context, kernel_result.quality)
    route_decision = _json_object(kernel_result.routeDecision) if kernel_result.routeDecision else {}
    retrieval_trace = _json_object(kernel_result.retrievalTrace) if kernel_result.retrievalTrace else {}
    answer_plan = _json_object(kernel_result.answerPlan) if kernel_result.answerPlan else {}
    answer_material = kernel_result.answerMaterial
    key_facts = _list_value(_field_value(answer_material, "keyFacts")) if answer_material else []
    evidence_highlights = _list_value(_field_value(answer_material, "evidenceHighlights")) if answer_material else []
    missing_context_material = _list_value(_field_value(answer_material, "missingContext")) if answer_material else []
    boundary_notes_material = _list_value(_field_value(answer_material, "boundaryNotes")) if answer_material else []
    source_labels = [
        str(item)
        for item in _list_value(_field_value(answer_material, "sourceLabels"))[:12]
        if str(item).strip()
    ] if answer_material else []
    material_summary = {
        "keyFactCount": len(key_facts),
        "evidenceHighlightCount": len(evidence_highlights),
        "missingContextCount": len(missing_context_material),
        "boundaryNoteCount": len(boundary_notes_material),
        "sourceLabels": source_labels,
    }
    missing_context = list(page_context.missingContext[:10]) if page_context is not None else []
    boundary_notes = list(page_context.boundaryNotes[:10]) if page_context is not None else []
    kernel_debug = kernel_result.debug if isinstance(kernel_result.debug, dict) else {}
    kernel_profiling = kernel_debug.get("profiling")
    reading_pass_count = int(retrieval_trace.get("readingPassCount") or 0)
    selected_document_family_count = int(retrieval_trace.get("selectedDocumentFamilyCount") or 0)
    selected_canonical_kinds = [
        str(item)
        for item in _list_value(retrieval_trace.get("selectedCanonicalKinds"))[:12]
        if str(item).strip()
    ]
    software_material_included = bool(retrieval_trace.get("softwareMaterialIncluded"))
    reading_meta_only = normalized_material_access_mode == "raw_reading_pack_v2"
    sanitized_state_sources = [] if reading_meta_only else state_sources
    sanitized_state_answer_sections = {} if reading_meta_only else state_answer_sections
    sanitized_state_source_summary = {} if reading_meta_only else state_source_summary
    sanitized_preview_summary = "" if reading_meta_only else str(preview_summary or "").strip()
    sanitized_work_trace = {} if reading_meta_only else dict(work_trace or {})
    return {
        "kernelResultUsed": True,
        "dataCenterPrimaryEnabled": data_center_primary_enabled,
        "legacyIntent": legacy_intent,
        "legacyRetrievalReason": legacy_retrieval_reason,
        "llmAttemptCount": llm_attempt_count,
        "compactRetryAttempted": compact_retry_attempted,
        "fallbackTemplateUsed": fallback_template_used,
        "finalFailureStage": final_failure_stage,
        "routeDecisionSource": route_decision_source,
        "answerMode": answer_mode,
        "answerIntent": answer_intent,
        "evidenceStatus": evidence_status,
        "failureReason": failure_reason,
        "retrievalDecisionReason": retrieval_decision_reason,
        "retrievalDeferred": not should_run_retrieval,
        "shouldRunRetrieval": should_run_retrieval,
        "fallbackPresentationMode": fallback_presentation_mode,
        "stateConfidence": state_confidence,
        "stateSources": sanitized_state_sources,
        "stateAnswerSections": sanitized_state_answer_sections,
        "stateSourceSummary": sanitized_state_source_summary,
        "boundaryNotes": boundary_notes,
        "missingContext": missing_context,
        "contextQuality": quality_summary,
        "pageContextQuality": quality_summary.get("contextQuality"),
        "stateObjectCount": int(getattr(kernel_result.quality, "stateObjectCount", 0) or 0),
        "routeDecision": route_decision,
        "retrievalTrace": retrieval_trace,
        "answerPlan": answer_plan,
        "answerMaterialSummary": material_summary,
        "answerQuality": answer_quality,
        "qualityGateWarned": quality_gate_warned,
        "generationPolicy": generation_policy,
        "llmErrorKind": llm_error_kind,
        "generationProfile": generation_profile,
        "materialAccessMode": normalized_material_access_mode or None,
        "sourceLabels": source_labels,
        "readingPassCount": reading_pass_count,
        "selectedDocumentFamilyCount": selected_document_family_count,
        "selectedCanonicalKinds": selected_canonical_kinds,
        "softwareMaterialIncluded": software_material_included,
        "partialGenerationPreserved": partial_generation_preserved,
        "sourceIntegrityMatch": source_integrity_match,
        "workspaceWorkflow": workspace_workflow,
        "generationMode": workspace_generation_mode,
        "workspaceRoute": workspace_route or {},
        "primarySources": list(primary_sources or []),
        "previewSummary": sanitized_preview_summary,
        "workTrace": sanitized_work_trace,
        "masterHitCount": int(master_hit_count or 0),
        "surrogateHitCount": int(surrogate_hit_count or 0),
        "rawChunkHitCount": int(raw_chunk_hit_count or 0),
        "actionSuggestions": [
            payload
            for item in kernel_result.actionSuggestions[:8]
            if (payload := _json_object(item))
        ],
        "proposalDrafts": [
            payload
            for item in kernel_result.proposalDrafts[:8]
            if (payload := _json_object(item))
        ],
        "searchResult": _json_object(kernel_result.searchResult) if kernel_result.searchResult else None,
        "suggestedFollowups": [str(item) for item in (suggested_followups or [])[:3] if str(item).strip()],
        "followupScenario": str(followup_scenario or "").strip() or None,
        "followupGenerationMode": str(followup_generation_mode or "").strip() or None,
        "followupRejectedCount": int(followup_rejected_count or 0),
        "materialPackProfile": str(material_pack_profile or "").strip() or None,
        "materialPackSourceCounts": dict(material_pack_source_counts or {}),
        "actionAdvisorySourceCounts": dict(action_advisory_source_counts or {}),
        "answerPerspective": str(answer_perspective or "").strip() or None,
        "perspectiveSource": str(perspective_source or "").strip() or None,
        "excludedNoiseCount": int(excluded_noise_count or 0),
        "consultantContextChars": int(consultant_context_chars or 0),
        "consultantBoundaryNotes": [str(item) for item in (consultant_boundary_notes or [])[:8] if str(item).strip()],
        "kernelProfiling": kernel_profiling if isinstance(kernel_profiling, dict) else {},
        "questionFocusFrame": _json_object(kernel_debug.get("questionFocusFrame")),
        "evidenceDecisionTrace": _list_value(kernel_debug.get("evidenceDecisionTrace"))[:16],
        "selectedEvidenceRoles": [str(item) for item in _list_value(kernel_debug.get("selectedEvidenceRoles"))[:10] if str(item).strip()],
        "sourceReachability": _json_object(kernel_debug.get("sourceReachability")),
        "unselectedHighPrioritySources": _list_value(kernel_debug.get("unselectedHighPrioritySources"))[:10],
        "priorityParseFailures": _list_value(kernel_debug.get("priorityParseFailures"))[:8],
        "supportOnlySources": _list_value(kernel_debug.get("supportOnlySources"))[:8],
        "timing": {
            "totalMs": total_elapsed_ms,
            "retrievalMs": retrieval_elapsed_ms,
            "llmMs": llm_elapsed_ms,
        },
    }
