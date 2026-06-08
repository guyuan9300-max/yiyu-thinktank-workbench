"""data_flow_ledger · 机器生成"数据流账本"的 AST 静态分析工具。

对后端 Python 代码 (backend/app/ 主力 main.py 巨文件 + services/) 做 AST 分析，
为每张数据表产出：

  · 写边:所有 `INSERT INTO <表>` / `UPDATE <表>` 所在函数 @file:line，
          并 AST 上溯调用链到入口 (@app.* 端点 或 worker/scheduler/sync/_background)。
  · 读边:所有 `SELECT ... FROM <表>` / `JOIN <表>` 所在函数 @file:line + WHERE 过滤文本。
  · 置信度:
        static_confirmed  — 字面 `INSERT INTO 表名` / `FROM 表名` 直接确证
        call_name_match   — 调用链靠函数名匹配 (中等)
        needs_human       — 动态表名 (f-string / 拼接 / `{var}`)，或 "0 写边但真库有行"

纯只读:绝不修改任何运行系统/真库。连库只用 immutable=1。

跑法:
    # 全表 + 经验层 + 调用链，落盘账本
    python3 scripts/data_flow_ledger.py --all --chain \
        --db "/Users/.../app.db" \
        --out docs/CODEMAPS/data-flow/DATA_CENTER_LEDGER_20260608.md

    # 单表 eval
    python3 scripts/data_flow_ledger.py atomic_facts v2_documents \
        --db "/Users/.../app.db" --chain
"""
from __future__ import annotations

import argparse
import ast
import re
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND_APP = ROOT / "backend" / "app"

# 扫描范围:main.py + services/ (含子目录) + api/ + modules/ + db.py
SCAN_DIRS = [
    BACKEND_APP / "services",
    BACKEND_APP / "api",
    BACKEND_APP / "modules",
]
SCAN_FILES = [
    BACKEND_APP / "main.py",
    BACKEND_APP / "db.py",
    BACKEND_APP / "models.py",
]

SKIP_FRAGMENTS = (".venv", "__pycache__", "node_modules", "/dist/", "/build/")

# 入口名匹配 (worker / scheduler / sync / background)
ENTRY_NAME_RE = re.compile(r"(worker|scheduler|sched|sync|_background|background_|_loop|run_internet)", re.I)

# SQL 关键字抽取 (作用在单个字符串字面量上)
RE_INSERT = re.compile(r"\bINSERT\s+(?:OR\s+\w+\s+)?INTO\s+([A-Za-z_][\w]*)", re.I)
RE_UPDATE = re.compile(r"\bUPDATE\s+([A-Za-z_][\w]*)", re.I)
RE_FROM = re.compile(r"\bFROM\s+([A-Za-z_][\w]*)", re.I)
RE_JOIN = re.compile(r"\bJOIN\s+([A-Za-z_][\w]*)", re.I)

# 动态表名:f-string 占位、字符串拼接产生的 SQL → needs_human
RE_DYNAMIC_INSERT = re.compile(r"\bINSERT\s+(?:OR\s+\w+\s+)?INTO\s+(\{|\"|'|\s*$)", re.I)
RE_DYNAMIC_FROM = re.compile(r"\bFROM\s+(\{)", re.I)
RE_DYNAMIC_UPDATE = re.compile(r"\bUPDATE\s+(\{)", re.I)

# 抽取 WHERE 子句文本 (粗粒度:WHERE 到下一个分组关键字/字符串结束)
RE_WHERE = re.compile(
    r"\bWHERE\s+(.+?)(?:\bGROUP\s+BY\b|\bORDER\s+BY\b|\bLIMIT\b|\bHAVING\b|$)",
    re.I | re.S,
)

# 非数据表的 SQL 噪声 (FROM 子查询别名等很难完全排除，这里只挡明显非表)
SQL_NOISE_TABLES = {"dual"}


