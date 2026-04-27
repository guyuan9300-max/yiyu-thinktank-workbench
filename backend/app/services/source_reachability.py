from __future__ import annotations

from typing import Any

from app.db import Database
from app.models import (
    EvidenceItem,
    QuestionFocusFrameRecord,
    SourceReachabilityRecord,
)
from app.services.question_focus import score_focus_role_match
from app.services.source_semantics import infer_semantic_source_roles_fields


def _boolish(value: object) -> bool:
    return bool(value)


def _doc_keys(items: list[EvidenceItem]) -> set[str]:
    keys: set[str] = set()
    for item in items:
        keys.add(f"{item.documentId or ''}:{item.path or ''}")
    return keys


def _row_roles(row: dict[str, Any]) -> tuple[list[str], list[str]]:
    return infer_semantic_source_roles_fields(
        title=str(row.get("title") or row.get("file_name") or ""),
        excerpt=str(row.get("preview_text") or row.get("excerpt") or ""),
        path=str(row.get("path") or row.get("original_path") or row.get("managed_path") or ""),
        visible_category=str(row.get("visible_category") or ""),
        secondary_category=str(row.get("secondary_category") or ""),
        material_layer=str(row.get("material_layer") or ""),
        source_type=str(row.get("source_type") or ""),
    )


def _to_record(
    row: dict[str, Any],
    *,
    focus_frame: QuestionFocusFrameRecord,
    source_reachability: str,
    source_selection_pool: str,
    source_final_decision: str,
) -> SourceReachabilityRecord:
    roles, role_reasons = _row_roles(row)
    match_score, focus_reasons = score_focus_role_match(focus_frame, roles)
    priority_reasons = [*role_reasons, *focus_reasons]
    if source_reachability == "reachable_support":
        priority_reasons.append("support_only_material")
    if source_reachability == "unreachable_local":
        priority_reasons.append("not_indexed_in_primary_chain")
    if source_reachability == "parse_failed":
        priority_reasons.append(f"parse_status:{row.get('parse_status') or 'failed'}")
    if source_selection_pool == "included":
        priority_reasons.append("selection_pool_hit")
    return SourceReachabilityRecord(
        title=str(row.get("title") or row.get("file_name") or "资料"),
        path=str(row.get("path") or row.get("original_path") or row.get("managed_path") or ""),
        documentId=str(row.get("document_id") or row.get("id") or "") or None,
        semanticRoles=roles,
        roleReasons=role_reasons,
        sourcePresence="present",
        sourceReachability=source_reachability,
        sourceSelectionPool=source_selection_pool,
        sourcePriorityReason=priority_reasons,
        sourceFinalDecision=source_final_decision,
        matchScore=round(match_score, 4),
    )


def build_source_reachability_audit(
    db: Database,
    *,
    client_id: str | None,
    focus_frame: QuestionFocusFrameRecord,
    evidence_items: list[EvidenceItem],
    selected_evidence: list[EvidenceItem],
) -> dict[str, object]:
    if not client_id:
        return {
            "indexedPrimarySources": [],
            "reachableSupportSources": [],
            "unreachableLocalSources": [],
            "priorityParseFailures": [],
            "supportOnlySources": [],
            "indexedPrimaryCount": 0,
            "reachableSupportCount": 0,
            "unreachableLocalCount": 0,
            "priorityParseFailureCount": 0,
        }

    pool_keys = _doc_keys(evidence_items)
    selected_keys = _doc_keys(selected_evidence)

    indexed_rows = [
        dict(row)
        for row in db.fetchall(
            """
            SELECT
                d.title AS title,
                d.path AS path,
                v.document_id,
                v.file_name,
                v.original_path,
                v.managed_path,
                v.visible_category,
                v.secondary_category,
                v.material_layer,
                v.parse_status,
                v.preview_text
            FROM v2_documents v
            LEFT JOIN documents d ON d.id = v.document_id
            WHERE v.client_id = ?
            ORDER BY v.updated_at DESC
            LIMIT 400
            """,
            (client_id,),
        )
    ]
    support_rows = [
        dict(row)
        for row in db.fetchall(
            """
            SELECT d.id AS document_id, d.title, d.path, d.excerpt
            FROM documents d
            LEFT JOIN v2_documents v ON v.document_id = d.id
            WHERE d.client_id = ?
              AND d.path LIKE '%/_imports/%'
              AND v.document_id IS NULL
            ORDER BY d.created_at DESC
            LIMIT 120
            """,
            (client_id,),
        )
    ]
    unreachable_rows = [
        dict(row)
        for row in db.fetchall(
            """
            SELECT d.id AS document_id, d.title, d.path, d.excerpt
            FROM documents d
            LEFT JOIN v2_documents v ON v.document_id = d.id
            WHERE d.client_id = ?
              AND v.document_id IS NULL
              AND d.path NOT LIKE '%/_imports/%'
            ORDER BY d.created_at DESC
            LIMIT 200
            """,
            (client_id,),
        )
    ]

    indexed_primary: list[SourceReachabilityRecord] = []
    priority_parse_failures: list[SourceReachabilityRecord] = []
    for row in indexed_rows:
        key = f"{row.get('document_id') or ''}:{row.get('path') or row.get('original_path') or ''}"
        parse_status = str(row.get("parse_status") or "")
        record = _to_record(
            row,
            focus_frame=focus_frame,
            source_reachability=("indexed_primary" if parse_status == "ready" else "parse_failed"),
            source_selection_pool=("included" if key in pool_keys else "excluded"),
            source_final_decision=(
                "selected"
                if key in selected_keys and parse_status == "ready"
                else ("parse_failed" if parse_status != "ready" else "not_selected")
            ),
        )
        if record.matchScore <= 0 and not record.semanticRoles:
            continue
        if parse_status == "ready":
            indexed_primary.append(record)
        else:
            priority_parse_failures.append(record)

    reachable_support = [
        _to_record(
            row,
            focus_frame=focus_frame,
            source_reachability="reachable_support",
            source_selection_pool="not_applicable",
            source_final_decision="support_only",
        )
        for row in support_rows
    ]
    reachable_support = [item for item in reachable_support if item.matchScore > 0 or item.semanticRoles]

    unreachable_local = [
        _to_record(
            row,
            focus_frame=focus_frame,
            source_reachability="unreachable_local",
            source_selection_pool="not_applicable",
            source_final_decision="unreachable",
        )
        for row in unreachable_rows
    ]
    unreachable_local = [item for item in unreachable_local if item.matchScore > 0 or item.semanticRoles]

    indexed_primary.sort(key=lambda item: (item.matchScore, item.sourceSelectionPool == "included", item.sourceFinalDecision == "selected"), reverse=True)
    reachable_support.sort(key=lambda item: item.matchScore, reverse=True)
    unreachable_local.sort(key=lambda item: item.matchScore, reverse=True)
    priority_parse_failures.sort(key=lambda item: item.matchScore, reverse=True)

    return {
        "indexedPrimarySources": [item.model_dump(mode="json") for item in indexed_primary[:12]],
        "reachableSupportSources": [item.model_dump(mode="json") for item in reachable_support[:8]],
        "unreachableLocalSources": [item.model_dump(mode="json") for item in unreachable_local[:8]],
        "priorityParseFailures": [item.model_dump(mode="json") for item in priority_parse_failures[:8]],
        "supportOnlySources": [item.model_dump(mode="json") for item in reachable_support[:8]],
        "indexedPrimaryCount": len(indexed_primary),
        "reachableSupportCount": len(reachable_support),
        "unreachableLocalCount": len(unreachable_local),
        "priorityParseFailureCount": len(priority_parse_failures),
    }
