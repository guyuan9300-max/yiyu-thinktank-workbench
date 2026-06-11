from __future__ import annotations

import re
from typing import Any

from app.models import SemanticSourceRole


_NOISE_HINTS = (
    "clicktoeditmaster",
    "母版",
    "模板",
    "模板页",
    "目录页",
    "封面",
    "页脚",
    "页码",
    "视觉",
    "背景图",
)
_GENERATED_HINTS = ("historyanswer", "历史回答", "生成稿", "草稿", "chat_", "answer_")
_PROFILE_ANCHOR_HINTS = (
    "机构介绍",
    "组织介绍",
    "业务介绍",
    "项目介绍",
    "项目资助申请书",
    "资助申请书",
    "使命愿景",
    "价值观",
    "核心观点总结",
    "工作坊核心观点",
    "战略蓝图",
    "战略结构",
    "战略核心思想",
)


def _norm(value: str | None) -> str:
    return re.sub(r"\s+", "", str(value or "").lower())


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def infer_semantic_source_roles_fields(
    *,
    title: str = "",
    excerpt: str = "",
    source_type: str = "",
    section_label: str = "",
    retrieval_stage: str = "",
    path: str = "",
    visible_category: str = "",
    secondary_category: str = "",
    material_layer: str = "",
) -> tuple[list[SemanticSourceRole], list[str]]:
    title_norm = _norm(title)
    excerpt_norm = _norm(excerpt)
    path_norm = _norm(path)
    source_type_norm = _norm(source_type)
    merged = _norm(
        " ".join(
            [
                title,
                excerpt,
                source_type,
                section_label,
                retrieval_stage,
                path,
                visible_category,
                secondary_category,
                material_layer,
            ]
        )
    )
    roles: list[SemanticSourceRole] = []
    reasons: list[str] = []

    def _add(role: SemanticSourceRole, reason: str) -> None:
        if role not in roles:
            roles.append(role)
        if reason not in reasons:
            reasons.append(reason)

    is_support_path = "/_imports/" in str(path or "") or _contains_any(merged, ("_imports",))
    is_operational = _contains_any(
        merged,
        (
            "会议纪要",
            "沟通纪要",
            "进度",
            "推进",
            "同步",
            "对齐",
            "筹备",
            "跟进",
            "完成",
            "下周",
            "本周",
            "一季度",
            "二季度",
            "季度",
            "联调",
        ),
    ) or "meeting" in source_type_norm
    if is_support_path:
        _add("derived_profile_support", "support_path:_imports")

    if _contains_any(title_norm + path_norm, _PROFILE_ANCHOR_HINTS):
        _add("institution_identity", "profile_anchor:title_or_path")

    # P2.12 FREEZE(source-semantics): 这里的语义角色规则当前是介绍类回答的底层入口。
    # 它们会直接改变“哪些资料被视为机构画像/方法/业务线材料”，先冻结。
    strong_identity_signal = _contains_any(
        excerpt_norm,
        (
            "机构介绍",
            "组织介绍",
            "申请机构",
            "机构背景",
            "关于我们",
            "使命",
            "愿景",
            "价值观",
            "定位",
            "测试机构A",
            "是一家",
        ),
    ) or _contains_any(title_norm, ("机构介绍", "组织介绍", "使命", "愿景", "价值观", "申请书"))
    if strong_identity_signal:
        _add("institution_identity", "identity_terms")

    if _contains_any(
        excerpt_norm,
        (
            "问题",
            "困境",
            "挑战",
            "需求",
            "焦虑",
            "孤独",
            "支持资源不足",
            "结构性",
            "根源",
            "为什么要做",
        ),
    ):
        _add("problem_definition", "problem_terms")

    strong_program_signal = _contains_any(
        excerpt_norm,
        (
            "业务",
            "业务线",
            "项目介绍",
            "课程",
            "学院",
            "测试项目C",
            "测试项目A",
            "繁星计划",
            "教师赋能",
            "教师发展中心",
            "服务对象",
            "教育公益项目",
            "主要项目",
        ),
    ) or _contains_any(title_norm, ("项目介绍", "资助申请书", "测试项目C", "教师发展中心", "测试项目A", "繁星计划"))
    if strong_program_signal and (not is_operational or _contains_any(title_norm, ("项目介绍", "资助申请书"))):
        _add("program_overview", "program_terms")

    if _contains_any(
        excerpt_norm,
        (
            "方法",
            "模型",
            "路径",
            "工具包",
            "脚本",
            "课程结构",
            "可复制",
            "交付模式",
            "机制",
            "生态协作",
            "场域",
            "工作坊",
            "基础设施",
            "数字化",
        ),
    ) or _contains_any(title_norm, ("工作坊核心观点", "方法", "模型", "路径")):
        _add("method_or_model", "method_terms")

    strong_strategy_signal = _contains_any(
        excerpt_norm,
        (
            "战略",
            "战略目标",
            "方向",
            "蓝图",
            "第二曲线",
            "飞轮",
            "升级",
            "复利",
            "增长",
            "未来",
            "资产",
            "数字价值",
            "韧性",
        ),
    ) or _contains_any(title_norm, ("战略结构", "战略核心思想", "战略蓝图", "飞轮", "第二曲线", "复利增长", "数字价值"))
    if strong_strategy_signal and (not is_operational or _contains_any(title_norm, ("战略结构", "战略核心思想", "战略蓝图", "飞轮", "第二曲线"))):
        _add("strategy_direction", "strategy_terms")

    if is_operational:
        _add("operational_update", "operational_terms")

    if _contains_any(
        excerpt_norm,
        (
            "风险",
            "待确认",
            "开放问题",
            "未决",
            "卡点",
            "阻塞",
            "挑战",
            "问题清单",
        ),
    ):
        _add("risk_or_open_issue", "risk_terms")

    if _contains_any(
        excerpt_norm,
        (
            "财务",
            "预算",
            "审计",
            "报销",
            "付款",
            "税",
            "资助额",
        ),
    ):
        _add("financial_or_admin", "financial_terms")

    if _contains_any(title_norm + excerpt_norm + path_norm, _NOISE_HINTS) or _contains_any(title_norm + excerpt_norm + path_norm, _GENERATED_HINTS):
        _add("noise_or_template", "noise_or_generated_terms")

    return roles, reasons


def infer_semantic_source_roles_payload(payload: dict[str, Any]) -> tuple[list[SemanticSourceRole], list[str]]:
    return infer_semantic_source_roles_fields(
        title=str(payload.get("title") or payload.get("file_name") or ""),
        excerpt=str(payload.get("excerpt") or payload.get("preview_text") or payload.get("retrievalSummary") or ""),
        source_type=str(payload.get("sourceType") or payload.get("source_type") or ""),
        section_label=str(payload.get("sectionLabel") or payload.get("section_label") or ""),
        retrieval_stage=str(payload.get("retrievalStage") or payload.get("sourceStage") or ""),
        path=str(payload.get("path") or payload.get("original_path") or payload.get("managed_path") or ""),
        visible_category=str(payload.get("visible_category") or payload.get("visibleCategory") or ""),
        secondary_category=str(payload.get("secondary_category") or payload.get("secondaryCategory") or ""),
        material_layer=str(payload.get("material_layer") or payload.get("materialLayer") or ""),
    )
