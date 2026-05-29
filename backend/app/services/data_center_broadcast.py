"""数据中心写后扩散 (P0 - 治本基础设施).

== 为什么需要这个 ==

数据中心设计初衷是"预制菜模式":
    入口写原始数据 → 预制菜层加工聚合 → 消费层快速读

但实际实现里只有"原始数据写入"和"消费层"两端,中间的"预制菜聚合层"是空的:
    - 写入端不知道下游谁要消费
    - 消费端各自从原始表 patch 着读
    - 新增写入方时下游不会自动接通(漏一个就出 bug)

本模块提供统一的写后通知钩子 `broadcast_data_changed(...)`,任何写入数据中心
的操作完成后调一次,内部负责通知所有下游 collector / re-aggregator.

== 扇出范围 ==

L1 (同步, 轻量, ms 级):
    - 入队 analysis_job (→ worker 写 evidence_cards)
    - 标记 narrative_stale_signals (→ 前端 useEffect 检测自动 regenerate)

L2 (异步 daemon, 重, 秒~分钟级):
    - portrait_build (生成 relations/risks/commits via LLM)
    - narrative regenerate (6 维度叙事 via LLM, 主动后台跑不依赖用户打开页面)
    - thoughts refresh (战略思考研判 via LLM)

== Throttle ==

同 client + 同任务 60-90 秒内只跑一次重操作 (in-memory state, daemon 重启清空).
analysis_job enqueue 不 throttle (后端 dedupe_key 已处理).
"""

from __future__ import annotations

import json as _json
import logging
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ─── In-memory throttle ─────────────────────────────────────────────────────

_THROTTLE_STATE: dict[tuple[str, str], float] = {}
_THROTTLE_LOCK = threading.Lock()

# Per-client 串行锁: 同一 client 的 portrait_build / narrative regen / self_verify
# 共享一个 Lock, 防止多个 daemon 同时 DELETE+INSERT 同一批 ai_inferred 表
# (P0 修复: 之前 broadcast 并发 daemon 写同一表 → race condition + 部分数据丢失)
_CLIENT_WRITE_LOCKS: dict[str, threading.Lock] = {}
_CLIENT_WRITE_LOCKS_MUX = threading.Lock()


def _get_client_write_lock(client_id: str) -> threading.Lock:
    """返回该 client 的写锁(全 backend 进程共用,不跨进程)."""
    with _CLIENT_WRITE_LOCKS_MUX:
        lock = _CLIENT_WRITE_LOCKS.get(client_id)
        if lock is None:
            lock = threading.Lock()
            _CLIENT_WRITE_LOCKS[client_id] = lock
        return lock


def _claim_throttle(client_id: str, task: str, window_sec: float) -> bool:
    """获得任务执行许可. True = 可以跑; False = 窗口内已跑过, 跳过."""
    key = (client_id, task)
    now = time.time()
    with _THROTTLE_LOCK:
        last = _THROTTLE_STATE.get(key, 0.0)
        if now - last < window_sec:
            return False
        _THROTTLE_STATE[key] = now
        return True


def reset_throttle(client_id: str | None = None) -> None:
    """测试 / 用户强制刷新时清掉 throttle. None = 全清."""
    with _THROTTLE_LOCK:
        if client_id is None:
            _THROTTLE_STATE.clear()
        else:
            for key in list(_THROTTLE_STATE.keys()):
                if key[0] == client_id:
                    del _THROTTLE_STATE[key]


# ─── 主入口 ──────────────────────────────────────────────────────────────────

