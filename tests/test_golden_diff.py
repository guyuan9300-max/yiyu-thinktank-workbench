"""
Pytest wrapper for scripts/golden_diff.py

跑法:
    pytest tests/test_golden_diff.py -v
    pytest tests/test_golden_diff.py::test_self_diff_is_perfect -v

设计:
- self diff:在同一 db 上跑应该 100% 复现(self-test)
- per_client diff:每个 golden 客户单独跑 + 单独 assert,失败时报告具体客户
- 跑这个测试需要可用的 yiyu db,CI 环境无 db 时整体 skip
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = ROOT / "tests" / "fixtures" / "golden"


def _db_available() -> bool:
    data_dir = os.environ.get(
        "YIYU_WORKBENCH_DATA_DIR",
        os.path.expanduser("~/Library/Application Support/YiyuThinkTankWorkbench2"),
    )
    return (Path(data_dir) / "app.db").exists()


pytestmark = pytest.mark.skipif(
    not _db_available(),
    reason="no yiyu db at YIYU_WORKBENCH_DATA_DIR — golden diff requires a live db",
)


def _run_diff(threshold: float = 0.95, json_out: Path | None = None) -> tuple[int, str, list[dict]]:
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "golden_diff.py"),
        f"--threshold={threshold}",
    ]
    if json_out:
        cmd.append(f"--json-out={json_out}")

    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    reports = []
    if json_out and json_out.exists():
        reports = json.loads(json_out.read_text(encoding="utf-8"))
    return result.returncode, result.stdout + result.stderr, reports


@pytest.mark.integration
def test_fixtures_exist():
    """golden fixtures 必须存在 — Day 0 产出"""
    for name in ["日慈基金会.json", "为爱黔行.json", "CFFC.json"]:
        path = FIXTURES_DIR / name
        assert path.exists(), f"missing golden fixture: {path}"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "raw" in data, f"fixture {name} missing 'raw' key"
        assert "event_lines" in data["raw"], f"fixture {name} missing raw.event_lines"


@pytest.mark.integration
def test_self_diff_is_perfect(tmp_path):
    """在 v1.0 baseline 数据上跑应该 100% 复现 — 否则 dump/diff 规则不一致"""
    json_out = tmp_path / "report.json"
    rc, output, reports = _run_diff(threshold=0.99, json_out=json_out)
    assert rc == 0, f"self-diff should pass with 99% threshold on baseline data:\n{output}"
    assert len(reports) == 3, f"expected 3 client reports, got {len(reports)}"
    for r in reports:
        assert "error" not in r, f"client {r.get('client_name')} errored: {r.get('error')}"
        assert r["overall_reproduction"] >= 0.99, (
            f"client {r['client_name']} only {r['overall_reproduction']:.2%} — "
            f"dump/diff 规则可能有漂移"
        )


@pytest.mark.integration
def test_v21_diff_meets_threshold(tmp_path):
    """v2.1 重构后跑这个:每个客户 ≥ 95% 复现"""
    json_out = tmp_path / "report.json"
    rc, output, reports = _run_diff(threshold=0.95, json_out=json_out)
    if rc != 0:
        # 失败时报告具体哪个客户哪个表掉链子
        failures = []
        for r in reports:
            if "error" in r:
                failures.append(f"{r['client_name']}: {r['error']}")
                continue
            if r["overall_reproduction"] < 0.95:
                bad_tables = {
                    t: m for t, m in r["per_table"].items()
                    if m["reproduction"] < 0.95
                }
                failures.append(
                    f"{r['client_name']} overall={r['overall_reproduction']:.2%} "
                    f"bad_tables={list(bad_tables.keys())}"
                )
        pytest.fail("\n".join(failures) + "\n\nFull output:\n" + output)


@pytest.mark.integration
@pytest.mark.parametrize("client_name", ["日慈基金会", "为爱黔行", "CFFC"])
def test_per_client_minimum(client_name, tmp_path):
    """每个客户单独 assert,失败时直接定位"""
    json_out = tmp_path / "report.json"
    rc, output, reports = _run_diff(threshold=0.95, json_out=json_out)
    matching = [r for r in reports if r.get("client_name") == client_name]
    assert matching, f"no report for {client_name}"
    r = matching[0]
    assert "error" not in r, f"{client_name} errored: {r.get('error')}"
    assert r["overall_reproduction"] >= 0.95, (
        f"{client_name} reproduction = {r['overall_reproduction']:.2%}\n"
        f"per_table = {json.dumps(r['per_table'], ensure_ascii=False, indent=2)}"
    )
