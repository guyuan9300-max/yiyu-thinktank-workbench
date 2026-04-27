from __future__ import annotations

from dataclasses import dataclass
from typing import Any


PRIVATE_VISIBILITY_SCOPES = {"self", "private", "personal"}
PRIVATE_CONTENT_DOMAINS = {"personal", "private"}
CEO_ROLES = {"ceo", "admin", "organization_admin", "org_admin"}


@dataclass(frozen=True)
class DataCenterAccessContext:
    organization_id: str = ""
    viewer_user_id: str = ""
    role: str = "ceo"
    department_ids: tuple[str, ...] = ()
    include_personal: bool = False
    include_inactive: bool = False

    @property
    def is_ceo(self) -> bool:
        return self.role.strip().lower() in CEO_ROLES


@dataclass(frozen=True)
class AccessWhereClause:
    sql: str
    params: tuple[Any, ...] = ()


def normalize_department_ids(values: object | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        stripped = values.strip()
        if not stripped:
            return ()
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                import json

                parsed = json.loads(stripped)
                return normalize_department_ids(parsed)
            except Exception:
                return ()
        return tuple(dict.fromkeys(part.strip() for part in stripped.split(",") if part.strip()))
    if isinstance(values, (list, tuple, set)):
        return tuple(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))
    return ()


def normalize_access_context(context: DataCenterAccessContext | dict[str, Any] | None = None) -> DataCenterAccessContext:
    if isinstance(context, DataCenterAccessContext):
        return context
    if isinstance(context, dict):
        return DataCenterAccessContext(
            organization_id=str(context.get("organization_id") or context.get("organizationId") or "").strip(),
            viewer_user_id=str(context.get("viewer_user_id") or context.get("viewerUserId") or "").strip(),
            role=str(context.get("role") or "ceo").strip() or "ceo",
            department_ids=normalize_department_ids(context.get("department_ids") or context.get("departmentIds")),
            include_personal=bool(context.get("include_personal") or context.get("includePersonal")),
            include_inactive=bool(context.get("include_inactive") or context.get("includeInactive")),
        )
    return DataCenterAccessContext()


def _col(alias: str, name: str) -> str:
    return f"{alias}.{name}"


def _coalesced(v2_alias: str, doc_alias: str, name: str, default: str = "") -> str:
    return f"COALESCE(NULLIF({_col(v2_alias, name)}, ''), NULLIF({_col(doc_alias, name)}, ''), '{default}')"


def _json_department_match(json_expr: str, department_ids: tuple[str, ...]) -> tuple[str, list[Any]]:
    if not department_ids:
        return "0 = 1", []
    placeholders = ", ".join("?" for _ in department_ids)
    return (
        "EXISTS ("
        "SELECT 1 FROM json_each(CASE WHEN json_valid("
        f"{json_expr}"
        f") THEN {json_expr} ELSE '[]' END) dc_dept WHERE CAST(dc_dept.value AS TEXT) IN ({placeholders})"
        ")",
        list(department_ids),
    )


