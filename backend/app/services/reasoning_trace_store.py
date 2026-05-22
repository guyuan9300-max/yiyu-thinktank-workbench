"""v2.2 F2.7 (N3 A3) · ReasoningTraceStore — provenance + AI 推理链路追溯

服务: V2.2_NORTH_STAR.md N3 A3 + N2 信息商

当 AI (LLM extractor) 写一条 atomic_fact / key_decision / org_event 时,
应该顺手往 reasoning_traces 表写一行, 记录:
- 用了哪些 v2_documents / chunks / 上游 facts 作为输入
- 跑了什么 prompt + 模型
- 怎么从碎片推出这条结论 (reasoning steps)
- 触发了 supersede / conflict / complement / none

价值:
1. 用户发现 AI 抽错 → 查 reasoning_trace_id 立即定位
2. 3.0 AI Memory 能基于 reasoning_traces 学"哪些推理路径靠谱"
3. event_log 只记"发生了什么", reasoning_traces 记"为什么发生" (互补)

用法 (LLM extractor 视角, F2.1 实施时接入):

    store = ReasoningTraceStore(db)
    # 1. 开始一次推理
    trace_id = store.start(
        ai_session_id="ai_sess_001",
        output_entity_type="atomic_fact",
        input_doc_ids=["doc_519"],
        input_chunk_ids=["chunk_519_3"],
        prompt_summary="抽取张真在 5/19 会议的角色变化",
        model_name="doubao-seed",
    )
    # 2. 跑 LLM ... 得到结果
    # 3. 用 IngestPipeline 写 atomic_fact, 拿 fact_id
    # 4. 关联回去 + 标记 completed
    store.complete(
        trace_id,
        output_entity_id=fact_id,
        reasoning_steps=[
            "段落 3 说'张真接任法人代表'",
            "段落 5 确认'5/19 决议生效'",
            "结论: 张真.角色 = 法人代表, 时间锚 5/19",
        ],
        output_summary="张真接任日慈法人代表",
        confidence=0.92,
        triggered_update_relation="supersedes",
    )

设计选择:
- 不存全 prompt (避免大字段重复), 通过 prompt_log_id 关联 llm_context.prompt_log
- reasoning_steps_json 是 list[str], 让 AI 自己描述推理链
- 失败 (LLM timeout/error) 时仍写一条 trace, status='failed' + error_message
"""
from __future__ import annotations

import json
import re
import sqlite3
import uuid
from dataclasses import dataclass


def _sanitize_error_for_storage(error_message: str) -> str:
    """P1-5: 写库 / 写日志前剥掉 LLM provider 错误响应体里的潜在 secret.

    豆包 / 通义 / OpenAI / Anthropic 等 provider 错误 body 可能含:
    - "Authorization: Bearer ey..." 或 "Bearer sk-..."
    - "api_key=xxx" / "x-api-key: xxx"
    - 完整 Bearer token / sk-xxx / pk_xxx / volc_xxx 前缀
    - request_id 等可追溯标识
    """
    if not error_message:
        return ""
    s = str(error_message)
    patterns = [
        (r"(?i)Bearer\s+[A-Za-z0-9_\-\.=+/]+", "Bearer [redacted]"),
        (r"(?i)Authorization\s*:\s*\S+", "Authorization: [redacted]"),
        (r"(?i)x[\-_]api[\-_]key\s*[:=]\s*[A-Za-z0-9_\-]+", "x-api-key: [redacted]"),
        (r"(?i)api[\-_]key\s*[:=]\s*[A-Za-z0-9_\-]+", "api_key=[redacted]"),
        (r"(?<![A-Za-z0-9_])sk-[A-Za-z0-9_\-]{20,}", "sk-[redacted]"),
        (r"(?<![A-Za-z0-9_])volc_[A-Za-z0-9_\-]{20,}", "volc_[redacted]"),
        (r"(?<![A-Za-z0-9_])eyJ[A-Za-z0-9_\-\.]{20,}", "eyJ[redacted-JWT]"),
    ]
    for pat, repl in patterns:
        s = re.sub(pat, repl, s)
    return s[:1000]
from datetime import datetime, timezone
from typing import Any, Literal, Protocol


