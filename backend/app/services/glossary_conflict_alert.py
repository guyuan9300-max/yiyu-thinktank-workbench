"""新文件 vs 字典权威值冲突报警 (Codex 方案 A · 强提示).

机制:
- 用户在字典里审过 X.attribute = V (verified)
- 新文件 ingest 进来抽出新 atomic_fact: X.attribute = V', V' != V
- 系统立刻报警: "与字典冲突, 要不要更新字典", 不等用户事后翻才发现

输出到 fact_contradictions 表 (复用现有审核流), severity='high',
contradiction_type='glossary_drift', 这样在事实澄清面板里就能看到。
"""
from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def check_fact_against_glossary(
    conn: sqlite3.Connection,
    *,
    client_id: str,
    new_fact_id: str,
    subject_text: str,
    attribute: str,
    value_text: str,
) -> dict[str, Any]:
    """检查新事实是否与字典 verified attribute 冲突, 命中即报警.

    Returns:
        {"conflict": True, "alert_id": ..., "verified_value": ...} 命中
        {"conflict": False} 没命中
    """
    if not (subject_text and attribute and value_text):
        return {"conflict": False, "reason": "empty"}

    # 字典 attribute term 可能跟 fact subject 不完全一致 (例: "D组织" vs "D组织基金会")
    # 用 LIKE 匹配, 加上 attribute_name 精确匹配
    try:
        from app.services.text_normalizer import is_noise_difference

        attrs = conn.execute(
            """SELECT ga.id, ga.value_text, ga.attribute_name, cg.term
               FROM glossary_attributes ga
               JOIN client_glossary cg ON cg.id = ga.term_id
               WHERE ga.client_id = ?
                 AND ga.verification_status = 'verified'
                 AND (cg.term = ? OR cg.term LIKE ? OR ? LIKE '%' || cg.term || '%')
                 AND (ga.attribute_name = ? OR ga.attribute_name LIKE ?)""",
            (
                client_id,
                subject_text,
                f"%{subject_text}%",
                subject_text,
                attribute,
                f"%{attribute}%",
            ),
        ).fetchall()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[glossary-conflict] query failed: %s", exc)
        return {"conflict": False, "reason": f"query failed: {exc}"}

    if not attrs:
        return {"conflict": False, "reason": "no matching verified attribute"}

    # 检查 value 是否一致 (OCR 噪声归一后比较)
    for ga in attrs:
        verified_value = str(ga["value_text"] or "")
        if is_noise_difference(value_text, verified_value):
            return {"conflict": False, "reason": "value matches verified"}

    # 真冲突 — 写入 glossary_drift_alerts 表 (跟 fact_contradictions 解耦)
    target = attrs[0]  # 取第一条 verified 作为对比锚点
    verified_value = str(target["value_text"] or "")
    now = datetime.now(timezone.utc).isoformat()
    alert_id = f"drift_{uuid.uuid4().hex[:10]}"
    try:
        conn.execute(
            """INSERT INTO glossary_drift_alerts (
                id, client_id, glossary_attribute_id, new_fact_id,
                verified_value_text, new_value_text,
                severity, review_status, detected_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'high', 'pending', ?)""",
            (alert_id, client_id, str(target["id"]), new_fact_id,
             verified_value, value_text, now),
        )
        logger.info(
            "[glossary-drift] client=%s fact=%s vs verified=%s.%s: '%s' → '%s'",
            client_id, new_fact_id, target["term"], target["attribute_name"],
            verified_value[:30], value_text[:30],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[glossary-drift] insert alert failed: %s", exc)
        return {"conflict": True, "alert_id": None, "error": str(exc)}

    return {
        "conflict": True,
        "alert_id": alert_id,
        "verified_term": str(target["term"]),
        "verified_attr": str(target["attribute_name"]),
        "verified_value": verified_value,
        "new_value": value_text,
    }