# ────────────────────────────────────────────────────────────────────
# 数据结构
# ────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class FuncKey:
    """函数唯一定位:文件 + 限定名 (含嵌套 qualname) + 行号。"""
    file: str
    qualname: str
    lineno: int

    def loc(self) -> str:
        return f"{self.file}:{self.lineno}"


@dataclass
class FuncInfo:
    key: FuncKey
    simple_name: str
    is_endpoint: bool = False
    endpoint_route: str = ""  # @app.post("/x") → "/x"
    is_worker_like: bool = False
    # 该函数体内出现的 string-literal SQL 片段 (拼接后近似)
    sql_strings: list[str] = field(default_factory=list)
    # 该函数体内被调用的简单函数名集合
    callees: set[str] = field(default_factory=set)
    # 该函数体内是否出现动态 SQL 表名 (f-string / 拼接)
    has_dynamic_sql: bool = False
    dynamic_sql_samples: list[str] = field(default_factory=list)


@dataclass
class WriteEdge:
    table: str
    func: FuncKey
    op: str  # INSERT / UPDATE
    chains: list[list[str]] = field(default_factory=list)  # 上溯到入口的链 (每条是 loc 列表)
    confidence: str = "static_confirmed"


@dataclass
class ReadEdge:
    table: str
    func: FuncKey
    op: str  # SELECT-FROM / JOIN
    where_texts: list[str] = field(default_factory=list)
    confidence: str = "static_confirmed"


# ────────────────────────────────────────────────────────────────────
# AST 提取
# ────────────────────────────────────────────────────────────────────
def _iter_string_literals(node: ast.AST) -> list[str]:
    """收集一个 AST 子树里所有字符串字面量 (含 f-string 的静态部分)。"""
    out: list[str] = []
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            out.append(n.value)
        elif isinstance(n, ast.JoinedStr):
            # f-string:把静态片段拼起来,占位用 {…} 标记 (供动态检测)
            buf = []
            for part in n.values:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    buf.append(part.value)
                else:
                    buf.append("{?}")
            out.append("".join(buf))
    return out


def _has_dynamic_table(s: str) -> bool:
    return bool(
        RE_DYNAMIC_INSERT.search(s)
        or RE_DYNAMIC_FROM.search(s)
        or RE_DYNAMIC_UPDATE.search(s)
        or "INSERT INTO {?}" in s.upper().replace("{?}", "{?}")
        or re.search(r"\bINTO\s+\{\?\}", s)
        or re.search(r"\bFROM\s+\{\?\}", s, re.I)
        or re.search(r"\bUPDATE\s+\{\?\}", s, re.I)
    )


def _collect_callees(node: ast.AST) -> set[str]:
    """收集函数体内被调用的简单名 (foo(...) 或 obj.foo(...) 取 foo)。"""
    out: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name):
                out.add(f.id)
            elif isinstance(f, ast.Attribute):
                out.add(f.attr)
    return out


def _endpoint_route(decorator: ast.AST) -> str | None:
    """若 decorator 形如 @app.post("/x") / @router.get(...) 返回路由字符串，否则 None。"""
    if not isinstance(decorator, ast.Call):
        return None
    f = decorator.func
    if not isinstance(f, ast.Attribute):
        return None
    if f.attr.lower() not in ("get", "post", "put", "delete", "patch"):
        return None
    base = f.value
    base_name = ""
    if isinstance(base, ast.Name):
        base_name = base.id
    elif isinstance(base, ast.Attribute):
        base_name = base.attr
    if base_name.lower() not in ("app", "router", "api", "apirouter"):
        return None
    route = ""
    if decorator.args and isinstance(decorator.args[0], ast.Constant):
        route = str(decorator.args[0].value)
    return route or "(route)"