class _DbLike(Protocol):
    def fetchone(self, query: str, params: tuple = ()) -> sqlite3.Row | None: ...
    def fetchall(self, query: str, params: tuple = ()) -> list[sqlite3.Row]: ...
    def execute(self, query: str, params: tuple = ()) -> None: ...


OutputEntityType = Literal["atomic_fact", "key_decision", "org_event", "task"]
TraceStatus = Literal["pending", "completed", "failed", "reverted"]


@dataclass(frozen=True)
class ReasoningTrace:
    id: str
    ai_session_id: str
    output_entity_type: str
    output_entity_id: str | None
    input_doc_ids: list[str]
    input_chunk_ids: list[str]
    input_fact_ids: list[str]
    prompt_summary: str
    prompt_log_id: str | None
    model_name: str
    model_version: str
    reasoning_steps: list[str]
    output_summary: str
    confidence: float
    triggered_update_relation: str
    started_at: str
    completed_at: str | None
    duration_ms: int | None
    status: str
    error_message: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_trace(row: Any) -> ReasoningTrace:
    return ReasoningTrace(
        id=str(row["id"]),
        ai_session_id=str(row["ai_session_id"]),
        output_entity_type=str(row["output_entity_type"]),
        output_entity_id=str(row["output_entity_id"]) if row["output_entity_id"] else None,
        input_doc_ids=json.loads(row["input_doc_ids_json"] or "[]"),
        input_chunk_ids=json.loads(row["input_chunk_ids_json"] or "[]"),
        input_fact_ids=json.loads(row["input_fact_ids_json"] or "[]"),
        prompt_summary=str(row["prompt_summary"] or ""),
        prompt_log_id=str(row["prompt_log_id"]) if row["prompt_log_id"] else None,
        model_name=str(row["model_name"] or ""),
        model_version=str(row["model_version"] or ""),
        reasoning_steps=json.loads(row["reasoning_steps_json"] or "[]"),
        output_summary=str(row["output_summary"] or ""),
        confidence=float(row["confidence"] or 0.0),
        triggered_update_relation=str(row["triggered_update_relation"]),
        started_at=str(row["started_at"]),
        completed_at=str(row["completed_at"]) if row["completed_at"] else None,
        duration_ms=int(row["duration_ms"]) if row["duration_ms"] is not None else None,
        status=str(row["status"]),
        error_message=str(row["error_message"] or ""),
    )


