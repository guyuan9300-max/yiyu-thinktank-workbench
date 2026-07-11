"""战略陪伴叙事面板 service (Phase 1.5c).

云端原生 — 同一组织有权限的账号共享同一份 6 维度故事网, 任何人澄清都让 AI
更新故事网, 所有人下次打开看到新版本 + 共同编织追溯。

数据流:
1. GET narrative → 拿最新 rev 的 6 段叙事 (cache friendly)
2. POST clarification → 追加澄清记录, status=pending
3. POST regenerate → LLM 用 (旧叙事 + pending 澄清 + 关系网 facts) 生成 rev+1
4. 落库新 version + 把 clarifications status 改 applied + 写 revisions 快照

本文件**只**负责 db 读写 + 叙事打包, LLM 调用单独抽离到 narrative_generator
(后续 Day 3 加, 当前留 stub)。
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from app.db import Database
from app.models import (
    ClientNarrativeRecord,
    NarrativeClarificationCreatePayload,
    NarrativeClarificationRecord,
    NarrativeContributor,
    NarrativeDimension,
    NarrativeDimensionRecord,
    NarrativeReference,
)

DIMENSIONS: tuple[NarrativeDimension, ...] = (
    "essence",         # Layer 1 项目本质
    "cooperation",     # Layer 2 合作关系 (新)
    "business_intro",  # Layer 3 业务介绍 (新)
    "people",          # Layer 4 关键人物 (语义升级)
    "timeline",        # Layer 5 时间线 (新)
    "next_steps",      # Layer 6 承诺与下一步 (新)
)

DIM_LABELS: dict[NarrativeDimension, str] = {
    "essence": "项目本质",
    "cooperation": "合作关系",
    "business_intro": "业务介绍",
    "people": "关键人物",
    "timeline": "时间线",
    "next_steps": "承诺与下一步",
}

DIM_COLUMN: dict[NarrativeDimension, str] = {
    "essence": "dim_essence_json",
    "cooperation": "dim_cooperation_json",
    "business_intro": "dim_business_intro_json",
    "people": "dim_people_json",
    "timeline": "dim_timeline_json",
    "next_steps": "dim_next_steps_json",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_dimension(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return {}


def _dimension_from_payload(dim: NarrativeDimension, payload: dict) -> NarrativeDimensionRecord:
    refs_raw = payload.get("references", []) or []
    refs: list[NarrativeReference] = []
    for item in refs_raw:
        if not isinstance(item, dict):
            continue
        refs.append(
            NarrativeReference(
                sourceType=str(item.get("sourceType", "")),
                sourceId=str(item.get("sourceId", "")),
                label=str(item.get("label", "")),
                confidence=str(item.get("confidence", "medium")) or "medium",  # type: ignore[arg-type]
            )
        )
    open_clar = payload.get("openClarifications", []) or []
    return NarrativeDimensionRecord(
        dimension=dim,
        narrative=str(payload.get("narrative", "")),
        confidence=str(payload.get("confidence", "low")) or "low",  # type: ignore[arg-type]
        confidenceReason=str(payload.get("confidenceReason", "")),
        references=refs,
        dataLayerGap=str(payload.get("dataLayerGap", "")),
        openClarifications=[str(x) for x in open_clar if str(x).strip()],
        # S1 取材标签透传(5/29): 从存储的原始 payload 读出本地 emit 的取材来源标记。
        # ingest 存的是原始 dim payload(已含这些字段),此前只是没在这里读出来。
        retrievalMode=(str(payload["retrievalMode"]) if payload.get("retrievalMode") else None),
        fallbackUsed=bool(payload.get("fallbackUsed", False)),
        reindexRequired=bool(payload.get("reindexRequired", False)),
    )


def _empty_dimension(dim: NarrativeDimension) -> NarrativeDimensionRecord:
    """缺数据时的占位段落 — 诚实告诉用户 'AI 暂时讲不出, 因为 ...'."""
    gaps = {
        "essence": "未生成: 等本地 backend 跑 narrative_generator 后落库",
        "cooperation": "未生成: cooperation_relationships 表为空, 需从 event_line.intent + 协议文档抽",
        "business_intro": "未生成: 等 collector 抽机构内含项目列表 (atomic_facts attribute=项目 + entities org/product)",
        "people": "未生成: 等本地 entities (person) 喂给 LLM",
        "timeline": "未生成: 等 event_line_activities + tasks/v2_documents 的 imported_at 倒推",
        "next_steps": "未生成: 等 event_line.intent + tasks(deadline) + 合同协议数据",
    }
    return NarrativeDimensionRecord(
        dimension=dim,
        narrative=f"⏳ AI 暂时讲不出{DIM_LABELS[dim]}, 因为数据中心还没建好这个加工层。",
        confidence="low",
        confidenceReason="数据中心加工层缺失",
        references=[],
        dataLayerGap=gaps.get(dim, ""),
        openClarifications=[],
    )


def get_latest_narrative(
    db: Database,
    organization_id: str,
    client_id: str,
) -> ClientNarrativeRecord | None:
    row = db.fetchone(
        """
        SELECT v.*, c.name AS client_name
        FROM client_narrative_versions v
        LEFT JOIN clients c
          ON c.id = v.client_id AND c.organization_id = v.organization_id
        WHERE v.organization_id = ? AND v.client_id = ? AND v.is_latest = 1
        ORDER BY v.rev DESC LIMIT 1
        """,
        (organization_id, client_id),
    )
    if not row:
        return None
    return _row_to_narrative(db, row)


def _row_to_narrative(db: Database, row) -> ClientNarrativeRecord:
    dims: list[NarrativeDimensionRecord] = []
    for d in DIMENSIONS:
        payload = _load_dimension(row[DIM_COLUMN[d]])
        if not payload:
            dims.append(_empty_dimension(d))
        else:
            dims.append(_dimension_from_payload(d, payload))

    gaps_raw = _load_dimension(row["data_layer_gaps_json"])
    gaps_list: list[str] = []
    if isinstance(gaps_raw, list):
        gaps_list = [str(x) for x in gaps_raw]

    contributors = _fetch_contributors(
        db,
        str(row["organization_id"]),
        str(row["client_id"]),
        int(row["rev"]),
    )

    return ClientNarrativeRecord(
        id=str(row["id"]),
        clientId=str(row["client_id"]),
        clientName=str(row["client_name"] or ""),
        rev=int(row["rev"]),
        generator=str(row["generator"] or "ai"),
        generatedAt=str(row["generated_at"]),
        modelName=str(row["model_name"] or ""),
        dimensions=dims,
        overallConfidence=float(row["overall_confidence"] or 0.0),
        openClarificationsCount=int(row["open_clarifications_count"] or 0),
        dataLayerGaps=gaps_list,
        contributors=contributors,
        updatedAt=str(row["updated_at"]),
    )


def _fetch_contributors(
    db: Database,
    organization_id: str,
    client_id: str,
    based_on_rev_max: int,
) -> list[NarrativeContributor]:
    rows = db.fetchall(
        """
        SELECT dimension, answered_by_user_id, answered_by_display_name, answered_at
        FROM client_narrative_clarifications
        WHERE organization_id = ? AND client_id = ?
          AND status = 'applied' AND answered_by_user_id IS NOT NULL
        ORDER BY answered_at DESC
        LIMIT 30
        """,
        (organization_id, client_id),
    )
    out: list[NarrativeContributor] = []
    for r in rows:
        out.append(
            NarrativeContributor(
                userId=str(r["answered_by_user_id"]) if r["answered_by_user_id"] else None,
                displayName=str(r["answered_by_display_name"] or ""),
                dimension=str(r["dimension"]),  # type: ignore[arg-type]
                answeredAt=str(r["answered_at"]),
            )
        )
    return out


def make_empty_narrative(
    db: Database,
    organization_id: str,
    client_id: str,
    client_name: str,
) -> ClientNarrativeRecord:
    """没生成过叙事时返回的"诚实空版本" — 6 段都标 ⏳ AI 还没讲."""
    return ClientNarrativeRecord(
        id="",
        clientId=client_id,
        clientName=client_name,
        rev=0,
        generator="ai",
        generatedAt=_now(),
        modelName="",
        dimensions=[_empty_dimension(d) for d in DIMENSIONS],
        overallConfidence=0.0,
        openClarificationsCount=0,
        dataLayerGaps=[
            "external_persons 花名册 (Phase 1)",
            "event_lines 9 字段升级 (Phase 1)",
            "evidence_cards 业务语义化重打标 (Phase 1)",
            "client_strategic_profile 补 4 字段 (Phase 1)",
            "risk_signals 表 (Phase 2)",
        ],
        contributors=[],
        updatedAt=_now(),
    )


def list_clarifications(
    db: Database,
    organization_id: str,
    client_id: str,
    limit: int = 50,
) -> list[NarrativeClarificationRecord]:
    rows = db.fetchall(
        """
        SELECT * FROM client_narrative_clarifications
        WHERE organization_id = ? AND client_id = ?
        ORDER BY created_at DESC LIMIT ?
        """,
        (organization_id, client_id, limit),
    )
    return [
        NarrativeClarificationRecord(
            id=str(r["id"]),
            clientId=str(r["client_id"]),
            basedOnRev=int(r["based_on_rev"] or 0),
            dimension=str(r["dimension"]),  # type: ignore[arg-type]
            question=str(r["question"] or ""),
            askedBy=str(r["asked_by"] or "ai"),
            answer=str(r["answer"] or ""),
            answeredByUserId=str(r["answered_by_user_id"]) if r["answered_by_user_id"] else None,
            answeredByDisplayName=str(r["answered_by_display_name"] or ""),
            answeredAt=str(r["answered_at"]),
            resultedInRev=(int(r["resulted_in_rev"]) if r["resulted_in_rev"] is not None else None),
            status=str(r["status"] or "pending"),  # type: ignore[arg-type]
        )
        for r in rows
    ]


def add_clarification(
    db: Database,
    organization_id: str,
    client_id: str,
    payload: NarrativeClarificationCreatePayload,
    answered_by_user_id: str,
    answered_by_display_name: str,
) -> NarrativeClarificationRecord:
    """追加一条澄清记录, status=pending 等下次 regenerate 应用."""
    if payload.dimension not in DIMENSIONS:
        raise ValueError(f"unknown dimension: {payload.dimension}")
    based_on_rev = payload.basedOnRev
    if based_on_rev is None:
        latest = db.fetchone(
            """
            SELECT rev FROM client_narrative_versions
            WHERE organization_id = ? AND client_id = ?
            ORDER BY rev DESC LIMIT 1
            """,
            (organization_id, client_id),
        )
        based_on_rev = int(latest["rev"]) if latest else 0
    clar_id = str(uuid.uuid4())
    now = _now()
    db.execute(
        """
        INSERT INTO client_narrative_clarifications
            (id, organization_id, client_id, based_on_rev, dimension, question,
             asked_by, answer, answered_by_user_id, answered_by_display_name,
             answered_at, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 'user', ?, ?, ?, ?, 'pending', ?, ?)
        """,
        (
            clar_id,
            organization_id,
            client_id,
            based_on_rev,
            payload.dimension,
            payload.question or "",
            payload.answer,
            answered_by_user_id,
            answered_by_display_name,
            now,
            now,
            now,
        ),
    )
    return NarrativeClarificationRecord(
        id=clar_id,
        clientId=client_id,
        basedOnRev=based_on_rev,
        dimension=payload.dimension,
        question=payload.question or "",
        askedBy="user",
        answer=payload.answer,
        answeredByUserId=answered_by_user_id,
        answeredByDisplayName=answered_by_display_name,
        answeredAt=now,
        resultedInRev=None,
        status="pending",
    )


def count_pending_clarifications(db: Database, organization_id: str, client_id: str) -> int:
    row = db.fetchone(
        """
        SELECT COUNT(*) AS c FROM client_narrative_clarifications
        WHERE organization_id = ? AND client_id = ? AND status = 'pending'
        """,
        (organization_id, client_id),
    )
    return int(row["c"]) if row else 0


def write_new_version(
    db: Database,
    organization_id: str,
    client_id: str,
    dimensions: dict[NarrativeDimension, dict],
    *,
    overall_confidence: float,
    data_layer_gaps: list[str],
    generator: str = "ai",
    model_name: str = "",
    triggered_by_user_id: str | None = None,
    triggered_by_display_name: str = "",
    trigger: str = "manual",
) -> int:
    """落库一个新的 rev — 把旧版的 is_latest 翻到 0, 写新版 + 历史快照,
    把基于 (新版 rev - 1) 的 pending 澄清状态改成 applied (resulted_in_rev=新版).
    返回新 rev 号."""
    now = _now()
    last = db.fetchone(
        """
        SELECT rev FROM client_narrative_versions
        WHERE organization_id = ? AND client_id = ?
        ORDER BY rev DESC LIMIT 1
        """,
        (organization_id, client_id),
    )
    new_rev = (int(last["rev"]) + 1) if last else 1
    new_id = str(uuid.uuid4())

    # 1. 翻旧版 is_latest=0
    db.execute(
        """
        UPDATE client_narrative_versions
        SET is_latest = 0, updated_at = ?
        WHERE organization_id = ? AND client_id = ? AND is_latest = 1
        """,
        (now, organization_id, client_id),
    )

    # 2. 落新版 — DIMENSIONS 顺序: essence/cooperation/business_intro/people/timeline/next_steps
    dim_payloads_ordered = [
        json.dumps(dimensions.get(d, {}), ensure_ascii=False)
        for d in DIMENSIONS
    ]
    dim_columns = ", ".join(DIM_COLUMN[d] for d in DIMENSIONS)
    dim_placeholders = ", ".join("?" * len(DIMENSIONS))
    open_count = count_pending_clarifications(db, organization_id, client_id)
    db.execute(
        f"""
        INSERT INTO client_narrative_versions
            (id, organization_id, client_id, rev, generator, generated_at, model_name,
             {dim_columns},
             overall_confidence, open_clarifications_count, data_layer_gaps_json,
             is_latest, schema_version, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, {dim_placeholders}, ?, ?, ?, 1, 'v1', ?, ?)
        """,
        (
            new_id, organization_id, client_id, new_rev, generator, now, model_name,
            *dim_payloads_ordered,
            float(overall_confidence),
            open_count,
            json.dumps(data_layer_gaps, ensure_ascii=False),
            now, now,
        ),
    )

    # 3. 写历史快照
    snapshot = {
        "id": new_id,
        "rev": new_rev,
        "dimensions": {d: dimensions.get(d, {}) for d in DIMENSIONS},
        "overallConfidence": overall_confidence,
        "dataLayerGaps": data_layer_gaps,
    }
    db.execute(
        """
        INSERT INTO client_narrative_revisions
            (client_id, rev, organization_id, snapshot_json, trigger,
             triggered_by_user_id, triggered_by_display_name, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            client_id, new_rev, organization_id,
            json.dumps(snapshot, ensure_ascii=False),
            trigger,
            triggered_by_user_id,
            triggered_by_display_name,
            now,
        ),
    )

    # 4. 把 based_on_rev < new_rev 的 pending 澄清标 applied
    db.execute(
        """
        UPDATE client_narrative_clarifications
        SET status = 'applied', resulted_in_rev = ?, updated_at = ?
        WHERE organization_id = ? AND client_id = ?
          AND status = 'pending' AND based_on_rev < ?
        """,
        (new_rev, now, organization_id, client_id, new_rev),
    )

    return new_rev
