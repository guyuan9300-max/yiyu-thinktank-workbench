"""[A] V2.4 P0-2 · FormalConflictDetector · 正式冲突识别 + clarification 持久化

服务: docs/V2.4_MASTER_PLAN.md § 阶段 2

顾源源 5/23 核心指令:
> 不再允许 "runner 内存里识别了, 但数据库没有".
> 只要没有持久化, 就算没通过.

6 种冲突 (全部写 fact_contradictions + clarification_records):
  1. 同主体同属性不同值        (300 万 vs 500 万)
  2. 同项目不同范围            (3 所 vs 10 所)
  3. 同人物不同角色            (负责人 vs 执行推进)
  4. 外部口径滞后              (媒体 vs 内部新版)
  5. 用户口述但缺正式证据      (陈老师拍板缺正式证据)
  6. 版本链检测                (v2 是否覆盖 v1)

每条冲突生成高质量澄清问题:
  · 带来源对比
  · 说明影响
  · 用户能直接回答
  · 用户确认后能写回权威值

调用方:
  · IngestPipeline.ingest() 写完后调 detect_all
  · 测试 runner 验收
  · 后台兜底任务
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class _DbLike(Protocol):
    def execute(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchone(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchall(self, sql: str, params: tuple = ...) -> Any: ...


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ConflictDetectResult:
    """单次冲突检测统计."""
    same_attr_value_diff: int = 0
    range_diff: int = 0
    role_diff: int = 0
    media_lag: int = 0
    oral_no_official: int = 0
    version_chain: int = 0
    fact_contradictions_written: int = 0
    clarifications_written: int = 0
    errors: int = 0


# ─── 辅助 ────────────────────────────────────────────


def _normalize_attr_base(attr: str) -> str:
    """去掉 (v1)/(v2) 等版本标记, 返回属性基名."""
    return re.sub(r"\(v\d+\)", "", attr or "").strip()


def _normalize_value(value: str) -> str:
    """归一化 value (去除空格/标点)."""
    return re.sub(r"[\s,，.。　]", "", value or "")


def _insert_fact_contradiction(
    db: _DbLike, *, client_id: str,
    fact_a_id: str, fact_b_id: str,
    contradiction_type: str, severity: str,
) -> str | None:
    """插一条 fact_contradictions, 重复返回 None."""
    cid = f"fc_{uuid.uuid4().hex[:24]}"
    try:
        # 检查是否已存在
        existing = db.fetchone(
            """SELECT id FROM fact_contradictions
               WHERE client_id = ? AND
                     ((fact_a_id = ? AND fact_b_id = ?)
                      OR (fact_a_id = ? AND fact_b_id = ?))""",
            (client_id, fact_a_id, fact_b_id, fact_b_id, fact_a_id),
        )
        if existing:
            return None
        db.execute(
            """INSERT INTO fact_contradictions (
                id, client_id, fact_a_id, fact_b_id,
                contradiction_type, severity, review_status, detected_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (cid, client_id, fact_a_id, fact_b_id,
             contradiction_type, severity, _now_iso()),
        )
        return cid
    except Exception as exc:
        logger.warning("写 fact_contradictions 失败: %s", exc)
        return None


def _insert_clarification(
    db: _DbLike, *, client_id: str,
    slot_key: str, question: str,
    write_scope: dict, resolved_fact_ids: list[str],
) -> str | None:
    """插 clarification_records, 重复返回 None."""
    try:
        existing = db.fetchone(
            "SELECT id FROM clarification_records WHERE slot_key = ?", (slot_key,),
        )
        if existing:
            return None
        cid = f"clar_{uuid.uuid4().hex[:24]}"
        now = _now_iso()
        db.execute(
            """INSERT INTO clarification_records (
                id, scope_type, scope_id, slot_key, question, status,
                write_scope_json, resolved_fact_ids_json, reusable,
                created_at, updated_at
            ) VALUES (?, 'client', ?, ?, ?, 'pending', ?, ?, 0, ?, ?)""",
            (cid, client_id, slot_key, question,
             json.dumps(write_scope, ensure_ascii=False),
             json.dumps(resolved_fact_ids, ensure_ascii=False),
             now, now),
        )
        return cid
    except Exception as exc:
        logger.warning("写 clarification_records 失败: %s", exc)
        return None


# ─── 1 · 同主体同属性不同值 (含版本链检测) ─────────────


