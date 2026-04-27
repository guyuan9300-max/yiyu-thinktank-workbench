from __future__ import annotations

from datetime import datetime
from typing import Callable

from app.db import Database
from app.models import DataCenterSchemaStatusRecord


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _table_exists(db: Database, table_name: str) -> bool:
    row = db.fetchone(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
        (table_name,),
    )
    return bool(row and row["name"])


def _count(db: Database, query: str) -> int:
    try:
        row = db.fetchone(query)
    except Exception:
        return 0
    if not row:
        return 0
    try:
        return int(row["count"] or 0)
    except Exception:
        return 0


def _permission_diagnostics(db: Database) -> dict[str, int]:
    return {
        "documentsMissingOrganization": _count(db, "SELECT COUNT(1) AS count FROM documents WHERE COALESCE(organization_id, '') = ''"),
        "v2DocumentsMissingOrganization": _count(db, "SELECT COUNT(1) AS count FROM v2_documents WHERE COALESCE(organization_id, '') = ''"),
        "memoryFactsMissingOrganization": _count(db, "SELECT COUNT(1) AS count FROM memory_facts WHERE COALESCE(organization_id, '') = ''"),
        "documentsMissingDepartmentIds": _count(db, "SELECT COUNT(1) AS count FROM documents WHERE COALESCE(department_ids_json, '[]') IN ('', '[]')"),
        "v2DocumentsMissingDepartmentIds": _count(db, "SELECT COUNT(1) AS count FROM v2_documents WHERE COALESCE(department_ids_json, '[]') IN ('', '[]')"),
        "memoryFactsMissingDepartmentIds": _count(db, "SELECT COUNT(1) AS count FROM memory_facts WHERE COALESCE(department_ids_json, '[]') IN ('', '[]')"),
        "documentsMissingOwner": _count(db, "SELECT COUNT(1) AS count FROM documents WHERE COALESCE(owner_user_id, '') = ''"),
        "v2DocumentsMissingOwner": _count(db, "SELECT COUNT(1) AS count FROM v2_documents WHERE COALESCE(owner_user_id, '') = ''"),
        "memoryFactsMissingOwner": _count(db, "SELECT COUNT(1) AS count FROM memory_facts WHERE COALESCE(owner_user_id, '') = ''"),
        "privateSearchableDocuments": _count(
            db,
            """
            SELECT COUNT(1) AS count
            FROM documents
            WHERE COALESCE(is_searchable, 1) = 1
              AND (
                LOWER(COALESCE(visibility_scope, 'project_public')) IN ('self', 'private', 'personal')
                OR LOWER(COALESCE(content_domain, 'work')) IN ('personal', 'private')
              )
            """,
        ),
        "inactiveSearchableDocuments": _count(
            db,
            """
            SELECT COUNT(1) AS count
            FROM documents
            WHERE COALESCE(is_searchable, 1) = 1
              AND COALESCE(lifecycle_status, 'active') != 'active'
            """,
        ),
        "inactiveSearchableV2Documents": _count(
            db,
            """
            SELECT COUNT(1) AS count
            FROM v2_documents
            WHERE COALESCE(is_searchable, 1) = 1
              AND COALESCE(lifecycle_status, 'active') != 'active'
            """,
        ),
    }


def ensure_data_center_schema(db: Database) -> dict[str, object]:
    from app.services.data_center_ingest import ensure_data_center_ingest_schema
    from app.services.data_center_proposal import ensure_data_center_proposal_draft_schema
    from app.services.data_center_shadow import ensure_data_center_shadow_schema
    from app.services.data_center_sync import ensure_data_center_sync_schema
    from app.services.evidence_quality_feedback_snapshot import ensure_evidence_quality_feedback_snapshot_schema
    from app.services.evidence_quality_store import ensure_evidence_quality_annotation_schema
    from app.services.external_evidence import ensure_external_evidence_schema
    from app.services.generation_runtime_policy import ensure_generation_runtime_schema
    from app.services.kernel_primary_rollout import ensure_kernel_primary_rollout_schema
    from app.services.retrieval_shadow import ensure_retrieval_shadow_schema
    from app.services.workspace_answer_value_diagnostics import (
        ensure_workspace_answer_quality_failure_schema,
        ensure_workspace_answer_value_review_schema,
        ensure_workspace_value_validation_session_schema,
    )
    from app.services.workspace_context_refresh import ensure_workspace_context_refresh_schema

    registry: list[tuple[str, Callable[[Database], None], list[str]]] = [
        ("data_center_ingest_events", ensure_data_center_ingest_schema, ["data_center_ingest_events"]),
        ("data_center_sync_outbox", ensure_data_center_sync_schema, ["data_center_sync_outbox"]),
        ("proposal_drafts", ensure_data_center_proposal_draft_schema, ["data_center_proposal_drafts"]),
        ("kernel_primary_rollout", ensure_kernel_primary_rollout_schema, ["kernel_primary_rollout_runs"]),
        ("external_evidence", ensure_external_evidence_schema, ["external_evidence_cards"]),
        ("evidence_quality_annotations", ensure_evidence_quality_annotation_schema, ["evidence_quality_annotations"]),
        (
            "evidence_quality_feedback_snapshots",
            ensure_evidence_quality_feedback_snapshot_schema,
            ["evidence_quality_feedback_snapshots"],
        ),
        (
            "workspace_answer_value_reviews",
            ensure_workspace_answer_value_review_schema,
            ["workspace_answer_value_reviews"],
        ),
        (
            "workspace_value_validation_sessions",
            ensure_workspace_value_validation_session_schema,
            ["workspace_value_validation_sessions"],
        ),
        (
            "workspace_answer_quality_failures",
            ensure_workspace_answer_quality_failure_schema,
            ["workspace_answer_quality_failures"],
        ),
        (
            "workspace_context_refresh_events",
            ensure_workspace_context_refresh_schema,
            ["workspace_context_refresh_events"],
        ),
        ("generation_runtime_state", ensure_generation_runtime_schema, ["generation_runtime_state"]),
        ("data_center_shadow_runs", ensure_data_center_shadow_schema, ["data_center_shadow_runs"]),
        ("retrieval_shadow_runs", ensure_retrieval_shadow_schema, ["retrieval_shadow_runs"]),
    ]

    ensured_tables: list[str] = []
    missing_tables: list[str] = []
    errors: list[str] = []

    for label, ensure_fn, tables in registry:
        try:
            ensure_fn(db)
        except Exception as exc:  # pragma: no cover - defensive path
            errors.append(f"{label}: {exc}")
        for table_name in tables:
            if _table_exists(db, table_name):
                if table_name not in ensured_tables:
                    ensured_tables.append(table_name)
            elif table_name not in missing_tables:
                missing_tables.append(table_name)

    return DataCenterSchemaStatusRecord(
        generatedAt=_now_iso(),
        ensuredTables=sorted(ensured_tables),
        missingTables=sorted(missing_tables),
        errors=errors,
        permissionDiagnostics=_permission_diagnostics(db),
    ).model_dump(mode="json")
