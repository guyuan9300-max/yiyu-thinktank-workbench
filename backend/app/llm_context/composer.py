"""ContextComposer · 把业务数据装配成给 LLM 的 prompt

设计原则:
1. 输入是 intent + client_id(+ user_id),输出是 LLMContext(完整 prompt)
2. ContextComposer 通过 Repository 读数据,绝不裸 SQL
3. 不同 intent 装载不同 section(narrative 装 persons+events;qa 装 chat history)
4. token 估算 + 触发裁剪(避免超过模型限制)

Week 2 雏形:只先支持 'narrative' intent,其他 intent stub("not implemented")。
Week 3-4 接 Repository(W2-C 的 client/event_line/task Repository 就位后)。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .types import LLMContext, PromptIntent


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _estimate_tokens(text: str) -> int:
    """粗略估算:中文 ~1.5 字符/token,英文 ~4 字符/token,平均 3"""
    return max(1, len(text) // 3)


class ContextComposer:
    """v2.1 LLM Context 装配器 · SSOT 走 Repository,不裸 SQL"""

    def __init__(self, db: Any):
        self._db = db

    def compose(
        self,
        *,
        intent: PromptIntent,
        client_id: str | None = None,
        user_id: str | None = None,
        max_tokens: int = 4000,
    ) -> LLMContext:
        if intent == "narrative":
            return self._compose_narrative(client_id=client_id, user_id=user_id, max_tokens=max_tokens)
        if intent == "test_intent":
            return self._compose_test(client_id=client_id, user_id=user_id, max_tokens=max_tokens)
        # 其他 intent stub
        return self._compose_stub(intent=intent, client_id=client_id, user_id=user_id)

    # ─────────────────────────────────────────────────────────────────────
    # narrative intent · Week 2 雏形实现
    # ─────────────────────────────────────────────────────────────────────

    def _compose_narrative(
        self,
        *,
        client_id: str | None,
        user_id: str | None,
        max_tokens: int,
    ) -> LLMContext:
        if not client_id:
            return self._compose_stub(intent="narrative", client_id=None, user_id=user_id,
                                      reason="narrative intent requires client_id")

        sections: list[str] = []
        body_parts: list[str] = []

        # 1. client header(通过 SQL view v_active_clients,SSOT 守卫)
        client_row = self._db.fetchone(
            "SELECT id, name, alias, domain, stage FROM v_active_clients WHERE id = ?",
            (client_id,),
        )
        if not client_row:
            # client 不存在或已 frozen
            return self._compose_stub(
                intent="narrative", client_id=client_id, user_id=user_id,
                reason=f"client {client_id} not in v_active_clients (frozen or missing)",
            )

        body_parts.append(
            f"# 客户 · {client_row['name']}\n"
            f"- 别名:{client_row['alias'] or '(无)'}\n"
            f"- 领域:{client_row['domain']}\n"
            f"- 阶段:{client_row['stage']}\n"
        )
        sections.append("client_header")

        # 2. active event lines(通过 v_active_event_lines)
        event_rows = self._db.fetchall(
            "SELECT name, stage, summary, next_step FROM v_active_event_lines "
            "WHERE primary_client_id = ? ORDER BY updated_at DESC LIMIT 10",
            (client_id,),
        )
        if event_rows:
            event_lines = ["\n## 进行中的事件线\n"]
            for row in event_rows:
                event_lines.append(
                    f"- **{row['name']}**(阶段:{row['stage'] or '未定'})"
                )
                if row['summary']:
                    event_lines.append(f"  {row['summary']}")
                if row['next_step']:
                    event_lines.append(f"  下一步:{row['next_step']}")
            body_parts.append("\n".join(event_lines))
            sections.append("active_events")

        # 3. pending tasks(通过 v_pending_tasks)
        task_rows = self._db.fetchall(
            "SELECT title, priority, ddl FROM v_pending_tasks "
            "WHERE client_id = ? ORDER BY ddl ASC LIMIT 5",
            (client_id,),
        )
        if task_rows:
            task_lines = ["\n## 待办任务\n"]
            for row in task_rows:
                ddl = row['ddl'] or '无截止'
                task_lines.append(f"- {row['title']}(优先级 {row['priority']},截止 {ddl})")
            body_parts.append("\n".join(task_lines))
            sections.append("pending_tasks")

        system_text = (
            "你是益语智库的客户叙事助手。基于下面的事实材料,生成一段简洁、客观、"
            "可溯源的客户叙事。不要编造材料里没有的事实,不要添加情感修辞。"
        )
        prompt_text = "\n".join(body_parts)

        # 触发裁剪(粗略):超过 max_tokens 就保留 client_header + active_events,去掉 tasks
        truncated = False
        if _estimate_tokens(prompt_text) > max_tokens and "pending_tasks" in sections:
            sections = [s for s in sections if s != "pending_tasks"]
            body_parts = body_parts[:-1]
            prompt_text = "\n".join(body_parts)
            truncated = True

        return LLMContext(
            intent="narrative",
            client_id=client_id,
            user_id=user_id,
            system_text=system_text,
            prompt_text=prompt_text,
            sections_included=tuple(sections),
            token_estimate=_estimate_tokens(prompt_text),
            truncated=truncated,
            composed_at=_now_iso(),
        )

    # ─────────────────────────────────────────────────────────────────────
    # 测试 intent
    # ─────────────────────────────────────────────────────────────────────

    def _compose_test(
        self,
        *,
        client_id: str | None,
        user_id: str | None,
        max_tokens: int,
    ) -> LLMContext:
        text = f"test prompt for client={client_id} user={user_id}"
        return LLMContext(
            intent="test_intent",
            client_id=client_id,
            user_id=user_id,
            system_text="test system",
            prompt_text=text,
            sections_included=("test",),
            token_estimate=_estimate_tokens(text),
            truncated=False,
            composed_at=_now_iso(),
        )

    # ─────────────────────────────────────────────────────────────────────
    # stub:未实现的 intent
    # ─────────────────────────────────────────────────────────────────────

    def _compose_stub(
        self,
        *,
        intent: str,
        client_id: str | None,
        user_id: str | None,
        reason: str = "intent not yet implemented in Week 2 prototype",
    ) -> LLMContext:
        return LLMContext(
            intent=intent,
            client_id=client_id,
            user_id=user_id,
            system_text="",
            prompt_text="",
            sections_included=(),
            token_estimate=0,
            truncated=False,
            composed_at=_now_iso(),
        )


def compose_context(
    db: Any,
    *,
    intent: PromptIntent,
    client_id: str | None = None,
    user_id: str | None = None,
    max_tokens: int = 4000,
) -> LLMContext:
    """函数式入口"""
    return ContextComposer(db).compose(
        intent=intent, client_id=client_id, user_id=user_id, max_tokens=max_tokens,
    )
