"""[A] V2.6 R4-P0-1 · CompanyBrainContextBuilder · 公司大脑统一上下文入口

顾源源 5/23 R4 钦定核心基础设施:
> 所有生成型功能都不要自己拼数据.
> 所有生成型功能都统一调用它.

不同 task_type 走不同 evidence 路由 (但底层 build 一次).

task_type:
  · workbench_qa        — 工作台问答 (8 类 evidence + clarification 建议)
  · strategy_narrative  — 战略陪伴 6 段叙事 (重 contracts/historical/data_gaps)
  · smart_import        — 智能文件导入 (重 file_identities/contract_structures)
  · template_fill       — 模板填充 (重 权威值/合同结构/最新版本)
  · weekly_review       — 周复盘 (重 historical_links/timeline/commitments)
  · proposal_generation — 写为提案 (重 external_evidence/data_gaps)

底层复用: company_brain_qa.build_evidence_pack (R3-M3 已实现 8 类 evidence)
本服务: 加 task_type 路由 + 加 4 类新 evidence (file_identities/method_cards/plan_links/approvals)
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

logger = logging.getLogger(__name__)


class _DbLike(Protocol):
    def execute(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchone(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchall(self, sql: str, params: tuple = ...) -> Any: ...


TaskType = Literal[
    "workbench_qa", "strategy_narrative", "smart_import",
    "template_fill", "weekly_review", "proposal_generation",
]


@dataclass
class CompanyBrainContextPack:
    """统一公司大脑上下文 — 12 类 evidence + 4 类 summary."""
    # 12 类 evidence (顾源源 R4 §七 设计)
    authoritative_facts: list[dict] = field(default_factory=list)  # 用户确认 / 高置信
    candidate_facts: list[dict] = field(default_factory=list)      # 待澄清
    contracts: list[dict] = field(default_factory=list)
    files: list[dict] = field(default_factory=list)
    historical_links: list[dict] = field(default_factory=list)
    timeline: list[dict] = field(default_factory=list)
    commitments: list[dict] = field(default_factory=list)
    risks: list[dict] = field(default_factory=list)
    clarifications: list[dict] = field(default_factory=list)
    external_evidence: list[dict] = field(default_factory=list)
    data_gaps: list[dict] = field(default_factory=list)
    method_cards: list[dict] = field(default_factory=list)
    plan_links: list[dict] = field(default_factory=list)
    approvals: list[dict] = field(default_factory=list)
    # 4 类 summary
    evidence_summary: dict = field(default_factory=dict)
    uncertainty_summary: dict = field(default_factory=dict)
    recommended_actions: list[str] = field(default_factory=list)
    used_tables: list[str] = field(default_factory=list)
    # meta
    client_id: str | None = None
    project_id: str | None = None
    task_type: str = "workbench_qa"
    keywords_used: list[str] = field(default_factory=list)


def _fetch_safe(db: _DbLike, sql: str, params: tuple = ()) -> list[dict]:
    """安全 fetchall, 表不存在/字段缺失返回空."""
    try:
        rows = db.fetchall(sql, params)
        return [dict(r) for r in rows]
    except Exception as exc:
        logger.debug("fetch_safe failed: %s | sql=%s", exc, sql[:80])
        return []


def build_company_brain_context(
    db: _DbLike, *,
    client_id: str,
    project_id: str | None = None,
    user_query: str | None = None,
    task_type: TaskType = "workbench_qa",
    source_ids: list[str] | None = None,
    keywords: list[str] | None = None,
    include: dict | None = None,
) -> CompanyBrainContextPack:
    """统一公司大脑上下文构建.

    Args:
        client_id:    必填 — 跨客户隔离硬门槛
        task_type:    路由不同 evidence 重点
        keywords:     如果用户 query 已经提取关键词, 直接传; 否则从 user_query 自动抽
        include:      {'contracts': True, ...} 控制返回字段
    """
    include = include or {"all": True}
    inc = lambda k: include.get("all") or include.get(k, False)

    # auto-extract keywords
    if not keywords and user_query:
        keywords = [k for k in re.findall(r"[一-龥]{2,6}", user_query) if len(k) >= 2][:8]
    keywords = keywords or []

    used_tables: list[str] = []
    pack = CompanyBrainContextPack(
        client_id=client_id, project_id=project_id, task_type=task_type,
        keywords_used=keywords,
    )

    # 关键字 LIKE clause helper
    def _kw_like_clause(cols: list[str]) -> tuple[str, list[Any]]:
        if not keywords:
            return "", []
        clauses, params = [], []
        for kw in keywords[:5]:
            for c in cols:
                clauses.append(f"{c} LIKE ?")
                params.append(f"%{kw}%")
        return " AND (" + " OR ".join(clauses) + ")", params

    # 1. atomic_facts (split authoritative vs candidate)
    if inc("facts"):
        kw_sql, kw_params = _kw_like_clause(["subject_text", "attribute", "value_text"])
        rows = _fetch_safe(db,
            f"""SELECT id, subject_text, attribute, value_text, source_type,
                       confidence, time_anchor, verification_status, status
                FROM atomic_facts WHERE client_id = ? AND status = 'active' {kw_sql}
                ORDER BY confidence DESC LIMIT 30""",
            tuple([client_id] + kw_params),
        )
        for r in rows:
            if r.get("verification_status") == "user_confirmed" or r.get("confidence", 0) >= 0.85:
                pack.authoritative_facts.append(r)
            else:
                pack.candidate_facts.append(r)
        if rows: used_tables.append("atomic_facts")

    # 2. contract_structures (R3-M1)
    if inc("contracts"):
        rows = _fetch_safe(db,
            """SELECT id, party_a, party_b, project_name, signed_at, effective_period,
                      amount, deliverables_json, responsibilities_json, version
               FROM contract_structures WHERE client_id = ?""",
            (client_id,),
        )
        pack.contracts.extend(rows)
        if rows: used_tables.append("contract_structures")

    # 3. file_identities (R3-M1)
    if inc("files"):
        rows = _fetch_safe(db,
            """SELECT id, file_name, file_type, file_role, project_name,
                      version, file_time, main_subject, is_authoritative
               FROM file_identities WHERE client_id = ?
               ORDER BY file_time DESC LIMIT 30""",
            (client_id,),
        )
        pack.files.extend(rows)
        if rows: used_tables.append("file_identities")

    # 4. historical_reference_links (R3-M2)
    if inc("historical_links"):
        rows = _fetch_safe(db,
            """SELECT ref_text, ref_type, target_table, target_id, match_score, source_doc_type
               FROM historical_reference_links WHERE client_id = ?
               ORDER BY resolved_at DESC LIMIT 20""",
            (client_id,),
        )
        pack.historical_links.extend(rows)
        if rows: used_tables.append("historical_reference_links")

    # 5. event_line_activities (timeline)
    if inc("timeline"):
        rows = _fetch_safe(db,
            """SELECT a.id, a.happened_at, a.actor_name, a.title, a.summary
               FROM event_line_activities a
               JOIN event_lines el ON el.id = a.event_line_id
               WHERE el.primary_client_id = ?
               ORDER BY a.happened_at DESC LIMIT 30""",
            (client_id,),
        )
        pack.timeline.extend(rows)
        if rows: used_tables.append("event_line_activities")

    # 6. commitments (V2.4 P0-1)
    if inc("commitments"):
        rows = _fetch_safe(db,
            """SELECT id, committer, recipient, content, deadline, status
               FROM commitments WHERE client_id = ? AND status != 'cancelled'
               ORDER BY created_at DESC LIMIT 20""",
            (client_id,),
        )
        pack.commitments.extend(rows)
        if rows: used_tables.append("commitments")

    # 7. risks
    if inc("risks"):
        rows = _fetch_safe(db,
            """SELECT id, title, description, severity, status
               FROM risk_signals WHERE client_id = ? AND status = 'active'
               ORDER BY severity DESC LIMIT 20""",
            (client_id,),
        )
        pack.risks.extend(rows)
        if rows: used_tables.append("risk_signals")

    # 8. clarifications (pending only)
    if inc("clarifications"):
        rows = _fetch_safe(db,
            """SELECT id, question, slot_key FROM clarification_records
               WHERE scope_type='client' AND scope_id=? AND status='pending'
               ORDER BY created_at DESC LIMIT 20""",
            (client_id,),
        )
        pack.clarifications.extend(rows)
        if rows: used_tables.append("clarification_records")

    # 9. external_evidence_cards (R3-M4)
    if inc("external_evidence"):
        rows = _fetch_safe(db,
            """SELECT id, title, summary, source_tier, relation_to_internal, confidence
               FROM external_evidence_cards WHERE client_id = ? AND status = 'active'
               ORDER BY created_at DESC LIMIT 15""",
            (client_id,),
        )
        pack.external_evidence.extend(rows)
        if rows: used_tables.append("external_evidence_cards")

    # 10. data_gaps (R3-M4)
    if inc("data_gaps"):
        rows = _fetch_safe(db,
            """SELECT id, gap_type, subject, internal_value, external_value, suggested_action
               FROM data_gaps WHERE client_id = ? AND status = 'open'
               ORDER BY detected_at DESC LIMIT 10""",
            (client_id,),
        )
        pack.data_gaps.extend(rows)
        if rows: used_tables.append("data_gaps")

    # 11. method_cards (handbook_entries)
    if inc("method_cards"):
        rows = _fetch_safe(db,
            """SELECT id, title, content FROM handbook_entries
               ORDER BY updated_at DESC LIMIT 10""", (),
        )
        pack.method_cards.extend(rows)
        if rows: used_tables.append("handbook_entries")

    # 12. approval_queue + agent_run_log (R2-A)
    if inc("approvals"):
        rows = _fetch_safe(db,
            """SELECT id, action_type, target_resource, payload_json, status
               FROM approval_queue WHERE client_id = ? AND status = 'pending'
               ORDER BY created_at DESC LIMIT 10""",
            (client_id,),
        )
        pack.approvals.extend(rows)
        if rows: used_tables.append("approval_queue")

    # ─── summary ──────────────────────────────────────
    pack.used_tables.extend(used_tables)
    pack.evidence_summary = {
        "facts_authoritative": len(pack.authoritative_facts),
        "facts_candidate": len(pack.candidate_facts),
        "contracts": len(pack.contracts),
        "files": len(pack.files),
        "historical_links": len(pack.historical_links),
        "timeline_events": len(pack.timeline),
        "commitments": len(pack.commitments),
        "risks": len(pack.risks),
        "clarifications_pending": len(pack.clarifications),
        "external_evidence": len(pack.external_evidence),
        "data_gaps": len(pack.data_gaps),
        "method_cards": len(pack.method_cards),
        "approvals_pending": len(pack.approvals),
        "tables_used": len(used_tables),
        "evidence_types_count": sum(1 for n in [
            len(pack.authoritative_facts), len(pack.contracts), len(pack.files),
            len(pack.historical_links), len(pack.timeline), len(pack.commitments),
            len(pack.risks), len(pack.clarifications), len(pack.external_evidence),
            len(pack.data_gaps),
        ] if n > 0),
    }

    pack.uncertainty_summary = {
        "candidate_facts_count": len(pack.candidate_facts),
        "pending_clarifications": len(pack.clarifications),
        "data_gaps": len(pack.data_gaps),
        "external_needs_confirm": sum(
            1 for e in pack.external_evidence
            if e.get("relation_to_internal") == "needs_confirm"
        ),
    }

    # 推荐动作
    actions = []
    if pack.clarifications:
        actions.append(f"处理 {len(pack.clarifications)} 个待澄清问题")
    if pack.data_gaps:
        actions.append(f"补 {len(pack.data_gaps)} 个数据缺口")
    if pack.approvals:
        actions.append(f"审批 {len(pack.approvals)} 个待审批动作")
    pack.recommended_actions = actions

    return pack


def render_context_for_prompt(pack: CompanyBrainContextPack, max_chars: int = 6000) -> str:
    """把 ContextPack 拼成 LLM prompt 可读 markdown (带 [fact:xxx] 引用 ID)."""
    lines = []

    if pack.authoritative_facts:
        lines.append("## 权威事实 (authoritative)")
        for f in pack.authoritative_facts[:15]:
            lines.append(
                f"[fact:{f['id']}] {f['subject_text']} · {f['attribute']} = "
                f"{f.get('value_text','')[:80]} (源={f.get('source_type','?')}, "
                f"conf={f.get('confidence',0):.2f})"
            )

    if pack.contracts:
        lines.append("\n## 合同结构 (contracts)")
        for c in pack.contracts[:8]:
            lines.append(
                f"[contract:{c['id']}] {c.get('party_a','?')}↔{c.get('party_b','?')} · "
                f"{c.get('project_name','?')} · {c.get('amount','?')} · "
                f"签于 {c.get('signed_at','?')} · v={c.get('version','-')}"
            )

    if pack.files:
        lines.append("\n## 文件清单 (files)")
        for f in pack.files[:12]:
            lines.append(
                f"[file:{f['id']}] {f.get('file_name','?')} · "
                f"类型={f.get('file_type','?')} · 角色={f.get('file_role','?')} · "
                f"项目={f.get('project_name','-')}"
            )

    if pack.historical_links:
        lines.append("\n## 历史材料回指 (historical_links)")
        for h in pack.historical_links[:10]:
            lines.append(
                f"[hist:{h.get('ref_text','?')[:30]}] {h.get('ref_type','?')} → "
                f"{h.get('target_table','?')}/{h.get('target_id','?')} (score {h.get('match_score',0)})"
            )

    if pack.timeline:
        lines.append("\n## 时间线 (timeline)")
        for t in pack.timeline[:15]:
            lines.append(
                f"[timeline:{t['id']}] {(t.get('happened_at','?') or '')[:10]} · "
                f"{t.get('actor_name','sys')}: {(t.get('title','') or '')[:80]}"
            )

    if pack.commitments:
        lines.append("\n## 承诺 (commitments)")
        for cm in pack.commitments[:10]:
            lines.append(
                f"[commitment:{cm['id']}] {cm.get('committer','?')}: "
                f"{(cm.get('content','') or '')[:120]} (deadline={cm.get('deadline','?')})"
            )

    if pack.risks:
        lines.append("\n## 风险 (risks)")
        for r in pack.risks[:8]:
            lines.append(
                f"[risk:{r['id']}] {r.get('title','?')} · sev={r.get('severity','?')}: "
                f"{(r.get('description','') or '')[:100]}"
            )

    if pack.clarifications:
        lines.append("\n## 待澄清 (clarifications)")
        for cl in pack.clarifications[:8]:
            lines.append(f"[clarification:{cl['id']}] {cl.get('question','')[:120]}")

    if pack.external_evidence:
        lines.append("\n## 外部证据 (external_evidence)")
        for e in pack.external_evidence[:8]:
            lines.append(
                f"[external:{e['id']}] {e.get('title','')[:80]} · "
                f"{e.get('source_tier','?')} · {e.get('relation_to_internal','?')}"
            )

    if pack.data_gaps:
        lines.append("\n## 数据缺口 (data_gaps)")
        for g in pack.data_gaps[:6]:
            lines.append(
                f"[gap:{g['id']}] {g.get('gap_type','?')}: {g.get('subject','')[:50]} — "
                f"{g.get('suggested_action','')[:80]}"
            )

    if pack.approvals:
        lines.append("\n## 待审批 (approvals)")
        for a in pack.approvals[:5]:
            lines.append(f"[approval:{a['id']}] {a.get('action_type','?')}")

    text = "\n".join(lines)
    return text[:max_chars]


def summarize_for_api_response(pack: CompanyBrainContextPack) -> dict:
    """给 API 返回 evidence_summary 用 (前端展示)."""
    return {
        "task_type": pack.task_type,
        "client_id": pack.client_id,
        "evidence_summary": pack.evidence_summary,
        "uncertainty_summary": pack.uncertainty_summary,
        "recommended_actions": pack.recommended_actions,
        "used_tables": pack.used_tables,
        "single_file_only": (
            len(pack.used_tables) <= 1 and not pack.contracts and not pack.files
        ),
    }
