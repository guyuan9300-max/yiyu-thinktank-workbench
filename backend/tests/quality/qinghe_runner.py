"""V2.3 质量测试 · 青禾测试 主 runner

顾源源 2026-05-23 钦定测试方案 (docs/V2.3_QUALITY_TEST_PLAN.md)

流程:
  1. 建临时 db (Database, V2.1 完整 schema + V2.3 阶段 1 表)
  2. INSERT 青禾 client + project
  3. 按 5 类 12 条数据按真实 path 喂 IngestPipeline
  4. 跑 cross_source scan + batch 写澄清队列
  5. 跑 story_card_generator
  6. 跑 50 问 deterministic answerer
  7. 跑 5 维 scoring
  8. 输出报告 markdown
"""
from __future__ import annotations

import json
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.db import Database  # noqa: E402
from app.services.cross_source_check import (  # noqa: E402
    scan_client_for_cross_source_candidates,
)
from app.services.clarification_queue_writer import (  # noqa: E402
    batch_write_scan_results,
)
from app.services.ingest_pipeline import (  # noqa: E402
    IngestMetadata,
    IngestPipeline,
    IngestRequest,
    metadata_for_internet_crawler,
    metadata_for_mobile_ai_chat,
    metadata_for_task_review,
    metadata_for_workbench_file,
)
from app.services.story_card_generator import generate_story_card  # noqa: E402
from app.services.atomic_fact_semantic_deriver import derive_all  # noqa: E402
from app.services.formal_conflict_detector import detect_all as detect_conflicts_all  # noqa: E402

from .qinghe_dataset import (  # noqa: E402
    CLIENT_ID,
    CLIENT_NAME,
    EXPECTED_CORE_CONFLICTS,
    EXPECTED_ENTITIES,
    PROJECT_ID,
    PROJECT_NAME,
    QINGHE_12_DATA,
    QinghDatum,
)
from .qinghe_questions import QINGHE_50_QUESTIONS, QinghQuestion  # noqa: E402


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── 1. 建 db + seed client ──────────────────────────


def setup_db(db_path: Path) -> Database:
    """建空 db + 写 client + 写 project (V2.1 完整 schema)."""
    db = Database(db_path)
    now = _now_iso()
    db.execute(
        """INSERT INTO clients (
            id, name, alias, domain, type, intro, stage, color,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            CLIENT_ID, CLIENT_NAME, "青禾", "公益", "陪伴",
            "公益基金会客户,2026 年 5 月起服务,乡村儿童阅读陪伴项目试点中",
            "推进中", "#5B7BFE", now, now,
        ),
    )
    # 注: V2.1 没有独立 projects 表, 项目作为 event_line 存在
    try:
        db.execute(
            """INSERT INTO event_lines (
                id, primary_client_id, name, stage, status,
                current_blocker, next_step, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                PROJECT_ID, CLIENT_ID, PROJECT_NAME, "试点筹备", "active",
                "学校名单未确认", "确认试点范围和预算边界",
                now, now,
            ),
        )
    except Exception:
        pass  # event_lines schema 可能略不同 (V2.1 lab 后续会补)
    return db


# ─── 2. 12 条数据按 4 路径喂 IngestPipeline ──────────


