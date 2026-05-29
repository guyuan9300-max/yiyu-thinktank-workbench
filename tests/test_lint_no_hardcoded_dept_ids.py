"""W1-5 验证 · lint 规则自身的回归测试

确保:
- 真硬编码部门 id 会被检测出来
- 合法字符串(角色名/列名/类型字符串)不被误判
- 注释行不被检测
- 排除路径(tests/ / cloud_backend/)不被扫描
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "lint_no_hardcoded_dept_ids.py"


def _run_against_dir(target_dir: Path) -> tuple[int, str]:
    """临时改 cwd 跑 lint(但 lint 用的是 ROOT)— 改成 import + 直接调"""
    sys.path.insert(0, str(ROOT / "scripts"))
    import importlib.util
    spec = importlib.util.spec_from_file_location("lint_mod", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    violations = []
    for path in target_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in mod.EXTENSIONS:
            continue
        violations.extend(mod.scan_file(path, target_dir))
    return len(violations), "\n".join(f"{p}:{l}: {h}" for p, l, h, _ in violations)


@pytest.mark.unit
def test_lint_script_executable():
    """直接跑脚本应该 0 violation(当前 codebase 干净)"""
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"lint failed:\n{result.stderr}"


@pytest.mark.unit
def test_lint_catches_real_dept_id(tmp_path: Path):
    """植入一个 dept_consult_strategy 硬编码,应被检测"""
    bad_file = tmp_path / "bad.py"
    bad_file.write_text(
        "def check(dept_id):\n"
        "    if dept_id == 'dept_consult_strategy':\n"
        "        return True\n",
        encoding="utf-8",
    )
    count, output = _run_against_dir(tmp_path)
    assert count >= 1, f"should catch dept_consult_strategy, got:\n{output}"


@pytest.mark.unit
def test_lint_catches_random_department_id(tmp_path: Path):
    """植入 department_gq160gdz(随机 id)应被检测"""
    bad_file = tmp_path / "bad.ts"
    bad_file.write_text(
        "const MY_DEPT = 'department_gq160gdz';\n",
        encoding="utf-8",
    )
    count, output = _run_against_dir(tmp_path)
    assert count >= 1, f"should catch department_gq160gdz, got:\n{output}"


@pytest.mark.unit
def test_lint_ignores_role_type_strings(tmp_path: Path):
    """department_alignment / department_lead / department_id 这些不是部门 id"""
    file = tmp_path / "ok.py"
    file.write_text(
        "ROLE = 'department_lead'\n"
        "KEY = 'department_alignment'\n"
        "COLUMN = 'department_id'\n"
        "TYPE = 'department_control'\n",
        encoding="utf-8",
    )
    count, output = _run_against_dir(tmp_path)
    assert count == 0, f"should not flag role strings, got:\n{output}"


@pytest.mark.unit
def test_lint_ignores_comments(tmp_path: Path):
    """注释里的 dept_consult_strategy 不被检测"""
    file = tmp_path / "commented.py"
    file.write_text(
        "# old dept id was 'dept_consult_strategy'\n"
        "# we don't use 'department_gq160gdz' anymore\n",
        encoding="utf-8",
    )
    count, output = _run_against_dir(tmp_path)
    assert count == 0, f"should not flag comments, got:\n{output}"


@pytest.mark.unit
def test_lint_ignores_ts_comments(tmp_path: Path):
    """TS 双斜杠注释也忽略"""
    file = tmp_path / "commented.ts"
    file.write_text(
        "// old: 'dept_consult_strategy'\n"
        "// random: 'department_b3zvoei7'\n",
        encoding="utf-8",
    )
    count, output = _run_against_dir(tmp_path)
    assert count == 0, f"should not flag TS comments, got:\n{output}"
