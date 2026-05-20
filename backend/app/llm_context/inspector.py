"""ContextInspector · 查看历史 prompt log

用法:
    insp = ContextInspector(db)
    recent = insp.last_n(n=10)                           # 最近 10 次
    for_client = insp.for_client("client_a", n=20)       # 某 client 最近 20 次
    by_intent = insp.by_intent("narrative", n=50)        # 某 intent 最近 50 次
    failures = insp.recent_failures(n=20)                # 最近 20 次失败

debug 场景:用户说"那个 narrative 写得不对",你想看上次 LLM 看到了什么 →
    last = insp.last_for_client("client_a", intent="narrative")
    print(last.system_text)
    print(last.prompt_text)
    print(last.output_text)
"""
from __future__ import annotations

import json
from typing import Any

from .types import PromptLogEntry


def _row_to_entry(row: Any) -> PromptLogEntry:
    raw_meta = row["metadata_json"] or "{}"
    try:
        metadata = json.loads(raw_meta)
    except json.JSONDecodeError:
        metadata = {}
    return PromptLogEntry(
        id=str(row["id"]),
        intent=str(row["intent"] or ""),
        client_id=str(row["client_id"]) if row["client_id"] else None,
        user_id=str(row["user_id"]) if row["user_id"] else None,
        system_text=str(row["system_text"] or ""),
        prompt_text=str(row["prompt_text"] or ""),
        output_text=str(row["output_text"] or ""),
        duration_ms=float(row["duration_ms"] or 0),
        tokens_used=int(row["tokens_used"] or 0),
        model_id=str(row["model_id"] or ""),
        error=str(row["error"] or ""),
        score=float(row["score"]) if row["score"] is not None else None,
        score_note=str(row["score_note"] or ""),
        metadata=metadata if isinstance(metadata, dict) else {},
        created_at=str(row["created_at"] or ""),
    )


class ContextInspector:
    def __init__(self, db: Any):
        self._db = db

    def last_n(self, n: int = 10) -> list[PromptLogEntry]:
        rows = self._db.fetchall(
            "SELECT * FROM prompt_log ORDER BY created_at DESC LIMIT ?",
            (int(n),),
        )
        return [_row_to_entry(r) for r in rows]

    def for_client(self, client_id: str, *, n: int = 10) -> list[PromptLogEntry]:
        if not client_id:
            return []
        rows = self._db.fetchall(
            "SELECT * FROM prompt_log WHERE client_id = ? ORDER BY created_at DESC LIMIT ?",
            (client_id, int(n)),
        )
        return [_row_to_entry(r) for r in rows]

    def by_intent(self, intent: str, *, n: int = 10) -> list[PromptLogEntry]:
        rows = self._db.fetchall(
            "SELECT * FROM prompt_log WHERE intent = ? ORDER BY created_at DESC LIMIT ?",
            (intent, int(n)),
        )
        return [_row_to_entry(r) for r in rows]

    def last_for_client(self, client_id: str, *, intent: str | None = None) -> PromptLogEntry | None:
        if intent:
            row = self._db.fetchone(
                "SELECT * FROM prompt_log WHERE client_id = ? AND intent = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (client_id, intent),
            )
        else:
            row = self._db.fetchone(
                "SELECT * FROM prompt_log WHERE client_id = ? ORDER BY created_at DESC LIMIT 1",
                (client_id,),
            )
        return _row_to_entry(row) if row else None

    def recent_failures(self, n: int = 20) -> list[PromptLogEntry]:
        rows = self._db.fetchall(
            "SELECT * FROM prompt_log WHERE error != '' ORDER BY created_at DESC LIMIT ?",
            (int(n),),
        )
        return [_row_to_entry(r) for r in rows]

    def stats_by_intent(self) -> list[dict]:
        rows = self._db.fetchall(
            """
            SELECT intent, COUNT(*) AS total,
                   AVG(duration_ms) AS avg_ms,
                   AVG(tokens_used) AS avg_tokens,
                   SUM(CASE WHEN error != '' THEN 1 ELSE 0 END) AS failures
            FROM prompt_log GROUP BY intent ORDER BY total DESC
            """
        )
        return [
            {
                "intent": str(r["intent"]),
                "total": int(r["total"]),
                "avg_ms": round(float(r["avg_ms"] or 0), 1),
                "avg_tokens": round(float(r["avg_tokens"] or 0), 1),
                "failures": int(r["failures"]),
            }
            for r in rows
        ]


def inspect_recent_prompts(db: Any, n: int = 10) -> list[PromptLogEntry]:
    return ContextInspector(db).last_n(n)