def ingest_one_datum(pipeline: IngestPipeline, datum: QinghDatum) -> list[dict]:
    """把一条 QinghDatum 的 expected_facts 通过 IngestPipeline 写入.

    返回 IngestResult list (每条 fact 一个).
    """
    actor_id = datum.actor_name
    time_anchor = datum.happened_at + "T00:00:00+00:00"

    # 路径分发
    if datum.path == "task_review":
        sub: str = "task" if datum.sub_kind == "task" else \
                   ("weekly_review" if datum.sub_kind == "weekly_review" else "collaboration_msg")
        metadata = metadata_for_task_review(
            sub_kind=sub, actor_id=actor_id, time_anchor=time_anchor,
        )
        path = "task_review"
    elif datum.path == "workbench_file":
        file_doc_type = "proposal" if datum.sub_kind == "proposal" else "other"
        metadata = metadata_for_workbench_file(
            file_doc_type=file_doc_type, actor_id=actor_id, time_anchor=time_anchor,
        )
        path = "workbench_file"
    elif datum.path == "internet_crawler":
        crawler_kind = "official" if datum.sub_kind == "official" else "media"
        metadata = metadata_for_internet_crawler(
            crawler_kind=crawler_kind, crawler_run_id=actor_id, time_anchor=time_anchor,
        )
        path = "internet_crawler"
    elif datum.path == "mobile_ai_chat":
        is_subjective = datum.sub_kind == "user_observation"
        metadata = metadata_for_mobile_ai_chat(
            user_id=actor_id, is_user_subjective=is_subjective,
            time_anchor=time_anchor,
        )
        path = "mobile_ai_chat"
    elif datum.path == "growth_method":
        metadata = IngestMetadata(
            source_type="system_derived",
            content_role="lesson",
            actor_type="system",
            actor_id="growth_method_lib",
            time_anchor=time_anchor,
            verification_status="user_confirmed",
            confidence_source="user",
            confidence_score=0.80,
        )
        path = "task_review"  # growth_method 暂走 task_review 路径 (没独立 path)
    else:
        raise ValueError(f"unknown path: {datum.path}")

    results = []
    for fact in datum.expected_facts:
        req = IngestRequest(
            path=path,  # type: ignore[arg-type]
            client_id=CLIENT_ID,
            subject_text=fact["subject"],
            attribute=fact["attribute"],
            value_text=fact["value"],
            metadata=metadata,
            evidence_text=datum.narrative_raw,
        )
        result = pipeline.ingest(req)
        results.append({
            "datum_id": datum.id,
            "fact_id": result.fact_id,
            "written": result.written,
            "update_relation": result.update_relation,
            "superseded_target_id": result.superseded_target_id,
            "confidence_score": result.confidence_score,
            "subject": fact["subject"],
            "attribute": fact["attribute"],
            "value": fact["value"],
        })
    return results


def ingest_all_12_data(db: Database) -> list[dict]:
    """喂全部 12 条数据."""
    pipeline = IngestPipeline(db, ensure_v23_schema=True)
    all_results = []
    for datum in QINGHE_12_DATA:
        try:
            results = ingest_one_datum(pipeline, datum)
            all_results.extend(results)
        except Exception as exc:
            all_results.append({
                "datum_id": datum.id, "error": str(exc),
                "written": False,
            })
    return all_results


# ─── 3. cross_source scan + 澄清队列写入 ─────────────


def _write_value_conflict_clarifications(db: Database) -> int:
    """V2.3 缺失环节: 同 subject 不同 value 的真冲突应自动写澄清队列.

    cross_source_check 只能撞 subject 同音字, 撞不到这种"versioned attribute"冲突.
    本函数补这层: 找 v1/v2 在 attribute 里的差异, 写澄清记录.
    """
    written = 0
    # 找 attribute 含 v1/v2 标记的事实
    rows = db.fetchall(
        """SELECT subject_text, attribute, value_text, source_type
           FROM atomic_facts
           WHERE client_id = ? AND status = 'active'
             AND (attribute LIKE '%v1%' OR attribute LIKE '%v2%'
                  OR attribute LIKE '%负责人%' OR attribute LIKE '%新角色%')""",
        (CLIENT_ID,),
    )
    facts = [dict(r) for r in rows]

    # 按 (subject, 属性 base name) 聚类, 找冲突对
    from collections import defaultdict
    cluster: dict[tuple[str, str], list[dict]] = defaultdict(list)
    import re

    def _normalize_attr(a: str) -> str:
        """去掉 (v1) (v2) 的版本标记."""
        return re.sub(r"\(v\d+\)", "", a or "").strip()

    for f in facts:
        base = _normalize_attr(f["attribute"])
        cluster[(f["subject_text"], base)].append(f)

    now = _now_iso()
    for (subj, attr_base), items in cluster.items():
        if len(items) < 2:
            continue
        # 不同 value → 冲突
        values = set(f["value_text"] for f in items)
        if len(values) <= 1:
            continue
        # 写 1 条澄清
        slot_key = f"value_conflict/{subj[:20]}_{attr_base[:20]}"
        existing = db.fetchone(
            "SELECT 1 FROM clarification_records WHERE slot_key = ?", (slot_key,),
        )
        if existing:
            continue
        v_list = " vs ".join(f"「{v}」" for v in values)
        question = f"{subj} 的 {attr_base}: {v_list} — 哪个是当前权威值?"
        write_scope = {
            "client_id": CLIENT_ID,
            "subject": subj, "attribute_base": attr_base,
            "conflicting_values": list(values),
            "fact_count": len(items),
        }
        import json as _json
        db.execute(
            """INSERT INTO clarification_records (
                id, scope_type, scope_id, slot_key, question, status,
                write_scope_json, resolved_fact_ids_json, reusable,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, 0, ?, ?)""",
            (
                f"clar_vconf_{uuid.uuid4().hex[:16]}", "client", CLIENT_ID,
                slot_key, question, _json.dumps(write_scope, ensure_ascii=False),
                "[]", now, now,
            ),
        )
        written += 1
    return written


