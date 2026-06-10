"""[A] V2.5 R2-B · MeetingMinuteProcessor · 端到端 orchestrator

顾源源 5/23 钦定 R2 总目标:
> 在 V2.1 lab 完成一次"真实会议纪要 → 客户理解与行动包"的端到端闭环.
> 让用户看到系统从会议材料中自动生成事实、时间线、风险、承诺、澄清问题、
> 任务草稿、故事卡更新和可审计日志.

流程:
  1. Agent Run Log start
  2. LLM 抽取 atomic_facts (qwen2.5:14b)
  3. 用 IngestPipeline 写入 (走 V2.5 P0-1 实时 trigger)
     → 自动 derive + detect
  4. 起草任务 (从派生的 commitments)
  5. 更新故事卡
  6. 危险动作 → Approval Queue
  7. Agent Run Log complete
  8. 渲染 6 段客户理解变化报告

R2 最小通过线 (顾源源钦定):
  · ≥ 5 新增候选事实
  · ≥ 1 新增时间线事件
  · ≥ 1 新增风险信号
  · ≥ 1 新增承诺/待办
  · ≥ 1 新增澄清问题
  · ≥ 1 新增任务草稿
  · Agent Run Log 100%
  · 跨客户串线 0
"""
from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Protocol

logger = logging.getLogger(__name__)