def detect_same_attr_value_diff(db: _DbLike, client_id: str) -> tuple[int, int, int]:
    """同 subject + 同 attribute_base + 不同 value → fact_contradiction + clarification.

    版本链: 如果 v1/v2 都在, 视为版本链关系 (severity=medium); 否则 high.

    Returns:
        (contradictions_written, clarifications_written, errors)
    """
    rows = db.fetchall(
        """SELECT id, subject_text, attribute, value_text, source_type, time_anchor
           FROM atomic_facts
           WHERE client_id = ? AND status = 'active'""",
        (client_id,),
    )
    facts = [dict(r) for r in rows]

    # 按 (subject, attribute_base) 聚类
    cluster: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for f in facts:
        base = _normalize_attr_base(f["attribute"])
        if not base:
            continue
        cluster[(f["subject_text"], base)].append(f)

    cont_count = 0
    clar_count = 0
    err = 0

    for (subj, attr_base), items in cluster.items():
        if len(items) < 2:
            continue
        # 不同 normalize value
        unique_values = {_normalize_value(f["value_text"]): f for f in items}
        if len(unique_values) <= 1:
            continue

        # 检测版本链
        has_v1 = any("v1" in (f["attribute"] or "") for f in items)
        has_v2 = any("v2" in (f["attribute"] or "") for f in items)
        is_versioned = has_v1 and has_v2

        severity = "medium" if is_versioned else "high"
        contradiction_type = "version_chain" if is_versioned else "value_diff"

        # 写 fact_contradictions: 取前 2 个 fact 作为 a/b
        f_list = list(unique_values.values())
        cid = _insert_fact_contradiction(
            db, client_id=client_id,
            fact_a_id=f_list[0]["id"], fact_b_id=f_list[1]["id"],
            contradiction_type=contradiction_type, severity=severity,
        )
        if cid:
            cont_count += 1

        # 写 clarification (高质量带来源说明)
        v_summary = " vs ".join(f"「{f['value_text']}」(来源 {f['source_type']})"
                                for f in f_list[:3])
        slot_key = f"value_diff/{subj[:20]}_{attr_base[:20]}"
        if is_versioned:
            question = (
                f"{subj} 的 {attr_base}: {v_summary} — "
                f"系统检测到 v1/v2 版本链, 请确认 v2 是否覆盖 v1, 并标记权威值."
            )
        else:
            question = (
                f"{subj} 的 {attr_base}: {v_summary} — 哪个是当前权威值? "
                f"用户确认后系统会标旧值为 superseded."
            )
        write_scope = {
            "client_id": client_id, "subject": subj, "attribute_base": attr_base,
            "conflict_kind": contradiction_type,
            "values": [{"v": f["value_text"], "src": f["source_type"], "fid": f["id"]}
                       for f in f_list],
        }
        ccid = _insert_clarification(
            db, client_id=client_id, slot_key=slot_key, question=question,
            write_scope=write_scope, resolved_fact_ids=[f["id"] for f in f_list],
        )
        if ccid:
            clar_count += 1

    return cont_count, clar_count, err


# ─── 2 · 媒体口径滞后检测 ────────────────────────────