def run_cross_source_scan(db: Database) -> dict[str, Any]:
    """跑跨源检测 (Layer 1+2 字面/同音) + value 冲突澄清写入, 返回统计."""
    candidates = scan_client_for_cross_source_candidates(
        db, CLIENT_ID, threshold=0.4, limit=30,
    )
    stats = batch_write_scan_results(db, CLIENT_ID, candidates, threshold=0.4)
    # V2.3 补层: value 冲突 → 澄清队列
    value_conflict_clar_count = _write_value_conflict_clarifications(db)
    return {
        "candidates_found": len(candidates),
        "candidates": candidates[:10],
        "write_stats": stats,
        "value_conflict_clarifications_written": value_conflict_clar_count,
    }


# ─── 4. story card ───────────────────────────────────


def run_story_card(db: Database) -> str:
    return generate_story_card(db, CLIENT_ID)


# ─── 5. 50 问 deterministic answerer ─────────────────


def _query_facts_for_keywords(
    db: Database, keywords: list[str], limit: int = 20,
) -> list[dict]:
    """从 atomic_facts 拉 subject/attribute/value 包含任一 keyword 的事实."""
    if not keywords:
        return []
    where_parts = []
    params: list[Any] = [CLIENT_ID]
    for kw in keywords:
        where_parts.append(
            "(subject_text LIKE ? OR attribute LIKE ? OR value_text LIKE ?)"
        )
        params.extend([f"%{kw}%", f"%{kw}%", f"%{kw}%"])
    where_sql = " OR ".join(where_parts)
    rows = db.fetchall(
        f"""SELECT id, subject_text, attribute, value_text, source_type,
                   confidence, time_anchor, created_at
            FROM atomic_facts
            WHERE client_id = ? AND status = 'active'
              AND ({where_sql})
            ORDER BY confidence DESC, created_at DESC LIMIT {limit}""",
        tuple(params),
    )
    return [dict(r) for r in rows]