def broadcast_data_changed(
    db: Any,
    ai: Any,
    *,
    client_id: str,
    scope: str,
    sync_narrative: bool = True,
    sync_thoughts: bool = False,  # thoughts LLM 贵, 默认让用户点按钮触发
    sync_portrait: bool = True,
    sync_self_verify: bool = True,  # L3 自校验: 实体聚类+矛盾+canonical
    backend_base_url: str = "http://127.0.0.1:47829",
) -> dict[str, Any]:
    """写后扩散统一钩子.

    Args:
        db: sqlite Database wrapper.
        ai: AI service.
        client_id: 哪个客户的数据变了.
        scope: 变更来源,用于日志 / dedupe,比如 'smart_import_story' / 'document_ingest'.
        sync_narrative: 是否后台自动重生 narrative (默认 True).
        sync_thoughts: 是否后台 refresh strategic_thoughts (默认 False, 太贵).
        sync_portrait: 是否后台跑 portrait_build (默认 True).
        backend_base_url: 本机 backend 地址,daemon thread 用 HTTP 调内部 endpoint.

    Returns:
        {triggered: [...], skipped: [...], errors: [...]}
    """
    triggered: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    if not client_id:
        return {"triggered": [], "skipped": ["no_client_id"], "errors": []}

    now_iso = _now_iso()

    # ── L1.1 ── enqueue analysis_job (轻, 后端 dedupe_key 防重)
    try:
        _enqueue_analysis_job(db, client_id, scope)
        triggered.append("analysis_job_enqueued")
    except Exception as exc:  # noqa: BLE001
        logger.exception("[broadcast] analysis_job enqueue failed")
        errors.append(f"analysis_job: {str(exc)[:100]}")

    # ── L1.2 ── mark narrative_stale_signals (轻, INSERT ON CONFLICT)
    if sync_narrative:
        try:
            _mark_narrative_stale(db, client_id, scope, now_iso)
            triggered.append("narrative_stale_marked")
        except Exception as exc:  # noqa: BLE001
            logger.exception("[broadcast] narrative_stale failed")
            errors.append(f"narrative_stale: {str(exc)[:100]}")

    # ── L2.1 ── portrait_build (LLM, throttle 60s)
    if sync_portrait:
        if _claim_throttle(client_id, "portrait_build", 60.0):
            threading.Thread(
                target=_bg_portrait_build,
                args=(db, ai, client_id, scope),
                daemon=True,
                name=f"bcast-portrait-{client_id[:8]}",
            ).start()
            triggered.append("portrait_build_queued")
        else:
            skipped.append("portrait_throttled")

    # ── L2.2 ── narrative regenerate (LLM, throttle 60s)
    if sync_narrative:
        if _claim_throttle(client_id, "narrative", 60.0):
            threading.Thread(
                target=_bg_regen_narrative,
                args=(client_id, scope, backend_base_url),
                daemon=True,
                name=f"bcast-narrative-{client_id[:8]}",
            ).start()
            triggered.append("narrative_regenerate_queued")
        else:
            skipped.append("narrative_throttled")

    # ── L2.3 ── refresh strategic_thoughts (LLM, throttle 90s, 默认 off)
    if sync_thoughts:
        if _claim_throttle(client_id, "thoughts", 90.0):
            threading.Thread(
                target=_bg_refresh_thoughts,
                args=(client_id, backend_base_url),
                daemon=True,
                name=f"bcast-thoughts-{client_id[:8]}",
            ).start()
            triggered.append("thoughts_refresh_queued")
        else:
            skipped.append("thoughts_throttled")

    # ── L3 ── AI 自校验: 实体聚类 / 矛盾检测 / canonical 化
    # 减少人工澄清的概率和内容 — 让 AI 自我审稿,主动标记矛盾和别名
    if sync_self_verify:
        if _claim_throttle(client_id, "self_verify", 120.0):
            threading.Thread(
                target=_bg_self_verify,
                args=(db, ai, client_id),
                daemon=True,
                name=f"bcast-verify-{client_id[:8]}",
            ).start()
            triggered.append("self_verify_queued")
        else:
            skipped.append("self_verify_throttled")

    logger.info(
        "[broadcast] client=%s scope=%s triggered=%s skipped=%s errors=%s",
        client_id, scope, triggered, skipped, errors,
    )
    return {"triggered": triggered, "skipped": skipped, "errors": errors}


# ─── L1: 同步操作 ────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _enqueue_analysis_job(db: Any, client_id: str, scope: str) -> None:
    """复用 analysis_center.create_analysis_job, dedupe_key 保证短时间内不重复."""
    from app.models import AnalysisJobCreatePayload
    from app.services.analysis_center import create_analysis_job

    create_analysis_job(
        db,
        AnalysisJobCreatePayload(
            jobType="strategy_pack",
            clientId=client_id,
            scopeType="client",
            scopeId=client_id,
            priority="normal",
            triggerType="auto",
            question=f"auto:{scope}",
            intentProfile="client_overview",
        ),
        source_snapshot={
            "clientId": client_id,
            "scopeType": "client",
            "scopeId": client_id,
            "triggerType": "auto",
            "reason": scope,
        },
    )


def _mark_narrative_stale(db: Any, client_id: str, scope: str, now_iso: str) -> None:
    """标 narrative 过期. PK=client_id, ON CONFLICT 覆盖 marked_at."""
    db.execute(
        """INSERT INTO narrative_stale_signals (client_id, marked_at, last_doc_title, reason)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(client_id) DO UPDATE SET
             marked_at=excluded.marked_at,
             reason=excluded.reason""",
        (client_id, now_iso, "", scope),
    )
    try:
        db.conn.commit()
    except Exception:  # noqa: BLE001
        pass