class ReasoningTraceStore:
    def __init__(self, db: _DbLike):
        self._db = db
        self._started_at_cache: dict[str, datetime] = {}  # trace_id → start time for duration calc

    def start(
        self,
        *,
        ai_session_id: str,
        output_entity_type: OutputEntityType,
        input_doc_ids: list[str] | None = None,
        input_chunk_ids: list[str] | None = None,
        input_fact_ids: list[str] | None = None,
        prompt_summary: str = "",
        prompt_log_id: str | None = None,
        model_name: str = "",
        model_version: str = "",
    ) -> str:
        """开始一次 AI 推理, 返回 trace_id。

        后续 LLM 调用完成后调 complete() 或 fail()。
        """
        trace_id = f"rt_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        self._started_at_cache[trace_id] = now
        self._db.execute(
            """
            INSERT INTO reasoning_traces (
                id, ai_session_id, output_entity_type, output_entity_id,
                input_doc_ids_json, input_chunk_ids_json, input_fact_ids_json,
                prompt_summary, prompt_log_id, model_name, model_version,
                reasoning_steps_json, output_summary,
                confidence, triggered_update_relation,
                started_at, status
            ) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, '[]', '', 0.5, 'none', ?, 'pending')
            """,
            (
                trace_id, ai_session_id, output_entity_type,
                json.dumps(input_doc_ids or [], ensure_ascii=False),
                json.dumps(input_chunk_ids or [], ensure_ascii=False),
                json.dumps(input_fact_ids or [], ensure_ascii=False),
                prompt_summary[:500],  # 截断防过长
                prompt_log_id, model_name, model_version,
                now.isoformat(),
            ),
        )
        return trace_id

    def complete(
        self,
        trace_id: str,
        *,
        output_entity_id: str | None,
        reasoning_steps: list[str],
        output_summary: str,
        confidence: float = 0.5,
        triggered_update_relation: Literal["none", "conflict", "supersedes", "complement"] = "none",
    ) -> None:
        """标记成功 + 回填 output_entity_id + 推理痕迹"""
        now = datetime.now(timezone.utc)
        # 计算 duration
        start = self._started_at_cache.get(trace_id)
        duration_ms = None
        if start:
            duration_ms = int((now - start).total_seconds() * 1000)

        self._db.execute(
            """
            UPDATE reasoning_traces
            SET output_entity_id = ?,
                reasoning_steps_json = ?,
                output_summary = ?,
                confidence = ?,
                triggered_update_relation = ?,
                completed_at = ?,
                duration_ms = ?,
                status = 'completed'
            WHERE id = ?
            """,
            (
                output_entity_id,
                json.dumps(reasoning_steps, ensure_ascii=False),
                output_summary[:1000],
                confidence,
                triggered_update_relation,
                now.isoformat(),
                duration_ms,
                trace_id,
            ),
        )
        self._started_at_cache.pop(trace_id, None)

    def fail(
        self,
        trace_id: str,
        *,
        error_message: str,
    ) -> None:
        """标记失败 (LLM timeout / parse error / 内容拒绝等)"""
        now = datetime.now(timezone.utc)
        start = self._started_at_cache.get(trace_id)
        duration_ms = None
        if start:
            duration_ms = int((now - start).total_seconds() * 1000)
        # P1-5 修复: 旧版 error_message[:1000] 直接写库.
        # AiInvocationError detail 会拼接 LLM provider 错误响应体,
        # 豆包/通义等 provider 错误响应有时含 Bearer token / api_key=... / request_id
        # 可用于重放或追溯. 写库前正则脱敏掉常见 secret pattern.
        self._db.execute(
            """
            UPDATE reasoning_traces
            SET completed_at = ?, duration_ms = ?, status = 'failed', error_message = ?
            WHERE id = ?
            """,
            (now.isoformat(), duration_ms, _sanitize_error_for_storage(error_message), trace_id),
        )
        self._started_at_cache.pop(trace_id, None)

    def revert(self, trace_id: str) -> None:
        """用户撤销了 AI 这次推理 (跟 event_log.reversed_at 一致, 爱马仕保修)"""
        self._db.execute(
            "UPDATE reasoning_traces SET status = 'reverted' WHERE id = ?",
            (trace_id,),
        )

    def get(self, trace_id: str) -> ReasoningTrace | None:
        row = self._db.fetchone(
            "SELECT * FROM reasoning_traces WHERE id = ?", (trace_id,)
        )
        return _row_to_trace(row) if row else None

    def list_for_entity(
        self, output_entity_type: str, output_entity_id: str,
    ) -> list[ReasoningTrace]:
        """用户在 UI 上点一条 fact / decision 想看 'AI 怎么推出来的' → 调这个"""
        rows = self._db.fetchall(
            """
            SELECT * FROM reasoning_traces
            WHERE output_entity_type = ? AND output_entity_id = ?
            ORDER BY started_at DESC
            """,
            (output_entity_type, output_entity_id),
        )
        return [_row_to_trace(r) for r in rows]

    def list_session_recent(
        self, ai_session_id: str, limit: int = 20,
    ) -> list[ReasoningTrace]:
        """看一个 AI session 最近做了什么 (类似 git log)"""
        rows = self._db.fetchall(
            """
            SELECT * FROM reasoning_traces
            WHERE ai_session_id = ?
            ORDER BY started_at DESC LIMIT ?
            """,
            (ai_session_id, limit),
        )
        return [_row_to_trace(r) for r in rows]

    def list_failed_recent(self, limit: int = 50) -> list[ReasoningTrace]:
        """诊断: AI 最近失败了哪些, 看是否有 prompt 设计问题"""
        rows = self._db.fetchall(
            """
            SELECT * FROM reasoning_traces
            WHERE status = 'failed'
            ORDER BY started_at DESC LIMIT ?
            """,
            (limit,),
        )
        return [_row_to_trace(r) for r in rows]


def get_reasoning_trace_store(db: _DbLike) -> ReasoningTraceStore:
    return ReasoningTraceStore(db)
