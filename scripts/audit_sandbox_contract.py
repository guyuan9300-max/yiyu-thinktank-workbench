#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_SCHEMA = ROOT / "backend" / "app" / "db.py"

# Tables that are directly visible as business roots or workspace-level state.
# They must carry sandbox_id themselves.
DIRECT_SANDBOX_TABLES = {
    "analysis_jobs",
    "clients",
    "task_lists",
    "task_tags",
    "task_settings",
    "tasks",
    "event_lines",
    "memory_facts",
    "weekly_reviews",
    "topic_radars",
    "data_center_ingest_events",
    "exp_wall_quotes",
    "exp_wall_reactions",
    "handbook_entries",
    "knowledge_jobs",
    "growth_signal_events",
    "growth_evidence_records",
    "growth_validation_events",
    "xp_ledger",
    "badge_unlock_records",
    "learning_recommendations",
    "workspace_context_refresh_events",
}

# Tables that intentionally inherit scope from a parent object. Adding a new
# business table without sandbox_id should extend this map with an explicit
# parent relation, otherwise the audit fails.
INHERITED_SCOPE_TABLES = {
    "documents": "client_id -> clients.sandbox_id",
    "task_notes": "task_id -> tasks.sandbox_id",
    "task_attachments": "task_id -> tasks.sandbox_id",
    "task_attachments_cloud": "task_id/event_line_id -> tasks/event_lines.sandbox_id",
    "task_collaborators": "task_id -> tasks.sandbox_id",
    "event_line_activities": "event_line_id -> event_lines.sandbox_id",
    "event_line_memory_snapshots": "event_line_id -> event_lines.sandbox_id",
    "intelligence_items": "client_id/project_module_id -> clients.sandbox_id",
    "intelligence_profiles": "client_id/project_module_id/scope_id -> clients.sandbox_id",
    "intelligence_refresh_runs": "client_id/project_module_id/scope_id -> clients.sandbox_id",
    "intelligence_candidate_items": "radar_id/client_id/project_module_id -> topic_radars/clients.sandbox_id",
    "intelligence_focus_directives": "global scope_id stores sandbox_id; client/project scopes inherit",
    "intelligence_verification_rules": "owned by intelligence profile/radar context",
    "intelligence_feedback_events": "item_id -> intelligence_items current sandbox view",
    "intelligence_feedback_summaries": "item_id -> intelligence_items current sandbox view",
    "intelligence_search_intents": "current sandbox search session only",
    "intelligence_search_diagnostics": "current sandbox search session only",
    "intelligence_source_configs": "current sandbox settings view",
    "intelligence_fetch_jobs": "source/radar context inherits current sandbox",
    "growth_capture_states": "user_id + current sandbox service layer; legacy table backfilled separately",
    "growth_ability_profiles": "user profile baseline; evidence records are sandbox-scoped",
    "growth_ability_weekly_snapshot": "derived from growth ledger/evidence sandbox view",
    "growth_recommendation_feedback": "recommendation_id -> learning_recommendations.sandbox_id",
    "agent_weekly_plan_overrides": "operator/plan data scoped through current sandbox service layer",
    "card_review_queue": "source task/document/client context inherits current sandbox",
    "chat_thread_memory_packs": "chat thread context inherits current sandbox",
    "client_analysis_runs": "client_id -> clients.sandbox_id",
    "client_dna_documents": "client_id -> clients.sandbox_id",
    "client_folders": "client_id -> clients.sandbox_id",
    "client_glossary": "client_id -> clients.sandbox_id",
    "client_narrative_local_mirror": "client_id -> clients.sandbox_id",
    "client_stage_audit": "client_id -> clients.sandbox_id",
    "client_strategic_profiles": "client_id -> clients.sandbox_id",
    "client_template_fill_runs": "client_id -> clients.sandbox_id",
    "client_units": "client_id -> clients.sandbox_id",
    "digital_asset_narrative_snapshots": "client_id/source context -> clients.sandbox_id",
    "document_cards": "document_id -> documents -> clients.sandbox_id",
    "document_catalog_index": "document_id -> documents -> clients.sandbox_id",
    "document_chunks": "document_id -> documents -> clients.sandbox_id",
    "document_deep_read_states": "document_id -> documents -> clients.sandbox_id",
    "document_fields": "document_id -> documents -> clients.sandbox_id",
    "document_kinds": "configuration scoped by document/client service layer",
    "document_path_optimizations": "document_id -> documents -> clients.sandbox_id",
    "document_recycle_bin": "document/client context inherits sandbox",
    "duplicate_group_reviews": "source document/client context inherits sandbox",
    "event_line_approval_nodes": "event_line_id -> event_lines.sandbox_id",
    "event_line_attachments": "event_line_id -> event_lines.sandbox_id",
    "event_line_state_changes": "event_line_id -> event_lines.sandbox_id",
    "event_line_weekly_snapshots": "event_line_id -> event_lines.sandbox_id",
    "knowledge_document_versions": "knowledge_document_id -> knowledge_documents -> client/document sandbox",
    "knowledge_documents": "client/document context inherits sandbox",
    "local_model_tasks": "device-level local model queue, not organization business data",
    "organization_dna_documents": "organization workspace context service-scoped",
    "strategic_thought_reviews": "client/task/event context inherits sandbox",
    "sync_memory_records": "source object context inherits sandbox",
    "task_context_brief_snapshots": "task_id -> tasks.sandbox_id",
    "task_notes_cloud": "task_id -> tasks.sandbox_id",
    "task_smart_brief_action_adoptions": "task_id -> tasks.sandbox_id",
    "task_understanding_cache": "task_id -> tasks.sandbox_id",
    "task_views": "view settings scoped by sandbox in task settings service",
    "v2_documents": "client/document context inherits sandbox",
    "weekly_review_task_entries": "weekly_review_id -> weekly_reviews.sandbox_id",
}

