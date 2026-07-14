"""智能文件导入(故事线导入)服务模块.

== 设计原则 ==
用户讲故事 + 挂文件 → LLM 解析 → 结构化数据(entity/事件/承诺/风险/文件分类)
→ 一次性 commit 到数据中心.

替代"批量拖文件让机器猜"的混乱路径,把"叙述者大脑里"的隐性知识
(谁产出/谁评价/为什么找这个对标) 显式捕捉为一等数据.

== 数据流 ==
1. 创建会话 (绑定 client + event_line + narrator)
2. 上传文件到 staging pool
3. 添加 chunk (讲述文本 + 挂载文件 id 列表)
4. 异步触发 LLM 解析 chunk → parsed_json
5. 重复 3-4 直到用户讲完
6. (M3) preview → commit → 落库
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.async_job_scope import (
    AsyncJobScopeError,
    load_persisted_job_workspace_context,
    resolve_client_workspace_context,
)

logger = logging.getLogger(__name__)


VALID_ROLES = (
    "client_owned",
    "partner_submission",
    "yiyu_advisory",
    "external_reference",
    "policy_industry",
    "unknown",
)


# ------------------------ 工具 ------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _safe_json_loads(text: str | None, default: Any) -> Any:
    """JSON 解析容错版. 解析失败时 log warning 后返回 default,
    避免 UI 静默拿到空对象但又没有任何错误线索."""
    if not text:
        return default
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("[smart_file_import] _safe_json_loads failed, fallback to default: %s", exc)
        return default


def _row_to_dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}
    return dict(row)


class SmartImportScopeNotFound(ValueError):
    """Direct-id smart-import object is absent from the caller's frozen sandbox."""


def _require_sandbox_id(db: Any, sandbox_id: str) -> str:
    normalized = str(sandbox_id or "").strip()
    if not normalized:
        raise SmartImportScopeNotFound("smart import object not found")
    row = db.fetchone("SELECT id FROM sandboxes WHERE id = ?", (normalized,))
    if not row:
        raise SmartImportScopeNotFound("smart import object not found")
    return normalized


def _require_client_in_sandbox(db: Any, client_id: str, sandbox_id: str) -> Any:
    row = db.fetchone(
        "SELECT * FROM clients WHERE id = ? AND COALESCE(sandbox_id, '') = ?",
        (client_id, sandbox_id),
    )
    if not row:
        raise SmartImportScopeNotFound("client not found")
    return row


def _require_event_line_in_sandbox(db: Any, event_line_id: str, sandbox_id: str) -> Any:
    row = db.fetchone(
        "SELECT * FROM event_lines WHERE id = ? AND COALESCE(sandbox_id, '') = ?",
        (event_line_id, sandbox_id),
    )
    if not row:
        raise SmartImportScopeNotFound("event line not found")
    return row


_SESSION_SCOPE_INTEGRITY_SQL = """
    AND (
        COALESCE(s.client_id, '') = ''
        OR EXISTS (
            SELECT 1 FROM clients c
            WHERE c.id = s.client_id
              AND COALESCE(c.sandbox_id, '') = COALESCE(s.sandbox_id, '')
        )
    )
    AND (
        COALESCE(s.project_event_line_id, '') = ''
        OR EXISTS (
            SELECT 1 FROM event_lines e
            WHERE e.id = s.project_event_line_id
              AND COALESCE(e.sandbox_id, '') = COALESCE(s.sandbox_id, '')
        )
    )
"""


def require_session_in_sandbox(db: Any, session_id: str, sandbox_id: str) -> Any:
    """Fail closed unless the session and every bound parent stay in one sandbox."""
    normalized = _require_sandbox_id(db, sandbox_id)
    row = db.fetchone(
        """
        SELECT s.*
        FROM import_story_sessions s
        WHERE s.id = ?
          AND COALESCE(s.sandbox_id, '') = ?
        """ + _SESSION_SCOPE_INTEGRITY_SQL,
        (session_id, normalized),
    )
    if not row:
        raise SmartImportScopeNotFound("session not found")
    return row


def require_file_in_sandbox(db: Any, file_id: str, sandbox_id: str) -> Any:
    normalized = _require_sandbox_id(db, sandbox_id)
    row = db.fetchone(
        """
        SELECT f.*
        FROM import_staged_files f
        JOIN import_story_sessions s ON s.id = f.session_id
        WHERE f.id = ?
          AND COALESCE(s.sandbox_id, '') = ?
        """ + _SESSION_SCOPE_INTEGRITY_SQL,
        (file_id, normalized),
    )
    if not row:
        raise SmartImportScopeNotFound("staged file not found")
    return row


def require_chunk_in_sandbox(db: Any, chunk_id: str, sandbox_id: str) -> Any:
    normalized = _require_sandbox_id(db, sandbox_id)
    row = db.fetchone(
        """
        SELECT ch.*
        FROM import_story_chunks ch
        JOIN import_story_sessions s ON s.id = ch.session_id
        WHERE ch.id = ?
          AND COALESCE(s.sandbox_id, '') = ?
        """ + _SESSION_SCOPE_INTEGRITY_SQL,
        (chunk_id, normalized),
    )
    if not row:
        raise SmartImportScopeNotFound("chunk not found")
    return row


# ------------------------ Session CRUD ------------------------


def create_session(
    db: Any,
    *,
    sandbox_id: str,
    narrator_user_id: str,
    client_id: str | None = None,
    project_event_line_id: str | None = None,
    title: str = "",
) -> str:
    """新建会话, 返回 session id."""
    sandbox_id = _require_sandbox_id(db, sandbox_id)
    if client_id:
        _require_client_in_sandbox(db, client_id, sandbox_id)
    if project_event_line_id:
        _require_event_line_in_sandbox(db, project_event_line_id, sandbox_id)
    session_id = _new_id("is")
    now = _now()
    db.execute(
        """INSERT INTO import_story_sessions
           (id, sandbox_id, client_id, project_event_line_id, narrator_user_id, title,
            status, total_chunks, total_files, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, 'drafting', 0, 0, ?, ?)""",
        (
            session_id,
            sandbox_id,
            client_id or None,
            project_event_line_id or None,
            narrator_user_id or "",
            title or "未命名会话",
            now, now,
        ),
    )
    try:
        db.conn.commit()
    except Exception:
        pass
    return session_id


def get_session(db: Any, session_id: str, *, sandbox_id: str) -> dict[str, Any]:
    """返回 session 完整状态(含 chunks + staged_files), 用于恢复或预览."""
    row = require_session_in_sandbox(db, session_id, sandbox_id)
    session = _row_to_dict(row)
    # parsed_json 字段返回时 hydrate
    chunks_rows = db.fetchall(
        "SELECT * FROM import_story_chunks WHERE session_id = ? ORDER BY sequence ASC",
        (session_id,),
    )
    chunks: list[dict[str, Any]] = []
    for cr in chunks_rows:
        cd = _row_to_dict(cr)
        cd["parsed"] = _safe_json_loads(cd.get("parsed_json", "{}"), {})
        chunks.append(cd)
    files_rows = db.fetchall(
        "SELECT * FROM import_staged_files WHERE session_id = ? ORDER BY upload_at ASC",
        (session_id,),
    )
    files = [_row_to_dict(r) for r in files_rows]
    return {
        "session": session,
        "chunks": chunks,
        "staged_files": files,
    }


