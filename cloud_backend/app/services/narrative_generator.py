"""6 维度叙事生成器 — 调云端豆包 LLM 生成 narrative + references + confidence.

设计要点 (服从 DNA 铁律):
  1. 真实数据支撑 (submodule:strategic_clarification_panel.decision):
     prompt 只喂 collector 收集的真实 facts, 不让 LLM 凭空编造;
     每条 reference 必须能指回真实 (sourceType, sourceId).
  2. 诚实暴露加工层缺口 (submodule:data_center processing_layer_gaps):
     当 facts 稀疏时, LLM 必须在对应维度返回 confidence=low + dataLayerGap;
     不允许"看上去丰满但全是猜的"输出.
  3. 用户判断节奏 (principle:user_judgment_pace):
     LLM 失败时降级到 stub (拼澄清原文), 而不是阻塞 — 让用户先看到 UI.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict
from typing import Any

import httpx

from app.db import Database
from app.services import client_narrative as narrative_svc
from app.services.narrative_collector import (
    ClientContext,
    EventLineActivityFact,
    EventLineFact,
    TaskFact,
    collect_client_context,
)


DIMENSIONS = narrative_svc.DIMENSIONS  # ("essence", "people", ...)


# ============================================================
# Prompt 构造
# ============================================================

DIMENSION_BRIEF = {
    "essence": (
        "项目本质 — 用 2-4 句话讲: 这家客户是谁 / 体量 / 来找益语做什么类型的项目 "
        "(培训/咨询/落地/续约/方案) / 客户对成功的定义 / 当前阶段 / 边界. "
        "structured_profile 缺失时 confidence=low + dataLayerGap='client_strategic_profile 未填'."
    ),
    "cooperation": (
        "合作关系 — 益语与客户的合作形态: 合作起止时间 / 合作类型 (培训/咨询/落地/方案/续约) / "
        "合作深度与节奏 / 续约或扩展信号 / 客户侧决策链. cooperation_relationships 表为空时, "
        "尝试从 event_line.intent + structured_profile 推断, 标 confidence=low + "
        "dataLayerGap='cooperation_relationships 未建'."
    ),
    "business_intro": (
        "业务介绍 — 客户机构主营业务 / 行业定位 / 旗下含项目列表 / 与本项目的关系. "
        "external_persons 的 affiliation 字段 + understanding_payload 的 entities (org/product) "
        "是主要素材. 没素材时 confidence=low + dataLayerGap='机构画像未抽取'."
    ),
    "people": (
        "关键人物网 — 列出客户方关键人物 (姓名+职务+在项目里的角色: 决策者/sponsor/经办/反对者/中立) "
        "+ 益语方分工 + 人物间关系 (信任/影响/矛盾). 没有花名册时只能列名字, 标 confidence=low."
    ),
    "timeline": (
        "时间线 — 用 5-8 个节点呈现: 项目怎么起来的 / 关键节点 (合同/启动会/关键交付/转折事件) / "
        "现在到了哪一步 / 下一步关键时刻. 强调 '关键' 转折, 不是流水账. "
        "event_line_activities + tasks(deadline) + v2_documents.imported_at 是主要素材."
    ),
    "next_steps": (
        "承诺与下一步 — 益语对客户的承诺 + 客户对益语的承诺 (含 deadline + 履约状态), "
        "再列出 1-2 周关键事 + 由谁负责 + 衡量进展的标志 + AI 推荐的下一步动作. "
        "标出履约风险高的承诺."
    ),
}

NARRATIVE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "essence": {"$ref": "#/$defs/dim"},
        "cooperation": {"$ref": "#/$defs/dim"},
        "business_intro": {"$ref": "#/$defs/dim"},
        "people": {"$ref": "#/$defs/dim"},
        "timeline": {"$ref": "#/$defs/dim"},
        "next_steps": {"$ref": "#/$defs/dim"},
        "overallConfidence": {"type": "number"},
    },
    "required": [
        "essence",
        "cooperation",
        "business_intro",
        "people",
        "timeline",
        "next_steps",
        "overallConfidence",
    ],
    "$defs": {
        "dim": {
            "type": "object",
            "properties": {
                "narrative": {"type": "string"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "confidenceReason": {"type": "string"},
                "references": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "sourceType": {"type": "string"},
                            "sourceId": {"type": "string"},
                            "label": {"type": "string"},
                            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                        },
                        "required": ["sourceType", "sourceId"],
                    },
                },
                "dataLayerGap": {"type": "string"},
                "openClarifications": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["narrative", "confidence"],
        }
    },
}


SYSTEM_PROMPT = (
    "你是益语智库战略陪伴模块的资深业务分析师。你的工作是基于数据中心已有事实, "
    "为某一家客户/项目生成 6 个维度的『故事网』, 让用户能 1 分钟内判断 AI 是否已经全面理解了这个业务。\n\n"
    "硬约束 (违反任何一条则失败):\n"
    "  - 只能基于下面提供的 facts 作叙述, 不能凭空编造任何事实/人名/日期/金额。\n"
    "  - 每段叙事的关键判断都必须在 references 里点回真实 source (sourceType+sourceId)。\n"
    "  - facts 稀疏时, 必须在对应维度返回 confidence=low + dataLayerGap (说明数据中心缺什么), "
    "    禁止用通用话术填满字数。\n"
    "  - openClarifications 是 AI 想跟用户澄清的具体业务问题 (不是字段缺失抱怨), "
    "    例如 '王强是正式接手老高的工作吗? 还是临时代管?'。\n"
    "  - 全部用中文, 自然语言, 不要 markdown 标记。\n"
    "  - 返回严格 JSON, 不要解释, 不要 ```json 包裹。\n"
)


def _format_event_line(el: EventLineFact) -> str:
    parts = [f"- id={el.id} | name={el.name} | stage={el.stage or '-'} | status={el.status}"]
    if el.intent:
        parts.append(f"  intent: {el.intent}")
    if el.summary:
        parts.append(f"  summary: {el.summary}")
    if el.current_blocker:
        parts.append(f"  blocker: {el.current_blocker}")
    if el.recent_decision:
        parts.append(f"  recent_decision: {el.recent_decision}")
    if el.next_step:
        parts.append(f"  next_step: {el.next_step}")
    return "\n".join(parts)


def _format_activity(act: EventLineActivityFact) -> str:
    return (
        f"- activityId={act.id} | {act.happened_at} | [{act.event_line_name}] {act.title}\n"
        f"  origin: sourceType={act.source_type}, sourceId={act.source_id}\n"
        f"  {act.summary}\n"
        f"  (引用时 sourceType=event_line_activity, sourceId={act.id})"
    )


def _format_task(t: TaskFact) -> str:
    parts = [
        f"- id={t.id} | title={t.title} | status={t.progress_status} | priority={t.priority}"
        + (f" | due={t.deadline_at}" if t.deadline_at else "")
    ]
    if t.next_action:
        parts.append(f"  next_action: {t.next_action}")
    if t.current_blocker:
        parts.append(f"  blocker: {t.current_blocker}")
    return "\n".join(parts)


def build_user_prompt(ctx: ClientContext) -> str:
    """把 ClientContext 拼成 LLM 输入. 故意只塞结构化关键字段, 不塞全文."""
    lines: list[str] = []
    lines.append(f"# 客户基本信息")
    lines.append(
        f"client_id={ctx.client_id} | name={ctx.client_name} | "
        f"alias={ctx.client_alias or '-'} | type={ctx.client_type}"
    )

    # 加工层 Phase 1 · 项目档案（结构化, 4 核心字段）—— 优先用这个
    if ctx.structured_profile:
        sp = ctx.structured_profile
        lines.append("\n# 项目档案 (cloud_client_strategic_profiles · 用户手填权威信息)")
        for k_zh, k in [
            ("项目类型", "project_type"),
            ("项目目标", "project_goal"),
            ("成功标准", "success_metric"),
            ("当前阶段", "current_phase"),
            ("合作起始", "cooperation_start_date"),
            ("合作结束", "cooperation_end_date"),
            ("补充备注", "notes"),
        ]:
            v = sp.get(k) or ""
            if v:
                lines.append(f"- {k_zh}: {v}")
        upd = sp.get("updated_by") or ""
        if upd:
            lines.append(f"- 最近更新人: {upd} @ {sp.get('updated_at') or ''}")
    elif ctx.strategic_profile:
        lines.append("\n# 战略画像 (cloud_client_workspace_snapshots 同步)")
        lines.append(json.dumps(ctx.strategic_profile, ensure_ascii=False, indent=2)[:1500])
    else:
        lines.append("\n# 项目档案: ⚠️ 无 (用户尚未在事实澄清面板填写项目类型/目标/成功标准/当前阶段)")

    # 加工层 Phase 1 · 关键人物花名册（结构化）—— 用户手填权威信息
    if ctx.external_persons:
        lines.append(f"\n# 关键人物花名册 (cloud_external_persons · 共 {len(ctx.external_persons)} 人, 用户手填)")
        for p in ctx.external_persons:
            bits = [p.name]
            if p.role_title:
                bits.append(f"职务={p.role_title}")
            if p.affiliation:
                bits.append(f"所属={p.affiliation}")
            if p.relationship_type:
                bits.append(f"关系类型={p.relationship_type}")
            if p.one_liner:
                bits.append(f"一句话={p.one_liner}")
            if p.notes:
                bits.append(f"备注={p.notes[:80]}")
            lines.append("- " + " | ".join(bits))
    else:
        lines.append("\n# 关键人物花名册: ⚠️ 无 (用户尚未在事实澄清面板录入关键人物)")

    if ctx.cooperation_payload:
        lines.append("\n# 合作关系 (cooperation_relationships)")
        lines.append(json.dumps(ctx.cooperation_payload, ensure_ascii=False, indent=2)[:1200])

    if ctx.understanding_payload:
        lines.append("\n# 客户理解快照 (client_understanding · entities/relations/atomic_facts)")
        lines.append(json.dumps(ctx.understanding_payload, ensure_ascii=False, indent=2)[:2000])

    lines.append(f"\n# 主线列表 (event_lines, 共 {len(ctx.event_lines)} 条)")
    if ctx.event_lines:
        lines.extend(_format_event_line(e) for e in ctx.event_lines)
    else:
        lines.append("⚠️ 无主线 (数据中心未关联或未建)")

    lines.append(f"\n# 主线流水 (event_line_activities, 共 {len(ctx.activities)} 条最近)")
    if ctx.activities:
        lines.extend(_format_activity(a) for a in ctx.activities)
    else:
        lines.append("⚠️ 无活动流水")

    lines.append(f"\n# 任务 (tasks 关联到主线, 共 {len(ctx.tasks)} 条)")
    if ctx.tasks:
        lines.extend(_format_task(t) for t in ctx.tasks)
    else:
        lines.append("⚠️ 无任务")

    if ctx.applied_clarifications:
        lines.append(f"\n# 历史澄清 ({len(ctx.applied_clarifications)} 条, 已 applied 进过去版本)")
        for c in ctx.applied_clarifications[:10]:
            lines.append(
                f"- [{c.dimension}] {c.answered_by_display_name} {c.answered_at}: {c.answer}"
            )

    if ctx.pending_clarifications:
        lines.append(f"\n# 用户新澄清 ({len(ctx.pending_clarifications)} 条 pending, 本次必须吸纳)")
        for c in ctx.pending_clarifications:
            lines.append(
                f"- [{c.dimension}] {c.answered_by_display_name} {c.answered_at}: {c.answer}"
            )

    lines.append("\n# 维度生成指引")
    for d in DIMENSIONS:
        lines.append(f"- {d}: {DIMENSION_BRIEF[d]}")

    lines.append(
        "\n请严格按下面 JSON Schema 输出 6 个维度 + overallConfidence (0.0-1.0):\n"
        + json.dumps(NARRATIVE_OUTPUT_SCHEMA, ensure_ascii=False)
    )
    return "\n".join(lines)


# ============================================================
# LLM 调用 + 解析
# ============================================================


def _strip_to_json(raw: str) -> str:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end >= start:
        cleaned = cleaned[start : end + 1]
    return cleaned


def _chat_completions_endpoint(base_url: str) -> str:
    normalized = str(base_url or "").strip().rstrip("/")
    if not normalized:
        raise RuntimeError("organization AI base URL is missing")
    return normalized if normalized.endswith("/chat/completions") else f"{normalized}/chat/completions"


def call_llm(
    user_prompt: str,
    *,
    api_key: str,
    base_url: str,
    model: str,
) -> dict[str, Any]:
    if not api_key or not model:
        raise RuntimeError("organization AI configuration is incomplete")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "top_p": 0.9,
        "max_tokens": 4000,
        "stream": False,
        "enable_thinking": False,
    }
    # max_tokens=4000 时 Qwen/Doubao 真实生成耗时常超 90 秒，read 给到 180s
    timeout = httpx.Timeout(timeout=None, connect=10.0, read=180.0, write=20.0, pool=10.0)
    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            _chat_completions_endpoint(base_url),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        result = response.json()
    text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    return json.loads(_strip_to_json(text))


# ============================================================
# 主流程 · 真生成或降级
# ============================================================


def _validate_and_clean_dim(payload: Any, dim: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _stub_dim(dim, "LLM 返回结构不合法")
    narrative = str(payload.get("narrative") or "").strip()
    if not narrative:
        return _stub_dim(dim, "LLM 在此维度未给出叙事")
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
    return {
        "narrative": narrative,
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


def _build_clarification_append_dim(ctx: ClientContext, dim: str) -> dict[str, Any] | None:
    """LLM 失败时的降级: 把这次 pending 澄清的 answer 拼到对应维度."""
    relevant = [c for c in ctx.pending_clarifications if c.dimension == dim]
    if not relevant:
        return None
    bits = [
        f"[{c.answered_by_display_name} {c.answered_at}] {c.answer}"
        for c in relevant
    ]
    return {
        "narrative": "\n\n".join(bits),
        "confidence": "medium",
        "confidenceReason": "降级: LLM 调用失败, 仅拼接用户澄清原文",
        "references": [],
        "dataLayerGap": "",
        "openClarifications": [],
    }


def regenerate_narrative(
    db: Database,
    organization_id: str,
    client_id: str,
    *,
    triggered_by_user_id: str | None,
    triggered_by_display_name: str,
    trigger: str = "manual",
    force: bool = False,
    use_llm: bool = True,
    ai_api_key: str | None = None,
    ai_base_url: str = "",
    ai_model: str = "",
) -> int:
    """主入口: 收集 facts → 调 LLM → 解析 → 落新 rev. 返回新 rev 号."""
    ctx = collect_client_context(db, organization_id, client_id)

    # 1. 真生成 (use_llm=True 且调用方传入当前组织的 AI 配置)
    parsed: dict[str, Any] | None = None
    model_name = ""
    generator_tag = "ai_doubao"
    error_reason = ""
    if use_llm and ai_api_key and ai_base_url and ai_model:
        user_prompt = build_user_prompt(ctx)
        try:
            parsed = call_llm(
                user_prompt,
                api_key=ai_api_key,
                base_url=ai_base_url,
                model=ai_model,
            )
            model_name = ai_model
        except (httpx.HTTPError, json.JSONDecodeError, RuntimeError) as exc:
            parsed = None
            error_reason = f"{type(exc).__name__}: {exc}"
    elif not use_llm:
        error_reason = "use_llm=False (test or override)"
    else:
        error_reason = "当前组织 AI 配置未提供"

    # 2. 解析 + 校验; 失败维度降级到澄清拼接 or stub
    dims_payload: dict[str, dict[str, Any]] = {}
    overall_confidence = 0.0
    if parsed and isinstance(parsed, dict):
        for d in DIMENSIONS:
            dims_payload[d] = _validate_and_clean_dim(parsed.get(d), d)
        try:
            overall_confidence = float(parsed.get("overallConfidence") or 0.0)
        except (TypeError, ValueError):
            overall_confidence = 0.0
    else:
        generator_tag = "stub_clarification_append"
        for d in DIMENSIONS:
            stub = _build_clarification_append_dim(ctx, d)
            dims_payload[d] = stub if stub is not None else _stub_dim(d, error_reason or "未生成")

    # 3. 落库
    data_layer_gaps = _compute_gaps(ctx)
    return narrative_svc.write_new_version(
        db,
        organization_id,
        client_id,
        dims_payload,
        overall_confidence=overall_confidence,
        data_layer_gaps=data_layer_gaps,
        generator=generator_tag,
        model_name=model_name or "stub",
        triggered_by_user_id=triggered_by_user_id,
        triggered_by_display_name=triggered_by_display_name,
        trigger=trigger,
    )


def _compute_gaps(ctx: ClientContext) -> list[str]:
    """根据 collector 实际拿到啥, 报告数据中心加工层缺口。
    Phase 1 第 1/4 项已建 (cloud_client_strategic_profiles + cloud_external_persons),
    只有当用户没填时才报缺。"""
    gaps: list[str] = []
    if not ctx.structured_profile and not ctx.strategic_profile:
        gaps.append("client_strategic_profile (用户尚未填写 项目类型/目标/成功标准/当前阶段)")
    if not ctx.external_persons:
        gaps.append("external_persons 花名册 (用户尚未录入关键人物)")
    if not ctx.event_lines:
        gaps.append("event_lines (主线尚未关联 primary_client_id)")
    if not ctx.activities:
        gaps.append("event_line_activities (业务流水缺业务语义标注)")
    if not ctx.tasks:
        gaps.append("tasks (任务未跟主线绑定)")
    gaps.append("evidence_cards 业务语义化 (现 polarity 全 neutral)")
    gaps.append("risk_signals 表 (尚未建)")
    return gaps


# ============================================================
# 便利封装: 给 CLI / 测试调用
# ============================================================

def context_to_dict(ctx: ClientContext) -> dict[str, Any]:
    """方便日志/测试打印."""
    return {
        "client_id": ctx.client_id,
        "client_name": ctx.client_name,
        "event_lines": [asdict(e) for e in ctx.event_lines],
        "activities": [asdict(a) for a in ctx.activities],
        "tasks": [asdict(t) for t in ctx.tasks],
        "pending_clarifications": [asdict(c) for c in ctx.pending_clarifications],
        "applied_clarifications": [asdict(c) for c in ctx.applied_clarifications],
    }