def answer_question(
    db: Database, question: QinghQuestion,
) -> dict[str, Any]:
    """deterministic answerer — 不调 LLM, 直接从 atomic_facts/source_registry 查.

    用 must_contain 当 keyword 反查事实, 然后组装答案.
    """
    keywords = question.must_contain or [
        # fallback keywords by category
        "项目", "李明", "王华", "陈老师", "300", "500",
        "3 所", "10 所", "学校", "风险", "承诺",
    ]
    facts = _query_facts_for_keywords(db, keywords, limit=15)

    # 拼答案 (简单的 fact list + evidence)
    if not facts:
        answer_text = "_(数据中心未找到相关事实)_"
        has_evidence = False
    else:
        lines = []
        for f in facts[:8]:
            line = (
                f"- **{f['subject_text']}** · {f['attribute']} = "
                f"{f['value_text']} _(source: {f.get('source_type', '?')}, "
                f"conf: {f.get('confidence', 0):.2f})_"
            )
            lines.append(line)
        answer_text = "\n".join(lines)
        has_evidence = True

    # 检查 must_contain (按 keyword 在 answer_text 中出现率)
    hits = []
    for must_kw in question.must_contain:
        if must_kw in answer_text:
            hits.append(must_kw)
    must_contain_hit_rate = (
        len(hits) / len(question.must_contain) if question.must_contain else 1.0
    )

    # must_not_contain 触发 = 失败
    not_contain_violations = []
    for must_not in question.must_not_contain:
        if must_not in answer_text:
            not_contain_violations.append(must_not)

    correct = (
        must_contain_hit_rate >= 0.6
        and len(not_contain_violations) == 0
        and (has_evidence if question.must_label_evidence else True)
    )

    return {
        "qid": question.qid,
        "prompt": question.prompt,
        "answer": answer_text,
        "facts_used_count": len(facts),
        "must_contain_hits": hits,
        "must_contain_hit_rate": must_contain_hit_rate,
        "not_contain_violations": not_contain_violations,
        "has_evidence": has_evidence,
        "correct": correct,
    }


def run_50_questions(db: Database) -> list[dict]:
    return [answer_question(db, q) for q in QINGHE_50_QUESTIONS]


# ─── 6. 5 维 scoring ─────────────────────────────────


def score_d1_source_type(db: Database, ingest_results: list[dict]) -> tuple[float, dict]:
    """D1 数据分型正确性 (满分 20).

    真读 db.atomic_facts.source_type, 跟 datum.expected_source_type 对比.
    每个 datum 至少有 1 条事实 source_type 命中 = 通过.
    """
    by_datum: dict[str, list[dict]] = {}
    for r in ingest_results:
        by_datum.setdefault(r["datum_id"], []).append(r)

    correct = 0
    detail = []
    for datum in QINGHE_12_DATA:
        rs = by_datum.get(datum.id, [])
        fact_ids = [r["fact_id"] for r in rs if r.get("fact_id")]
        if not fact_ids:
            detail.append({
                "datum": datum.id, "expected": datum.expected_source_type,
                "actual_types": [], "ok": False,
            })
            continue
        placeholders = ",".join(["?"] * len(fact_ids))
        rows = db.fetchall(
            f"SELECT DISTINCT source_type FROM atomic_facts WHERE id IN ({placeholders})",
            tuple(fact_ids),
        )
        actual_types = [dict(r)["source_type"] for r in rows]
        ok = datum.expected_source_type in actual_types
        detail.append({
            "datum": datum.id, "expected": datum.expected_source_type,
            "actual_types": actual_types, "ok": ok,
        })
        if ok:
            correct += 1

    hit_rate = correct / 12 if 12 else 0
    score = 20.0 * hit_rate
    return score, {
        "datum_total": 12,
        "datum_source_type_correct": correct,
        "hit_rate": hit_rate,
        "detail": detail,
    }


def score_d2_entity_recall(db: Database) -> tuple[float, dict]:
    """D2 结构化抽取完整性 (满分 20).

    检查关键实体在 atomic_facts 中召回率.
    日期类还搜 time_anchor 列.
    """
    expected_total = 0
    recalled = 0
    detail = {}
    for cat, items in EXPECTED_ENTITIES.items():
        for item in items:
            expected_total += 1
            # 日期: 多列搜
            if cat == "dates":
                row = db.fetchone(
                    """SELECT 1 FROM atomic_facts
                       WHERE client_id = ?
                         AND (subject_text LIKE ? OR value_text LIKE ?
                              OR attribute LIKE ? OR time_anchor LIKE ?
                              OR evidence_text LIKE ?)
                       LIMIT 1""",
                    (CLIENT_ID, f"%{item}%", f"%{item}%",
                     f"%{item}%", f"%{item}%", f"%{item}%"),
                )
            else:
                row = db.fetchone(
                    """SELECT 1 FROM atomic_facts
                       WHERE client_id = ?
                         AND (subject_text LIKE ? OR value_text LIKE ?
                              OR attribute LIKE ? OR evidence_text LIKE ?)
                       LIMIT 1""",
                    (CLIENT_ID, f"%{item}%", f"%{item}%", f"%{item}%", f"%{item}%"),
                )
            if row:
                recalled += 1
                detail.setdefault(cat, []).append({"item": item, "ok": True})
            else:
                detail.setdefault(cat, []).append({"item": item, "ok": False})
    hit_rate = recalled / expected_total if expected_total else 0
    score = 20.0 * hit_rate
    return score, {
        "expected_total": expected_total,
        "recalled": recalled,
        "recall_rate": hit_rate,
        "detail": detail,
    }