def update_session(
    db: Any, session_id: str,
    *,
    sandbox_id: str,
    client_id: str | None = None,
    project_event_line_id: str | None = None,
    title: str | None = None,
) -> None:
    sandbox_id = _require_sandbox_id(db, sandbox_id)
    require_session_in_sandbox(db, session_id, sandbox_id)
    if client_id:
        _require_client_in_sandbox(db, client_id, sandbox_id)
    if project_event_line_id:
        _require_event_line_in_sandbox(db, project_event_line_id, sandbox_id)
    updates: list[str] = []
    params: list[Any] = []
    if client_id is not None:
        updates.append("client_id = ?")
        params.append(client_id or None)
    if project_event_line_id is not None:
        updates.append("project_event_line_id = ?")
        params.append(project_event_line_id or None)
    if title is not None:
        updates.append("title = ?")
        params.append(title)
    if not updates:
        return
    updates.append("updated_at = ?")
    params.append(_now())
    params.extend((session_id, sandbox_id))
    db.execute(
        f"UPDATE import_story_sessions SET {', '.join(updates)} "
        "WHERE id = ? AND COALESCE(sandbox_id, '') = ?",
        tuple(params),
    )
    try:
        db.conn.commit()
    except Exception:
        pass


def discard_session(db: Any, session_id: str, *, sandbox_id: str) -> None:
    """标记 session 为 discarded (软删, 文件留 staging 等清理 job 处理)."""
    sandbox_id = _require_sandbox_id(db, sandbox_id)
    require_session_in_sandbox(db, session_id, sandbox_id)
    db.execute(
        "UPDATE import_story_sessions SET status='discarded', updated_at=? "
        "WHERE id = ? AND COALESCE(sandbox_id, '') = ?",
        (_now(), session_id, sandbox_id),
    )
    try:
        db.conn.commit()
    except Exception:
        pass


# ------------------------ Staged Files ------------------------


