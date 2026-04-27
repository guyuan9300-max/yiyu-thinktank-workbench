from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DepartmentCatalogEntry:
    id: str
    name: str
    color: str
    aliases: tuple[str, ...] = ()


DEPARTMENT_CATALOG: tuple[DepartmentCatalogEntry, ...] = (
    DepartmentCatalogEntry(
        id="dept_consult_strategy",
        name="咨询策略部",
        color="#5B7BFE",
        aliases=("咨询策略", "咨询策略部", "战略设计部", "战略设计", "战略陪伴组"),
    ),
    DepartmentCatalogEntry(
        id="dept_tech_development",
        name="科技发展部",
        color="#F59E0B",
        aliases=("科技发展部", "科技发展"),
    ),
    DepartmentCatalogEntry(
        id="dept_info_data",
        name="信息数据部",
        color="#10B981",
        aliases=("信息数据部", "信息数据", "洞察研究", "洞察研究部"),
    ),
    DepartmentCatalogEntry(
        id="dept_customer_service",
        name="客户服务部",
        color="#14B8A6",
        aliases=("客户服务部", "客户服务", "交付协同", "交付协同部"),
    ),
)

_ALIAS_LOOKUP: dict[str, DepartmentCatalogEntry] = {}
for _entry in DEPARTMENT_CATALOG:
    _ALIAS_LOOKUP[_entry.id.lower()] = _entry
    _ALIAS_LOOKUP[_entry.name.lower()] = _entry
    for _alias in _entry.aliases:
        _ALIAS_LOOKUP[_alias.lower()] = _entry


def list_department_catalog() -> list[DepartmentCatalogEntry]:
    return list(DEPARTMENT_CATALOG)


def get_department_entry(raw_id: str | None = None, raw_name: str | None = None) -> DepartmentCatalogEntry | None:
    for value in (raw_id, raw_name):
        key = (value or "").strip().lower()
        if key and key in _ALIAS_LOOKUP:
            return _ALIAS_LOOKUP[key]
    return None