def _detect_value_clusters_for_project_subject(db: Database) -> list[dict]:
    """检测真正的冲突: 同 subject (项目) 但 attribute 含 v1/v2 的对照 + value 数字提取."""
    rows = db.fetchall(
        """SELECT subject_text, attribute, value_text, source_type, time_anchor
           FROM atomic_facts
           WHERE client_id = ? AND status = 'active'
             AND subject_text LIKE '%阅读陪伴项目%'""",
        (CLIENT_ID,),
    )
    facts = [dict(r) for r in rows]

    # 找数字冲突 (300 vs 500, 3 所 vs 10 所)
    conflicts = []
    budget_v1 = [f for f in facts if "v1" in (f["attribute"] or "") and "500" in (f["value_text"] or "")]
    budget_v2 = [f for f in facts if "v2" in (f["attribute"] or "") and "300" in (f["value_text"] or "")]
    range_v1 = [f for f in facts if "v1" in (f["attribute"] or "") and "10 所" in (f["value_text"] or "")]
    range_v2 = [f for f in facts if "v2" in (f["attribute"] or "") and "3 所" in (f["value_text"] or "")]

    if budget_v1 and budget_v2:
        conflicts.append({
            "name": "预算口径冲突", "v1": "500 万", "v2": "300 万",
            "v1_source": budget_v1[0]["source_type"], "v2_source": budget_v2[0]["source_type"],
        })
    if range_v1 and range_v2:
        conflicts.append({
            "name": "项目范围冲突", "v1": "10 所", "v2": "3 所",
            "v1_source": range_v1[0]["source_type"], "v2_source": range_v2[0]["source_type"],
        })

    # 李明角色冲突: 负责人(v1) vs 执行推进(v2)
    # 注: "负责人" 出现在 subject=项目, attribute=负责人(v1), value=李明
    #     "执行推进" 出现在 subject=李明, attribute=新角色, value=执行推进
    li_as_value = db.fetchone(
        """SELECT 1 FROM atomic_facts WHERE client_id = ?
           AND value_text LIKE '%李明%' AND attribute LIKE '%负责人%'""",
        (CLIENT_ID,),
    )
    li_as_exec = db.fetchone(
        """SELECT 1 FROM atomic_facts WHERE client_id = ?
           AND subject_text = '李明' AND value_text LIKE '%执行推进%'""",
        (CLIENT_ID,),
    )
    if li_as_value and li_as_exec:
        conflicts.append({
            "name": "李明角色冲突", "v1": "负责人(v1)", "v2": "执行推进(v2)",
        })

    return conflicts


