"""W2-A · 模块边界 linter:禁止跨模块直接 import 内部文件

v2.1 铁律:
    模块间只能通过 __init__.py 导出的接口对话,不能 import 模块内部文件。

合法:
    from app.modules.organization import get_organization_directory     ✓
    from app.modules.organization import OrganizationDirectory          ✓

非法:
    from app.modules.organization.repository import OrganizationDirectory  ✗
    from app.modules.organization.sync import sync_organization_directory  ✗
    import app.modules.organization.schema                                 ✗

例外:
    - 模块内部 import 自己的内部文件
      (如 organization/__init__.py 里 `from .repository import ...` OK)
    - tests/ 和 backend/tests/ 可以 import 内部(测试需要直接覆盖内部)
    - scripts/ 可以 import 内部(脚本是边界外的)
    - backend/app/db.py 可以 import schema(启动时执行 schema SQL)

跑法:
    backend/.venv/bin/python3 scripts/lint_module_boundaries.py
    # exit 0 = 全合规
    # exit 1 = 发现违反

设计:
- 用 ast 模块精确解析 import(不靠 grep,避免字符串误匹配)
- 区分 "from X.Y import Z" 和 "import X.Y" 两种形式
- 输出 violation 时给具体 file:line:offending_import + 建议
"""
from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULES_DIR = ROOT / "backend" / "app" / "modules"


@dataclass(frozen=True)
class Violation:
    file: str
    line: int
    offending_import: str
    target_module: str  # 比如 "organization"
    target_internal: str  # 比如 "repository"
    suggestion: str


# 例外路径(可以 import 内部)
EXEMPT_PREFIXES = (
    "tests/",
    "backend/tests/",
    "scripts/",
    "backend/app/db.py",            # 启动时 import schema(setup 边界)
    "backend/app/modules/",         # 模块内部
)


def _is_exempt(file_rel: str) -> bool:
    return any(file_rel.startswith(p) for p in EXEMPT_PREFIXES)


def _list_module_names() -> set[str]:
    """枚举 backend/app/modules/ 下的所有子模块名"""
    if not MODULES_DIR.exists():
        return set()
    return {
        p.name for p in MODULES_DIR.iterdir()
        if p.is_dir() and not p.name.startswith("_") and not p.name.startswith("__")
    }


def _check_file(path: Path, module_names: set[str]) -> list[Violation]:
    rel = str(path.relative_to(ROOT))
    if _is_exempt(rel):
        return []

    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=rel)
    except (SyntaxError, UnicodeDecodeError):
        return []

    violations: list[Violation] = []

    for node in ast.walk(tree):
        # form 1: from app.modules.X.Y import Z
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            v = _check_dotted(mod, module_names)
            if v:
                target_module, target_internal = v
                violations.append(Violation(
                    file=rel,
                    line=node.lineno,
                    offending_import=f"from {mod} import {', '.join(a.name for a in node.names)}",
                    target_module=target_module,
                    target_internal=target_internal,
                    suggestion=f"改为:from app.modules.{target_module} import <name>(必须在 __init__.py __all__ 里)",
                ))

        # form 2: import app.modules.X.Y
        elif isinstance(node, ast.Import):
            for alias in node.names:
                v = _check_dotted(alias.name, module_names)
                if v:
                    target_module, target_internal = v
                    violations.append(Violation(
                        file=rel,
                        line=node.lineno,
                        offending_import=f"import {alias.name}",
                        target_module=target_module,
                        target_internal=target_internal,
                        suggestion=f"改为:from app.modules.{target_module} import <name>",
                    ))

    return violations


def _check_dotted(dotted: str, module_names: set[str]) -> tuple[str, str] | None:
    """检查 'app.modules.X.Y' 是否违反:返回 (X, Y) 或 None"""
    parts = dotted.split(".")
    # 形如 app.modules.<mod>.<internal>... 才检查;app.modules.<mod> 是合法的(__init__.py)
    if len(parts) < 4:
        return None
    if parts[0] != "app" or parts[1] != "modules":
        return None
    mod = parts[2]
    internal = parts[3]
    if mod not in module_names:
        return None
    if internal in ("__init__",):
        return None
    return mod, internal


def lint_directory(
    root: Path,
    module_names: set[str] | None = None,
) -> list[Violation]:
    """对指定 root 目录跑 lint,返回 violation 列表(可程序化调用)

    参数:
        root: 要扫描的目录根
        module_names: 模块名集合;None = 从 root/backend/app/modules/ 自动枚举
    """
    if module_names is None:
        module_dir = root / "backend" / "app" / "modules"
        if module_dir.exists():
            module_names = {
                p.name for p in module_dir.iterdir()
                if p.is_dir() and not p.name.startswith("_") and not p.name.startswith("__")
            }
        else:
            module_names = set()

    violations: list[Violation] = []
    for path in root.rglob("*.py"):
        if any(p in str(path) for p in (".venv", "__pycache__", "node_modules", ".git/")):
            continue
        rel = str(path.relative_to(root))
        if _is_exempt(rel):
            continue
        try:
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text, filename=rel)
        except (SyntaxError, UnicodeDecodeError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                v = _check_dotted(mod, module_names)
                if v:
                    target_module, target_internal = v
                    violations.append(Violation(
                        file=rel,
                        line=node.lineno,
                        offending_import=f"from {mod} import {', '.join(a.name for a in node.names)}",
                        target_module=target_module,
                        target_internal=target_internal,
                        suggestion=f"改为:from app.modules.{target_module} import <name>(必须在 __init__.py __all__ 里)",
                    ))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    v = _check_dotted(alias.name, module_names)
                    if v:
                        target_module, target_internal = v
                        violations.append(Violation(
                            file=rel,
                            line=node.lineno,
                            offending_import=f"import {alias.name}",
                            target_module=target_module,
                            target_internal=target_internal,
                            suggestion=f"改为:from app.modules.{target_module} import <name>",
                        ))
    return violations


def main() -> int:
    module_names = _list_module_names()
    if not module_names:
        print("ℹ no modules under backend/app/modules/, nothing to check")
        return 0

    all_violations = lint_directory(ROOT, module_names)

    if not all_violations:
        print(f"✓ no module boundary violations across {len(module_names)} module(s): {sorted(module_names)}")
        return 0

    print(f"\n❌ {len(all_violations)} module boundary violation(s) across {len(module_names)} module(s):\n",
          file=sys.stderr)
    for v in all_violations:
        print(f"  {v.file}:{v.line}", file=sys.stderr)
        print(f"      bad: {v.offending_import}", file=sys.stderr)
        print(f"      hit: app.modules.{v.target_module}.{v.target_internal}", file=sys.stderr)
        print(f"      fix: {v.suggestion}", file=sys.stderr)
        print(file=sys.stderr)
    print("v2.1 铁律:模块间只通过 __init__.py 接口对话,不能 import 内部文件。",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