# ─── L2: 后台 LLM 操作 ───────────────────────────────────────────────────────

def _bg_portrait_build(db: Any, ai: Any, client_id: str, scope: str) -> None:
    """后台跑 portrait_build, 生成 relations/risk_signals/commitments (source=ai_inferred).

    用 per-client 写锁串行化, 避免跟 _bg_regen_narrative / _bg_self_verify 并发写冲突.
    """
    write_lock = _get_client_write_lock(client_id)
    if not write_lock.acquire(blocking=True, timeout=300.0):
        logger.warning("[broadcast bg portrait] lock timeout client=%s", client_id)
        return
    try:
        from app.services.project_portrait_builder import (
            backfill_task_glossary_links,
            build_portrait,
        )
        # 门槛:atomic_facts ≥ 10
        atomic_count = int(db.scalar(
            "SELECT COUNT(*) AS n FROM atomic_facts WHERE client_id = ? AND status = 'active'",
            (client_id,),
        ) or 0)
        if atomic_count < 10:
            logger.info(
                "[broadcast bg portrait] skip client=%s atomic=%d<10",
                client_id, atomic_count,
            )
            return
        backfill_task_glossary_links(db, client_id)
        result = build_portrait(db, ai, client_id)
        logger.info(
            "[broadcast bg portrait] client=%s scope=%s status=%s rels=%d risks=%d commits=%d",
            client_id, scope,
            result.get("status"),
            result.get("relations", 0),
            result.get("risk_signals", 0),
            result.get("commitments", 0),
        )
    except Exception:  # noqa: BLE001
        logger.exception("[broadcast bg portrait] failed client=%s", client_id)
    finally:
        write_lock.release()


def _bg_regen_narrative(client_id: str, scope: str, backend_base_url: str) -> None:
    """后台调本机 /narrative/regenerate. 内部跑 collect → LLM 生成 6 维度 → POST 云端持久化."""
    url = f"{backend_base_url}/api/v1/clients/{client_id}/narrative/regenerate"
    body = _json.dumps({"trigger": f"broadcast_{scope}", "force": True}).encode("utf-8")
    try:
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=180.0) as resp:
            payload = _json.loads(resp.read().decode("utf-8"))
            logger.info(
                "[broadcast bg narrative] client=%s rev=%s dims=%d scope=%s",
                client_id,
                payload.get("rev"),
                len(payload.get("dimensions") or []),
                scope,
            )
    except urllib.error.HTTPError as exc:
        logger.warning(
            "[broadcast bg narrative] http %s for client=%s: %s",
            exc.code, client_id, exc.reason,
        )
    except Exception:  # noqa: BLE001
        logger.exception("[broadcast bg narrative] failed client=%s", client_id)


def _bg_self_verify(db: Any, ai: Any, client_id: str) -> None:
    """后台跑 AI 自校验 (canonical + entity cluster + contradictions).

    用 per-client 写锁串行化, 避免跟 portrait/narrative 同时改 atomic_facts/entities.
    """
    write_lock = _get_client_write_lock(client_id)
    if not write_lock.acquire(blocking=True, timeout=300.0):
        logger.warning("[broadcast bg self_verify] lock timeout client=%s", client_id)
        return
    try:
        from app.services.data_center_self_verify import run_self_verify
        result = run_self_verify(db, ai, client_id)
        logger.info(
            "[broadcast bg self_verify] client=%s result=%s",
            client_id, result,
        )
    except Exception:  # noqa: BLE001
        logger.exception("[broadcast bg self_verify] failed client=%s", client_id)
    finally:
        write_lock.release()


def _bg_refresh_thoughts(client_id: str, backend_base_url: str) -> None:
    """后台调本机 /strategic/thoughts/refresh."""
    url = f"{backend_base_url}/api/v1/strategic/thoughts/refresh"
    body = _json.dumps({"clientId": client_id, "limit": 8}).encode("utf-8")
    try:
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=180.0) as resp:
            payload = _json.loads(resp.read().decode("utf-8"))
            logger.info(
                "[broadcast bg thoughts] client=%s thoughts=%d",
                client_id, len(payload.get("items") or []),
            )
    except urllib.error.HTTPError as exc:
        logger.warning(
            "[broadcast bg thoughts] http %s for client=%s: %s",
            exc.code, client_id, exc.reason,
        )
    except Exception:  # noqa: BLE001
        logger.exception("[broadcast bg thoughts] failed client=%s", client_id)