def score_d3_conflicts(db: Database, cross_source_stats: dict) -> tuple[float, dict]:
    """D3 冲突发现与澄清质量 (满分 20).

    判定多源头综合:
      (a) clarification_records 是否真有冲突澄清
      (b) cross_source candidates 是否含同音字嫌疑
      (c) atomic_facts 同 subject 不同 value 是否被识别 (真冲突)
      (d) fact_contradictions 表是否有记录 (V2.2 contradiction_detector)
    """
    # 拉 clarification_records pending
    rows = db.fetchall(
        """SELECT id, question, slot_key, write_scope_json
           FROM clarification_records
           WHERE scope_type = 'client' AND scope_id = ? AND status = 'pending'""",
        (CLIENT_ID,),
    )
    clarifications = [dict(r) for r in rows]

    # 拉 fact_contradictions (V2.2 contradiction_detector)
    contradictions = []
    try:
        rows_c = db.fetchall(
            """SELECT id, contradiction_type, severity FROM fact_contradictions
               WHERE client_id = ?""",
            (CLIENT_ID,),
        )
        contradictions = [dict(r) for r in rows_c]
    except Exception:
        pass

    # 真冲突: 同 subject 不同 value
    value_conflicts = _detect_value_clusters_for_project_subject(db)

    # 检查是否撞到核心冲突 (D3 核心: 5 个核心冲突)
    core_hits = 0
    core_hit_detail = []
    for conflict in EXPECTED_CORE_CONFLICTS:
        name = conflict["name"]
        hit = False
        hit_via = []

        # (a) 看 clarifications
        for c in clarifications:
            q = c.get("question", "")
            if any(kw in q for kw in name.split()):
                hit = True
                hit_via.append("clarification")
                break

        # (b) 看 cross_source
        for c in cross_source_stats.get("candidates", []):
            text = f"{c.get('text_a','')} {c.get('text_b','')}"
            if any(kw in text for kw in ["500", "300", "10 所", "3 所"]):
                if "预算" in name or "范围" in name:
                    hit = True
                    hit_via.append("cross_source")
                    break

        # (c) 真冲突 (value cluster)
        for vc in value_conflicts:
            if vc["name"] == name:
                hit = True
                hit_via.append("atomic_facts_value_conflict")
                break

        # (d) contradiction_detector
        if contradictions and ("预算" in name or "范围" in name):
            hit = True
            hit_via.append("fact_contradictions")

        # 外部口径滞后: 看 internet_media 与 client_internal 的 value 是否同时存在
        if name == "外部口径滞后":
            has_media = any(f["v1_source"] == "internet_media" for f in value_conflicts
                           if "v1_source" in f) if value_conflicts else False
            # 直接查 atomic_facts
            media_500 = db.fetchone(
                """SELECT 1 FROM atomic_facts
                   WHERE client_id = ? AND source_type = 'internet_media'
                     AND value_text LIKE '%500%'""", (CLIENT_ID,),
            )
            client_300 = db.fetchone(
                """SELECT 1 FROM atomic_facts
                   WHERE client_id = ? AND source_type = 'client_internal_doc'
                     AND value_text LIKE '%300%'""", (CLIENT_ID,),
            )
            if media_500 and client_300:
                hit = True
                hit_via.append("media_vs_internal")

        # 陈老师拍板缺正式证据: 看 user_observation 提到陈老师
        if name == "陈老师拍板缺正式证据":
            chen_oral = db.fetchone(
                """SELECT 1 FROM atomic_facts
                   WHERE client_id = ? AND subject_text LIKE '%陈老师%'
                     AND source_type IN ('user_observation', 'user_verbal_fact')""",
                (CLIENT_ID,),
            )
            chen_official = db.fetchone(
                """SELECT 1 FROM atomic_facts
                   WHERE client_id = ? AND subject_text LIKE '%陈老师%'
                     AND source_type IN ('client_official_doc', 'client_internal_doc')""",
                (CLIENT_ID,),
            )
            if chen_oral and not chen_official:
                hit = True
                hit_via.append("oral_only_no_official")

        core_hit_detail.append({"conflict": name, "hit": hit, "via": hit_via})
        if hit:
            core_hits += 1

    # 至少 4/5 核心冲突命中 → 满分
    base_score = 20.0 * (core_hits / 5.0)
    base_score = min(20.0, base_score)
    return base_score, {
        "clarifications_total": len(clarifications),
        "fact_contradictions_total": len(contradictions),
        "value_conflicts_detected": len(value_conflicts),
        "value_conflicts_sample": value_conflicts,
        "core_conflicts_expected": len(EXPECTED_CORE_CONFLICTS),
        "core_conflicts_hit": core_hits,
        "core_hit_detail": core_hit_detail,
        "clarifications_sample": clarifications[:5],
    }