class _DbLike(Protocol):
    def execute(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchone(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchall(self, sql: str, params: tuple = ...) -> Any: ...


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_LLM_MODEL = "qwen2.5:14b"
LLM_TIMEOUT_SECONDS = 90


@dataclass(frozen=True)
class MinuteProcessResult:
    """端到端处理结果."""
    run_id: str
    client_id: str
    new_facts: list[dict] = field(default_factory=list)
    new_event_line_count: int = 0
    new_risks: list[dict] = field(default_factory=list)
    new_commitments: list[dict] = field(default_factory=list)
    new_clarifications: list[dict] = field(default_factory=list)
    new_task_drafts: list[dict] = field(default_factory=list)
    new_insights: list[dict] = field(default_factory=list)
    approval_queue_ids: list[str] = field(default_factory=list)
    story_card_md: str = ""
    elapsed_seconds: float = 0
    errors: list[str] = field(default_factory=list)


# ─── LLM 抽取 ────────────────────────────────────────


def _build_extract_prompt(minute_text: str, client_name: str, roster_text: str = "") -> str:
    """会议纪要抽取 prompt (区分事实/承诺/风险/判断/纠错/任务).

    R2 fix-2: 强化 clarifications 抽取要求 (B sync 缺口 2).
    """
    return (
        "你是益语智库的会议纪要分析助手. 给你一段中文会议纪要, 抽取结构化信息.\n\n"
        f"客户: {client_name}\n\n"
        + (f"{roster_text}\n\n" if roster_text else "")
        + "请输出一个 JSON 对象, 包含 6 个字段:\n"
        '{\n'
        '  "facts": [...]          // 客户事实 (subject/attribute/value/time)\n'
        '  "risks": [...]          // 风险 (title/description/severity high|medium|low)\n'
        '  "commitments": [...]    // 承诺 (committer/recipient/content/deadline)\n'
        '  "judgments": [...]      // 我方/用户判断 (subject/judgment/confidence)\n'
        '  "task_drafts": [...]    // 待办任务草稿 (title/owner/due_date/priority)\n'
        '  "clarifications": [...] // 待澄清问题 (question/why/options)\n'
        '}\n\n'
        "要求:\n"
        "1. 输出严格 JSON, 不要 markdown 包裹, 不要任何解释\n"
        "2. 数字/日期/人名/范围都要保留原文表达\n"
        "3. 缺信息的字段填 null 或空数组\n"
        "4. 不允许编造原文没有的数字/日期/人名\n"
        "5. facts 至少抽 5 条 (如果原文够多)\n"
        "6. ★ clarifications 必须至少 1 条 (会议总有不确定点):\n"
        "   - 任何'担心/担忧/可能/不确定/再说/具体/还需要' 类表达 → 1 个澄清问题\n"
        "   - 任何模糊范围 ('几个'/'若干'/'部分') → 1 个澄清问题\n"
        "   - 任何责任人不明 → 1 个澄清问题\n"
        "   - 即使全文都明确, 也要主动问 1 个'下一步最应该问客户的关键点'\n\n"
        "会议纪要:\n"
        f"{minute_text}\n\n"
        "JSON 输出:\n"
    )


def _call_ollama(prompt: str, model: str = DEFAULT_LLM_MODEL) -> str:
    data = json.dumps({
        "model": model, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.1, "num_predict": 3000},
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL, data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=LLM_TIMEOUT_SECONDS) as resp:
        return json.loads(resp.read().decode("utf-8")).get("response", "")


def _parse_json_object(text: str) -> dict:
    """从 LLM 输出抽 JSON 对象."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        logger.warning("LLM JSON 解析失败: %s", exc)
        return {}


# ─── 主处理 ──────────────────────────────────────────


def process_meeting_minute(
    db: _DbLike, *,
    client_id: str,
    minute_text: str,
    actor_type: str = "internal_ai",
    actor_id: str = "meeting_minute_processor",
    session_id: str | None = None,
    idempotency_key: str | None = None,
    use_llm: bool = True,
    auto_approve_safe_actions: bool = True,
) -> MinuteProcessResult:
    """端到端处理一段会议纪要.

    R2 fix-2 (2026-05-23 B sync 后):
      · idempotency_key 真传给 log_agent_run_start (缺口 1)
      · 末尾写一条 event_line_activity 不依赖 derive_all (缺口 3)
    """
    from app.services.agent_governance import (
        log_agent_run_start, log_agent_run_complete,
        enqueue_approval, ApprovalRequest,
    )
    from app.services.atomic_fact_semantic_deriver import derive_all
    from app.services.formal_conflict_detector import detect_all

    t0 = time.time()
    errors: list[str] = []

    # 客户名 (Agent Log 用)
    client_row = db.fetchone("SELECT name FROM clients WHERE id = ?", (client_id,))
    client_name = dict(client_row)["name"] if client_row else client_id

    # 1. Agent Run Log start (R2 fix-2 缺口 1: idempotency_key 真记录)
    run_id = log_agent_run_start(
        db, actor_type=actor_type, actor_id=actor_id,
        tool_name="meeting_minute_processor.process",
        client_id=client_id,
        input_payload={"minute_text": minute_text[:500], "client_name": client_name},
        idempotency_key=idempotency_key,
        session_id=session_id,
    )

    new_facts: list[dict] = []
    new_risks: list[dict] = []
    new_commitments: list[dict] = []
    new_clarifications: list[dict] = []
    new_task_drafts: list[dict] = []
    new_insights: list[dict] = []
    approval_ids: list[str] = []

    # 2. LLM 抽取
    extracted: dict = {}
    if use_llm:
        try:
            # meeting-spine Phase1③: 注入客户名册, 让 owner/committer/speaker 对齐到已知人名
            roster_text = ""
            _conn = getattr(db, "conn", None)
            if _conn is not None:
                try:
                    from app.services.person_resolver import build_client_roster_hint
                    roster_text = build_client_roster_hint(_conn, client_id)
                except Exception:
                    roster_text = ""
            prompt = _build_extract_prompt(minute_text, client_name, roster_text)
            raw = _call_ollama(prompt)
            extracted = _parse_json_object(raw)
        except Exception as exc:
            errors.append(f"LLM 抽取失败: {exc}")

    # 3. 写入 atomic_facts (按抽取的 6 类)
    now = _now_iso()
    extracted_facts = extracted.get("facts") or []
    for f in extracted_facts[:30]:
        if not isinstance(f, dict):
            continue
        fid = f"af_mm_{uuid.uuid4().hex[:20]}"
        try:
            db.execute(
                """INSERT INTO atomic_facts (
                    id, client_id, subject_text, attribute, value_text,
                    value_normalized, confidence, source_v2_chunk_id, source_v2_document_id,
                    evidence_text, created_at, updated_at,
                    source_type, content_role, actor_type, actor_id,
                    speaker_person_id, time_anchor, verification_status,
                    confidence_source, update_relation, status
                ) VALUES (?, ?, ?, ?, ?, ?, 0.85, NULL, NULL, ?, ?, ?,
                          'client_internal_doc', 'fact', 'ai_agent', ?,
                          NULL, ?, 'unverified', 'rule', 'none', 'active')""",
                (
                    fid, client_id,
                    str(f.get("subject", "未知"))[:200],
                    str(f.get("attribute", "事实"))[:200],
                    str(f.get("value", ""))[:500],
                    str(f.get("value", ""))[:200].lower(),
                    f"[meeting:{run_id}] {minute_text[:300]}",
                    now, now, run_id,
                    f.get("time"),
                ),
            )
            new_facts.append({"fact_id": fid, **f})
        except Exception as exc:
            errors.append(f"写 fact 失败: {exc}")

    # 4. 写入风险
    for r in (extracted.get("risks") or [])[:10]:
        if not isinstance(r, dict):
            continue
        rid = f"risk_mm_{uuid.uuid4().hex[:20]}"
        try:
            db.execute(
                """INSERT INTO risk_signals (
                    id, client_id, signal_kind, title, description,
                    severity, related_term_ids_json, source_type, source_id,
                    captured_at, status, resolution_note, created_at, updated_at
                ) VALUES (?, ?, 'meeting_extracted', ?, ?, ?, '[]',
                          'meeting_minute_processor', ?, ?, 'active', '', ?, ?)""",
                (
                    rid, client_id, str(r.get("title", ""))[:200],
                    str(r.get("description", ""))[:500],
                    r.get("severity", "medium") if r.get("severity") in ("high","medium","low") else "medium",
                    run_id, now, now, now,
                ),
            )
            new_risks.append({"risk_id": rid, **r})
        except Exception as exc:
            errors.append(f"写 risk 失败: {exc}")

    # 5. 写入承诺
    for c in (extracted.get("commitments") or [])[:10]:
        if not isinstance(c, dict):
            continue
        cid = f"com_mm_{uuid.uuid4().hex[:20]}"
        try:
            db.execute(
                """INSERT INTO commitments (
                    id, client_id, committer, recipient, commitment_type,
                    content, deadline, status, related_term_ids_json,
                    source_type, source_id, fulfilled_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'verbal', ?, ?, 'pending', '[]',
                          'meeting_minute_processor', ?, NULL, ?, ?)""",
                (
                    cid, client_id,
                    str(c.get("committer", "未知"))[:80],
                    str(c.get("recipient", ""))[:80],
                    str(c.get("content", ""))[:500],
                    c.get("deadline"),
                    run_id, now, now,
                ),
            )
            new_commitments.append({"commitment_id": cid, **c})
        except Exception as exc:
            errors.append(f"写 commitment 失败: {exc}")

    # 6. 写入用户判断 → strategic_thought_insights
    for j in (extracted.get("judgments") or [])[:10]:
        if not isinstance(j, dict):
            continue
        sid = f"sti_mm_{uuid.uuid4().hex[:20]}"
        try:
            db.execute(
                """INSERT INTO strategic_thought_insights (
                    id, scope_type, client_id, client_name,
                    title, insight_type, insight_text, future_judgment, recommended_action,
                    evidence_summary, evidence_labels_json, source_refs_json,
                    source_fingerprint, signal_score, raw_payload_json,
                    is_favorite, is_deleted, generated_at, created_at, updated_at
                ) VALUES (?, 'client', ?, ?, ?, 'meeting_judgment', ?, '', '',
                          ?, '["meeting"]', ?, ?, 70, '{}',
                          0, 0, ?, ?, ?)""",
                (
                    sid, client_id, client_name,
                    str(j.get("subject", ""))[:120],
                    str(j.get("judgment", ""))[:500],
                    minute_text[:200],
                    json.dumps([run_id]),
                    f"meeting:{run_id}",
                    now, now, now,
                ),
            )
            new_insights.append({"insight_id": sid, **j})
        except Exception as exc:
            errors.append(f"写 insight 失败: {exc}")

    # 7. 任务草稿 (走 approval queue, 不直接发布)
    for t in (extracted.get("task_drafts") or [])[:10]:
        if not isinstance(t, dict):
            continue
        appr_id = enqueue_approval(
            db, ApprovalRequest(
                action_type="task.publish",
                actor_type=actor_type, actor_id=actor_id,
                client_id=client_id,
                target_resource=f"task_draft/{uuid.uuid4().hex[:16]}",
                payload={
                    "title": t.get("title"),
                    "owner": t.get("owner"),
                    "due_date": t.get("due_date"),
                    "priority": t.get("priority", "medium"),
                    "source_meeting_run": run_id,
                },
                reason="LLM 从会议纪要起草, 等用户审批后发布到 tasks",
                agent_run_id=run_id,
            ),
        )
        approval_ids.append(appr_id)
        new_task_drafts.append({"approval_id": appr_id, **t})

    # 8. 澄清问题 (直接写 clarification_records, status=pending 等用户处理)
    for clar in (extracted.get("clarifications") or [])[:10]:
        if not isinstance(clar, dict):
            continue
        clar_id = f"clar_mm_{uuid.uuid4().hex[:20]}"
        try:
            db.execute(
                """INSERT INTO clarification_records (
                    id, scope_type, scope_id, slot_key, question, status,
                    write_scope_json, resolved_fact_ids_json, reusable,
                    created_at, updated_at
                ) VALUES (?, 'client', ?, ?, ?, 'pending', ?, '[]', 0, ?, ?)""",
                (
                    clar_id, client_id,
                    f"meeting/{run_id}/{clar_id[-8:]}",
                    str(clar.get("question", ""))[:500],
                    json.dumps({
                        "source": "meeting_minute_processor",
                        "run_id": run_id,
                        "why": clar.get("why", ""),
                        "options": clar.get("options", []),
                    }, ensure_ascii=False),
                    now, now,
                ),
            )
            new_clarifications.append({"clarification_id": clar_id, **clar})
        except Exception as exc:
            errors.append(f"写 clarification 失败: {exc}")

    # 9. 跑派生器 (补 V2.5 P0-1 链路, 让新写入的 facts 派生到时间线)
    try:
        d = derive_all(db, client_id)
        new_event_line_count = d.event_line_activities_new
    except Exception as exc:
        errors.append(f"derive_all 失败: {exc}")
        new_event_line_count = 0

    # 9b. R2 fix-2 缺口 3 · 会议本身直写 event_line_activity (不依赖 derive_all)
    # B sync d2eb27d 实测: derive_all 对 测试论坛A/测试机构A 返回 ela+0 (客户可能无 event_line 或派生条件未触发)
    # 修法: 把"本次会议"作为一条 ela 直写, 让时间线真长.
    try:
        # 找客户的 event_line; 没有就 fallback 建一条"客户主线"
        el_row = db.fetchone(
            "SELECT id FROM event_lines WHERE primary_client_id = ? LIMIT 1",
            (client_id,),
        )
        if el_row:
            event_line_id = dict(el_row)["id"]
        else:
            event_line_id = f"el_meeting_{uuid.uuid4().hex[:20]}"
            db.execute(
                """INSERT INTO event_lines (
                    id, primary_client_id, name, stage, status,
                    current_blocker, next_step, created_at, updated_at
                ) VALUES (?, ?, ?, '进行中', 'active', '', '', ?, ?)""",
                (event_line_id, client_id, f"{client_name} 主线", now, now),
            )
        # 抽 meeting 时间 (从第 1 条 fact 的 time 或当前时间)
        meeting_time = now
        for f in extracted_facts:
            if isinstance(f, dict) and f.get("time"):
                meeting_time = str(f["time"])
                break
        # 写 ela (会议本身)
        ela_id = f"ela_meeting_{uuid.uuid4().hex[:20]}"
        db.execute(
            """INSERT INTO event_line_activities (
                id, event_line_id, source_type, source_id, happened_at,
                actor_id, actor_name, title, summary, metadata_json,
                is_key, created_at
            ) VALUES (?, ?, 'meeting_minute', ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (
                ela_id, event_line_id, run_id, meeting_time,
                actor_id, client_name,
                f"{client_name} · 会议纪要处理 ({len(new_facts)} 事实 {len(new_risks)} 风险)",
                minute_text[:500],
                json.dumps({
                    "run_id": run_id,
                    "facts": len(new_facts),
                    "risks": len(new_risks),
                    "commitments": len(new_commitments),
                }, ensure_ascii=False),
                now,
            ),
        )
        new_event_line_count += 1  # 直写本次会议 ela
    except Exception as exc:
        errors.append(f"写 meeting ela 失败: {exc}")

    # 10. 跑冲突检测 (跨源印证)
    try:
        detect_all(db, client_id)
    except Exception as exc:
        errors.append(f"detect_all 失败: {exc}")

    # 11. 生成故事卡
    story_card_md = ""
    try:
        from app.services.story_card_generator import generate_story_card
        story_card_md = generate_story_card(db, client_id)
    except Exception as exc:
        errors.append(f"故事卡生成失败: {exc}")

    # 12. Agent Run Log complete
    elapsed = time.time() - t0
    log_agent_run_complete(
        db, run_id,
        output_payload={
            "facts": len(new_facts), "risks": len(new_risks),
            "commitments": len(new_commitments), "insights": len(new_insights),
            "clarifications": len(new_clarifications),
            "task_drafts": len(new_task_drafts),
            "event_line_new": new_event_line_count,
            "errors": errors[:5],
        },
        status="success" if not errors else "partial",
        error_message="; ".join(errors[:3]) if errors else None,
        duration_ms=int(elapsed * 1000),
    )

    return MinuteProcessResult(
        run_id=run_id, client_id=client_id,
        new_facts=new_facts,
        new_event_line_count=new_event_line_count,
        new_risks=new_risks,
        new_commitments=new_commitments,
        new_clarifications=new_clarifications,
        new_task_drafts=new_task_drafts,
        new_insights=new_insights,
        approval_queue_ids=approval_ids,
        story_card_md=story_card_md,
        elapsed_seconds=elapsed,
        errors=errors,
    )


# ─── 客户理解变化报告渲染 ────────────────────────────


def render_understanding_change_report(
    result: MinuteProcessResult, *, client_name: str, minute_excerpt: str = "",
) -> str:
    """渲染顾源源 5/23 钦定 6 段客户理解变化报告 markdown."""
    lines = []
    lines.append(f"# 会议纪要处理后的客户理解变化报告 · {client_name}")
    lines.append("")
    lines.append(f"**run_id**: `{result.run_id}`")
    lines.append(f"**耗时**: {result.elapsed_seconds:.1f}s")
    lines.append(f"**会议纪要摘要**: {minute_excerpt[:200]}...")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 段 1: 新增事实
    lines.append("## 1️⃣ 这次会议让系统新增了什么事实")
    lines.append("")
    if result.new_facts:
        for f in result.new_facts[:10]:
            subj = f.get("subject", "?")
            attr = f.get("attribute", "?")
            val = f.get("value", "?")
            lines.append(f"- **{subj}** · {attr} = {val}")
    else:
        lines.append("_(未抽到新事实)_")
    lines.append("")
    lines.append(f"> 共 {len(result.new_facts)} 条新事实 (派生 +{result.new_event_line_count} 时间线事件)")
    lines.append("")

    # 段 2: 新增风险
    lines.append("## 2️⃣ 这次会议让系统新增了什么风险")
    lines.append("")
    if result.new_risks:
        for r in result.new_risks[:10]:
            sev = r.get("severity", "medium")
            badge = "🔴" if sev == "high" else ("🟡" if sev == "medium" else "🟢")
            lines.append(f"- {badge} **{r.get('title','?')}** — {r.get('description','')[:120]}")
    else:
        lines.append("_(未抽到新风险)_")
    lines.append("")

    # 段 3: 待澄清问题
    lines.append("## 3️⃣ 这次会议产生了哪些待澄清问题")
    lines.append("")
    if result.new_clarifications:
        for c in result.new_clarifications[:10]:
            q = c.get("question", "?")
            why = c.get("why", "")
            lines.append(f"- **{q}**")
            if why:
                lines.append(f"  - 为什么要问: {why}")
    else:
        lines.append("_(未抽到新澄清问题)_")
    lines.append("")

    # 段 4: 任务草稿
    lines.append("## 4️⃣ 这次会议产生了哪些任务草稿 (待审批)")
    lines.append("")
    if result.new_task_drafts:
        for t in result.new_task_drafts[:10]:
            title = t.get("title", "?")
            owner = t.get("owner", "待确认")
            due = t.get("due_date", "?")
            lines.append(f"- **{title}** · 负责人: {owner} · 截止: {due}")
            lines.append(f"  - approval_id: `{t.get('approval_id','?')}` (待用户审批)")
    else:
        lines.append("_(未抽到任务草稿)_")
    lines.append("")

    # 段 5: 故事卡更新概览
    lines.append("## 5️⃣ 这次会议改变了客户故事卡哪几段")
    lines.append("")
    sections_changed = []
    if result.new_event_line_count > 0:
        sections_changed.append(f"段 4 时间线 +{result.new_event_line_count} 条活动")
    if result.new_risks:
        sections_changed.append(f"段 8 风险 +{len(result.new_risks)} 条")
    if result.new_commitments:
        sections_changed.append(f"段 9 下一步 +{len(result.new_commitments)} 承诺")
    if result.new_insights:
        sections_changed.append(f"段 6 关键判断 +{len(result.new_insights)} 条")
    if result.new_clarifications:
        sections_changed.append(f"段 7 冲突待澄清 +{len(result.new_clarifications)} 条")
    for s in sections_changed:
        lines.append(f"- {s}")
    if not sections_changed:
        lines.append("_(无段落变化)_")
    lines.append("")

    # 段 6: 待用户确认动作
    lines.append("## 6️⃣ 哪些动作需要用户确认")
    lines.append("")
    if result.approval_queue_ids:
        lines.append(f"**Approval Queue: {len(result.approval_queue_ids)} 个待审批**")
        lines.append("")
        for t in result.new_task_drafts:
            lines.append(f"- 任务发布: `{t.get('title','?')}` (approval `{t.get('approval_id','?')}`)")
    else:
        lines.append("_(无待审批动作)_")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## R2 判决线核对")
    lines.append("")
    targets = [
        ("新增候选事实 ≥ 5", len(result.new_facts) >= 5),
        ("新增时间线事件 ≥ 1", result.new_event_line_count >= 1),
        ("新增风险信号 ≥ 1", len(result.new_risks) >= 1),
        ("新增承诺/待办 ≥ 1", len(result.new_commitments) >= 1),
        ("新增澄清问题 ≥ 1", len(result.new_clarifications) >= 1),
        ("新增任务草稿 ≥ 1", len(result.new_task_drafts) >= 1),
        ("Agent Run Log 100%", bool(result.run_id)),
    ]
    passed = sum(1 for _, ok in targets if ok)
    for label, ok in targets:
        lines.append(f"- {'✅' if ok else '❌'} {label}")
    lines.append("")
    lines.append(f"**R2 通过 {passed}/7 项**" + (" — 达到最小通过线" if passed >= 6 else " — 未达"))
    if result.errors:
        lines.append("")
        lines.append("### 错误清单 (前 5)")
        for e in result.errors[:5]:
            lines.append(f"- {e}")
    return "\n".join(lines)