def _scope_clause(
    *,
    context: DataCenterAccessContext,
    organization_expr: str,
    owner_expr: str,
    department_expr: str,
    department_ids_json_expr: str,
    visibility_expr: str,
    content_domain_expr: str,
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []

    if context.organization_id:
        clauses.append(f"{organization_expr} = ?")
        params.append(context.organization_id)

    private_visibility = ", ".join("?" for _ in PRIVATE_VISIBILITY_SCOPES)
    private_domains = ", ".join("?" for _ in PRIVATE_CONTENT_DOMAINS)
    private_params = [*sorted(PRIVATE_VISIBILITY_SCOPES), *sorted(PRIVATE_CONTENT_DOMAINS)]
    non_private_clause = (
        f"LOWER({visibility_expr}) NOT IN ({private_visibility}) "
        f"AND LOWER({content_domain_expr}) NOT IN ({private_domains})"
    )
    if context.include_personal and context.viewer_user_id:
        clauses.append(
            "("
            f"({non_private_clause}) OR "
            f"((LOWER({visibility_expr}) IN ({private_visibility}) OR LOWER({content_domain_expr}) IN ({private_domains})) "
            f"AND {owner_expr} = ?)"
            ")"
        )
        params.extend(private_params)
        params.extend(sorted(PRIVATE_VISIBILITY_SCOPES))
        params.extend(sorted(PRIVATE_CONTENT_DOMAINS))
        params.append(context.viewer_user_id)
    else:
        clauses.append(non_private_clause)
        params.extend(private_params)

    if not context.is_ceo:
        ownership_parts: list[str] = []
        ownership_params: list[Any] = []
        if context.viewer_user_id:
            ownership_parts.append(f"{owner_expr} = ?")
            ownership_params.append(context.viewer_user_id)
        department_match_sql, department_match_params = _json_department_match(department_ids_json_expr, context.department_ids)
        if context.department_ids:
            placeholders = ", ".join("?" for _ in context.department_ids)
            ownership_parts.append(f"({department_expr} IN ({placeholders}) OR {department_match_sql})")
            ownership_params.extend(context.department_ids)
            ownership_params.extend(department_match_params)
        clauses.append(f"({' OR '.join(ownership_parts)})" if ownership_parts else "0 = 1")
        params.extend(ownership_params)

    return " AND ".join(f"({clause})" for clause in clauses), params


def build_document_access_where(
    v2_alias: str,
    doc_alias: str,
    context: DataCenterAccessContext | dict[str, Any] | None = None,
) -> AccessWhereClause:
    normalized = normalize_access_context(context)
    clauses: list[str] = []
    params: list[Any] = []
    visibility_expr = _coalesced(v2_alias, doc_alias, "visibility_scope", "project_public")
    content_domain_expr = _coalesced(v2_alias, doc_alias, "content_domain", "work")
    owner_expr = _coalesced(v2_alias, doc_alias, "owner_user_id")
    if not normalized.include_inactive:
        searchable_expr = f"COALESCE({_col(v2_alias, 'is_searchable')}, {_col(doc_alias, 'is_searchable')}, 1)"
        if normalized.include_personal and normalized.viewer_user_id:
            private_visibility = ", ".join("?" for _ in PRIVATE_VISIBILITY_SCOPES)
            private_domains = ", ".join("?" for _ in PRIVATE_CONTENT_DOMAINS)
            clauses.append(
                "("
                f"{searchable_expr} = 1 OR "
                f"((LOWER({visibility_expr}) IN ({private_visibility}) OR LOWER({content_domain_expr}) IN ({private_domains})) "
                f"AND {owner_expr} = ?)"
                ")"
            )
            params.extend(sorted(PRIVATE_VISIBILITY_SCOPES))
            params.extend(sorted(PRIVATE_CONTENT_DOMAINS))
            params.append(normalized.viewer_user_id)
        else:
            clauses.append(f"{searchable_expr} = 1")
        clauses.append(
            f"COALESCE(NULLIF({_col(v2_alias, 'lifecycle_status')}, ''), NULLIF({_col(doc_alias, 'lifecycle_status')}, ''), 'active') = 'active'"
        )
    scope_sql, scope_params = _scope_clause(
        context=normalized,
        organization_expr=_coalesced(v2_alias, doc_alias, "organization_id"),
        owner_expr=owner_expr,
        department_expr=_coalesced(v2_alias, doc_alias, "department_id"),
        department_ids_json_expr=_coalesced(v2_alias, doc_alias, "department_ids_json", "[]"),
        visibility_expr=visibility_expr,
        content_domain_expr=content_domain_expr,
    )
    clauses.append(scope_sql)
    params.extend(scope_params)
    return AccessWhereClause(" AND ".join(f"({clause})" for clause in clauses), tuple(params))


def build_memory_fact_access_where(
    alias: str,
    context: DataCenterAccessContext | dict[str, Any] | None = None,
) -> AccessWhereClause:
    normalized = normalize_access_context(context)
    clauses: list[str] = []
    params: list[Any] = []
    if not normalized.include_inactive:
        clauses.append(f"COALESCE(NULLIF({_col(alias, 'lifecycle_status')}, ''), 'active') = 'active'")
    scope_sql, scope_params = _scope_clause(
        context=normalized,
        organization_expr=f"COALESCE(NULLIF({_col(alias, 'organization_id')}, ''), '')",
        owner_expr=f"COALESCE(NULLIF({_col(alias, 'owner_user_id')}, ''), '')",
        department_expr=f"COALESCE(NULLIF({_col(alias, 'department_id')}, ''), '')",
        department_ids_json_expr=f"COALESCE(NULLIF({_col(alias, 'department_ids_json')}, ''), '[]')",
        visibility_expr=f"COALESCE(NULLIF({_col(alias, 'visibility_scope')}, ''), 'project_public')",
        content_domain_expr=f"COALESCE(NULLIF({_col(alias, 'content_domain')}, ''), 'work')",
    )
    clauses.append(scope_sql)
    params.extend(scope_params)
    return AccessWhereClause(" AND ".join(f"({clause})" for clause in clauses), tuple(params))


def build_ingest_event_access_where(
    alias: str,
    context: DataCenterAccessContext | dict[str, Any] | None = None,
) -> AccessWhereClause:
    normalized = normalize_access_context(context)
    clauses: list[str] = []
    params: list[Any] = []
    if not normalized.include_inactive:
        clauses.append(f"COALESCE(NULLIF({_col(alias, 'lifecycle_status')}, ''), 'active') = 'active'")
    scope_sql, scope_params = _scope_clause(
        context=normalized,
        organization_expr=f"COALESCE(NULLIF({_col(alias, 'organization_id')}, ''), '')",
        owner_expr=f"COALESCE(NULLIF({_col(alias, 'owner_user_id')}, ''), '')",
        department_expr=f"COALESCE(NULLIF({_col(alias, 'department_id')}, ''), '')",
        department_ids_json_expr=f"COALESCE(NULLIF({_col(alias, 'department_ids_json')}, ''), '[]')",
        visibility_expr=f"COALESCE(NULLIF({_col(alias, 'visibility_scope')}, ''), 'project_public')",
        content_domain_expr=f"COALESCE(NULLIF({_col(alias, 'content_domain')}, ''), 'work')",
    )
    clauses.append(scope_sql)
    params.extend(scope_params)
    return AccessWhereClause(" AND ".join(f"({clause})" for clause in clauses), tuple(params))