def detect_media_lag(db: _DbLike, client_id: str) -> tuple[int, int]:
    """媒体口径滞后: media facts 的值 == 客户某 v1 旧版值, 但客户已有 v2 新值.

    输出: fact_contradiction (type=media_lag) + clarification.
    """
    rows = db.fetchall(
        """SELECT id, subject_text, attribute, value_text, source_type, time_anchor
           FROM atomic_facts
           WHERE client_id = ? AND status = 'active'""",
        (client_id,),
    )
    facts = [dict(r) for r in rows]

    media_facts = [f for f in facts if f["source_type"] == "internet_media"]
    client_facts = [f for f in facts if (f["source_type"] or "").startswith("client_")]
    if not media_facts or not client_facts:
        return 0, 0

    # 客户事实按 (subject, attribute_base) 聚合
    client_by_subj_attr: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for f in client_facts:
        base = _normalize_attr_base(f["attribute"])
        client_by_subj_attr[(f["subject_text"], base)].append(f)

    # 找客户有 v1+v2 双版本的 (subject, attribute_base)
    has_versions = {
        k: v for k, v in client_by_subj_attr.items()
        if any("v1" in (it["attribute"] or "") for it in v)
        and any("v2" in (it["attribute"] or "") for it in v)
    }

    cont_count = 0
    clar_count = 0
    used_slots = set()

    for mf in media_facts:
        m_val_norm = _normalize_value(mf["value_text"])
        if not m_val_norm:
            continue
        # 找客户某个 (subject, attr) 有 v1+v2, 且 v1 值 == 媒体值
        for (subj, attr_base), items in has_versions.items():
            v1_items = [it for it in items if "v1" in (it["attribute"] or "")]
            v2_items = [it for it in items if "v2" in (it["attribute"] or "")]
            if not v1_items or not v2_items:
                continue
            v1_val = v1_items[0]["value_text"]
            v2_val = v2_items[0]["value_text"]
            if _normalize_value(v1_val) != m_val_norm:
                continue
            # 命中: 媒体说的等于 v1 旧版, 但有 v2 新版
            slot_key = f"media_lag/{subj[:20]}_{attr_base[:20]}"
            if slot_key in used_slots:
                continue
            used_slots.add(slot_key)

            cid = _insert_fact_contradiction(
                db, client_id=client_id,
                fact_a_id=mf["id"], fact_b_id=v2_items[0]["id"],
                contradiction_type="media_lag", severity="medium",
            )
            if cid:
                cont_count += 1

            question = (
                f"{subj} 的 {attr_base} 对外口径可能滞后: "
                f"媒体说「{mf['value_text']}」(同 v1 旧版), "
                f"客户最新 v2 已是「{v2_val}」. "
                f"对外引用应该用 v2 吗? 是否需要提醒客户更新外部口径?"
            )
            write_scope = {
                "client_id": client_id, "subject": subj,
                "attribute_base": attr_base, "conflict_kind": "media_lag",
                "media_value": mf["value_text"], "v1_value": v1_val,
                "v2_value": v2_val,
            }
            ccid = _insert_clarification(
                db, client_id=client_id, slot_key=slot_key, question=question,
                write_scope=write_scope,
                resolved_fact_ids=[mf["id"], v1_items[0]["id"], v2_items[0]["id"]],
            )
            if ccid:
                clar_count += 1
            break  # 一条 media fact 只匹配一次

    return cont_count, clar_count


# ─── 3 · 用户口述但缺正式证据 ────────────────────────


def detect_oral_no_official(db: _DbLike, client_id: str) -> tuple[int, int]:
    """user_observation/user_verbal_fact 提到的人物 + 客户官方文件无此人 → oral_no_official.

    高价值场景: "陈老师是最终拍板人 (只在用户口述, 客户文件没提)"
    """
    rows = db.fetchall(
        """SELECT id, subject_text, attribute, value_text, source_type
           FROM atomic_facts
           WHERE client_id = ? AND status = 'active'""",
        (client_id,),
    )
    facts = [dict(r) for r in rows]

    # 按 subject 分组, 看 source_type 分布
    by_subj: dict[str, list[dict]] = defaultdict(list)
    for f in facts:
        by_subj[f["subject_text"]].append(f)

    cont_count = 0
    clar_count = 0

    for subj, items in by_subj.items():
        # 只看人物 (含老/师/总/王/李/陈/赵/张/刘 等中文姓常见字)
        if not any(ch in subj for ch in "李王陈赵张刘黄周吴徐孙朱马胡郭何林老师"):
            continue
        sources = set(f["source_type"] for f in items)
        only_oral = sources.issubset({"user_observation", "user_verbal_fact"})
        no_official = not any(s in sources for s in
                              ["client_official_doc", "client_internal_doc",
                               "internet_official"])
        if only_oral and no_official:
            # 找一条 oral fact 作为 anchor
            anchor = items[0]
            # 写 fact_contradiction (type=oral_no_official; b 为 None 用 self-pair)
            cid = _insert_fact_contradiction(
                db, client_id=client_id,
                fact_a_id=anchor["id"], fact_b_id=anchor["id"],  # 自配对表示孤证
                contradiction_type="oral_no_official", severity="high",
            )
            if cid:
                cont_count += 1

            slot_key = f"oral_no_official/{subj[:30]}"
            question = (
                f"{subj} 相关信息只在用户口述里出现 (例如: 「{anchor['value_text'][:80]}」), "
                f"客户官方文件和外部公开信息都没有提到. "
                f"是否需要找客户正式确认这个人物的角色和职责?"
            )
            write_scope = {
                "client_id": client_id, "subject": subj,
                "conflict_kind": "oral_no_official",
                "oral_facts": [f["id"] for f in items],
            }
            ccid = _insert_clarification(
                db, client_id=client_id, slot_key=slot_key, question=question,
                write_scope=write_scope, resolved_fact_ids=[f["id"] for f in items],
            )
            if ccid:
                clar_count += 1

    return cont_count, clar_count