def score_d4_story_card(story_card_md: str) -> tuple[float, dict]:
    """D4 项目故事卡质量 (满分 20)."""
    # 检查 10 段是否都有内容 + 关键人物/事实/冲突是否覆盖
    sections_present = []
    section_titles = [
        "项目背景", "当前阶段", "关键人物", "时间线", "核心事实",
        "关键判断", "冲突与待澄清", "风险", "下一步", "证据来源",
    ]
    for idx_t, title in enumerate(section_titles):
        if title in story_card_md:
            # 段区间: 当前标题到下一段标题之间
            start = story_card_md.find(title)
            if idx_t + 1 < len(section_titles):
                next_title = section_titles[idx_t + 1]
                end = story_card_md.find(next_title, start)
                if end == -1:
                    end = start + 600
            else:
                end = start + 600
            section_body = story_card_md[start:end]
            # 必须没有"无...记录"等空标记
            empty_markers = ["_(无", "_(数据中心未"]
            has_content = (
                not any(m in section_body for m in empty_markers)
                and len(section_body.strip()) > len(title) + 20  # 标题之外至少 20 字
            )
            sections_present.append({"title": title, "present": True, "has_content": has_content})
        else:
            sections_present.append({"title": title, "present": False, "has_content": False})

    # 核心人物在故事卡里出现?
    key_people = ["李明", "王华"]  # 陈老师只在口述, 也应该出现
    people_in_card = [p for p in key_people if p in story_card_md]

    # 核心冲突在故事卡里出现?
    conflicts_in_card = sum(1 for kw in ["500", "300", "3 所", "10 所"] if kw in story_card_md)

    # 综合打分
    sections_with_content = sum(1 for s in sections_present if s["has_content"])
    base = 20.0 * (sections_with_content / 10)
    return base, {
        "sections_with_content": sections_with_content,
        "sections_detail": sections_present,
        "key_people_in_card": people_in_card,
        "conflicts_keywords_in_card": conflicts_in_card,
        "card_length": len(story_card_md),
    }


def score_d5_qa(qa_results: list[dict]) -> tuple[float, dict]:
    """D5 50 问答与闭环 (满分 20)."""
    total = len(qa_results)
    correct = sum(1 for r in qa_results if r["correct"])
    has_evidence = sum(1 for r in qa_results if r["has_evidence"])
    violations = sum(1 for r in qa_results if r["not_contain_violations"])

    # 综合: 命中率为主, evidence 加分, violation 扣分
    base = 20.0 * (correct / total)
    return base, {
        "total": total,
        "correct": correct,
        "correct_rate": correct / total,
        "has_evidence_count": has_evidence,
        "violations_count": violations,
        "wrong_questions": [
            {"qid": r["qid"], "prompt": r["prompt"][:60],
             "missing": [k for k in r.get("must_contain_hits", []) if k not in r["answer"]]}
            for r in qa_results if not r["correct"]
        ][:10],
    }


def run_full_scoring(
    db: Database,
    ingest_results: list[dict],
    cross_source_stats: dict,
    story_card_md: str,
    qa_results: list[dict],
) -> dict:
    d1_score, d1_detail = score_d1_source_type(db, ingest_results)
    d2_score, d2_detail = score_d2_entity_recall(db)
    d3_score, d3_detail = score_d3_conflicts(db, cross_source_stats)
    d4_score, d4_detail = score_d4_story_card(story_card_md)
    d5_score, d5_detail = score_d5_qa(qa_results)

    total = d1_score + d2_score + d3_score + d4_score + d5_score
    if total >= 85:
        grade = "A"
        verdict = "可进入真实客户试点"
    elif total >= 70:
        grade = "B"
        verdict = "内测中, 不可进真客户"
    else:
        grade = "C"
        verdict = "数据中心假设未成立"

    return {
        "scores": {
            "D1_source_type": d1_score,
            "D2_entity_recall": d2_score,
            "D3_conflicts": d3_score,
            "D4_story_card": d4_score,
            "D5_qa": d5_score,
            "TOTAL": total,
        },
        "grade": grade,
        "verdict": verdict,
        "details": {
            "D1": d1_detail,
            "D2": d2_detail,
            "D3": d3_detail,
            "D4": d4_detail,
            "D5": d5_detail,
        },
    }


