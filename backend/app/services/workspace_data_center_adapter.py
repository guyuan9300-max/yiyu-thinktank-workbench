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
    max_chars: int = 6000,
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
            goal = _short_label(getattr(module, "goal", ""), limit=120)
            owner = _short_label(getattr(module, "ownerName", ""), limit=40)
            extras = "；".join(p for p in (goal, f"负责人={owner}" if owner else "") if p)
            module_lines.append(f"- {name}" + (f"（{extras}）" if extras else ""))
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
            task_lines.append(
                f"- {title}"
                + (f" [{status}]" if status else "")
                + (f" / 截止 {due}" if due else "")
                + (f" / {owner}" if owner else "")
            )
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
        max_chars=4000,
        judgment_limit=4,
        meeting_limit=2,
        task_limit=3,
        project_module_limit=3,
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
                "你是这家组织的资深陪伴顾问；先在心里建立对这家组织的当前画像（基于背景包），再在画像里定位用户的问题。",
                '回答时给出有判断的结论，而不是中立陈述；明确区分"资料明示的"与"基于背景推断的"。',
                "只基于提供资料和背景包推断，不要编造资料之外的硬事实。",
                "可以自由组织结构和长度；不要暴露系统过程或检索细节。",
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