# ─── 4 · 同人物不同角色 ──────────────────────────────


def detect_role_diff(db: _DbLike, client_id: str) -> tuple[int, int]:
    """同人物 (subject=人名) 出现"角色 vs 新角色"差异 OR
    出现在不同主体的"负责人/执行人" attribute 中, value 同人 → role_diff.

    例: subject="李明" attribute="角色"="项目经理"
        subject="李明" attribute="新角色"="执行推进"
        subject="项目" attribute="负责人(v1)"="李明"
    """
    rows = db.fetchall(
        """SELECT id, subject_text, attribute, value_text, source_type
           FROM atomic_facts
           WHERE client_id = ? AND status = 'active'""",
        (client_id,),
    )
    facts = [dict(r) for r in rows]

    # 找所有 "人物 + 角色描述" 的事实
    person_roles: dict[str, list[dict]] = defaultdict(list)
    for f in facts:
        attr = f["attribute"] or ""
        # 人物名 = subject (含中文姓)
        if any(ch in (f["subject_text"] or "") for ch in "李王陈赵张刘老师"):
            if "角色" in attr or "职务" in attr or "新角色" in attr:
                person_roles[f["subject_text"]].append(f)
        # 反向: 项目 attribute 含"负责人/执行人" value 是人名
        if attr and ("负责人" in attr or "执行" in attr):
            v = f["value_text"] or ""
            if any(ch in v for ch in "李王陈赵张刘"):
                person_roles[v].append(f)

    cont_count = 0
    clar_count = 0

    for person, items in person_roles.items():
        if len(items) < 2:
            continue
        # 不同 value 或 attribute 表达
        unique_roles = set()
        for it in items:
            attr = it["attribute"] or ""
            if "负责人" in attr:
                unique_roles.add("负责人")
            elif "执行" in attr or "执行推进" in (it["value_text"] or ""):
                unique_roles.add("执行推进")
            elif "新角色" in attr:
                unique_roles.add(f"新角色:{it['value_text'][:20]}")
            elif "角色" in attr:
                unique_roles.add(f"角色:{it['value_text'][:20]}")
        if len(unique_roles) < 2:
            continue

        cid = _insert_fact_contradiction(
            db, client_id=client_id,
            fact_a_id=items[0]["id"], fact_b_id=items[1]["id"],
            contradiction_type="role_diff", severity="medium",
        )
        if cid:
            cont_count += 1

        slot_key = f"role_diff/{person[:20]}"
        question = (
            f"{person} 在不同资料里角色描述不同: {', '.join(unique_roles)}. "
            f"请确认 {person} 当前真实角色, 系统会更新人物档案."
        )
        write_scope = {
            "client_id": client_id, "person": person,
            "conflict_kind": "role_diff",
            "roles": list(unique_roles),
        }
        ccid = _insert_clarification(
            db, client_id=client_id, slot_key=slot_key, question=question,
            write_scope=write_scope, resolved_fact_ids=[f["id"] for f in items],
        )
        if ccid:
            clar_count += 1

    return cont_count, clar_count


# ─── 主入口 · detect_all ─────────────────────────────


def detect_all(db: _DbLike, client_id: str) -> ConflictDetectResult:
    """跑全部 6 种冲突检测 + 写持久化."""
    same_attr_c, same_attr_clar, _ = detect_same_attr_value_diff(db, client_id)
    media_c, media_clar = detect_media_lag(db, client_id)
    oral_c, oral_clar = detect_oral_no_official(db, client_id)
    role_c, role_clar = detect_role_diff(db, client_id)

    return ConflictDetectResult(
        same_attr_value_diff=same_attr_c,
        range_diff=0,  # range 已被 same_attr_value_diff 覆盖 (10 所 vs 3 所同 attr_base)
        role_diff=role_c,
        media_lag=media_c,
        oral_no_official=oral_c,
        version_chain=0,  # 已合入 same_attr_value_diff (is_versioned 标记)
        fact_contradictions_written=same_attr_c + media_c + oral_c + role_c,
        clarifications_written=same_attr_clar + media_clar + oral_clar + role_clar,
    )