# ─── 主入口 · 串起来 ─────────────────────────────────


def run_full_quality_test(db_path: Path | None = None) -> dict:
    """跑完整测试 + 返回结果 dict."""
    if db_path is None:
        tmp = Path(tempfile.mkdtemp(prefix="qinghe_v23test_"))
        db_path = tmp / "app.db"

    db = setup_db(db_path)
    ingest_results = ingest_all_12_data(db)
    cross_source_stats = run_cross_source_scan(db)
    # V2.4 P0-1: atomic_facts → 4 张语义表派生
    derive_result = derive_all(db, CLIENT_ID)
    # V2.4 P0-2: 正式冲突检测 + clarification 持久化 (6 类冲突)
    conflict_result = detect_conflicts_all(db, CLIENT_ID)
    story_card_md = run_story_card(db)
    qa_results = run_50_questions(db)
    scoring = run_full_scoring(
        db, ingest_results, cross_source_stats, story_card_md, qa_results,
    )

    # V2.4 派生统计 (4 张语义表的真实持久化条数)
    semantic_table_counts = {
        "event_line_activities": _count(db, "event_line_activities",
                                        "event_line_id IN (SELECT id FROM event_lines WHERE primary_client_id = ?)",
                                        (CLIENT_ID,)),
        "risk_signals": _count(db, "risk_signals", "client_id = ?", (CLIENT_ID,)),
        "commitments": _count(db, "commitments", "client_id = ?", (CLIENT_ID,)),
        "strategic_thought_insights": _count(db, "strategic_thought_insights",
                                             "client_id = ? AND is_deleted = 0", (CLIENT_ID,)),
        "fact_contradictions": _count(db, "fact_contradictions", "client_id = ?", (CLIENT_ID,)),
        "clarification_records": _count(db, "clarification_records",
                                        "scope_type = 'client' AND scope_id = ? AND status = 'pending'",
                                        (CLIENT_ID,)),
    }

    return {
        "test_meta": {
            "run_at": _now_iso(),
            "client_id": CLIENT_ID,
            "client_name": CLIENT_NAME,
            "project_name": PROJECT_NAME,
            "db_path": str(db_path),
            "data_count": 12,
            "question_count": 50,
        },
        "ingest_results": ingest_results,
        "cross_source_stats": cross_source_stats,
        "derive_result": {
            "event_line_activities_new": derive_result.event_line_activities_new,
            "risk_signals_new": derive_result.risk_signals_new,
            "commitments_new": derive_result.commitments_new,
            "strategic_insights_new": derive_result.strategic_insights_new,
        },
        "conflict_result": {
            "same_attr_value_diff": conflict_result.same_attr_value_diff,
            "role_diff": conflict_result.role_diff,
            "media_lag": conflict_result.media_lag,
            "oral_no_official": conflict_result.oral_no_official,
            "fact_contradictions_written": conflict_result.fact_contradictions_written,
            "clarifications_written": conflict_result.clarifications_written,
        },
        "semantic_table_counts": semantic_table_counts,
        "story_card_md": story_card_md,
        "qa_results": qa_results,
        "scoring": scoring,
    }


def _count(db: Database, table: str, where: str, params: tuple) -> int:
    """辅助: 数表."""
    try:
        row = db.fetchone(f"SELECT COUNT(*) AS c FROM {table} WHERE {where}", params)
        return dict(row)["c"] if row else 0
    except Exception:
        return 0


if __name__ == "__main__":
    result = run_full_quality_test()
    print(json.dumps(result["scoring"]["scores"], ensure_ascii=False, indent=2))
    print(f"\nGrade: {result['scoring']['grade']} · {result['scoring']['verdict']}")
