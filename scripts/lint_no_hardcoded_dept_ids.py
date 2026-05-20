"""W1-5 · Lint:禁止硬编码部门实例 id

v2.1 SSOT 铁律:部门 id 是 organization 模块的动态数据,不能硬编码在业务代码里。

合法:
- `directory.get_department_by_id(dept_id)` — dept_id 是变量
- `"department_lead"` — 这是角色类型字符串,不是部门 id
- `"department_alignment"` — 类型枚举值
- `"department_id"` — 列名

非法:
- `if dept_id == "dept_consult_strategy":` — 硬编码具体部门 id
- `DEPT_ID = "department_gq160gdz"` — 硬编码

跑法:
    python scripts/lint_no_hardcoded_dept_ids.py
    # exit 0 = 无 violation
    # exit 1 = 有 violation,列在 stderr

设计:
- 只 grep 字符串字面量(单/双引号包裹)
- 匹配模式:
  - `dept_<word>_<word>` (像 dept_consult_strategy)
  - `department_<8+ alphanumeric>` (像 department_gq160gdz / department_b3zvoei7)
- 排除:
  - 注释行(# 或 //)
  - tests/  scripts/  docs/  node_modules/  .git/  __pycache__/
  - backend/app/modules/organization/(允许 sync.py 等内部)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 部门 id 硬编码模式
# 部门 id 形式:
#   - `dept_<word>_<word>`:语义化 id(像 dept_consult_strategy)
#   - `department_<6+ alnum,含数字>`:随机 id(像 department_b3zvoei7 / department_gq160gdz)
# 排除:
#   - `department_alignment` / `department_lead` 等是角色/类型字符串(全字母 + 单一概念词)
PATTERNS = [
    re.compile(r"""['"]dept_[a-z]+_[a-z][a-z_]*['"]"""),                # dept_consult_strategy
    re.compile(r"""['"]department_(?=[a-z0-9]*[0-9])[a-z0-9]{6,}['"]"""),  # 必须含数字
]

# 扫描的文件类型
EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx"}

# 排除路径前缀(相对 ROOT)
EXCLUDE_PREFIXES = {
    "tests/",
    "backend/tests/",
    "cloud_backend/",          # cloud_backend 不在 v2.1 范围(Week 6 单独处理)
    "scripts/",
    "docs/",
    "node_modules/",
    ".git/",
    "dist/",
    "build/",
    "out/",
    "release/",
    "backend/.venv/",
    "backend/app/__pycache__/",
    "backend/app/modules/organization/",  # 允许 sync.py 内部使用
}


def _is_excluded(rel_path: str) -> bool:
    for prefix in EXCLUDE_PREFIXES:
        if rel_path.startswith(prefix):
            return True
    if "__pycache__" in rel_path:
        return True
    if "/node_modules/" in rel_path:
        return True
    return False


def _is_comment_line(line: str, ext: str) -> bool:
    stripped = line.lstrip()
    if ext == ".py":
        return stripped.startswith("#")
    if ext in {".ts", ".tsx", ".js", ".jsx"}:
        return stripped.startswith("//") or stripped.startswith("*")
    return False


def scan_file(path: Path, root: Path) -> list[tuple[str, int, str, str]]:
    """返回 [(rel_path, line_no, hit, line_content)]"""
    ext = path.suffix
    violations: list[tuple[str, int, str, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if _is_comment_line(line, ext):
            continue
        for pattern in PATTERNS:
            for m in pattern.finditer(line):
                violations.append((
                    str(path.relative_to(root)),
                    lineno,
                    m.group(0),
                    line.strip(),
                ))
    return violations


def main() -> int:
    all_violations: list[tuple[str, int, str, str]] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in EXTENSIONS:
            continue
        rel = str(path.relative_to(ROOT))
        if _is_excluded(rel):
            continue
        all_violations.extend(scan_file(path, ROOT))

    if not all_violations:
        print("✓ no hardcoded department ids found")
        return 0

    print(f"\n❌ {len(all_violations)} hardcoded department id(s) found:\n", file=sys.stderr)
    for rel_path, lineno, hit, content in all_violations:
        print(f"  {rel_path}:{lineno}", file=sys.stderr)
        print(f"      hit: {hit}", file=sys.stderr)
        print(f"      line: {content[:120]}", file=sys.stderr)
        print(file=sys.stderr)
    print(
        "v2.1 SSOT 铁律:部门 id 是动态数据,改用 OrganizationDirectory.get_department_by_id() 或语义判断。",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