def _staging_dir(data_dir: str | Path, session_id: str) -> Path:
    root = Path(data_dir) / "smart_import_staging" / session_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def upload_staged_file(
    db: Any,
    *,
    sandbox_id: str,
    session_id: str,
    filename: str,
    content: bytes,
    mime_type: str = "",
    data_dir: str | Path = "/tmp",
) -> dict[str, Any]:
    """把上传文件写到 staging 目录, 记 staged_files 表, 返回 file 元数据."""
    sandbox_id = _require_sandbox_id(db, sandbox_id)
    require_session_in_sandbox(db, session_id, sandbox_id)
    if not content:
        raise ValueError("upload content is empty")

    file_id = _new_id("isf")
    safe_filename = filename.replace("/", "_").replace("\\", "_") or "uploaded"
    storage = _staging_dir(data_dir, session_id) / f"{file_id}_{safe_filename}"
    storage.write_bytes(content)

    now = _now()
    db.execute(
        """INSERT INTO import_staged_files
           (id, session_id, original_filename, storage_path, size_bytes, mime_type, upload_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (file_id, session_id, safe_filename, str(storage), len(content), mime_type or "", now),
    )
    db.execute(
        "UPDATE import_story_sessions SET total_files = total_files + 1, updated_at = ? WHERE id = ?",
        (now, session_id),
    )
    try:
        db.conn.commit()
    except Exception:
        pass

    # 返回完整 SmartImportStagedFile 字段(跟 get_session 输出的 row 形状一致),
    # 避免前端读 assigned_chunk_id/role_override/document_id/document_inserted_at 时 undefined
    return {
        "id": file_id,
        "session_id": session_id,
        "original_filename": safe_filename,
        "storage_path": str(storage),
        "size_bytes": len(content),
        "mime_type": mime_type or "",
        "assigned_chunk_id": None,
        "role_override": None,
        "document_id": None,
        "document_inserted_at": None,
        "upload_at": now,
    }


def delete_staged_file(
    db: Any,
    file_id: str,
    *,
    sandbox_id: str,
    data_dir: str | Path,
) -> None:
    sandbox_id = _require_sandbox_id(db, sandbox_id)
    row = require_file_in_sandbox(db, file_id, sandbox_id)
    expected_root = (Path(data_dir) / "smart_import_staging" / row["session_id"]).resolve()
    storage_path = Path(str(row["storage_path"] or ""))
    resolved_storage = storage_path.resolve()
    try:
        resolved_storage.relative_to(expected_root)
    except ValueError as exc:
        raise ValueError("staged file path is outside its session directory") from exc

    db.execute("DELETE FROM import_staged_files WHERE id=?", (file_id,))
    db.execute(
        "UPDATE import_story_sessions SET total_files = MAX(0, total_files - 1), updated_at=? WHERE id=?",
        (_now(), row["session_id"]),
    )
    try:
        if row["storage_path"] and os.path.exists(storage_path):
            storage_path.unlink()
    except Exception:  # noqa: BLE001
        pass
    try:
        db.conn.commit()
    except Exception:
        pass


# ------------------------ Chunks ------------------------


def add_chunk(
    db: Any, ai: Any,
    *,
    sandbox_id: str,
    session_id: str,
    raw_text: str,
    file_ids: list[str] | None = None,
    auto_parse: bool = True,
) -> str:
    """新增一段, 返回 chunk_id. auto_parse=True 时立即同步触发 LLM 解析.

    file_ids 是这一段挂载的 staged_files id 列表, 会写入关联表 + 更新
    staged_files.assigned_chunk_id.
    """
    sandbox_id = _require_sandbox_id(db, sandbox_id)
    require_session_in_sandbox(db, session_id, sandbox_id)

    file_ids = list(dict.fromkeys(file_ids or []))
    for file_id in file_ids:
        file_row = require_file_in_sandbox(db, file_id, sandbox_id)
        if str(file_row["session_id"]) != session_id:
            raise ValueError("staged file and chunk must be in the same session")

    chunk_id = _new_id("ic")
    now = _now()
    # 序号 = 当前最大序号 + 1
    max_seq_row = db.fetchone(
        "SELECT COALESCE(MAX(sequence), -1) AS m FROM import_story_chunks WHERE session_id = ?",
        (session_id,),
    )
    next_seq = int(max_seq_row["m"]) + 1 if max_seq_row else 0

    db.execute(
        """INSERT INTO import_story_chunks
           (id, session_id, sequence, raw_text, parsed_json, parse_status,
            parse_error, user_edited_parsed, created_at, updated_at)
           VALUES (?, ?, ?, ?, '{}', 'pending', '', 0, ?, ?)""",
        (chunk_id, session_id, next_seq, raw_text or "", now, now),
    )
    # 挂文件
    for idx, fid in enumerate(file_ids):
        db.execute(
            """INSERT INTO import_story_chunk_files
               (chunk_id, staged_file_id, sequence_in_chunk, role_hint, created_at)
               VALUES (?, ?, ?, '', ?)""",
            (chunk_id, fid, idx, now),
        )
        db.execute(
            "UPDATE import_staged_files SET assigned_chunk_id = ? WHERE id = ? AND session_id = ?",
            (chunk_id, fid, session_id),
        )

    db.execute(
        "UPDATE import_story_sessions SET total_chunks = total_chunks + 1, updated_at = ? WHERE id = ?",
        (now, session_id),
    )
    try:
        db.conn.commit()
    except Exception:
        pass

    if auto_parse and raw_text.strip():
        try:
            parse_chunk(db, ai, chunk_id, sandbox_id=sandbox_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[smart-import] auto parse for chunk %s failed: %s", chunk_id, exc)

    return chunk_id


def update_chunk_text(
    db: Any,
    ai: Any,
    chunk_id: str,
    *,
    sandbox_id: str,
    raw_text: str,
    auto_parse: bool = True,
) -> None:
    sandbox_id = _require_sandbox_id(db, sandbox_id)
    require_chunk_in_sandbox(db, chunk_id, sandbox_id)
    db.execute(
        "UPDATE import_story_chunks SET raw_text=?, parse_status='pending', updated_at=? WHERE id=?",
        (raw_text, _now(), chunk_id),
    )
    try:
        db.conn.commit()
    except Exception:
        pass
    if auto_parse and raw_text.strip():
        try:
            parse_chunk(db, ai, chunk_id, sandbox_id=sandbox_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[smart-import] reparse chunk %s failed: %s", chunk_id, exc)


def patch_chunk_parsed(
    db: Any,
    chunk_id: str,
    new_parsed: dict,
    *,
    sandbox_id: str,
) -> None:
    """用户 inline 编辑某字段后, 用新的 parsed 整体覆盖 chunk.parsed_json.

    不调用 LLM。设 user_edited_parsed=1 标记此 chunk 已被人工修订过,
    以后即使重新解析也保留用户改动 (M5+ 处理覆盖策略, 这里先 simple)。
    """
    sandbox_id = _require_sandbox_id(db, sandbox_id)
    require_chunk_in_sandbox(db, chunk_id, sandbox_id)
    if not isinstance(new_parsed, dict):
        raise ValueError("parsed must be a JSON object")
    cleaned = _clean_parsed_output(new_parsed)
    db.execute(
        """UPDATE import_story_chunks SET parsed_json=?, parse_status='parsed',
           parse_error='', user_edited_parsed=1, updated_at=? WHERE id=?""",
        (json.dumps(cleaned, ensure_ascii=False), _now(), chunk_id),
    )
    try:
        db.conn.commit()
    except Exception:
        pass


def delete_chunk(db: Any, chunk_id: str, *, sandbox_id: str) -> None:
    sandbox_id = _require_sandbox_id(db, sandbox_id)
    row = require_chunk_in_sandbox(db, chunk_id, sandbox_id)
    # 文件 unassign 回 pool
    db.execute(
        "UPDATE import_staged_files SET assigned_chunk_id = NULL WHERE assigned_chunk_id = ?",
        (chunk_id,),
    )
    db.execute("DELETE FROM import_story_chunks WHERE id=?", (chunk_id,))
    db.execute(
        "UPDATE import_story_sessions SET total_chunks = MAX(0, total_chunks - 1), updated_at=? WHERE id=?",
        (_now(), row["session_id"]),
    )
    try:
        db.conn.commit()
    except Exception:
        pass


def assign_file_to_chunk(
    db: Any,
    *,
    sandbox_id: str,
    file_id: str,
    chunk_id: str | None,
) -> None:
    """把 staged file 挂到某 chunk (chunk_id=None → 取消挂载, 回 pool)."""
    sandbox_id = _require_sandbox_id(db, sandbox_id)
    file_row = require_file_in_sandbox(db, file_id, sandbox_id)
    if chunk_id:
        chunk_row = require_chunk_in_sandbox(db, chunk_id, sandbox_id)
        if chunk_row["session_id"] != file_row["session_id"]:
            raise ValueError("chunk and file not in same session")
    db.execute(
        "UPDATE import_staged_files SET assigned_chunk_id=? WHERE id=?",
        (chunk_id, file_id),
    )
    # 同步更新关联表
    db.execute("DELETE FROM import_story_chunk_files WHERE staged_file_id=?", (file_id,))
    if chunk_id:
        # 取当前 chunk 内最大 sequence + 1
        seq_row = db.fetchone(
            "SELECT COALESCE(MAX(sequence_in_chunk), -1) AS m FROM import_story_chunk_files WHERE chunk_id=?",
            (chunk_id,),
        )
        seq = int(seq_row["m"]) + 1 if seq_row else 0
        db.execute(
            "INSERT INTO import_story_chunk_files(chunk_id, staged_file_id, sequence_in_chunk, role_hint, created_at) "
            "VALUES (?, ?, ?, '', ?)",
            (chunk_id, file_id, seq, _now()),
        )
    try:
        db.conn.commit()
    except Exception:
        pass


# ------------------------ LLM Parsing ------------------------


_PARSE_PROMPT_TEMPLATE = """\
你是益语智库的项目档案整理助手。用户在做"智能文件导入" —— 他们讲述一段项目历史
并附上相关文件,你的任务是把讲述+文件结构化成 JSON,作为数据中心写入候选。

== 上下文 ==
客户: {client_name}
项目/事件线: {project_name}
本会话已有故事块摘要: {previous_summary}
本会话已识别的人物/机构: {known_entities}

== 本段讲述 (用户原文) ==
{raw_text}

== 本段挂载的文件 ==
{files_block}

== 全部未挂文件 (用于"叙述里隐式提到的文件"匹配) ==
{unassigned_block}

== 输出要求 ==
严格返回 JSON, 必须满足以下结构 (不允许 markdown / 解释):

{{
  "entities": [
    {{"name": "知合公益", "kind": "organization",
      "role_in_project": "合作方",
      "first_mention": true}},
    {{"name": "顾源源", "kind": "person",
      "role_in_project": "对接人",
      "first_mention": true}}
  ],
  "relationships": [
    {{"from": "知合公益", "to": "士平",
      "type": "合作提交方案",
      "description": "知合向士平提交项目方案"}},
    {{"from": "士平", "to": "顾源源",
      "type": "委托咨询",
      "description": "士平找顾源源咨询"}}
  ],
  "events": [
    {{"happened_at": "2017-02-10", "actor": "知合公益", "action": "提交方案",
      "target": "士平", "summary": "知合公益给士平提了 2017 年版本"}}
  ],
  "opinions": [
    {{"holder": "士平", "subject": "知合方案", "polarity": "negative",
      "raw_quote": "觉得糟糕"}}
  ],
  "files_classified": [
    {{"original_filename": "20170210知合公益青少年足球项目方案.pdf",
      "role": "partner_submission",
      "subject_entity_name": "知合公益",
      "evidence_tier": "first_party",
      "narrator_hint": "知合 2017 早期稿,资方不满意",
      "confidence": 0.9}}
  ],
  "files_suggested_to_attach": [
    {{"original_filename": "美好体育项目教师实践指南.pdf",
      "reason": "用户讲对标资料,这个文件名匹配"}}
  ],
  "commitments": [
    {{"committer": "益语", "recipient": "士平", "commitment_type": "delivery",
      "content": "提供督导服务", "deadline": null, "status": "pending"}}
  ],
  "risk_signals": [
    {{"title": "资方对合作方早期方案不满意", "severity": "medium",
      "description": "...", "subject": "知合公益"}}
  ],
  "open_questions": ["还有什么不清楚的事实"]
}}

== 关键规则(违反 = 解析废) ==

1. **entity.name 必须从原文一字不差复制**, 严禁同音/形近字替换。
   错误示例: 原文"顾源源" → 写成"顾源潺" ❌ ; 原文"红霞总" → 写成"红霞点" ❌

2. **entity.role_in_project 必须是 ≤8 字的短语**, 严禁塞整段事件描述。
   正确: "资助方"/"合作方"/"对接人"/"决策人"/"执行人"/"需求方"/"咨询服务"
   错误: "集团老板红霞总发起足球项目,由士平基金会推进..." ❌ (这是事件不是角色)
   错误: "未明确集团老板红霞总..." ❌ (说"未明确"就到这里, 后面什么都不接)
   推断不出来时, role_in_project 字段直接留空字符串 "", 不要写"未明确"

3. **relationships.type 必须是 ≤8 字的纯短语, 严禁内嵌箭头 →**。
   正确: "合作提交方案"/"委托咨询"/"上下级"/"导师学员"/"决策执行"/"资助监管"
   错误: "合作方→资方" ❌  错误: "需求方→对接人" ❌  错误: "决策人→执行方" ❌
   箭头由前端 from/to 字段表达, type 只写关系本身。

4. **relationships.from 和 to 都必须是 entities 数组里出现过的 name**,
   严禁出现没在 entities 里登记的新名字。

5. **events.happened_at 尽量给具体日期**(YYYY-MM-DD / YYYY-MM / YYYY);
   原文说"上周/上月/今年"就照搬原文, 不要瞎编日期。

6. entities 跟 known_entities 同名的复用名称, 不重新建。

7. 文件 role 必须是这 5 个之一: client_owned / partner_submission /
   yiyu_advisory / external_reference / policy_industry

8. evidence_tier 必须是: first_party / second_party / third_party

9. 不确定的字段, 数组留空。

10. 一个文件只允许出现在 files_classified 一次。

11. 严格忠实原文, 不要推断没说过的事。
"""


# ------------------------ 后处理: 兜底截断/清理 ------------------------


def _clean_parsed_output(parsed: dict) -> dict:
    """LLM 偶尔不守约,这里兜底截断长字段 + 清理嵌套箭头。

    - entity.role_in_project: 截断 ≤20 字; 单独是"未明确"的清空
    - relationships.type: 去掉 → 箭头, 截断 ≤15 字
    """
    if not isinstance(parsed, dict):
        return parsed
    for e in (parsed.get("entities") or []):
        if not isinstance(e, dict):
            continue
        role = str(e.get("role_in_project") or "").strip()
        # "未明确" 单独出现或带后缀 → 清空, 让前端能显示编辑入口
        if role in ("未明确", "未提及", "未说明"):
            e["role_in_project"] = ""
        elif role.startswith("未明确") or role.startswith("未提及"):
            # "未明确集团老板红霞总..." → 清空
            e["role_in_project"] = ""
        elif len(role) > 20:
            # 整段事件描述被塞进来了, 截断
            e["role_in_project"] = role[:20]
    for r in (parsed.get("relationships") or []):
        if not isinstance(r, dict):
            continue
        type_ = str(r.get("type") or "").strip()
        # 去嵌套箭头: "合作方→资方" → "合作方/资方"
        type_ = type_.replace("→", "/").replace("->", "/").replace("→", "/")
        if len(type_) > 15:
            type_ = type_[:15]
        r["type"] = type_
    return parsed


def _format_files_block(file_rows: list[dict[str, Any]]) -> str:
    if not file_rows:
        return "(本段无挂载文件)"
    lines = []
    for f in file_rows:
        size_kb = (f.get("size_bytes") or 0) / 1024
        lines.append(
            f"  - {f.get('original_filename', '<unknown>')} "
            f"(mime: {f.get('mime_type') or '?'}, {size_kb:.0f} KB)"
        )
    return "\n".join(lines)


def _gather_previous_summary(db: Any, session_id: str, current_chunk_id: str) -> str:
    rows = db.fetchall(
        """SELECT sequence, raw_text FROM import_story_chunks
           WHERE session_id = ? AND id != ?
           ORDER BY sequence ASC""",
        (session_id, current_chunk_id),
    )
    if not rows:
        return "(本会话第一段)"
    parts = []
    for r in rows:
        txt = str(r["raw_text"] or "").strip().replace("\n", " ")[:120]
        parts.append(f"第{int(r['sequence'])+1}段: {txt}")
    return "\n".join(parts)


def _gather_known_entities(db: Any, session_id: str) -> list[str]:
    rows = db.fetchall(
        "SELECT parsed_json FROM import_story_chunks WHERE session_id = ?",
        (session_id,),
    )
    names: set[str] = set()
    for r in rows:
        parsed = _safe_json_loads(r["parsed_json"], {})
        for e in (parsed.get("entities") or []):
            n = str(e.get("name", "")).strip()
            if n:
                names.add(n)
    return sorted(names)


_PARSE_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "entities": {"type": "ARRAY"},
        "relationships": {"type": "ARRAY"},
        "events": {"type": "ARRAY"},
        "opinions": {"type": "ARRAY"},
        "files_classified": {"type": "ARRAY"},
        "files_suggested_to_attach": {"type": "ARRAY"},
        "commitments": {"type": "ARRAY"},
        "risk_signals": {"type": "ARRAY"},
        "open_questions": {"type": "ARRAY"},
    },
    "required": ["entities", "events", "opinions", "files_classified"],
}


def parse_chunk(
    db: Any,
    ai: Any,
    chunk_id: str,
    *,
    sandbox_id: str,
) -> dict[str, Any]:
    """同步调 LLM 解析 chunk, 把结果写回 parsed_json."""
    sandbox_id = _require_sandbox_id(db, sandbox_id)
    chunk_row = require_chunk_in_sandbox(db, chunk_id, sandbox_id)
    session_row = require_session_in_sandbox(db, chunk_row["session_id"], sandbox_id)

    # 拉客户/项目名(可空)
    client_name = ""
    if session_row["client_id"]:
        c_row = db.fetchone(
            "SELECT name FROM clients WHERE id = ?", (session_row["client_id"],)
        )
        if c_row:
            client_name = str(c_row["name"] or "")
    project_name = ""
    if session_row["project_event_line_id"]:
        e_row = db.fetchone(
            "SELECT name FROM event_lines WHERE id = ?",
            (session_row["project_event_line_id"],),
        )
        if e_row:
            project_name = str(e_row["name"] or "")

    # 本段挂载文件 + 全 session 未挂文件
    attached_files = [_row_to_dict(r) for r in db.fetchall(
        """SELECT sf.* FROM import_staged_files sf
           JOIN import_story_chunk_files cf ON cf.staged_file_id = sf.id
           WHERE cf.chunk_id = ? ORDER BY cf.sequence_in_chunk ASC""",
        (chunk_id,),
    )]
    unassigned_files = [_row_to_dict(r) for r in db.fetchall(
        """SELECT * FROM import_staged_files
           WHERE session_id = ? AND assigned_chunk_id IS NULL""",
        (chunk_row["session_id"],),
    )]

    prompt = _PARSE_PROMPT_TEMPLATE.format(
        client_name=client_name or "(未指定)",
        project_name=project_name or "(未指定)",
        previous_summary=_gather_previous_summary(db, chunk_row["session_id"], chunk_id),
        known_entities=", ".join(_gather_known_entities(db, chunk_row["session_id"])) or "(无)",
        raw_text=chunk_row["raw_text"] or "",
        files_block=_format_files_block(attached_files),
        unassigned_block=_format_files_block(unassigned_files),
    )

    # 标记 parsing
    db.execute(
        "UPDATE import_story_chunks SET parse_status='parsing', updated_at=? WHERE id=?",
        (_now(), chunk_id),
    )
    try:
        db.conn.commit()
    except Exception:
        pass

    try:
        # 智能文件导入是轻量结构化 JSON 抽取, Doubao 够用 + 无 openclaw 并发锁问题
        # GPT-5.4 留给 narrative_generator 那种深度推理场景
        result = ai._qwen_generate(  # noqa: SLF001
            prompt,
            "你是数据中心档案整理助手, 只返回 JSON.",
            _PARSE_RESPONSE_SCHEMA,
            timeout_seconds=180.0,
            max_tokens=6000,
            temperature=0.15,
            provider_override="doubao",
        )
    except Exception as exc:  # noqa: BLE001
        db.execute(
            "UPDATE import_story_chunks SET parse_status='failed', parse_error=?, updated_at=? WHERE id=?",
            (str(exc)[:500], _now(), chunk_id),
        )
        try:
            db.conn.commit()
        except Exception:
            pass
        raise

    if not isinstance(result, dict):
        result = {}

    # 兜底: 截断长字段 + 清理嵌套箭头(LLM 偶尔不守约)
    result = _clean_parsed_output(result)

    db.execute(
        "UPDATE import_story_chunks SET parsed_json=?, parse_status='parsed', parse_error='', updated_at=? WHERE id=?",
        (json.dumps(result, ensure_ascii=False), _now(), chunk_id),
    )
    try:
        db.conn.commit()
    except Exception:
        pass
    return result


# ------------------------ Preview (聚合) ------------------------


def aggregate_session_to_plan(
    db: Any,
    session_id: str,
    *,
    sandbox_id: str,
) -> dict[str, Any]:
    """聚合所有 chunks 的 parsed_json → 一个 import_plan.

    去重逻辑:
      - entities: 按 name 去重
      - opinions / events / commitments / risk_signals: 简单合并(留给 M3 commit 时去重)
      - files_classified: 按 original_filename 去重(取最后一个 chunk 的分类)
    """
    sandbox_id = _require_sandbox_id(db, sandbox_id)
    require_session_in_sandbox(db, session_id, sandbox_id)
    chunks = db.fetchall(
        """SELECT id, sequence, raw_text, parsed_json, parse_status
           FROM import_story_chunks WHERE session_id = ?
           ORDER BY sequence ASC""",
        (session_id,),
    )
    entities_by_name: dict[str, dict] = {}
    relationships: list[dict] = []
    events: list[dict] = []
    opinions: list[dict] = []
    commitments: list[dict] = []
    risks: list[dict] = []
    files_by_filename: dict[str, dict] = {}
    files_suggested: list[dict] = []
    open_questions: list[str] = []

    parsed_chunks_count = 0
    failed_chunks: list[dict] = []
    for c in chunks:
        if c["parse_status"] != "parsed":
            if c["parse_status"] == "failed":
                failed_chunks.append({"chunk_id": c["id"], "sequence": c["sequence"]})
            continue
        parsed_chunks_count += 1
        p = _safe_json_loads(c["parsed_json"], {})
        for e in (p.get("entities") or []):
            name = str(e.get("name", "")).strip()
            if name and name not in entities_by_name:
                entities_by_name[name] = e
        relationships.extend(p.get("relationships") or [])
        events.extend(p.get("events") or [])
        opinions.extend(p.get("opinions") or [])
        commitments.extend(p.get("commitments") or [])
        risks.extend(p.get("risk_signals") or [])
        for f in (p.get("files_classified") or []):
            fname = str(f.get("original_filename", "")).strip()
            if fname:
                files_by_filename[fname] = f
        files_suggested.extend(p.get("files_suggested_to_attach") or [])
        open_questions.extend(p.get("open_questions") or [])

    return {
        "session_id": session_id,
        "chunks_total": len(chunks),
        "chunks_parsed": parsed_chunks_count,
        "chunks_failed": failed_chunks,
        "entities": list(entities_by_name.values()),
        "relationships": relationships,
        "events": events,
        "opinions": opinions,
        "commitments": commitments,
        "risk_signals": risks,
        "files_classified": list(files_by_filename.values()),
        "files_suggested_to_attach": files_suggested,
        "open_questions": list(set(open_questions)),
    }


# ------------------------ Commit (M3) ------------------------


def _normalize_entity_name(name: str) -> str:
    return (name or "").strip().lower()


def _upsert_entity(db: Any, *, client_id: str, name: str, kind: str, attrs: dict, now: str) -> str:
    """按 (client_id, normalized_name) upsert. 返回 entity id.

    优先复用 active entity; 若仅找到 merged 的同名实体, **复活它**
    (status='active'), 而不是新建 — 避免反复创建/合并循环.
    """
    normalized = _normalize_entity_name(name)
    # 优先找 active
    existing = db.fetchone(
        "SELECT id, attributes_json, mention_count, status FROM entities "
        "WHERE client_id = ? AND normalized_name = ? AND status = 'active' "
        "LIMIT 1",
        (client_id, normalized),
    )
    # active 没找到 → 找 merged 的同名(可能 self_verify 之前合并过), 复活它
    if not existing:
        existing = db.fetchone(
            "SELECT id, attributes_json, mention_count, status FROM entities "
            "WHERE client_id = ? AND normalized_name = ? AND status = 'merged' "
            "ORDER BY mention_count DESC LIMIT 1",
            (client_id, normalized),
        )
    if existing:
        # 合并 attributes
        try:
            merged = json.loads(existing["attributes_json"] or "{}")
        except Exception:  # noqa: BLE001
            merged = {}
        merged.update(attrs or {})
        # 同时把 status 复位到 active(如果是从 merged 找到的)
        db.execute(
            "UPDATE entities SET attributes_json=?, mention_count=mention_count+1, "
            "status='active', last_seen_at=?, updated_at=? WHERE id=?",
            (json.dumps(merged, ensure_ascii=False), now, now, existing["id"]),
        )
        return str(existing["id"])
    eid = _new_id("ent")
    db.execute(
        """INSERT INTO entities
           (id, client_id, entity_type, normalized_name, display_name, aliases_json,
            attributes_json, mention_count, confidence, first_seen_at, last_seen_at,
            status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, '[]', ?, 1, 0.9, ?, ?, 'active', ?, ?)""",
        (
            eid, client_id, kind or "organization", normalized, name.strip(),
            json.dumps(attrs or {}, ensure_ascii=False),
            now, now, now, now,
        ),
    )
    return eid


def _file_dest_path(data_dir: str | Path, client_id: str, role: str, filename: str) -> Path:
    """根据 role 决定文件落到哪个客户子目录."""
    role_folder = {
        "client_owned": "客户资料",
        "partner_submission": "合作方资料",
        "yiyu_advisory": "益语顾问产出",
        "external_reference": "对标参考",
        "policy_industry": "行业政策",
    }.get(role, "智能导入")
    dest_dir = Path(data_dir) / "client_workspace" / client_id / "智能导入" / role_folder
    dest_dir.mkdir(parents=True, exist_ok=True)
    return dest_dir / filename


def commit_session(
    db: Any,
    ai: Any,
    *,
    sandbox_id: str,
    session_id: str,
    data_dir: str | Path,
    ingest_document_fn: Any = None,  # ingest_document_knowledge from knowledge_v2
) -> dict[str, Any]:
    """把 session 的 LLM 解析结果一次性写入数据中心.

    步骤:
      1. 校验 session 状态 (status='drafting'/'ready_for_review' 才能 commit)
      2. 必须绑定 client_id
      3. 把 pending/failed 的 chunks 再 parse 一次
      4. 聚合 plan
      5. 事务里: upsert entities → atomic_facts → commitments → risks → events → files
      6. UPDATE session.status='imported'

    返回 stats: { entities_created, atomic_facts_created, commitments_created,
                  risk_signals_created, events_created, documents_created, errors }
    """
    sandbox_id = _require_sandbox_id(db, sandbox_id)
    session_row = require_session_in_sandbox(db, session_id, sandbox_id)
    if session_row["status"] == "imported":
        raise ValueError("session already imported")
    if session_row["status"] == "discarded":
        raise ValueError("session is discarded")
    client_id = str(session_row["client_id"] or "").strip()
    if not client_id:
        raise ValueError("session has no client_id - must bind to a client before commit")
    event_line_id = str(session_row["project_event_line_id"] or "").strip() or None

    # 把 pending / failed 的 chunks 重新 parse 一次
    pending_chunks = db.fetchall(
        "SELECT id FROM import_story_chunks WHERE session_id = ? "
        "AND parse_status IN ('pending','failed') AND raw_text != ''",
        (session_id,),
    )
    for c in pending_chunks:
        try:
            parse_chunk(db, ai, c["id"], sandbox_id=sandbox_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[smart-import commit] chunk %s reparse failed: %s", c["id"], exc)

    plan = aggregate_session_to_plan(db, session_id, sandbox_id=sandbox_id)
    now = _now()
    stats = {
        "entities_created": 0,
        "atomic_facts_created": 0,
        "commitments_created": 0,
        "risk_signals_created": 0,
        "events_created": 0,
        "documents_created": 0,
        "errors": [],
    }

    # P1-1: 显式 BEGIN IMMEDIATE 事务包裹整个写库流程, 任何系统级失败 → ROLLBACK.
    # 单条业务错误(format/dedup)仍走内层 try/except,只跳过那条不影响整体.
    # P0-Bug2: 收集所有事务内 copy 出的目标文件, rollback 时 cleanup 防孤儿文件.
    copied_files: list[Path] = []
    ingest_sandbox_id = ""
    db.begin_transaction("IMMEDIATE")
    try:
        # P0 TOCTOU 防御: 事务内再次检查 status,
        # 防止两个并发请求都通过函数最前面的检查后, 都进入事务写库, 导致数据重复.
        # IMMEDIATE 锁后, 另一个并发请求会在 begin_transaction 阻塞, 它进来时再次读 status
        # 看到的就是上一个事务标完 'imported' 的状态, 直接 raise.
        recheck_row = require_session_in_sandbox(db, session_id, sandbox_id)
        cur_status = str(recheck_row["status"] or "")
        if cur_status == "imported":
            raise ValueError("session already imported (race detected)")
        if cur_status == "discarded":
            raise ValueError("session is discarded (race detected)")

        # === 1. entities upsert ===
        entity_name_to_id: dict[str, str] = {}
        for e in plan["entities"]:
            ename = str(e.get("name") or "").strip()
            if not ename:
                continue
            kind = str(e.get("kind") or "organization").strip() or "organization"
            attrs = {k: v for k, v in e.items() if k not in ("name", "kind", "first_mention")}
            try:
                eid = _upsert_entity(db, client_id=client_id, name=ename, kind=kind, attrs=attrs, now=now)
                entity_name_to_id[ename] = eid
                stats["entities_created"] += 1
            except Exception as exc:  # noqa: BLE001
                stats["errors"].append(f"entity '{ename}': {exc}")

        # 简单归一函数: 去标点空格小写, 用于近重判定
        def _norm_for_dedup(s: str) -> str:
            import re as _re
            return _re.sub(r"[\s,。.·、\-\—_;:;:!?！？]+", "", str(s or "").strip().lower())

        # === 2. opinions → atomic_facts (按 holder+subject+polarity 去重) ===
        seen_opinions: set[tuple] = set()
        for op in plan["opinions"]:
            holder = str(op.get("holder") or "").strip()
            subj = str(op.get("subject") or "").strip()
            polarity = str(op.get("polarity") or "neutral").strip()
            quote = str(op.get("raw_quote") or "").strip()
            if not (holder and subj):
                continue
            dedup_key = (_norm_for_dedup(holder), _norm_for_dedup(subj), polarity)
            if dedup_key in seen_opinions:
                continue
            seen_opinions.add(dedup_key)
            try:
                # ★ V2.3 阶段 2 M-D2.1: smart_file_import opinion 接 source_registry
                # 蓝图 § 七 第 1 层 + B AI K-3 §1 错层修
                fact_id = _new_id("af")
                source_registry_id: str | None = None
                try:
                    from app.services.source_registry_store import register_source, ensure_schema
                    from app.services.atomic_fact_confidence_history import (
                        ensure_schema as ensure_ch, record_confidence_change,
                    )
                    ensure_schema(db)
                    ensure_ch(db)
                    try:
                        db.execute("ALTER TABLE atomic_facts ADD COLUMN source_registry_id TEXT")
                    except Exception:
                        pass
                    source_registry_id = register_source(
                        db,
                        source_type="oral_claim",  # 智能导入讲述
                        source_channel="smart_import_narration",
                        source_owner="smart_file_import",
                        client_id=client_id,
                        content=f"{holder}|{subj}|{polarity}",
                        source_role="user_oral",
                        raw_reference=f"smart_import_session={session_id}",
                        strict_4_required=False,
                    )
                except Exception as exc:
                    pass  # 失败则 source_registry_id=None, 仍写 atomic_facts

                db.execute(
                    """INSERT INTO atomic_facts
                       (id, client_id, subject_entity_id, subject_text, attribute,
                        value_text, value_normalized, confidence, evidence_text,
                        status, created_at, updated_at, source_registry_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)""",
                    (
                        fact_id, client_id,
                        entity_name_to_id.get(holder),
                        holder,
                        f"对「{subj}」的评价",
                        f"{polarity}: {quote}" if quote else polarity,
                        polarity,
                        0.92,
                        f"smart_import_session={session_id}; quote='{quote}'",
                        now, now, source_registry_id,
                    ),
                )
                # V2.3 confidence_history initial_extract
                if source_registry_id:
                    try:
                        from app.services.atomic_fact_confidence_history import record_confidence_change
                        record_confidence_change(
                            db, fact_id=fact_id, new_confidence=0.92,
                            trigger_event="initial_extract",
                            evidence_link=source_registry_id,
                            actor_id="smart_file_import",
                            reasoning_note=f"smart_import_opinion {holder}→{subj}",
                        )
                    except Exception:
                        pass
                stats["atomic_facts_created"] += 1
            except Exception as exc:  # noqa: BLE001
                stats["errors"].append(f"opinion '{holder}→{subj}': {exc}")

        # === 3. commitments (按 committer+recipient+content 短键去重) ===
        seen_commitments: set[tuple] = set()
        for cm in plan["commitments"]:
            committer = str(cm.get("committer") or "").strip()
            recipient = str(cm.get("recipient") or "").strip()
            content = str(cm.get("content") or "").strip()
            ctype = str(cm.get("commitment_type") or "delivery").strip() or "delivery"
            cstatus = str(cm.get("status") or "pending").strip()
            deadline = cm.get("deadline") or None
            if not (committer and content):
                continue
            # 去重 key: content 取前 20 字符 normalized
            dedup_key = (
                _norm_for_dedup(committer), _norm_for_dedup(recipient),
                _norm_for_dedup(content)[:30],
            )
            if dedup_key in seen_commitments:
                continue
            seen_commitments.add(dedup_key)
            try:
                db.execute(
                    """INSERT INTO commitments
                       (id, client_id, committer, recipient, commitment_type, content,
                        deadline, status, source_type, source_id, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'smart_import_story', ?, ?, ?)""",
                    (
                        _new_id("cmt"), client_id, committer, recipient,
                        ctype, content, deadline, cstatus,
                        session_id, now, now,
                    ),
                )
                stats["commitments_created"] += 1
            except Exception as exc:  # noqa: BLE001
                stats["errors"].append(f"commitment '{content[:30]}': {exc}")

        # === 4. risk_signals (按 title 短键去重) ===
        seen_risks: set[str] = set()
        for r in plan["risk_signals"]:
            title = str(r.get("title") or "").strip()
            desc = str(r.get("description") or "").strip()
            sev = str(r.get("severity") or "medium").strip()
            kind = str(r.get("signal_kind") or r.get("kind") or "关系").strip()
            if not title:
                continue
            dedup_key = _norm_for_dedup(title)[:50]
            if dedup_key in seen_risks:
                continue
            seen_risks.add(dedup_key)
            try:
                db.execute(
                    """INSERT INTO risk_signals
                       (id, client_id, signal_kind, title, description, severity,
                        source_type, source_id, captured_at, status, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, 'smart_import_story', ?, ?, 'active', ?, ?)""",
                    (
                        _new_id("rsk"), client_id, kind, title, desc, sev,
                        session_id, now, now, now,
                    ),
                )
                stats["risk_signals_created"] += 1
            except Exception as exc:  # noqa: BLE001
                stats["errors"].append(f"risk '{title}': {exc}")

        # === 5. events → event_line_activities (要求 session 绑了 event_line) ===
        if event_line_id:
            for ev in plan["events"]:
                actor = str(ev.get("actor") or "").strip()
                action = str(ev.get("action") or "").strip()
                summary = str(ev.get("summary") or f"{actor} {action}").strip()
                happened = str(ev.get("happened_at") or "").strip()
                if not summary:
                    continue
                try:
                    db.execute(
                        """INSERT INTO event_line_activities
                           (id, event_line_id, source_type, source_id, happened_at,
                            actor_name, title, summary, metadata_json, is_key, created_at)
                           VALUES (?, ?, 'smart_import_story', ?, ?, ?, ?, ?, ?, 0, ?)""",
                        (
                            _new_id("ela"), event_line_id, session_id,
                            happened or now,
                            actor[:80], summary[:80], summary,
                            json.dumps({"target": ev.get("target"), "action": action}, ensure_ascii=False),
                            now,
                        ),
                    )
                    stats["events_created"] += 1
                except Exception as exc:  # noqa: BLE001
                    stats["errors"].append(f"event '{summary[:30]}': {exc}")

        # === 6. files → documents (复制文件 + INSERT, ingest 异步后台跑) ===
        # 取所有 staged_files
        files_classified_by_filename = {
            str(f.get("original_filename") or ""): f for f in plan["files_classified"]
        }
        all_staged = db.fetchall(
            "SELECT * FROM import_staged_files WHERE session_id = ? AND document_id IS NULL",
            (session_id,),
        )
        # 收集需要后台 ingest 的文件列表 (异步处理)
        ingest_queue: list[dict[str, Any]] = []
        for sf in all_staged:
            try:
                fclass = files_classified_by_filename.get(sf["original_filename"], {})
                role = (
                    sf["role_override"]
                    or fclass.get("role")
                    or "unknown"
                )
                if role not in VALID_ROLES:
                    role = "unknown"
                subject_entity = str(fclass.get("subject_entity_name") or "").strip()

                # 复制文件到客户工作区
                src = Path(sf["storage_path"])
                if not src.exists():
                    stats["errors"].append(f"file missing: {sf['storage_path']}")
                    continue
                dest = _file_dest_path(data_dir, client_id, role, sf["original_filename"])
                base, suffix = dest.stem, dest.suffix
                counter = 1
                while dest.exists():
                    counter += 1
                    dest = dest.with_name(f"{base}_{counter}{suffix}")
                shutil.copy2(src, dest)
                copied_files.append(dest)  # 事务 rollback 时 cleanup 用

                doc_id = _new_id("doc")
                kind = (sf["mime_type"] or "").lower()
                kind_short = "pdf" if "pdf" in kind else ("docx" if "word" in kind or sf["original_filename"].endswith(".docx") else "file")
                excerpt = (fclass.get("narrator_hint") or "")[:140]

                db.execute(
                    """INSERT INTO documents
                       (id, client_id, title, path, original_source_path, kind, source,
                        excerpt, tags_json, created_at,
                        document_role, subject_entity_name, import_story_session_id,
                        owner_user_id, visibility_scope, content_domain, lifecycle_status)
                       VALUES (?, ?, ?, ?, ?, ?, 'smart_import', ?, ?, ?,
                               ?, ?, ?, ?, 'project_public', 'work', 'active')""",
                    (
                        doc_id, client_id, sf["original_filename"],
                        str(dest), str(dest),
                        kind_short, excerpt,
                        json.dumps(["smart_import", role], ensure_ascii=False),
                        now, role, subject_entity, session_id,
                        str(session_row["narrator_user_id"] or ""),
                    ),
                )
                db.execute(
                    "UPDATE import_staged_files SET document_id=?, document_inserted_at=? WHERE id=?",
                    (doc_id, now, sf["id"]),
                )
                stats["documents_created"] += 1
                # 加入后台 ingest 队列
                ingest_queue.append({
                    "doc_id": doc_id,
                    "dest": str(dest),
                    "title": sf["original_filename"],
                    "kind": kind_short,
                    "excerpt": excerpt,
                })
            except Exception as exc:  # noqa: BLE001
                stats["errors"].append(f"file '{sf['original_filename']}': {exc}")

        # === 7. 创建 knowledge_jobs 让工作台进度条接管 OCR 进度 ===
        ingest_job_id = ""
        if ingest_queue and ingest_document_fn:
            ingest_job_id = _new_id("kjob")
            workspace_context = resolve_client_workspace_context(db, client_id)
            if workspace_context.sandbox_id != sandbox_id:
                raise SmartImportScopeNotFound("session not found")
            ingest_sandbox_id = workspace_context.sandbox_id
            db.execute(
                """INSERT INTO knowledge_jobs
                   (id, client_id, sandbox_id, job_type, status, payload_json, total_items,
                    processed_items, last_error, created_at, started_at,
                    finished_at, updated_at)
                   VALUES (?, ?, ?, 'smart_import_ingest', 'running', ?, ?, 0,
                           NULL, ?, ?, NULL, ?)""",
                (
                    ingest_job_id, client_id, workspace_context.sandbox_id,
                    json.dumps({
                        "sessionId": session_id,
                        "fileCount": len(ingest_queue),
                    }, ensure_ascii=False),
                    len(ingest_queue), now, now, now,
                ),
            )

        # === 8. 标记 session imported ===
        db.execute(
            "UPDATE import_story_sessions SET status='imported', imported_at=?, updated_at=? "
            "WHERE id=? AND COALESCE(sandbox_id, '')=?",
            (now, now, session_id, sandbox_id),
        )
        db.commit_transaction()
    except Exception:
        try:
            db.rollback_transaction()
        except Exception:  # noqa: BLE001
            logger.exception("[smart-import commit] rollback also failed for session %s", session_id)
        # P0-Bug2: 事务回滚后, cleanup 已经复制到客户工作区的孤儿文件
        for orphan in copied_files:
            try:
                if orphan.exists():
                    orphan.unlink()
            except Exception:  # noqa: BLE001
                logger.warning("[smart-import commit] cleanup orphan file failed: %s", orphan)
        logger.exception("[smart-import commit] failed for session %s", session_id)
        raise

    # === 9. 启动后台 daemon 线程异步跑 ingest(让 commit 接口立刻返回)===
    # 工作台进度条会实时显示 ingest 进度
    if ingest_queue and ingest_document_fn and ingest_job_id:
        import threading
        threading.Thread(
            target=_bg_ingest_files,
            args=(db, ingest_document_fn, ai, data_dir, client_id, ingest_sandbox_id, ingest_job_id, ingest_queue),
            daemon=True,
            name=f"smart-import-ingest-{session_id[:12]}",
        ).start()

    stats["ingest_job_id"] = ingest_job_id  # type: ignore[assignment]
    stats["ingest_pending_count"] = len(ingest_queue)  # type: ignore[assignment]
    return stats


def _reap_stale_knowledge_jobs(db: Any, *, max_running_minutes: int = 30) -> int:
    """把跑了 > N 分钟还 status='running' 的 knowledge_jobs 标 failed.

    用途: daemon thread 崩溃 / 进程被杀, 留下卡死的 'running' job, UI 进度条永远转.
    每次 _bg_ingest_files 结束时顺手清一遍. 返回 reap 数.
    """
    try:
        def _reap(conn) -> int:
            stale_rows = conn.execute(
                """
                SELECT id, sandbox_id
                FROM knowledge_jobs
                WHERE status = 'running'
                  AND COALESCE(updated_at, started_at, created_at) < datetime('now', ?)
                """,
                (f"-{max_running_minutes} minutes",),
            ).fetchall()
            count = 0
            for row in stale_rows:
                now = _now()
                cur = conn.execute(
                    """UPDATE knowledge_jobs
                       SET status='failed',
                           last_error=COALESCE(last_error,'') || ' [auto-reaped: stale running > ' || ? || ' min]',
                           finished_at=?,
                           updated_at=?
                       WHERE id = ?
                         AND COALESCE(sandbox_id, '') = ?
                         AND status='running'
                         AND COALESCE(updated_at, started_at, created_at) < datetime('now', ?)""",
                    (
                        max_running_minutes,
                        now,
                        now,
                        str(row["id"]),
                        str(row["sandbox_id"] or ""),
                        f"-{max_running_minutes} minutes",
                    ),
                )
                count += max(0, int(cur.rowcount or 0))
            return count

        transaction_runner = getattr(db, "run_in_transaction", None)
        if callable(transaction_runner):
            n = int(transaction_runner(_reap) or 0)
        else:
            n = _reap(db.conn)
            db.conn.commit()
        if n > 0:
            logger.info("[reap_stale_knowledge_jobs] reaped %d stale jobs", n)
        return n
    except Exception:
        logger.exception("[reap_stale_knowledge_jobs] failed")
        return 0


def _run_bg_ingest_files_scoped(
    db: Any,
    ingest_document_fn: Any,
    ai: Any,
    data_dir: str | Path,
    client_id: str,
    sandbox_id: str,
    workspace_context: Any,
    job_id: str,
    queue: list[dict[str, Any]],
) -> None:
    """后台 daemon 线程: 逐个文件跑 ingest, 实时更新 knowledge_jobs 进度.

    P1-2: 任何阶段崩溃都用 finally + outer try 兜底, 必须把 job 标记成 completed/failed,
          不留 'running' 孤儿状态. 末尾还会跑 timeout reaper 清前的孤儿 job.
    """
    processed = 0
    last_error = ""
    fatal_error: str | None = None  # outer 致命错误标记
    from app.services.knowledge_v2 import _resolve_team_context_for_async_worker

    team_context = _resolve_team_context_for_async_worker(db, workspace_context)
    try:
        for item in queue:
            try:
                ingest_document_fn(
                    db,
                    data_dir=Path(data_dir),
                    client_id=client_id,
                    import_id=None,
                    document_id=item["doc_id"],
                    source_path=Path(item["dest"]),
                    original_source_path=Path(item["dest"]),
                    title=item["title"],
                    kind=item["kind"],
                    source="smart_import",
                    fallback_excerpt=item["excerpt"],
                    created_at=_now(),
                    ai_service=ai,
                    organization_id=team_context.get("organization_id", ""),
                    owner_user_id=team_context.get("owner_user_id", ""),
                    department_id=team_context.get("department_id", ""),
                    visibility_scope=team_context.get("visibility_scope", "project_public"),
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("[smart-import bg ingest] doc=%s failed", item["doc_id"])
                last_error = f"{item['title']}: {str(exc)[:120]}"
            finally:
                processed += 1
                try:
                    db.execute(
                        """UPDATE knowledge_jobs SET processed_items = ?,
                           last_error = ?, updated_at = ? WHERE id = ? AND sandbox_id = ?""",
                        (processed, last_error[:500], _now(), job_id, sandbox_id),
                    )
                    db.conn.commit()
                except Exception:
                    logger.exception(
                        "[smart-import bg ingest] update progress failed job=%s", job_id,
                    )
    except Exception as outer_exc:  # noqa: BLE001
        # daemon 内部不可恢复异常 (e.g. KeyboardInterrupt/MemoryError/db handle 死)
        fatal_error = f"{type(outer_exc).__name__}: {str(outer_exc)[:160]}"
        logger.exception("[smart-import bg ingest] fatal job=%s", job_id)
    finally:
        # 必须把 job 标记到终态, 不留 'running' 孤儿
        final_status = "failed" if fatal_error else "completed"
        final_error = fatal_error if fatal_error else (last_error if last_error else None)
        try:
            finished = _now()
            db.execute(
                """UPDATE knowledge_jobs SET status = ?, processed_items = ?,
                   last_error = ?, finished_at = ?, updated_at = ? WHERE id = ? AND sandbox_id = ?""",
                (final_status, processed, (final_error or "")[:500], finished, finished, job_id, sandbox_id),
            )
            db.conn.commit()
        except Exception:
            logger.exception("[smart-import bg ingest] finalize FAILED job=%s", job_id)
        # 顺手清理超时 running 孤儿 (跑了 > 30 分钟还 running 的, 标 failed)
        try:
            _reap_stale_knowledge_jobs(db, max_running_minutes=30)
        except Exception:
            logger.exception("[smart-import bg ingest] reap_stale failed")

    # 全部 ingest 完成后, 走数据中心统一 broadcast 钩子
    # → 入队 analysis_job + 标 narrative_stale + 后台跑 portrait/narrative
    try:
        from app.services.data_center_broadcast import broadcast_data_changed
        broadcast_data_changed(
            db, ai,
            client_id=client_id,
            scope="smart_import_story",
        )
    except Exception:
        logger.exception("[smart-import bg ingest] broadcast failed")


def _bg_ingest_files(
    db: Any,
    ingest_document_fn: Any,
    ai: Any,
    data_dir: str | Path,
    client_id: str,
    sandbox_id: str,
    job_id: str,
    queue: list[dict[str, Any]],
) -> None:
    """Validate and bind the persisted scope before the daemon touches business data or AI."""

    try:
        workspace_context = load_persisted_job_workspace_context(
            db,
            sandbox_id=sandbox_id,
            client_id=client_id,
        )
        use_sandbox = getattr(ai, "use_sandbox", None)
        if not callable(use_sandbox):
            raise AsyncJobScopeError(
                "ai_scope_binding_unavailable",
                client_id=client_id,
                sandbox_id=sandbox_id,
            )
        with use_sandbox(workspace_context.sandbox_id):
            _run_bg_ingest_files_scoped(
                db,
                ingest_document_fn,
                ai,
                data_dir,
                client_id,
                workspace_context.sandbox_id,
                workspace_context,
                job_id,
                queue,
            )
    except Exception as error:
        logger.exception("[smart-import bg ingest] scope validation failed job=%s", job_id)
        try:
            finished = _now()
            db.execute(
                """
                UPDATE knowledge_jobs
                SET status = 'failed', last_error = ?, finished_at = ?, updated_at = ?
                WHERE id = ? AND COALESCE(sandbox_id, '') = ?
                """,
                (str(error)[:500], finished, finished, job_id, str(sandbox_id or "")),
            )
            db.conn.commit()
        except Exception:
            logger.exception("[smart-import bg ingest] scope failure finalization failed job=%s", job_id)