GLOBAL_TABLE_ALLOWLIST = {
    "settings",
    "sandboxes",
    "sandbox_settings",
    "local_identities",
}


def _extract_create_table_blocks(schema_text: str) -> dict[str, str]:
    pattern = re.compile(
        r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([A-Za-z_][A-Za-z0-9_]*)\s*\((.*?)\);",
        re.IGNORECASE | re.DOTALL,
    )
    return {match.group(1): match.group(2) for match in pattern.finditer(schema_text)}


def audit_schema() -> list[str]:
    schema_text = DB_SCHEMA.read_text(encoding="utf-8")
    tables = _extract_create_table_blocks(schema_text)
    failures: list[str] = []

    def has_sandbox_id_contract(table: str, block: str) -> bool:
        if re.search(r"\bsandbox_id\b", block):
            return True
        ensure_pattern = rf"_ensure_column\(\s*[\"']{re.escape(table)}[\"']\s*,\s*[\"']sandbox_id[\"']"
        return bool(re.search(ensure_pattern, schema_text))

    for table in sorted(DIRECT_SANDBOX_TABLES):
        block = tables.get(table, "")
        if not block and not has_sandbox_id_contract(table, ""):
            failures.append(f"direct table `{table}` is not declared in backend/app/db.py")
            continue
        if not has_sandbox_id_contract(table, block):
            failures.append(f"direct table `{table}` must declare sandbox_id")
    for table, block in sorted(tables.items()):
        if table in DIRECT_SANDBOX_TABLES or table in INHERITED_SCOPE_TABLES or table in GLOBAL_TABLE_ALLOWLIST:
            continue
        is_business_like = any(
            key in table
            for key in (
                "task",
                "client",
                "document",
                "event_line",
                "intelligence",
                "growth",
                "weekly",
                "memory",
                "handbook",
                "asset",
                "review",
            )
        )
        if is_business_like and not has_sandbox_id_contract(table, block):
            failures.append(
                f"business-like table `{table}` lacks sandbox_id and has no inherited-scope declaration"
            )
    return failures


def main() -> int:
    failures = audit_schema()
    if failures:
        print("Sandbox contract audit failed:")
        for item in failures:
            print(f"- {item}")
        return 1
    print("Sandbox contract audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