def _build_func_registry(rel_file: str, tree: ast.AST) -> list[FuncInfo]:
    """遍历一个文件的 AST，为每个 (含嵌套) 函数建 FuncInfo。

    用 qualname (Outer.inner) 保证嵌套端点也能被识别。
    每个函数的 sql_strings/callees 只取"直接 body" (排除更深层嵌套函数),
    避免外层把内层的 SQL 误算进来。
    """
    infos: list[FuncInfo] = []

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = f"{prefix}.{child.name}" if prefix else child.name
                key = FuncKey(file=rel_file, qualname=qual, lineno=child.lineno)

                # 端点判定
                route = None
                for dec in child.decorator_list:
                    r = _endpoint_route(dec)
                    if r is not None:
                        route = r
                        break

                # 该函数"直接拥有"的节点 = body 内、但不进入更深的 FunctionDef
                direct_strings: list[str] = []
                direct_callees: set[str] = set()
                has_dyn = False
                dyn_samples: list[str] = []

                def scan_direct(n: ast.AST) -> None:
                    nonlocal has_dyn
                    for c in ast.iter_child_nodes(n):
                        if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            continue  # 不下钻嵌套函数 (它们自己会被 visit)
                        if isinstance(c, ast.Constant) and isinstance(c.value, str):
                            direct_strings.append(c.value)
                        elif isinstance(c, ast.JoinedStr):
                            for s in _iter_string_literals(c):
                                direct_strings.append(s)
                                if _has_dynamic_table(s):
                                    has_dyn = True
                                    if len(dyn_samples) < 4:
                                        dyn_samples.append(s.strip()[:120])
                        elif isinstance(c, ast.Call):
                            fn = c.func
                            if isinstance(fn, ast.Name):
                                direct_callees.add(fn.id)
                            elif isinstance(fn, ast.Attribute):
                                direct_callees.add(fn.attr)
                        scan_direct(c)

                for stmt in child.body:
                    scan_direct(stmt)

                # 再扫一遍 direct_strings 里普通字符串的动态拼接信号
                for s in direct_strings:
                    if _has_dynamic_table(s):
                        has_dyn = True
                        if len(dyn_samples) < 4:
                            dyn_samples.append(s.strip()[:120])

                info = FuncInfo(
                    key=key,
                    simple_name=child.name,
                    is_endpoint=route is not None,
                    endpoint_route=route or "",
                    is_worker_like=bool(ENTRY_NAME_RE.search(child.name)),
                    sql_strings=direct_strings,
                    callees=direct_callees,
                    has_dynamic_sql=has_dyn,
                    dynamic_sql_samples=dyn_samples,
                )
                infos.append(info)
                visit(child, qual)
            else:
                visit(child, prefix)

    visit(tree, "")
    return infos


# ────────────────────────────────────────────────────────────────────
# SQL → 表名 抽取
# ────────────────────────────────────────────────────────────────────
def _extract_tables(sql: str) -> dict[str, set[str]]:
    """从一段 SQL 字符串抽 {op: {table,...}}。op ∈ insert/update/from/join。"""
    res: dict[str, set[str]] = {"insert": set(), "update": set(), "from": set(), "join": set()}
    for m in RE_INSERT.finditer(sql):
        res["insert"].add(m.group(1))
    for m in RE_UPDATE.finditer(sql):
        res["update"].add(m.group(1))
    for m in RE_FROM.finditer(sql):
        t = m.group(1)
        if t.lower() not in SQL_NOISE_TABLES:
            res["from"].add(t)
    for m in RE_JOIN.finditer(sql):
        res["join"].add(m.group(1))
    return res


def _extract_where(sql: str) -> list[str]:
    out: list[str] = []
    for m in RE_WHERE.finditer(sql):
        w = " ".join(m.group(1).split())
        if w:
            out.append(w[:200])
    return out


