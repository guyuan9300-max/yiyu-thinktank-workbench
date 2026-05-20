"""W2-A 验证 · 模块 boundary linter 自检

跑法:
    backend/.venv/bin/python3 -m pytest tests/test_lint_module_boundaries.py -v

设计:
- 检测真违反:`from app.modules.organization.repository import X`
- 不误报合法:`from app.modules.organization import X`
- 例外路径(tests/ / scripts/)不被扫
- 模块内部 self-import 不被报
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "lint_module_boundaries.py"


_LINT_MOD = None


def _get_lint_module():
    global _LINT_MOD
    if _LINT_MOD is None:
        sys.path.insert(0, str(ROOT / "scripts"))
        import importlib.util
        spec = importlib.util.spec_from_file_location("lint_mb", SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        # dataclass 在 frozen=True 时需要 sys.modules 里找到自己的模块
        sys.modules["lint_mb"] = mod
        spec.loader.exec_module(mod)
        _LINT_MOD = mod
    return _LINT_MOD


def _check_files(files: dict[str, str], module_names: set[str]) -> int:
    """在虚拟文件目录上跑 linter,返回 violation 数"""
    import tempfile
    from pathlib import Path as P
    mod = _get_lint_module()
    with tempfile.TemporaryDirectory() as td:
        tmp_root = P(td)
        for rel, content in files.items():
            file_path = tmp_root / rel
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
        violations = mod.lint_directory(tmp_root, module_names)
        return len(violations)


@pytest.mark.unit
def test_linter_script_runs_clean_on_current_codebase():
    """当前 codebase 应该 0 violation"""
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"linter found violations:\n{result.stdout}\n{result.stderr}"


@pytest.mark.unit
def test_catches_internal_file_import():
    """from app.modules.organization.repository import X → 应该被检测"""
    files = {
        "src/some_service.py": "from app.modules.organization.repository import OrganizationDirectory\n",
    }
    assert _check_files(files, {"organization"}) == 1


@pytest.mark.unit
def test_catches_internal_module_import_statement():
    """import app.modules.organization.sync → 应该被检测"""
    files = {
        "src/some_service.py": "import app.modules.organization.sync\n",
    }
    assert _check_files(files, {"organization"}) == 1


@pytest.mark.unit
def test_legal_init_import_not_flagged():
    """from app.modules.organization import X → 合法,不报"""
    files = {
        "src/some_service.py": "from app.modules.organization import OrganizationDirectory\n",
    }
    assert _check_files(files, {"organization"}) == 0


@pytest.mark.unit
def test_tests_dir_is_exempt():
    """tests/ 路径可以 import 内部文件(测试需要)"""
    files = {
        "tests/test_x.py": "from app.modules.organization.repository import OrganizationDirectory\n",
    }
    assert _check_files(files, {"organization"}) == 0


@pytest.mark.unit
def test_scripts_dir_is_exempt():
    """scripts/ 路径可以 import 内部(脚本是边界外)"""
    files = {
        "scripts/dump.py": "from app.modules.organization.repository import OrganizationDirectory\n",
    }
    assert _check_files(files, {"organization"}) == 0


@pytest.mark.unit
def test_module_self_import_not_flagged():
    """organization 模块内部 import 自己的内部文件 → 合法"""
    files = {
        "backend/app/modules/organization/__init__.py": "from .repository import OrganizationDirectory\n",
    }
    assert _check_files(files, {"organization"}) == 0


@pytest.mark.unit
def test_unknown_module_name_not_flagged():
    """如果 import 的模块不在 modules/ 下,不报(可能是别的库)"""
    files = {
        "src/x.py": "from app.modules.nonexistent.foo import bar\n",
    }
    assert _check_files(files, {"organization"}) == 0


@pytest.mark.unit
def test_multiple_violations_all_caught():
    files = {
        "src/a.py": "from app.modules.organization.repository import X\n",
        "src/b.py": "import app.modules.organization.sync\n",
        "src/c.py": "from app.modules.organization.views import VIEWS_SQL\n",
    }
    assert _check_files(files, {"organization"}) == 3
