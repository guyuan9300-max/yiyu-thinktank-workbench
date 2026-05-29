"""Week 2 验收 runner · 10 维度 + 复用 W1 12 维度

跑法:
    backend/.venv/bin/python3 scripts/run_w2_acceptance.py
    # exit 0 = W2 + W1 全 PASS
    # exit 1 = 有 FAIL

输出:
    tests/reports/w2_acceptance.json
    stdout — 人读摘要
"""
from __future__ import annotations

import json
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

    import re
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


def _run_shell(name: str, cmd: list[str]) -> DimensionReport:
    started = time.perf_counter()
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=60)
    return DimensionReport(
        name=name,
        status="PASS" if result.returncode == 0 else "FAIL",
        details={"exit_code": result.returncode,
                 "stdout_tail": result.stdout[-200:],
                 "stderr_tail": result.stderr[-200:]},
        error=None if result.returncode == 0 else f"exit {result.returncode}",
        duration_ms=(time.perf_counter() - started) * 1000,
    )


# ─── W2 维度 ───


def dim_w2_a_linter_self_tests() -> DimensionReport:
    return _run_pytest("tests/test_lint_module_boundaries.py", expected_count=9)


def dim_w2_a_linter_runs_clean() -> DimensionReport:
    return _run_shell("lint_module_boundaries 实跑", [PY, "scripts/lint_module_boundaries.py"])


def dim_w2_b_llm_context() -> DimensionReport:
    return _run_pytest("tests/test_llm_context.py", expected_count=21)


def dim_w2_c_business_modules() -> DimensionReport:
    return _run_pytest("tests/test_w2_business_modules.py", expected_count=29)


def dim_w2_all_modules_loadable() -> DimensionReport:
    """所有 7 业务模块 + llm_context + organization 都能 import,且 __all__ 不为空"""
    started = time.perf_counter()
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "backend"))
    expected_modules = [
        "app.modules.client", "app.modules.commitment", "app.modules.glossary",
        "app.modules.intelligence", "app.modules.knowledge", "app.modules.narrative",
        "app.modules.task", "app.modules.organization", "app.llm_context",
    ]
    failed: list[str] = []
    info: dict[str, list[str]] = {}
    for name in expected_modules:
        try:
            import importlib
            mod = importlib.import_module(name)
            all_list = getattr(mod, "__all__", [])
            if not all_list:
                failed.append(f"{name}: empty __all__")
            else:
                info[name] = list(all_list)
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{name}: import failed: {exc}")

    return DimensionReport(
        name="9 个模块都能 import + 有 __all__",
        status="PASS" if not failed else "FAIL",
        details={"modules": info, "failed": failed},
        error=None if not failed else f"{len(failed)} 个模块失败",
        duration_ms=(time.perf_counter() - started) * 1000,
    )


def dim_w2_prompt_log_table_present() -> DimensionReport:
    """prompt_log 表 + 3 个索引在新建 db 里存在"""
    started = time.perf_counter()
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "backend"))
    import tempfile
    try:
        from app.db import Database
        with tempfile.TemporaryDirectory() as td:
            db = Database(Path(td) / "app.db")
            table = db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='prompt_log'"
            ).fetchone()
            indexes = db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_prompt_log_%'"
            ).fetchall()
            idx_names = {r["name"] for r in indexes}
        ok = table is not None and len(idx_names) >= 3
        return DimensionReport(
            name="prompt_log 表 + 索引",
            status="PASS" if ok else "FAIL",
            details={"table_exists": table is not None, "indexes": sorted(idx_names)},
            error=None if ok else "missing table or indexes",
            duration_ms=(time.perf_counter() - started) * 1000,
        )
    except Exception as exc:  # noqa: BLE001
        return DimensionReport(
            name="prompt_log 表 + 索引", status="FAIL", error=str(exc),
            duration_ms=(time.perf_counter() - started) * 1000,
        )


# ─── 复用 W1 12 维度 ───


def dim_w1_reuse() -> DimensionReport:
    """跑一遍 W1 12 维度,作为 W2 不破坏 W1 的回归"""
    started = time.perf_counter()
    result = subprocess.run(
        [PY, "scripts/run_w1_acceptance.py"],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    # parse PASS=X FAIL=Y SKIPPED=Z
    import re
    out = result.stdout
    pass_m = re.search(r"PASS=(\d+)", out)
    fail_m = re.search(r"FAIL=(\d+)", out)
    skip_m = re.search(r"SKIPPED=(\d+)", out)
    pass_n = int(pass_m.group(1)) if pass_m else 0
    fail_n = int(fail_m.group(1)) if fail_m else 0
    skip_n = int(skip_m.group(1)) if skip_m else 0
    return DimensionReport(
        name="W1 12 维度回归(reuse)",
        status="PASS" if result.returncode == 0 else "FAIL",
        details={"w1_pass": pass_n, "w1_fail": fail_n, "w1_skipped": skip_n},
        error=None if result.returncode == 0 else f"{fail_n} W1 维度失败",
        duration_ms=(time.perf_counter() - started) * 1000,
    )


# ─── 编排 ───


DIMENSIONS = [
    ("W2-A 1. lint module boundaries 自检测试", dim_w2_a_linter_self_tests),
    ("W2-A 2. lint module boundaries 实跑全 codebase", dim_w2_a_linter_runs_clean),
    ("W2-B 3. LLM Context (composer/logger/inspector)", dim_w2_b_llm_context),
    ("W2-B 4. prompt_log 表 + 索引存在", dim_w2_prompt_log_table_present),
    ("W2-C 5. 7 业务模块骨架(commitment 完整 + 占位 SSOT 通路)", dim_w2_c_business_modules),
    ("W2-C 6. 9 模块全可 import + __all__ 不为空", dim_w2_all_modules_loadable),
    ("W2 回归. W1 12 维度仍全过", dim_w1_reuse),
]


def main() -> int:
    print(f"\n{'='*72}\n  v2.1 Week 2 验收 · 7 维度(含 W1 全套回归)\n{'='*72}\n")
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
    print(f"  W2 验收 · PASS={pass_count} FAIL={fail_count} SKIPPED={skip_count}")
    print(f"  总耗时 {total_ms/1000:.1f}s")
    print(f"{'='*72}\n")

    json_path = REPORTS_DIR / "w2_acceptance.json"
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
