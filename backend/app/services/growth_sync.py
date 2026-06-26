"""成长积分 (growth) 云端同步 service.

真**核心目标** (顾源源 5/27 阶段 1+2 · "卷"机制核心):
  · 同步 3 源表: signal_events + evidence_records + validation_events
  · 派生表本地重算: capture_states + ability_weekly_snapshot
  · ability_profiles 是 seed, 不同步

真**同步状态机** (跟 exp_wall / handbook 一致):
  local → pending → synced (push 成功) / failed (push 失败)

真**写入 hook**:
  · badge_engine.py / growth_engine.py / local_memory.py 真INSERT 后真调 mark_*_pending
  · validation_events 真同理

真**后台 worker**:
  · _background_sync_exp_wall 真扩展加 growth push/pull (跟 exp_wall/handbook 同一 5min 线程)
  · pull 后真自动 rebuild_capture_states + rebuild_weekly_snapshots
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from app.db import Database

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _scoped_pull_key(base_key: str, sandbox_id: str | None) -> str:
    normalized = (sandbox_id or "").strip()
    return f"{base_key}.{normalized}" if normalized else base_key


# ──────────────────────────────────────────────────────────────────
# 写入 hook (供 badge_engine / growth_engine / local_memory 调用)
# ──────────────────────────────────────────────────────────────────


def mark_signal_pending(db: Database, signal_id: str) -> None:
    """真signal INSERT 后真调. 真幂等."""
    db.conn.execute(
        "UPDATE growth_signal_events SET sync_status='pending', pending_sync_action='upsert', updated_at=? WHERE id = ?",
        (_now_iso(), signal_id),
    )
    db.conn.commit()


def mark_evidence_pending(db: Database, evidence_id: str) -> None:
    """真evidence INSERT 后真调. 真幂等."""
    db.conn.execute(
        "UPDATE growth_evidence_records SET sync_status='pending', pending_sync_action='upsert', updated_at=? WHERE id = ?",
        (_now_iso(), evidence_id),
    )
    db.conn.commit()


def mark_validation_event_pending(db: Database, event_id: str) -> None:
    """真validation event INSERT 后真调. 真幂等."""
    db.conn.execute(
        "UPDATE growth_validation_events SET sync_status='pending', pending_sync_action='upsert', updated_at=? WHERE id = ?",
        (_now_iso(), event_id),
    )
    db.conn.commit()


# ──────────────────────────────────────────────────────────────────
# Row → cloud payload 转换
# ──────────────────────────────────────────────────────────────────


def _signal_row_to_payload(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": str(row["id"]),
        "userId": str(row["user_id"]),
        "userName": str(row["user_name"] or ""),
        "sourceType": str(row["source_type"]),
        "sourceId": str(row["source_id"]),
        "reviewId": str(row["review_id"]) if row["review_id"] else None,
        "taskId": str(row["task_id"]) if row["task_id"] else None,
        "weekLabel": str(row["week_label"] or ""),
        "rawText": str(row["raw_text"] or ""),
        "contextJson": str(row["context_json"] or "{}"),
        "dedupeKey": str(row["dedupe_key"]),
        "createdAt": str(row["created_at"]),
        "updatedAt": str(row["updated_at"] or row["created_at"]),
    }


def _evidence_row_to_payload(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": str(row["id"]),
        "signalId": str(row["signal_id"]),
        "userId": str(row["user_id"]),
        "userName": str(row["user_name"] or ""),
        "abilityKey": str(row["ability_key"]),
        "evidenceType": str(row["evidence_type"]),
        "level": str(row["level"]),
        "confidence": str(row["confidence"] or "medium"),
        "reason": str(row["reason"] or ""),
        "reviewId": str(row["review_id"]) if row["review_id"] else None,
        "taskId": str(row["task_id"]) if row["task_id"] else None,
        "handbookEntryId": str(row["handbook_entry_id"]) if row["handbook_entry_id"] else None,
        "metadataJson": str(row["metadata_json"] or "{}"),
        "contributionTagsJson": str(row["contribution_tags_json"] or "[]"),
        "orgContributionScore": int(row["org_contribution_score"] or 0),
        "suggestedPremiumRate": float(row["suggested_premium_rate"] or 0),
        "validationState": str(row["validation_state"] or "candidate"),
        "aiReason": str(row["ai_reason"] or ""),
        "aiConfidence": float(row["ai_confidence"] or 0),
        "createdAt": str(row["created_at"]),
        "updatedAt": str(row["updated_at"] or row["created_at"]),
    }


def _validation_event_row_to_payload(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": str(row["id"]),
        "userId": str(row["user_id"]),
        "evidenceId": str(row["evidence_id"]),
        "eventType": str(row["event_type"]),
        "actorId": str(row["actor_id"] or ""),
        "actorName": str(row["actor_name"] or ""),
        "sourceType": str(row["source_type"] or ""),
        "sourceId": str(row["source_id"]) if row["source_id"] else None,
        "detailJson": str(row["detail_json"] or "{}"),
        "createdAt": str(row["created_at"]),
        "updatedAt": str(row["updated_at"] or row["created_at"]),
    }


# ──────────────────────────────────────────────────────────────────
# Push: pending → cloud
# ──────────────────────────────────────────────────────────────────


def _push_table_to_cloud(
    db: Database,
    *,
    table: str,
    endpoint: str,
    row_to_payload,
    cloud_base_url: str,
    cloud_token: str,
    httpx_client,
    extra_required_field: str | None = None,
    sandbox_id: str | None = None,
) -> dict[str, int]:
    """通用 push 函数 — table 真pending 行 真POST 到云端."""
    if sandbox_id:
        rows = db.fetchall(
            f"SELECT * FROM {table} WHERE sync_status = 'pending' AND sandbox_id = ? ORDER BY created_at ASC LIMIT 100",
            (sandbox_id,),
        )
    else:
        rows = db.fetchall(
            f"SELECT * FROM {table} WHERE sync_status = 'pending' ORDER BY created_at ASC LIMIT 100"
        )
    pushed = 0
    failed = 0
    for row in rows:
        row_id = str(row["id"])
        # 真extra_required_field 检查 (例: evidence 真signal_id, validation 真evidence_id)
        if extra_required_field and not row[extra_required_field]:
            db.conn.execute(
                f"UPDATE {table} SET sync_status='failed' WHERE id = ?",
                (row_id,),
            )
            failed += 1
            continue
        try:
            payload = row_to_payload(row)
            resp = httpx_client.post(
                f"{cloud_base_url.rstrip('/')}{endpoint}",
                json=payload,
                headers={"Authorization": f"Bearer {cloud_token}"},
                timeout=15.0,
            )
            if 200 <= resp.status_code < 300:
                db.conn.execute(
                    f"UPDATE {table} SET sync_status='synced', last_synced_at=?, pending_sync_action='' WHERE id = ?",
                    (_now_iso(), row_id),
                )
                pushed += 1
            else:
                logger.warning("push %s %s failed: HTTP %d %s", table, row_id, resp.status_code, resp.text[:200])
                db.conn.execute(
                    f"UPDATE {table} SET sync_status='failed' WHERE id = ?",
                    (row_id,),
                )
                failed += 1
        except Exception as exc:
            logger.warning("push %s %s exception: %s", table, row_id, exc)
            db.conn.execute(
                f"UPDATE {table} SET sync_status='failed' WHERE id = ?",
                (row_id,),
            )
            failed += 1
    db.conn.commit()
    return {"pushed": pushed, "failed": failed}


def push_pending_signals_to_cloud(
    db: Database, *, cloud_base_url: str, cloud_token: str, httpx_client, sandbox_id: str | None = None,
) -> dict[str, int]:
    return _push_table_to_cloud(
        db,
        table="growth_signal_events",
        endpoint="/api/v1/growth/sync/signals",
        row_to_payload=_signal_row_to_payload,
        cloud_base_url=cloud_base_url,
        cloud_token=cloud_token,
        httpx_client=httpx_client,
        sandbox_id=sandbox_id,
    )


def push_pending_evidence_to_cloud(
    db: Database, *, cloud_base_url: str, cloud_token: str, httpx_client, sandbox_id: str | None = None,
) -> dict[str, int]:
    """注意: evidence 真push 真**先决条件** = signal_id 在云端已存在.
    真排序按 signal_id 真group 真**signal 先 push, evidence 后 push** (本函数真依赖 signal push 已跑过)."""
    return _push_table_to_cloud(
        db,
        table="growth_evidence_records",
        endpoint="/api/v1/growth/sync/evidence",
        row_to_payload=_evidence_row_to_payload,
        cloud_base_url=cloud_base_url,
        cloud_token=cloud_token,
        httpx_client=httpx_client,
        extra_required_field="signal_id",
        sandbox_id=sandbox_id,
    )


def push_pending_validation_events_to_cloud(
    db: Database, *, cloud_base_url: str, cloud_token: str, httpx_client, sandbox_id: str | None = None,
) -> dict[str, int]:
    return _push_table_to_cloud(
        db,
        table="growth_validation_events",
        endpoint="/api/v1/growth/sync/validation-events",
        row_to_payload=_validation_event_row_to_payload,
        cloud_base_url=cloud_base_url,
        cloud_token=cloud_token,
        httpx_client=httpx_client,
        extra_required_field="evidence_id",
        sandbox_id=sandbox_id,
    )


# ──────────────────────────────────────────────────────────────────
# Pull: cloud → local
# ──────────────────────────────────────────────────────────────────


def pull_signals_from_cloud(
    db: Database, *, cloud_base_url: str, cloud_token: str, httpx_client, sandbox_id: str | None = None,
) -> dict[str, object]:
    """真拉云端真signal 增量, 真合并到本地 (按 id upsert)."""
    pull_key = _scoped_pull_key("last_growth_signal_pull_at", sandbox_id)
    since = db.get_setting(pull_key, "") or db.get_setting("last_growth_signal_pull_at", "")
    try:
        resp = httpx_client.get(
            f"{cloud_base_url.rstrip('/')}/api/v1/growth/sync/signals",
            params={"since": since} if since else {},
            headers={"Authorization": f"Bearer {cloud_token}"},
            timeout=20.0,
        )
        if not (200 <= resp.status_code < 300):
            logger.warning("pull growth signals failed: HTTP %d", resp.status_code)
            return {"pulled": 0, "merged": 0, "skipped_pending": 0}
        data = resp.json()
    except Exception as exc:
        logger.warning("pull growth signals exception: %s", exc)
        return {"pulled": 0, "merged": 0, "skipped_pending": 0}

    signals = data.get("signals", []) or []
    server_ts = data.get("serverTimestamp", "") or _now_iso()
    merged = 0
    skipped_pending = 0
    for s in signals:
        sid = str(s.get("id", ""))
        if not sid:
            continue
        existing = db.fetchone("SELECT sync_status FROM growth_signal_events WHERE id = ?", (sid,))
        if existing and str(existing["sync_status"]) == "pending":
            skipped_pending += 1
            continue
        db.conn.execute(
            """
            INSERT INTO growth_signal_events(
                id, sandbox_id, user_id, user_name, source_type, source_id,
                review_id, task_id, week_label, raw_text, context_json, dedupe_key,
                created_at, updated_at,
                sync_status, last_synced_at, pending_sync_action
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'synced', ?, '')
            ON CONFLICT(id) DO UPDATE SET
                sandbox_id = excluded.sandbox_id,
                raw_text = excluded.raw_text,
                context_json = excluded.context_json,
                week_label = excluded.week_label,
                review_id = excluded.review_id,
                task_id = excluded.task_id,
                updated_at = excluded.updated_at,
                sync_status = 'synced',
                last_synced_at = excluded.last_synced_at,
                pending_sync_action = ''
            """,
            (
                sid, (sandbox_id or "sbx_local_default"), str(s.get("userId", "")), str(s.get("userName", "")),
                str(s.get("sourceType", "")), str(s.get("sourceId", "")),
                s.get("reviewId"), s.get("taskId"),
                str(s.get("weekLabel", "")), str(s.get("rawText", "")),
                str(s.get("contextJson", "{}")), str(s.get("dedupeKey", "")),
                str(s.get("createdAt", "")), str(s.get("updatedAt", "")),
                _now_iso(),
            ),
        )
        merged += 1

    db.set_setting(pull_key, server_ts)
    db.conn.commit()
    return {"pulled": len(signals), "merged": merged, "skipped_pending": skipped_pending}


def pull_evidence_from_cloud(
    db: Database, *, cloud_base_url: str, cloud_token: str, httpx_client, sandbox_id: str | None = None,
) -> dict[str, object]:
    pull_key = _scoped_pull_key("last_growth_evidence_pull_at", sandbox_id)
    since = db.get_setting(pull_key, "") or db.get_setting("last_growth_evidence_pull_at", "")
    try:
        resp = httpx_client.get(
            f"{cloud_base_url.rstrip('/')}/api/v1/growth/sync/evidence",
            params={"since": since} if since else {},
            headers={"Authorization": f"Bearer {cloud_token}"},
            timeout=20.0,
        )
        if not (200 <= resp.status_code < 300):
            return {"pulled": 0, "merged": 0, "skipped_pending": 0}
        data = resp.json()
    except Exception as exc:
        logger.warning("pull growth evidence exception: %s", exc)
        return {"pulled": 0, "merged": 0, "skipped_pending": 0}

    items = data.get("evidence", []) or []
    server_ts = data.get("serverTimestamp", "") or _now_iso()
    merged = 0
    skipped_pending = 0
    for e in items:
        eid = str(e.get("id", ""))
        if not eid:
            continue
        existing = db.fetchone("SELECT sync_status FROM growth_evidence_records WHERE id = ?", (eid,))
        if existing and str(existing["sync_status"]) == "pending":
            skipped_pending += 1
            continue
        db.conn.execute(
            """
            INSERT INTO growth_evidence_records(
                id, sandbox_id, signal_id, user_id, user_name, ability_key, evidence_type, level,
                confidence, reason, review_id, task_id, handbook_entry_id,
                metadata_json, contribution_tags_json, org_contribution_score,
                suggested_premium_rate, validation_state, ai_reason, ai_confidence,
                created_at, updated_at,
                sync_status, last_synced_at, pending_sync_action
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'synced', ?, '')
            ON CONFLICT(id) DO UPDATE SET
                sandbox_id = excluded.sandbox_id,
                level = excluded.level,
                confidence = excluded.confidence,
                reason = excluded.reason,
                metadata_json = excluded.metadata_json,
                contribution_tags_json = excluded.contribution_tags_json,
                org_contribution_score = excluded.org_contribution_score,
                suggested_premium_rate = excluded.suggested_premium_rate,
                validation_state = excluded.validation_state,
                ai_reason = excluded.ai_reason,
                ai_confidence = excluded.ai_confidence,
                updated_at = excluded.updated_at,
                sync_status = 'synced',
                last_synced_at = excluded.last_synced_at,
                pending_sync_action = ''
            """,
            (
                eid, (sandbox_id or "sbx_local_default"), str(e.get("signalId", "")), str(e.get("userId", "")), str(e.get("userName", "")),
                str(e.get("abilityKey", "")), str(e.get("evidenceType", "")), str(e.get("level", "")),
                str(e.get("confidence", "medium")), str(e.get("reason", "")),
                e.get("reviewId"), e.get("taskId"), e.get("handbookEntryId"),
                str(e.get("metadataJson", "{}")), str(e.get("contributionTagsJson", "[]")),
                int(e.get("orgContributionScore", 0)), float(e.get("suggestedPremiumRate", 0)),
                str(e.get("validationState", "candidate")),
                str(e.get("aiReason", "")), float(e.get("aiConfidence", 0)),
                str(e.get("createdAt", "")), str(e.get("updatedAt", "")),
                _now_iso(),
            ),
        )
        merged += 1

    db.set_setting(pull_key, server_ts)
    db.conn.commit()
    return {"pulled": len(items), "merged": merged, "skipped_pending": skipped_pending}


def pull_validation_events_from_cloud(
    db: Database, *, cloud_base_url: str, cloud_token: str, httpx_client, sandbox_id: str | None = None,
) -> dict[str, object]:
    pull_key = _scoped_pull_key("last_growth_validation_pull_at", sandbox_id)
    since = db.get_setting(pull_key, "") or db.get_setting("last_growth_validation_pull_at", "")
    try:
        resp = httpx_client.get(
            f"{cloud_base_url.rstrip('/')}/api/v1/growth/sync/validation-events",
            params={"since": since} if since else {},
            headers={"Authorization": f"Bearer {cloud_token}"},
            timeout=20.0,
        )
        if not (200 <= resp.status_code < 300):
            return {"pulled": 0, "merged": 0, "skipped_pending": 0}
        data = resp.json()
    except Exception as exc:
        logger.warning("pull growth validation events exception: %s", exc)
        return {"pulled": 0, "merged": 0, "skipped_pending": 0}

    events = data.get("events", []) or []
    server_ts = data.get("serverTimestamp", "") or _now_iso()
    merged = 0
    skipped_pending = 0
    for v in events:
        vid = str(v.get("id", ""))
        if not vid:
            continue
        existing = db.fetchone("SELECT sync_status FROM growth_validation_events WHERE id = ?", (vid,))
        if existing and str(existing["sync_status"]) == "pending":
            skipped_pending += 1
            continue
        db.conn.execute(
            """
            INSERT INTO growth_validation_events(
                id, sandbox_id, user_id, evidence_id, event_type, actor_id, actor_name,
                source_type, source_id, detail_json, created_at, updated_at,
                sync_status, last_synced_at, pending_sync_action
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'synced', ?, '')
            ON CONFLICT(id) DO UPDATE SET
                sandbox_id = excluded.sandbox_id,
                event_type = excluded.event_type,
                actor_id = excluded.actor_id,
                actor_name = excluded.actor_name,
                detail_json = excluded.detail_json,
                updated_at = excluded.updated_at,
                sync_status = 'synced',
                last_synced_at = excluded.last_synced_at,
                pending_sync_action = ''
            """,
            (
                vid, (sandbox_id or "sbx_local_default"), str(v.get("userId", "")), str(v.get("evidenceId", "")),
                str(v.get("eventType", "")), str(v.get("actorId", "")), str(v.get("actorName", "")),
                str(v.get("sourceType", "")), v.get("sourceId"),
                str(v.get("detailJson", "{}")),
                str(v.get("createdAt", "")), str(v.get("updatedAt", "")),
                _now_iso(),
            ),
        )
        merged += 1

    db.set_setting(pull_key, server_ts)
    db.conn.commit()
    return {"pulled": len(events), "merged": merged, "skipped_pending": skipped_pending}


# ──────────────────────────────────────────────────────────────────
# 阶段 2 · 派生表本地重算
# ──────────────────────────────────────────────────────────────────


def rebuild_capture_states_from_signals(db: Database) -> dict[str, int]:
    """真按 signal_events 真重算 capture_states.

    真**规则**:
      · 真新 signal → 真插入一条 capture_state (status='open')
      · 真已有 signal → 真保留 (不动 status, 不覆盖用户已 promote/dismiss 真状态)
      · 真**只补**真**新 pulled 的 signal**, 真不破坏本地用户行为
    """
    # 真找 真**signal 真没对应 capture_state** 真的 — 真新加
    rows = db.fetchall(
        """
        SELECT s.id AS signal_id, s.user_id, s.created_at
        FROM growth_signal_events s
        LEFT JOIN growth_capture_states c ON c.signal_id = s.id
        WHERE c.id IS NULL
        """
    )
    new_count = 0
    for r in rows:
        db.conn.execute(
            """
            INSERT OR IGNORE INTO growth_capture_states(
                id, user_id, signal_id, status, reason, created_at, updated_at
            ) VALUES(?, ?, ?, 'open', '', ?, ?)
            """,
            (
                f"cap_{r['signal_id']}",  # 真稳定 id (基于 signal_id) → 真幂等
                str(r["user_id"]),
                str(r["signal_id"]),
                str(r["created_at"]),
                _now_iso(),
            ),
        )
        new_count += 1
    db.conn.commit()
    return {"new_captures": new_count}


def rebuild_weekly_snapshots_from_evidence(db: Database) -> dict[str, int]:
    """真按 evidence_records 真重算 ability_weekly_snapshot.

    真**规则**:
      · 真按 (user_id, week_label, ability_key) 真分组聚合 evidence
      · current_score = SUM(org_contribution_score) WHERE validation_state IN ('validated','institutionalized')
      · total_xp = SUM(org_contribution_score)
      · 真**week_label 真从 evidence.created_at 真推导** (ISO week format: 2026-W22)
    """
    # 真先收集真"应该有快照"的 (user, week, ability) 真组合
    db.conn.execute("CREATE TEMP TABLE IF NOT EXISTS _growth_week_temp (user_id TEXT, week_label TEXT, ability_key TEXT, current_score INTEGER, total_xp INTEGER, PRIMARY KEY(user_id, week_label, ability_key))")
    db.conn.execute("DELETE FROM _growth_week_temp")

    # 真按 evidence 真聚合
    db.conn.execute(
        """
        INSERT INTO _growth_week_temp(user_id, week_label, ability_key, current_score, total_xp)
        SELECT user_id,
               strftime('%Y-W%W', created_at) AS week_label,
               ability_key,
               SUM(CASE WHEN validation_state IN ('validated', 'institutionalized') THEN org_contribution_score ELSE 0 END) AS current_score,
               SUM(org_contribution_score) AS total_xp
        FROM growth_evidence_records
        GROUP BY user_id, week_label, ability_key
        """
    )

    # 真 upsert 到 ability_weekly_snapshot
    rows = db.fetchall("SELECT * FROM _growth_week_temp")
    rebuilt = 0
    now_ts = _now_iso()
    for r in rows:
        snap_id = f"snap_{r['user_id']}_{r['week_label']}_{r['ability_key']}"
        db.conn.execute(
            """
            INSERT INTO growth_ability_weekly_snapshot(
                id, user_id, week_label, ability_key, current_score, total_xp, snapshot_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, week_label, ability_key) DO UPDATE SET
                current_score = excluded.current_score,
                total_xp = excluded.total_xp,
                snapshot_at = excluded.snapshot_at
            """,
            (snap_id, str(r["user_id"]), str(r["week_label"]), str(r["ability_key"]),
             int(r["current_score"] or 0), int(r["total_xp"] or 0), now_ts),
        )
        rebuilt += 1
    db.conn.execute("DROP TABLE IF EXISTS _growth_week_temp")
    db.conn.commit()
    return {"rebuilt_snapshots": rebuilt}


__all__ = [
    "mark_signal_pending",
    "mark_evidence_pending",
    "mark_validation_event_pending",
    "push_pending_signals_to_cloud",
    "push_pending_evidence_to_cloud",
    "push_pending_validation_events_to_cloud",
    "pull_signals_from_cloud",
    "pull_evidence_from_cloud",
    "pull_validation_events_from_cloud",
    "rebuild_capture_states_from_signals",
    "rebuild_weekly_snapshots_from_evidence",
]