# ────────────────────────────────────────────────────────────────────
# 全局索引 + 调用图
# ────────────────────────────────────────────────────────────────────
class Index:
    def __init__(self) -> None:
        self.funcs: list[FuncInfo] = []
        # simple_name → [FuncInfo]  (可能多个同名)
        self.by_name: dict[str, list[FuncInfo]] = defaultdict(list)
        # callee_name → set(caller simple_name)  反向调用图
        self.callers_of: dict[str, set[str]] = defaultdict(set)
        # 动态表名待人工核 (file:line, sample)
        self.dynamic_hits: list[tuple[str, str]] = []

    def add(self, info: FuncInfo) -> None:
        self.funcs.append(info)
        self.by_name[info.simple_name].append(info)
        for callee in info.callees:
            self.callers_of[callee].add(info.simple_name)
        if info.has_dynamic_sql:
            for s in (info.dynamic_sql_samples or ["<dynamic>"]):
                self.dynamic_hits.append((info.key.loc(), s))

    def is_entry(self, info: FuncInfo) -> bool:
        return info.is_endpoint or info.is_worker_like


def _read_py(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return None


def build_index() -> Index:
    idx = Index()
    targets: list[Path] = list(SCAN_FILES)
    for d in SCAN_DIRS:
        if d.exists():
            targets.extend(d.rglob("*.py"))
    seen: set[Path] = set()
    for path in targets:
        if path in seen or not path.exists():
            continue
        seen.add(path)
        sp = str(path)
        if any(frag in sp for frag in SKIP_FRAGMENTS):
            continue
        tree = _read_py(path)
        if tree is None:
            continue
        try:
            rel = str(path.relative_to(ROOT))
        except ValueError:
            rel = sp
        for info in _build_func_registry(rel, tree):
            idx.add(info)
    return idx


def _upstream_chains(
    idx: Index,
    start: FuncInfo,
    max_hops: int = 6,
    max_chains: int = 12,
) -> tuple[list[list[str]], str]:
    """从 start 函数向上 BFS 调用图，找到入口 (端点/worker)。

    返回 (chains, confidence)。chains 每条是 ["name @loc", ...] 从起点到入口。
    confidence:
        static_confirmed — 起点本身就是入口
        call_name_match  — 通过函数名匹配上溯到入口 (中等)
        needs_human      — 上溯不到任何入口 (孤立写边)
    """
    if idx.is_entry(start):
        tag = "endpoint" if start.is_endpoint else "worker"
        label = start.endpoint_route or start.simple_name
        return [[f"{start.simple_name} [{tag}:{label}] @{start.key.loc()}"]], "static_confirmed"

    # BFS over simple-name call graph
    chains: list[list[str]] = []
    # queue holds (current_simple_name, path_of_labels, depth)
    start_label = f"{start.simple_name} @{start.key.loc()}"
    queue: list[tuple[str, list[str], int]] = [(start.simple_name, [start_label], 0)]
    visited: set[str] = {start.simple_name}
    found_entry = False

    while queue and len(chains) < max_chains:
        name, path, depth = queue.pop(0)
        if depth >= max_hops:
            continue
        callers = idx.callers_of.get(name, set())
        for caller_name in sorted(callers):
            # 找该 caller 的 FuncInfo (取第一个;同名取代表)
            caller_infos = idx.by_name.get(caller_name, [])
            entry_info = next((ci for ci in caller_infos if idx.is_entry(ci)), None)
            if entry_info is not None:
                tag = "endpoint" if entry_info.is_endpoint else "worker"
                label = entry_info.endpoint_route or entry_info.simple_name
                chains.append(path + [f"{caller_name} [{tag}:{label}] @{entry_info.key.loc()}"])
                found_entry = True
                if len(chains) >= max_chains:
                    break
                continue
            if caller_name in visited:
                continue
            visited.add(caller_name)
            rep = caller_infos[0] if caller_infos else None
            loc = f" @{rep.key.loc()}" if rep else ""
            queue.append((caller_name, path + [f"{caller_name}{loc}"], depth + 1))

    if found_entry:
        return chains, "call_name_match"
    # 没找到入口:把已探出的最长几条链返回作线索
    leftover: list[list[str]] = []
    if not chains:
        # 至少给出直接 callers
        direct = sorted(idx.callers_of.get(start.simple_name, set()))
        if direct:
            for c in direct[:6]:
                rep = idx.by_name.get(c, [None])[0]
                loc = f" @{rep.key.loc()}" if rep else ""
                leftover.append([start_label, f"{c}{loc}"])
        else:
            leftover.append([start_label, "(no caller found — orphan write)"])
    return (chains or leftover), "needs_human"


# ────────────────────────────────────────────────────────────────────
# 账本组装 (按表)
# ────────────────────────────────────────────────────────────────────
def collect_edges_for_table(
    idx: Index,
    table: str,
    with_chain: bool,
) -> tuple[list[WriteEdge], list[ReadEdge]]:
    tl = table.lower()
    writes: list[WriteEdge] = []
    reads: list[ReadEdge] = []

    for info in idx.funcs:
        ins_hit = False
        upd_hit = False
        from_hit = False
        join_hit = False
        where_texts: list[str] = []

        for sql in info.sql_strings:
            tabs = _extract_tables(sql)
            if table in tabs["insert"] or tl in {t.lower() for t in tabs["insert"]}:
                ins_hit = True
            if table in tabs["update"] or tl in {t.lower() for t in tabs["update"]}:
                upd_hit = True
            if tl in {t.lower() for t in tabs["from"]}:
                from_hit = True
                where_texts.extend(_extract_where(sql))
            if tl in {t.lower() for t in tabs["join"]}:
                join_hit = True
                where_texts.extend(_extract_where(sql))

        if ins_hit or upd_hit:
            op = "+".join([x for x, h in (("INSERT", ins_hit), ("UPDATE", upd_hit)) if h])
            if with_chain:
                chains, conf = _upstream_chains(idx, info)
            else:
                chains, conf = [], "static_confirmed"
            writes.append(WriteEdge(table=table, func=info.key, op=op, chains=chains, confidence=conf))

        if from_hit or join_hit:
            op = "+".join([x for x, h in (("SELECT-FROM", from_hit), ("JOIN", join_hit)) if h])
            reads.append(ReadEdge(
                table=table,
                func=info.key,
                op=op,
                where_texts=sorted(set(where_texts))[:8],
            ))

    return writes, reads


# ────────────────────────────────────────────────────────────────────
# 经验层 (只读真库)
# ────────────────────────────────────────────────────────────────────
@dataclass
class TableStats:
    table: str
    exists: bool = False
    row_count: int | None = None
    columns: list[str] = field(default_factory=list)
    source_type_dist: list[tuple[str, int]] = field(default_factory=list)
    origin_dist: list[tuple[str, int]] = field(default_factory=list)
    latest_created_at: str | None = None
    error: str | None = None


def _open_ro(db_path: str) -> sqlite3.Connection:
    """immutable=1 只读打开;绝不写。"""
    uri = f"file:{db_path}?immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def probe_table(conn: sqlite3.Connection, table: str) -> TableStats:
    st = TableStats(table=table)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not row:
            st.exists = False
            return st
        st.exists = True
        st.columns = [r["name"] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()]
        st.row_count = int(conn.execute(f'SELECT COUNT(*) AS n FROM "{table}"').fetchone()["n"])

        colset = {c.lower() for c in st.columns}
        if "source_type" in colset:
            st.source_type_dist = [
                (str(r["source_type"]), int(r["n"]))
                for r in conn.execute(
                    f'SELECT source_type, COUNT(*) AS n FROM "{table}" '
                    f"GROUP BY source_type ORDER BY n DESC LIMIT 12"
                ).fetchall()
            ]
        if "origin" in colset:
            st.origin_dist = [
                (str(r["origin"]), int(r["n"]))
                for r in conn.execute(
                    f'SELECT origin, COUNT(*) AS n FROM "{table}" '
                    f"GROUP BY origin ORDER BY n DESC LIMIT 12"
                ).fetchall()
            ]
        for col in ("created_at", "updated_at", "ingested_at"):
            if col in colset:
                r = conn.execute(f'SELECT MAX("{col}") AS m FROM "{table}"').fetchone()
                if r and r["m"]:
                    st.latest_created_at = f"{col}={r['m']}"
                    break
    except sqlite3.Error as exc:
        st.error = str(exc)
    return st


def list_all_db_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [r["name"] for r in rows]


# ────────────────────────────────────────────────────────────────────
# 输出渲染
# ────────────────────────────────────────────────────────────────────
def _confidence_for_write(w: WriteEdge, dyn_func_locs: set[str]) -> str:
    if w.func.loc() in dyn_func_locs:
        return "needs_human"
    return w.confidence


def render_table_section(
    table: str,
    writes: list[WriteEdge],
    reads: list[ReadEdge],
    stats: TableStats | None,
    dyn_func_locs: set[str],
) -> str:
    lines: list[str] = []
    lines.append(f"## `{table}`")
    lines.append("")

    # 经验层
    if stats is not None:
        if not stats.exists:
            lines.append(f"- 经验层: 真库**无此表** (静态边 {len(writes)}写/{len(reads)}读)")
        elif stats.error:
            lines.append(f"- 经验层: 读取出错 — {stats.error}")
        else:
            extra = []
            if stats.latest_created_at:
                extra.append(f"最近写入 {stats.latest_created_at}")
            extra_s = (" · " + " · ".join(extra)) if extra else ""
            lines.append(f"- 经验层: **{stats.row_count} 行**{extra_s}")
            if stats.source_type_dist:
                dist = ", ".join(f"{k}:{v}" for k, v in stats.source_type_dist)
                lines.append(f"  - source_type 分布: {dist}")
            if stats.origin_dist:
                dist = ", ".join(f"{k}:{v}" for k, v in stats.origin_dist)
                lines.append(f"  - origin 分布: {dist}")
        lines.append("")

    # 写边
    lines.append(f"### 写边 ({len(writes)})")
    if not writes:
        warn = ""
        if stats and stats.exists and (stats.row_count or 0) > 0:
            warn = "  ⚠️ **0 写边但真库有行 → needs_human (写入路径在静态扫描盲区:可能动态表名/ORM/外部进程)**"
        lines.append(f"- (无静态写边){warn}")
    else:
        for w in sorted(writes, key=lambda x: x.func.loc()):
            conf = _confidence_for_write(w, dyn_func_locs)
            lines.append(f"- `{w.op}` @ **{w.func.qualname}** `{w.func.loc()}` — _{conf}_")
            for chain in w.chains[:6]:
                lines.append(f"    - chain: {'  ←  '.join(chain)}")
    lines.append("")

    # 读边
    lines.append(f"### 读边 ({len(reads)})")
    if not reads:
        lines.append("- (无静态读边)")
    else:
        for r in sorted(reads, key=lambda x: x.func.loc()):
            lines.append(f"- `{r.op}` @ **{r.func.qualname}** `{r.func.loc()}` — _{r.confidence}_")
            for w in r.where_texts[:5]:
                lines.append(f"    - WHERE: `{w}`")
    lines.append("")
    return "\n".join(lines)


def render_console(
    table: str,
    writes: list[WriteEdge],
    reads: list[ReadEdge],
    stats: TableStats | None,
    dyn_func_locs: set[str],
) -> str:
    return render_table_section(table, writes, reads, stats, dyn_func_locs)


# ────────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="数据流账本:后端 SQL 写/读边 AST 静态分析 (纯只读)")
    p.add_argument("tables", nargs="*", help="要分析的表名 (留空且无 --all 报错)")
    p.add_argument("--all", action="store_true", help="分析所有表 (静态扫到的 + 真库里的并集)")
    p.add_argument("--db", default=None, help="真库路径 (immutable=1 只读连接)")
    p.add_argument("--chain", action="store_true", help="写边上溯调用链到入口")
    p.add_argument("--out", default=None, help="落盘 markdown 账本路径")
    args = p.parse_args(argv)

    if not args.tables and not args.all:
        p.error("需指定表名，或用 --all")

    print("→ 构建函数索引 (AST)…", file=sys.stderr)
    idx = build_index()
    print(f"  收录函数 {len(idx.funcs)} 个 (含嵌套)；动态 SQL 命中 {len(idx.dynamic_hits)} 处", file=sys.stderr)

    dyn_func_locs = {loc for loc, _ in idx.dynamic_hits}

    # 真库连接
    conn: sqlite3.Connection | None = None
    if args.db:
        try:
            conn = _open_ro(args.db)
            print(f"  真库 (只读 immutable=1): {args.db}", file=sys.stderr)
        except sqlite3.Error as exc:
            print(f"  ⚠️ 无法打开真库: {exc}", file=sys.stderr)
            conn = None

    # 决定表集合
    if args.all:
        static_tables: set[str] = set()
        for info in idx.funcs:
            for sql in info.sql_strings:
                t = _extract_tables(sql)
                static_tables |= t["insert"] | t["update"] | t["from"] | t["join"]
        db_tables = set(list_all_db_tables(conn)) if conn else set()
        tables = sorted(static_tables | db_tables)
    else:
        tables = list(args.tables)

    # 逐表
    sections: list[str] = []
    zero_write_has_rows: list[tuple[str, int]] = []
    for table in tables:
        writes, reads = collect_edges_for_table(idx, table, with_chain=args.chain)
        stats = probe_table(conn, table) if conn else None
        sec = render_table_section(table, writes, reads, stats, dyn_func_locs)
        sections.append(sec)
        if not args.out:  # 单表 eval 模式:打到 stdout
            print(sec)
        if stats and stats.exists and (stats.row_count or 0) > 0 and not writes:
            zero_write_has_rows.append((table, stats.row_count or 0))

    # 盲区清单
    blind_lines: list[str] = []
    blind_lines.append("## 盲区清单 (接通排查重点)\n")
    blind_lines.append("### 0 写边但真库有行 (写入路径在静态扫描盲区)\n")
    if zero_write_has_rows:
        for t, n in sorted(zero_write_has_rows, key=lambda x: -x[1]):
            blind_lines.append(f"- `{t}` — {n} 行,0 静态写边 → needs_human")
    else:
        blind_lines.append("- (无)")
    blind_lines.append("\n### needs_human 动态表名 (f-string / 拼接 SQL)\n")
    if idx.dynamic_hits:
        seen_loc: set[str] = set()
        for loc, sample in idx.dynamic_hits:
            if loc in seen_loc:
                continue
            seen_loc.add(loc)
            blind_lines.append(f"- `{loc}` — `{sample}`")
    else:
        blind_lines.append("- (无)")
    blind_section = "\n".join(blind_lines)

    if not args.out:
        print("\n" + blind_section)

    # 落盘
    if args.out:
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = ROOT / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        header = [
            "# 数据中心 · 数据流账本 (机器生成)",
            "",
            f"> 工具: `scripts/data_flow_ledger.py` · AST 静态分析 + immutable=1 只读经验层",
            f"> 真库: `{args.db or '(未连)'}`",
            f"> 收录函数 {len(idx.funcs)} 个 · 覆盖表 {len(tables)} 张 · 调用链上溯 {'开' if args.chain else '关'}",
            "",
            "置信度: `static_confirmed`=字面表名直接确证 · "
            "`call_name_match`=调用链靠函数名匹配 · "
            "`needs_human`=动态表名/0写边有行。",
            "",
            "---",
            "",
        ]
        body = "\n".join(header) + "\n".join(sections) + "\n\n---\n\n" + blind_section + "\n"
        out_path.write_text(body, encoding="utf-8")
        print(f"\n✓ 账本落盘: {out_path}", file=sys.stderr)
        print(f"  0写边有行: {len(zero_write_has_rows)} 张 · 动态表名命中: {len(idx.dynamic_hits)} 处", file=sys.stderr)

    if conn:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
