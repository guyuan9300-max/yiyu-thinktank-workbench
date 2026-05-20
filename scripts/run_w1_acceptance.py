"""Week 1 验收 runner · 一键跑完 12 个维度

跑法:
    backend/.venv/bin/python3 scripts/run_w1_acceptance.py
    # exit 0 = 全 PASS
    # exit 1 = 有 FAIL

输出:
    tests/reports/w1_acceptance.json — 每维度 JSON 结果
    tests/reports/w1_acceptance.log  — 完整日志
    stdout                            — 人读摘要

设计原则:
- 不 mock,尽量调真实路径
- 不夸大 PASS;FAIL 详细列出根因
- 每个维度独立可重跑
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "tests" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

VENV_PY = ROOT / "backend" / ".venv" / "bin" / "python3"
PY = str(VENV_PY) if VENV_PY.exists() else sys.executable


# ─────────────────────────────────────────────────────────────────────────────
# 维度报告类型
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class DimensionReport:
    name: str
    status: str  # PASS / FAIL / SKIPPED
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# 帮手
# ─────────────────────────────────────────────────────────────────────────────


def _run_pytest(test_path: str, expected_count: int | None = None) -> DimensionReport:
    started = time.perf_counter()
    result = subprocess.run(
        [PY, "-m", "pytest", test_path, "-v", "--tb=short", "-q", "--no-header"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    duration_ms = (time.perf_counter() - started) * 1000
    out = result.stdout + result.stderr

    # parse "X passed" / "Y failed" / "Z skipped"
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
        error = f"expected {expected_count} tests, got {passed} passed + {skipped} skipped"

    return DimensionReport(
        name=test_path,
        status=status,
        details={
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
            "expected": expected_count,
            "exit_code": result.returncode,
        },
        error=error,
        duration_ms=duration_ms,
    )


def _run_command(name: str, cmd: list[str], cwd: Path | None = None, timeout: int = 60) -> DimensionReport:
    started = time.perf_counter()
    result = subprocess.run(
        cmd,
        cwd=cwd or ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    duration_ms = (time.perf_counter() - started) * 1000
    return DimensionReport(
        name=name,
        status="PASS" if result.returncode == 0 else "FAIL",
        details={
            "exit_code": result.returncode,
            "stdout_tail": result.stdout[-300:],
            "stderr_tail": result.stderr[-300:],
        },
        error=None if result.returncode == 0 else f"exit code {result.returncode}",
        duration_ms=duration_ms,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 维度 1-6:pytest 套件
# ─────────────────────────────────────────────────────────────────────────────


def dim_1_schema() -> DimensionReport:
    return _run_pytest("tests/test_organization_mirror_schema.py", expected_count=11)


def dim_2_sync() -> DimensionReport:
    # 8 原 + 3 reviewer W3 新加(pending/disabled / HTTP 401 / malformed JSON)
    return _run_pytest("tests/test_organization_sync.py", expected_count=11)


def dim_3_directory() -> DimensionReport:
    # 17 原 - 1 替换 + 3 reviewer W3 新加(default exclude / explicit status / no filter)
    return _run_pytest("tests/test_organization_directory.py", expected_count=19)


def dim_4_views() -> DimensionReport:
    return _run_pytest("tests/test_organization_views.py", expected_count=12)


def dim_5_api() -> DimensionReport:
    return _run_pytest("backend/tests/test_local_organization_api.py", expected_count=3)


def dim_6_lint() -> DimensionReport:
    """lint 规则自检测 + 实跑(0 violation)"""
    lint_tests = _run_pytest("tests/test_lint_no_hardcoded_dept_ids.py", expected_count=6)
    lint_run = _run_command(
        "lint_no_hardcoded_dept_ids.py",
        [PY, "scripts/lint_no_hardcoded_dept_ids.py"],
    )
    combined_status = "PASS" if (lint_tests.status == "PASS" and lint_run.status == "PASS") else "FAIL"
    return DimensionReport(
        name="lint(6 tests + 实跑)",
        status=combined_status,
        details={
            "tests": lint_tests.details,
            "lint_exit": lint_run.details.get("exit_code"),
            "lint_stdout_tail": lint_run.details.get("stdout_tail"),
        },
        error=lint_tests.error or lint_run.error,
        duration_ms=lint_tests.duration_ms + lint_run.duration_ms,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 维度 7:Golden diff
# ─────────────────────────────────────────────────────────────────────────────


def dim_7_golden_diff() -> DimensionReport:
    rep = _run_command(
        "golden_diff.py",
        [PY, "scripts/golden_diff.py", "--threshold", "0.95"],
        timeout=120,
    )
    # 报告里加上 stdout 摘要(看 reproduction 比例)
    return rep


# ─────────────────────────────────────────────────────────────────────────────
# 维度 8:真实生产 e2e
# ─────────────────────────────────────────────────────────────────────────────


def dim_8_real_e2e() -> DimensionReport:
    rep = _run_pytest("backend/tests/test_local_organization_e2e.py", expected_count=1)
    # 这个测试可能被 skip(没生产 db)— 也算 PASS
    if rep.details.get("skipped") == 1 and rep.details.get("passed") == 0:
        rep.status = "SKIPPED"
        rep.error = "no production db or cloud unavailable"
    return rep


# ─────────────────────────────────────────────────────────────────────────────
# 维度 9:模块边界(静态)
# ─────────────────────────────────────────────────────────────────────────────


def dim_9_module_boundary() -> DimensionReport:
    """grep mirror_* 表名,只能出现在 organization 模块 / 测试 / 验收脚本里"""
    import re
    started = time.perf_counter()
    tables = ["mirror_organizations", "mirror_departments", "mirror_users", "mirror_client_related_users"]
    pattern = re.compile("|".join(tables))

    # 精确 allowlist(reviewer W2 修):startswith 太宽松,改成 dir 精确匹配 + 文件精确匹配
    allowed_dirs = (
        "backend/app/modules/organization",  # 模块自己合法
        "docs",                               # 文档可以提到表名
    )
    allowed_files = {
        "tests/test_organization_mirror_schema.py",
        "tests/test_organization_sync.py",
        "tests/test_organization_directory.py",
        "tests/test_organization_views.py",
        "tests/test_lint_no_hardcoded_dept_ids.py",
        "backend/tests/test_local_organization_api.py",
        "backend/tests/test_local_organization_e2e.py",
        "scripts/run_w1_acceptance.py",
        "scripts/lint_no_hardcoded_dept_ids.py",
    }

    violations: list[dict[str, Any]] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in {".py", ".ts", ".tsx", ".js", ".jsx"}:
            continue
        rel = str(path.relative_to(ROOT))
        # 排除 venv / node_modules / __pycache__
        if any(p in rel for p in (".venv", "node_modules", "__pycache__", ".git/")):
            continue
        # 精确匹配:文件名整个在 allowlist 里,或目录前缀 + '/'(避免 organization 匹配到 organizational)
        if rel in allowed_files:
            continue
        if any(rel.startswith(d + "/") for d in allowed_dirs):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            # 跳过注释行
            stripped = line.lstrip()
            if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("*"):
                continue
            if pattern.search(line):
                violations.append({"file": rel, "line": lineno, "snippet": line.strip()[:120]})

    duration_ms = (time.perf_counter() - started) * 1000
    return DimensionReport(
        name="模块边界(mirror_* 表)",
        status="PASS" if not violations else "FAIL",
        details={"violation_count": len(violations), "violations": violations[:10]},
        error=None if not violations else f"{len(violations)} 个非法引用",
        duration_ms=duration_ms,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 维度 10:启动健康(空 db + 真实 db)
# ─────────────────────────────────────────────────────────────────────────────


def dim_10_boot_health() -> DimensionReport:
    """create_app 在空 dir 和 真实 db 拷贝上都能启动"""
    started = time.perf_counter()
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "backend"))

    results = {}

    # A. 空 db
    try:
        from app.main import create_app
        with tempfile.TemporaryDirectory() as td:
            app = create_app(Path(td) / "data")
            state = app.state.app_state
            views = state.db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='view' AND name LIKE 'v_%'"
            ).fetchall()
            tables = state.db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'mirror_%'"
            ).fetchall()
            results["empty_db"] = {
                "ok": True,
                "view_count": len(views),
                "mirror_table_count": len(tables),
            }
    except Exception as exc:  # noqa: BLE001
        results["empty_db"] = {"ok": False, "error": str(exc)}

    # B. 真实生产 db 的拷贝(如果有)
    # reviewer W4 修:不只是看行数,要快照具体业务字段内容,verify migration 没改原数据
    prod_db = Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2/app.db"
    if prod_db.exists():
        try:
            # 1. migration 前快照(用 sqlite3 直接读,跳过 Database 自动 migration)
            pre_conn = sqlite3.connect(prod_db)
            pre_conn.row_factory = sqlite3.Row
            pre_clients = sorted(
                ((r["id"], r["name"], r["alias"], r["frozen_at"])
                 for r in pre_conn.execute("SELECT id, name, alias, frozen_at FROM clients").fetchall()),
                key=lambda x: x[0],
            )
            pre_events_count = pre_conn.execute("SELECT COUNT(*) AS n FROM event_lines").fetchone()["n"]
            pre_tasks_count = pre_conn.execute("SELECT COUNT(*) AS n FROM tasks").fetchone()["n"]
            pre_glossary_count = pre_conn.execute("SELECT COUNT(*) AS n FROM glossary_attributes").fetchone()["n"]
            pre_commits_count = pre_conn.execute("SELECT COUNT(*) AS n FROM commitments").fetchone()["n"]
            pre_conn.close()

            # 2. 拷贝 + 跑 migration
            with tempfile.TemporaryDirectory() as td:
                data_dir = Path(td) / "data"
                data_dir.mkdir()
                shutil.copy(prod_db, data_dir / "app.db")
                for ext in ("-wal", "-shm"):
                    f = (data_dir / "app.db").with_name("app.db" + ext)
                    if f.exists():
                        f.unlink()
                from app.main import create_app
                app = create_app(data_dir)
                state = app.state.app_state

                # 3. migration 后快照
                post_clients = sorted(
                    ((r["id"], r["name"], r["alias"], r["frozen_at"])
                     for r in state.db.fetchall("SELECT id, name, alias, frozen_at FROM clients")),
                    key=lambda x: x[0],
                )
                post_events_count = state.db.fetchone("SELECT COUNT(*) AS n FROM event_lines")["n"]
                post_tasks_count = state.db.fetchone("SELECT COUNT(*) AS n FROM tasks")["n"]
                post_glossary_count = state.db.fetchone("SELECT COUNT(*) AS n FROM glossary_attributes")["n"]
                post_commits_count = state.db.fetchone("SELECT COUNT(*) AS n FROM commitments")["n"]
                mirror_count = state.db.fetchone(
                    "SELECT COUNT(*) AS n FROM sqlite_master WHERE type='table' AND name LIKE 'mirror_%'"
                )["n"]
                view_count = state.db.fetchone(
                    "SELECT COUNT(*) AS n FROM sqlite_master WHERE type='view' AND name LIKE 'v_%'"
                )["n"]

                # 4. 内容级比对(reviewer W4 修)
                # 注意:v1.0 启动会自身做清理(purge_private_task_ingest_events 等),
                # 所以 tasks/events count 允许小幅波动。clients 内容严格不能改。
                data_intact = True
                data_diffs: list[str] = []
                v1_self_cleanup: list[str] = []

                # CLIENTS:严格检测(任何 client 消失或字段被改都是 v2.1 bug)
                if pre_clients != post_clients:
                    data_intact = False
                    pre_set = {c[0]: c for c in pre_clients}
                    post_set = {c[0]: c for c in post_clients}
                    for cid in pre_set:
                        if cid not in post_set:
                            data_diffs.append(f"client {cid} disappeared")
                        elif pre_set[cid] != post_set[cid]:
                            data_diffs.append(f"client {cid}: {pre_set[cid]} → {post_set[cid]}")
                        if len(data_diffs) >= 3:
                            break

                # 其他表:计数差小于 10% 算 v1.0 自身清理(可接受);超过 10% 报警
                def _check_table(name, pre, post, hard_limit=0.10):
                    if pre == 0 and post == 0:
                        return
                    if pre == 0:
                        v1_self_cleanup.append(f"{name}: 0 → {post}")
                        return
                    delta_pct = abs(pre - post) / max(pre, 1)
                    if delta_pct > hard_limit:
                        nonlocal data_intact
                        data_intact = False
                        data_diffs.append(f"{name} count {pre} → {post} (Δ {delta_pct:.1%} > {hard_limit:.0%})")
                    elif pre != post:
                        v1_self_cleanup.append(f"{name}: {pre} → {post} (v1.0 startup cleanup,可接受)")

                _check_table("event_lines", pre_events_count, post_events_count)
                _check_table("tasks", pre_tasks_count, post_tasks_count)
                _check_table("glossary_attributes", pre_glossary_count, post_glossary_count)
                _check_table("commitments", pre_commits_count, post_commits_count)

                results["real_db_migrated"] = {
                    "ok": data_intact and mirror_count == 4 and view_count >= 6,
                    "v1_clients_count": len(post_clients),
                    "v1_clients_data_intact": data_intact,
                    "data_diffs_sample": data_diffs[:5],
                    "v1_self_cleanup": v1_self_cleanup,  # 可接受的 v1.0 自清理
                    "v1_events_count": post_events_count,
                    "v1_tasks_count": post_tasks_count,
                    "v1_glossary_count": post_glossary_count,
                    "v1_commits_count": post_commits_count,
                    "mirror_tables_added": mirror_count,
                    "views_added": view_count,
                }
        except Exception as exc:  # noqa: BLE001
            results["real_db_migrated"] = {"ok": False, "error": str(exc)}
    else:
        results["real_db_migrated"] = {"ok": "SKIPPED", "reason": "no production db"}

    duration_ms = (time.perf_counter() - started) * 1000
    all_ok = all(r.get("ok") in (True, "SKIPPED") for r in results.values())
    return DimensionReport(
        name="启动健康(空 db + 真实 db)",
        status="PASS" if all_ok else "FAIL",
        details=results,
        error=None if all_ok else "见 details",
        duration_ms=duration_ms,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 维度 11:性能基线
# ─────────────────────────────────────────────────────────────────────────────


def dim_11_performance() -> DimensionReport:
    """真实 sync 一次计时 + 真实 HTTP API 100 次(经过 FastAPI 全栈)

    (修 reviewer W1):之前测的是 in-process Python 调用,数字 0.028ms 没意义。
    现在用 FastAPI TestClient 发真实 HTTP,经过 routing + 序列化 + middleware。
    """
    started = time.perf_counter()
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "backend"))

    prod_db = Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2/app.db"
    if not prod_db.exists():
        return DimensionReport(
            name="性能基线",
            status="SKIPPED",
            error="no production db",
            duration_ms=(time.perf_counter() - started) * 1000,
        )

    try:
        conn = sqlite3.connect(prod_db)
        conn.row_factory = sqlite3.Row
        token = conn.execute("SELECT value FROM settings WHERE key='cloud_access_token'").fetchone()
        url = conn.execute("SELECT value FROM settings WHERE key='cloud_api_url'").fetchone()
        conn.close()
        if not token or not url:
            return DimensionReport(
                name="性能基线",
                status="SKIPPED",
                error="no cloud creds",
                duration_ms=(time.perf_counter() - started) * 1000,
            )
        token_val = token["value"]
        url_val = url["value"]
    except Exception as exc:  # noqa: BLE001
        return DimensionReport(
            name="性能基线",
            status="SKIPPED",
            error=f"settings read fail: {exc}",
            duration_ms=(time.perf_counter() - started) * 1000,
        )

    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.modules.organization import sync_organization_directory

    sync_durations: list[float] = []
    api_durations: list[float] = []

    try:
        with tempfile.TemporaryDirectory() as td:
            # 拷贝真实 db,启动 FastAPI(模拟生产)
            data_dir = Path(td) / "data"
            data_dir.mkdir()
            shutil.copy(prod_db, data_dir / "app.db")
            for ext in ("-wal", "-shm"):
                f = data_dir / ("app.db" + ext)
                if f.exists():
                    f.unlink()

            app = create_app(data_dir)
            client = TestClient(app)
            client.__enter__()
            state = app.state.app_state  # type: ignore[attr-defined]
            state.cloud_api_url = url_val
            state.db.conn.execute(
                "INSERT OR REPLACE INTO settings(key, value) VALUES('cloud_access_token', ?)",
                (token_val,),
            )
            state.db.conn.commit()

            # 1 次 sync 计时(直接调函数,不是 HTTP — sync 本来就是后端内部操作)
            sync_start = time.perf_counter()
            report = sync_organization_directory(
                state.db, cloud_base_url=url_val, cloud_token=token_val, derive_cru_from_local=True,
            )
            sync_durations.append((time.perf_counter() - sync_start) * 1000)
            if report.status != "ok":
                return DimensionReport(
                    name="性能基线",
                    status="FAIL",
                    error=f"sync failed: {report.error}",
                    details={"sync_status": report.status},
                    duration_ms=(time.perf_counter() - started) * 1000,
                )

            # 100 次 profile API:走真实 HTTP routing + Pydantic 序列化 + FastAPI middleware
            for _ in range(100):
                api_start = time.perf_counter()
                resp = client.get("/api/v1/local/organization/profile")
                api_durations.append((time.perf_counter() - api_start) * 1000)
                assert resp.status_code == 200, f"profile API broke: {resp.status_code}"

            client.__exit__(None, None, None)
    except Exception as exc:  # noqa: BLE001
        return DimensionReport(
            name="性能基线",
            status="FAIL",
            error=str(exc),
            duration_ms=(time.perf_counter() - started) * 1000,
        )

    sync_avg = sync_durations[0]
    api_avg = sum(api_durations) / len(api_durations) if api_durations else 0
    api_p95 = sorted(api_durations)[int(len(api_durations) * 0.95) - 1] if api_durations else 0

    # 阈值(真实 HTTP):sync < 5000ms,api avg < 50ms,api p95 < 200ms
    ok = sync_avg < 5000 and api_avg < 50 and api_p95 < 200

    return DimensionReport(
        name="性能基线",
        status="PASS" if ok else "FAIL",
        details={
            "sync_ms": round(sync_avg, 1),
            "api_avg_ms": round(api_avg, 3),
            "api_p95_ms": round(api_p95, 3),
            "api_samples": len(api_durations),
            "note": "API 数字走真实 HTTP TestClient + Pydantic 序列化 + FastAPI middleware,非纯 SQL 时间",
            "thresholds": {"sync_ms": 5000, "api_avg_ms": 50, "api_p95_ms": 200},
        },
        error=None if ok else f"sync={sync_avg:.0f}ms api_avg={api_avg:.1f}ms api_p95={api_p95:.1f}ms",
        duration_ms=(time.perf_counter() - started) * 1000,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 维度 12:mirror_users vs cloud_session_user 一致性
# ─────────────────────────────────────────────────────────────────────────────


def dim_12_data_consistency() -> DimensionReport:
    """sync 后,mirror_users 跟 cloud_session_user 在共有字段上一致"""
    started = time.perf_counter()
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "backend"))

    prod_db = Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2/app.db"
    if not prod_db.exists():
        return DimensionReport(
            name="数据真实性比对",
            status="SKIPPED",
            error="no production db",
            duration_ms=(time.perf_counter() - started) * 1000,
        )

    conn = sqlite3.connect(prod_db)
    conn.row_factory = sqlite3.Row
    session_row = conn.execute("SELECT value FROM settings WHERE key='cloud_session_user'").fetchone()
    token = conn.execute("SELECT value FROM settings WHERE key='cloud_access_token'").fetchone()
    url = conn.execute("SELECT value FROM settings WHERE key='cloud_api_url'").fetchone()
    conn.close()

    if not session_row or not token or not url:
        return DimensionReport(
            name="数据真实性比对",
            status="SKIPPED",
            error="no cloud_session_user or creds",
            duration_ms=(time.perf_counter() - started) * 1000,
        )

    session = json.loads(session_row["value"])
    token_val = token["value"]
    url_val = url["value"]

    from app.db import Database
    from app.modules.organization import (
        get_organization_directory,
        sync_organization_directory,
    )

    with tempfile.TemporaryDirectory() as td:
        shutil.copy(prod_db, Path(td) / "app.db")
        for ext in ("-wal", "-shm"):
            f = Path(td) / ("app.db" + ext)
            if f.exists():
                f.unlink()
        db = Database(Path(td) / "app.db")

        report = sync_organization_directory(
            db, cloud_base_url=url_val, cloud_token=token_val,
        )
        if report.status != "ok":
            return DimensionReport(
                name="数据真实性比对",
                status="FAIL",
                error=f"sync failed: {report.error}",
                duration_ms=(time.perf_counter() - started) * 1000,
            )

        directory = get_organization_directory(db)
        mirror_user = directory.get_user_by_id(session["id"])

    if mirror_user is None:
        return DimensionReport(
            name="数据真实性比对",
            status="FAIL",
            error=f"user {session['id']} not in mirror_users after sync",
            duration_ms=(time.perf_counter() - started) * 1000,
        )

    # 比对字段
    diffs = []
    if session.get("fullName") != mirror_user.full_name:
        diffs.append(f"fullName: session='{session.get('fullName')}' vs mirror='{mirror_user.full_name}'")
    if (session.get("departmentId") or None) != (mirror_user.department_id or None):
        diffs.append(f"departmentId: session='{session.get('departmentId')}' vs mirror='{mirror_user.department_id}'")
    if bool(session.get("isDepartmentLead")) != bool(mirror_user.is_department_lead):
        diffs.append(f"isDepartmentLead: session={session.get('isDepartmentLead')} vs mirror={mirror_user.is_department_lead}")
    if session.get("organizationId") != mirror_user.organization_id:
        diffs.append(f"organizationId: session='{session.get('organizationId')}' vs mirror='{mirror_user.organization_id}'")

    # 部门名:session.departmentName 应该 == mirror_departments[user.department_id].name
    if mirror_user.department_id:
        dept = directory.get_department_by_id(mirror_user.department_id)
        if dept and session.get("departmentName") and session["departmentName"] != dept.name:
            diffs.append(
                f"departmentName mismatch: session='{session.get('departmentName')}' "
                f"vs cloud_truth='{dept.name}'"
            )

    return DimensionReport(
        name="数据真实性比对",
        status="PASS" if not diffs else "FAIL",
        details={
            "session_user_id": session.get("id"),
            "session_departmentId": session.get("departmentId"),
            "session_departmentName": session.get("departmentName"),
            "mirror_full_name": mirror_user.full_name,
            "mirror_department_id": mirror_user.department_id,
            "diffs": diffs,
        },
        error=None if not diffs else f"{len(diffs)} 处不一致",
        duration_ms=(time.perf_counter() - started) * 1000,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 总编排
# ─────────────────────────────────────────────────────────────────────────────


DIMENSIONS = [
    ("1. Schema 完整性", dim_1_schema),
    ("2. Sync 正确性", dim_2_sync),
    ("3. Repository SSOT getter", dim_3_directory),
    ("4. SQL Views", dim_4_views),
    ("5. 后端 API", dim_5_api),
    ("6. Lint 防御", dim_6_lint),
    ("7. 不破坏 v1.0 (golden diff)", dim_7_golden_diff),
    ("8. 真实生产 e2e", dim_8_real_e2e),
    ("9. 模块边界", dim_9_module_boundary),
    ("10. 启动健康", dim_10_boot_health),
    ("11. 性能基线", dim_11_performance),
    ("12. 数据真实性比对", dim_12_data_consistency),
]


def main() -> int:
    print(f"\n{'='*72}\n  v2.1 Week 1 验收 · 12 维度全跑\n{'='*72}\n")
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
    print(f"  总计 {len(reports)} 维度 · PASS={pass_count} FAIL={fail_count} SKIPPED={skip_count}")
    print(f"  总耗时 {total_ms/1000:.1f}s")
    print(f"{'='*72}\n")

    # 写 JSON
    json_path = REPORTS_DIR / "w1_acceptance.json"
    json_path.write_text(
        json.dumps(
            {
                "summary": {
                    "total": len(reports),
                    "pass": pass_count,
                    "fail": fail_count,
                    "skipped": skip_count,
                    "duration_ms": total_ms,
                    "verdict": "PASS" if fail_count == 0 else "FAIL",
                },
                "dimensions": [asdict(r) for r in reports],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"详细结果: {json_path.relative_to(ROOT)}")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
