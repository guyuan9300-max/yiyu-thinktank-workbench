"""Week 3 验收 runner · 6 维度 + 复用 W2 7 维度

跑法:
    backend/.venv/bin/python3 scripts/run_w3_acceptance.py
    # exit 0 = W3 + W2 + W1 全 PASS
    # exit 1 = 有 FAIL

输出:
    tests/reports/w3_acceptance.json
    stdout — 人读摘要
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "tests" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

VENV_PY = ROOT / "backend" / ".venv" / "bin" / "python3"
PY = str(VENV_PY) if VENV_PY.exists() else sys.executable


@dataclass
class DimensionReport:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0


def _run_pytest(test_path: str, expected_count: int | None = None) -> DimensionReport:
    started = time.perf_counter()
    result = subprocess.run(
        [PY, "-m", "pytest", test_path, "-v", "--tb=short", "-q", "--no-header"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    duration_ms = (time.perf_counter() - started) * 1000
    out = result.stdout + result.stderr

    passed = int(m.group(1)) if (m := re.search(r"(\d+) passed", out)) else 0
    failed = int(m.group(1)) if (m := re.search(r"(\d+) failed", out)) else 0
    skipped = int(m.group(1)) if (m := re.search(r"(\d+) skipped", out)) else 0
    errors = int(m.group(1)) if (m := re.search(r"(\d+) error", out)) else 0

    status = "PASS"
    error = None
    if failed > 0 or errors > 0:
        status = "FAIL"
        error = f"{failed} failed + {errors} errors"
    elif expected_count is not None and passed + skipped != expected_count:
        status = "FAIL"
        error = f"expected {expected_count}, got {passed} passed + {skipped} skipped"

    return DimensionReport(
        name=test_path, status=status,
        details={"passed": passed, "failed": failed, "skipped": skipped,
                 "errors": errors, "expected": expected_count, "exit_code": result.returncode},
        error=error, duration_ms=duration_ms,
    )


# ─── W3 维度 ────────────────────────────────────────────────


def dim_w3_migration_tests() -> DimensionReport:
    """26 个测试覆盖:repo 新方法 + ConnAdapter + legacy services 等价 + 无裸 SQL"""
    return _run_pytest("tests/test_w3_services_migration.py", expected_count=26)


def dim_w3_glossary_store_no_raw_sql() -> DimensionReport:
    """glossary_store.py 切线后 0 处裸 SQL on client_glossary 表"""
    started = time.perf_counter()
    f = ROOT / "backend" / "app" / "services" / "glossary_store.py"
    src = f.read_text(encoding="utf-8")
    forbidden = re.compile(
        r"\b(SELECT|INSERT INTO|UPDATE|DELETE FROM)\b[^\n]*\bclient_glossary\b",
        re.IGNORECASE,
    )
    matches = forbidden.findall(src)
    return DimensionReport(
        name="glossary_store.py 无裸 SQL",
        status="PASS" if not matches else "FAIL",
        details={"matches": matches[:3], "match_count": len(matches),
                 "file": str(f.relative_to(ROOT))},
        error=None if not matches else f"{len(matches)} 处仍裸 SQL",
        duration_ms=(time.perf_counter() - started) * 1000,
    )


def dim_w3_commitment_services_no_raw_sql() -> DimensionReport:
    """3 个 commitment 切线服务文件 0 处裸 SQL on commitments 表"""
    started = time.perf_counter()
    files = [
        ROOT / "backend" / "app" / "services" / "todo_aggregator.py",
        ROOT / "backend" / "app" / "services" / "clarification_context.py",
        ROOT / "backend" / "app" / "services" / "narrative_collector.py",
    ]
    forbidden = re.compile(
        r"\b(FROM|INTO|UPDATE|DELETE\s+FROM)\s+commitments\b",
        re.IGNORECASE,
    )
    per_file: dict[str, int] = {}
    total = 0
    for f in files:
        src = f.read_text(encoding="utf-8")
        matches = forbidden.findall(src)
        per_file[f.name] = len(matches)
        total += len(matches)
    return DimensionReport(
        name="3 commit services 无裸 SQL",
        status="PASS" if total == 0 else "FAIL",
        details={"per_file": per_file, "total_violations": total},
        error=None if total == 0 else f"{total} 处仍裸 SQL",
        duration_ms=(time.perf_counter() - started) * 1000,
    )


def dim_w3_repository_method_coverage() -> DimensionReport:
    """新增 Repository 方法都可调用,返回正确类型"""
    started = time.perf_counter()
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "backend"))
    try:
        from app.modules.commitment import CommitmentRepository
        from app.modules.glossary import GlossaryRepository

        expected_glossary = {
            "list_terms_paginated", "create_term", "update_term", "delete_term",
        }
        expected_commitment = {
            "list_pending_for_client", "list_for_client_status_grouped",
            "list_active_for_client",
        }
        glossary_methods = {m for m in dir(GlossaryRepository) if not m.startswith("_")}
        commitment_methods = {m for m in dir(CommitmentRepository) if not m.startswith("_")}

        missing_g = expected_glossary - glossary_methods
        missing_c = expected_commitment - commitment_methods
        ok = not missing_g and not missing_c
        return DimensionReport(
            name="Repository 新方法覆盖",
            status="PASS" if ok else "FAIL",
            details={
                "glossary_new_methods": sorted(expected_glossary & glossary_methods),
                "commitment_new_methods": sorted(expected_commitment & commitment_methods),
                "missing_glossary": sorted(missing_g),
                "missing_commitment": sorted(missing_c),
            },
            error=None if ok else f"missing g={missing_g} c={missing_c}",
            duration_ms=(time.perf_counter() - started) * 1000,
        )
    except Exception as exc:  # noqa: BLE001
        return DimensionReport(
            name="Repository 新方法覆盖", status="FAIL", error=str(exc),
            duration_ms=(time.perf_counter() - started) * 1000,
        )


def dim_w3_conn_adapter_works() -> DimensionReport:
    """ConnAdapter 真能让 raw sqlite3.Connection 跑通 Repository"""
    started = time.perf_counter()
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "backend"))
    import tempfile
    try:
        from app.db import Database
        from app.modules.commitment import CommitmentRepository
        from app.modules.glossary import GlossaryRepository

        with tempfile.TemporaryDirectory() as td:
            db = Database(Path(td) / "app.db")
            db.conn.execute("PRAGMA foreign_keys=OFF")
            db.conn.execute(
                """INSERT INTO clients(id, name, alias, domain, type, intro, stage,
                                       color, created_at, updated_at, frozen_at)
                   VALUES('c1','X','','p','p','','','#fff','2026-05-20','2026-05-20',NULL)"""
            )
            db.conn.commit()

            # 直接传 conn(不传 Database)
            g = GlossaryRepository(db.conn)
            c = CommitmentRepository(db.conn)

            term = g.create_term(client_id="c1", term="测试", definition="")
            assert term.term == "测试"
            terms, total = g.list_terms_paginated("c1")
            assert total == 1

            pendings = c.list_pending_for_client("c1")
            assert pendings == []

        return DimensionReport(
            name="ConnAdapter raw conn 兼容",
            status="PASS",
            details={"glossary_create_via_conn": True, "commitment_query_via_conn": True},
            duration_ms=(time.perf_counter() - started) * 1000,
        )
    except Exception as exc:  # noqa: BLE001
        return DimensionReport(
            name="ConnAdapter raw conn 兼容", status="FAIL", error=str(exc),
            duration_ms=(time.perf_counter() - started) * 1000,
        )


def dim_w3_legacy_glossary_store_api_compat() -> DimensionReport:
    """legacy services/glossary_store.py 的 5 个公开函数签名仍可用"""
    started = time.perf_counter()
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "backend"))
    try:
        from app.services.glossary_store import (
            GlossaryEntry,
            create_glossary_entry,
            delete_glossary_entry,
            get_glossary_entry,
            list_glossary,
            update_glossary_entry,
        )
        # 函数都能 import,GlossaryEntry 是 frozen dataclass
        import dataclasses
        assert dataclasses.is_dataclass(GlossaryEntry)
        return DimensionReport(
            name="legacy glossary_store 签名兼容",
            status="PASS",
            details={
                "exports": [
                    "list_glossary", "create_glossary_entry", "get_glossary_entry",
                    "update_glossary_entry", "delete_glossary_entry", "GlossaryEntry",
                ],
            },
            duration_ms=(time.perf_counter() - started) * 1000,
        )
    except Exception as exc:  # noqa: BLE001
        return DimensionReport(
            name="legacy glossary_store 签名兼容", status="FAIL", error=str(exc),
            duration_ms=(time.perf_counter() - started) * 1000,
        )


# ─── 回归 W2 全套 ────────────────────────────────────────────


def dim_w2_reuse() -> DimensionReport:
    """W2 7 维度(包含 W1 12 维度)"""
    started = time.perf_counter()
    result = subprocess.run(
        [PY, "scripts/run_w2_acceptance.py"],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    out = result.stdout
    pass_m = re.search(r"PASS=(\d+)", out)
    fail_m = re.search(r"FAIL=(\d+)", out)
    skip_m = re.search(r"SKIPPED=(\d+)", out)
    pass_n = int(pass_m.group(1)) if pass_m else 0
    fail_n = int(fail_m.group(1)) if fail_m else 0
    skip_n = int(skip_m.group(1)) if skip_m else 0
    return DimensionReport(
        name="W2 全套回归(含 W1)",
        status="PASS" if result.returncode == 0 else "FAIL",
        details={"w2_pass": pass_n, "w2_fail": fail_n, "w2_skipped": skip_n},
        error=None if result.returncode == 0 else f"{fail_n} W2 维度失败",
        duration_ms=(time.perf_counter() - started) * 1000,
    )


# ─── 编排 ──────────────────────────────────────────────────


DIMENSIONS = [
    ("W3-A 1. services 切线 26 测试全过", dim_w3_migration_tests),
    ("W3-A 2. glossary_store.py 无裸 SQL", dim_w3_glossary_store_no_raw_sql),
    ("W3-A 3. 3 commit services 无裸 SQL", dim_w3_commitment_services_no_raw_sql),
    ("W3-B 4. Repository 新方法覆盖", dim_w3_repository_method_coverage),
    ("W3-B 5. ConnAdapter raw conn 兼容", dim_w3_conn_adapter_works),
    ("W3-B 6. legacy glossary_store API 兼容", dim_w3_legacy_glossary_store_api_compat),
    ("W3 回归. W2 全套(含 W1 12)仍全过", dim_w2_reuse),
]


def main() -> int:
    print(f"\n{'='*72}\n  v2.1 Week 3 验收 · 6 维度 + W2 全套回归(=W1 12)\n{'='*72}\n")
    started_all = time.perf_counter()
    reports: list[DimensionReport] = []
    for name, func in DIMENSIONS:
        print(f"▸ {name} ...", end=" ", flush=True)
        try:
            rep = func()
            rep.name = name
        except Exception as exc:  # noqa: BLE001
            rep = DimensionReport(name=name, status="FAIL", error=f"runner crash: {exc}")
        reports.append(rep)
        marker = {"PASS": "✓", "FAIL": "✗", "SKIPPED": "○"}.get(rep.status, "?")
        print(f"{marker} {rep.status} ({rep.duration_ms:.0f}ms)")
        if rep.error:
            print(f"    └─ {rep.error}")

    total_ms = (time.perf_counter() - started_all) * 1000
    pass_count = sum(1 for r in reports if r.status == "PASS")
    fail_count = sum(1 for r in reports if r.status == "FAIL")
    skip_count = sum(1 for r in reports if r.status == "SKIPPED")

    print(f"\n{'='*72}")
    print(f"  W3 验收 · PASS={pass_count} FAIL={fail_count} SKIPPED={skip_count}")
    print(f"  总耗时 {total_ms/1000:.1f}s")
    print(f"{'='*72}\n")

    json_path = REPORTS_DIR / "w3_acceptance.json"
    json_path.write_text(
        json.dumps({
            "summary": {
                "total": len(reports),
                "pass": pass_count, "fail": fail_count, "skipped": skip_count,
                "duration_ms": total_ms,
                "verdict": "PASS" if fail_count == 0 else "FAIL",
            },
            "dimensions": [asdict(r) for r in reports],
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"详细结果: {json_path.relative_to(ROOT)}")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
